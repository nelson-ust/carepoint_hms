"""Unit tests for SaaSAuthService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.saas_auth_service import SaaSAuthService


class TestSaaSAuthConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = SaaSAuthService(db)
        assert svc.db is db
