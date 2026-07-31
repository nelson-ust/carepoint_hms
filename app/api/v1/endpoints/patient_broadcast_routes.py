# app/api/v1/endpoints/patient_broadcast_routes.py
from __future__ import annotations

"""
Staff-facing endpoints for hospital→patient outbound messaging.

Users holding ``MESSAGE_SEND`` (plus superusers) can compose a message and send
it to a single patient, a selected group of patients, or every registered
patient. Patients read these messages from the patient portal.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.patient_broadcast_schemas import (
    AudiencePreviewResponse,
    AudiencePreviewSchema,
    PatientBroadcastCreateResponse,
    PatientBroadcastCreateSchema,
    PatientBroadcastListResponse,
    PatientBroadcastReadSchema,
)
from app.services.patient_broadcast_service import PatientBroadcastService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/patient-broadcasts",
    tags=["Patient Broadcasts"],
    dependencies=[Depends(require_permission("MESSAGE_SEND"))],
)


def _get_service(db: Annotated[Session, Depends(get_db)]) -> PatientBroadcastService:
    return PatientBroadcastService(db)


@router.post(
    "",
    response_model=PatientBroadcastCreateResponse,
    summary="Send a message to one, several, or all patients",
)
def send_broadcast(
    payload: PatientBroadcastCreateSchema,
    service: Annotated[PatientBroadcastService, Depends(_get_service)],
    current_user: Annotated[User, Depends(require_permission("MESSAGE_SEND"))],
):
    broadcast, sender_name = service.create_broadcast(
        payload, actor_user_id=getattr(current_user, "id", None)
    )
    reached = broadcast.recipient_count
    return PatientBroadcastCreateResponse(
        success=True,
        message=(
            f"Message sent to {reached} patient" + ("" if reached == 1 else "s") + "."
        ),
        broadcast=PatientBroadcastReadSchema.from_row(broadcast, sent_by_name=sender_name),
    )


@router.get(
    "",
    response_model=PatientBroadcastListResponse,
    summary="List previously sent patient messages",
)
def list_broadcasts(
    service: Annotated[PatientBroadcastService, Depends(_get_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    rows, total, sender_names, read_counts = service.list_broadcasts(skip=skip, limit=limit)
    items = [
        PatientBroadcastReadSchema.from_row(
            b,
            sent_by_name=sender_names.get(b.sent_by_user_id) if b.sent_by_user_id else None,
            read_count=read_counts.get(b.id, 0),
        )
        for b in rows
    ]
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Messages fetched successfully.",
    )


@router.post(
    "/audience-preview",
    response_model=AudiencePreviewResponse,
    summary="Count how many patients an audience selection will reach",
)
def preview_audience(
    payload: AudiencePreviewSchema,
    service: Annotated[PatientBroadcastService, Depends(_get_service)],
):
    count = service.audience_preview(payload.audience_type, payload.patient_ids)
    return AudiencePreviewResponse(
        audience_type=payload.audience_type, recipient_count=count
    )
