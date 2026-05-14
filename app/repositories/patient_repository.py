from __future__ import annotations

"""
app.repositories.patient_repository

Repository layer for patient registration and Master Patient Index (MPI).

Purpose
-------
This module centralizes direct database operations for:

- creating patients
- updating patient demographics
- soft-deleting patients
- reading patient details
- listing/searching patients in the MPI
- duplicate detection using configurable matching attributes
- logging patient registration events
- managing patient identifiers
- managing patient photo and document attachments stored on AWS S3
- managing patient consent records
- managing scanned clinical/registration forms
- logging patient demographic audit history
- optionally creating patient insurance enrollment
- optionally creating patient loyalty enrollment
- supporting duplicate-review outcomes such as linking to an existing patient

Design goals
------------
- keep raw SQLAlchemy query logic out of route handlers
- keep business rules out of the repository layer
- expose reusable persistence/query helpers for the service layer
- use AWS S3 for patient photos and other file attachments
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.all_models import (
    Patient,
    PatientAttachment,
    PatientConsent,
    PatientDemographicAudit,
    PatientIdentifier,
    PatientInsurance,
    PatientLoyalty,
    PatientRegistration,
    PatientScannedForm,
)
from app.utils.s3_utils import (
    build_s3_object_key,
    delete_file_from_s3,
    generate_presigned_url_file,
    generate_presigned_url_image,
    upload_bytes_to_s3,
)


class PatientRepository:
    """
    Repository for patient registration, MPI lookup, duplicate detection,
    patient file handling, insurance/loyalty enrollment, and registration
    artifact persistence.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ============================================================
    # BASIC LOOKUPS
    # ============================================================

    def get_by_id(self, patient_id: int) -> Optional[Patient]:
        return (
            self.db.query(Patient)
            .filter(
                Patient.id == patient_id,
                Patient.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_hospital_number(self, hospital_number: str) -> Optional[Patient]:
        return (
            self.db.query(Patient)
            .filter(
                Patient.hospital_number == hospital_number,
                Patient.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_national_identifier(self, national_identifier: str) -> Optional[Patient]:
        return (
            self.db.query(Patient)
            .filter(
                Patient.national_identifier == national_identifier,
                Patient.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, patient_id: int) -> Patient:
        patient = self.get_by_id(patient_id)
        if not patient:
            raise ValueError(f"Patient with id={patient_id} was not found.")
        return patient

    # ============================================================
    # DETAILED LOOKUPS
    # ============================================================

    def get_detailed_by_id(self, patient_id: int) -> Optional[Patient]:
        """
        Return a patient by ID with major relationships eagerly loaded.
        """
        return (
            self.db.query(Patient)
            .options(
                selectinload(
                    Patient.registrations
                ).filter(
                    PatientRegistration.is_deleted.is_(False)
                ).joinedload(
                    PatientRegistration.registered_by
                ),
                selectinload(
                    Patient.identifiers
                ).filter(
                    PatientIdentifier.is_deleted.is_(False)
                ),
                selectinload(
                    Patient.attachments
                ).filter(
                    PatientAttachment.is_deleted.is_(False)
                ),
                selectinload(
                    Patient.consent_records
                ).filter(
                    PatientConsent.is_deleted.is_(False)
                ),
                selectinload(
                    Patient.scanned_forms
                ).filter(
                    PatientScannedForm.is_deleted.is_(False)
                ),
                selectinload(
                    Patient.demographic_audits
                ).filter(
                    PatientDemographicAudit.is_deleted.is_(False)
                ),
                selectinload(
                    Patient.insurance_records
                ).filter(
                    PatientInsurance.is_deleted.is_(False)
                ).joinedload(
                    PatientInsurance.insurance_provider
                ),
                selectinload(
                    Patient.loyalty_memberships
                ).filter(
                    PatientLoyalty.is_deleted.is_(False)
                ).joinedload(
                    PatientLoyalty.loyalty_program
                ),
                joinedload(Patient.preferred_payer),
                selectinload(Patient.appointments),
                selectinload(Patient.visits),
                selectinload(Patient.admissions),
                selectinload(Patient.billings),
                selectinload(Patient.invoices),
                selectinload(Patient.notifications),
            )
            .filter(
                Patient.id == patient_id,
                Patient.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # CREATE / UPDATE / DELETE
    # ============================================================

    def create_patient(
        self,
        *,
        global_patient_id: str,
        hospital_number: str,
        first_name: str,
        last_name: str,
        middle_name: Optional[str] = None,
        date_of_birth=None,
        gender=None,
        marital_status=None,
        phone_number: Optional[str] = None,
        alternate_phone_number: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        blood_group=None,
        genotype=None,
        allergies: Optional[str] = None,
        emergency_contact_name: Optional[str] = None,
        emergency_contact_phone: Optional[str] = None,
        emergency_contact_relationship: Optional[str] = None,
        next_of_kin_name: Optional[str] = None,
        next_of_kin_phone: Optional[str] = None,
        next_of_kin_relationship: Optional[str] = None,
        next_of_kin_address: Optional[str] = None,
        patient_type=None,
        preferred_payer_id: Optional[int] = None,
        payer_type: Optional[str] = None,
        national_identifier: Optional[str] = None,
        national_identifier_type: Optional[str] = None,
        identification_details: Optional[dict] = None,
    ) -> Patient:
        patient = Patient(
            global_patient_id=global_patient_id,
            hospital_number=hospital_number,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            date_of_birth=date_of_birth,
            gender=gender,
            marital_status=marital_status,
            phone_number=phone_number,
            alternate_phone_number=alternate_phone_number,
            email=email,
            address=address,
            city=city,
            state=state,
            country=country,
            blood_group=blood_group,
            genotype=genotype,
            allergies=allergies,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            emergency_contact_relationship=emergency_contact_relationship,
            next_of_kin_name=next_of_kin_name,
            next_of_kin_phone=next_of_kin_phone,
            next_of_kin_relationship=next_of_kin_relationship,
            next_of_kin_address=next_of_kin_address,
            patient_type=patient_type,
            preferred_payer_id=preferred_payer_id,
            payer_type=payer_type,
            national_identifier=national_identifier,
            national_identifier_type=national_identifier_type,
            identification_details=identification_details,
        )
        self.db.add(patient)
        self.db.flush()
        self.db.refresh(patient)
        return patient

    def update_patient(self, patient: Patient) -> Patient:
        self.db.add(patient)
        self.db.flush()
        self.db.refresh(patient)
        return patient

    def soft_delete_patient(self, patient: Patient) -> Patient:
        patient.is_deleted = True
        self.db.add(patient)
        self.db.flush()
        return patient

    # ============================================================
    # REGISTRATION EVENTS
    # ============================================================

    def create_registration_event(
        self,
        *,
        patient_id: int,
        registered_by_id: Optional[int] = None,
        registration_date: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> PatientRegistration:
        event = PatientRegistration(
            patient_id=patient_id,
            registered_by_id=registered_by_id,
            registration_date=registration_date or datetime.now(timezone.utc),
            notes=notes,
        )
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def list_registration_events(
        self,
        patient_id: int,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[PatientRegistration], int]:
        base_filters = [
            PatientRegistration.patient_id == patient_id,
            PatientRegistration.is_deleted.is_(False),
        ]
        
        # 1. Count
        total = (
            self.db.query(func.count(PatientRegistration.id))
            .filter(*base_filters)
            .scalar()
            or 0
        )

        if total == 0:
            return [], 0

        # 2. Data
        items = (
            self.db.query(PatientRegistration)
            .options(joinedload(PatientRegistration.registered_by))
            .filter(*base_filters)
            .order_by(PatientRegistration.registration_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, int(total)

    # ============================================================
    # INSURANCE ENROLLMENT
    # ============================================================

    def create_patient_insurance(
        self,
        *,
        patient_id: int,
        insurance_provider_id: int,
        policy_number: str,
        member_id: Optional[str] = None,
        plan_name: Optional[str] = None,
        coverage_details: Optional[dict] = None,
        status=None,
        valid_from=None,
        valid_to=None,
        note: Optional[str] = None,
    ) -> PatientInsurance:
        """
        Create patient insurance enrollment.

        Adjust field names here only if your final PatientInsurance ORM differs.
        """
        insurance = PatientInsurance(
            patient_id=patient_id,
            insurance_provider_id=insurance_provider_id,
            policy_number=policy_number,
            member_id=member_id,
            plan_name=plan_name,
            coverage_details=coverage_details,
            status=status,
            policy_status=status or "ACTIVE",
            valid_from=valid_from,
            coverage_start_date=valid_from,
            valid_to=valid_to,
            coverage_end_date=valid_to,
            note=note,
        )
        self.db.add(insurance)
        self.db.flush()
        self.db.refresh(insurance)
        return insurance

    def list_patient_insurance_records(self, patient_id: int) -> list[PatientInsurance]:
        return (
            self.db.query(PatientInsurance)
            .filter(
                PatientInsurance.patient_id == patient_id,
                PatientInsurance.is_deleted.is_(False),
            )
            .order_by(PatientInsurance.date_created.desc())
            .all()
        )

    def find_patient_insurance_by_policy_number(
        self,
        *,
        insurance_provider_id: int,
        policy_number: str,
    ) -> Optional[PatientInsurance]:
        return (
            self.db.query(PatientInsurance)
            .filter(
                PatientInsurance.insurance_provider_id == insurance_provider_id,
                PatientInsurance.policy_number == policy_number,
                PatientInsurance.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # LOYALTY ENROLLMENT
    # ============================================================

    def create_patient_loyalty_membership(
        self,
        *,
        patient_id: int,
        loyalty_program_id: int,
        membership_no: str,
        points_balance: Decimal | int | float = Decimal("0"),
        joined_date: Optional[datetime] = None,
        note: Optional[str] = None,
    ) -> PatientLoyalty:
        membership = PatientLoyalty(
            patient_id=patient_id,
            loyalty_program_id=loyalty_program_id,
            membership_no=membership_no,
            points_balance=points_balance,
            joined_date=joined_date or datetime.now(timezone.utc),
            note=note,
        )
        self.db.add(membership)
        self.db.flush()
        self.db.refresh(membership)
        return membership

    def list_patient_loyalty_memberships(self, patient_id: int) -> list[PatientLoyalty]:
        return (
            self.db.query(PatientLoyalty)
            .filter(
                PatientLoyalty.patient_id == patient_id,
                PatientLoyalty.is_deleted.is_(False),
            )
            .order_by(PatientLoyalty.joined_date.desc())
            .all()
        )

    def get_patient_loyalty_by_membership_no(self, membership_no: str) -> Optional[PatientLoyalty]:
        return (
            self.db.query(PatientLoyalty)
            .filter(
                PatientLoyalty.membership_no == membership_no,
                PatientLoyalty.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # IDENTIFIERS
    # ============================================================

    def create_patient_identifier(
        self,
        *,
        patient_id: int,
        identifier_type: str,
        identifier_value: str,
        issuing_authority: Optional[str] = None,
        is_primary: bool = False,
        is_active: bool = True,
        note: Optional[str] = None,
    ) -> PatientIdentifier:
        identifier = PatientIdentifier(
            patient_id=patient_id,
            identifier_type=identifier_type,
            identifier_value=identifier_value,
            issuing_authority=issuing_authority,
            is_primary=is_primary,
            is_active=is_active,
            note=note,
        )
        self.db.add(identifier)
        self.db.flush()
        self.db.refresh(identifier)
        return identifier

    def get_identifier_by_type_and_value(
        self,
        *,
        identifier_type: str,
        identifier_value: str,
    ) -> Optional[PatientIdentifier]:
        return (
            self.db.query(PatientIdentifier)
            .filter(
                PatientIdentifier.identifier_type == identifier_type,
                PatientIdentifier.identifier_value == identifier_value,
                PatientIdentifier.is_deleted.is_(False),
            )
            .first()
        )

    def list_patient_identifiers(self, patient_id: int) -> list[PatientIdentifier]:
        return (
            self.db.query(PatientIdentifier)
            .filter(
                PatientIdentifier.patient_id == patient_id,
                PatientIdentifier.is_deleted.is_(False),
            )
            .order_by(PatientIdentifier.is_primary.desc(), PatientIdentifier.date_created.desc())
            .all()
        )

    # ============================================================
    # MPI LIST / SEARCH
    # ============================================================

    def list_patients(self, *, skip: int = 0, limit: int = 20) -> tuple[list[Patient], int]:
        # 1. Count
        total = (
            self.db.query(func.count(Patient.id))
            .filter(Patient.is_deleted.is_(False))
            .scalar()
            or 0
        )

        if total == 0:
            return [], 0

        # 2. Data
        items = (
            self.db.query(Patient)
            .options(
                joinedload(Patient.preferred_payer),
                selectinload(
                    Patient.insurance_records
                ).filter(PatientInsurance.is_deleted.is_(False)),
                selectinload(
                    Patient.loyalty_memberships
                ).filter(PatientLoyalty.is_deleted.is_(False)),
            )
            .filter(Patient.is_deleted.is_(False))
            .order_by(Patient.last_name.asc(), Patient.first_name.asc(), Patient.hospital_number.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

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
    ) -> tuple[list[Patient], int]:
        # Define base filters to reuse
        base_filters = [Patient.is_deleted.is_(False)]

        if hospital_number:
            base_filters.append(Patient.hospital_number == hospital_number)

        if full_name:
            like_term = f"%{full_name.strip()}%"
            base_filters.append(
                or_(
                    func.concat(Patient.first_name, " ", Patient.last_name).ilike(like_term),
                    func.concat(Patient.first_name, " ", Patient.middle_name, " ", Patient.last_name).ilike(like_term),
                    Patient.first_name.ilike(like_term),
                    Patient.last_name.ilike(like_term),
                    Patient.middle_name.ilike(like_term),
                )
            )

        if phone_number:
            base_filters.append(
                or_(
                    Patient.phone_number == phone_number,
                    Patient.alternate_phone_number == phone_number,
                    Patient.emergency_contact_phone == phone_number,
                    Patient.next_of_kin_phone == phone_number,
                )
            )

        if date_of_birth is not None:
            base_filters.append(Patient.date_of_birth == date_of_birth)
        if email:
            base_filters.append(Patient.email == email)
        if city:
            base_filters.append(Patient.city.ilike(f"%{city.strip()}%"))
        if state:
            base_filters.append(Patient.state.ilike(f"%{state.strip()}%"))
        if patient_type is not None:
            base_filters.append(Patient.patient_type == patient_type)
        if payer_type:
            base_filters.append(Patient.payer_type == payer_type)
        if national_identifier:
            base_filters.append(Patient.national_identifier == national_identifier)

        # 1. Count
        total = (
            self.db.query(func.count(Patient.id))
            .filter(*base_filters)
            .scalar()
            or 0
        )

        if total == 0:
            return [], 0

        # 2. Data
        items = (
            self.db.query(Patient)
            .filter(*base_filters)
            .options(
                joinedload(Patient.preferred_payer),
                selectinload(
                    Patient.insurance_records
                ).filter(PatientInsurance.is_deleted.is_(False)),
                selectinload(
                    Patient.loyalty_memberships
                ).filter(PatientLoyalty.is_deleted.is_(False)),
            )
            .order_by(Patient.last_name.asc(), Patient.first_name.asc(), Patient.hospital_number.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    # ============================================================
    # DUPLICATE DETECTION
    # ============================================================

    def find_possible_duplicates(
        self,
        *,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        middle_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        date_of_birth=None,
        national_identifier: Optional[str] = None,
        previous_record_identifiers: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[Patient]:
        query = self.db.query(Patient).filter(Patient.is_deleted.is_(False))
        conditions = []

        if first_name and last_name and date_of_birth is not None:
            conditions.append(
                and_(
                    func.lower(Patient.first_name) == first_name.strip().lower(),
                    func.lower(Patient.last_name) == last_name.strip().lower(),
                    Patient.date_of_birth == date_of_birth,
                )
            )

        if phone_number:
            conditions.append(
                or_(
                    Patient.phone_number == phone_number,
                    Patient.alternate_phone_number == phone_number,
                )
            )

        if first_name and last_name and phone_number:
            conditions.append(
                and_(
                    func.lower(Patient.first_name) == first_name.strip().lower(),
                    func.lower(Patient.last_name) == last_name.strip().lower(),
                    or_(
                        Patient.phone_number == phone_number,
                        Patient.alternate_phone_number == phone_number,
                    ),
                )
            )

        if middle_name and first_name and last_name:
            conditions.append(
                and_(
                    func.lower(Patient.first_name) == first_name.strip().lower(),
                    func.lower(Patient.middle_name) == middle_name.strip().lower(),
                    func.lower(Patient.last_name) == last_name.strip().lower(),
                )
            )

        if national_identifier:
            conditions.append(Patient.national_identifier == national_identifier)

            identifier_match = (
                self.db.query(Patient.id)
                .join(PatientIdentifier, PatientIdentifier.patient_id == Patient.id)
                .filter(
                    PatientIdentifier.identifier_value == national_identifier,
                    PatientIdentifier.is_deleted.is_(False),
                    Patient.is_deleted.is_(False),
                )
                .subquery()
            )
            conditions.append(Patient.id.in_(identifier_match))

        if previous_record_identifiers:
            previous_match = (
                self.db.query(Patient.id)
                .join(PatientIdentifier, PatientIdentifier.patient_id == Patient.id)
                .filter(
                    PatientIdentifier.identifier_type.in_(["PREVIOUS_RECORD_ID", "EXTERNAL_MRN"]),
                    PatientIdentifier.identifier_value.in_(previous_record_identifiers),
                    PatientIdentifier.is_deleted.is_(False),
                    Patient.is_deleted.is_(False),
                )
                .subquery()
            )
            conditions.append(Patient.id.in_(previous_match))

        if not conditions:
            return []

        return (
            query.filter(or_(*conditions))
            .order_by(Patient.date_updated.desc(), Patient.date_created.desc())
            .limit(limit)
            .all()
        )

    # ============================================================
    # DUPLICATE REVIEW / LINK EXISTING SUPPORT
    # ============================================================

    def get_existing_patient_for_duplicate_link(self, patient_id: int) -> Optional[Patient]:
        """
        Return the patient to link to after registrar duplicate review.
        """
        return self.get_by_id(patient_id)

    # ============================================================
    # UNIQUENESS / EXISTENCE HELPERS
    # ============================================================

    def hospital_number_exists(self, hospital_number: str) -> bool:
        count = (
            self.db.query(func.count(Patient.id))
            .filter(
                Patient.hospital_number == hospital_number,
                Patient.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )
        return count > 0

    def patient_has_visits(self, patient_id: int) -> bool:
        patient = self.get_detailed_by_id(patient_id)
        return bool(patient and patient.visits)

    def patient_has_admissions(self, patient_id: int) -> bool:
        patient = self.get_detailed_by_id(patient_id)
        return bool(patient and patient.admissions)

    def patient_has_billing(self, patient_id: int) -> bool:
        patient = self.get_detailed_by_id(patient_id)
        return bool(patient and (patient.billings or patient.invoices))

    # ============================================================
    # S3-BASED PHOTO / ATTACHMENT / FORM STORAGE
    # ============================================================

    def upload_patient_photo(
        self,
        *,
        patient: Patient,
        file_bytes: bytes,
        file_name: str,
        content_type: Optional[str] = None,
        uploaded_by_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> dict:
        object_key = build_s3_object_key(
            folder=f"patients/{patient.id}/photos",
            filename=file_name,
            prefix="photo",
            include_timestamp=True,
        )

        metadata = upload_bytes_to_s3(
            data=file_bytes,
            object_name=object_key,
            file_name=file_name,
            content_type=content_type,
            metadata={
                "patient_id": str(patient.id),
                "attachment_type": "PHOTO",
            },
        )

        patient.photo_file_name = str(metadata["file_name"])
        patient.photo_file_key = str(metadata["file_key"])
        patient.photo_file_url = str(metadata["file_url"])
        self.db.add(patient)
        self.db.flush()

        attachment = PatientAttachment(
            patient_id=patient.id,
            uploaded_by_id=uploaded_by_id,
            attachment_type="PHOTO",
            title="Patient Photo",
            file_name=str(metadata["file_name"]),
            file_key=str(metadata["file_key"]),
            file_url=str(metadata["file_url"]),
            content_type=str(metadata["content_type"]),
            checksum=str(metadata["checksum"]),
            is_primary=True,
            note=note,
        )
        self.db.add(attachment)
        self.db.flush()
        self.db.refresh(attachment)

        return {
            "attachment_id": attachment.id,
            "patient_id": patient.id,
            "file_name": attachment.file_name,
            "file_key": attachment.file_key,
            "file_url": attachment.file_url,
            "content_type": attachment.content_type,
            "checksum": attachment.checksum,
            "presigned_url": generate_presigned_url_image(attachment.file_key),
        }

    def create_patient_attachment(
        self,
        *,
        patient_id: int,
        attachment_type: str,
        file_bytes: bytes,
        file_name: str,
        uploaded_by_id: Optional[int] = None,
        title: Optional[str] = None,
        content_type: Optional[str] = None,
        note: Optional[str] = None,
        is_primary: bool = False,
    ) -> PatientAttachment:
        object_key = build_s3_object_key(
            folder=f"patients/{patient_id}/attachments",
            filename=file_name,
            prefix=attachment_type.lower(),
            include_timestamp=True,
        )

        metadata = upload_bytes_to_s3(
            data=file_bytes,
            object_name=object_key,
            file_name=file_name,
            content_type=content_type,
            metadata={
                "patient_id": str(patient_id),
                "attachment_type": attachment_type,
            },
        )

        attachment = PatientAttachment(
            patient_id=patient_id,
            uploaded_by_id=uploaded_by_id,
            attachment_type=attachment_type,
            title=title,
            file_name=str(metadata["file_name"]),
            file_key=str(metadata["file_key"]),
            file_url=str(metadata["file_url"]),
            content_type=str(metadata["content_type"]),
            checksum=str(metadata["checksum"]),
            is_primary=is_primary,
            note=note,
        )
        self.db.add(attachment)
        self.db.flush()
        self.db.refresh(attachment)
        return attachment

    def list_patient_attachments(self, patient_id: int) -> list[PatientAttachment]:
        return (
            self.db.query(PatientAttachment)
            .filter(
                PatientAttachment.patient_id == patient_id,
                PatientAttachment.is_deleted.is_(False),
            )
            .order_by(PatientAttachment.date_created.desc())
            .all()
        )

    def generate_attachment_presigned_url(self, attachment: PatientAttachment) -> Optional[str]:
        if not attachment.file_key:
            return None

        if attachment.attachment_type == "PHOTO":
            return generate_presigned_url_image(attachment.file_key)

        return generate_presigned_url_file(attachment.file_key)

    def delete_patient_attachment(
        self,
        attachment: PatientAttachment,
        *,
        delete_from_s3: bool = True,
    ) -> PatientAttachment:
        if delete_from_s3 and attachment.file_key:
            delete_file_from_s3(attachment.file_key)

        attachment.is_deleted = True
        self.db.add(attachment)
        self.db.flush()
        return attachment

    def create_patient_scanned_form(
        self,
        *,
        patient_id: int,
        form_type: str,
        file_bytes: bytes,
        file_name: str,
        uploaded_by_id: Optional[int] = None,
        content_type: Optional[str] = None,
        note: Optional[str] = None,
    ) -> PatientScannedForm:
        object_key = build_s3_object_key(
            folder=f"patients/{patient_id}/scanned_forms",
            filename=file_name,
            prefix=form_type.lower(),
            include_timestamp=True,
        )

        metadata = upload_bytes_to_s3(
            data=file_bytes,
            object_name=object_key,
            file_name=file_name,
            content_type=content_type,
            metadata={
                "patient_id": str(patient_id),
                "form_type": form_type,
            },
        )

        form = PatientScannedForm(
            patient_id=patient_id,
            uploaded_by_id=uploaded_by_id,
            form_type=form_type,
            file_name=str(metadata["file_name"]),
            file_key=str(metadata["file_key"]),
            file_url=str(metadata["file_url"]),
            content_type=str(metadata["content_type"]),
            checksum=str(metadata["checksum"]),
            note=note,
        )
        self.db.add(form)
        self.db.flush()
        self.db.refresh(form)
        return form

    # ============================================================
    # CONSENT RECORDS
    # ============================================================

    def create_patient_consent_record(
        self,
        *,
        patient_id: int,
        consent_type: str,
        consent_status: str,
        recorded_by_id: Optional[int] = None,
        consent_date: Optional[datetime] = None,
        expiry_date: Optional[datetime] = None,
        document_file_name: Optional[str] = None,
        document_file_key: Optional[str] = None,
        document_file_url: Optional[str] = None,
        note: Optional[str] = None,
    ) -> PatientConsent:
        consent = PatientConsent(
            patient_id=patient_id,
            recorded_by_id=recorded_by_id,
            consent_type=consent_type,
            consent_status=consent_status,
            consent_date=consent_date,
            expiry_date=expiry_date,
            document_file_name=document_file_name,
            document_file_key=document_file_key,
            document_file_url=document_file_url,
            note=note,
        )
        self.db.add(consent)
        self.db.flush()
        self.db.refresh(consent)
        return consent

    def list_patient_consents(self, patient_id: int) -> list[PatientConsent]:
        return (
            self.db.query(PatientConsent)
            .filter(
                PatientConsent.patient_id == patient_id,
                PatientConsent.is_deleted.is_(False),
            )
            .order_by(PatientConsent.consent_date.desc(), PatientConsent.date_created.desc())
            .all()
        )

    # ============================================================
    # DEMOGRAPHIC AUDIT HISTORY
    # ============================================================

    def log_patient_demographic_change(
        self,
        *,
        patient_id: int,
        changed_by_id: Optional[int] = None,
        change_source: Optional[str] = None,
        changed_at: Optional[datetime] = None,
        before_snapshot: Optional[dict] = None,
        after_snapshot: Optional[dict] = None,
        changed_fields: Optional[list] = None,
        note: Optional[str] = None,
    ) -> PatientDemographicAudit:
        audit = PatientDemographicAudit(
            patient_id=patient_id,
            changed_by_id=changed_by_id,
            change_source=change_source,
            changed_at=changed_at or datetime.now(timezone.utc),
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            changed_fields=changed_fields,
            note=note,
        )
        self.db.add(audit)
        self.db.flush()
        self.db.refresh(audit)
        return audit