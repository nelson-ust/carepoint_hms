from __future__ import annotations

"""
app.api.v1.endpoints.service_delivery_routes

FastAPI routes for service delivery point configuration and retrieval.

Purpose
-------
This module exposes API endpoints for:

- creating service delivery points
- retrieving service delivery points
- listing and filtering service delivery points
- listing active service delivery points
- updating service delivery points
- activating/deactivating service delivery points
- soft-deleting service delivery points

Security
--------
These endpoints are intended for authorized administrative/configuration users
and are protected with the admin dependency.
"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.schemas.service_delivery_point_schemas import (
    ServiceDeliveryPointActionResponseSchema,
    ServiceDeliveryPointCreateSchema,
    ServiceDeliveryPointListResponseSchema,
    ServiceDeliveryPointReadSchema,
    ServiceDeliveryPointStatusToggleSchema,
    ServiceDeliveryPointUpdateSchema,
    StaffAssignmentSchema,
    StaffUnassignmentSchema,
)
from app.services.service_delivery_point_service import ServiceDeliveryService
from app.services.staff_profile_service import StaffProfileService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/service-delivery-points",
    tags=["Service Delivery Points"],
)


def get_service_delivery_service(
    db: Annotated[Session, Depends(get_db)],
) -> ServiceDeliveryService:
    """
    Dependency provider for the service delivery service.
    """
    return ServiceDeliveryService(db)


def get_staff_profile_service(
    db: Annotated[Session, Depends(get_db)],
) -> StaffProfileService:
    """
    Dependency provider for the staff profile service.
    """
    return StaffProfileService(db)


# ============================================================
# ROUTES
# ============================================================

@router.post(
    "/",
    response_model=ServiceDeliveryPointReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create service delivery point",
)
def create_service_delivery_point(
    payload: ServiceDeliveryPointCreateSchema,
    _: AdminUser,
    service: Annotated[ServiceDeliveryService, Depends(get_service_delivery_service)],
):
    """
    Create a new service delivery point.
    """
    return service.create_service_delivery_point(payload)


@router.get(
    "/",
    response_model=ServiceDeliveryPointListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List service delivery points",
)
def list_service_delivery_points(
    _: AdminUser,
    service: Annotated[ServiceDeliveryService, Depends(get_service_delivery_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=1000, description="Pagination size."),
    name: Optional[str] = Query(None),
    code: Optional[str] = Query(None),
    service_point_type: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    supports_appointments: Optional[bool] = Query(None),
    supports_walk_in: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    """
    Return a paginated list of service delivery points with optional filters.
    """
    items, total = service.list_service_delivery_points(
        skip=skip,
        limit=limit,
        name=name,
        code=code,
        service_point_type=service_point_type,
        department_id=department_id,
        supports_appointments=supports_appointments,
        supports_walk_in=supports_walk_in,
        is_active=is_active,
    )

    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Service delivery points fetched successfully.",
    )


@router.get(
    "/active",
    response_model=ServiceDeliveryPointListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List active service delivery points",
)
def list_active_service_delivery_points(
    _: AdminUser,
    service: Annotated[ServiceDeliveryService, Depends(get_service_delivery_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(100, ge=1, le=1000, description="Pagination size."),
    service_point_type: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
):
    """
    Return a paginated list of active service delivery points.
    """
    items, total = service.list_active_service_delivery_points(
        skip=skip,
        limit=limit,
        service_point_type=service_point_type,
        department_id=department_id,
    )

    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Active service delivery points fetched successfully.",
    )


@router.get(
    "/queue-stats",
    status_code=status.HTTP_200_OK,
    summary="Live queue metrics per service delivery point",
)
def service_delivery_point_queue_stats(
    _: AdminUser,
    service: Annotated[ServiceDeliveryService, Depends(get_service_delivery_service)],
):
    """
    Return live per-SDP queue counts (waiting/called/serving) and today's
    total tickets issued.
    """
    return service.queue_stats()


@router.get(
    "/by-code/{code}",
    response_model=ServiceDeliveryPointReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get service delivery point by code",
)
def get_service_delivery_point_by_code(
    code: str,
    _: AdminUser,
    service: Annotated[ServiceDeliveryService, Depends(get_service_delivery_service)],
):
    """
    Return a service delivery point by code.
    """
    return service.get_service_delivery_point_by_code(code)


@router.get(
    "/{service_delivery_point_id}",
    response_model=ServiceDeliveryPointReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get service delivery point",
)
def get_service_delivery_point(
    service_delivery_point_id: int,
    _: AdminUser,
    service: Annotated[ServiceDeliveryService, Depends(get_service_delivery_service)],
):
    """
    Return a single service delivery point by ID.
    """
    return service.get_service_delivery_point(service_delivery_point_id)


@router.put(
    "/{service_delivery_point_id}",
    response_model=ServiceDeliveryPointReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update service delivery point",
)
def update_service_delivery_point(
    service_delivery_point_id: int,
    payload: ServiceDeliveryPointUpdateSchema,
    _: AdminUser,
    service: Annotated[ServiceDeliveryService, Depends(get_service_delivery_service)],
):
    """
    Update a service delivery point.
    """
    return service.update_service_delivery_point(service_delivery_point_id, payload)


@router.patch(
    "/{service_delivery_point_id}/status",
    response_model=ServiceDeliveryPointReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Activate or deactivate service delivery point",
)
def set_service_delivery_point_status(
    service_delivery_point_id: int,
    payload: ServiceDeliveryPointStatusToggleSchema,
    _: AdminUser,
    service: Annotated[ServiceDeliveryService, Depends(get_service_delivery_service)],
):
    """
    Activate or deactivate a service delivery point.
    """
    return service.set_active_status(service_delivery_point_id, payload)


@router.delete(
    "/{service_delivery_point_id}",
    response_model=ServiceDeliveryPointActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Delete service delivery point",
)
def delete_service_delivery_point(
    service_delivery_point_id: int,
    _: AdminUser,
    service: Annotated[ServiceDeliveryService, Depends(get_service_delivery_service)],
):
    """
    Soft-delete a service delivery point.
    """
    record = service.delete_service_delivery_point(service_delivery_point_id)
    return {
        "success": True,
        "message": f"Service delivery point '{record.code}' deleted successfully.",
    }


# ============================================================
# STAFF ASSIGNMENT ROUTES
# ============================================================

@router.post(
    "/{service_delivery_point_id}/assign-staff",
    response_model=ServiceDeliveryPointActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Assign staff to service delivery point",
)
def assign_staff_to_sdp(
    service_delivery_point_id: int,
    payload: StaffAssignmentSchema,
    _: AdminUser,
    staff_service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Assign one or more staff profiles to this service delivery point.
    """
    count = staff_service.assign_staff_to_sdp(
        payload.staff_profile_ids,
        service_delivery_point_id
    )
    return {
        "success": True,
        "message": f"{count} staff member(s) assigned successfully.",
    }


@router.post(
    "/{service_delivery_point_id}/unassign-staff",
    response_model=ServiceDeliveryPointActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Unassign staff from service delivery point",
)
def unassign_staff_from_sdp(
    service_delivery_point_id: int,
    payload: StaffUnassignmentSchema,
    _: AdminUser,
    staff_service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
):
    """
    Unassign one or more staff profiles from this service delivery point.
    """
    count = staff_service.unassign_staff_from_sdp(
        service_delivery_point_id,
        payload.staff_profile_ids
    )
    return {
        "success": True,
        "message": f"{count} staff member(s) unassigned successfully.",
    }


@router.get(
    "/{service_delivery_point_id}/staff",
    status_code=status.HTTP_200_OK,
    summary="List staff assigned to service delivery point",
)
def list_sdp_staff(
    service_delivery_point_id: int,
    _: AdminUser,
    staff_service: Annotated[StaffProfileService, Depends(get_staff_profile_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Return a paginated list of staff profiles assigned to this service delivery point.
    """
    items, total = staff_service.list_staff_by_sdp(
        service_delivery_point_id,
        skip=skip,
        limit=limit
    )
    return paginate_response(
        items=[{
            "id": item.id,
            "staff_no": item.staff_no,
            "job_title": item.job_title,
            "first_name": item.user.first_name if item.user else None,
            "last_name": item.user.last_name if item.user else None,
            "email": item.user.email if item.user else None,
        } for item in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Staff members fetched successfully.",
    )