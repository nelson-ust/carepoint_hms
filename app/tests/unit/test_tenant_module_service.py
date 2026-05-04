"""Unit tests for TenantModuleService."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.core.exceptions import BadRequestError
from app.services.tenant_module_service import (
    SUPPORTED_MODULE_CODES,
    SUPPORTED_MODULES,
    TenantModuleService,
    _normalize,
)


class TestNormalize:
    def test_accepts_supported_module(self):
        assert _normalize("clinical") == "clinical"
        assert _normalize("PHARMACY") == "pharmacy"

    def test_rejects_blank(self):
        with pytest.raises(BadRequestError):
            _normalize("")

    def test_rejects_unsupported(self):
        with pytest.raises(BadRequestError):
            _normalize("nonexistent_module")


class TestModuleCatalog:
    def test_all_codes_unique(self):
        codes = [c for c, _ in SUPPORTED_MODULES]
        assert len(codes) == len(set(codes))

    def test_supported_set_matches_tuple(self):
        assert SUPPORTED_MODULE_CODES == {c for c, _ in SUPPORTED_MODULES}

    def test_clinical_present(self):
        assert "clinical" in SUPPORTED_MODULE_CODES


class TestTenantModuleServiceConstructor:
    def test_holds_session(self):
        db = MagicMock()
        svc = TenantModuleService(db)
        assert svc.db is db


class TestSetModule:
    def test_set_module_validates_code(self):
        db = MagicMock()
        svc = TenantModuleService(db)
        with pytest.raises(BadRequestError):
            svc.set_module(1, "not_a_real_module", is_enabled=False)
