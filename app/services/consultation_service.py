# app/services/consultation_service.py
from __future__ import annotations

"""
app.services.consultation_service

Service layer for clinical consultations and encounter management.

Purpose
-------
This module orchestrates the clinical encounter workflow, ensuring that 
consultations are correctly initiated, updated, and finalized. It handles 
integration with visit routing and enforces business rules for medical 
documentation.

Workflow State Machine
----------------------
OPEN -> AMENDED (if updated after finalization)
     -> CLOSED (on finalization)
     -> CANCELLED (on voiding)

Business Rules
--------------
- Only one OPEN consultation can exist for a visit at a time.
- Consultations must be initiated from a clinical Service Delivery Point (CLINIC, EMERGENCY, WARD).
- Finalization can trigger automatic visit termination or routing to ancillary services (Lab, Pharmacy, etc.).
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import EncounterStatus, ServicePointType, VisitStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import Consultation
from app.repositories.consultation_repository import ConsultationRepository
from app.schemas.consultation_schema import (
    ConsultationCreateSchema,
    ConsultationFinalizeSchema,
    ConsultationUpdateSchema,
)
from app.utils.charge_capture import (
    add_charge,
    resolve_billable_service,
    get_or_create_open_billing,
)
from app.utils.visit_routing import end_visit, route_visit_to_next_sdp, validate_visit_sdp_activity

logger = logging.getLogger(__name__)


_TERMINAL_VISIT = {VisitStatus.COMPLETED, VisitStatus.CANCELLED}


class ConsultationService:
    """
    Business logic coordinator for clinical consultations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ConsultationRepository(db)

    # ============================================================
    # READ OPERATIONS
    # ============================================================

    def list_for_visit(self, visit_id: int, *, skip: int = 0, limit: int = 20):
        """
        Fetch all clinical notes recorded during a specific visit.
        """
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)


    def get(self, consultation_id: int) -> Consultation:
        """
        Retrieve a single consultation record with full clinical context.
        """
        return self.repository.get_required_by_id(consultation_id)


    # ============================================================
    # WRITE OPERATIONS
    # ============================================================

    def create(
        self,
        payload: ConsultationCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Consultation:
        """
        Initiate a new clinical consultation encounter.
        
        Orchestration:
        - Validates visit state.
        - Checks for existing open encounters to prevent data fragmentation.
        - Enforces clinical service point context.
        - Creates the initial record and flushes to capture the primary key.
        """
        visit = self.repository.get_required_visit(payload.visit_id)
        
        # 1. Integrity check: Visit must be active
        if visit.status in _TERMINAL_VISIT:
            raise BadRequestError(
                message="Cannot start a consultation on a closed visit.",
                detail={"visit_status": str(visit.status)},
            )

        # 2. Integrity check: Prevent multiple open encounters
        existing_open = self.repository.get_open_for_visit(visit.id)
        if existing_open is not None:
            raise BadRequestError(
                message="An open consultation already exists for this visit.",
                detail={"existing_consultation_id": existing_open.id},
            )

        # 3. Context validation: User must be in a Clinical SDP
        current_step = validate_visit_sdp_activity(
            self.db,
            visit_id=visit.id,
            required_sdp_types=[ServicePointType.CLINIC, ServicePointType.EMERGENCY, ServicePointType.WARD],
            activity_name="Consultation",
        )

        # 4. Persistence
        consultation = self.repository.create(
            visit_id=visit.id,
            visit_flow_step_id=current_step.id,
            clinician_staff_id=payload.clinician_staff_id,
            subjective_note=payload.subjective_note,
            objective_note=payload.objective_note,
            assessment_note=payload.assessment_note,
            plan_note=payload.plan_note,
        )

        # Doctor's admission recommendation (gates inpatient admission).
        if payload.recommends_admission:
            consultation.recommends_admission = True
            consultation.admission_recommended_at = datetime.now(timezone.utc)
        consultation.admission_recommendation_note = payload.admission_recommendation_note

        # 5. Capture the consultation fee onto the visit's running charge sheet
        #    (idempotent per consultation). Priced from the CONSULTATION billable
        #    service, which is auto-created on first use and re-priceable by admins.
        self._capture_consultation_fee(visit, consultation.id)

        self.db.commit()
        return self.repository.get_required_by_id(consultation.id)

    # Default price used only when the CONSULTATION billable service is first
    # auto-created; admins can edit it afterwards in the billable services catalog.
    _DEFAULT_CONSULTATION_FEE = Decimal("5000.00")

    def _capture_consultation_fee(self, visit, consultation_id: int) -> None:
        """Best-effort: add the consultation fee to the visit's OPEN billing."""
        try:
            service = resolve_billable_service(
                self.db,
                code="CONSULTATION",
                name="Consultation Fee",
                default_price=self._DEFAULT_CONSULTATION_FEE,
                category="CONSULTATION",
                domain="CONSULTATION",
            )
            unit_price = Decimal(str(service.default_price or 0))
            if unit_price <= 0:
                # Nothing to charge (fee not configured) — skip silently.
                return
            billing = get_or_create_open_billing(self.db, visit=visit)
            add_charge(
                self.db,
                billing=billing,
                service_name="Consultation Fee",
                service_code="CONSULTATION",
                unit_price=unit_price,
                quantity=Decimal("1"),
                billable_service_id=service.id,
                source_reference=f"CONSULTATION:{consultation_id}",
            )
        except Exception as exc:  # pragma: no cover - charge capture must not block care
            logger.warning("Failed to capture consultation fee for visit %s: %s", visit.id, exc)


    def update(
        self,
        consultation_id: int,
        payload: ConsultationUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Consultation:
        """
        Update clinical notes on a consultation.
        
        Note: If the consultation is already CLOSED, this action marks it 
        as AMENDED to preserve audit integrity.
        """
        consultation = self.repository.get_required_by_id(consultation_id)

        was_closed = consultation.status == EncounterStatus.CLOSED

        # Apply updates
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(consultation, field, value)

        # Stamp / clear the recommendation timestamp when the flag changes.
        _changed = payload.model_dump(exclude_unset=True)
        if "recommends_admission" in _changed:
            if _changed["recommends_admission"]:
                if consultation.admission_recommended_at is None:
                    consultation.admission_recommended_at = datetime.now(timezone.utc)
            else:
                consultation.admission_recommended_at = None

        # Maintain state integrity
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
        Finalize a consultation encounter and decide the patient's next destination.
        
        Workflow Outcomes:
        - Route to Ancillary: Sends patient to Lab, Pharmacy, or Cashier.
        - End Visit: Completes the entire visit lifecycle.
        """
        consultation = self.repository.get_required_by_id(consultation_id)
        
        if consultation.status == EncounterStatus.CANCELLED:
            raise BadRequestError(message="Cancelled consultations cannot be finalized.")

        # 1. State transition
        consultation.status = EncounterStatus.CLOSED
        consultation.consultation_ended_at = datetime.now(timezone.utc)
        
        # Append closing note to plan if provided
        if payload.closing_note:
            existing = consultation.plan_note or ""
            consultation.plan_note = (existing + ("\n\n" if existing else "") + payload.closing_note).strip()
        
        self.repository.save(consultation)

        # 2. Visit Lifecycle Routing
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
        """
        Void a consultation record. 
        
        Only OPEN or AMENDED consultations can be cancelled.
        """
        consultation = self.repository.get_required_by_id(consultation_id)
        
        if consultation.status in {EncounterStatus.CLOSED, EncounterStatus.CANCELLED}:
            raise BadRequestError(
                message="Consultation is no longer open and cannot be cancelled.",
                detail={"status": str(consultation.status)},
            )
            
        consultation.status = EncounterStatus.CANCELLED
        consultation.consultation_ended_at = datetime.now(timezone.utc)
        
        # Append cancellation audit note
        if reason:
            note = consultation.plan_note or ""
            consultation.plan_note = (note + ("\n\n" if note else "") + f"[CANCELLED] {reason}").strip()
            
        self.repository.save(consultation)
        self.db.commit()
        return self.repository.get_required_by_id(consultation.id)
