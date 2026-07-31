# app/services/paystack_service.py
from __future__ import annotations

import hmac
import hashlib
import json
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import PaystackTransactionStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import PaystackTransaction, Patient, MembershipCard
from app.utils.helpers import generate_uuid_str


class PaystackService:
    BASE_URL = "https://api.paystack.co"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.secret_key = settings.PAYSTACK_SECRET_KEY.get_secret_value() if settings.PAYSTACK_SECRET_KEY else None

    def _get_headers(self) -> Dict[str, str]:
        if not self.secret_key:
            raise BadRequestError("Paystack is not configured. Missing Secret Key.")
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    async def initialize_transaction(
        self, patient: Patient, card: MembershipCard, amount: Decimal
    ) -> PaystackTransaction:
        """
        Initialize a Paystack transaction and return the authorization URL.
        """
        if not patient.email:
            raise BadRequestError("Patient must have an email address to use Paystack.")

        # Paystack amount is in kobo (NGN * 100)
        amount_kobo = int(amount * 100)
        reference = f"PS-{generate_uuid_str()[:12].upper()}"

        payload = {
            "email": patient.email,
            "amount": amount_kobo,
            "reference": reference,
            "metadata": {
                "patient_id": patient.id,
                "membership_card_id": card.id,
                "type": "membership_card_funding"
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/transaction/initialize",
                json=payload,
                headers=self._get_headers(),
                timeout=30.0
            )

        if response.status_code != 200:
            error_data = response.json()
            raise BadRequestError(f"Paystack initialization failed: {error_data.get('message', 'Unknown error')}")

        data = response.json()["data"]

        tx = PaystackTransaction(
            patient_id=patient.id,
            membership_card_id=card.id,
            reference=reference,
            access_code=data["access_code"],
            authorization_url=data["authorization_url"],
            amount=amount,
            currency="NGN",
            status=PaystackTransactionStatus.PENDING
        )
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    async def initialize_checkout(
        self,
        *,
        email: str,
        amount: Decimal | float,
        reference: str,
        callback_url: str,
        currency: str = "NGN",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Initialize a generic Paystack hosted checkout (used for SaaS
        subscription payments) and return the raw ``data`` object which contains
        ``authorization_url``, ``access_code`` and ``reference``.

        Unlike :meth:`initialize_transaction` (which is tied to a patient's
        membership card), this does not persist a domain row — subscription
        payments are recorded by the billing service on verification.
        """
        amount_minor = int(Decimal(str(amount)) * 100)  # Paystack expects the minor unit (kobo)
        base_url = (getattr(settings, "PAYSTACK_BASE_URL", None) or self.BASE_URL).rstrip("/")
        payload = {
            "email": email,
            "amount": amount_minor,
            "reference": reference,
            "currency": (currency or "NGN").upper(),
            "callback_url": callback_url,
            "metadata": metadata or {},
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/transaction/initialize",
                json=payload,
                headers=self._get_headers(),
                timeout=30.0,
            )
        if response.status_code != 200:
            try:
                error_data = response.json()
            except Exception:
                error_data = {}
            raise BadRequestError(
                f"Paystack initialization failed: {error_data.get('message', 'Unknown error')}"
            )
        return response.json()["data"]

    async def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Verify a transaction with Paystack.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/transaction/verify/{reference}",
                headers=self._get_headers(),
                timeout=30.0
            )

        if response.status_code != 200:
            error_data = response.json()
            raise BadRequestError(f"Paystack verification failed: {error_data.get('message', 'Unknown error')}")

        return response.json()["data"]

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify that a webhook request came from Paystack.
        """
        webhook_secret = settings.PAYSTACK_WEBHOOK_SECRET.get_secret_value() if settings.PAYSTACK_WEBHOOK_SECRET else None
        if not webhook_secret:
            # If not configured, we might want to log this but for security we should probably fail
            return False

        hash_value = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()

        return hmac.compare_digest(hash_value, signature)
