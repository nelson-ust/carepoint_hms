"""Unit tests for IntegrationService.

The service moved from an ``IntegrationEndpoint`` + per-credential model to an
``IntegrationPartner`` model (API-key based, stored in the master DB). The old
``get_endpoints`` / ``get_endpoint`` / ``create_endpoint`` / ``update_endpoint``
/ ``delete_endpoint`` / ``get_decrypted_credentials`` methods were replaced by
``list_partners`` / ``create_partner`` / ``update_partner`` / ``rotate_key`` /
``revoke_partner`` (all operating over the master DB via
``get_master_db_context``). These tests exercise that current API.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.services.integration_service import IntegrationService

_CTX = "app.services.integration_service.get_master_db_context"
_KEYGEN = "app.services.integration_service.generate_api_key"
_ENCRYPT = "app.services.integration_service.encrypt_string"


def _master_ctx(mdb):
    """A stand-in for the ``get_master_db_context()`` context manager."""
    ctx = MagicMock()
    ctx.__enter__.return_value = mdb
    ctx.__exit__.return_value = False
    return ctx


def _partner_row(**overrides):
    """Object shaped like an ``IntegrationPartner`` row for ``_partner_read``."""
    base = dict(
        id=1,
        name="Alpha",
        description=None,
        is_active=True,
        key_prefix="chp_pref",
        key_hash="hash",
        scopes="READ",
        expires_at=None,
        last_used_at=None,
        base_url=None,
        auth_header="X-API-Key",
        auth_secret_encrypted=None,
        created_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestCreatePartner:
    @patch(_KEYGEN, return_value=("chp_full_key", "chp_pref", "hashval"))
    def test_creates_and_returns_full_key(self, mock_keygen):
        mdb = MagicMock()
        with patch(_CTX, return_value=_master_ctx(mdb)):
            svc = IntegrationService()
            info, full_key = svc.create_partner(
                tenant_id=1, name="Partner A", description=None, scopes=["READ"],
                expiry_days=None, base_url=None, auth_header=None,
                auth_secret=None, created_by_user_id=7,
            )
        assert full_key == "chp_full_key"
        assert info["name"] == "Partner A"
        mdb.add.assert_called_once()
        mdb.commit.assert_called_once()

    @patch(_KEYGEN, return_value=("k", "p", "h"))
    @patch(_ENCRYPT, return_value="ENC")
    def test_encrypts_auth_secret(self, mock_encrypt, mock_keygen):
        mdb = MagicMock()
        with patch(_CTX, return_value=_master_ctx(mdb)):
            svc = IntegrationService()
            info, _ = svc.create_partner(
                tenant_id=1, name="P", description=None, scopes=None,
                expiry_days=None, base_url="https://x", auth_header="X-Key",
                auth_secret="s3cret", created_by_user_id=None,
            )
        mock_encrypt.assert_called_once_with("s3cret")
        assert info["has_outbound_secret"] is True


class TestListPartners:
    def test_returns_partner_dicts(self):
        mdb = MagicMock()
        rows = [_partner_row(id=1, name="Alpha"), _partner_row(id=2, name="Beta")]
        mdb.query.return_value.filter.return_value.order_by.return_value.all.return_value = rows
        with patch(_CTX, return_value=_master_ctx(mdb)):
            svc = IntegrationService()
            out = svc.list_partners(tenant_id=1)
        assert [r["name"] for r in out] == ["Alpha", "Beta"]


class TestUpdatePartner:
    def test_rejects_missing_partner(self):
        mdb = MagicMock()
        mdb.query.return_value.filter.return_value.first.return_value = None
        with patch(_CTX, return_value=_master_ctx(mdb)):
            svc = IntegrationService()
            with pytest.raises(NotFoundError, match="Integration partner not found"):
                svc.update_partner(partner_id=1, tenant_id=1, changes={"name": "x"})

    def test_applies_name_change(self):
        mdb = MagicMock()
        p = _partner_row(id=1, name="old")
        mdb.query.return_value.filter.return_value.first.return_value = p
        with patch(_CTX, return_value=_master_ctx(mdb)):
            svc = IntegrationService()
            out = svc.update_partner(partner_id=1, tenant_id=1, changes={"name": "new"})
        assert p.name == "new"
        assert out["name"] == "new"
        mdb.commit.assert_called_once()


class TestRotateKey:
    @patch(_KEYGEN, return_value=("newfull", "newpref", "newhash"))
    def test_rotates_and_returns_new_key(self, mock_keygen):
        mdb = MagicMock()
        p = _partner_row(id=1, key_prefix="oldpref", key_hash="oldhash")
        mdb.query.return_value.filter.return_value.first.return_value = p
        with patch(_CTX, return_value=_master_ctx(mdb)):
            svc = IntegrationService()
            info, full_key = svc.rotate_key(partner_id=1, tenant_id=1)
        assert full_key == "newfull"
        assert p.key_prefix == "newpref"
        assert p.key_hash == "newhash"
        assert info["key_prefix"] == "newpref"
        mdb.commit.assert_called_once()


class TestRevokePartner:
    def test_marks_inactive(self):
        mdb = MagicMock()
        p = _partner_row(id=1, is_active=True)
        mdb.query.return_value.filter.return_value.first.return_value = p
        with patch(_CTX, return_value=_master_ctx(mdb)):
            svc = IntegrationService()
            out = svc.revoke_partner(partner_id=1, tenant_id=1)
        assert p.is_active is False
        assert out["is_active"] is False
        mdb.commit.assert_called_once()

    def test_rejects_missing_partner(self):
        mdb = MagicMock()
        mdb.query.return_value.filter.return_value.first.return_value = None
        with patch(_CTX, return_value=_master_ctx(mdb)):
            svc = IntegrationService()
            with pytest.raises(NotFoundError):
                svc.revoke_partner(partner_id=99, tenant_id=1)
