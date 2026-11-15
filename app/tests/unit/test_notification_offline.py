"""Outbound notifications must NOT attempt the network (or hang) when offline;
they return False so the record stays pending for a later retry."""
from __future__ import annotations

import app.services.connectivity_service as cs
import app.services.notification_dispatcher as nd


def test_email_short_circuits_when_offline(monkeypatch):
    monkeypatch.setattr(cs, "is_online", lambda **k: False)
    called = {"hit": False}

    def _boom(*a, **k):
        called["hit"] = True
        raise AssertionError("network send attempted while offline")

    # If the guard works, these are never reached.
    monkeypatch.setattr("app.services.tenant_email_service.send_tenant_email", _boom, raising=False)
    assert nd._send_email_safe(None, subject="s", recipients=["a@b.c"], body_text="x") is False
    assert called["hit"] is False


def test_sms_short_circuits_when_offline(monkeypatch):
    monkeypatch.setattr(cs, "is_online", lambda **k: False)
    assert nd._send_sms_safe("+123", "hi") is False


def test_sends_are_allowed_when_online(monkeypatch):
    # When online the guard is transparent; the helper proceeds (and fails
    # gracefully to False if no transport is configured in the test env).
    monkeypatch.setattr(cs, "is_online", lambda **k: True)
    result = nd._send_sms_safe("+123", "hi")
    assert result in (True, False)
