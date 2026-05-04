"""Unit tests for PatientPaymentService helpers."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.patient_payment_service import _decimal, _generate_reference


class TestDecimalHelper:
    def test_converts_int(self):
        assert _decimal(100) == Decimal("100")

    def test_converts_float(self):
        assert _decimal(10.5) == Decimal("10.5")

    def test_converts_string(self):
        assert _decimal("99.99") == Decimal("99.99")

    def test_passthrough_decimal(self):
        d = Decimal("42.00")
        assert _decimal(d) == d


class TestGenerateReference:
    def test_starts_with_prefix(self):
        ref = _generate_reference("INV")
        assert ref.startswith("INV-")

    def test_has_entropy(self):
        # Should be reasonably long with entropy
        ref = _generate_reference("PAY")
        assert len(ref) > 6

    def test_unique_references(self):
        refs = {_generate_reference("TXN") for _ in range(50)}
        assert len(refs) == 50
