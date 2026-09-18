# app/api/v1/endpoints/home_visit_routes.py
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.home_visit_schemas import (
    HomeVisitActionResponseSchema,
    HomeVisitAssignSchema,
    HomeVisitCancelSchema,
    HomeVisitCreateSchema,
    HomeVisitEventListResponseSchema,
    HomeVisitListResponseSchema,
    HomeVisitNoteResponseSchema,
    HomeVisitNoteUpsertSchema,
    HomeVisitStatusChangeSchema,
    HomeVisitUpdateSchema,
)
from app.services.home_visit_service import HomeVisitService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/home-visits",
    tags=["Home Health - Home Visits"],
    dependencies=[Depends(require_plan_feature("clinical"))],
)


def get_service(db: Annotated[Session, Depends(get_db)]) -> HomeVisitService:
    return HomeVisitService(db)


@router.get("/", response_model=HomeVisitListResponseSchema, summary="List home visits")
def list_home_visits(
    _: Annotated[User, Depends(require_permission("HOME_VISIT_READ", "HOME_VISIT_CREATE"))],
    service: Annotated[HomeVisitService, Depends(get_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    patient_id: Optional[int] = Query(None),
    assigned_staff_id: Optional[int] = Query(None),
    visit_type: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    from_dt: Optional[datetime] = Query(None),
    to_dt: Optional[datetime] = Query(None),
):
    items, total = service.list(
        status=status_filter, patient_id=patient_id, assigned_staff_id=assigned_staff_id,
        visit_type=visit_type, priority=priority, from_dt=from_dt, to_dt=to_dt,
        skip=skip, limit=limit,
    )
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Home visits fetched successfully.")


@router.get("/{visit_id}", response_model=HomeVisitActionResponseSchema, summary="Get a home visit")
def get_home_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("HOME_VISIT_READ", "HOME_VISIT_CREATE"))],
    service: Annotated[HomeVisitService, Depends(get_service)],
):
    visit = service.get(visit_id)
    return {"success": True, "message": "Home visit fetched.", "home_visit": visit}


@router.post("/", response_model=HomeVisitActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Request/schedule a home visit")
def create_home_visit(
    payload: HomeVisitCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[HomeVisitService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("HOME_VISIT_CREATE"))],
):
    visit = service.create(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Home visit created.", "home_visit": visit}


@router.patch("/{visit_id}", response_model=HomeVisitActionResponseSchema, summary="Update home visit scheduling")
def update_home_visit(
    visit_id: int,
    payload: HomeVisitUpdateSchema,
    actor: CurrentActiveUser,
    service: Annotated[HomeVisitService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("HOME_VISIT_UPDATE"))],
):
    visit = service.update(visit_id, payload)
    return {"success": True, "message": "Home visit updated.", "home_visit": visit}


@router.post("/{visit_id}/assign", response_model=HomeVisitActionResponseSchema, summary="Assign a caregiver")
def assign_home_visit(
    visit_id: int,
    payload: HomeVisitAssignSchema,
    actor: CurrentActiveUser,
    service: Annotated[HomeVisitService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("HOME_VISIT_ASSIGN", "HOME_VISIT_UPDATE"))],
):
    visit = service.assign(visit_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Caregiver assigned.", "home_visit": visit}


@router.post("/{visit_id}/status", response_model=HomeVisitActionResponseSchema, summary="Transition home visit status")
def change_status(
    visit_id: int,
    payload: HomeVisitStatusChangeSchema,
    actor: CurrentActiveUser,
    service: Annotated[HomeVisitService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("HOME_VISIT_UPDATE", "HOME_VISIT_DOCUMENT"))],
):
    visit = service.change_status(visit_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": f"Home visit is now {visit.status}.", "home_visit": visit}


@router.post("/{visit_id}/cancel", response_model=HomeVisitActionResponseSchema, summary="Cancel a home visit")
def cancel_home_visit(
    visit_id: int,
    payload: HomeVisitCancelSchema,
    actor: CurrentActiveUser,
    service: Annotated[HomeVisitService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("HOME_VISIT_CANCEL", "HOME_VISIT_UPDATE"))],
):
    visit = service.cancel(visit_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Home visit cancelled.", "home_visit": visit}


@router.get("/{visit_id}/events", response_model=HomeVisitEventListResponseSchema, summary="Home visit status/GPS timeline")
def list_events(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("HOME_VISIT_READ", "HOME_VISIT_CREATE"))],
    service: Annotated[HomeVisitService, Depends(get_service)],
):
    items = service.list_events(visit_id)
    return paginate_response(items=items, total=len(items), skip=0, limit=len(items) or 1, message="Status events fetched successfully.")


@router.get("/{visit_id}/documentation", response_model=HomeVisitNoteResponseSchema, summary="Get home visit documentation")
def get_documentation(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("HOME_VISIT_READ", "HOME_VISIT_DOCUMENT"))],
    service: Annotated[HomeVisitService, Depends(get_service)],
):
    note = service.get_note(visit_id)
    if note is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No documentation recorded for this visit yet.")
    return {"success": True, "message": "Documentation fetched.", "note": note}


@router.put("/{visit_id}/documentation", response_model=HomeVisitNoteResponseSchema, summary="Record/update home visit documentation")
def upsert_documentation(
    visit_id: int,
    payload: HomeVisitNoteUpsertSchema,
    actor: CurrentActiveUser,
    service: Annotated[HomeVisitService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("HOME_VISIT_DOCUMENT"))],
):
    note = service.upsert_note(visit_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Documentation saved.", "note": note}
