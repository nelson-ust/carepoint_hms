# app/services/surgical_service.py
from __future__ import annotations

"""
Service layer for the Surgical / Theatre module.

Composes repositories, charge-capture, visit-routing, and the security-event
audit log into orchestration units. Service methods commit; repositories only
flush.

Service classes:
- :class:`OperatingTheatreService`     — theatre CRUD + status transitions
- :class:`SurgicalCatalogService`      — surgical-procedure catalog CRUD
- :class:`SurgicalCaseService`         — full case lifecycle BOOKED → COMPLETED
- :class:`SurgicalTeamService`         — add / remove team members
- :class:`SurgicalConsentService`      — consent capture
- :class:`SurgicalChecklistService`    — WHO sign-in / time-out / sign-out
- :class:`AnaesthesiaService`          — anaesthesia record capture
- :class:`TheatreNoteService`          — intra-op notes
- :class:`InstrumentSetService`        — instrument sets + sterilization cycles

Lifecycle for ``SurgicalCase``::

    BOOKED → CONFIRMED → PRE_OP → IN_THEATRE
    → PROCEDURE_STARTED → PROCEDURE_ENDED → POST_OP → COMPLETED

Side effects:
- COMPLETED  → captures one BillingItem ``SURGICAL_CASE:{case_id}`` (idempotent)
              and routes the visit on to ward / inpatient SDP if provided.
- IN_THEATRE → flips the OperatingTheatre status to OCCUPIED.
- COMPLETED / CANCELLED → flips the OperatingTheatre status back to CLEANING.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    SterilizationStatus,
    SurgicalCaseStatus,
    TheatreStatus,
    VisitStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    AnaesthesiaRecord,
    InstrumentSterilizationLog,
    OperatingTheatre,
    SurgicalCase,
    SurgicalConsent,
    SurgicalInstrumentSet,
    SurgicalProcedureCatalog,
    SurgicalSafetyChecklist,
    SurgicalTeamMember,
    TheatreNote,
)
from app.repositories.surgical_repository import (
    AnaesthesiaRepository,
    InstrumentSetRepository,
    InstrumentSterilizationRepository,
    OperatingTheatreRepository,
    SurgicalCaseRepository,
    SurgicalCatalogRepository,
    SurgicalChecklistRepository,
    SurgicalConsentRepository,
    SurgicalTeamRepository,
    TheatreNoteRepository,
)
from app.schemas.surgical_schemas import (
    AnaesthesiaRecordCreateSchema,
    InstrumentSterilizationLogCreateSchema,
    OperatingTheatreCreateSchema,
    OperatingTheatreStatusSchema,
    OperatingTheatreUpdateSchema,
    SurgicalCaseBookSchema,
    SurgicalCaseTransitionSchema,
    SurgicalChecklistRecordSchema,
    SurgicalConsentCreateSchema,
    SurgicalInstrumentSetAssignSchema,
    SurgicalInstrumentSetCreateSchema,
    SurgicalProcedureCatalogCreateSchema,
    SurgicalTeamMemberAddSchema,
    TheatreNoteCreateSchema,
)
from app.utils.charge_capture import (
    add_charge,
    find_billable_service,
    get_or_create_open_billing,
)
from app.utils.security_event_util import record_security_event
from app.utils.visit_routing import route_visit_to_next_sdp


# ============================================================
# OPERATING THEATRE
# ============================================================


class OperatingTheatreService:
    """CRUD over physical theatres + status transitions."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = OperatingTheatreRepository(db)
        self.case_repository = SurgicalCaseRepository(db)

    def get(self, theatre_id: int) -> OperatingTheatre:
        return self.repository.get_required_by_id(theatre_id)

    def list_theatres(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        facility_id: Optional[int] = None,
        emergency_only: bool = False,
        search: Optional[str] = None,
    ):
        normalized_status = (
            TheatreStatus(status.strip().upper()) if status else None
        )
        return self.repository.list_theatres(
            skip=skip,
            limit=limit,
            status=normalized_status,
            facility_id=facility_id,
            emergency_only=emergency_only,
            search=search,
        )

    def create(self, payload: OperatingTheatreCreateSchema) -> OperatingTheatre:
        data = payload.model_dump(exclude_unset=True)
        t = self.repository.create(**data)
        self.db.commit()
        return self.repository.get_required_by_id(t.id)

    def update(
        self, theatre_id: int, payload: OperatingTheatreUpdateSchema
    ) -> OperatingTheatre:
        t = self.repository.get_required_by_id(theatre_id)
        updated = self.repository.update(t, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def change_status(
        self,
        theatre_id: int,
        payload: OperatingTheatreStatusSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> OperatingTheatre:
        t = self.repository.get_required_by_id(theatre_id)
        new_status = TheatreStatus(payload.new_status)

        # Guard: cannot mark AVAILABLE while a case still occupies the theatre.
        if new_status == TheatreStatus.AVAILABLE:
            occupant = self.case_repository.open_case_in_theatre(t.id)
            if occupant is not None:
                raise BadRequestError(
                    message="Theatre still has an active case; cannot mark AVAILABLE.",
                    detail={"theatre_id": t.id, "case_id": occupant.id},
                )

        previous = str(t.status)
        t.status = new_status
        self.repository.save(t)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="THEATRE_STATUS_CHANGED",
            severity="INFO",
            event_detail=f"Theatre {t.code} status {previous} → {new_status.value}.",
            event_metadata={
                "theatre_id": t.id,
                "previous_status": previous,
                "new_status": new_status.value,
                "reason": payload.reason,
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(t.id)

    def soft_delete(
        self, theatre_id: int, *, actor_user_id: Optional[int] = None
    ) -> OperatingTheatre:
        t = self.repository.get_required_by_id(theatre_id)
        occupant = self.case_repository.open_case_in_theatre(t.id)
        if occupant is not None:
            raise BadRequestError(
                message="Cannot delete a theatre with an open case.",
                detail={"theatre_id": t.id, "case_id": occupant.id},
            )
        t = self.repository.soft_delete(t)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="THEATRE_DELETED",
            severity="WARNING",
            event_detail=f"Theatre {t.code} soft-deleted.",
            event_metadata={"theatre_id": t.id},
        )
        self.db.commit()
        return t


# ============================================================
# SURGICAL PROCEDURE CATALOG
# ============================================================


class SurgicalCatalogService:
    """CRUD over the surgical-procedure master catalog."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SurgicalCatalogRepository(db)

    def list_procedures(
        self, *, skip: int = 0, limit: int = 50, search: Optional[str] = None
    ):
        return self.repository.list_procedures(skip=skip, limit=limit, search=search)

    def get(self, procedure_id: int) -> SurgicalProcedureCatalog:
        return self.repository.get_required_by_id(procedure_id)

    def create(
        self, payload: SurgicalProcedureCatalogCreateSchema
    ) -> SurgicalProcedureCatalog:
        p = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(p.id)

    def soft_delete(self, procedure_id: int) -> SurgicalProcedureCatalog:
        p = self.repository.get_required_by_id(procedure_id)
        p = self.repository.soft_delete(p)
        self.db.commit()
        return p


# ============================================================
# SURGICAL CASE LIFECYCLE
# ============================================================


# Allowed forward transitions from each status.
_FORWARD_TRANSITIONS: dict[SurgicalCaseStatus, set[SurgicalCaseStatus]] = {
    SurgicalCaseStatus.BOOKED: {
        SurgicalCaseStatus.CONFIRMED,
        SurgicalCaseStatus.PRE_OP,
        SurgicalCaseStatus.CANCELLED,
        SurgicalCaseStatus.POSTPONED,
    },
    SurgicalCaseStatus.CONFIRMED: {
        SurgicalCaseStatus.PRE_OP,
        SurgicalCaseStatus.CANCELLED,
        SurgicalCaseStatus.POSTPONED,
    },
    SurgicalCaseStatus.PRE_OP: {
        SurgicalCaseStatus.IN_THEATRE,
        SurgicalCaseStatus.CANCELLED,
    },
    SurgicalCaseStatus.IN_THEATRE: {
        SurgicalCaseStatus.PROCEDURE_STARTED,
        SurgicalCaseStatus.CANCELLED,
    },
    SurgicalCaseStatus.PROCEDURE_STARTED: {SurgicalCaseStatus.PROCEDURE_ENDED},
    SurgicalCaseStatus.PROCEDURE_ENDED: {SurgicalCaseStatus.POST_OP},
    SurgicalCaseStatus.POST_OP: {SurgicalCaseStatus.COMPLETED},
    SurgicalCaseStatus.POSTPONED: {
        SurgicalCaseStatus.BOOKED,
        SurgicalCaseStatus.CONFIRMED,
        SurgicalCaseStatus.CANCELLED,
    },
}


def _assert_can_transition(
    case: SurgicalCase, target: SurgicalCaseStatus
) -> None:
    if case.status == target:
        return
    allowed = _FORWARD_TRANSITIONS.get(case.status, set())
    if target not in allowed:
        raise BadRequestError(
            message="Illegal surgical case state transition.",
            detail={
                "case_id": case.id,
                "current_status": str(case.status),
                "requested_status": str(target),
                "allowed_next": sorted(s.value for s in allowed),
            },
        )


class SurgicalCaseService:
    """Booking + lifecycle for surgical cases."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SurgicalCaseRepository(db)
        self.catalog_repository = SurgicalCatalogRepository(db)
        self.theatre_repository = OperatingTheatreRepository(db)
        self.team_repository = SurgicalTeamRepository(db)
        self.consent_repository = SurgicalConsentRepository(db)
        self.checklist_repository = SurgicalChecklistRepository(db)

    # ----- queries ---------------------------------------------------------
    def get(self, case_id: int) -> SurgicalCase:
        return self.repository.get_required_by_id(case_id)

    def list_for_visit(self, visit_id: int, *, skip: int = 0, limit: int = 50):
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)

    def list_worklist(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        statuses: Optional[list[str]] = None,
        operating_theatre_id: Optional[int] = None,
        emergency_only: bool = False,
    ):
        normalized = (
            [SurgicalCaseStatus(s.strip().upper()) for s in statuses]
            if statuses
            else None
        )
        return self.repository.list_worklist(
            skip=skip,
            limit=limit,
            statuses=normalized,
            operating_theatre_id=operating_theatre_id,
            emergency_only=emergency_only,
        )

    # ----- booking ---------------------------------------------------------
    def book_case(
        self,
        payload: SurgicalCaseBookSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalCase:
        # Validate procedure
        catalog = self.catalog_repository.get_required_by_id(
            payload.procedure_catalog_id
        )

        # Validate visit (if provided)
        visit = None
        if payload.visit_id is not None:
            visit = self.repository.get_visit(payload.visit_id)
            if visit is None:
                raise NotFoundError(
                    message="Visit not found.",
                    detail={"visit_id": payload.visit_id},
                )
            if visit.status in {VisitStatus.COMPLETED, VisitStatus.CANCELLED}:
                raise BadRequestError(
                    message="Cannot book a surgical case on a closed visit.",
                    detail={"visit_status": str(visit.status)},
                )

        # Validate theatre (if provided)
        if payload.operating_theatre_id is not None:
            self.theatre_repository.get_required_by_id(payload.operating_theatre_id)

        kwargs: dict = dict(
            patient_id=payload.patient_id,
            visit_id=payload.visit_id,
            facility_id=payload.facility_id,
            procedure_catalog_id=catalog.id,
            operating_theatre_id=payload.operating_theatre_id,
            is_emergency=payload.is_emergency,
            scheduled_start_at=payload.scheduled_start_at,
            scheduled_end_at=payload.scheduled_end_at,
            diagnosis_text=payload.diagnosis_text,
        )
        if payload.asa_class:
            from app.core.enums import ASAClass

            kwargs["asa_class"] = ASAClass(payload.asa_class)
        if payload.anaesthesia_type:
            from app.core.enums import AnaesthesiaType

            kwargs["anaesthesia_type"] = AnaesthesiaType(payload.anaesthesia_type)

        case = self.repository.create(**kwargs)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="SURGICAL_CASE_BOOKED",
            severity="INFO",
            event_detail=f"Surgical case {case.case_no} booked.",
            event_metadata={
                "case_id": case.id,
                "patient_id": case.patient_id,
                "visit_id": case.visit_id,
                "is_emergency": case.is_emergency,
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(case.id)

    # ----- transitions -----------------------------------------------------
    def _transition(
        self,
        case_id: int,
        target: SurgicalCaseStatus,
        payload: Optional[SurgicalCaseTransitionSchema],
        *,
        actor_user_id: Optional[int] = None,
        timestamps: Optional[dict[str, datetime]] = None,
        side_effect_after: Optional[callable] = None,
    ) -> SurgicalCase:
        case = self.repository.get_required_by_id(case_id)
        _assert_can_transition(case, target)
        previous = str(case.status)
        case.status = target
        if timestamps:
            for field, value in timestamps.items():
                setattr(case, field, value)
        if payload and payload.findings:
            case.findings_text = payload.findings
        self.repository.save(case)

        if side_effect_after is not None:
            side_effect_after(case, payload)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type=f"SURGICAL_CASE_{target.value}",
            severity="INFO",
            event_detail=(
                f"Surgical case {case.case_no} transitioned {previous} → {target.value}."
            ),
            event_metadata={
                "case_id": case.id,
                "previous_status": previous,
                "new_status": target.value,
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(case.id)

    def confirm(
        self,
        case_id: int,
        payload: SurgicalCaseTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalCase:
        return self._transition(
            case_id,
            SurgicalCaseStatus.CONFIRMED,
            payload,
            actor_user_id=actor_user_id,
        )

    def start_pre_op(
        self,
        case_id: int,
        payload: SurgicalCaseTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalCase:
        # Pre-op can only start once consent is on file.
        case = self.repository.get_required_by_id(case_id)
        if not self.consent_repository.has_consent(case.id):
            raise BadRequestError(
                message="Cannot start pre-op without recorded consent.",
                detail={"case_id": case.id},
            )
        return self._transition(
            case_id,
            SurgicalCaseStatus.PRE_OP,
            payload,
            actor_user_id=actor_user_id,
            timestamps={"pre_op_started_at": datetime.now(timezone.utc)},
        )

    def into_theatre(
        self,
        case_id: int,
        payload: SurgicalCaseTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalCase:
        # Sign-in checklist must be on file before patient enters theatre.
        case = self.repository.get_required_by_id(case_id)
        if not self.checklist_repository.has_phase(case.id, "SIGN_IN"):
            raise BadRequestError(
                message="WHO sign-in checklist must be completed before entering theatre.",
                detail={"case_id": case.id},
            )

        def _occupy_theatre(case: SurgicalCase, _payload):
            if case.operating_theatre_id is not None:
                t = self.theatre_repository.get_required_by_id(
                    case.operating_theatre_id
                )
                t.status = TheatreStatus.OCCUPIED
                self.theatre_repository.save(t)

        return self._transition(
            case_id,
            SurgicalCaseStatus.IN_THEATRE,
            payload,
            actor_user_id=actor_user_id,
            side_effect_after=_occupy_theatre,
        )

    def incision(
        self,
        case_id: int,
        payload: SurgicalCaseTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalCase:
        # Time-out checklist must be on file before incision.
        case = self.repository.get_required_by_id(case_id)
        if not self.checklist_repository.has_phase(case.id, "TIME_OUT"):
            raise BadRequestError(
                message="WHO time-out checklist must be completed before incision.",
                detail={"case_id": case.id},
            )
        return self._transition(
            case_id,
            SurgicalCaseStatus.PROCEDURE_STARTED,
            payload,
            actor_user_id=actor_user_id,
            timestamps={"incision_at": datetime.now(timezone.utc)},
        )

    def closure(
        self,
        case_id: int,
        payload: SurgicalCaseTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalCase:
        return self._transition(
            case_id,
            SurgicalCaseStatus.PROCEDURE_ENDED,
            payload,
            actor_user_id=actor_user_id,
            timestamps={"closure_at": datetime.now(timezone.utc)},
        )

    def to_post_op(
        self,
        case_id: int,
        payload: SurgicalCaseTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalCase:
        # Sign-out checklist must be recorded before leaving the theatre.
        case = self.repository.get_required_by_id(case_id)
        if not self.checklist_repository.has_phase(case.id, "SIGN_OUT"):
            raise BadRequestError(
                message="WHO sign-out checklist must be completed before post-op.",
                detail={"case_id": case.id},
            )

        def _release_theatre(case: SurgicalCase, _payload):
            if case.operating_theatre_id is not None:
                t = self.theatre_repository.get_required_by_id(
                    case.operating_theatre_id
                )
                t.status = TheatreStatus.CLEANING
                self.theatre_repository.save(t)

        return self._transition(
            case_id,
            SurgicalCaseStatus.POST_OP,
            payload,
            actor_user_id=actor_user_id,
            timestamps={"out_of_theatre_at": datetime.now(timezone.utc)},
            side_effect_after=_release_theatre,
        )

    def complete(
        self,
        case_id: int,
        payload: SurgicalCaseTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
        route_to_service_delivery_point_id: Optional[int] = None,
    ) -> SurgicalCase:
        """
        Complete a case. Captures one BillingItem per case (idempotent on
        ``SURGICAL_CASE:{case_id}``) and optionally hands the visit on to
        the next SDP (e.g. recovery / inpatient ward).
        """

        def _capture_charge_and_route(
            case: SurgicalCase, _payload
        ) -> None:
            # Capture procedure charge against the visit's open billing.
            if case.visit_id is None:
                return
            visit = self.repository.get_visit(case.visit_id)
            if visit is None:
                return
            catalog = self.catalog_repository.get_required_by_id(
                case.procedure_catalog_id
            )
            billing = get_or_create_open_billing(self.db, visit=visit)
            billable = find_billable_service(
                self.db, code=f"SUR-{catalog.code}"
            )
            add_charge(
                self.db,
                billing=billing,
                service_name=f"Surgery: {catalog.name}",
                service_code=f"SUR-{catalog.code}",
                unit_price=Decimal(catalog.default_price or 0),
                quantity=Decimal("1"),
                billable_service_id=billable.id if billable else None,
                source_reference=f"SURGICAL_CASE:{case.id}",
            )
            # Hand-off the visit to the recovery / ward SDP if asked.
            if route_to_service_delivery_point_id is not None:
                route_visit_to_next_sdp(
                    self.db,
                    visit_id=visit.id,
                    target_service_delivery_point_id=route_to_service_delivery_point_id,
                    routed_by_id=actor_user_id,
                    notes=f"Routed after surgical case {case.case_no}.",
                )

        return self._transition(
            case_id,
            SurgicalCaseStatus.COMPLETED,
            payload,
            actor_user_id=actor_user_id,
            side_effect_after=_capture_charge_and_route,
        )

    def cancel(
        self,
        case_id: int,
        payload: SurgicalCaseTransitionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalCase:
        case = self.repository.get_required_by_id(case_id)
        if case.status in {
            SurgicalCaseStatus.COMPLETED,
            SurgicalCaseStatus.CANCELLED,
        }:
            raise BadRequestError(
                message="Case is already in a terminal state.",
                detail={"status": str(case.status)},
            )
        previous = str(case.status)
        case.status = SurgicalCaseStatus.CANCELLED
        case.cancellation_reason = (payload.note if payload else None) or "Cancelled."
        self.repository.save(case)

        # Release theatre if it was occupied by this case.
        if case.operating_theatre_id is not None:
            t = self.theatre_repository.get_required_by_id(case.operating_theatre_id)
            if t.status == TheatreStatus.OCCUPIED:
                t.status = TheatreStatus.CLEANING
                self.theatre_repository.save(t)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="SURGICAL_CASE_CANCELLED",
            severity="WARNING",
            event_detail=f"Surgical case {case.case_no} cancelled.",
            event_metadata={
                "case_id": case.id,
                "previous_status": previous,
                "reason": case.cancellation_reason,
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(case.id)


# ============================================================
# TEAM MEMBERS
# ============================================================


class SurgicalTeamService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SurgicalTeamRepository(db)
        self.case_repository = SurgicalCaseRepository(db)

    def list_for_case(self, case_id: int) -> list[SurgicalTeamMember]:
        # Existence check first.
        self.case_repository.get_required_by_id(case_id)
        return self.repository.list_for_case(case_id)

    def add(
        self,
        payload: SurgicalTeamMemberAddSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalTeamMember:
        from app.core.enums import SurgicalRole

        case = self.case_repository.get_required_by_id(payload.surgical_case_id)
        existing = self.repository.find_existing(
            case.id, payload.staff_profile_id, SurgicalRole(payload.role)
        )
        if existing is not None:
            raise BadRequestError(
                message="This staff member is already assigned to this role on the case.",
                detail={"member_id": existing.id},
            )
        m = self.repository.create(
            surgical_case_id=case.id,
            staff_profile_id=payload.staff_profile_id,
            role=SurgicalRole(payload.role),
            is_lead=payload.is_lead,
            notes=payload.notes,
        )
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="SURGICAL_TEAM_MEMBER_ADDED",
            severity="INFO",
            event_detail=(
                f"Staff {payload.staff_profile_id} added as {payload.role} on "
                f"case {case.case_no}."
            ),
            event_metadata={
                "case_id": case.id,
                "staff_profile_id": payload.staff_profile_id,
                "role": payload.role,
            },
        )
        self.db.commit()
        return m

    def remove(
        self, member_id: int, *, actor_user_id: Optional[int] = None
    ) -> SurgicalTeamMember:
        m = self.repository.get_required_by_id(member_id)
        m = self.repository.soft_delete(m)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="SURGICAL_TEAM_MEMBER_REMOVED",
            severity="WARNING",
            event_detail=f"Team member {m.id} removed from case {m.surgical_case_id}.",
            event_metadata={"member_id": m.id, "case_id": m.surgical_case_id},
        )
        self.db.commit()
        return m


# ============================================================
# CONSENT
# ============================================================


class SurgicalConsentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SurgicalConsentRepository(db)
        self.case_repository = SurgicalCaseRepository(db)

    def list_for_case(self, case_id: int) -> list[SurgicalConsent]:
        self.case_repository.get_required_by_id(case_id)
        return self.repository.list_for_case(case_id)

    def record(
        self,
        payload: SurgicalConsentCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalConsent:
        case = self.case_repository.get_required_by_id(payload.surgical_case_id)
        c = self.repository.create(
            surgical_case_id=case.id,
            consent_text=payload.consent_text,
            consent_signed_by=payload.consent_signed_by,
            relationship_to_patient=payload.relationship_to_patient,
            witnessed_by_staff_id=payload.witnessed_by_staff_id,
            signed_at=payload.signed_at or datetime.now(timezone.utc),
            signature_image_url=payload.signature_image_url,
        )
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="SURGICAL_CONSENT_RECORDED",
            severity="INFO",
            event_detail=f"Consent recorded for surgical case {case.case_no}.",
            event_metadata={"case_id": case.id, "consent_id": c.id},
        )
        self.db.commit()
        return c


# ============================================================
# CHECKLIST
# ============================================================


class SurgicalChecklistService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = SurgicalChecklistRepository(db)
        self.case_repository = SurgicalCaseRepository(db)

    def list_for_case(self, case_id: int) -> list[SurgicalSafetyChecklist]:
        self.case_repository.get_required_by_id(case_id)
        return self.repository.list_for_case(case_id)

    def record(
        self,
        payload: SurgicalChecklistRecordSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalSafetyChecklist:
        from app.core.enums import SurgicalChecklistPhase

        case = self.case_repository.get_required_by_id(payload.surgical_case_id)
        if self.repository.has_phase(case.id, payload.phase):
            raise BadRequestError(
                message="This checklist phase is already recorded for the case.",
                detail={"case_id": case.id, "phase": payload.phase},
            )
        cl = self.repository.create(
            surgical_case_id=case.id,
            phase=SurgicalChecklistPhase(payload.phase),
            items=payload.items,
            completed_by_staff_id=payload.completed_by_staff_id,
            notes=payload.notes,
        )
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type=f"SURGICAL_CHECKLIST_{payload.phase}",
            severity="INFO",
            event_detail=(
                f"Checklist phase {payload.phase} recorded for case {case.case_no}."
            ),
            event_metadata={"case_id": case.id, "phase": payload.phase},
        )
        self.db.commit()
        return cl


# ============================================================
# ANAESTHESIA
# ============================================================


class AnaesthesiaService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AnaesthesiaRepository(db)
        self.case_repository = SurgicalCaseRepository(db)

    def list_for_case(self, case_id: int) -> list[AnaesthesiaRecord]:
        self.case_repository.get_required_by_id(case_id)
        return self.repository.list_for_case(case_id)

    def record(
        self,
        payload: AnaesthesiaRecordCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> AnaesthesiaRecord:
        from app.core.enums import AnaesthesiaType

        case = self.case_repository.get_required_by_id(payload.surgical_case_id)
        r = self.repository.create(
            surgical_case_id=case.id,
            anaesthetist_staff_id=payload.anaesthetist_staff_id,
            anaesthesia_type=AnaesthesiaType(payload.anaesthesia_type),
            induction_time=payload.induction_time,
            emergence_time=payload.emergence_time,
            agents=payload.agents,
            monitoring_intervals=payload.monitoring_intervals,
            complications=payload.complications,
            notes=payload.notes,
        )
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="ANAESTHESIA_RECORD_CREATED",
            severity="INFO",
            event_detail=f"Anaesthesia record created for case {case.case_no}.",
            event_metadata={"case_id": case.id, "record_id": r.id},
        )
        self.db.commit()
        return r


# ============================================================
# THEATRE NOTE
# ============================================================


class TheatreNoteService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TheatreNoteRepository(db)
        self.case_repository = SurgicalCaseRepository(db)

    def list_for_case(self, case_id: int) -> list[TheatreNote]:
        self.case_repository.get_required_by_id(case_id)
        return self.repository.list_for_case(case_id)

    def add(
        self,
        payload: TheatreNoteCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> TheatreNote:
        case = self.case_repository.get_required_by_id(payload.surgical_case_id)
        n = self.repository.create(
            surgical_case_id=case.id,
            author_staff_id=payload.author_staff_id,
            note_type=payload.note_type,
            note=payload.note,
            captured_at=payload.captured_at or datetime.now(timezone.utc),
        )
        return n


# ============================================================
# INSTRUMENT SETS
# ============================================================


class InstrumentSetService:
    """Instrument-set CRUD + sterilization-cycle tracking."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InstrumentSetRepository(db)
        self.log_repository = InstrumentSterilizationRepository(db)
        self.case_repository = SurgicalCaseRepository(db)

    # ----- queries ---------------------------------------------------------
    def get(self, set_id: int) -> SurgicalInstrumentSet:
        return self.repository.get_required_by_id(set_id)

    def list_sets(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        sterilization_status: Optional[str] = None,
        facility_id: Optional[int] = None,
        search: Optional[str] = None,
    ):
        normalized = (
            SterilizationStatus(sterilization_status.strip().upper())
            if sterilization_status
            else None
        )
        return self.repository.list_sets(
            skip=skip,
            limit=limit,
            sterilization_status=normalized,
            facility_id=facility_id,
            search=search,
        )

    # ----- mutations -------------------------------------------------------
    def create(
        self,
        payload: SurgicalInstrumentSetCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalInstrumentSet:
        s = self.repository.create(**payload.model_dump(exclude_unset=True))
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INSTRUMENT_SET_CREATED",
            severity="INFO",
            event_detail=f"Instrument set {s.code} created.",
            event_metadata={"set_id": s.id},
        )
        self.db.commit()
        return s

    def assign_to_case(
        self,
        set_id: int,
        payload: SurgicalInstrumentSetAssignSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> SurgicalInstrumentSet:
        s = self.repository.get_required_by_id(set_id)
        case = self.case_repository.get_required_by_id(payload.surgical_case_id)
        if s.sterilization_status not in {SterilizationStatus.READY}:
            raise BadRequestError(
                message="Only READY instrument sets can be assigned to a case.",
                detail={"set_id": s.id, "status": str(s.sterilization_status)},
            )
        s.surgical_case_id = case.id
        s.sterilization_status = SterilizationStatus.IN_USE
        self.repository.save(s)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INSTRUMENT_SET_ASSIGNED",
            severity="INFO",
            event_detail=f"Instrument set {s.code} assigned to case {case.case_no}.",
            event_metadata={"set_id": s.id, "case_id": case.id},
        )
        self.db.commit()
        return s

    def record_sterilization_cycle(
        self,
        payload: InstrumentSterilizationLogCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> InstrumentSterilizationLog:
        s = self.repository.get_required_by_id(payload.instrument_set_id)
        log = self.log_repository.create(
            instrument_set_id=s.id,
            performed_by_staff_id=payload.performed_by_staff_id,
            cycle_started_at=payload.cycle_started_at,
            cycle_ended_at=payload.cycle_ended_at,
            method=payload.method,
            machine_identifier=payload.machine_identifier,
            indicator_passed=payload.indicator_passed,
            notes=payload.notes,
        )
        # Roll status forward according to indicator outcome.
        if payload.cycle_ended_at is not None:
            if payload.indicator_passed:
                s.sterilization_status = SterilizationStatus.READY
                s.last_autoclaved_at = payload.cycle_ended_at
                s.surgical_case_id = None
            else:
                s.sterilization_status = SterilizationStatus.QUARANTINED
        else:
            s.sterilization_status = SterilizationStatus.AUTOCLAVE
        self.repository.save(s)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INSTRUMENT_STERILIZATION_LOGGED",
            severity="INFO",
            event_detail=(
                f"Sterilization cycle logged for set {s.code} "
                f"(indicator_passed={payload.indicator_passed})."
            ),
            event_metadata={
                "set_id": s.id,
                "log_id": log.id,
                "indicator_passed": payload.indicator_passed,
            },
        )
        self.db.commit()
        return log
