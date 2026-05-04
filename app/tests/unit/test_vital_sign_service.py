"""Unit tests for VitalSignService and BMI computation."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.enums import VisitStatus
from app.core.exceptions import BadRequestError
from app.services.vital_sign_service import VitalSignService, _compute_bmi


class TestComputeBmi:
    def test_returns_none_when_no_weight(self):
        assert _compute_bmi(None, Decimal("170")) is None

    def test_returns_none_when_no_height(self):
        assert _compute_bmi(Decimal("70"), None) is None

    def test_returns_none_when_height_zero(self):
        assert _compute_bmi(Decimal("70"), Decimal("0")) is None

    def test_computes_correctly(self):
        bmi = _compute_bmi(Decimal("80"), Decimal("180"))
        # 80 / (1.8^2) = 24.69
        assert bmi is not None
        assert abs(bmi - Decimal("24.69")) < Decimal("0.01")


class TestVitalSignCreate:
    def test_rejects_closed_visit(self):
        db = MagicMock()
        svc = VitalSignService(db)
        svc.repository = MagicMock()
        visit = SimpleNamespace(id=1, status=VisitStatus.COMPLETED)
        svc.repository.get_required_visit.return_value = visit
        payload = MagicMock(visit_id=1)
        with pytest.raises(BadRequestError, match="closed visit"):
            svc.create(payload)


class TestVitalSignGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = VitalSignService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)
