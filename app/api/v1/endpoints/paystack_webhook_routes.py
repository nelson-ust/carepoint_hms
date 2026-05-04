# app/api/v1/endpoints/paystack_webhook_routes.py
from __future__ import annotations

import json
from typing import Annotated
from fastapi import APIRouter, Depends, Request, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.enums import PaystackTransactionStatus
from app.services.paystack_service import PaystackService
from app.services.membership_card_service import MembershipCardService
from app.models.all_models import PaystackTransaction


router = APIRouter(prefix="/paystack", tags=["Paystack Webhook"])


@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    x_paystack_signature: Annotated[str, Header()],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Handle Paystack webhook events.
    """
    payload = await request.body()
    service = PaystackService(db)
    
    if not service.verify_webhook_signature(payload, x_paystack_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Paystack signature."
        )

    event_data = json.loads(payload)
    event_type = event_data.get("event")

    if event_type == "charge.success":
        data = event_data["data"]
        reference = data["reference"]
        
        # Find the transaction in our DB
        tx = db.query(PaystackTransaction).filter(PaystackTransaction.reference == reference).first()
        if not tx:
            # We might not have initiated this, or it's from another system
            return {"status": "ignored", "reason": "transaction_not_found"}

        if tx.status == PaystackTransactionStatus.SUCCESS:
            return {"status": "success", "reason": "already_processed"}

        # Update transaction status
        tx.status = PaystackTransactionStatus.SUCCESS
        tx.paid_at = data.get("paid_at")
        tx.metadata_json = data.get("metadata")
        db.add(tx)
        db.commit()

        # Credit the membership card
        card_service = MembershipCardService(db)
        card_service.credit_via_paystack(tx)
        
        return {"status": "success"}

    return {"status": "ignored", "event": event_type}
