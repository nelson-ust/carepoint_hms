# app/api/v1/endpoints/ambulance_routes.py
from __future__ import annotations

"""
FastAPI routes for the ambulance / emergency-transport module (Stage 15).

Sub-routes
----------
- ``/ambulances`` — fleet master data and readiness
- ``/ambulances/{id}/drivers`` — driver assignments
- ``/ambulances/{id}/equipment`` — equipment catalog
- ``/ambulances/{id}/maintenance`` — maintenance log
- ``/ambulance-dispatches`` — dispatch lifecycle
- ``/ambulance-dispatches/{id}/incidents`` — incident reports

Permission codes
----------------
- ``AMBULANCE_READ``      — fleet listing / details
- ``AMBULANCE_MANAGE``    — fleet master data + driver / equipment / maintenance
- ``DISPATCH_READ``       — dispatch list / details
- ``DISPATCH_MANAGE``     — create / progress dispatches and file incidents
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.ambulance_schemas import (
    AmbulanceActionResponseSchema,
    AmbulanceCreateSchema,
    AmbulanceDispatchActionResponseSchema,
    AmbulanceDispatchAssignSchema,
    AmbulanceDispatchCreateSchema,
    AmbulanceDispatchListResponseSchema,
    AmbulanceDispatchReadSchema,
    AmbulanceDispatchTransitionSchema,
    AmbulanceDriverActionResponseSchema,
    AmbulanceDriverCreateSchema,
    AmbulanceDriverListResponseSchema,
    AmbulanceDriverReadSchema,
    AmbulanceDriverUpdateSchema,
    AmbulanceEquipmentActionResponseSchema,
    AmbulanceEquipmentCreateSchema,
    AmbulanceEquipmentListResponseSchema,
    AmbulanceEquipmentReadSchema,
    AmbulanceEquipmentUpdateSchema,
    AmbulanceIncidentReportActionResponseSchema,
    AmbulanceIncidentReportCreateSchema,
    AmbulanceIncidentReportListResponseSchema,
    AmbulanceListResponseSchema,
    AmbulanceMaintenanceActionResponseSchema,
    AmbulanceMaintenanceCreateSchema,
    AmbulanceMaintenanceListResponseSchema,
    AmbulanceMaintenanceReadSchema,
    AmbulanceMaintenanceUpdateSchema,
    AmbulanceReadinessResponseSchema,
    AmbulanceReadSchema,
    AmbulanceStatsResponseSchema,
    AmbulanceStatusUpdateSchema,
    AmbulanceUpdateSchema,
)
from app.services.ambulance_service import AmbulanceService
from app.utils.pagination import paginate_response


from app.core.dependencies import require_plan_feature

# Two routers under one prefix tree keep dispatches discoverable in Swagger.
router = APIRouter(
    prefix="/ambulances", 
    tags=["Ambulances"],
    dependencies=[Depends(require_plan_feature("ambulance"))]
)
dispatch_router = APIRouter(
    prefix="/ambulance-dispatches", 
    tags=["Ambulance Dispatches"],
    dependencies=[Depends(require_plan_feature("ambulance"))]
)



def get_ambulance_service(db: Annotated[Session, Depends(get_db)]) -> AmbulanceService:
    """FastAPI dependency that constructs an AmbulanceService per-request."""
    return AmbulanceService(db)


# --- ORM -> dict helpers ----------------------------------------------------
# Kept here to avoid duplicating shape decisions across both routers.

def _ambulance_dict(a) -> dict:
    return {
        "id": a.id,
        "code": a.code,
        "plate_number": a.plate_number,
        "model": a.model,
        "manufacturer": a.manufacturer,
        "year_of_manufacture": a.year_of_manufacture,
        "color": a.color,
        "status": str(a.status),
        "current_mileage": a.current_mileage,
        "notes": a.notes,
        "created_at": getattr(a, "created_at", None),
        "updated_at": getattr(a, "updated_at", None),
    }


def _driver_dict(d) -> dict:
    return {
        "id": d.id,
        "staff_profile_id": d.staff_profile_id,
        "ambulance_id": d.ambulance_id,
        "driver_license_no": d.driver_license_no,
        "license_expiry_date": d.license_expiry_date,
        "is_primary_driver": bool(d.is_primary_driver),
        "emergency_response_certified": bool(d.emergency_response_certified),
        "notes": d.notes,
        "created_at": getattr(d, "created_at", None),
        "updated_at": getattr(d, "updated_at", None),
    }


def _equipment_dict(e) -> dict:
    return {
        "id": e.id,
        "ambulance_id": e.ambulance_id,
        "equipment_name": e.equipment_name,
        "equipment_code": e.equipment_code,
        "quantity": e.quantity,
        "condition_status": e.condition_status,
        "expiry_date": e.expiry_date,
        "notes": e.notes,
        "created_at": getattr(e, "created_at", None),
    }


def _maintenance_dict(m) -> dict:
    return {
        "id": m.id,
        "ambulance_id": m.ambulance_id,
        "maintenance_status": str(m.maintenance_status),
        "maintenance_type": m.maintenance_type,
        "issue_description": m.issue_description,
        "service_provider": m.service_provider,
        "maintenance_date": m.maintenance_date,
        "completed_date": m.completed_date,
        "cost": m.cost,
        "mileage_at_service": m.mileage_at_service,
    }


def _dispatch_dict(d) -> dict:
    return {
        "id": d.id,
        "dispatch_no": d.dispatch_no,
        "ambulance_id": d.ambulance_id,
        "driver_id": d.driver_id,
        "patient_id": d.patient_id,
        "visit_id": d.visit_id,
        "dispatch_status": str(d.dispatch_status),
        "pickup_location": d.pickup_location,
        "destination_location": d.destination_location,
        "incident_description": d.incident_description,
        "requested_at": d.requested_at,
        "assigned_at": d.assigned_at,
        "departed_at": d.departed_at,
        "arrived_at": d.arrived_at,
        "completed_at": d.completed_at,
        "created_at": getattr(d, "created_at", None),
    }


def _incident_dict(i) -> dict:
    return {
        "id": i.id,
        "dispatch_id": i.dispatch_id,
        "reported_by_staff_id": i.reported_by_staff_id,
        "severity": str(i.severity),
        "incident_date": i.incident_date,
        "summary": i.summary,
        "action_taken": i.action_taken,
        "follow_up_required": bool(i.follow_up_required),
        "created_at": getattr(i, "created_at", None),
    }


# ============================================================
# FLEET
# ============================================================


@router.get(
    "/",
    response_model=AmbulanceListResponseSchema,
    summary="List ambulances",
)
def list_ambulances(
    _: Annotated[User, Depends(require_permission("AMBULANCE_READ"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    status_filter: Optional[str] = Query(
        None, alias="status",
        description="AVAILABLE, DISPATCHED, IN_TRANSIT, OUT_OF_SERVICE, UNDER_MAINTENANCE.",
    ),
):
    items, total = service.list_ambulances(skip=skip, limit=limit, status=status_filter)
    return paginate_response(
        items=[_ambulance_dict(a) for a in items],
        total=total, skip=skip, limit=limit,
        message="Ambulances fetched successfully.",
    )


# NOTE: declared before "/{ambulance_id}" so the literal path wins routing.
@router.get(
    "/stats",
    response_model=AmbulanceStatsResponseSchema,
    summary="Fleet-wide ambulance statistics",
)
def get_fleet_stats(
    _: Annotated[User, Depends(require_permission("AMBULANCE_READ"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    data = service.get_fleet_stats()
    return {
        "success": True,
        "message": "Fleet statistics computed successfully.",
        **data,
    }


@router.post(
    "/",
    response_model=AmbulanceActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add an ambulance",
)
def create_ambulance(
    payload: AmbulanceCreateSchema,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    a = service.create(payload)
    return {"success": True, "message": "Ambulance added.", "ambulance": _ambulance_dict(a)}


@router.get(
    "/{ambulance_id}",
    response_model=AmbulanceReadSchema,
    summary="Get an ambulance",
)
def get_ambulance(
    ambulance_id: int,
    _: Annotated[User, Depends(require_permission("AMBULANCE_READ"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    return _ambulance_dict(service.get(ambulance_id))


@router.put(
    "/{ambulance_id}",
    response_model=AmbulanceActionResponseSchema,
    summary="Update an ambulance",
)
def update_ambulance(
    ambulance_id: int,
    payload: AmbulanceUpdateSchema,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    a = service.update(ambulance_id, payload)
    return {"success": True, "message": "Ambulance updated.", "ambulance": _ambulance_dict(a)}


@router.post(
    "/{ambulance_id}/status",
    response_model=AmbulanceActionResponseSchema,
    summary="Change ambulance operational status",
)
def update_ambulance_status(
    ambulance_id: int,
    payload: AmbulanceStatusUpdateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    a = service.update_status(ambulance_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": f"Ambulance status updated to {payload.new_status}.",
        "ambulance": _ambulance_dict(a),
    }


@router.delete(
    "/{ambulance_id}",
    summary="Retire (soft-delete) an ambulance",
)
def soft_delete_ambulance(
    ambulance_id: int,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    a = service.soft_delete(ambulance_id)
    return {"success": True, "message": "Ambulance retired.", "ambulance_id": a.id}


@router.get(
    "/{ambulance_id}/readiness",
    response_model=AmbulanceReadinessResponseSchema,
    summary="Compute ambulance dispatch readiness",
)
def compute_readiness(
    ambulance_id: int,
    _: Annotated[User, Depends(require_permission("AMBULANCE_READ", "DISPATCH_READ"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    data = service.compute_readiness(ambulance_id)
    return {
        "success": True,
        "message": "Readiness computed successfully.",
        **data,
    }


# ============================================================
# DRIVERS
# ============================================================


@router.get(
    "/drivers/",
    response_model=AmbulanceDriverListResponseSchema,
    summary="List ambulance drivers",
)
def list_drivers(
    _: Annotated[User, Depends(require_permission("AMBULANCE_READ"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    ambulance_id: Optional[int] = Query(None),
):
    items, total = service.list_drivers(skip=skip, limit=limit, ambulance_id=ambulance_id)
    return paginate_response(
        items=[_driver_dict(d) for d in items],
        total=total, skip=skip, limit=limit,
        message="Drivers fetched successfully.",
    )


@router.post(
    "/drivers/",
    response_model=AmbulanceDriverActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register an ambulance driver",
)
def create_driver(
    payload: AmbulanceDriverCreateSchema,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    d = service.create_driver(payload)
    return {"success": True, "message": "Driver registered.", "driver": _driver_dict(d)}


@router.put(
    "/drivers/{driver_id}",
    response_model=AmbulanceDriverActionResponseSchema,
    summary="Update an ambulance driver",
)
def update_driver(
    driver_id: int,
    payload: AmbulanceDriverUpdateSchema,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    d = service.update_driver(driver_id, payload)
    return {"success": True, "message": "Driver updated.", "driver": _driver_dict(d)}


@router.delete(
    "/drivers/{driver_id}",
    summary="Soft-delete an ambulance driver",
)
def soft_delete_driver(
    driver_id: int,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    d = service.soft_delete_driver(driver_id)
    return {"success": True, "message": "Driver retired.", "driver_id": d.id}


# ============================================================
# EQUIPMENT
# ============================================================


@router.get(
    "/{ambulance_id}/equipment",
    response_model=AmbulanceEquipmentListResponseSchema,
    summary="List equipment for an ambulance",
)
def list_equipment(
    ambulance_id: int,
    _: Annotated[User, Depends(require_permission("AMBULANCE_READ"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    items = service.list_equipment(ambulance_id)
    return paginate_response(
        items=[_equipment_dict(i) for i in items],
        total=len(items), skip=0, limit=len(items) or 1,
        message="Equipment fetched successfully.",
    )


@router.post(
    "/{ambulance_id}/equipment",
    response_model=AmbulanceEquipmentActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add equipment to an ambulance",
)
def add_equipment(
    ambulance_id: int,
    payload: AmbulanceEquipmentCreateSchema,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    # Cross-check the URL ambulance_id against the body so callers can't
    # accidentally add equipment to a different ambulance.
    if payload.ambulance_id != ambulance_id:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(
            message="ambulance_id in payload must match URL.",
            detail={"path_id": ambulance_id, "payload_id": payload.ambulance_id},
        )
    e = service.add_equipment(payload)
    return {"success": True, "message": "Equipment added.", "equipment": _equipment_dict(e)}


@router.put(
    "/equipment/{equipment_id}",
    response_model=AmbulanceEquipmentActionResponseSchema,
    summary="Update an equipment item",
)
def update_equipment(
    equipment_id: int,
    payload: AmbulanceEquipmentUpdateSchema,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    e = service.update_equipment(equipment_id, payload)
    return {"success": True, "message": "Equipment updated.", "equipment": _equipment_dict(e)}


@router.delete(
    "/equipment/{equipment_id}",
    summary="Remove an equipment item",
)
def soft_delete_equipment(
    equipment_id: int,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    e = service.soft_delete_equipment(equipment_id)
    return {"success": True, "message": "Equipment removed.", "equipment_id": e.id}


# ============================================================
# MAINTENANCE
# ============================================================


@router.get(
    "/{ambulance_id}/maintenance",
    response_model=AmbulanceMaintenanceListResponseSchema,
    summary="List maintenance records for an ambulance",
)
def list_maintenance(
    ambulance_id: int,
    _: Annotated[User, Depends(require_permission("AMBULANCE_READ"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    items = service.list_maintenance(ambulance_id)
    return paginate_response(
        items=[_maintenance_dict(i) for i in items],
        total=len(items), skip=0, limit=len(items) or 1,
        message="Maintenance records fetched successfully.",
    )


@router.post(
    "/{ambulance_id}/maintenance",
    response_model=AmbulanceMaintenanceActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a maintenance event",
)
def schedule_maintenance(
    ambulance_id: int,
    payload: AmbulanceMaintenanceCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    if payload.ambulance_id != ambulance_id:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(
            message="ambulance_id in payload must match URL.",
            detail={"path_id": ambulance_id, "payload_id": payload.ambulance_id},
        )
    m = service.schedule_maintenance(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Maintenance scheduled.", "maintenance": _maintenance_dict(m)}


@router.put(
    "/maintenance/{maintenance_id}",
    response_model=AmbulanceMaintenanceActionResponseSchema,
    summary="Update a maintenance record",
)
def update_maintenance(
    maintenance_id: int,
    payload: AmbulanceMaintenanceUpdateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("AMBULANCE_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    m = service.update_maintenance(maintenance_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Maintenance updated.", "maintenance": _maintenance_dict(m)}


# ============================================================
# DISPATCHES (separate router)
# ============================================================


@dispatch_router.get(
    "/",
    response_model=AmbulanceDispatchListResponseSchema,
    summary="List dispatches",
)
def list_dispatches(
    _: Annotated[User, Depends(require_permission("DISPATCH_READ"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    ambulance_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(
        None, alias="status",
        description="PENDING, ASSIGNED, EN_ROUTE, ARRIVED, PATIENT_PICKED, COMPLETED, CANCELLED.",
    ),
    active_only: bool = Query(False, description="If True, return only non-terminal dispatches."),
):
    items, total = service.list_dispatches(
        skip=skip, limit=limit,
        ambulance_id=ambulance_id, status=status_filter, active_only=active_only,
    )
    return paginate_response(
        items=[_dispatch_dict(d) for d in items],
        total=total, skip=skip, limit=limit,
        message="Dispatches fetched successfully.",
    )


@dispatch_router.post(
    "/",
    response_model=AmbulanceDispatchActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new dispatch",
)
def create_dispatch(
    payload: AmbulanceDispatchCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("DISPATCH_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    d = service.create_dispatch(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Dispatch opened.", "dispatch": _dispatch_dict(d)}


@dispatch_router.get(
    "/{dispatch_id}",
    response_model=AmbulanceDispatchReadSchema,
    summary="Get a dispatch",
)
def get_dispatch(
    dispatch_id: int,
    _: Annotated[User, Depends(require_permission("DISPATCH_READ"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    return _dispatch_dict(service.get_dispatch(dispatch_id))


@dispatch_router.post(
    "/{dispatch_id}/assign",
    response_model=AmbulanceDispatchActionResponseSchema,
    summary="Assign ambulance and driver to a pending dispatch",
)
def assign_dispatch(
    dispatch_id: int,
    payload: AmbulanceDispatchAssignSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("DISPATCH_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    d = service.assign_dispatch(dispatch_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Dispatch assigned.", "dispatch": _dispatch_dict(d)}


@dispatch_router.post(
    "/{dispatch_id}/depart",
    response_model=AmbulanceDispatchActionResponseSchema,
    summary="Mark dispatch as EN_ROUTE",
)
def depart_dispatch(
    dispatch_id: int,
    payload: AmbulanceDispatchTransitionSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("DISPATCH_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    d = service.depart_dispatch(dispatch_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Dispatch en route.", "dispatch": _dispatch_dict(d)}


@dispatch_router.post(
    "/{dispatch_id}/arrive",
    response_model=AmbulanceDispatchActionResponseSchema,
    summary="Mark dispatch as ARRIVED",
)
def arrive_dispatch(
    dispatch_id: int,
    payload: AmbulanceDispatchTransitionSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("DISPATCH_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    d = service.arrive_dispatch(dispatch_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Dispatch arrived on scene.", "dispatch": _dispatch_dict(d)}


@dispatch_router.post(
    "/{dispatch_id}/patient-picked",
    response_model=AmbulanceDispatchActionResponseSchema,
    summary="Mark dispatch as PATIENT_PICKED",
)
def patient_picked_dispatch(
    dispatch_id: int,
    payload: AmbulanceDispatchTransitionSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("DISPATCH_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    d = service.patient_picked_dispatch(dispatch_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Patient picked.", "dispatch": _dispatch_dict(d)}


@dispatch_router.post(
    "/{dispatch_id}/complete",
    response_model=AmbulanceDispatchActionResponseSchema,
    summary="Complete a dispatch and free the ambulance",
)
def complete_dispatch(
    dispatch_id: int,
    payload: AmbulanceDispatchTransitionSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("DISPATCH_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    d = service.complete_dispatch(dispatch_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Dispatch completed.", "dispatch": _dispatch_dict(d)}


@dispatch_router.post(
    "/{dispatch_id}/cancel",
    response_model=AmbulanceDispatchActionResponseSchema,
    summary="Cancel a dispatch",
)
def cancel_dispatch(
    dispatch_id: int,
    payload: AmbulanceDispatchTransitionSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("DISPATCH_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    d = service.cancel_dispatch(dispatch_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Dispatch cancelled.", "dispatch": _dispatch_dict(d)}


# ============================================================
# INCIDENT REPORTS
# ============================================================


@dispatch_router.get(
    "/{dispatch_id}/incidents",
    response_model=AmbulanceIncidentReportListResponseSchema,
    summary="List incident reports for a dispatch",
)
def list_incidents(
    dispatch_id: int,
    _: Annotated[User, Depends(require_permission("DISPATCH_READ"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    items = service.list_incidents(dispatch_id)
    return paginate_response(
        items=[_incident_dict(i) for i in items],
        total=len(items), skip=0, limit=len(items) or 1,
        message="Incident reports fetched successfully.",
    )


@dispatch_router.post(
    "/{dispatch_id}/incidents",
    response_model=AmbulanceIncidentReportActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="File an incident report against a dispatch",
)
def file_incident(
    dispatch_id: int,
    payload: AmbulanceIncidentReportCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("DISPATCH_MANAGE"))],
    service: Annotated[AmbulanceService, Depends(get_ambulance_service)],
):
    if payload.dispatch_id != dispatch_id:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(
            message="dispatch_id in payload must match URL.",
            detail={"path_id": dispatch_id, "payload_id": payload.dispatch_id},
        )
    i = service.file_incident(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Incident filed.", "incident": _incident_dict(i)}
