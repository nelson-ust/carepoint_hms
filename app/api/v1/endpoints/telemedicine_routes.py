# app/api/v1/endpoints/telemedicine_routes.py
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.core.enums import TelemedicineSenderRole
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.telemedicine_schemas import (
    TelemedicineActionResponseSchema,
    TelemedicineCancelSchema,
    TelemedicineCompleteSchema,
    TelemedicineJoinResponseSchema,
    TelemedicineListResponseSchema,
    TelemedicineMessageCreateSchema,
    TelemedicineMessageListResponseSchema,
    TelemedicineMessageResponseSchema,
    TelemedicineNoteUpsertSchema,
    TelemedicineSessionCreateSchema,
    TelemedicineSessionUpdateSchema,
)
from app.services.telemedicine_service import TelemedicineService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/telemedicine/sessions",
    tags=["Telemedicine"],
    dependencies=[Depends(require_plan_feature("clinical"))],
)


def get_service(db: Annotated[Session, Depends(get_db)]) -> TelemedicineService:
    return TelemedicineService(db)


def _actor_name(user: User) -> str:
    name = " ".join(x for x in [getattr(user, "first_name", None), getattr(user, "last_name", None)] if x).strip()
    return name or getattr(user, "email", None) or "Clinician"


@router.get("/", response_model=TelemedicineListResponseSchema, summary="List telemedicine sessions")
def list_sessions(
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_READ", "TELEMEDICINE_CREATE"))],
    service: Annotated[TelemedicineService, Depends(get_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    patient_id: Optional[int] = Query(None),
    clinician_staff_id: Optional[int] = Query(None),
    modality: Optional[str] = Query(None),
    from_dt: Optional[datetime] = Query(None),
    to_dt: Optional[datetime] = Query(None),
):
    items, total = service.list(
        status=status_filter, patient_id=patient_id, clinician_staff_id=clinician_staff_id,
        modality=modality, from_dt=from_dt, to_dt=to_dt, skip=skip, limit=limit,
    )
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Telemedicine sessions fetched successfully.")


@router.get("/{session_id}", response_model=TelemedicineActionResponseSchema, summary="Get a telemedicine session")
def get_session(
    session_id: int,
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_READ", "TELEMEDICINE_CREATE"))],
    service: Annotated[TelemedicineService, Depends(get_service)],
):
    return {"success": True, "message": "Session fetched.", "session": service.get(session_id)}


@router.post("/", response_model=TelemedicineActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Schedule a telemedicine session")
def create_session(
    payload: TelemedicineSessionCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[TelemedicineService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_CREATE"))],
):
    return {"success": True, "message": "Telemedicine session scheduled.", "session": service.create(payload, actor_user_id=actor.id)}


@router.patch("/{session_id}", response_model=TelemedicineActionResponseSchema, summary="Update session scheduling")
def update_session(
    session_id: int,
    payload: TelemedicineSessionUpdateSchema,
    service: Annotated[TelemedicineService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_UPDATE", "TELEMEDICINE_CREATE"))],
):
    return {"success": True, "message": "Session updated.", "session": service.update(session_id, payload)}


@router.post("/{session_id}/join", response_model=TelemedicineJoinResponseSchema, summary="Clinician joins the virtual room")
def join_session(
    session_id: int,
    actor: CurrentActiveUser,
    service: Annotated[TelemedicineService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_CONDUCT", "TELEMEDICINE_READ"))],
):
    session = service.join(session_id, user_id=actor.id, is_clinician=True, display_name=_actor_name(actor))
    join = service.build_join_info(session, is_clinician=True, display_name=_actor_name(actor))
    return {"success": True, "message": "Joined session.", "join": join, "session": session}


@router.post("/{session_id}/start", response_model=TelemedicineActionResponseSchema, summary="Start the consultation")
def start_session(
    session_id: int,
    actor: CurrentActiveUser,
    service: Annotated[TelemedicineService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_CONDUCT"))],
):
    return {"success": True, "message": "Consultation started.", "session": service.start(session_id, actor_user_id=actor.id)}


@router.put("/{session_id}/notes", response_model=TelemedicineActionResponseSchema, summary="Record/update SOAP consultation notes")
def upsert_notes(
    session_id: int,
    payload: TelemedicineNoteUpsertSchema,
    actor: CurrentActiveUser,
    service: Annotated[TelemedicineService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_CONDUCT"))],
):
    return {"success": True, "message": "Notes saved.", "session": service.upsert_notes(session_id, payload, actor_user_id=actor.id)}


@router.post("/{session_id}/complete", response_model=TelemedicineActionResponseSchema, summary="Complete the consultation")
def complete_session(
    session_id: int,
    payload: TelemedicineCompleteSchema,
    actor: CurrentActiveUser,
    service: Annotated[TelemedicineService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_CONDUCT"))],
):
    return {"success": True, "message": "Consultation completed.", "session": service.complete(session_id, payload, actor_user_id=actor.id)}


@router.post("/{session_id}/cancel", response_model=TelemedicineActionResponseSchema, summary="Cancel a telemedicine session")
def cancel_session(
    session_id: int,
    payload: TelemedicineCancelSchema,
    actor: CurrentActiveUser,
    service: Annotated[TelemedicineService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_CANCEL", "TELEMEDICINE_UPDATE"))],
):
    return {"success": True, "message": "Session cancelled.", "session": service.cancel(session_id, payload, actor_user_id=actor.id)}


@router.post("/{session_id}/no-show", response_model=TelemedicineActionResponseSchema, summary="Mark session as no-show")
def no_show_session(
    session_id: int,
    actor: CurrentActiveUser,
    service: Annotated[TelemedicineService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_CONDUCT", "TELEMEDICINE_UPDATE"))],
):
    return {"success": True, "message": "Marked as no-show.", "session": service.mark_no_show(session_id, actor_user_id=actor.id)}


@router.get("/{session_id}/messages", response_model=TelemedicineMessageListResponseSchema, summary="Session chat history")
def list_messages(
    session_id: int,
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_READ", "TELEMEDICINE_CONDUCT"))],
    service: Annotated[TelemedicineService, Depends(get_service)],
):
    items = service.list_messages(session_id)
    return paginate_response(items=items, total=len(items), skip=0, limit=len(items) or 1, message="Messages fetched successfully.")


@router.post("/{session_id}/messages", response_model=TelemedicineMessageResponseSchema, status_code=status.HTTP_201_CREATED, summary="Send a secure chat message")
def send_message(
    session_id: int,
    payload: TelemedicineMessageCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[TelemedicineService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("TELEMEDICINE_CONDUCT", "TELEMEDICINE_READ"))],
):
    msg = service.send_message(
        session_id, payload,
        sender_user_id=actor.id, sender_role=TelemedicineSenderRole.CLINICIAN, sender_name=_actor_name(actor),
    )
    return {"success": True, "message": "Message sent.", "chat_message": msg}
