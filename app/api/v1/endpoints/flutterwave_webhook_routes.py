"""
Flutterwave webhook receiver for subscription payments.

Flutterwave POSTs a ``charge.completed`` event and echoes the dashboard secret
hash in the ``verif-hash`` header. We verify the hash, then — for successful
charges carrying our subscription metadata — record the gateway payment
idempotently (the browser callback may have already recorded it).
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.services.flutterwave_service import FlutterwaveService
from app.services.subscription_billing_service import SubscriptionBillingService

router = APIRouter(prefix="/flutterwave", tags=["Flutterwave Webhook"])


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def flutterwave_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_master_db)],
    verif_hash: Annotated[Optional[str], Header(alias="verif-hash")] = None,
):
    flw = FlutterwaveService()
    if not flw.verify_webhook_signature(verif_hash):
        # 200 so Flutterwave stops retrying, but do nothing.
        return JSONResponse({"status": "ignored", "reason": "invalid signature"}, status_code=200)

    body = await request.json()
    event = body.get("event")
    data = body.get("data") or {}

    if event != "charge.completed" or str(data.get("status", "")).lower() != "successful":
        return JSONResponse({"status": "ignored"}, status_code=200)

    meta = data.get("meta") or {}
    if str(meta.get("purpose")) != "subscription":
        return JSONResponse({"status": "ignored", "reason": "not a subscription charge"}, status_code=200)

    invoice_id = meta.get("invoice_id")
    if not invoice_id:
        return JSONResponse({"status": "ignored", "reason": "no invoice_id"}, status_code=200)

    # Re-verify with Flutterwave before trusting the amount.
    try:
        verified = await flw.verify_transaction(data.get("id"))
    except Exception:
        verified = data

    service = SubscriptionBillingService(db)
    service.record_gateway_payment(
        int(invoice_id),
        amount=verified.get("amount", data.get("amount", 0)),
        provider="FLUTTERWAVE",
        transaction_reference=str(verified.get("tx_ref") or data.get("tx_ref") or data.get("id")),
        raw_payload=verified,
    )
    return JSONResponse({"status": "processed"}, status_code=200)
