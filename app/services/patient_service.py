from __future__ import annotations

"""
app.services.patient_service

Service layer for patient registration and Master Patient Index (MPI).

Purpose
-------
This module implements business logic for:

- first-time patient registration
- duplicate detection before registration
- registrar duplicate review outcomes
- patient demographic updates
- patient insurance enrollment
- patient loyalty enrollment
- patient identifier management
- patient photo / attachment / scanned form upload
- patient consent records
- patient demographic audit history
- safe patient deletion

Requirements coverage
---------------------
This service is designed to support:

1. Search existing records to avoid duplicates
2. Capture demographics, contacts, emergency contact, and administrative details
3. Generate hospital number
4. Create patient registration record
5. Optionally create insurance or loyalty enrollment if applicable
6. If duplicate exists, registrar can:
   - link to an existing patient
   - continue after override
7. If insurance details are incomplete, save patient first and attach insurance later
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
import uuid

from app.core.exceptions import AlreadyExistsError, BadRequestError, NotFoundError
from app.models.all_models import Patient
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient_schemas import (
    PatientAttachInsuranceLaterSchema,
    PatientAttachmentCreateSchema,
    PatientConsentCreateSchema,
    PatientCreateSchema,
    PatientDuplicateCheckSchema,
    PatientDuplicateReviewDecisionSchema,
    PatientIdentifierCreateSchema,
    PatientLoyaltyEnrollmentSchema,
    PatientScannedFormCreateSchema,
    PatientUpdateSchema,
    PatientAllergyCreateSchema,
    PatientAllergyUpdateSchema,
)

from app.utils.audit_util import log_entity_change, build_audit_payload


class PatientService:
    """
    Service layer for patient registration and MPI workflows.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PatientRepository(db)

    # ============================================================
    # FIRST-TIME REGISTRATION
    # ============================================================

    def create_patient(
        self,
        payload: PatientCreateSchema,
        *,
        registered_by_id: Optional[int] = None,
        force_create_if_possible_duplicate: bool = False,
    ) -> Patient:
        """
        Create a patient record and registration event.

        Workflow
        --------
        - validate MRN uniqueness if supplied
        - validate national identifier uniqueness if supplied
        - run duplicate detection
        - optionally block create unless override is allowed
        - create patient master record
        - create patient registration event
        - create optional identifiers
        - create optional insurance enrollment
        - create optional loyalty enrollment

        Args:
            payload: Patient creation payload.
            registered_by_id: User performing the registration.
            force_create_if_possible_duplicate: Whether to continue after duplicate warning.

        Returns:
            Patient: Newly created patient with related data available.

        Raises:
            AlreadyExistsError: For duplicate MRN / national identifier / identifier.
            BadRequestError: When duplicate candidates exist and override is not allowed.
        """
        hospital_number = payload.hospital_number or self._generate_next_hospital_number()

        # Check for existing patient by hospital number (Idempotency)
        existing_patient = self.repository.get_by_hospital_number(hospital_number)
        if existing_patient:
            return existing_patient

        if payload.national_identifier:
            existing_national_id = self.repository.get_by_national_identifier(
                payload.national_identifier
            )
            if existing_national_id:
                # Idempotent: return the existing patient
                return existing_national_id

        possible_duplicates = self.repository.find_possible_duplicates(
            first_name=payload.first_name,
            last_name=payload.last_name,
            middle_name=payload.middle_name,
            phone_number=payload.phone_number,
            date_of_birth=payload.date_of_birth,
            national_identifier=payload.national_identifier,
            previous_record_identifiers=[
                item.identifier_value
                for item in payload.previous_identifiers
                if item.identifier_type in {"PREVIOUS_RECORD_ID", "EXTERNAL_MRN"}
            ],
        )

        if possible_duplicates and not force_create_if_possible_duplicate:
            raise BadRequestError(
                message=(
                    "Possible duplicate patient record(s) found. "
                    "Registrar review is required before continuing."
                ),
                detail={
                    "possible_duplicate_found": True,
                    "candidate_patient_ids": [item.id for item in possible_duplicates],
                },
            )

        global_patient_id = str(uuid.uuid4())

        patient = self.repository.create_patient(
            global_patient_id=global_patient_id,
            hospital_number=hospital_number,
            first_name=payload.first_name,
            last_name=payload.last_name,
            middle_name=payload.middle_name,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            marital_status=payload.marital_status,
            phone_number=payload.phone_number,
            alternate_phone_number=payload.alternate_phone_number,
            email=str(payload.email) if payload.email else None,
            address=payload.address,
            city=payload.city,
            state=payload.state,
            country=payload.country,
            blood_group=payload.blood_group,
            genotype=payload.genotype,
            allergies=payload.allergies,
            emergency_contact_name=payload.emergency_contact_name,
            emergency_contact_phone=payload.emergency_contact_phone,
            emergency_contact_relationship=payload.emergency_contact_relationship,
            next_of_kin_name=payload.next_of_kin_name,
            next_of_kin_phone=payload.next_of_kin_phone,
            next_of_kin_relationship=payload.next_of_kin_relationship,
            next_of_kin_address=payload.next_of_kin_address,
            patient_type=payload.patient_type,
            preferred_payer_id=payload.preferred_payer_id,
            payer_type=payload.payer_type,
            national_identifier=payload.national_identifier,
            national_identifier_type=payload.national_identifier_type,
            identification_details=payload.identification_details,
            chronic_conditions=payload.chronic_conditions,
        )

        registration = self.repository.create_registration_event(
            patient_id=patient.id,
            registered_by_id=registered_by_id,
            notes=payload.registration_notes,
        )

        for identifier in payload.previous_identifiers:
            self._ensure_identifier_available(
                identifier_type=identifier.identifier_type,
                identifier_value=identifier.identifier_value,
            )
            self.repository.create_patient_identifier(
                patient_id=patient.id,
                identifier_type=identifier.identifier_type,
                identifier_value=identifier.identifier_value,
                issuing_authority=identifier.issuing_authority,
                is_primary=identifier.is_primary,
                is_active=identifier.is_active,
                note=identifier.note,
            )

        if payload.national_identifier:
            existing_identifier = self.repository.get_identifier_by_type_and_value(
                identifier_type=payload.national_identifier_type or "NATIONAL_ID",
                identifier_value=payload.national_identifier,
            )
            if not existing_identifier:
                self.repository.create_patient_identifier(
                    patient_id=patient.id,
                    identifier_type=payload.national_identifier_type or "NATIONAL_ID",
                    identifier_value=payload.national_identifier,
                    issuing_authority=None,
                    is_primary=True,
                    is_active=True,
                    note="Auto-created from patient master record.",
                )

        if payload.insurance_enrollment is not None:
            self._validate_patient_insurance_uniqueness(payload.insurance_enrollment)
            self.repository.create_patient_insurance(
                patient_id=patient.id,
                insurance_provider_id=payload.insurance_enrollment.insurance_provider_id,
                policy_number=payload.insurance_enrollment.policy_number,
                member_id=payload.insurance_enrollment.member_id,
                plan_name=payload.insurance_enrollment.plan_name,
                coverage_details=payload.insurance_enrollment.coverage_details,
                status=payload.insurance_enrollment.status,
                valid_from=payload.insurance_enrollment.valid_from,
                valid_to=payload.insurance_enrollment.valid_to,
                note=payload.insurance_enrollment.note,
            )

        if payload.loyalty_enrollment is not None:
            membership_no = (
                payload.loyalty_enrollment.membership_no
                or self._generate_loyalty_membership_no(patient.id)
            )
            self._validate_loyalty_membership_no_available(membership_no)
            self.repository.create_patient_loyalty_membership(
                patient_id=patient.id,
                loyalty_program_id=payload.loyalty_enrollment.loyalty_program_id,
                membership_no=membership_no,
                points_balance=payload.loyalty_enrollment.points_balance or Decimal("0"),
                joined_date=payload.loyalty_enrollment.joined_date,
                note=payload.loyalty_enrollment.note,
            )

        self.db.commit()
        return self.get_detailed_patient(patient.id)

    # ============================================================
    # DUPLICATE REVIEW OUTCOME
    # ============================================================

    def resolve_duplicate_review(
        self,
        payload: PatientDuplicateReviewDecisionSchema,
        *,
        create_payload: Optional[PatientCreateSchema] = None,
        registered_by_id: Optional[int] = None,
    ) -> Patient:
        """
        Resolve duplicate review after registrar decision.

        Supported outcomes
        ------------------
        - LINK_EXISTING: return existing patient and optionally log a registration event
        - CONTINUE_CREATE: continue and create a new patient after override

        Args:
            payload: Registrar duplicate-review decision.
            create_payload: Required for CONTINUE_CREATE.
            registered_by_id: User performing the action.

        Returns:
            Patient: Existing or newly created patient.

        Raises:
            BadRequestError: When required inputs are missing.
            NotFoundError: When existing patient link target does not exist.
        """
        if payload.decision == "LINK_EXISTING":
            if not payload.existing_patient_id:
                raise BadRequestError(
                    message="existing_patient_id is required when decision is LINK_EXISTING."
                )

            existing = self.repository.get_existing_patient_for_duplicate_link(
                payload.existing_patient_id
            )
            if not existing:
                raise NotFoundError(
                    message="Existing patient to link was not found.",
                    detail={"patient_id": payload.existing_patient_id},
                )

            self.repository.create_registration_event(
                patient_id=existing.id,
                registered_by_id=registered_by_id,
                notes=payload.review_note or "Linked to existing patient after duplicate review.",
            )
            self.db.commit()
            return self.get_detailed_patient(existing.id)

        if payload.decision == "CONTINUE_CREATE":
            if create_payload is None:
                raise BadRequestError(
                    message="create_payload is required when decision is CONTINUE_CREATE."
                )

            return self.create_patient(
                create_payload,
                registered_by_id=registered_by_id,
                force_create_if_possible_duplicate=True,
            )

        raise BadRequestError(message="Unsupported duplicate review decision.")

    # ============================================================
    # INSURANCE LATER ATTACHMENT FLOW
    # ============================================================

    def attach_patient_insurance_later(
        self,
        patient_id: int,
        payload: PatientAttachInsuranceLaterSchema,
    ):
        """
        Attach insurance after patient creation.

        Supports alternate flow where registration is completed first and
        insurance is attached later when details become available.
        """
        self.get_patient(patient_id)
        enrollment = payload.insurance_enrollment

        # Idempotency check: if insurance with this policy exists for THIS patient, return success
        existing = self.repository.find_patient_insurance_by_policy_number(
            insurance_provider_id=enrollment.insurance_provider_id,
            policy_number=enrollment.policy_number,
        )
        if existing:
            if existing.patient_id == patient_id:
                return existing
            raise AlreadyExistsError(
                message="This insurance policy number is already attached to another patient.",
                detail={
                    "insurance_provider_id": enrollment.insurance_provider_id,
                    "policy_number": enrollment.policy_number,
                    "existing_patient_id": existing.patient_id,
                },
            )

        insurance = self.repository.create_patient_insurance(
            patient_id=patient_id,
            insurance_provider_id=enrollment.insurance_provider_id,
            policy_number=enrollment.policy_number,
            member_id=enrollment.member_id,
            plan_name=enrollment.plan_name,
            coverage_details=enrollment.coverage_details,
            status=enrollment.status,
            valid_from=enrollment.valid_from,
            valid_to=enrollment.valid_to,
            note=enrollment.note,
        )
        self.db.commit()
        return insurance

    # ============================================================
    # READ
    # ============================================================

    def get_patient(self, patient_id: int) -> Patient:
        patient = self.repository.get_by_id(patient_id)
        if not patient:
            raise NotFoundError(
                message="Patient not found.",
                detail={"patient_id": patient_id},
            )
        return patient

    def get_patient_by_hospital_number(self, hospital_number: str) -> Patient:
        patient = self.repository.get_by_hospital_number(hospital_number)
        if not patient:
            raise NotFoundError(
                message="Patient not found.",
                detail={"hospital_number": hospital_number},
            )
        return patient

    def get_detailed_patient(self, patient_id: int) -> Patient:
        patient = self.repository.get_detailed_by_id(patient_id)
        if not patient:
            raise NotFoundError(
                message="Patient not found.",
                detail={"patient_id": patient_id},
            )
        return patient

    def list_patients(self, *, skip: int = 0, limit: int = 20):
        return self.repository.list_patients(skip=skip, limit=limit)

    def search_patients(
        self,
        *,
        hospital_number: Optional[str] = None,
        full_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        date_of_birth=None,
        email: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        patient_type=None,
        payer_type: Optional[str] = None,
        national_identifier: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ):
        return self.repository.search_patients(
            hospital_number=hospital_number,
            full_name=full_name,
            phone_number=phone_number,
            date_of_birth=date_of_birth,
            email=email,
            city=city,
            state=state,
            patient_type=patient_type,
            payer_type=payer_type,
            national_identifier=national_identifier,
            skip=skip,
            limit=limit,
        )

    # ============================================================
    # UPDATE DEMOGRAPHICS
    # ============================================================

    def update_patient(
        self,
        patient_id: int,
        payload: PatientUpdateSchema,
        *,
        changed_by_id: Optional[int] = None,
        change_source: Optional[str] = "MPI_UPDATE",
        audit_note: Optional[str] = None,
    ) -> Patient:
        patient = self.get_patient(patient_id)
        before_snapshot = self._build_demographic_snapshot(patient)

        if (
            payload.national_identifier is not None
            and payload.national_identifier != patient.national_identifier
        ):
            existing_national_id = self.repository.get_by_national_identifier(
                payload.national_identifier
            )
            if existing_national_id and existing_national_id.id != patient.id:
                raise AlreadyExistsError(
                    message="A patient with this national identifier already exists.",
                    detail={"national_identifier": payload.national_identifier},
                )

        if payload.first_name is not None:
            patient.first_name = payload.first_name
        if payload.last_name is not None:
            patient.last_name = payload.last_name
        if payload.middle_name is not None:
            patient.middle_name = payload.middle_name

        if payload.date_of_birth is not None:
            patient.date_of_birth = payload.date_of_birth
        if payload.gender is not None:
            patient.gender = payload.gender
        if payload.marital_status is not None:
            patient.marital_status = payload.marital_status

        if payload.phone_number is not None:
            patient.phone_number = payload.phone_number
        if payload.alternate_phone_number is not None:
            patient.alternate_phone_number = payload.alternate_phone_number
        if payload.email is not None:
            patient.email = str(payload.email)

        if payload.address is not None:
            patient.address = payload.address
        if payload.city is not None:
            patient.city = payload.city
        if payload.state is not None:
            patient.state = payload.state
        if payload.country is not None:
            patient.country = payload.country

        if payload.blood_group is not None:
            patient.blood_group = payload.blood_group
        if payload.genotype is not None:
            patient.genotype = payload.genotype
        if payload.allergies is not None:
            patient.allergies = payload.allergies
        if payload.chronic_conditions is not None:
            patient.chronic_conditions = payload.chronic_conditions

        if payload.emergency_contact_name is not None:
            patient.emergency_contact_name = payload.emergency_contact_name
        if payload.emergency_contact_phone is not None:
            patient.emergency_contact_phone = payload.emergency_contact_phone
        if payload.emergency_contact_relationship is not None:
            patient.emergency_contact_relationship = payload.emergency_contact_relationship

        if payload.next_of_kin_name is not None:
            patient.next_of_kin_name = payload.next_of_kin_name
        if payload.next_of_kin_phone is not None:
            patient.next_of_kin_phone = payload.next_of_kin_phone
        if payload.next_of_kin_relationship is not None:
            patient.next_of_kin_relationship = payload.next_of_kin_relationship
        if payload.next_of_kin_address is not None:
            patient.next_of_kin_address = payload.next_of_kin_address

        if payload.patient_type is not None:
            patient.patient_type = payload.patient_type

        if payload.preferred_payer_id is not None:
            patient.preferred_payer_id = payload.preferred_payer_id
        if payload.payer_type is not None:
            patient.payer_type = payload.payer_type

        if payload.national_identifier is not None:
            patient.national_identifier = payload.national_identifier
        if payload.national_identifier_type is not None:
            patient.national_identifier_type = payload.national_identifier_type
        if payload.identification_details is not None:
            patient.identification_details = payload.identification_details

        updated = self.repository.update_patient(patient)

        after_snapshot = self._build_demographic_snapshot(updated)
        changed_fields = self._calculate_changed_fields(before_snapshot, after_snapshot)

        if changed_fields:
            self.repository.log_patient_demographic_change(
                patient_id=updated.id,
                changed_by_id=changed_by_id,
                change_source=change_source,
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
                changed_fields=changed_fields,
                note=audit_note,
            )
            
            # General Audit Logging
            log_entity_change(
                db=self.db,
                actor_user_id=changed_by_id,
                action="UPDATE",
                entity_name="PATIENT",
                entity_id=updated.id,
                before_data=before_snapshot,
                after_data=after_snapshot,
                extra_metadata={
                    "change_source": change_source,
                    "changed_fields": changed_fields
                }
            )

        self.db.commit()
        return self.get_detailed_patient(updated.id)

    # ============================================================
    # DUPLICATE CHECK
    # ============================================================

    def check_for_possible_duplicates(
        self,
        payload: PatientDuplicateCheckSchema,
    ):
        return self.repository.find_possible_duplicates(
            first_name=payload.first_name,
            last_name=payload.last_name,
            middle_name=payload.middle_name,
            phone_number=payload.phone_number,
            date_of_birth=payload.date_of_birth,
            national_identifier=payload.national_identifier,
            previous_record_identifiers=payload.previous_record_identifiers,
        )

    # ============================================================
    # IDENTIFIERS
    # ============================================================

    def add_patient_identifier(
        self,
        patient_id: int,
        payload: PatientIdentifierCreateSchema,
    ):
        self.get_patient(patient_id)
        # Idempotency check
        existing = self.repository.get_identifier_by_type_and_value(
            identifier_type=payload.identifier_type,
            identifier_value=payload.identifier_value,
        )
        if existing:
            if existing.patient_id == patient_id:
                return existing
            raise AlreadyExistsError(
                message="This identifier is already assigned to another patient.",
                detail={
                    "identifier_type": payload.identifier_type,
                    "identifier_value": payload.identifier_value,
                    "existing_patient_id": existing.patient_id,
                },
            )

        identifier = self.repository.create_patient_identifier(
            patient_id=patient_id,
            identifier_type=payload.identifier_type,
            identifier_value=payload.identifier_value,
            issuing_authority=payload.issuing_authority,
            is_primary=payload.is_primary,
            is_active=payload.is_active,
            note=payload.note,
        )
        self.db.commit()
        return identifier

    # ============================================================
    # PHOTO / ATTACHMENTS / SCANNED FORMS
    # ============================================================

    def upload_patient_photo(
        self,
        patient_id: int,
        *,
        file_bytes: bytes,
        file_name: str,
        content_type: Optional[str] = None,
        uploaded_by_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> dict:
        patient = self.get_patient(patient_id)
        result = self.repository.upload_patient_photo(
            patient=patient,
            file_bytes=file_bytes,
            file_name=file_name,
            content_type=content_type,
            uploaded_by_id=uploaded_by_id,
            note=note,
        )
        self.db.commit()
        return result

    def create_patient_attachment(
        self,
        patient_id: int,
        payload: PatientAttachmentCreateSchema,
        *,
        file_bytes: bytes,
        uploaded_by_id: Optional[int] = None,
    ):
        self.get_patient(patient_id)

        attachment = self.repository.create_patient_attachment(
            patient_id=patient_id,
            attachment_type=payload.attachment_type,
            file_bytes=file_bytes,
            file_name=payload.file_name,
            uploaded_by_id=uploaded_by_id,
            title=payload.title,
            content_type=payload.content_type,
            note=payload.note,
            is_primary=payload.is_primary,
        )
        self.db.commit()
        return attachment

    def create_patient_scanned_form(
        self,
        patient_id: int,
        payload: PatientScannedFormCreateSchema,
        *,
        file_bytes: bytes,
        uploaded_by_id: Optional[int] = None,
    ):
        self.get_patient(patient_id)

        form = self.repository.create_patient_scanned_form(
            patient_id=patient_id,
            form_type=payload.form_type,
            file_bytes=file_bytes,
            file_name=payload.file_name,
            uploaded_by_id=uploaded_by_id,
            content_type=payload.content_type,
            note=payload.note,
        )
        self.db.commit()
        return form

    # ============================================================
    # CONSENT RECORDS
    # ============================================================

    def create_patient_consent_record(
        self,
        patient_id: int,
        payload: PatientConsentCreateSchema,
        *,
        recorded_by_id: Optional[int] = None,
    ):
        self.get_patient(patient_id)

        consent = self.repository.create_patient_consent_record(
            patient_id=patient_id,
            consent_type=payload.consent_type,
            consent_status=payload.consent_status,
            recorded_by_id=recorded_by_id,
            consent_date=payload.consent_date,
            expiry_date=payload.expiry_date,
            document_file_name=payload.document_file_name,
            document_file_key=payload.document_file_key,
            document_file_url=payload.document_file_url,
            note=payload.note,
        )
        self.db.commit()
        return consent

    # ============================================================
    # DELETE
    # ============================================================

    def delete_patient(self, patient_id: int) -> Patient:
        patient = self.get_patient(patient_id)

        if self.repository.patient_has_visits(patient_id):
            raise BadRequestError(
                message="This patient cannot be deleted because visit records already exist.",
                detail={"patient_id": patient_id},
            )

        if self.repository.patient_has_admissions(patient_id):
            raise BadRequestError(
                message="This patient cannot be deleted because admission records already exist.",
                detail={"patient_id": patient_id},
            )

        if self.repository.patient_has_billing(patient_id):
            raise BadRequestError(
                message="This patient cannot be deleted because billing or invoice records already exist.",
                detail={"patient_id": patient_id},
            )

        deleted = self.repository.soft_delete_patient(patient)
        self.db.commit()
        return deleted

    # ============================================================
    # ALLERGIES
    # ============================================================

    def add_patient_allergy(
        self,
        patient_id: int,
        payload: PatientAllergyCreateSchema,
    ):
        self.get_patient(patient_id)
        allergy = self.repository.create_patient_allergy(
            patient_id=patient_id,
            allergen_name=payload.allergen_name,
            severity=payload.severity,
            reaction_description=payload.reaction_description,
            is_active=payload.is_active,
        )
        self.db.commit()
        return allergy

    def list_patient_allergies(self, patient_id: int):
        self.get_patient(patient_id)
        return self.repository.list_patient_allergies(patient_id)

    def update_patient_allergy(
        self,
        allergy_id: int,
        payload: PatientAllergyUpdateSchema,
    ):
        allergy = self.repository.get_patient_allergy_by_id(allergy_id)
        if not allergy:
            raise NotFoundError(message="Patient allergy record not found.")

        if payload.allergen_name is not None:
            allergy.allergen_name = payload.allergen_name
        if payload.severity is not None:
            allergy.severity = payload.severity
        if payload.reaction_description is not None:
            allergy.reaction_description = payload.reaction_description
        if payload.is_active is not None:
            allergy.is_active = payload.is_active

        updated = self.repository.update_patient_allergy(allergy)
        self.db.commit()
        return updated

    def delete_patient_allergy(self, allergy_id: int):
        allergy = self.repository.get_patient_allergy_by_id(allergy_id)
        if not allergy:
            raise NotFoundError(message="Patient allergy record not found.")

        self.repository.soft_delete_patient_allergy(allergy)
        self.db.commit()
        return True

    # ============================================================
    # HELPERS
    # ============================================================

    def _generate_next_hospital_number(self) -> str:
        """
        Generate the next patient MRN / hospital number.

        Current approach uses a timestamp fallback.
        Replace later with facility/config-driven sequencing if needed.
        """
        return f"MRN-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    def _generate_loyalty_membership_no(self, patient_id: int) -> str:
        """
        Generate a simple loyalty membership number.
        """
        return f"LOY-{patient_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    def _ensure_identifier_available(self, *, identifier_type: str, identifier_value: str) -> None:
        existing = self.repository.get_identifier_by_type_and_value(
            identifier_type=identifier_type,
            identifier_value=identifier_value,
        )
        if existing:
            raise AlreadyExistsError(
                message="This patient identifier already exists.",
                detail={
                    "identifier_type": identifier_type,
                    "identifier_value": identifier_value,
                    "existing_patient_id": existing.patient_id,
                },
            )

    def _validate_patient_insurance_uniqueness(self, enrollment) -> None:
        existing = self.repository.find_patient_insurance_by_policy_number(
            insurance_provider_id=enrollment.insurance_provider_id,
            policy_number=enrollment.policy_number,
        )
        if existing:
            raise AlreadyExistsError(
                message="This insurance policy number is already attached.",
                detail={
                    "insurance_provider_id": enrollment.insurance_provider_id,
                    "policy_number": enrollment.policy_number,
                    "existing_patient_id": existing.patient_id,
                },
            )

    def _validate_loyalty_membership_no_available(self, membership_no: str) -> None:
        existing = self.repository.get_patient_loyalty_by_membership_no(membership_no)
        if existing:
            raise AlreadyExistsError(
                message="This loyalty membership number already exists.",
                detail={
                    "membership_no": membership_no,
                    "existing_patient_id": existing.patient_id,
                },
            )

    def _build_demographic_snapshot(self, patient: Patient) -> dict:
        return {
            "hospital_number": patient.hospital_number,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "middle_name": patient.middle_name,
            "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "gender": str(patient.gender) if patient.gender is not None else None,
            "marital_status": str(patient.marital_status) if patient.marital_status is not None else None,
            "phone_number": patient.phone_number,
            "alternate_phone_number": patient.alternate_phone_number,
            "email": patient.email,
            "address": patient.address,
            "city": patient.city,
            "state": patient.state,
            "country": patient.country,
            "blood_group": str(patient.blood_group) if patient.blood_group is not None else None,
            "genotype": str(patient.genotype) if patient.genotype is not None else None,
            "allergies": patient.allergies,
            "emergency_contact_name": patient.emergency_contact_name,
            "emergency_contact_phone": patient.emergency_contact_phone,
            "emergency_contact_relationship": patient.emergency_contact_relationship,
            "next_of_kin_name": patient.next_of_kin_name,
            "next_of_kin_phone": patient.next_of_kin_phone,
            "next_of_kin_relationship": patient.next_of_kin_relationship,
            "next_of_kin_address": patient.next_of_kin_address,
            "patient_type": str(patient.patient_type) if patient.patient_type is not None else None,
            "preferred_payer_id": patient.preferred_payer_id,
            "payer_type": patient.payer_type,
            "national_identifier": patient.national_identifier,
            "national_identifier_type": patient.national_identifier_type,
            "identification_details": patient.identification_details,
        }

    def _calculate_changed_fields(self, before_snapshot: dict, after_snapshot: dict) -> list[str]:
        changed_fields: list[str] = []
        for key in sorted(set(before_snapshot.keys()) | set(after_snapshot.keys())):
            if before_snapshot.get(key) != after_snapshot.get(key):
                changed_fields.append(key)
        return changed_fields