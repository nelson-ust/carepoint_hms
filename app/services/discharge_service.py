# app/services/discharge_service.py
from __future__ import annotations

"""
Inpatient discharge service.

The discharge service is the close-out boundary for an admission. It is
intentionally a thin orchestrator that composes:

- :class:`AdmissionRepository`           — flip the admission status
- :class:`DischargeRepository`           — persist the clinical summary
- :mod:`app.utils.charge_capture`        — capture any outstanding bed-day fees
- :mod:`app.utils.visit_routing`         — optionally close the visit
- :mod:`app.utils.security_event_util`   — audit trail

Steps in :meth:`DischargeService.discharge`:

1. Resolve the admission (must be in an open state).
2. Capture any uncaptured bed-day charges through the discharge date.
3. Free the bed (status -> AVAILABLE).
4. Mark the admission DISCHARGED with ``actual_discharge_at`` set.
5. Persist a :class:`Discharge` record with the clinical summary.
6. If the admission was the visit's last open clinical event, mark the
   visit COMPLETED.
7. Record a ``PATIENT_DISCHARGED`` security event with the bed-day capture
   details for finance traceability.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import AdmissionStatus, BedStatus, VisitFlowStepStatus, VisitStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import Admission, Discharge, VisitFlowStep
from app.repositories.admission_repository import AdmissionRepository
from app.repositories.discharge_repository import DischargeRepository
from app.schemas.discharge_schema import DischargeCreateSchema
from app.utils.charge_capture import capture_bed_day_charges_for_admission
from app.utils.discharge_readiness import check_admission_ready_to_discharge
from app.utils.security_event_util import record_security_event
from app.utils.visit_routing import end_visit


# Open admission states — only these can be discharged. Other states (CANCELLED,
# DECEASED, DISCHARGED) are already terminal and cannot be discharged again.
_OPEN_STATES = {
    AdmissionStatus.PENDING,
    AdmissionStatus.ADMITTED,
    AdmissionStatus.TRANSFERRED,
}


class DischargeService:
    """Service layer for the discharge close-out."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DischargeRepository(db)
        self.admission_repository = AdmissionRepository(db)

    # ============================================================
    # READ
    # ============================================================

    def get(self, discharge_id: int) -> Discharge:
        """Return the discharge record by id, raising NotFoundError if missing."""
        return self.repository.get_required_by_id(discharge_id)

    def get_for_admission(self, admission_id: int) -> Optional[Discharge]:
        """Return the existing discharge tied to an admission, or None."""
        return self.repository.get_for_admission(admission_id)

    def readiness_for_admission(self, admission_id: int) -> dict:
        """
        Inspect an admission's readiness for discharge without performing the
        discharge. Useful for the discharge UI ("ready to discharge?" panel).
        """
        admission = self.admission_repository.get_required_by_id(admission_id)
        ready, blockers = check_admission_ready_to_discharge(
            self.db, visit_id=admission.visit_id
        )
        return {
            "admission_id": admission.id,
            "visit_id": admission.visit_id,
            "is_ready": ready,
            "blockers": blockers,
        }

    # ============================================================
    # DISCHARGE
    # ============================================================

    def discharge(
        self,
        payload: DischargeCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """
        Close out an admission.

        Returns a dict the route layer can serialise directly.
        """
        admission = self.admission_repository.get_required_by_id(payload.admission_id)

        # Reject double-discharge or discharge of already-terminal admissions.
        if admission.admission_status not in _OPEN_STATES:
            raise BadRequestError(
                message="Admission is no longer in an open state.",
                detail={
                    "admission_id": admission.id,
                    "status": str(admission.admission_status),
                },
            )
        if self.repository.get_for_admission(admission.id) is not None:
            raise BadRequestError(
                message="Admission has already been discharged.",
                detail={"admission_id": admission.id},
            )

        # ----- Discharge readiness gate -----------------------------------
        # Refuse discharge while there are open lab/radiology orders,
        # undispensed prescriptions, or open theatre cases on the visit.
        # Allow ``force=True`` for AMA / supervisor overrides.
        if not getattr(payload, "force", False):
            ready, blockers = check_admission_ready_to_discharge(
                self.db,
                visit_id=admission.visit_id,
            )
            if not ready:
                raise BadRequestError(
                    message=(
                        "Cannot discharge: there are still open clinical orders "
                        "on this admission's visit."
                    ),
                    detail={
                        "admission_id": admission.id,
                        "visit_id": admission.visit_id,
                        "blockers": blockers,
                        "hint": "Pass force=true to override (e.g. AMA discharge).",
                    },
                )

        # Resolve the discharge timestamp once. We use it for both the
        # clinical record and the bed-day capture window.
        discharge_dt = payload.discharge_date or datetime.now(timezone.utc)
        through_date = discharge_dt.date()

        # Capture any outstanding bed-day charges through the discharge date
        # so finance has the full inpatient bill on the cashier workstation.
        bed_day_charges_captured = 0
        if payload.capture_final_bed_day_charges and admission.visit_id is not None:
            summary = capture_bed_day_charges_for_admission(
                self.db,
                admission=admission,
                through_date=through_date,
            )
            bed_day_charges_captured = int(summary.get("charges_captured", 0))

        # Free the bed (if any). This is the moment the bed becomes available
        # to the admission queue again.
        if admission.bed_id is not None:
            bed = self.admission_repository.get_bed(admission.bed_id)
            if bed is not None:
                self.admission_repository.update_bed_status(bed, BedStatus.AVAILABLE)

        # Flip the admission to DISCHARGED with the final timestamp.
        admission.admission_status = AdmissionStatus.DISCHARGED
        admission.actual_discharge_at = discharge_dt
        self.admission_repository.save(admission)

        # Persist the clinical discharge record. The unique constraint on
        # admission_id ensures the at-most-one rule is enforced at the DB layer.
        discharge = self.repository.create_discharge(
            admission_id=admission.id,
            discharged_by_staff_id=payload.discharged_by_staff_id,
            discharge_date=discharge_dt,
            discharge_condition=payload.discharge_condition,
            discharge_summary=payload.discharge_summary,
            follow_up_instruction=payload.follow_up_instruction,
        )

        # Optionally close the visit when the admission was its last open
        # clinical event.
        visit_completed = False
        if (
            payload.end_visit_if_only_open_event
            and admission.visit_id is not None
            and self._admission_was_last_open_event(visit_id=admission.visit_id)
        ):
            end_visit(
                self.db,
                visit_id=admission.visit_id,
                actor_user_id=actor_user_id,
                note="Visit ended at discharge.",
            )
            visit_completed = True

        # Audit. We include the bed-day capture summary so a single security
        # query can correlate the discharge with the financial close-out.
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PATIENT_DISCHARGED",
            severity="INFO",
            event_detail=(
                f"Admission {admission.id} discharged at {discharge_dt.isoformat()}."
            ),
            event_metadata={
                "admission_id": admission.id,
                "patient_id": admission.patient_id,
                "visit_id": admission.visit_id,
                "bed_day_charges_captured": bed_day_charges_captured,
                "visit_completed": visit_completed,
            },
        )

        self.db.commit()
        return {
            "discharge": self.repository.get_required_by_id(discharge.id),
            "admission_id": admission.id,
            "bed_day_charges_captured": bed_day_charges_captured,
            "visit_completed": visit_completed,
        }

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _admission_was_last_open_event(self, *, visit_id: int) -> bool:
        """
        Return True when the only open clinical event on the visit was the
        admission we are discharging.

        We use VisitFlowStep as the source of truth for "what's still open".
        If every step is COMPLETED / SKIPPED / CANCELLED / FAILED, the visit
        is effectively ready to close.
        """
        open_states = {
            VisitFlowStepStatus.PENDING,
            VisitFlowStepStatus.QUEUED,
            VisitFlowStepStatus.CALLED,
            VisitFlowStepStatus.IN_PROGRESS,
        }
        # SQLAlchemy doesn't support `not in_` against an enum collection in
        # all dialects without explicit cast, so we filter in Python after a
        # cheap fetch.
        steps = (
            self.db.query(VisitFlowStep)
            .filter(VisitFlowStep.visit_id == visit_id, VisitFlowStep.is_deleted.is_(False))
            .all()
        )
        for step in steps:
            if step.status in open_states:
                return False
        return True
