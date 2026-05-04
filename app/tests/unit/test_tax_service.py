"""Unit tests for TaxService."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.core.enums import TaxApplicability, TaxKind, TaxPricingMode, TaxScope
from app.core.exceptions import BadRequestError
from app.services.tax_service import TaxService, _q


class TestQuantize:
    def test_q_two_places(self):
        assert _q(Decimal("1.236")) == Decimal("1.24")
        assert _q(Decimal("0")) == Decimal("0.00")


class TestCreateTaxTypeIdempotency:
    def test_rejects_duplicate_code(self):
        db = MagicMock()
        existing = MagicMock(id=1)
        db.query.return_value.filter.return_value.first.return_value = existing
        svc = TaxService(db)
        with pytest.raises(BadRequestError):
            svc.create_tax_type(code="vat", name="Value Added Tax")

    def test_normalizes_code_uppercase(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = TaxService(db)
        rec = svc.create_tax_type(code="vat", name="VAT")
        assert rec.code == "VAT"


class TestLineBaseFallback:
    def test_uses_amount_attr(self):
        item = MagicMock()
        item.net_amount = None
        item.subtotal_amount = None
        item.amount = Decimal("100")
        item.total_amount = None
        assert TaxService._line_base(item) == Decimal("100")

    def test_falls_back_to_qty_times_unit(self):
        item = MagicMock()
        item.net_amount = None
        item.subtotal_amount = None
        item.amount = None
        item.total_amount = None
        item.quantity = 3
        item.unit_price = Decimal("25")
        assert TaxService._line_base(item) == Decimal("75")


class TestSnapMethod:
    def test_serialises_columns(self):
        # Use a real-ish object with __table__.columns shape.
        class _Col:
            def __init__(self, name):
                self.name = name
        class _Tab:
            columns = [_Col("id"), _Col("name"), _Col("rate")]

        class _Rec:
            __table__ = _Tab()
            id = 1
            name = "VAT"
            rate = Decimal("7.5")

        out = TaxService._snap(_Rec())
        assert out["name"] == "VAT"
        assert out["rate"] == "7.5"
