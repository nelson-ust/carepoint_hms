from __future__ import annotations

"""
app.api.v1.endpoints.ward_routes

FastAPI routes for ward management.

Purpose
-------
This module exposes API endpoints for:

- creating wards
- listing wards
- retrieving ward details
- retrieving detailed ward operational summaries
- updating wards
- soft-deleting wards

Security
--------
These endpoints are intended for administrative access and are protected
with the admin dependency.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser, require_plan_feature
from app.schemas.ward_schemas import (
    WardActionResponseSchema,
    WardCreateSchema,
    WardDetailedReadSchema,
    WardListResponseSchema,
    WardReadSchema,
    WardUpdateSchema,
)
from app.services.ward_service import WardService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/wards",
    tags=["Ward Management"],
    dependencies=[Depends(require_plan_feature("inpatient"))]
)


def get_ward_service(
    db: Annotated[Session, Depends(get_db)],
) -> WardService:
    """
    Dependency provider for the ward service.

    Args:
        db: Request-scoped SQLAlchemy session.

    Returns:
        WardService: Service instance.
    """
    return WardService(db)


# ============================================================
# ROUTES
# ============================================================

@router.post(
    "/",
    response_model=WardReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create ward",
)
def create_ward(
    payload: WardCreateSchema,
    _: AdminUser,
    service: Annotated[WardService, Depends(get_ward_service)],
):
    """
    Create a new ward.

    Business rules enforced by the service layer:
    - ward name must be unique
    - ward code must be unique
    """
    return service.create_ward(payload)


@router.get(
    "/",
    response_model=WardListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List wards",
)
def list_wards(
    _: CurrentActiveUser,
    service: Annotated[WardService, Depends(get_ward_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=1000, description="Pagination size."),
):
    """
    Return a paginated list of wards with operational summary fields.

    Returned list items include:
    - total beds
    - available beds
    - occupied beds
    - active admissions
    """
    items, total = service.list_wards(skip=skip, limit=limit)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Wards fetched successfully.",
    )


@router.get(
    "/{ward_id}",
    response_model=WardReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get ward details",
)
def get_ward(
    ward_id: int,
    _: CurrentActiveUser,
    service: Annotated[WardService, Depends(get_ward_service)],
):
    """
    Return the basic details of a single ward.
    """
    return service.get_ward(ward_id)


@router.get(
    "/{ward_id}/summary",
    response_model=WardDetailedReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get detailed ward summary",
)
def get_detailed_ward(
    ward_id: int,
    _: CurrentActiveUser,
    service: Annotated[WardService, Depends(get_ward_service)],
):
    """
    Return a detailed operational summary for a ward.

    Summary fields include:
    - total beds
    - available beds
    - occupied beds
    - total admissions
    - active admissions
    """
    return service.get_detailed_ward(ward_id)


@router.put(
    "/{ward_id}",
    response_model=WardReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update ward",
)
def update_ward(
    ward_id: int,
    payload: WardUpdateSchema,
    _: AdminUser,
    service: Annotated[WardService, Depends(get_ward_service)],
):
    """
    Update an existing ward.

    Business rules enforced by the service layer:
    - updated ward name must remain unique
    - updated ward code must remain unique
    """
    return service.update_ward(ward_id, payload)


@router.delete(
    "/{ward_id}",
    response_model=WardActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Delete ward",
)
def delete_ward(
    ward_id: int,
    _: AdminUser,
    service: Annotated[WardService, Depends(get_ward_service)],
):
    """
    Soft-delete a ward.

    Delete is blocked when the ward still has:
    - linked bed records
    - linked admission records
    """
    ward = service.delete_ward(ward_id)
    return {
        "success": True,
        "message": f"Ward '{ward.name}' deleted successfully.",
    }