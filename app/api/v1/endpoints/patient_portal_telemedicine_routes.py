# app/api/v1/endpoints/patient_portal_telemedicine_routes.py
from __future__ import annotations

"""
Patient-facing Telemedicine endpoints (portal).

A patient can see their own telemedicine sessions, join the virtual room for
an upcoming/active session, read the in-session chat and send messages. All
data is strictly scoped to the authenticated patient; scheduling, SOAP notes
and lifecycle control remain clinician-only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_plan_feature
from app.core.enums import TelemedicineSenderRole
from app.models.all_models import User
from app.schemas.telemedicine_schemas import (
    TelemedicineJoinResponseSchema,
    TelemedicineListResponseSchema,
    TelemedicineMessageCreateSchema,
    TelemedicineMessageListResponseSchema,
    TelemedicineMessageResponseSchema,
)
from app.services.patient_portal_service import PatientPortalService
from app.services.telemedicine_service import TelemedicineService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/portal/telemedicine",
    tags=["Patient Portal - Telemedicine"],
    dependencies=[Depends(require_plan_feature("patient_portal"))],
)


def _patient_id(db: Session, user: User) -> int:
    return PatientPortalService(db).get_patient_by_user_id(user.id).id


def _patient_name(db: Session, user: User) -> str:
    name = " ".join(x for x in [getattr(user, "first_name", None), getattr(user, "last_name", None)] if x).strip()
    return name or "Patient"


def _own_session(service: TelemedicineService, session_id: int, pid: int):
    session = service.get(session_id)
    if session.patient_id != pid:
        raise HTTPException(status_code=404, detail="Telemedicine session not found.")
    return session


@router.get("/sessions", response_model=TelemedicineListResponseSchema, summary="My telemedicine sessions")
def my_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    pid = _patient_id(db, current_user)
    items, total = TelemedicineService(db).list(patient_id=pid, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Your telemedicine sessions.")


@router.post("/sessions/{session_id}/join", response_model=TelemedicineJoinResponseSchema, summary="Join my telemedicine room")
def join_my_session(
    session_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    pid = _patient_id(db, current_user)
    service = TelemedicineService(db)
    _own_session(service, session_id, pid)
    name = _patient_name(db, current_user)
    session = service.join(session_id, user_id=current_user.id, is_clinician=False, display_name=name)
    join = service.build_join_info(session, is_clinician=False, display_name=name)
    return {"success": True, "message": "Joined session.", "join": join, "session": session}


@router.get("/sessions/{session_id}/messages", response_model=TelemedicineMessageListResponseSchema, summary="My session chat history")
def my_messages(
    session_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    pid = _patient_id(db, current_user)
    service = TelemedicineService(db)
    _own_session(service, session_id, pid)
    items = service.list_messages(session_id)
    return paginate_response(items=items, total=len(items), skip=0, limit=len(items) or 1, message="Messages fetched successfully.")


@router.post("/sessions/{session_id}/messages", response_model=TelemedicineMessageResponseSchema, summary="Send a message to my care team")
def send_my_message(
    session_id: int,
    payload: TelemedicineMessageCreateSchema,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    pid = _patient_id(db, current_user)
    service = TelemedicineService(db)
    _own_session(service, session_id, pid)
    msg = service.send_message(
        session_id, payload,
        sender_user_id=current_user.id, sender_role=TelemedicineSenderRole.PATIENT,
        sender_name=_patient_name(db, current_user),
    )
    return {"success": True, "message": "Message sent.", "chat_message": msg}
