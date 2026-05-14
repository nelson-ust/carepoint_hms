from __future__ import annotations

"""
app.schemas.patient_schemas

Pydantic schemas for patient registration, Master Patient Index (MPI),
duplicate review, patient insurance enrollment, loyalty enrollment,
attachments, consent records, scanned forms, and demographic audit history.

Purpose
-------
This module defines request and response schemas for:

- first-time patient registration
- duplicate detection and duplicate resolution
- patient demographic updates
- patient insurance enrollment
- patient loyalty enrollment
- patient identifier management
- patient photo / document / scanned-form metadata
- consent records
- demographic audit history

Requirements coverage
---------------------
This schema module is designed to support:

1. Search existing records to avoid duplicates
2. Capture demographics, contacts, emergency contact, and administrative details
3. Generate hospital number
4. Create patient registration record
5. Optionally create insurance or loyalty enrollment if applicable
6. Registrar duplicate review outcome:
   - link to existing patient
   - continue after override
7. Save patient first and attach insurance later when insurance details are incomplete

Associated models
-----------------
- Patient
- PatientRegistration
- PatientInsurance
- PatientLoyalty
- PatientIdentifier
- PatientAttachment
- PatientConsent
- PatientScannedForm
- PatientDemographicAudit
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.enums import (
    BloodGroup,
    Gender,
    Genotype,
    MaritalStatus,
    PatientType,
)


# ============================================================
# SHARED / EMBEDDED LITE SCHEMAS
# ============================================================

class RegisteredByLiteSchema(BaseModel):
    """
    Lightweight user representation for patient registration history.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    first_name: str
    last_name: str


class PayerLiteSchema(BaseModel):
    """
    Lightweight payer representation for nested patient responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    payer_type: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None


class InsuranceProviderLiteSchema(BaseModel):
    """
    Lightweight insurance provider representation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    phone_number: Optional[str] = None
    email: Optional[str] = None


class LoyaltyProgramLiteSchema(BaseModel):
    """
    Lightweight loyalty program representation.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None


# ============================================================
# IDENTIFIER SCHEMAS
# ============================================================

class PatientIdentifierBaseSchema(BaseModel):
    """
    Base schema for flexible patient identifiers.

    Examples
    --------
    - NATIONAL_ID
    - PREVIOUS_RECORD_ID
    - PASSPORT
    - INSURANCE_MEMBER_ID
    - EXTERNAL_MRN
    """

    identifier_type: str = Field(..., min_length=1, max_length=50)
    identifier_value: str = Field(..., min_length=1, max_length=150)
    issuing_authority: Optional[str] = Field(None, max_length=150)
    is_primary: bool = False
    is_active: bool = True
    note: Optional[str] = None

    @field_validator("identifier_type", "identifier_value", "issuing_authority")
    @classmethod
    def normalize_identifier_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if value and not normalized:
            raise ValueError("Identifier field cannot be empty.")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class PatientIdentifierCreateSchema(PatientIdentifierBaseSchema):
    """
    Schema for creating a patient identifier.
    """
    pass


class PatientIdentifierUpdateSchema(BaseModel):
    """
    Schema for updating a patient identifier.
    """

    identifier_type: Optional[str] = Field(None, min_length=1, max_length=50)
    identifier_value: Optional[str] = Field(None, min_length=1, max_length=150)
    issuing_authority: Optional[str] = Field(None, max_length=150)
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    note: Optional[str] = None

    @field_validator("identifier_type", "identifier_value", "issuing_authority")
    @classmethod
    def normalize_identifier_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Identifier field cannot be empty.")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class PatientIdentifierReadSchema(BaseModel):
    """
    Read schema for patient identifiers.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    identifier_type: str
    identifier_value: str
    issuing_authority: Optional[str] = None
    is_primary: bool
    is_active: bool
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# ATTACHMENT / PHOTO / CONSENT / SCANNED FORM SCHEMAS
# ============================================================

class PatientPhotoSchema(BaseModel):
    """
    Patient photo metadata.
    """

    file_name: Optional[str] = None
    file_key: Optional[str] = None
    file_url: Optional[str] = None


class PatientAttachmentBaseSchema(BaseModel):
    """
    Base schema for patient attachments/documents.
    """

    attachment_type: str = Field(..., min_length=1, max_length=50)
    title: Optional[str] = Field(None, max_length=255)
    file_name: str = Field(..., min_length=1, max_length=255)
    file_key: Optional[str] = Field(None, max_length=500)
    file_url: Optional[str] = None
    content_type: Optional[str] = Field(None, max_length=100)
    checksum: Optional[str] = Field(None, max_length=128)
    is_primary: bool = False
    note: Optional[str] = None

    @field_validator("attachment_type", "title", "file_name", "file_key", "content_type", "checksum")
    @classmethod
    def normalize_attachment_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if value and not normalized:
            raise ValueError("Attachment field cannot be empty.")
        return normalized

    @field_validator("note", "file_url")
    @classmethod
    def normalize_attachment_free_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class PatientAttachmentCreateSchema(PatientAttachmentBaseSchema):
    """
    Schema for creating a patient attachment.
    """
    pass


class PatientAttachmentReadSchema(BaseModel):
    """
    Read schema for patient attachments.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    uploaded_by_id: Optional[int] = None
    attachment_type: str
    title: Optional[str] = None
    file_name: str
    file_key: Optional[str] = None
    file_url: Optional[str] = None
    content_type: Optional[str] = None
    checksum: Optional[str] = None
    is_primary: bool
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PatientConsentBaseSchema(BaseModel):
    """
    Base schema for patient consent records.
    """

    consent_type: str = Field(..., min_length=1, max_length=100)
    consent_status: str = Field(..., min_length=1, max_length=50)
    consent_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    document_file_name: Optional[str] = Field(None, max_length=255)
    document_file_key: Optional[str] = Field(None, max_length=500)
    document_file_url: Optional[str] = None
    note: Optional[str] = None

    @field_validator("consent_type", "consent_status", "document_file_name", "document_file_key")
    @classmethod
    def normalize_consent_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if value and not normalized:
            raise ValueError("Consent field cannot be empty.")
        return normalized

    @field_validator("document_file_url", "note")
    @classmethod
    def normalize_consent_free_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class PatientConsentCreateSchema(PatientConsentBaseSchema):
    """
    Schema for creating a patient consent record.
    """
    pass


class PatientConsentReadSchema(BaseModel):
    """
    Read schema for patient consent records.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    recorded_by_id: Optional[int] = None
    consent_type: str
    consent_status: str
    consent_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    document_file_name: Optional[str] = None
    document_file_key: Optional[str] = None
    document_file_url: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PatientScannedFormBaseSchema(BaseModel):
    """
    Base schema for scanned forms.
    """

    form_type: str = Field(..., min_length=1, max_length=100)
    file_name: str = Field(..., min_length=1, max_length=255)
    file_key: Optional[str] = Field(None, max_length=500)
    file_url: Optional[str] = None
    content_type: Optional[str] = Field(None, max_length=100)
    checksum: Optional[str] = Field(None, max_length=128)
    note: Optional[str] = None

    @field_validator("form_type", "file_name", "file_key", "content_type", "checksum")
    @classmethod
    def normalize_form_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if value and not normalized:
            raise ValueError("Scanned form field cannot be empty.")
        return normalized

    @field_validator("file_url", "note")
    @classmethod
    def normalize_form_free_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class PatientScannedFormCreateSchema(PatientScannedFormBaseSchema):
    """
    Schema for creating a scanned patient form.
    """
    pass


class PatientScannedFormReadSchema(BaseModel):
    """
    Read schema for scanned patient forms.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    uploaded_by_id: Optional[int] = None
    form_type: str
    file_name: str
    file_key: Optional[str] = None
    file_url: Optional[str] = None
    content_type: Optional[str] = None
    checksum: Optional[str] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# INSURANCE / LOYALTY REGISTRATION SCHEMAS
# ============================================================

class PatientInsuranceEnrollmentSchema(BaseModel):
    """
    Optional insurance-enrollment payload that can be supplied during
    first-time patient registration or attached later.

    Notes
    -----
    This is designed to map to PatientInsurance.
    """

    insurance_provider_id: int = Field(..., gt=0)
    policy_number: str = Field(..., min_length=1, max_length=100)
    member_id: Optional[str] = Field(None, max_length=100)
    plan_name: Optional[str] = Field(None, max_length=150)
    coverage_details: Optional[dict[str, Any]] = None
    status: Optional[str] = Field(
        None,
        max_length=50,
        description="Insurance policy status, if your model/service supports it.",
    )
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    note: Optional[str] = None

    @field_validator("policy_number", "member_id", "plan_name", "status")
    @classmethod
    def normalize_insurance_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if value and not normalized:
            raise ValueError("Insurance field cannot be empty.")
        return normalized

    @field_validator("note")
    @classmethod
    def normalize_insurance_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class PatientInsuranceReadSchema(BaseModel):
    """
    Read schema for attached patient insurance.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    insurance_provider_id: Optional[int] = None
    policy_number: Optional[str] = None
    member_id: Optional[str] = None
    plan_name: Optional[str] = None
    coverage_details: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    note: Optional[str] = None
    insurance_provider: Optional[InsuranceProviderLiteSchema] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PatientLoyaltyEnrollmentSchema(BaseModel):
    """
    Optional loyalty enrollment payload for first-time registration.

    Notes
    -----
    This is designed to map to PatientLoyalty.
    """

    loyalty_program_id: int = Field(..., gt=0)
    membership_no: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional supplied membership number. Can be generated by service layer.",
    )
    points_balance: Optional[Decimal] = Field(
        default=Decimal("0"),
        description="Optional starting balance.",
    )
    joined_date: Optional[datetime] = None
    note: Optional[str] = None

    @field_validator("membership_no")
    @classmethod
    def normalize_membership_no(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("note")
    @classmethod
    def normalize_loyalty_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class PatientLoyaltyReadSchema(BaseModel):
    """
    Read schema for patient loyalty enrollment.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    loyalty_program_id: int
    membership_no: str
    points_balance: Decimal
    joined_date: datetime
    loyalty_program: Optional[LoyaltyProgramLiteSchema] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# REGISTRATION / DUPLICATE REVIEW / AUDIT SCHEMAS
# ============================================================

class PatientRegistrationReadSchema(BaseModel):
    """
    Read schema for patient registration event history.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    registered_by_id: Optional[int] = None
    registration_date: datetime
    notes: Optional[str] = None
    registered_by: Optional[RegisteredByLiteSchema] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PatientDemographicAuditReadSchema(BaseModel):
    """
    Read schema for demographic audit history.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    changed_by_id: Optional[int] = None
    change_source: Optional[str] = None
    changed_at: datetime
    before_snapshot: Optional[dict[str, Any]] = None
    after_snapshot: Optional[dict[str, Any]] = None
    changed_fields: Optional[list[Any]] = None
    note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PatientDuplicateReviewDecisionSchema(BaseModel):
    """
    Registrar decision after reviewing a possible duplicate.

    Supported outcomes
    ------------------
    - LINK_EXISTING: link registration workflow to an existing patient record
    - CONTINUE_CREATE: continue and create a new patient despite duplicate warning
    """

    decision: str = Field(..., description="LINK_EXISTING or CONTINUE_CREATE")
    existing_patient_id: Optional[int] = Field(
        None,
        description="Required when decision is LINK_EXISTING.",
    )
    review_note: Optional[str] = None

    @field_validator("decision")
    @classmethod
    def normalize_decision(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"LINK_EXISTING", "CONTINUE_CREATE"}:
            raise ValueError("decision must be LINK_EXISTING or CONTINUE_CREATE.")
        return normalized

    @field_validator("review_note")
    @classmethod
    def normalize_review_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class PatientDuplicateReviewResultSchema(BaseModel):
    """
    Result schema for duplicate review action.
    """

    success: bool = True
    decision: str
    patient_id: int
    message: str


# ============================================================
# BASE / SHARED PATIENT SCHEMAS
# ============================================================

class PatientBaseSchema(BaseModel):
    """
    Base shared patient demographic and administrative fields.
    """

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)

    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    marital_status: Optional[MaritalStatus] = None

    phone_number: Optional[str] = Field(None, max_length=30)
    alternate_phone_number: Optional[str] = Field(None, max_length=30)
    email: Optional[EmailStr] = None

    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)

    blood_group: Optional[BloodGroup] = None
    genotype: Optional[Genotype] = None
    allergies: Optional[str] = None

    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, max_length=30)
    emergency_contact_relationship: Optional[str] = Field(None, max_length=100)

    next_of_kin_name: Optional[str] = Field(None, max_length=200)
    next_of_kin_phone: Optional[str] = Field(None, max_length=30)
    next_of_kin_relationship: Optional[str] = Field(None, max_length=100)
    next_of_kin_address: Optional[str] = None

    patient_type: Optional[PatientType] = Field(PatientType.OUTPATIENT)

    preferred_payer_id: Optional[int] = None
    payer_type: Optional[str] = Field(None, max_length=100)

    national_identifier: Optional[str] = Field(None, max_length=100)
    national_identifier_type: Optional[str] = Field(None, max_length=50)
    identification_details: Optional[dict[str, Any]] = None

    @field_validator(
        "first_name",
        "last_name",
        "middle_name",
        "city",
        "state",
        "country",
        "emergency_contact_name",
        "emergency_contact_relationship",
        "next_of_kin_name",
        "next_of_kin_relationship",
        "gender",
        "marital_status",
        "patient_type",
        "blood_group",
        "genotype",
        "payer_type",
        "national_identifier",
        "national_identifier_type",
    )
    @classmethod
    def normalize_text_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("patient_type", mode="before")
    @classmethod
    def map_and_normalize_patient_type(cls, value: Any) -> Any:
        """
        Maps legacy or incorrect frontend values to valid PatientType enum values.
        Specifically handles 'INDIVIDUAL' which is often sent by the frontend
        but should be treated as 'OUTPATIENT' in the clinical flow.
        """
        if value is None:
            return value
        
        if isinstance(value, str):
            val_upper = value.strip().upper()
            if val_upper == "INDIVIDUAL":
                return PatientType.OUTPATIENT
            return val_upper
        
        return value

    @field_validator(
        "phone_number",
        "alternate_phone_number",
        "emergency_contact_phone",
        "next_of_kin_phone",
    )
    @classmethod
    def normalize_phone_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().replace(" ", "")
        return normalized or None

    @field_validator("address", "allergies", "next_of_kin_address")
    @classmethod
    def normalize_long_text_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


# ============================================================
# CREATE / UPDATE SCHEMAS
# ============================================================

class PatientCreateSchema(PatientBaseSchema):
    """
    Schema for creating a patient record.

    This supports:
    - supplied or generated MRN
    - registration event notes
    - previous identifiers
    - optional insurance enrollment
    - optional loyalty enrollment
    """

    hospital_number: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Optional supplied MRN. If omitted, system can generate one.",
    )
    registration_notes: Optional[str] = None

    previous_identifiers: list[PatientIdentifierCreateSchema] = Field(
        default_factory=list,
        description="Additional previous/external identifiers to attach during creation.",
    )

    insurance_enrollment: Optional[PatientInsuranceEnrollmentSchema] = Field(
        None,
        description="Optional insurance enrollment during registration.",
    )
    loyalty_enrollment: Optional[PatientLoyaltyEnrollmentSchema] = Field(
        None,
        description="Optional loyalty enrollment during registration.",
    )

    @field_validator("hospital_number")
    @classmethod
    def normalize_hospital_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("registration_notes")
    @classmethod
    def normalize_registration_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class PatientUpdateSchema(BaseModel):
    """
    Schema for partially updating patient demographics and administrative data.
    """

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    middle_name: Optional[str] = Field(None, max_length=100)

    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    marital_status: Optional[MaritalStatus] = None

    phone_number: Optional[str] = Field(None, max_length=30)
    alternate_phone_number: Optional[str] = Field(None, max_length=30)
    email: Optional[EmailStr] = None

    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)

    blood_group: Optional[BloodGroup] = None
    genotype: Optional[Genotype] = None
    allergies: Optional[str] = None

    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, max_length=30)
    emergency_contact_relationship: Optional[str] = Field(None, max_length=100)

    next_of_kin_name: Optional[str] = Field(None, max_length=200)
    next_of_kin_phone: Optional[str] = Field(None, max_length=30)
    next_of_kin_relationship: Optional[str] = Field(None, max_length=100)
    next_of_kin_address: Optional[str] = None

    patient_type: Optional[PatientType] = None

    preferred_payer_id: Optional[int] = None
    payer_type: Optional[str] = Field(None, max_length=100)

    national_identifier: Optional[str] = Field(None, max_length=100)
    national_identifier_type: Optional[str] = Field(None, max_length=50)
    identification_details: Optional[dict[str, Any]] = None

    @field_validator(
        "first_name",
        "last_name",
        "middle_name",
        "city",
        "state",
        "country",
        "emergency_contact_name",
        "emergency_contact_relationship",
        "next_of_kin_name",
        "next_of_kin_relationship",
        "gender",
        "marital_status",
        "patient_type",
        "blood_group",
        "genotype",
        "payer_type",
        "national_identifier",
        "national_identifier_type",
    )
    @classmethod
    def normalize_text_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("patient_type", mode="before")
    @classmethod
    def map_and_normalize_patient_type(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, str):
            val_upper = value.strip().upper()
            if val_upper == "INDIVIDUAL":
                return PatientType.OUTPATIENT
            return val_upper
        return value

    @field_validator(
        "phone_number",
        "alternate_phone_number",
        "emergency_contact_phone",
        "next_of_kin_phone",
    )
    @classmethod
    def normalize_phone_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().replace(" ", "")
        return normalized or None

    @field_validator("address", "allergies", "next_of_kin_address")
    @classmethod
    def normalize_long_text_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class PatientAttachInsuranceLaterSchema(BaseModel):
    """
    Supports the alternate flow where patient is saved first and insurance is attached later.
    """

    insurance_enrollment: PatientInsuranceEnrollmentSchema


# ============================================================
# READ / LIST SCHEMAS
# ============================================================

class PatientLiteSchema(BaseModel):
    """
    Lightweight patient representation for nested responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    global_patient_id: str
    hospital_number: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    phone_number: Optional[str] = None
    patient_type: Optional[PatientType] = None


class PatientReadSchema(BaseModel):
    """
    Full patient read schema aligned to the expanded patient registration model.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    global_patient_id: Optional[str] = ""
    hospital_number: str

    first_name: str
    last_name: str
    middle_name: Optional[str] = None

    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    marital_status: Optional[MaritalStatus] = None

    phone_number: Optional[str] = None
    alternate_phone_number: Optional[str] = None
    email: Optional[str] = None

    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    blood_group: Optional[BloodGroup] = None
    genotype: Optional[Genotype] = None
    allergies: Optional[str] = None

    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None

    next_of_kin_name: Optional[str] = None
    next_of_kin_phone: Optional[str] = None
    next_of_kin_relationship: Optional[str] = None
    next_of_kin_address: Optional[str] = None

    patient_type: Optional[PatientType] = None

    preferred_payer_id: Optional[int] = None
    payer_type: Optional[str] = None
    preferred_payer: Optional[PayerLiteSchema] = None

    national_identifier: Optional[str] = None
    national_identifier_type: Optional[str] = None
    identification_details: Optional[dict[str, Any]] = None

    photo: Optional[PatientPhotoSchema] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_photo_and_defaults(cls, data: Any) -> Any:
        if hasattr(data, "photo_file_name") and (data.photo_file_name or data.photo_file_url):
            data.photo = {
                "file_name": data.photo_file_name,
                "file_key": data.photo_file_key,
                "file_url": data.photo_file_url,
            }
        return data

    registrations: list[PatientRegistrationReadSchema] = Field(default_factory=list)
    identifiers: list[PatientIdentifierReadSchema] = Field(default_factory=list)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PatientExtendedReadSchema(PatientReadSchema):
    """
    Extended patient read schema with registration artifacts, insurance,
    loyalty enrollment, consent records, scanned forms, and audits.
    """

    insurance_records: list[PatientInsuranceReadSchema] = Field(default_factory=list)
    loyalty_memberships: list[PatientLoyaltyReadSchema] = Field(default_factory=list)
    document_attachments: list[PatientAttachmentReadSchema] = Field(default_factory=list)
    consent_records: list[PatientConsentReadSchema] = Field(default_factory=list)
    scanned_forms: list[PatientScannedFormReadSchema] = Field(default_factory=list)
    demographic_audits: list[PatientDemographicAuditReadSchema] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def map_extended_relationships(cls, data: Any) -> Any:
        # Map ORM relationship names to schema field names if they differ
        if hasattr(data, "attachments") and not hasattr(data, "document_attachments"):
            data.document_attachments = data.attachments
        return data


class PatientListItemSchema(BaseModel):
    """
    Patient list item schema for MPI list/search results.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    hospital_number: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    patient_type: Optional[PatientType] = None
    payer_type: Optional[str] = None
    national_identifier: Optional[str] = None


class PatientListResponseSchema(BaseModel):
    """
    Paginated patient list response schema.
    """

    success: bool = True
    message: str = "Patients fetched successfully."
    items: list[PatientListItemSchema]
    count: int
    meta: dict


# ============================================================
# DUPLICATE DETECTION / MPI SEARCH
# ============================================================

class PatientDuplicateCheckSchema(BaseModel):
    """
    Schema for duplicate-detection checks before or during registration.
    """

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    phone_number: Optional[str] = None
    date_of_birth: Optional[date] = None

    national_identifier: Optional[str] = None
    previous_record_identifiers: list[str] = Field(default_factory=list)

    @field_validator("first_name", "last_name", "middle_name", "national_identifier")
    @classmethod
    def normalize_names_and_identifiers(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().replace(" ", "")
        return normalized or None


class PatientDuplicateCandidateSchema(BaseModel):
    """
    Candidate match returned by duplicate detection.
    """

    patient: PatientLiteSchema
    match_score: float = Field(..., ge=0, le=100)
    matched_on: list[str] = Field(default_factory=list)


class PatientDuplicateCheckResponseSchema(BaseModel):
    """
    Response schema for duplicate detection results.
    """

    success: bool = True
    possible_duplicate_found: bool
    candidates: list[PatientDuplicateCandidateSchema] = Field(default_factory=list)
    message: str


class PatientMPISearchSchema(BaseModel):
    """
    Master Patient Index search/filter schema.
    """

    hospital_number: Optional[str] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    date_of_birth: Optional[date] = None
    email: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    patient_type: Optional[PatientType] = None
    payer_type: Optional[str] = None
    national_identifier: Optional[str] = None

    @field_validator(
        "hospital_number",
        "full_name",
        "email",
        "city",
        "state",
        "patient_type",
        "payer_type",
        "national_identifier",
    )
    @classmethod
    def normalize_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("phone_number")
    @classmethod
    def normalize_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return value.strip().replace(" ", "") or None


# ============================================================
# REGISTRATION WORKFLOW RESPONSE SCHEMAS
# ============================================================

class PatientRegistrationCreateResultSchema(BaseModel):
    """
    Response schema for successful new patient registration.
    """

    success: bool = True
    patient_id: int
    hospital_number: str
    registration_id: int
    insurance_record_id: Optional[int] = None
    loyalty_membership_id: Optional[int] = None
    message: str


class PatientLinkExistingRegistrationResultSchema(BaseModel):
    """
    Response schema when registrar links to an existing patient after duplicate review.
    """

    success: bool = True
    patient_id: int
    hospital_number: str
    message: str


# ============================================================
# GENERIC ACTION RESPONSE
# ============================================================

class PatientActionResponseSchema(BaseModel):
    """
    Generic action response for patient-related mutations.
    """

    success: bool = True
    message: str