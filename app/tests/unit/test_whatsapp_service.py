"""Unit tests for the WhatsApp integration's pure helpers (no DB):
verification handshake, signature validation, and payload parsing.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from app.services.whatsapp_service import (
    extract_message_content,
    normalize_phone,
    parse_change_value,
    phone_suffix,
    verify_signature,
    verify_subscription,
    _status_is_regression,
)

# The example delivery from Meta's webhook documentation.
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


class TestVerifySubscription:
    def test_valid_returns_challenge(self):
        out = verify_subscription("subscribe", "tok", "CHALLENGE-123", ["tok"])
        assert out == "CHALLENGE-123"

    def test_wrong_token_returns_none(self):
        assert verify_subscription("subscribe", "nope", "C", ["tok"]) is None

    def test_wrong_mode_returns_none(self):
        assert verify_subscription("unsubscribe", "tok", "C", ["tok"]) is None

    def test_no_tokens_configured(self):
        assert verify_subscription("subscribe", "tok", "C", []) is None

    def test_multiple_acceptable_tokens(self):
        assert verify_subscription("subscribe", "second", "C", ["first", "second"]) == "C"


class TestVerifySignature:
    def _sig(self, body: bytes, secret: str) -> str:
        return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_valid_signature(self):
        body = json.dumps(SAMPLE).encode()
        assert verify_signature(body, self._sig(body, "s3cr3t"), "s3cr3t") is True

    def test_valid_without_prefix(self):
        body = b'{"a":1}'
        digest = hmac.new(b"k", body, hashlib.sha256).hexdigest()
        assert verify_signature(body, digest, "k") is True

    def test_tampered_body_fails(self):
        body = b'{"a":1}'
        sig = self._sig(body, "k")
        assert verify_signature(b'{"a":2}', sig, "k") is False

    def test_wrong_secret_fails(self):
        body = b'{"a":1}'
        assert verify_signature(body, self._sig(body, "k"), "other") is False

    def test_missing_secret_or_header(self):
        assert verify_signature(b"x", "sha256=abc", None) is False
        assert verify_signature(b"x", None, "k") is False


class TestPhoneHelpers:
    def test_normalize_strips_symbols(self):
        assert normalize_phone("+1 (650) 555-1234") == "16505551234"

    def test_suffix_last_10(self):
        assert phone_suffix("+2348012345678", 10) == "8012345678"

    def test_empty(self):
        assert normalize_phone(None) == "" and phone_suffix("", 10) == ""


class TestExtractMessageContent:
    def test_text(self):
        c = extract_message_content(SAMPLE["entry"][0]["changes"][0]["value"]["messages"][0])
        assert c["message_type"] == "TEXT"
        assert c["body"] == "Does it come in another color?"
        assert c["from_number"] == "16505551234"
        assert c["wa_message_id"].startswith("wamid.")
        assert c["wa_timestamp"] is not None

    def test_image_with_caption(self):
        c = extract_message_content({
            "type": "image", "id": "wamid.img",
            "image": {"id": "MEDIA1", "mime_type": "image/jpeg", "caption": "x-ray"},
        })
        assert c["message_type"] == "IMAGE"
        assert c["media_id"] == "MEDIA1"
        assert c["media_mime_type"] == "image/jpeg"
        assert c["caption"] == "x-ray" and c["body"] == "x-ray"

    def test_document(self):
        c = extract_message_content({
            "type": "document", "id": "wamid.doc",
            "document": {"id": "D1", "mime_type": "application/pdf", "filename": "result.pdf"},
        })
        assert c["message_type"] == "DOCUMENT"
        assert c["media_filename"] == "result.pdf"

    def test_location(self):
        c = extract_message_content({
            "type": "location", "id": "wamid.loc",
            "location": {"latitude": 6.5, "longitude": 3.3, "name": "Clinic"},
        })
        assert c["message_type"] == "LOCATION" and c["body"] == "Clinic"

    def test_interactive_button_reply(self):
        c = extract_message_content({
            "type": "interactive", "id": "wamid.int",
            "interactive": {"type": "button_reply",
                            "button_reply": {"id": "1", "title": "Yes, confirm"}},
        })
        assert c["message_type"] == "INTERACTIVE" and c["body"] == "Yes, confirm"

    def test_unknown_type(self):
        c = extract_message_content({"type": "carrier_pigeon", "id": "w"})
        assert c["message_type"] == "UNKNOWN"


class TestParseChangeValue:
    def test_parses_sample(self):
        parsed = parse_change_value(SAMPLE["entry"][0]["changes"][0]["value"])
        assert parsed["phone_number_id"] == "106540352242922"
        assert parsed["display_phone_number"] == "15550783881"
        assert parsed["contacts"]["16505551234"] == "Sheena Nelson"
        assert len(parsed["messages"]) == 1
        assert parsed["messages"][0]["body"] == "Does it come in another color?"
        assert parsed["statuses"] == []

    def test_parses_statuses(self):
        value = {
            "metadata": {"phone_number_id": "PNID"},
            "statuses": [{
                "id": "wamid.out1", "status": "delivered", "recipient_id": "234",
                "timestamp": "1749416400",
            }],
        }
        parsed = parse_change_value(value)
        assert parsed["messages"] == []
        assert len(parsed["statuses"]) == 1
        st = parsed["statuses"][0]
        assert st["wa_message_id"] == "wamid.out1"
        assert st["status"] == "DELIVERED"
        assert st["timestamp"] is not None

    def test_failed_status_carries_error(self):
        value = {"metadata": {"phone_number_id": "P"}, "statuses": [{
            "id": "wamid.x", "status": "failed", "timestamp": "1",
            "errors": [{"code": 131047, "title": "Re-engagement message"}],
        }]}
        st = parse_change_value(value)["statuses"][0]
        assert st["status"] == "FAILED"
        assert st["error_code"] == "131047"
        assert "Re-engagement" in st["error_title"]


class TestStatusRegression:
    def test_forward_progress_allowed(self):
        assert _status_is_regression("SENT", "DELIVERED") is False
        assert _status_is_regression("DELIVERED", "READ") is False

    def test_backwards_blocked(self):
        assert _status_is_regression("READ", "DELIVERED") is True
        assert _status_is_regression("DELIVERED", "SENT") is True

    def test_failed_always_applies(self):
        assert _status_is_regression("READ", "FAILED") is False

    def test_unknown_states_pass_through(self):
        assert _status_is_regression(None, "SENT") is False
