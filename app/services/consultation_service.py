# app/services/consultation_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import EncounterStatus, VisitStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import Consultation
from app.repositories.consultation_repository import ConsultationRepository
from app.schemas.consultation_schema import (
    ConsultationCreateSchema,
    ConsultationFinalizeSchema,
    ConsultationUpdateSchema,
)
from app.utils.visit_routing import end_visit, route_visit_to_next_sdp


_TERMINAL_VISIT = {VisitStatus.COMPLETED, VisitStatus.CANCELLED}


class ConsultationService:
    """
    Service layer for clinical consultations.

    Lifecycle
    ---------
    OPEN -> AMENDED (on edit-after-finalize) | CLOSED (on finalize)
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ConsultationRepository(db)

    # ---- READ ----
    def list_for_visit(self, visit_id: int, *, skip: int = 0, limit: int = 20):
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)

    def get(self, consultation_id: int) -> Consultation:
        return self.repository.get_required_by_id(consultation_id)

    # ---- WRITE ----
    def create(
        self,
        payload: ConsultationCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Consultation:
        visit = self.repository.get_required_visit(payload.visit_id)
        if visit.status in _TERMINAL_VISIT:
            raise BadRequestError(
                message="Cannot start a consultation on a closed visit.",
                detail={"visit_status": str(visit.status)},
            )

        existing_open = self.repository.get_open_for_visit(visit.id)
        if existing_open is not None:
            raise BadRequestError(
                message="An open consultation already exists for this visit.",
                detail={"existing_consultation_id": existing_open.id},
            )

        consultation = self.repository.create(
            visit_id=visit.id,
            clinician_staff_id=payload.clinician_staff_id,
            subjective_note=payload.subjective_note,
            objective_note=payload.objective_note,
            assessment_note=payload.assessment_note,
            plan_note=payload.plan_note,
        )
        self.db.commit()
        return self.repository.get_required_by_id(consultation.id)

    def update(
        self,
        consultation_id: int,
        payload: ConsultationUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Consultation:
        consultation = self.repository.get_required_by_id(consultation_id)

        was_closed = consultation.status == EncounterStatus.CLOSED

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(consultation, field, value)

        if was_closed:
            consultation.status = EncounterStatus.AMENDED

        self.repository.save(consultation)
        self.db.commit()
        return self.repository.get_required_by_id(consultation.id)

    def finalize(
        self,
        consultation_id: int,
        payload: ConsultationFinalizeSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Consultation:
        """
        Finalize a consultation. Either route the patient to a next service
        delivery point (lab/pharmacy/cashier/etc.) or end the visit.
        """
        consultation = self.repository.get_required_by_id(consultation_id)
        if consultation.status == EncounterStatus.CANCELLED:
            raise BadRequestError(message="Cancelled consultations cannot be finalized.")

        consultation.status = EncounterStatus.CLOSED
        consultation.consultation_ended_at = datetime.now(timezone.utc)
        if payload.closing_note:
            existing = consultation.plan_note or ""
            consultation.plan_note = (existing + ("\n\n" if existing else "") + payload.closing_note).strip()
        self.repository.save(consultation)

        if payload.end_visit:
            end_visit(self.db, visit_id=consultation.visit_id, actor_user_id=actor_user_id)
        elif payload.next_service_delivery_point_id is not None:
            route_visit_to_next_sdp(
                self.db,
                visit_id=consultation.visit_id,
                target_service_delivery_point_id=payload.next_service_delivery_point_id,
                routed_by_id=actor_user_id,
                notes="Routed by clinician at consultation finalize.",
            )

        self.db.commit()
        return self.repository.get_required_by_id(consultation.id)

    def cancel(
        self,
        consultation_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> Consultation:
        consultation = self.repository.get_required_by_id(consultation_id)
        if consultation.status in {EncounterStatus.CLOSED, EncounterStatus.CANCELLED}:
            raise BadRequestError(
                message="Consultation is no longer open.",
                detail={"status": str(consultation.status)},
            )
        consultation.status = EncounterStatus.CANCELLED
        consultation.consultation_ended_at = datetime.now(timezone.utc)
        if reason:
            note = consultation.plan_note or ""
            consultation.plan_note = (note + ("\n\n" if note else "") + f"[CANCELLED] {reason}").strip()
        self.repository.save(consultation)
        self.db.commit()
        return self.repository.get_required_by_id(consultation.id)
