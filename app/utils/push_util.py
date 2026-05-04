"""
Push-notification helper.

Provides a thin :func:`send_push` adapter that delegates to a configurable
provider (Firebase Cloud Messaging by default). The function is intentionally
forgiving: when no provider is configured it logs and returns ``False`` so
callers can record a delivery failure instead of crashing the request.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

try:
    from app.core.config import settings
except Exception:  # pragma: no cover
    settings = None


logger = logging.getLogger(__name__)


def _provider() -> str:
    return (getattr(settings, "PUSH_PROVIDER", None) or "FCM").upper() if settings else "FCM"


def _fcm_server_key() -> Optional[str]:
    return getattr(settings, "FCM_SERVER_KEY", None) if settings else None


def send_push(
    *,
    device_token: str,
    title: Optional[str],
    body: str,
    data: Optional[dict[str, Any]] = None,
    timeout: float = 10.0,
) -> bool:
    """
    Deliver a push payload to a single device token.

    Returns ``True`` on a 2xx response from the provider, ``False`` otherwise.
    No exceptions are raised for delivery failures; callers should consult
    the return value and the log.
    """
    if not device_token:
        return False

    provider = _provider()

    if provider == "FCM":
        server_key = _fcm_server_key()
        if not server_key:
            logger.warning("send_push: FCM_SERVER_KEY not configured; dropping payload.")
            return False

        payload = {
            "to": device_token,
            "notification": {"title": title or "", "body": body},
            "data": data or {},
        }
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    "https://fcm.googleapis.com/fcm/send",
                    headers={
                        "Authorization": f"key={server_key}",
                        "Content-Type": "application/json",
                    },
                    content=json.dumps(payload),
                )
            if resp.status_code // 100 == 2:
                return True
            logger.warning(
                "send_push: FCM responded %s: %s", resp.status_code, resp.text[:200]
            )
            return False
        except Exception as exc:
            logger.exception("send_push: FCM delivery raised: %s", exc)
            return False

    logger.warning("send_push: unsupported PUSH_PROVIDER=%s", provider)
    return False
