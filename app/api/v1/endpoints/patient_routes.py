from __future__ import annotations

"""
app.api.v1.endpoints.patient_routes

FastAPI routes for patient registration and Master Patient Index (MPI).

Purpose
-------
This module exposes API endpoints for:

- first-time patient registration
- duplicate checking and duplicate review resolution
- MPI listing and searching
- patient demographic updates
- patient identifier management
- patient insurance attachment
- patient loyalty-aware registration
- patient photo / attachment / scanned form upload
- patient consent creation
- patient deletion

Security
--------
These endpoints are intended for authorized registration/admin staff and are
protected with the admin dependency.
"""

from datetime import date
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.schemas.patient_schemas import (
    PatientActionResponseSchema,
    PatientAttachInsuranceLaterSchema,
    PatientAttachmentCreateSchema,
    PatientAttachmentReadSchema,
    PatientConsentCreateSchema,
    PatientConsentReadSchema,
    PatientCreateSchema,
    PatientDuplicateCheckResponseSchema,
    PatientDuplicateCheckSchema,
    PatientDuplicateReviewDecisionSchema,
    PatientDuplicateReviewResultSchema,
    PatientExtendedReadSchema,
    PatientIdentifierCreateSchema,
    PatientIdentifierReadSchema,
    PatientInsuranceReadSchema,
    PatientLinkExistingRegistrationResultSchema,
    PatientListResponseSchema,
    PatientLoyaltyReadSchema,
    PatientReadSchema,
    PatientRegistrationCreateResultSchema,
    PatientScannedFormCreateSchema,
    PatientScannedFormReadSchema,
    PatientUpdateSchema,
)
from app.services.patient_service import PatientService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/patients",
    tags=["Patient Registration & MPI"],
)


def get_patient_service(
    db: Annotated[Session, Depends(get_db)],
) -> PatientService:
    """
    Dependency provider for the patient service.
    """
    return PatientService(db)


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def _safe_enum(value) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _serialize_registered_by(user) -> Optional[dict[str, Any]]:
    if not user:
        return None

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }


def _serialize_payer(payer) -> Optional[dict[str, Any]]:
    if not payer:
        return None

    return {
        "id": payer.id,
        "name": payer.name,
        "code": payer.code,
        "payer_type": _safe_enum(getattr(payer, "payer_type", None)),
        "phone_number": getattr(payer, "phone_number", None),
        "email": getattr(payer, "email", None),
    }


def _serialize_insurance_provider(provider) -> Optional[dict[str, Any]]:
    if not provider:
        return None

    return {
        "id": provider.id,
        "name": provider.name,
        "code": provider.code,
        "phone_number": getattr(provider, "phone_number", None),
        "email": getattr(provider, "email", None),
    }


def _serialize_loyalty_program(program) -> Optional[dict[str, Any]]:
    if not program:
        return None

    return {
        "id": program.id,
        "name": program.name,
        "code": program.code,
        "description": getattr(program, "description", None),
    }


def _serialize_registration_event(registration) -> dict[str, Any]:
    return {
        "id": registration.id,
        "patient_id": registration.patient_id,
        "registered_by_id": registration.registered_by_id,
        "registration_date": registration.registration_date,
        "notes": registration.notes,
        "registered_by": _serialize_registered_by(getattr(registration, "registered_by", None)),
        "created_at": getattr(registration, "date_created", None),
        "updated_at": getattr(registration, "date_updated", None),
    }


def _serialize_identifier(identifier) -> dict[str, Any]:
    return {
        "id": identifier.id,
        "patient_id": identifier.patient_id,
        "identifier_type": identifier.identifier_type,
        "identifier_value": identifier.identifier_value,
        "issuing_authority": identifier.issuing_authority,
        "is_primary": identifier.is_primary,
        "is_active": identifier.is_active,
        "note": identifier.note,
        "created_at": getattr(identifier, "date_created", None),
        "updated_at": getattr(identifier, "date_updated", None),
    }


def _serialize_attachment(attachment) -> dict[str, Any]:
    return {
        "id": attachment.id,
        "patient_id": attachment.patient_id,
        "uploaded_by_id": attachment.uploaded_by_id,
        "attachment_type": attachment.attachment_type,
        "title": attachment.title,
        "file_name": attachment.file_name,
        "file_key": attachment.file_key,
        "file_url": attachment.file_url,
        "content_type": attachment.content_type,
        "checksum": attachment.checksum,
        "is_primary": attachment.is_primary,
        "note": attachment.note,
        "created_at": getattr(attachment, "date_created", None),
        "updated_at": getattr(attachment, "date_updated", None),
    }


def _serialize_consent(consent) -> dict[str, Any]:
    return {
        "id": consent.id,
        "patient_id": consent.patient_id,
        "recorded_by_id": consent.recorded_by_id,
        "consent_type": consent.consent_type,
        "consent_status": consent.consent_status,
        "consent_date": consent.consent_date,
        "expiry_date": consent.expiry_date,
        "document_file_name": consent.document_file_name,
        "document_file_key": consent.document_file_key,
        "document_file_url": consent.document_file_url,
        "note": consent.note,
        "created_at": getattr(consent, "date_created", None),
        "updated_at": getattr(consent, "date_updated", None),
    }


def _serialize_scanned_form(form) -> dict[str, Any]:
    return {
        "id": form.id,
        "patient_id": form.patient_id,
        "uploaded_by_id": form.uploaded_by_id,
        "form_type": form.form_type,
        "file_name": form.file_name,
        "file_key": form.file_key,
        "file_url": form.file_url,
        "content_type": form.content_type,
        "checksum": form.checksum,
        "note": form.note,
        "created_at": getattr(form, "date_created", None),
        "updated_at": getattr(form, "date_updated", None),
    }


def _serialize_demographic_audit(audit) -> dict[str, Any]:
    return {
        "id": audit.id,
        "patient_id": audit.patient_id,
        "changed_by_id": audit.changed_by_id,
        "change_source": audit.change_source,
        "changed_at": audit.changed_at,
        "before_snapshot": audit.before_snapshot,
        "after_snapshot": audit.after_snapshot,
        "changed_fields": audit.changed_fields,
        "note": audit.note,
        "created_at": getattr(audit, "date_created", None),
        "updated_at": getattr(audit, "date_updated", None),
    }


def _serialize_insurance_record(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "patient_id": record.patient_id,
        "insurance_provider_id": getattr(record, "insurance_provider_id", None),
        "policy_number": getattr(record, "policy_number", None),
        "member_id": getattr(record, "member_id", None),
        "plan_name": getattr(record, "plan_name", None),
        "coverage_details": getattr(record, "coverage_details", None),
        "status": _safe_enum(getattr(record, "status", None)),
        "valid_from": getattr(record, "valid_from", None),
        "valid_to": getattr(record, "valid_to", None),
        "note": getattr(record, "note", None),
        "insurance_provider": _serialize_insurance_provider(getattr(record, "insurance_provider", None)),
        "created_at": getattr(record, "date_created", None),
        "updated_at": getattr(record, "date_updated", None),
    }


def _serialize_loyalty_membership(membership) -> dict[str, Any]:
    return {
        "id": membership.id,
        "patient_id": membership.patient_id,
        "loyalty_program_id": membership.loyalty_program_id,
        "membership_no": membership.membership_no,
        "points_balance": membership.points_balance,
        "joined_date": membership.joined_date,
        "loyalty_program": _serialize_loyalty_program(getattr(membership, "loyalty_program", None)),
        "created_at": getattr(membership, "date_created", None),
        "updated_at": getattr(membership, "date_updated", None),
    }


def _serialize_patient(patient) -> dict[str, Any]:
    registrations = [
        _serialize_registration_event(item)
        for item in (getattr(patient, "registrations", []) or [])
        if not getattr(item, "is_deleted", False)
    ]

    identifiers = [
        _serialize_identifier(item)
        for item in (getattr(patient, "identifiers", []) or [])
        if not getattr(item, "is_deleted", False)
    ]

    photo_payload = None
    if getattr(patient, "photo_file_name", None) or getattr(patient, "photo_file_url", None):
        photo_payload = {
            "file_name": getattr(patient, "photo_file_name", None),
            "file_key": getattr(patient, "photo_file_key", None),
            "file_url": getattr(patient, "photo_file_url", None),
        }

    return {
        "id": patient.id,
        "global_patient_id": getattr(patient, "global_patient_id", ""),
        "hospital_number": patient.hospital_number,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "middle_name": patient.middle_name,
        "date_of_birth": patient.date_of_birth,
        "gender": _safe_enum(patient.gender),
        "marital_status": _safe_enum(patient.marital_status),
        "phone_number": patient.phone_number,
        "alternate_phone_number": patient.alternate_phone_number,
        "email": patient.email,
        "address": patient.address,
        "city": patient.city,
        "state": patient.state,
        "country": patient.country,
        "blood_group": _safe_enum(patient.blood_group),
        "genotype": _safe_enum(patient.genotype),
        "allergies": patient.allergies,
        "emergency_contact_name": patient.emergency_contact_name,
        "emergency_contact_phone": patient.emergency_contact_phone,
        "emergency_contact_relationship": patient.emergency_contact_relationship,
        "next_of_kin_name": getattr(patient, "next_of_kin_name", None),
        "next_of_kin_phone": getattr(patient, "next_of_kin_phone", None),
        "next_of_kin_relationship": getattr(patient, "next_of_kin_relationship", None),
        "next_of_kin_address": getattr(patient, "next_of_kin_address", None),
        "patient_type": _safe_enum(patient.patient_type),
        "preferred_payer_id": getattr(patient, "preferred_payer_id", None),
        "payer_type": getattr(patient, "payer_type", None),
        "preferred_payer": _serialize_payer(getattr(patient, "preferred_payer", None)),
        "national_identifier": getattr(patient, "national_identifier", None),
        "national_identifier_type": getattr(patient, "national_identifier_type", None),
        "identification_details": getattr(patient, "identification_details", None),
        "photo": photo_payload,
        "registrations": registrations,
        "identifiers": identifiers,
        "created_at": getattr(patient, "date_created", None),
        "updated_at": getattr(patient, "date_updated", None),
    }


def _serialize_patient_extended(patient) -> dict[str, Any]:
    payload = _serialize_patient(patient)

    payload["insurance_records"] = [
        _serialize_insurance_record(item)
        for item in (getattr(patient, "insurance_records", []) or [])
        if not getattr(item, "is_deleted", False)
    ]
    payload["loyalty_memberships"] = [
        _serialize_loyalty_membership(item)
        for item in (getattr(patient, "loyalty_memberships", []) or [])
        if not getattr(item, "is_deleted", False)
    ]
    payload["document_attachments"] = [
        _serialize_attachment(item)
        for item in (getattr(patient, "attachments", []) or [])
        if not getattr(item, "is_deleted", False)
    ]
    payload["consent_records"] = [
        _serialize_consent(item)
        for item in (getattr(patient, "consent_records", []) or [])
        if not getattr(item, "is_deleted", False)
    ]
    payload["scanned_forms"] = [
        _serialize_scanned_form(item)
        for item in (getattr(patient, "scanned_forms", []) or [])
        if not getattr(item, "is_deleted", False)
    ]
    payload["demographic_audits"] = [
        _serialize_demographic_audit(item)
        for item in (getattr(patient, "demographic_audits", []) or [])
        if not getattr(item, "is_deleted", False)
    ]

    return payload


def _serialize_patient_list_item(patient) -> dict[str, Any]:
    return {
        "id": patient.id,
        "hospital_number": patient.hospital_number,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "middle_name": patient.middle_name,
        "date_of_birth": patient.date_of_birth,
        "gender": _safe_enum(patient.gender),
        "phone_number": patient.phone_number,
        "email": patient.email,
        "city": patient.city,
        "state": patient.state,
        "patient_type": _safe_enum(patient.patient_type),
        "payer_type": getattr(patient, "payer_type", None),
        "national_identifier": getattr(patient, "national_identifier", None),
    }


# ============================================================
# ROUTES
# ============================================================

@router.post(
    "/",
    response_model=PatientRegistrationCreateResultSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register new patient",
)
def create_patient(
    payload: PatientCreateSchema,
    current_user: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
    force_create_if_possible_duplicate: bool = Query(
        False,
        description="Allow create even when duplicate candidates are found.",
    ),
):
    """
    Register a first-time patient.

    This creates:
    - patient master record
    - registration event
    - optional insurance enrollment
    - optional loyalty enrollment
    """
    patient = service.create_patient(
        payload,
        registered_by_id=current_user.id,
        force_create_if_possible_duplicate=force_create_if_possible_duplicate,
    )

    latest_registration = (getattr(patient, "registrations", []) or [None])[0]
    latest_insurance = (getattr(patient, "insurance_records", []) or [None])[0]
    latest_loyalty = (getattr(patient, "loyalty_memberships", []) or [None])[0]

    return {
        "success": True,
        "patient_id": patient.id,
        "hospital_number": patient.hospital_number,
        "registration_id": latest_registration.id if latest_registration else 0,
        "insurance_record_id": latest_insurance.id if latest_insurance else None,
        "loyalty_membership_id": latest_loyalty.id if latest_loyalty else None,
        "message": "Patient registered successfully.",
    }


@router.post(
    "/duplicate-check",
    response_model=PatientDuplicateCheckResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Check for possible duplicate patients",
)
def check_for_possible_duplicates(
    payload: PatientDuplicateCheckSchema,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Search existing records to avoid duplicates before registration.
    """
    candidates = service.check_for_possible_duplicates(payload)

    serialized_candidates = []
    for candidate in candidates:
        matched_on: list[str] = []

        if payload.first_name and payload.last_name:
            if (
                candidate.first_name.lower() == payload.first_name.lower()
                and candidate.last_name.lower() == payload.last_name.lower()
            ):
                matched_on.extend(["first_name", "last_name"])

        if payload.middle_name and candidate.middle_name:
            if candidate.middle_name.lower() == payload.middle_name.lower():
                matched_on.append("middle_name")

        if payload.phone_number:
            if candidate.phone_number == payload.phone_number or candidate.alternate_phone_number == payload.phone_number:
                matched_on.append("phone_number")

        if payload.date_of_birth and candidate.date_of_birth == payload.date_of_birth:
            matched_on.append("date_of_birth")

        if payload.national_identifier and getattr(candidate, "national_identifier", None) == payload.national_identifier:
            matched_on.append("national_identifier")

        score = min(100.0, float(len(set(matched_on)) * 20))

        serialized_candidates.append(
            {
                "patient": {
                    "id": candidate.id,
                    "hospital_number": candidate.hospital_number,
                    "first_name": candidate.first_name,
                    "last_name": candidate.last_name,
                    "middle_name": candidate.middle_name,
                    "date_of_birth": candidate.date_of_birth,
                    "gender": _safe_enum(candidate.gender),
                    "phone_number": candidate.phone_number,
                    "patient_type": _safe_enum(candidate.patient_type),
                },
                "match_score": score,
                "matched_on": sorted(set(matched_on)),
            }
        )

    return {
        "success": True,
        "possible_duplicate_found": len(serialized_candidates) > 0,
        "candidates": serialized_candidates,
        "message": (
            "Possible duplicate patient record(s) found."
            if serialized_candidates
            else "No possible duplicate patient records found."
        ),
    }


@router.post(
    "/duplicate-review/resolve",
    response_model=PatientDuplicateReviewResultSchema,
    status_code=status.HTTP_200_OK,
    summary="Resolve duplicate review",
)
def resolve_duplicate_review(
    payload: PatientDuplicateReviewDecisionSchema,
    current_user: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
    create_payload: Optional[PatientCreateSchema] = None,
):
    """
    Registrar resolves duplicate review by either:
    - linking to an existing patient
    - continuing with new patient creation
    """
    patient = service.resolve_duplicate_review(
        payload,
        create_payload=create_payload,
        registered_by_id=current_user.id,
    )

    return {
        "success": True,
        "decision": payload.decision,
        "patient_id": patient.id,
        "message": (
            "Linked to existing patient successfully."
            if payload.decision == "LINK_EXISTING"
            else "New patient created successfully after duplicate override."
        ),
    }


@router.post(
    "/{patient_id}/link-existing-result",
    response_model=PatientLinkExistingRegistrationResultSchema,
    status_code=status.HTTP_200_OK,
    summary="Return linked existing patient result",
)
def get_link_existing_result(
    patient_id: int,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Convenience endpoint to fetch the linked existing patient after duplicate review.
    """
    patient = service.get_detailed_patient(patient_id)
    return {
        "success": True,
        "patient_id": patient.id,
        "hospital_number": patient.hospital_number,
        "message": "Existing patient linked successfully.",
    }


@router.post(
    "/{patient_id}/attach-insurance-later",
    response_model=PatientInsuranceReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Attach patient insurance later",
)
def attach_patient_insurance_later(
    patient_id: int,
    payload: PatientAttachInsuranceLaterSchema,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Attach insurance after the patient has already been saved.
    """
    insurance = service.attach_patient_insurance_later(patient_id, payload)
    return _serialize_insurance_record(insurance)


@router.get(
    "/",
    response_model=PatientListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List patients",
)
def list_patients(
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=100, description="Pagination size."),
):
    """
    Return a paginated list of patients in the MPI.
    """
    items, total = service.list_patients(skip=skip, limit=limit)
    return paginate_response(
        items=[_serialize_patient_list_item(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Patients fetched successfully.",
    )


@router.get(
    "/search",
    response_model=PatientListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Search patients in the MPI",
)
def search_patients(
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
    hospital_number: Optional[str] = Query(None),
    full_name: Optional[str] = Query(None),
    phone_number: Optional[str] = Query(None),
    date_of_birth: Optional[date] = Query(None),
    email: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    patient_type: Optional[str] = Query(None),
    payer_type: Optional[str] = Query(None),
    national_identifier: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Search the Master Patient Index.
    """
    items, total = service.search_patients(
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

    return paginate_response(
        items=[_serialize_patient_list_item(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Patients fetched successfully.",
    )


@router.get(
    "/by-hospital-number/{hospital_number}",
    response_model=PatientReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get patient by MRN",
)
def get_patient_by_hospital_number(
    hospital_number: str,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Return patient by hospital number.
    """
    patient = service.get_patient_by_hospital_number(hospital_number)
    return _serialize_patient(patient)


@router.get(
    "/{patient_id}",
    response_model=PatientReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get patient details",
)
def get_patient(
    patient_id: int,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Return the basic details of a patient.
    """
    patient = service.get_patient(patient_id)
    return _serialize_patient(patient)


@router.get(
    "/{patient_id}/detailed",
    response_model=PatientExtendedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get detailed patient record",
)
def get_detailed_patient(
    patient_id: int,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Return detailed patient record including insurance, loyalty, attachments,
    scanned forms, consent records, and audit history.
    """
    patient = service.get_detailed_patient(patient_id)
    return _serialize_patient_extended(patient)


@router.put(
    "/{patient_id}",
    response_model=PatientExtendedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update patient demographics",
)
def update_patient(
    patient_id: int,
    payload: PatientUpdateSchema,
    current_user: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Update patient demographics and administrative details.
    """
    patient = service.update_patient(
        patient_id,
        payload,
        changed_by_id=current_user.id,
        change_source="MPI_UPDATE",
    )
    return _serialize_patient_extended(patient)


@router.post(
    "/{patient_id}/identifiers",
    response_model=PatientIdentifierReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add patient identifier",
)
def add_patient_identifier(
    patient_id: int,
    payload: PatientIdentifierCreateSchema,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Add a patient identifier such as previous record ID or external MRN.
    """
    identifier = service.add_patient_identifier(patient_id, payload)
    return _serialize_identifier(identifier)


@router.post(
    "/{patient_id}/photo",
    status_code=status.HTTP_201_CREATED,
    summary="Upload patient photo",
)
async def upload_patient_photo(
    patient_id: int,
    current_user: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
    file: UploadFile = File(...),
    note: Optional[str] = Form(None),
):
    """
    Upload patient photo to AWS S3 and persist metadata.
    """
    file_bytes = await file.read()
    return service.upload_patient_photo(
        patient_id,
        file_bytes=file_bytes,
        file_name=file.filename or "patient_photo",
        content_type=file.content_type,
        uploaded_by_id=current_user.id,
        note=note,
    )


@router.post(
    "/{patient_id}/attachments",
    response_model=PatientAttachmentReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Upload patient attachment",
)
async def create_patient_attachment(
    patient_id: int,
    current_user: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
    attachment_type: str = Form(...),
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    is_primary: bool = Form(False),
):
    """
    Upload patient attachment to AWS S3 and persist metadata.
    """
    payload = PatientAttachmentCreateSchema(
        attachment_type=attachment_type,
        title=title,
        file_name=file.filename or "patient_attachment",
        content_type=file.content_type,
        note=note,
        is_primary=is_primary,
    )

    file_bytes = await file.read()
    attachment = service.create_patient_attachment(
        patient_id,
        payload,
        file_bytes=file_bytes,
        uploaded_by_id=current_user.id,
    )
    return _serialize_attachment(attachment)


@router.post(
    "/{patient_id}/scanned-forms",
    response_model=PatientScannedFormReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Upload scanned patient form",
)
async def create_patient_scanned_form(
    patient_id: int,
    current_user: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
    form_type: str = Form(...),
    file: UploadFile = File(...),
    note: Optional[str] = Form(None),
):
    """
    Upload scanned patient form to AWS S3 and persist metadata.
    """
    payload = PatientScannedFormCreateSchema(
        form_type=form_type,
        file_name=file.filename or "patient_scanned_form",
        content_type=file.content_type,
        note=note,
    )

    file_bytes = await file.read()
    form = service.create_patient_scanned_form(
        patient_id,
        payload,
        file_bytes=file_bytes,
        uploaded_by_id=current_user.id,
    )
    return _serialize_scanned_form(form)


@router.post(
    "/{patient_id}/consents",
    response_model=PatientConsentReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create patient consent record",
)
def create_patient_consent_record(
    patient_id: int,
    payload: PatientConsentCreateSchema,
    current_user: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Create patient consent record.
    """
    consent = service.create_patient_consent_record(
        patient_id,
        payload,
        recorded_by_id=current_user.id,
    )
    return _serialize_consent(consent)


@router.delete(
    "/{patient_id}",
    response_model=PatientActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Delete patient",
)
def delete_patient(
    patient_id: int,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Soft-delete patient record when safe.
    """
    patient = service.delete_patient(patient_id)
    return {
        "success": True,
        "message": f"Patient '{patient.hospital_number}' deleted successfully.",
    }