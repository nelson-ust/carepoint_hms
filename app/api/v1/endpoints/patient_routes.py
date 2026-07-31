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
from app.core.dependencies import AdminUser, AnyAuthenticatedUser, require_plan_feature

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
    PatientAllergyCreateSchema,
    PatientAllergyReadSchema,
    PatientAllergyUpdateSchema,
)
from app.services.patient_service import PatientService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/patients",
    tags=["Patient Registration & MPI"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)



def get_patient_service(
    db: Annotated[Session, Depends(get_db)],
) -> PatientService:
    """
    Dependency provider for the patient service.
    """
    return PatientService(db)





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

    # Note: The match score calculation is kept here as it's logic specific to the duplicate check view.
    # However, we return the ORM patient objects directly within the response structure.
    results = []
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

        results.append(
            {
                "patient": candidate,
                "match_score": score,
                "matched_on": sorted(set(matched_on)),
            }
        )

    return {
        "success": True,
        "possible_duplicate_found": len(results) > 0,
        "candidates": results,
        "message": (
            "Possible duplicate patient record(s) found."
            if results
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
    "/attach-insurance-later",
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
    return service.attach_patient_insurance_later(patient_id, payload)


@router.get(
    "/",
    response_model=PatientListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List patients",
)
def list_patients(
    _: AnyAuthenticatedUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=1000, description="Pagination size."),
):
    """
    Return a paginated list of patients in the MPI.
    """
    items, total = service.list_patients(skip=skip, limit=limit)
    return paginate_response(
        items=items,
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
    _: AnyAuthenticatedUser,
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
    search: Optional[str] = Query(
        None,
        description="Unified quick-search across patient name, hospital number, phone, or id.",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
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
        search=search,
        skip=skip,
        limit=limit,
    )

    return paginate_response(
        items=items,
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
    _: AnyAuthenticatedUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Return patient by hospital number.
    """
    return service.get_patient_by_hospital_number(hospital_number)


@router.get(
    "/{patient_id}",
    response_model=PatientReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get patient details",
)
def get_patient(
    patient_id: int,
    _: AnyAuthenticatedUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Return the basic details of a patient.
    """
    return service.get_patient(patient_id)


@router.get(
    "/{patient_id}/detailed",
    response_model=PatientExtendedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get detailed patient record",
)
def get_detailed_patient(
    patient_id: int,
    _: AnyAuthenticatedUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Return detailed patient record including insurance, loyalty, attachments,
    scanned forms, consent records, and audit history.
    """
    return service.get_detailed_patient(patient_id)


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
    return service.update_patient(
        patient_id,
        payload,
        changed_by_id=current_user.id,
        change_source="MPI_UPDATE",
    )


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
    return service.add_patient_identifier(patient_id, payload)


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
    return service.create_patient_attachment(
        patient_id,
        payload,
        file_bytes=file_bytes,
        uploaded_by_id=current_user.id,
    )


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
    return service.create_patient_scanned_form(
        patient_id,
        payload,
        file_bytes=file_bytes,
        uploaded_by_id=current_user.id,
    )


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
    return service.create_patient_consent_record(
        patient_id,
        payload,
        recorded_by_id=current_user.id,
    )


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


# ============================================================
# ALLERGY ROUTES
# ============================================================

@router.post(
    "/{patient_id}/allergies",
    response_model=PatientAllergyReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add patient allergy",
)
def add_patient_allergy(
    patient_id: int,
    payload: PatientAllergyCreateSchema,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Add a structured allergy record for a patient.
    """
    return service.add_patient_allergy(patient_id, payload)


@router.get(
    "/{patient_id}/allergies",
    response_model=list[PatientAllergyReadSchema],
    status_code=status.HTTP_200_OK,
    summary="List patient allergies",
)
def list_patient_allergies(
    patient_id: int,
    _: AnyAuthenticatedUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Return all structured allergies for a patient.
    """
    return service.list_patient_allergies(patient_id)


@router.put(
    "/allergies/{allergy_id}",
    response_model=PatientAllergyReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update patient allergy",
)
def update_patient_allergy(
    allergy_id: int,
    payload: PatientAllergyUpdateSchema,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Update an existing allergy record.
    """
    return service.update_patient_allergy(allergy_id, payload)


@router.delete(
    "/allergies/{allergy_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete patient allergy",
)
def delete_patient_allergy(
    allergy_id: int,
    _: AdminUser,
    service: Annotated[PatientService, Depends(get_patient_service)],
):
    """
    Soft-delete an allergy record.
    """
    service.delete_patient_allergy(allergy_id)
    return {"success": True, "message": "Allergy record deleted successfully."}