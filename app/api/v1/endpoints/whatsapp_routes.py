# app/api/v1/endpoints/whatsapp_routes.py
"""Authenticated, tenant-scoped WhatsApp management: number configuration,
outbound sending, and inbox reads."""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db, get_master_db
from app.core.dependencies import CurrentActiveUser
from app.core.multitenancy import get_current_tenant_id
from app.dependencies.role import require_permission
from app.models.all_models import (
    User,
    WhatsAppConversation,
    WhatsAppMessage,
)
from app.schemas.whatsapp_schemas import (
    SendTemplateMessageSchema,
    SendTextMessageSchema,
    WhatsAppConfigReadSchema,
    WhatsAppConfigUpsertSchema,
    WhatsAppConversationReadSchema,
    WhatsAppMessageReadSchema,
)
from app.services.whatsapp_service import (
    WhatsAppConfigService,
    WhatsAppOutboundService,
)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


def _tenant_id() -> int:
    tid = get_current_tenant_id()
    if tid is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No tenant context.")
    return tid


# --------------------------------------------------------------------------
# Configuration (number -> tenant mapping + credentials)
# --------------------------------------------------------------------------

@router.get("/config", response_model=list[WhatsAppConfigReadSchema],
            summary="List this tenant's WhatsApp number configurations")
def list_config(
    _: Annotated[User, Depends(require_permission("WHATSAPP_MANAGE"))],
    master_db: Annotated[Session, Depends(get_master_db)],
):
    service = WhatsAppConfigService(master_db)
    return [service.to_dict(c) for c in service.list_for_tenant(_tenant_id())]


@router.put("/config", response_model=WhatsAppConfigReadSchema,
            summary="Create or update a WhatsApp number configuration")
def upsert_config(
    payload: WhatsAppConfigUpsertSchema,
    _: Annotated[User, Depends(require_permission("WHATSAPP_MANAGE"))],
    master_db: Annotated[Session, Depends(get_master_db)],
):
    service = WhatsAppConfigService(master_db)
    cfg = service.upsert(_tenant_id(), payload.model_dump(exclude_unset=True))
    return service.to_dict(cfg)


# --------------------------------------------------------------------------
# Outbound send
# --------------------------------------------------------------------------

@router.post("/messages", response_model=WhatsAppMessageReadSchema,
             summary="Send a WhatsApp text message")
def send_text_message(
    payload: SendTextMessageSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("WHATSAPP_SEND"))],
    db: Annotated[Session, Depends(get_db)],
    master_db: Annotated[Session, Depends(get_master_db)],
):
    service = WhatsAppOutboundService(db, master_db, _tenant_id())
    return service.send_text(payload.to, payload.body,
                             sender_user_id=getattr(actor, "id", None),
                             preview_url=payload.preview_url)


@router.post("/messages/template", response_model=WhatsAppMessageReadSchema,
             summary="Send a WhatsApp template message")
def send_template_message(
    payload: SendTemplateMessageSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("WHATSAPP_SEND"))],
    db: Annotated[Session, Depends(get_db)],
    master_db: Annotated[Session, Depends(get_master_db)],
):
    service = WhatsAppOutboundService(db, master_db, _tenant_id())
    return service.send_template(payload.to, payload.template_name,
                                 language_code=payload.language_code,
                                 components=payload.components,
                                 sender_user_id=getattr(actor, "id", None))


# --------------------------------------------------------------------------
# Inbox reads
# --------------------------------------------------------------------------

@router.get("/conversations", response_model=list[WhatsAppConversationReadSchema],
            summary="List WhatsApp conversations")
def list_conversations(
    _: Annotated[User, Depends(require_permission("WHATSAPP_READ"))],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return (db.query(WhatsAppConversation)
            .filter(WhatsAppConversation.is_deleted.is_(False))
            .order_by(WhatsAppConversation.last_message_at.desc().nullslast())
            .offset(offset).limit(limit).all())


@router.get("/conversations/{conversation_id}/messages",
            response_model=list[WhatsAppMessageReadSchema],
            summary="List messages in a conversation")
def list_messages(
    conversation_id: int,
    _: Annotated[User, Depends(require_permission("WHATSAPP_READ"))],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conversation = (db.query(WhatsAppConversation)
                    .filter(WhatsAppConversation.id == conversation_id,
                            WhatsAppConversation.is_deleted.is_(False)).first())
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Conversation not found.")
    return (db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.conversation_id == conversation_id,
                    WhatsAppMessage.is_deleted.is_(False))
            .order_by(WhatsAppMessage.id.asc())
            .offset(offset).limit(limit).all())
