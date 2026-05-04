# app/api/v1/endpoints/admission_routes.py
from __future__ import annotations

"""
FastAPI routes for the inpatient admission lifecycle.

Endpoints
---------
- ``GET    /admissions``                          list with filters
- ``GET    /admissions/wards/{ward_id}/active``   ward-board view
- ``GET    /admissions/{admission_id}``           single admission
- ``POST   /admissions``                          admit a patient
- ``POST   /admissions/{admission_id}/transfer``  bed transfer
- ``POST   /admissions/{admission_id}/status``    cancel / decease
- ``POST   /admissions/{admission_id}/bed-days``  capture bed-day charges

Permission codes used
---------------------
- ``ADMISSION_CREATE``    — admit a patient
- ``ADMISSION_DISCHARGE`` — bed transfer / status change (we re-use the
  existing inpatient permission rather than introducing a new one)
- ``BED_MANAGE``          — bed transfer
- ``BILLING_CREATE``      — bed-day charge capture
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.admission_schemas import (
    AdmissionActionResponseSchema,
    AdmissionBedDayCaptureResponseSchema,
    AdmissionBedDayCaptureSchema,
    AdmissionCreateSchema,
    AdmissionFromVisitConvertSchema,
    AdmissionListResponseSchema,
    AdmissionReadSchema,
    AdmissionStatusUpdateSchema,
    AdmissionTransferBedSchema,
)
from app.services.admission_service import AdmissionService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/admissions",
    tags=["Admissions"],
    dependencies=[Depends(require_plan_feature("inpatient"))]
)


def get_admission_service(db: Annotated[Session, Depends(get_db)]) -> AdmissionService:
    """FastAPI dependency that constructs an AdmissionService per-request."""
    return AdmissionService(db)


def _serialize(a) -> dict:
    """
    Convert an Admission ORM row to the dict the response schemas expect.

    Kept here (not in the schema module) because we want a single, explicit
    place where ORM ↔ JSON shape decisions are made.
    """
    return {
        "id": a.id,
        "admission_no": a.admission_no,
        "patient_id": a.patient_id,
        "visit_id": a.visit_id,
        "ward_id": a.ward_id,
        "bed_id": a.bed_id,
        "admitted_by_staff_id": a.admitted_by_staff_id,
        "admission_status": str(a.admission_status),
        "admission_reason": a.admission_reason,
        "admitted_at": a.admitted_at,
        "expected_discharge_at": a.expected_discharge_at,
        "actual_discharge_at": a.actual_discharge_at,
        "created_at": getattr(a, "created_at", None),
        "updated_at": getattr(a, "updated_at", None),
    }


# ============================================================
# READ
# ============================================================


@router.get(
    "/",
    response_model=AdmissionListResponseSchema,
    summary="List admissions",
)
def list_admissions(
    _: Annotated[User, Depends(require_permission("BILLING_READ", "ADMISSION_CREATE", "VISIT_READ"))],
    service: Annotated[AdmissionService, Depends(get_admission_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    patient_id: Optional[int] = Query(None),
    ward_id: Optional[int] = Query(None),
    facility_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="PENDING, ADMITTED, TRANSFERRED, DISCHARGED, CANCELLED, DECEASED.",
    ),
):
    """Paginated admission list with the most common filters."""
    items, total = service.list_admissions(
        skip=skip, limit=limit,
        patient_id=patient_id, ward_id=ward_id,
        status=status_filter, facility_id=facility_id,
    )
    return paginate_response(
        items=[_serialize(a) for a in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Admissions fetched successfully.",
    )


@router.get(
    "/wards/{ward_id}/active",
    response_model=AdmissionListResponseSchema,
    summary="Active admissions in a ward (ward-board view)",
)
def list_active_for_ward(
    ward_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ", "ADMISSION_CREATE", "VISIT_READ"))],
    service: Annotated[AdmissionService, Depends(get_admission_service)],
):
    """Return all currently-active admissions sitting in beds of a given ward."""
    items = service.list_active_for_ward(ward_id)
    # The ward-board UI typically renders all active admissions at once, so
    # we don't paginate. The paginate_response wrapper still gives the
    # caller a count + meta block for consistency.
    return paginate_response(
        items=[_serialize(a) for a in items],
        total=len(items),
        skip=0,
        limit=len(items) or 1,
        message="Active admissions fetched successfully.",
    )


@router.get(
    "/{admission_id}",
    response_model=AdmissionReadSchema,
    summary="Get an admission",
)
def get_admission(
    admission_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ", "ADMISSION_CREATE", "VISIT_READ"))],
    service: Annotated[AdmissionService, Depends(get_admission_service)],
):
    """Return a single admission by id."""
    return _serialize(service.get(admission_id))


# ============================================================
# WRITE
# ============================================================


@router.post(
    "/",
    response_model=AdmissionActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Admit a patient",
)
def admit_patient(
    payload: AdmissionCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[AdmissionService, Depends(get_admission_service)],
    _: Annotated[User, Depends(require_permission("ADMISSION_CREATE"))],
):
    """
    Admit a patient: assign ward + bed, mark bed OCCUPIED, capture the first
    bed-day charge into the visit's billing, and emit a security audit row.
    """
    admission = service.admit(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Patient admitted.",
        "admission": _serialize(admission),
    }


@router.post(
    "/from-visit",
    response_model=AdmissionActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Convert an ER / OPD visit into an inpatient admission",
)
def convert_visit_to_admission(
    payload: AdmissionFromVisitConvertSchema,
    actor: CurrentActiveUser,
    service: Annotated[AdmissionService, Depends(get_admission_service)],
    _: Annotated[User, Depends(require_permission("ADMISSION_CREATE"))],
):
    """
    Single-call hand-off from emergency / outpatient to inpatient on the
    same Visit. Reuses the visit's billing, books a bed, captures the
    first bed-day charge, and (optionally) routes the visit to the
    inpatient SDP.
    """
    admission = service.convert_visit_to_admission(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Visit converted to inpatient admission.",
        "admission": _serialize(admission),
    }


@router.post(
    "/{admission_id}/transfer",
    response_model=AdmissionActionResponseSchema,
    summary="Transfer the patient to a new bed",
)
def transfer_bed(
    admission_id: int,
    payload: AdmissionTransferBedSchema,
    actor: CurrentActiveUser,
    service: Annotated[AdmissionService, Depends(get_admission_service)],
    _: Annotated[User, Depends(require_permission("BED_MANAGE", "ADMISSION_CREATE"))],
):
    """Move an admitted patient to a new bed (potentially in another ward)."""
    admission = service.transfer_bed(admission_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Patient transferred to new bed.",
        "admission": _serialize(admission),
    }


@router.post(
    "/{admission_id}/status",
    response_model=AdmissionActionResponseSchema,
    summary="Cancel or mark deceased",
)
def update_status(
    admission_id: int,
    payload: AdmissionStatusUpdateSchema,
    actor: CurrentActiveUser,
    service: Annotated[AdmissionService, Depends(get_admission_service)],
    _: Annotated[User, Depends(require_permission("ADMISSION_DISCHARGE", "ADMISSION_CREATE"))],
):
    """Move an admission to CANCELLED or DECEASED. Frees the bed in both cases."""
    admission = service.update_status(admission_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": f"Admission status updated to {payload.new_status}.",
        "admission": _serialize(admission),
    }


@router.post(
    "/{admission_id}/bed-days",
    response_model=AdmissionBedDayCaptureResponseSchema,
    summary="Capture bed-day charges up to a date",
)
def capture_bed_day_charges(
    admission_id: int,
    payload: AdmissionBedDayCaptureSchema,
    actor: CurrentActiveUser,
    service: Annotated[AdmissionService, Depends(get_admission_service)],
    _: Annotated[User, Depends(require_permission("BILLING_CREATE", "ADMISSION_CREATE"))],
):
    """
    Capture all bed-day charges for an admission up to ``through_date``.

    Idempotent. Used by the nightly rollover and by cashier "settle now" flows.
    """
    summary = service.capture_bed_day_charges(admission_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Bed-day charges captured successfully.",
        "admission_id": summary["admission_id"],
        "charges_captured": summary["charges_captured"],
        "total_amount_captured": summary["total_amount_captured"],
        "captured_through": summary["captured_through"],
    }
