# app/api/v1/endpoints/whatsapp_webhook_routes.py
"""Public Meta WhatsApp Business Platform webhook endpoint.

Two operations on the same path, per Meta's spec:

* ``GET /whatsapp/webhook``  — the subscription verification handshake. Meta
  sends ``hub.mode=subscribe``, ``hub.verify_token`` and ``hub.challenge``;
  we echo the challenge back as plain text with 200 when the token matches.
* ``POST /whatsapp/webhook`` — event delivery. We validate the
  ``X-Hub-Signature-256`` header against the app secret, then log + route the
  payload. We always answer 200 for authentic deliveries so Meta does not
  retry for 7 days on a transient processing error.

This endpoint is intentionally unauthenticated (Meta calls it) and tenant-less;
the tenant is resolved from each payload's ``phone_number_id``.
"""
from __future__ import annotations

import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_master_db
from app.core.logger import get_logger
from app.services.whatsapp_service import (
    WhatsAppWebhookService,
    verify_signature,
    verify_subscription,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Webhook"])


@router.get("/webhook", include_in_schema=True)
def verify_webhook(
    db: Annotated[Session, Depends(get_master_db)],
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """Meta subscription verification handshake."""
    service = WhatsAppWebhookService(db)
    challenge = verify_subscription(
        hub_mode, hub_verify_token, hub_challenge, service.acceptable_verify_tokens()
    )
    if challenge is None:
        logger.warning("WhatsApp webhook verification failed (mode=%s)", hub_mode)
        return PlainTextResponse("Verification failed", status_code=403)
    # Meta expects the raw challenge echoed back as text/plain.
    return PlainTextResponse(str(challenge), status_code=200)


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_master_db)],
    x_hub_signature_256: Annotated[Optional[str], Header()] = None,
):
    """Receive and process a webhook delivery."""
    raw_body = await request.body()

    if settings.WHATSAPP_VERIFY_SIGNATURE:
        app_secret = settings.WHATSAPP_APP_SECRET.get_secret_value() if settings.WHATSAPP_APP_SECRET else None
        if not verify_signature(raw_body, x_hub_signature_256, app_secret):
            logger.warning("WhatsApp webhook rejected: invalid X-Hub-Signature-256")
            return JSONResponse({"status": "invalid_signature"}, status_code=403)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        logger.warning("WhatsApp webhook: unparseable JSON body")
        # Authentic but malformed — ack so Meta stops retrying.
        return JSONResponse({"status": "ignored"}, status_code=200)

    try:
        result = WhatsAppWebhookService(db).handle_event(raw_body, payload)
    except Exception:
        logger.exception("WhatsApp webhook processing crashed")
        # Never surface a 500 to Meta (would trigger 7 days of retries).
        return JSONResponse({"status": "error_logged"}, status_code=200)

    return JSONResponse({"status": "ok", **result}, status_code=200)
