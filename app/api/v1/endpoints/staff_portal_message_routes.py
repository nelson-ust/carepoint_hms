# app/api/v1/endpoints/staff_portal_message_routes.py
from __future__ import annotations

"""
Staff-facing endpoints for the patient-message inbox.

Designated hospital users (holders of the ``PORTAL_MESSAGE_READ`` permission,
plus superusers) can see every message patients send through the portal and
mark them as read. This is read-only: replies are out of scope for now.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.services.portal_service import PortalService
from app.schemas.portal_schemas import (
    StaffPatientMessageRead,
    StaffPatientMessageListResponse,
    StaffPatientMessageUnreadCountResponse,
)
from app.utils.pagination import paginate_response


router = APIRouter(
    prefix="/portal-messages",
    tags=["Patient Messages"],
    dependencies=[Depends(require_permission("PORTAL_MESSAGE_READ"))],
)


def _get_service(db: Annotated[Session, Depends(get_db)]) -> PortalService:
    return PortalService(db)


@router.get(
    "",
    response_model=StaffPatientMessageListResponse,
    summary="List messages sent by patients",
)
def list_patient_messages(
    service: Annotated[PortalService, Depends(_get_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False, description="Only messages the care team hasn't opened yet."),
):
    rows, total = service.list_patient_messages(skip=skip, limit=limit, unread_only=unread_only)
    items = [StaffPatientMessageRead.from_row(msg, patient) for msg, patient in rows]
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Patient messages fetched successfully.",
    )


@router.get(
    "/unread-count",
    response_model=StaffPatientMessageUnreadCountResponse,
    summary="Count unread patient messages",
)
def unread_patient_messages_count(
    service: Annotated[PortalService, Depends(_get_service)],
):
    return StaffPatientMessageUnreadCountResponse(
        success=True, count=service.count_unread_patient_messages()
    )


@router.post(
    "/{message_id}/read",
    response_model=StaffPatientMessageRead,
    summary="Mark a patient message as read",
)
def mark_patient_message_read(
    message_id: int,
    service: Annotated[PortalService, Depends(_get_service)],
):
    message, patient = service.mark_patient_message_read(message_id)
    return StaffPatientMessageRead.from_row(message, patient)
