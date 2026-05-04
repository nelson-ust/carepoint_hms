# app/tests/unit/test_notification_dispatcher.py
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from app.models.all_models import User
from app.services.notification_dispatcher import NotificationDispatcher
from app.core.enums import NotificationEvent, NotificationChannel, NotificationStatus
from app.core.exceptions import BadRequestError

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def dispatcher(mock_db):
    with patch("app.services.notification_dispatcher.TenantSettingService") as mock_settings_cls:
        d = NotificationDispatcher(mock_db)
        d.settings = mock_settings_cls.return_value
        yield d

class TestNotificationDispatcher:

    def test_dispatch_fails_if_body_empty(self, dispatcher):
        with pytest.raises(BadRequestError) as excinfo:
            dispatcher.dispatch(event="TEST_EVENT", recipients=[], body="")
        assert "body must not be empty" in str(excinfo.value)

    def test_dispatch_respects_force_channels(self, dispatcher, mock_db):
        user = MagicMock(id=1, email="test@example.com")
        dispatcher._resolve_user = MagicMock(return_value=user)
        dispatcher._deliver = MagicMock()
        
        with patch("app.services.notification_dispatcher._CODE_TO_ENUM", {"email": NotificationChannel.EMAIL}):
            results = dispatcher.dispatch(
                event="TEST_EVENT",
                recipients=[user],
                body="Hello",
                force_channels=["email"]
            )
            
            assert len(results) == 1
            assert results[0].channel == NotificationChannel.EMAIL
            dispatcher._deliver.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_dispatch_skips_quiet_hours(self, dispatcher):
        dispatcher.settings.is_in_quiet_hours = MagicMock(return_value=True)
        dispatcher.settings.get_channels_for_event = MagicMock(return_value=["email", "sms"])
        
        user = MagicMock(id=1, email="test@example.com", phone_number="123")
        dispatcher._resolve_user = MagicMock(return_value=user)
        dispatcher._deliver = MagicMock()
        
        results = dispatcher.dispatch(
            event="TEST_EVENT",
            recipients=[user],
            body="Hello",
            suppress_quiet_hours=True
        )
        
        # SMS is a quiet hour channel, so only email should be sent
        assert len(results) == 1
        assert results[0].channel == NotificationChannel.EMAIL

    def test_resolve_user_handles_various_inputs(self, dispatcher, mock_db):
        user = MagicMock(spec=User, id=1)
        # 1. User instance
        assert dispatcher._resolve_user(user) == user
        
        # 2. User ID
        mock_db.query().filter().first.return_value = user
        assert dispatcher._resolve_user(1) == user
        
        # 3. Dict
        assert dispatcher._resolve_user({"user_id": 1}) == user

    def test_deliver_email_success(self, dispatcher, mock_db):
        notif = MagicMock(channel=NotificationChannel.EMAIL, recipient_address="test@example.com", body="Hello")
        with patch("app.services.notification_dispatcher._send_email_safe", return_value=True) as mock_send:
            dispatcher._deliver(notif, user=None, channel="email")
            assert notif.status == NotificationStatus.SENT
            mock_send.assert_called_once()

    def test_deliver_email_failure(self, dispatcher, mock_db):
        notif = MagicMock(channel=NotificationChannel.EMAIL, recipient_address="test@example.com", body="Hello", failure_reason=None)
        with patch("app.services.notification_dispatcher._send_email_safe", return_value=False) as mock_send:
            dispatcher._deliver(notif, user=None, channel="email")
            assert notif.status == NotificationStatus.FAILED
            assert notif.failure_reason == "delivery skipped"
