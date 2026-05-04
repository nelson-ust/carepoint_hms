# app/tests/unit/test_auth_service.py
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime, timezone, timedelta

from app.services.auth_service import AuthService
from app.schemas.auth_schemas import LoginSchema
from app.core.exceptions import UnauthorizedError, NotFoundError, BadRequestError

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def service(mock_db):
    with patch("app.services.auth_service.AuthRepository") as mock_repo_cls, \
         patch("app.services.auth_service.TenantUsageService") as mock_usage_cls:
        svc = AuthService(mock_db)
        svc.repository = mock_repo_cls.return_value
        yield svc

class TestAuthService:

    def test_login_fails_on_unknown_user(self, service, mock_db):
        payload = LoginSchema(identifier="unknown", password="Password123!")
        service.repository.get_user_with_roles_by_identifier = MagicMock(return_value=None)
        
        with patch("app.services.auth_service.get_current_tenant_id", return_value=1):
            with patch("app.services.auth_service.record_security_event") as mock_record:
                with pytest.raises(UnauthorizedError) as excinfo:
                    service.login(payload)
                
                assert "Invalid credentials" in str(excinfo.value)
                mock_record.assert_called_once()
                mock_db.commit.assert_called_once()

    def test_login_blocks_locked_user(self, service, mock_db):
        payload = LoginSchema(identifier="locked", password="Password123!")
        user = MagicMock(username="locked", locked_until=datetime.now(timezone.utc) + timedelta(minutes=10))
        service.repository.get_user_with_roles_by_identifier = MagicMock(return_value=user)
        service._is_user_locked = MagicMock(return_value=True)
        
        with patch("app.services.auth_service.get_current_tenant_id", return_value=1):
            with pytest.raises(UnauthorizedError) as excinfo:
                service.login(payload)
            assert "Account is locked" in str(excinfo.value)

    def test_login_success_no_2fa(self, service, mock_db):
        payload = LoginSchema(identifier="active", password="CorrectPassword123!")
        user = MagicMock(id=1, username="active", password_hash="hash", is_two_factor_enabled=False, status="ACTIVE")
        service.repository.get_user_with_roles_by_identifier = MagicMock(return_value=user)
        service._is_user_locked = MagicMock(return_value=False)
        service._extract_role_codes = MagicMock(return_value=["ADMIN"])
        
        with patch("app.services.auth_service.get_current_tenant_id", return_value=1):
            with patch("app.services.auth_service.verify_user_password", return_value=True):
                with patch("app.services.auth_service.build_login_result") as mock_build:
                    mock_build.return_value = {
                        "access_token": "at", "refresh_token": "rt", "token_type": "bearer",
                        "session_payload": {}
                    }
                    result = service.login(payload)
                    
                    assert result["success"] is True
                    assert result["tokens"]["access_token"] == "at"
                    mock_db.commit.assert_called_once()

    def test_logout_all_sessions(self, service, mock_db):
        service.logout(all_sessions=True, current_user_id=1)
        service.repository.revoke_all_user_sessions.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_logout_fails_if_no_user_id_for_all_sessions(self, service):
        with pytest.raises(BadRequestError):
            service.logout(all_sessions=True)
