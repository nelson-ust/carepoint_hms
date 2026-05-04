"""Unit tests for InsuranceClaimService and ClaimBatchService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.insurance_claim_service import InsuranceClaimService, ClaimBatchService


class TestInsuranceClaimGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = InsuranceClaimService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestClaimBatchGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ClaimBatchService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestInsuranceClaimConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = InsuranceClaimService(db)
        assert svc.db is db
