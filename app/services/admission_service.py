# app/services/admission_service.py
from __future__ import annotations

"""
Inpatient admission service.

The admission service is the orchestrator that ties together:

- :class:`AdmissionRepository`  — admission row + bed/ward lookups
- :mod:`app.utils.charge_capture` — bed-day charge capture into the visit's billing
- :mod:`app.utils.security_event_util` — security audit trail for admit/transfer/cancel
- :class:`VisitFlowRepository` (indirectly via routing helpers) — when an
  admission is part of an active visit, the patient's location is mirrored
  into the visit-flow timeline so the queue / SDP UI stays consistent.

Lifecycle
---------
PENDING (booked) -> ADMITTED -> [TRANSFERRED, ADMITTED, ...] -> DISCHARGED
                                                            \\-> CANCELLED
                                                            \\-> DECEASED

Key business rules
------------------
- A bed cannot be assigned to two active admissions concurrently.
- Bed-day charges are captured per (admission, calendar_date) tuple with an
  idempotent ``source_reference`` so re-running the rollover is safe.
- When the visit is reachable, admit / transfer events also flush a
  ``VisitFlowStep`` so the queue / SDP timeline reflects the patient's bed.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import AdmissionStatus, BedStatus, VisitStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Admission
from app.repositories.admission_repository import AdmissionRepository
from app.schemas.admission_schemas import (
    AdmissionBedDayCaptureSchema,
    AdmissionCreateSchema,
    AdmissionFromVisitConvertSchema,
    AdmissionStatusUpdateSchema,
    AdmissionTransferBedSchema,
)
from app.utils.charge_capture import capture_bed_day_charges_for_admission
from app.utils.security_event_util import record_security_event
from app.utils.visit_routing import route_visit_to_next_sdp


# Admissions that are still "open" — they hold a bed and accrue bed-day fees.
_OPEN_STATES = {
    AdmissionStatus.PENDING,
    AdmissionStatus.ADMITTED,
    AdmissionStatus.TRANSFERRED,
}


class AdmissionService:
    """Service layer for the inpatient admission workflow."""

    def __init__(self, db: Session) -> None:
        # The session is owned by the FastAPI request scope; this service
        # commits at coherent boundaries (admit, transfer, status-update,
        # bed-day-capture). Repositories never commit.
        self.db = db
        self.repository = AdmissionRepository(db)

    # ============================================================
    # READ
    # ============================================================

    def get(self, admission_id: int) -> Admission:
        """Return one admission by ID, raising NotFoundError if missing."""
        return self.repository.get_required_by_id(admission_id)

    def list_active_for_ward(self, ward_id: int) -> list[Admission]:
        """Active (non-closed) admissions sitting in a given ward."""
        # Used by the ward-board UI to render the bed map.
        return self.repository.list_active_for_ward(ward_id)

    def list_admissions(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        patient_id: Optional[int] = None,
        ward_id: Optional[int] = None,
        status: Optional[str] = None,
        facility_id: Optional[int] = None,
    ):
        """Paginated admission list with the most common filters."""
        # Translate the optional string status filter into the enum so the
        # repository can build the SQL filter cleanly.
        status_enum: Optional[AdmissionStatus] = None
        if status:
            try:
                status_enum = AdmissionStatus(status.strip().upper())
            except ValueError as exc:
                raise BadRequestError(
                    message="Invalid admission status filter.",
                    detail={"status": status},
                ) from exc
        return self.repository.list_admissions(
            skip=skip, limit=limit,
            patient_id=patient_id, ward_id=ward_id,
            status=status_enum, facility_id=facility_id,
        )

    # ============================================================
    # ADMIT
    # ============================================================

    def admit(
        self,
        payload: AdmissionCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Admission:
        """
        Create an admission, assign a bed, and capture the first bed-day charge.

        Steps
        -----
        1. Validate ward + bed exist and the bed is AVAILABLE.
        2. If ``bed_id`` is missing, auto-pick the first AVAILABLE bed in the
           ward (returns 400 if the ward is full).
        3. Persist the admission row with status ADMITTED.
        4. Mark the bed OCCUPIED.
        5. If ``capture_first_bed_day_charge`` is True and the visit is set,
           capture today's bed-day charge into the visit's open billing.
        6. Record a ``PATIENT_ADMITTED`` security event with the bed/ward IDs.
        """
        ward = self.repository.get_ward(payload.ward_id)
        if ward is None:
            raise NotFoundError(
                message="Ward not found.",
                detail={"ward_id": payload.ward_id},
            )

        # Resolve the target bed: explicit override or auto-pick.
        bed = None
        if payload.bed_id is not None:
            bed = self.repository.get_bed(payload.bed_id)
            if bed is None:
                raise NotFoundError(
                    message="Bed not found.",
                    detail={"bed_id": payload.bed_id},
                )
            if bed.ward_id != ward.id:
                raise BadRequestError(
                    message="Bed does not belong to the supplied ward.",
                    detail={"bed_id": bed.id, "bed_ward_id": bed.ward_id, "ward_id": ward.id},
                )
            if bed.bed_status != BedStatus.AVAILABLE:
                raise BadRequestError(
                    message="Bed is not currently available.",
                    detail={"bed_id": bed.id, "bed_status": str(bed.bed_status)},
                )
        else:
            bed = self.repository.first_available_bed(ward.id)
            if bed is None:
                raise BadRequestError(
                    message="No available beds in the selected ward.",
                    detail={"ward_id": ward.id},
                )

        # If a visit is supplied, ensure the visit is open. A closed visit
        # cannot accumulate inpatient charges.
        if payload.visit_id is not None:
            visit = self.repository.get_visit(payload.visit_id)
            if visit is None:
                raise NotFoundError(
                    message="Visit not found.",
                    detail={"visit_id": payload.visit_id},
                )
            if visit.status in {VisitStatus.COMPLETED, VisitStatus.CANCELLED}:
                raise BadRequestError(
                    message="Cannot admit on a closed visit.",
                    detail={"visit_id": visit.id, "visit_status": str(visit.status)},
                )

        # Persist the admission with the resolved bed/ward.
        admitted_at = payload.admitted_at or datetime.now(timezone.utc)
        admission = self.repository.create_admission(
            patient_id=payload.patient_id,
            visit_id=payload.visit_id,
            ward_id=ward.id,
            bed_id=bed.id,
            admitting_staff_id=payload.admitting_staff_id,
            admission_reason=payload.admission_reason,
            admitted_at=admitted_at,
            expected_discharge_at=payload.expected_discharge_at,
            status=AdmissionStatus.ADMITTED,
        )

        # Mark the bed OCCUPIED so it can't be re-assigned mid-flight.
        self.repository.update_bed_status(bed, BedStatus.OCCUPIED)

        # Capture the very first bed-day charge so finance teams see the
        # admission immediately on the cashier workstation.
        bed_day_summary = {"charges_captured": 0, "total_amount_captured": Decimal("0")}
        if payload.capture_first_bed_day_charge and admission.visit_id is not None:
            bed_day_summary = capture_bed_day_charges_for_admission(
                self.db,
                admission=admission,
                through_date=admitted_at.date(),
            )

        # Audit trail. Bed-day capture details are included so a security
        # reviewer can correlate financial and clinical rows in one query.
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PATIENT_ADMITTED",
            severity="INFO",
            event_detail=(
                f"Patient {admission.patient_id} admitted to ward {ward.id} bed {bed.id}."
            ),
            event_metadata={
                "admission_id": admission.id,
                "patient_id": admission.patient_id,
                "visit_id": admission.visit_id,
                "ward_id": ward.id,
                "bed_id": bed.id,
                "bed_day_charges_captured": int(bed_day_summary.get("charges_captured", 0)),
                "bed_day_amount_captured": str(bed_day_summary.get("total_amount_captured", Decimal("0"))),
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(admission.id)

    # ============================================================
    # ER → ADMISSION CONVERT
    # ============================================================

    def convert_visit_to_admission(
        self,
        payload: AdmissionFromVisitConvertSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Admission:
        """
        Single-call hand-off from an ER / OPD visit to an inpatient admission.

        Steps:
        1. Resolve the open visit (must not be closed).
        2. Reuse the visit's ``patient_id`` so the OPD bill rolls forward
           into the same billing.
        3. Delegate to :meth:`admit` to do the bed/ward + first bed-day
           capture machinery.
        4. Optionally route the visit to a destination SDP (typically the
           ward / inpatient-care SDP) so the queue / SDP timeline mirrors
           the patient's new location.
        """
        visit = self.repository.get_visit(payload.visit_id)
        if visit is None:
            raise NotFoundError(
                message="Visit not found.",
                detail={"visit_id": payload.visit_id},
            )
        if visit.status in {VisitStatus.COMPLETED, VisitStatus.CANCELLED}:
            raise BadRequestError(
                message="Cannot convert a closed visit to an admission.",
                detail={"visit_id": visit.id, "visit_status": str(visit.status)},
            )

        admit_payload = AdmissionCreateSchema(
            patient_id=visit.patient_id,
            visit_id=visit.id,
            ward_id=payload.ward_id,
            bed_id=payload.bed_id,
            admitting_staff_id=payload.admitting_staff_id,
            admission_reason=payload.admission_reason,
            expected_discharge_at=payload.expected_discharge_at,
            capture_first_bed_day_charge=payload.capture_first_bed_day_charge,
        )
        admission = self.admit(admit_payload, actor_user_id=actor_user_id)

        # Reflect the move on the visit timeline if asked. We open a fresh
        # txn boundary because :meth:`admit` already committed.
        if payload.route_to_service_delivery_point_id is not None:
            try:
                route_visit_to_next_sdp(
                    self.db,
                    visit_id=visit.id,
                    target_service_delivery_point_id=payload.route_to_service_delivery_point_id,
                    routed_by_id=actor_user_id,
                    notes=f"Converted to inpatient admission {admission.admission_no}.",
                )
                self.db.commit()
            except Exception:
                # Routing failure should not unwind the admission. The
                # admission row is the source of truth.
                self.db.rollback()

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="VISIT_CONVERTED_TO_ADMISSION",
            severity="INFO",
            event_detail=(
                f"Visit {visit.id} converted to inpatient admission "
                f"{admission.admission_no}."
            ),
            event_metadata={
                "visit_id": visit.id,
                "admission_id": admission.id,
                "ward_id": admission.ward_id,
                "bed_id": admission.bed_id,
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(admission.id)

    # ============================================================
    # TRANSFER
    # ============================================================

    def transfer_bed(
        self,
        admission_id: int,
        payload: AdmissionTransferBedSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Admission:
        """
        Move an admitted patient to a new bed.

        - The old bed flips back to AVAILABLE.
        - The new bed must be AVAILABLE; it flips to OCCUPIED.
        - The admission's ``ward_id`` and ``bed_id`` are updated.
        - Status moves from ADMITTED to TRANSFERRED on first transfer; subsequent
          transfers keep the TRANSFERRED status. (We don't bounce back to
          ADMITTED so the audit trail is clean.)
        """
        admission = self.repository.get_required_by_id(admission_id)
        if admission.admission_status not in _OPEN_STATES:
            raise BadRequestError(
                message="Cannot transfer an admission that is not active.",
                detail={"admission_id": admission.id, "status": str(admission.admission_status)},
            )

        new_bed = self.repository.get_bed(payload.new_bed_id)
        if new_bed is None:
            raise NotFoundError(
                message="Target bed not found.",
                detail={"bed_id": payload.new_bed_id},
            )
        if new_bed.bed_status != BedStatus.AVAILABLE:
            raise BadRequestError(
                message="Target bed is not available.",
                detail={"bed_id": new_bed.id, "bed_status": str(new_bed.bed_status)},
            )

        # If new_ward_id was supplied, validate the bed belongs to it. Otherwise,
        # infer the ward from the bed.
        if payload.new_ward_id is not None and payload.new_ward_id != new_bed.ward_id:
            raise BadRequestError(
                message="Target bed does not belong to the supplied target ward.",
                detail={
                    "bed_id": new_bed.id,
                    "bed_ward_id": new_bed.ward_id,
                    "target_ward_id": payload.new_ward_id,
                },
            )

        old_bed_id = admission.bed_id
        old_ward_id = admission.ward_id

        # Free the old bed if there is one.
        if admission.bed_id is not None:
            old_bed = self.repository.get_bed(admission.bed_id)
            if old_bed is not None:
                self.repository.update_bed_status(old_bed, BedStatus.AVAILABLE)

        # Move the admission to the new bed/ward.
        admission.bed_id = new_bed.id
        admission.ward_id = new_bed.ward_id
        admission.admission_status = AdmissionStatus.TRANSFERRED
        self.repository.save(admission)

        # Mark the new bed OCCUPIED.
        self.repository.update_bed_status(new_bed, BedStatus.OCCUPIED)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PATIENT_BED_TRANSFER",
            severity="INFO",
            event_detail=(
                f"Admission {admission.id} transferred from bed {old_bed_id} to bed {new_bed.id}."
            ),
            event_metadata={
                "admission_id": admission.id,
                "from_bed_id": old_bed_id,
                "to_bed_id": new_bed.id,
                "from_ward_id": old_ward_id,
                "to_ward_id": new_bed.ward_id,
                "reason": payload.reason,
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(admission.id)

    # ============================================================
    # CANCEL / DEATH (non-discharge terminal states)
    # ============================================================

    def update_status(
        self,
        admission_id: int,
        payload: AdmissionStatusUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Admission:
        """
        Move an admission into a non-discharge terminal state (CANCELLED or
        DECEASED). Both also free the bed and stop bed-day accrual.
        """
        admission = self.repository.get_required_by_id(admission_id)
        if admission.admission_status not in _OPEN_STATES:
            raise BadRequestError(
                message="Admission is no longer in an open state.",
                detail={"admission_id": admission.id, "status": str(admission.admission_status)},
            )
        new_status = AdmissionStatus(payload.new_status)

        # Free the bed in both terminal cases.
        if admission.bed_id is not None:
            bed = self.repository.get_bed(admission.bed_id)
            if bed is not None:
                self.repository.update_bed_status(bed, BedStatus.AVAILABLE)

        admission.admission_status = new_status
        admission.actual_discharge_at = datetime.now(timezone.utc)
        self.repository.save(admission)

        # Audit. Bedside reviewers can read the reason directly from
        # event_metadata.
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type=f"ADMISSION_{new_status.value}",
            severity="WARNING",
            event_detail=(
                f"Admission {admission.id} marked {new_status.value}."
            ),
            event_metadata={
                "admission_id": admission.id,
                "patient_id": admission.patient_id,
                "reason": payload.reason,
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(admission.id)

    # ============================================================
    # BED-DAY CAPTURE (rollover / pre-discharge)
    # ============================================================

    def capture_bed_day_charges(
        self,
        admission_id: int,
        payload: AdmissionBedDayCaptureSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """
        Capture bed-day charges for an admission up to ``through_date``.

        Idempotent: re-running with the same (admission, through_date) is a
        no-op for already-captured days. Returns a count of newly inserted
        lines and the running total. Used by:
        - the nightly bed-day rollover job
        - cashier "settle bill now" flows
        - the discharge service immediately before close-out
        """
        admission = self.repository.get_required_by_id(admission_id)
        if admission.admission_status not in _OPEN_STATES:
            raise BadRequestError(
                message="Cannot capture bed-day charges on a closed admission.",
                detail={"admission_id": admission.id, "status": str(admission.admission_status)},
            )

        # The actual ledger writes happen in the charge-capture utility. The
        # service is the boundary that owns the commit.
        summary = capture_bed_day_charges_for_admission(
            self.db,
            admission=admission,
            through_date=payload.through_date,
        )
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="BED_DAY_CAPTURE",
            severity="INFO",
            event_detail=(
                f"Bed-day charges captured for admission {admission.id} "
                f"through {payload.through_date}."
            ),
            event_metadata={
                "admission_id": admission.id,
                "through_date": payload.through_date.isoformat(),
                "charges_captured": int(summary.get("charges_captured", 0)),
                "total_amount_captured": str(summary.get("total_amount_captured", Decimal("0"))),
            },
        )

        self.db.commit()
        return {
            "admission_id": admission.id,
            "charges_captured": int(summary.get("charges_captured", 0)),
            "total_amount_captured": Decimal(summary.get("total_amount_captured", Decimal("0"))),
            "captured_through": payload.through_date,
        }
