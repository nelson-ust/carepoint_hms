# app/tests/unit/test_auth.py
from __future__ import annotations

"""
Unit tests for the security primitives in `app.core.security` and the
supporting OTP/password utilities.

These tests do not need a database. They focus on the highest-risk pure
functions in the auth stack:
- JWT round-trip
- Password hashing / verification
- Password strength validation
- OTP creation / verification / expiry
- Two-factor verification helper
- Lockout policy primitives
- Permission seed manifest sanity
"""

import os

# Tests require minimal env config. This is now handled globally in conftest.py.

from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import OTPError, TokenError, UnauthorizedError, ValidationError
from app.core.security import (
    create_access_token,
    create_otp_challenge_payload,
    create_refresh_token,
    decode_token,
    ensure_two_factor_verified,
    validate_password_strength,
    validate_token_type,
    verify_two_factor_code,
    verify_user_password,
    get_password_hash,
)
from app.utils.otp_utils import generate_otp, hash_otp, verify_otp


# ============================================================
# JWT ROUND-TRIP
# ============================================================

class TestJWTRoundTrip:

    def test_access_token_round_trip_carries_role_and_2fa_flag(self):
        token, payload = create_access_token(
            subject="42",
            role="ADMIN",
            roles=["ADMIN"],
            two_factor_verified=True,
        )
        decoded = decode_token(token)
        assert decoded["sub"] == "42"
        assert decoded["type"] == "access"
        assert decoded["role"] == "ADMIN"
        assert decoded["roles"] == ["ADMIN"]
        assert decoded["two_factor_verified"] is True
        assert "jti" in decoded
        assert decoded["jti"] == payload["jti"]

    def test_refresh_token_has_correct_type(self):
        token, _ = create_refresh_token(subject="42")
        payload = validate_token_type(token, "refresh")
        assert payload["type"] == "refresh"

    def test_invalid_token_raises_token_error(self):
        with pytest.raises(TokenError):
            decode_token("not-a-token")

    def test_validate_token_type_rejects_mismatched_type(self):
        token, _ = create_access_token(subject="1")
        with pytest.raises(TokenError):
            validate_token_type(token, "refresh")

    def test_ensure_two_factor_verified_blocks_unverified_token(self):
        token, _ = create_access_token(subject="1", two_factor_verified=False)
        with pytest.raises(UnauthorizedError):
            ensure_two_factor_verified(token)

    def test_ensure_two_factor_verified_passes_verified_token(self):
        token, _ = create_access_token(subject="1", two_factor_verified=True)
        payload = ensure_two_factor_verified(token)
        assert payload["two_factor_verified"] is True


# ============================================================
# PASSWORD HASHING + STRENGTH
# ============================================================

class TestPasswords:

    def test_hash_then_verify_succeeds(self):
        hashed = get_password_hash("Password123")
        assert verify_user_password("Password123", hashed) is True

    def test_verify_with_wrong_password_fails(self):
        hashed = get_password_hash("Password123")
        assert verify_user_password("WrongPassword", hashed) is False

    def test_password_too_short_is_rejected(self):
        with pytest.raises(ValidationError):
            validate_password_strength("Pa1")

    def test_password_missing_letter_is_rejected(self):
        with pytest.raises(ValidationError):
            validate_password_strength("12345678")

    def test_password_missing_digit_is_rejected(self):
        with pytest.raises(ValidationError):
            validate_password_strength("abcdefgh")

    def test_password_meeting_baseline_passes(self):
        validate_password_strength("Password123!")  # should not raise


# ============================================================
# OTP HELPERS
# ============================================================

class TestOTP:

    def test_generate_then_verify_otp_round_trip(self):
        code = generate_otp(6)
        hashed = hash_otp(code)
        assert verify_otp(code, hashed) is True
        assert verify_otp("wrong-code", hashed) is False

    def test_create_otp_challenge_payload_returns_expected_shape(self):
        payload = create_otp_challenge_payload(
            user_id=1,
            challenge_type="EMAIL",
            purpose="LOGIN",
            destination="user@example.com",
            otp_length=6,
            max_attempts=5,
        )
        assert payload["user_id"] == 1
        assert payload["plain_code"]
        assert payload["code_hash"]
        assert payload["plain_code"] != payload["code_hash"]
        assert payload["max_attempts"] == 5
        assert payload["expires_at"] > datetime.now(timezone.utc)
        assert verify_otp(payload["plain_code"], payload["code_hash"]) is True

    def test_verify_two_factor_code_rejects_expired(self):
        code = generate_otp(6)
        with pytest.raises(OTPError):
            verify_two_factor_code(
                plain_code=code,
                stored_code_hash=hash_otp(code),
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                attempt_count=0,
                max_attempts=5,
            )

    def test_verify_two_factor_code_rejects_max_attempts(self):
        code = generate_otp(6)
        with pytest.raises(OTPError):
            verify_two_factor_code(
                plain_code=code,
                stored_code_hash=hash_otp(code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                attempt_count=5,
                max_attempts=5,
            )

    def test_verify_two_factor_code_rejects_invalid_code(self):
        code = generate_otp(6)
        with pytest.raises(OTPError):
            verify_two_factor_code(
                plain_code="000000",
                stored_code_hash=hash_otp(code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                attempt_count=0,
                max_attempts=5,
            )

    def test_verify_two_factor_code_accepts_valid_code(self):
        code = generate_otp(6)
        assert verify_two_factor_code(
            plain_code=code,
            stored_code_hash=hash_otp(code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            attempt_count=0,
            max_attempts=5,
        ) is True


# ============================================================
# LOCKOUT POLICY PRIMITIVES
# ============================================================

class _MockUser:
    """
    Mock user object that mimics the SQLAlchemy User model surface used by
    `AuthService._is_user_locked`.
    """

    def __init__(
        self,
        *,
        status="ACTIVE",
        failed_login_attempts=0,
        locked_until=None,
    ) -> None:
        self.id = 1
        self.username = "test-user"
        self.status = status
        self.failed_login_attempts = failed_login_attempts
        self.locked_until = locked_until


class _MockRepo:
    """
    Mock repository capturing reset/update calls invoked by the lockout helper.
    """

    def __init__(self) -> None:
        self.reset_called = False
        self.status_updates: list = []

    def reset_failed_login_attempts(self, user):
        self.reset_called = True
        user.failed_login_attempts = 0
        user.locked_until = None
        return user

    def update_user_status(self, user, status):
        self.status_updates.append(status)
        user.status = status
        return user


class _LockoutTestService:
    """
    Minimal facade replicating the locked-window logic from AuthService for
    isolated testing.
    """

    def __init__(self, repository):
        self.repository = repository

    _is_user_locked = None  # populated below


def _bind_lockout_helper():
    from app.services.auth_service import AuthService
    _LockoutTestService._is_user_locked = AuthService._is_user_locked


_bind_lockout_helper()


class TestLockoutPolicy:

    def test_user_with_active_status_and_no_lockout_is_not_locked(self):
        repo = _MockRepo()
        service = _LockoutTestService(repo)
        user = _MockUser(status="ACTIVE", failed_login_attempts=0, locked_until=None)
        assert service._is_user_locked(user, now=datetime.now(timezone.utc)) is False
        assert repo.reset_called is False

    def test_user_locked_with_future_window_is_locked(self):
        repo = _MockRepo()
        service = _LockoutTestService(repo)
        user = _MockUser(
            status="LOCKED",
            failed_login_attempts=5,
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        assert service._is_user_locked(user, now=datetime.now(timezone.utc)) is True

    def test_user_with_expired_lockout_window_is_unlocked_and_reset(self):
        repo = _MockRepo()
        service = _LockoutTestService(repo)
        user = _MockUser(
            status="LOCKED",
            failed_login_attempts=5,
            locked_until=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        assert service._is_user_locked(user, now=datetime.now(timezone.utc)) is False
        assert repo.reset_called is True
        assert any(str(s).upper() == "ACTIVE" for s in repo.status_updates)

    def test_user_with_locked_status_but_no_window_is_locked(self):
        repo = _MockRepo()
        service = _LockoutTestService(repo)
        user = _MockUser(status="LOCKED", failed_login_attempts=5, locked_until=None)
        assert service._is_user_locked(user, now=datetime.now(timezone.utc)) is True

    def test_active_user_with_expired_lockout_window_resets(self):
        repo = _MockRepo()
        service = _LockoutTestService(repo)
        user = _MockUser(
            status="ACTIVE",
            failed_login_attempts=5,
            locked_until=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        assert service._is_user_locked(user, now=datetime.now(timezone.utc)) is False
        assert repo.reset_called is True


# ============================================================
# SEED MANIFEST SANITY
# ============================================================

class TestSecuritySeedManifest:

    def test_default_roles_have_unique_codes(self):
        from app.seeds.security_seed import DEFAULT_ROLES
        codes = [role["code"] for role in DEFAULT_ROLES]
        assert len(codes) == len(set(codes))

    def test_default_permissions_have_unique_codes(self):
        from app.seeds.security_seed import DEFAULT_PERMISSIONS
        codes = [permission["code"] for permission in DEFAULT_PERMISSIONS]
        assert len(codes) == len(set(codes))

    def test_role_permission_map_only_references_existing_permissions(self):
        from app.seeds.security_seed import (
            DEFAULT_PERMISSIONS,
            DEFAULT_ROLE_PERMISSIONS,
            DEFAULT_ROLES,
        )
        permission_codes = {permission["code"] for permission in DEFAULT_PERMISSIONS}
        role_codes = {role["code"] for role in DEFAULT_ROLES}

        for role_code, permissions in DEFAULT_ROLE_PERMISSIONS.items():
            assert role_code in role_codes, f"Unknown role: {role_code}"
            unknown = set(permissions) - permission_codes
            assert not unknown, f"Role {role_code} references unknown permissions: {unknown}"

    def test_super_admin_gets_every_permission(self):
        from app.seeds.security_seed import DEFAULT_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS
        all_codes = {permission["code"] for permission in DEFAULT_PERMISSIONS}
        super_admin = set(DEFAULT_ROLE_PERMISSIONS["TENANT_ADMIN"])
        assert super_admin == all_codes
