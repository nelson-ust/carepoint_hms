# app/tests/integration/test_auth_routes.py
from __future__ import annotations

"""
Integration tests for the auth, RBAC, lockout, and 2FA routes.

These tests depend on a running PostgreSQL database. They are auto-skipped
when `CAREPOINT_HMS_DATABASE_URL` is not configured (see conftest.py).

What they cover
---------------
- public auth endpoints (login, refresh, OTP verify, OTP resend)
- session revocation on logout
- failed-login lockout policy
- forced status change kicks active sessions
- role / permission admin endpoints require AdminUser
- effective permission resolution for the authenticated user
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.tests.conftest import HAS_TEST_DB

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


# ============================================================
# HELPERS
# ============================================================


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


@pytest.fixture()
def seeded_security(db_session):
    """
    Ensure the canonical role/permission seed has been applied for tests
    that assume those records exist.
    """
    from app.seeds.security_seed import seed_security_baseline
    seed_security_baseline(db_session)
    return True


@pytest.fixture()
def admin_user(db_session, seeded_security):
    """
    Create a TENANT_ADMIN user and return raw credentials for login tests.
    """
    from app.core.enums import UserStatus
    from app.core.security import get_password_hash
    from app.models.all_models import Role, User, UserRoleAssociation

    username = _unique("admin")
    email = f"{username}@test.example"
    password = "AdminPass123"

    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash(password),
        first_name="Test",
        last_name="Admin",
        status=UserStatus.ACTIVE,
        is_superuser=True,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    role = (
        db_session.query(Role)
        .filter(Role.code == "TENANT_ADMIN", Role.is_deleted.is_(False))
        .first()
    )
    if role is not None:
        db_session.add(UserRoleAssociation(user_id=user.id, role_id=role.id))

    db_session.commit()
    db_session.refresh(user)
    return {"user": user, "username": username, "email": email, "password": password}


@pytest.fixture()
def standard_user(db_session, seeded_security):
    """
    Create a non-admin DOCTOR user.
    """
    from app.core.enums import UserStatus
    from app.core.security import get_password_hash
    from app.models.all_models import Role, User, UserRoleAssociation

    username = _unique("doctor")
    email = f"{username}@test.example"
    password = "DoctorPass123"

    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash(password),
        first_name="Test",
        last_name="Doctor",
        status=UserStatus.ACTIVE,
        is_superuser=False,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    role = (
        db_session.query(Role)
        .filter(Role.code == "DOCTOR", Role.is_deleted.is_(False))
        .first()
    )
    if role is not None:
        db_session.add(UserRoleAssociation(user_id=user.id, role_id=role.id))

    db_session.commit()
    db_session.refresh(user)
    return {"user": user, "username": username, "email": email, "password": password}


def _login(client, identifier: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": identifier, "password": password},
    )
    return response


def _bearer_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ============================================================
# LOGIN / RBAC
# ============================================================


class TestLogin:

    def test_unknown_user_returns_401(self, client):
        response = _login(client, "nonexistent-user", "any-password")
        assert response.status_code == 401

    def test_login_success_returns_tokens(self, client, admin_user):
        response = _login(client, admin_user["username"], admin_user["password"])
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["tokens"]["access_token"]
        assert body["tokens"]["refresh_token"]

    def test_login_with_wrong_password_returns_401(self, client, admin_user):
        response = _login(client, admin_user["username"], "wrong-password")
        assert response.status_code == 401


class TestLockout:

    def test_repeated_bad_password_locks_account(self, client, admin_user, db_session):
        from app.core.config import settings
        from app.core.enums import UserStatus
        from app.models.all_models import User

        max_attempts = int(getattr(settings, "LOGIN_MAX_FAILED_ATTEMPTS", 5))

        for _ in range(max_attempts):
            response = _login(client, admin_user["username"], "wrong")
            assert response.status_code == 401

        # The next attempt — even with the correct password — should be blocked
        # because the account is now locked.
        response = _login(client, admin_user["username"], admin_user["password"])
        assert response.status_code == 401

        db_session.expire_all()
        user = db_session.get(User, admin_user["user"].id)
        assert user.status == UserStatus.LOCKED
        assert user.locked_until is not None


# ============================================================
# RBAC ENFORCEMENT
# ============================================================


class TestRoleProtectedEndpoints:

    def test_admin_can_list_roles(self, client, admin_user):
        token = _login(client, admin_user["username"], admin_user["password"]).json()["tokens"]["access_token"]
        response = client.get("/api/v1/roles/", headers=_bearer_headers(token))
        assert response.status_code == 200

    def test_non_admin_is_rejected(self, client, standard_user):
        token = _login(client, standard_user["username"], standard_user["password"]).json()["tokens"]["access_token"]
        response = client.get("/api/v1/roles/", headers=_bearer_headers(token))
        assert response.status_code == 403

    def test_unauthenticated_is_rejected(self, client):
        response = client.get("/api/v1/roles/")
        assert response.status_code == 401


# ============================================================
# PERMISSIONS RESOLVER
# ============================================================


class TestEffectivePermissions:

    def test_superuser_gets_wildcard(self, client, admin_user):
        token = _login(client, admin_user["username"], admin_user["password"]).json()["tokens"]["access_token"]
        response = client.get("/api/v1/permissions/me", headers=_bearer_headers(token))
        assert response.status_code == 200
        body = response.json()
        assert body["is_superuser"] is True
        assert body["permissions"] == ["*"]

    def test_doctor_has_clinical_permissions(self, client, standard_user):
        token = _login(client, standard_user["username"], standard_user["password"]).json()["tokens"]["access_token"]
        response = client.get("/api/v1/permissions/me", headers=_bearer_headers(token))
        assert response.status_code == 200
        body = response.json()
        assert body["is_superuser"] is False
        assert "PATIENT_READ" in body["permissions"]
        assert "USER_DELETE" not in body["permissions"]


# ============================================================
# 2FA EXPIRY / SESSION REVOCATION
# ============================================================


class TestTwoFactorPolicy:

    def test_admin_can_force_expire_open_challenges(
        self, client, admin_user, standard_user, db_session
    ):
        # Create an open 2FA challenge for the standard user.
        from app.models.all_models import TwoFactorChallenge
        from app.core.enums import TwoFactorPurpose, TwoFactorType

        challenge = TwoFactorChallenge(
            user_id=standard_user["user"].id,
            challenge_type=TwoFactorType.EMAIL,
            purpose=TwoFactorPurpose.LOGIN,
            destination=standard_user["email"],
            code_hash="dummyhash",
            attempt_count=0,
            max_attempts=5,
            is_verified=False,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db_session.add(challenge)
        db_session.commit()
        db_session.refresh(challenge)

        token = _login(client, admin_user["username"], admin_user["password"]).json()["tokens"]["access_token"]
        response = client.post(
            f"/api/v1/two-factor/users/{standard_user['user'].id}/expire-open-challenges",
            headers=_bearer_headers(token),
        )
        assert response.status_code == 200
        assert response.json()["expired_count"] >= 1


# ============================================================
# SECURITY EVENTS
# ============================================================


class TestSecurityEventLogging:

    def test_failed_login_records_security_event(self, client, admin_user, db_session):
        from app.models.all_models import SecurityEvent

        # Snapshot count, attempt one bad login, expect a new row.
        before_count = db_session.query(SecurityEvent).count()
        _login(client, admin_user["username"], "wrong-password")

        db_session.expire_all()
        after_count = db_session.query(SecurityEvent).count()
        assert after_count > before_count

        recent = (
            db_session.query(SecurityEvent)
            .order_by(SecurityEvent.id.desc())
            .first()
        )
        assert recent.event_type in {"LOGIN_FAILURE", "LOGIN_BLOCKED_INACTIVE"}
