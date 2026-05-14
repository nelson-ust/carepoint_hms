from __future__ import annotations

"""
app.api.v1.endpoints.bed_routes

FastAPI routes for bed management.

Purpose
-------
This module exposes API endpoints for:

- creating beds
- listing beds
- retrieving bed details
- retrieving detailed bed operational summaries
- updating beds
- soft-deleting beds

Security
--------
These endpoints are intended for administrative access and are protected
with the admin dependency.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, require_plan_feature
from app.schemas.bed_schemas import (
    BedActionResponseSchema,
    BedCreateSchema,
    BedDetailedReadSchema,
    BedListResponseSchema,
    BedReadSchema,
    BedUpdateSchema,
)
from app.services.bed_service import BedService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/beds",
    tags=["Bed Management"],
    dependencies=[Depends(require_plan_feature("inpatient"))]
)


def get_bed_service(
    db: Annotated[Session, Depends(get_db)],
) -> BedService:
    """
    Dependency provider for the bed service.

    Args:
        db: Request-scoped SQLAlchemy session.

    Returns:
        BedService: Service instance.
    """
    return BedService(db)


# ============================================================
# ROUTES
# ============================================================

@router.post(
    "/",
    response_model=BedReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create bed",
)
def create_bed(
    payload: BedCreateSchema,
    _: AdminUser,
    service: Annotated[BedService, Depends(get_bed_service)],
):
    """
    Create a new bed.

    Business rules enforced by the service layer:
    - linked ward must exist
    - bed number must be unique within the ward
    """
    return service.create_bed(payload)


@router.get(
    "/",
    response_model=BedListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List beds",
)
def list_beds(
    _: AdminUser,
    service: Annotated[BedService, Depends(get_bed_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=100, description="Pagination size."),
):
    """
    Return a paginated list of beds with ward context and admission summary fields.

    Returned list items include:
    - ward name
    - ward code
    - admission count
    - active admission flag
    """
    items, total = service.list_beds(skip=skip, limit=limit)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Beds fetched successfully.",
    )


@router.get(
    "/{bed_id}",
    response_model=BedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get bed details",
)
def get_bed(
    bed_id: int,
    _: AdminUser,
    service: Annotated[BedService, Depends(get_bed_service)],
):
    """
    Return the basic details of a single bed.
    """
    return service.get_bed(bed_id)


@router.get(
    "/{bed_id}/summary",
    response_model=BedDetailedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get detailed bed summary",
)
def get_detailed_bed(
    bed_id: int,
    _: AdminUser,
    service: Annotated[BedService, Depends(get_bed_service)],
):
    """
    Return a detailed operational summary for a bed.

    Summary fields include:
    - linked ward
    - admission count
    - active admission flag
    """
    return service.get_detailed_bed(bed_id)


@router.put(
    "/{bed_id}",
    response_model=BedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update bed",
)
def update_bed(
    bed_id: int,
    payload: BedUpdateSchema,
    _: AdminUser,
    service: Annotated[BedService, Depends(get_bed_service)],
):
    """
    Update an existing bed.

    Business rules enforced by the service layer:
    - new ward must exist if ward_id changes
    - final (ward_id, bed_no) combination must remain unique
    - moving a bed across wards is blocked when admissions already exist
    """
    return service.update_bed(bed_id, payload)


@router.delete(
    "/{bed_id}",
    response_model=BedActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Delete bed",
)
def delete_bed(
    bed_id: int,
    _: AdminUser,
    service: Annotated[BedService, Depends(get_bed_service)],
):
    """
    Soft-delete a bed.

    Delete is blocked when the bed still has an active admission.
    """
    bed = service.delete_bed(bed_id)
    return {
        "success": True,
        "message": f"Bed '{bed.bed_no}' deleted successfully.",
    }