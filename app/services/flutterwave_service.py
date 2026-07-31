# app/services/flutterwave_service.py
"""
Flutterwave gateway client for SaaS subscription checkout.

Mirrors the structure of :class:`app.services.paystack_service.PaystackService`
but targets Flutterwave's Standard v3 API:

* ``initialize_payment`` -> POST /payments   (returns a hosted checkout link)
* ``verify_transaction``  -> GET  /transactions/{id}/verify
* ``verify_transaction_by_ref`` -> GET /transactions/verify_by_reference
* ``verify_webhook_signature`` -> compares the ``verif-hash`` header

The service is intentionally synchronous-friendly (uses ``httpx`` in a short
-lived client per call) so it can be driven from FastAPI sync endpoints via
``asyncio.run`` helpers, matching how the existing routes call Paystack.
"""
from __future__ import annotations

import hmac
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.utils.helpers import generate_uuid_str


class FlutterwaveService:
    """Thin wrapper over the Flutterwave v3 REST API."""

    def __init__(self) -> None:
        self.secret_key = (
            settings.FLUTTERWAVE_SECRET_KEY.get_secret_value()
            if settings.FLUTTERWAVE_SECRET_KEY
            else None
        )
        self.base_url = (settings.FLUTTERWAVE_BASE_URL or "https://api.flutterwave.com/v3").rstrip("/")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @property
    def is_configured(self) -> bool:
        return bool(self.secret_key)

    def _headers(self) -> Dict[str, str]:
        if not self.secret_key:
            raise BadRequestError(
                message="Flutterwave is not configured. Set FLUTTERWAVE_SECRET_KEY."
            )
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def new_reference(prefix: str = "CPSUB") -> str:
        """Generate a unique tx_ref for a subscription checkout."""
        return f"{prefix}-{generate_uuid_str()[:14].upper()}"

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------
    async def initialize_payment(
        self,
        *,
        amount: Decimal | float,
        currency: str,
        tx_ref: str,
        customer_email: str,
        redirect_url: str,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        title: str = "CarePoint HMS Subscription",
    ) -> Dict[str, Any]:
        """
        Create a Flutterwave Standard payment and return the hosted checkout
        payload. Raises BadRequestError with the gateway message on failure.

        Returns the ``data`` object which contains ``link`` (the checkout URL).
        """
        payload: Dict[str, Any] = {
            "tx_ref": tx_ref,
            "amount": str(Decimal(str(amount))),
            "currency": (currency or "NGN").upper(),
            "redirect_url": redirect_url,
            "payment_options": "card,banktransfer,ussd,account",
            "customer": {
                "email": customer_email,
                "name": customer_name or customer_email,
                "phonenumber": customer_phone or "",
            },
            "customizations": {
                "title": title,
                "description": "Hospital subscription payment",
            },
            "meta": meta or {},
        }

        response = await _request("POST", f"{self.base_url}/payments", json=payload, headers=self._headers())
        body = _safe_json(response)
        if response.status_code not in (200, 201) or body.get("status") != "success":
            raise BadRequestError(
                message=f"Flutterwave checkout failed: {body.get('message', 'Unknown error')}"
            )
        return body.get("data", {})

    async def verify_transaction(self, transaction_id: str | int) -> Dict[str, Any]:
        """Verify a completed transaction by Flutterwave's numeric id."""
        response = await _request(
            "GET", f"{self.base_url}/transactions/{transaction_id}/verify", headers=self._headers()
        )
        body = _safe_json(response)
        if response.status_code != 200 or body.get("status") != "success":
            raise BadRequestError(
                message=f"Flutterwave verification failed: {body.get('message', 'Unknown error')}"
            )
        return body.get("data", {})

    async def verify_transaction_by_ref(self, tx_ref: str) -> Dict[str, Any]:
        """Verify a transaction by our own tx_ref (used from the callback)."""
        response = await _request(
            "GET",
            f"{self.base_url}/transactions/verify_by_reference",
            params={"tx_ref": tx_ref},
            headers=self._headers(),
        )
        body = _safe_json(response)
        if response.status_code != 200 or body.get("status") != "success":
            raise BadRequestError(
                message=f"Flutterwave verification failed: {body.get('message', 'Unknown error')}"
            )
        return body.get("data", {})

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------
    def verify_webhook_signature(self, signature: Optional[str]) -> bool:
        """
        Flutterwave signs webhooks by echoing the dashboard "secret hash" in
        the ``verif-hash`` header. We compare it (constant-time) to the
        configured hash.
        """
        configured = (
            settings.FLUTTERWAVE_WEBHOOK_HASH.get_secret_value()
            if settings.FLUTTERWAVE_WEBHOOK_HASH
            else None
        )
        if not configured or not signature:
            return False
        return hmac.compare_digest(str(configured), str(signature))


async def _request(method: str, url: str, **kwargs) -> httpx.Response:
    """
    Perform an httpx request, converting transport-level failures (network
    unreachable, proxy blocks, timeouts) into a clean BadRequestError so the
    API returns a helpful message instead of a raw 500.
    """
    try:
        async with httpx.AsyncClient() as client:
            return await client.request(method, url, timeout=30.0, **kwargs)
    except (httpx.ProxyError, httpx.ConnectError, httpx.ConnectTimeout) as exc:
        raise BadRequestError(
            message=(
                "Could not reach the Flutterwave payment gateway. Please try "
                "again, or use manual bank payment."
            )
        ) from exc
    except httpx.HTTPError as exc:
        raise BadRequestError(
            message=f"Payment gateway error: {type(exc).__name__}."
        ) from exc


def _safe_json(response: httpx.Response) -> Dict[str, Any]:
    try:
        return response.json()
    except Exception:
        return {"status": "error", "message": response.text[:200]}
