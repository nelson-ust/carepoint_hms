# utils/otp_utils.py
from __future__ import annotations

"""
OTP generation and validation helpers.

Purpose
-------
This module centralizes one-time password generation, hashing, validation,
expiry handling, and challenge-payload preparation for Carepoint HMS.

Typical usage
-------------
- generate an OTP for login or verification
- hash the OTP before storing it in the database
- compare a submitted OTP against the stored hash
- enforce expiry, resend intervals, and max attempts
- build a normalized payload for creating TwoFactorChallenge records
"""

import hashlib
import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

try:
    from app.core.config import settings
except Exception:  # pragma: no cover
    settings = None


# Default configuration values.
OTP_LENGTH = int(getattr(settings, "OTP_LENGTH", 6)) if settings else 6
OTP_EXPIRE_MINUTES = int(getattr(settings, "OTP_EXPIRE_MINUTES", 10)) if settings else 10
OTP_MAX_ATTEMPTS = int(getattr(settings, "OTP_MAX_ATTEMPTS", 5)) if settings else 5
OTP_RESEND_INTERVAL_SECONDS = (
    int(getattr(settings, "OTP_RESEND_INTERVAL_SECONDS", 60)) if settings else 60
)


def utc_now() -> datetime:
    """
    Return the current UTC datetime.
    """
    return datetime.now(timezone.utc)


def _ensure_timezone_aware(value: datetime) -> datetime:
    """
    Ensure a datetime is timezone-aware.

    Naive datetimes are treated as UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def generate_otp(
    length: int = OTP_LENGTH,
    *,
    digits_only: bool = True,
) -> str:
    """
    Generate a one-time password.

    Args:
        length: OTP length.
        digits_only: When True, generate a numeric OTP only. When False,
            generate an uppercase alphanumeric OTP.

    Returns:
        str: Generated OTP.

    Raises:
        ValueError: If length is invalid.
    """
    if length < 4:
        raise ValueError("OTP length must be at least 4.")
    if length > 12:
        raise ValueError("OTP length must not exceed 12.")

    alphabet = string.digits if digits_only else (string.ascii_uppercase + string.digits)
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_otp(otp: str, *, salt: Optional[str] = None) -> str:
    """
    Hash an OTP using SHA-256.

    Args:
        otp: Plain OTP value.
        salt: Optional salt string. If supplied, it is prepended before hashing.

    Returns:
        str: Hex-encoded SHA-256 digest.

    Raises:
        ValueError: If OTP is empty.
    """
    if not otp or not otp.strip():
        raise ValueError("OTP cannot be empty.")

    normalized = otp.strip()
    raw_value = f"{salt or ''}{normalized}".encode("utf-8")
    return hashlib.sha256(raw_value).hexdigest()


def verify_otp(
    plain_otp: str,
    hashed_otp: str,
    *,
    salt: Optional[str] = None,
) -> bool:
    """
    Verify a plain OTP against a stored hash.

    Uses constant-time comparison to reduce timing attack leakage.

    Args:
        plain_otp: User-supplied OTP.
        hashed_otp: Stored hashed OTP.
        salt: Optional salt that was used during hashing.

    Returns:
        bool: True when the OTP matches.
    """
    if not plain_otp or not hashed_otp:
        return False

    computed_hash = hash_otp(plain_otp, salt=salt)
    return hmac.compare_digest(computed_hash, hashed_otp)


def get_otp_expiry(minutes: int = OTP_EXPIRE_MINUTES) -> datetime:
    """
    Return the UTC expiry time for an OTP.

    Args:
        minutes: Validity duration in minutes.

    Returns:
        datetime: Expiry timestamp in UTC.
    """
    if minutes <= 0:
        raise ValueError("OTP expiry minutes must be greater than zero.")
    return utc_now() + timedelta(minutes=minutes)


def get_resend_available_at(seconds: int = OTP_RESEND_INTERVAL_SECONDS) -> datetime:
    """
    Return the UTC time when OTP resend becomes allowed again.

    Args:
        seconds: Resend wait period.

    Returns:
        datetime: UTC timestamp.
    """
    if seconds < 0:
        raise ValueError("Resend interval seconds cannot be negative.")
    return utc_now() + timedelta(seconds=seconds)


def is_expired(expires_at: Optional[datetime]) -> bool:
    """
    Check whether an expiry timestamp has passed.

    Args:
        expires_at: Expiry timestamp.

    Returns:
        bool: True if expired or missing.
    """
    if expires_at is None:
        return True

    expires_at = _ensure_timezone_aware(expires_at)
    return utc_now() >= expires_at


def can_resend(*, last_sent_at: Optional[datetime], interval_seconds: int = OTP_RESEND_INTERVAL_SECONDS) -> bool:
    """
    Check whether an OTP can be resent.

    Args:
        last_sent_at: Timestamp of the previous OTP dispatch.
        interval_seconds: Minimum wait time before resend.

    Returns:
        bool: True if resend is allowed.
    """
    if last_sent_at is None:
        return True

    last_sent_at = _ensure_timezone_aware(last_sent_at)
    return utc_now() >= (last_sent_at + timedelta(seconds=interval_seconds))


def has_attempts_remaining(*, attempt_count: int, max_attempts: int = OTP_MAX_ATTEMPTS) -> bool:
    """
    Check whether an OTP challenge still has attempts remaining.

    Args:
        attempt_count: Current failed attempt count.
        max_attempts: Maximum allowed attempts.

    Returns:
        bool: True if more attempts are allowed.
    """
    if attempt_count < 0:
        attempt_count = 0
    return attempt_count < max_attempts


def increment_attempt_count(attempt_count: int) -> int:
    """
    Increment and return the attempt count safely.
    """
    return max(0, attempt_count) + 1


def build_otp_challenge_payload(
    *,
    user_id: int,
    challenge_type: str,
    purpose: str,
    destination: Optional[str] = None,
    otp_length: int = OTP_LENGTH,
    otp_expire_minutes: int = OTP_EXPIRE_MINUTES,
    max_attempts: int = OTP_MAX_ATTEMPTS,
    digits_only: bool = True,
    salt: Optional[str] = None,
    extra_metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Build a normalized payload for creating a TwoFactorChallenge record.

    Important:
    ----------
    `plain_code` should be used only for delivery to the user and should not be
    persisted in the database.

    Returns:
        dict[str, Any]: Challenge payload.
    """
    plain_code = generate_otp(length=otp_length, digits_only=digits_only)
    expires_at = get_otp_expiry(minutes=otp_expire_minutes)

    return {
        "user_id": user_id,
        "challenge_type": challenge_type,
        "purpose": purpose,
        "destination": destination,
        "plain_code": plain_code,
        "code_hash": hash_otp(plain_code, salt=salt),
        "attempt_count": 0,
        "max_attempts": max_attempts,
        "is_verified": False,
        "verified_at": None,
        "expires_at": expires_at,
        "last_sent_at": utc_now(),
        "extra_metadata": extra_metadata or {},
    }


def build_successful_verification_update() -> dict[str, Any]:
    """
    Build a normalized update payload for a successfully verified OTP challenge.
    """
    return {
        "is_verified": True,
        "verified_at": utc_now(),
    }


def build_failed_attempt_update(current_attempt_count: int) -> dict[str, Any]:
    """
    Build a normalized update payload after a failed OTP attempt.
    """
    return {
        "attempt_count": increment_attempt_count(current_attempt_count),
    }


def validate_otp_submission(
    *,
    submitted_otp: str,
    stored_hash: str,
    expires_at: datetime,
    attempt_count: int,
    max_attempts: int = OTP_MAX_ATTEMPTS,
    salt: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Validate an OTP submission and return a result tuple.

    Returns:
        tuple[bool, str]:
            (is_valid, message)

    Possible messages:
        - "OTP verified successfully."
        - "OTP has expired."
        - "Maximum OTP attempts exceeded."
        - "Invalid OTP."
    """
    if not has_attempts_remaining(attempt_count=attempt_count, max_attempts=max_attempts):
        return False, "Maximum OTP attempts exceeded."

    if is_expired(expires_at):
        return False, "OTP has expired."

    if not verify_otp(submitted_otp, stored_hash, salt=salt):
        return False, "Invalid OTP."

    return True, "OTP verified successfully."