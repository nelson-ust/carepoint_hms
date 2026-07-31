"""Integration tests for the public WhatsApp webhook endpoint:
the GET verification handshake, POST signature enforcement, and end-to-end
delivery logging with idempotency.
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from pydantic import SecretStr

from app.core.config import settings


SAMPLE = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "102290129340398",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {"display_phone_number": "15550783881",
                             "phone_number_id": "106540352242922"},
                "contacts": [{"profile": {"name": "Sheena Nelson"}, "wa_id": "16505551234"}],
                "messages": [{
                    "from": "16505551234",
                    "id": "wamid.HBgLMTY1MDM4Nzk0MzkVAgASGBQzQTRBNjU5OUFFRTAzODEwMTQ0RgA=",
                    "timestamp": "1749416383",
                    "type": "text",
                    "text": {"body": "Does it come in another color?"},
                }],
            },
            "field": "messages",
        }],
    }],
}


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class TestVerificationHandshake:
    def test_valid_token_echoes_challenge(self, client, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", SecretStr("verify-me"))
        resp = client.get("/api/v1/whatsapp/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-me",
            "hub.challenge": "1158201444",
        })
        assert resp.status_code == 200
        assert resp.text == "1158201444"

    def test_wrong_token_forbidden(self, client, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", SecretStr("verify-me"))
        resp = client.get("/api/v1/whatsapp/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "123",
        })
        assert resp.status_code == 403


class TestDeliverySignature:
    def test_invalid_signature_rejected(self, client, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_VERIFY_SIGNATURE", True)
        monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", SecretStr("app-secret"))
        body = json.dumps(SAMPLE).encode()
        resp = client.post("/api/v1/whatsapp/webhook", content=body,
                           headers={"X-Hub-Signature-256": "sha256=deadbeef",
                                    "Content-Type": "application/json"})
        assert resp.status_code == 403

    def test_missing_signature_rejected(self, client, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_VERIFY_SIGNATURE", True)
        monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", SecretStr("app-secret"))
        resp = client.post("/api/v1/whatsapp/webhook", content=b"{}",
                           headers={"Content-Type": "application/json"})
        assert resp.status_code == 403


class TestDeliveryProcessing:
    def test_valid_delivery_logged_and_idempotent(self, client, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_VERIFY_SIGNATURE", True)
        monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", SecretStr("app-secret"))
        # Unique body so the idempotency (payload_hash) assertion is isolated
        # from any other test run against the shared DB.
        import uuid
        payload = json.loads(json.dumps(SAMPLE))
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = "wamid." + uuid.uuid4().hex
        body = json.dumps(payload).encode()
        headers = {"X-Hub-Signature-256": _sign(body, "app-secret"),
                   "Content-Type": "application/json"}

        first = client.post("/api/v1/whatsapp/webhook", content=body, headers=headers)
        assert first.status_code == 200
        assert first.json()["status"] == "processed"

        # The raw event is persisted for audit.
        from app.core.database import SessionLocal
        from app.models.all_models import WhatsAppWebhookEvent
        digest = hashlib.sha256(body).hexdigest()
        s = SessionLocal()
        try:
            event = (s.query(WhatsAppWebhookEvent)
                     .filter(WhatsAppWebhookEvent.payload_hash == digest).first())
            assert event is not None
            assert event.phone_number_id == "106540352242922"
            assert event.object_type == "whatsapp_business_account"
        finally:
            s.close()

        # A retried (identical) delivery is a no-op, not a duplicate row.
        second = client.post("/api/v1/whatsapp/webhook", content=body, headers=headers)
        assert second.status_code == 200
        assert second.json()["status"] == "duplicate"

    def test_signature_check_can_be_disabled(self, client, monkeypatch):
        monkeypatch.setattr(settings, "WHATSAPP_VERIFY_SIGNATURE", False)
        payload = json.loads(json.dumps(SAMPLE))
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = "wamid.itest-unique-2"
        resp = client.post("/api/v1/whatsapp/webhook",
                           content=json.dumps(payload).encode(),
                           headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
