# app/services/patient_registration_service.py
from __future__ import annotations

"""
Unified registration + visit initiation service.

This composes:
- patient lookup by hospital_number / national_identifier / phone / email
- inline new-patient registration
- visit initiation (uses VisitService)
- default OPD visit flow template resolution
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Patient, VisitFlowTemplate
from app.repositories.patient_repository import PatientRepository
from app.repositories.visit_flow_repository import VisitFlowRepository
from app.schemas.admission_schemas import AdmissionCreateSchema
from app.schemas.patient_registration_schema import (
    UnifiedVisitInitiationSchema,
)
from app.schemas.visit_schemas import VisitInitiateSchema
from app.services.admission_service import AdmissionService
from app.services.patient_service import PatientService
from app.services.visit_service import VisitService


class PatientRegistrationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.patient_service = PatientService(db)
        self.patient_repository = PatientRepository(db)
        self.visit_service = VisitService(db)
        self.flow_repository = VisitFlowRepository(db)
        # The unified flow can also create an inpatient admission. We instantiate
        # the admission service eagerly so the caller can rely on it being
        # available without having to thread a session through twice.
        self.admission_service = AdmissionService(db)

    # ============================================================
    # PATIENT LOOKUP
    # ============================================================

    def find_returning_patient(
        self,
        *,
        hospital_number: Optional[str] = None,
        national_identifier: Optional[str] = None,
        phone_number: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[Patient]:
        """
        Locate an existing patient by the first matching identifier.
        """
        if hospital_number:
            patient = self.patient_repository.get_by_hospital_number(hospital_number.strip())
            if patient:
                return patient

        if national_identifier and hasattr(self.patient_repository, "get_by_national_identifier"):
            patient = self.patient_repository.get_by_national_identifier(national_identifier.strip())
            if patient:
                return patient

        if phone_number:
            results, _ = self.patient_repository.search_patients(
                phone_number=phone_number.strip(), skip=0, limit=1
            )
            if results:
                return results[0]

        if email:
            results, _ = self.patient_repository.search_patients(email=email.strip(), skip=0, limit=1)
            if results:
                return results[0]

        return None

    # ============================================================
    # UNIFIED ENTRYPOINT
    # ============================================================

    def initiate_visit_with_registration(
        self,
        payload: UnifiedVisitInitiationSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> dict:
        """
        Single endpoint that initiates a visit for either an existing patient
        (matched by identifier) or a newly-registered patient.
        """
        is_returning = False
        patient: Optional[Patient] = None

        if payload.existing_patient is not None:
            lookup = payload.existing_patient
            patient = self.find_returning_patient(
                hospital_number=lookup.hospital_number,
                national_identifier=lookup.national_identifier,
                phone_number=lookup.phone_number,
                email=lookup.email,
            )
            if not patient:
                raise NotFoundError(
                    message="No matching patient found for the supplied identifiers.",
                    detail=lookup.model_dump(exclude_none=True),
                )
            is_returning = True
        else:
            assert payload.new_patient is not None
            patient = self.patient_service.create_patient(
                payload.new_patient,
                registered_by_id=actor_user_id,
            )

        # Resolve visit flow template (id > code > default code).
        template = self._resolve_visit_flow_template(
            template_id=payload.options.visit_flow_template_id,
            template_code=payload.options.visit_flow_template_code,
            fallback_code=getattr(settings, "DEFAULT_OPD_VISIT_FLOW_TEMPLATE_CODE", "OPD_DEFAULT"),
        )

        # Build the visit-initiation payload.
        visit_payload_kwargs = {
            "patient_id": patient.id,
            "appointment_id": payload.options.appointment_id,
            "visit_flow_template_id": template.id if template is not None else None,
            "first_service_delivery_point_id": payload.options.first_service_delivery_point_id,
            "use_appointment_service_point": payload.options.use_appointment_service_point,
            "fast_track": payload.options.fast_track,
            "priority": payload.options.priority,
            "visit_reason": payload.options.visit_reason,
            "visit_date": payload.options.visit_date,
            "referred_from": payload.options.referred_from,
            "create_first_flow_step": True,
            "create_queue_ticket": True,
        }
        try:
            visit_payload = VisitInitiateSchema(
                **{k: v for k, v in visit_payload_kwargs.items() if v is not None}
            )
        except Exception as exc:
            raise BadRequestError(
                message="Could not build visit initiation payload.",
                detail={"reason": str(exc)},
            ) from exc

        result = self.visit_service.initiate_visit(visit_payload, routed_by_id=actor_user_id)
        visit = result.get("visit") if isinstance(result, dict) else None
        queue_ticket = result.get("first_queue_ticket") if isinstance(result, dict) else None
        first_flow_step = result.get("first_flow_step") if isinstance(result, dict) else None

        # ----------------------------------------------------------------
        # Inpatient mode: when the receptionist supplied an admission block,
        # admit the patient inline using the same session/transaction. This
        # gives ER, scheduled-inpatient and obstetric flows a single API call
        # that produces (Patient, Visit, Admission, Bed, first bed-day charge).
        # ----------------------------------------------------------------
        admission = None
        bed_day_charges_captured = 0
        if payload.admission is not None:
            if visit is None:
                # Defensive guard — the unified entrypoint should always have
                # produced a visit at this point. If it didn't, refuse to admit
                # rather than leak an orphan admission row.
                raise BadRequestError(
                    message="Visit could not be created; admission aborted.",
                    detail={"patient_id": patient.id},
                )

            admission_payload = AdmissionCreateSchema(
                patient_id=patient.id,
                visit_id=visit.id,
                ward_id=payload.admission.ward_id,
                bed_id=payload.admission.bed_id,
                admitting_staff_id=payload.admission.admitting_staff_id,
                admission_reason=payload.admission.admission_reason,
                admitted_at=payload.admission.admitted_at or payload.options.visit_date,
                expected_discharge_at=payload.admission.expected_discharge_at,
                capture_first_bed_day_charge=payload.admission.capture_first_bed_day_charge,
            )

            # The admission service commits internally; that's fine here
            # because we've already committed the visit creation. The two
            # transactions are sequential rather than nested.
            admission = self.admission_service.admit(admission_payload, actor_user_id=actor_user_id)
            # When the first bed-day charge was captured during admit, we
            # surface that count to the response so the cashier UI knows the
            # bill is already non-zero.
            if payload.admission.capture_first_bed_day_charge:
                bed_day_charges_captured = 1

        return {
            "is_returning_patient": is_returning,
            "patient": patient,
            "visit": visit,
            "queue_ticket": queue_ticket,
            "first_flow_step": first_flow_step,
            "visit_flow_template": template,
            "admission": admission,
            "bed_day_charges_captured": bed_day_charges_captured,
        }

    # ============================================================
    # INTERNAL
    # ============================================================

    def _resolve_visit_flow_template(
        self,
        *,
        template_id: Optional[int],
        template_code: Optional[str],
        fallback_code: Optional[str],
    ) -> Optional[VisitFlowTemplate]:
        if template_id is not None:
            return self.flow_repository.get_template_by_id(template_id)
        if template_code:
            return self.flow_repository.get_template_by_code(template_code.strip().upper())
        if fallback_code:
            return self.flow_repository.get_template_by_code(fallback_code.strip().upper())
        return None
