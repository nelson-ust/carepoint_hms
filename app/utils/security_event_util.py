# app/utils/security_event_util.py
from __future__ import annotations

"""
Helpers for recording structured security events to the SecurityEvent table.

Purpose
-------
Use these helpers from services and middleware to capture security-relevant
state changes (login success/failure, account lock, role assignment, 2FA
challenges, password resets, etc.).

The helper writes (via `db.add` and `db.flush`) but does not commit.
Callers are responsible for committing inside their own transaction.
"""

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.all_models import SecurityEvent


VALID_SEVERITIES = {"INFO", "WARNING", "CRITICAL"}


def record_security_event(
    db: Session,
    *,
    event_type: str,
    user_id: Optional[int] = None,
    severity: str = "INFO",
    event_detail: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    event_metadata: Optional[dict[str, Any]] = None,
) -> SecurityEvent:
    """
    Persist a SecurityEvent row.

    Args:
        db: Active SQLAlchemy session (caller commits).
        event_type: Stable event identifier, e.g. LOGIN_SUCCESS, LOGIN_FAILURE.
        user_id: Optional subject user.
        severity: One of INFO, WARNING, CRITICAL.
        event_detail: Free-text detail.
        ip_address: Optional source IP.
        user_agent: Optional user agent.
        event_metadata: Optional structured metadata (JSON-serializable).

    Returns:
        SecurityEvent: The persisted event with id populated.
    """
    safe_severity = severity.strip().upper() if severity else "INFO"
    if safe_severity not in VALID_SEVERITIES:
        safe_severity = "INFO"

    safe_metadata: Optional[dict[str, Any]] = None
    if event_metadata is not None:
        safe_metadata = {}
        for key, value in event_metadata.items():
            try:
                # SQLAlchemy/JSON column needs serializable values.
                _ = repr(value)
                safe_metadata[str(key)] = value
            except Exception:
                safe_metadata[str(key)] = str(value)

    event = SecurityEvent(
        user_id=user_id,
        event_type=event_type.strip().upper(),
        event_detail=event_detail,
        ip_address=ip_address,
        user_agent=user_agent,
        event_metadata=safe_metadata,
        severity=safe_severity,
    )
    db.add(event)
    db.flush()
    return event
