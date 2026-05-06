"""Unit tests for IntegrationService.

Covers CRUD over IntegrationEndpoint, encryption of credential secrets,
NotFoundError on missing endpoints, and the decrypted-credentials helper.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.services.integration_service import IntegrationService


def _make_svc():
    db = MagicMock()
    return IntegrationService(db), db


class TestGetEndpoints:
    def test_returns_all(self):
        svc, db = _make_svc()
        db.query.return_value.all.return_value = ["e1", "e2"]
        assert svc.get_endpoints() == ["e1", "e2"]

    def test_get_endpoint_returns_record(self):
        svc, db = _make_svc()
        e = SimpleNamespace(id=1, code="HL7")
        db.query.return_value.filter.return_value.first.return_value = e
        assert svc.get_endpoint(1) is e

    def test_get_endpoint_raises_not_found(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError, match="Integration endpoint not found"):
            svc.get_endpoint(99)


class TestCreateEndpoint:
    @patch("app.services.integration_service.encrypt_string")
    def test_creates_without_credentials(self, mock_encrypt):
        svc, db = _make_svc()
        payload = MagicMock()
        payload.code = "EP"
        payload.name = "EP1"
        payload.base_url = "https://x"
        payload.protocol = "HTTP"
        payload.provider_type = "PROVIDER"
        payload.direction = "OUTBOUND"
        payload.is_active = True
        payload.credentials = []
        svc.create_endpoint(payload)
        # Endpoint added once, no credentials added
        assert db.add.call_count == 1
        db.flush.assert_called_once()
        db.commit.assert_called_once()
        mock_encrypt.assert_not_called()

    @patch("app.services.integration_service.encrypt_string")
    def test_encrypts_each_credential(self, mock_encrypt):
        svc, db = _make_svc()
        mock_encrypt.side_effect = lambda raw: f"ENC({raw})"
        cred1 = MagicMock()
        cred1.credential_type = "API_KEY"
        cred1.secret_reference = "key1"
        cred2 = MagicMock()
        cred2.credential_type = "PASSWORD"
        cred2.secret_reference = "pw"
        payload = MagicMock()
        payload.code = "EP"
        payload.name = "n"
        payload.base_url = "u"
        payload.protocol = "p"
        payload.provider_type = "x"
        payload.direction = "OUT"
        payload.is_active = True
        payload.credentials = [cred1, cred2]
        svc.create_endpoint(payload)
        # 1 endpoint + 2 credentials
        assert db.add.call_count == 3
        # Both credentials encrypted
        assert mock_encrypt.call_count == 2
        mock_encrypt.assert_any_call("key1")
        mock_encrypt.assert_any_call("pw")
        db.commit.assert_called_once()


class TestUpdateEndpoint:
    def test_rejects_missing_endpoint(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError):
            svc.update_endpoint(1, MagicMock())

    def test_applies_update(self):
        svc, db = _make_svc()
        e = SimpleNamespace(id=1, name="old", base_url="x")
        db.query.return_value.filter.return_value.first.return_value = e
        payload = MagicMock()
        payload.model_dump.return_value = {"name": "new"}
        svc.update_endpoint(1, payload)
        assert e.name == "new"
        db.commit.assert_called_once()


class TestDeleteEndpoint:
    def test_deletes_existing(self):
        svc, db = _make_svc()
        e = SimpleNamespace(id=1)
        db.query.return_value.filter.return_value.first.return_value = e
        svc.delete_endpoint(1)
        db.delete.assert_called_once_with(e)
        db.commit.assert_called_once()

    def test_raises_when_missing(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError):
            svc.delete_endpoint(99)


class TestGetDecryptedCredentials:
    @patch("app.services.integration_service.decrypt_string")
    def test_returns_dict(self, mock_decrypt):
        svc, db = _make_svc()
        mock_decrypt.side_effect = lambda v: v.replace("ENC", "PLAIN")
        cred1 = SimpleNamespace(credential_type="API_KEY", secret_reference="ENC1")
        cred2 = SimpleNamespace(credential_type="PASSWORD", secret_reference="ENC2")
        endpoint = SimpleNamespace(id=1, credentials=[cred1, cred2])
        db.query.return_value.filter.return_value.first.return_value = endpoint
        out = svc.get_decrypted_credentials(1)
        assert out == {"API_KEY": "PLAIN1", "PASSWORD": "PLAIN2"}

    def test_raises_when_endpoint_missing(self):
        svc, db = _make_svc()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundError):
            svc.get_decrypted_credentials(404)
