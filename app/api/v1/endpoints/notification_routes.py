# app/api/v1/endpoints/notification_routes.py
from __future__ import annotations

"""
FastAPI routes for the notifications module (Stage 17).

Endpoints
---------
Templates
- ``GET    /notifications/templates``         list templates
- ``POST   /notifications/templates``         create template
- ``GET    /notifications/templates/{id}``    get template
- ``PUT    /notifications/templates/{id}``    update template
- ``DELETE /notifications/templates/{id}``    soft-delete

Notifications
- ``GET    /notifications``                       list notifications (admin)
- ``GET    /notifications/{id}``                  get notification
- ``POST   /notifications/dispatch``              dispatch from template
- ``POST   /notifications/dispatch-ad-hoc``       dispatch ad-hoc (no template)
- ``POST   /notifications/retry-failed``          bulk retry failed
- ``POST   /notifications/{id}/mark-read``        mark in-app as read

Direct messages
- ``GET    /notifications/messages/inbox``        inbox for caller
- ``GET    /notifications/messages/sent``         sent box
- ``POST   /notifications/messages``              send a message
- ``POST   /notifications/messages/{id}/read``    mark direct message read
- ``GET    /notifications/messages/{id}``         get a message

Permission codes
----------------
- ``NOTIFICATION_READ``    — view templates / notifications
- ``NOTIFICATION_MANAGE``  — template CRUD
- ``NOTIFICATION_DISPATCH`` — send notifications + retry
- ``MESSAGE_SEND``         — send / mark direct messages
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.notification_schema import (
    MessageActionResponseSchema,
    MessageCreateSchema,
    MessageListResponseSchema,
    MessageReadSchema,
    NotificationActionResponseSchema,
    NotificationAdHocDispatchSchema,
    NotificationDispatchSchema,
    NotificationListResponseSchema,
    NotificationReadSchema,
    NotificationRetryResponseSchema,
    NotificationTemplateActionResponseSchema,
    NotificationTemplateCreateSchema,
    NotificationTemplateListResponseSchema,
    NotificationTemplateReadSchema,
    NotificationTemplateUpdateSchema,
)
from app.services.notification_service import (
    MessageService,
    NotificationService,
    NotificationTemplateService,
)
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# --- Service factories -----------------------------------------------------

def get_template_service(db: Annotated[Session, Depends(get_db)]) -> NotificationTemplateService:
    return NotificationTemplateService(db)


def get_notification_service(db: Annotated[Session, Depends(get_db)]) -> NotificationService:
    return NotificationService(db)


def get_message_service(db: Annotated[Session, Depends(get_db)]) -> MessageService:
    return MessageService(db)


# ============================================================
# TEMPLATES
# ============================================================


@router.get(
    "/templates",
    response_model=NotificationTemplateListResponseSchema,
    summary="List notification templates",
)
def list_templates(
    _: Annotated[User, Depends(require_permission("NOTIFICATION_READ"))],
    service: Annotated[NotificationTemplateService, Depends(get_template_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    channel: Optional[str] = Query(None, description="IN_APP, EMAIL, SMS, WHATSAPP."),
    search: Optional[str] = Query(None),
):
    items, total = service.list_templates(skip=skip, limit=limit, channel=channel, search=search)
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Notification templates fetched successfully.",
    )


@router.post(
    "/templates",
    response_model=NotificationTemplateActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a notification template",
)
def create_template(
    payload: NotificationTemplateCreateSchema,
    _: Annotated[User, Depends(require_permission("NOTIFICATION_MANAGE"))],
    service: Annotated[NotificationTemplateService, Depends(get_template_service)],
):
    t = service.create(payload)
    return {"success": True, "message": "Template created.", "template": t}


@router.get(
    "/templates/{template_id}",
    response_model=NotificationTemplateReadSchema,
    summary="Get a notification template",
)
def get_template(
    template_id: int,
    _: Annotated[User, Depends(require_permission("NOTIFICATION_READ"))],
    service: Annotated[NotificationTemplateService, Depends(get_template_service)],
):
    return service.get(template_id)


@router.put(
    "/templates/{template_id}",
    response_model=NotificationTemplateActionResponseSchema,
    summary="Update a notification template",
)
def update_template(
    template_id: int,
    payload: NotificationTemplateUpdateSchema,
    _: Annotated[User, Depends(require_permission("NOTIFICATION_MANAGE"))],
    service: Annotated[NotificationTemplateService, Depends(get_template_service)],
):
    t = service.update(template_id, payload)
    return {"success": True, "message": "Template updated.", "template": t}


@router.delete(
    "/templates/{template_id}",
    summary="Soft-delete a notification template",
)
def soft_delete_template(
    template_id: int,
    _: Annotated[User, Depends(require_permission("NOTIFICATION_MANAGE"))],
    service: Annotated[NotificationTemplateService, Depends(get_template_service)],
):
    t = service.soft_delete(template_id)
    return {"success": True, "message": "Template removed.", "template_id": t.id}


# ============================================================
# NOTIFICATIONS
# ============================================================


@router.get(
    "/",
    response_model=NotificationListResponseSchema,
    summary="List notifications",
)
def list_notifications(
    _: Annotated[User, Depends(require_permission("NOTIFICATION_READ"))],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    patient_id: Optional[int] = Query(None),
    channel: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    items, total = service.list_notifications(
        skip=skip, limit=limit,
        user_id=user_id, patient_id=patient_id,
        channel=channel, status=status_filter,
    )
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Notifications fetched successfully.",
    )


@router.get(
    "/{notification_id}",
    response_model=NotificationReadSchema,
    summary="Get a notification",
)
def get_notification(
    notification_id: int,
    _: Annotated[User, Depends(require_permission("NOTIFICATION_READ"))],
    service: Annotated[NotificationService, Depends(get_notification_service)],
):
    return service.get(notification_id)


@router.post(
    "/dispatch",
    response_model=NotificationActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Dispatch a notification using a template",
)
def dispatch_from_template(
    payload: NotificationDispatchSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("NOTIFICATION_DISPATCH"))],
    service: Annotated[NotificationService, Depends(get_notification_service)],
):
    n = service.dispatch_from_template(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": f"Notification dispatched ({n.status}).",
        "notification": n,
    }


@router.post(
    "/dispatch-ad-hoc",
    response_model=NotificationActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Send an ad-hoc notification (no template)",
)
def dispatch_ad_hoc(
    payload: NotificationAdHocDispatchSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("NOTIFICATION_DISPATCH"))],
    service: Annotated[NotificationService, Depends(get_notification_service)],
):
    n = service.dispatch_ad_hoc(payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": f"Notification dispatched ({n.status}).",
        "notification": n,
    }


@router.post(
    "/retry-failed",
    response_model=NotificationRetryResponseSchema,
    summary="Bulk-retry FAILED notifications",
)
def retry_failed(
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("NOTIFICATION_DISPATCH"))],
    service: Annotated[NotificationService, Depends(get_notification_service)],
    limit: int = Query(50, ge=1, le=500),
):
    summary = service.retry_failed(limit=limit, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Retry attempted.",
        **summary,
    }


@router.post(
    "/{notification_id}/mark-read",
    response_model=NotificationActionResponseSchema,
    summary="Mark an in-app notification as READ",
)
def mark_read(
    notification_id: int,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("NOTIFICATION_READ"))],
    service: Annotated[NotificationService, Depends(get_notification_service)],
):
    n = service.mark_read(notification_id, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Notification marked READ.",
        "notification": n,
    }


# ============================================================
# DIRECT MESSAGES
# ============================================================


@router.get(
    "/messages/inbox",
    response_model=MessageListResponseSchema,
    summary="My inbox",
)
def message_inbox(
    actor: CurrentActiveUser,
    service: Annotated[MessageService, Depends(get_message_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    items, total = service.list_inbox(actor.id, skip=skip, limit=limit)
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Inbox fetched successfully.",
    )


@router.get(
    "/messages/sent",
    response_model=MessageListResponseSchema,
    summary="My sent messages",
)
def message_sent(
    actor: CurrentActiveUser,
    service: Annotated[MessageService, Depends(get_message_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    items, total = service.list_sent(actor.id, skip=skip, limit=limit)
    return paginate_response(
        items=items,
        total=total, skip=skip, limit=limit,
        message="Sent messages fetched successfully.",
    )


@router.post(
    "/messages",
    response_model=MessageActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Send a direct message",
)
def send_message(
    payload: MessageCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("MESSAGE_SEND"))],
    service: Annotated[MessageService, Depends(get_message_service)],
):
    m = service.send(actor.id, payload)
    return {"success": True, "message": "Message sent.", "direct_message": m}


@router.post(
    "/messages/{message_id}/read",
    response_model=MessageActionResponseSchema,
    summary="Mark a direct message as read",
)
def mark_message_read(
    message_id: int,
    actor: CurrentActiveUser,
    service: Annotated[MessageService, Depends(get_message_service)],
):
    m = service.mark_read(message_id)
    return {"success": True, "message": "Message marked read.", "direct_message": m}


@router.get(
    "/messages/{message_id}",
    response_model=MessageReadSchema,
    summary="Get a direct message",
)
def get_message(
    message_id: int,
    actor: CurrentActiveUser,
    service: Annotated[MessageService, Depends(get_message_service)],
):
    return service.get(message_id)
