"""Unit tests for BillingService.record_visit_services — the Patient Queue
'record services rendered at the current service delivery point' capture.

Fully mocked (no DB): verifies validation, billable-service default
resolution, SDP/user provenance stamping, and the returned summary.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.enums import BillingStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.services.billing_service import BillingService


def _make_service(*, visit=None, svc=None):
    """Build a BillingService with its DB query dispatch + collaborators mocked."""
    service = BillingService(MagicMock())

    def _query(model):
        qm = MagicMock()
        name = getattr(model, "__name__", str(model))
        if name == "Visit":
            result = visit
        elif name == "BillableService":
            result = svc
        else:
            result = MagicMock()
        qm.filter.return_value.first.return_value = result
        return qm

    service.db.query.side_effect = _query
    service.repository = MagicMock()
    service.get_visit_billing_summary = MagicMock(
        return_value={"visit_id": 1, "total_charges": "0.00"}
    )
    return service


VISIT = SimpleNamespace(id=1, patient_id=99, is_deleted=False)


class TestValidation:
    def test_empty_items_rejected(self):
        service = _make_service(visit=VISIT)
        with pytest.raises(BadRequestError):
            service.record_visit_services(1, [])

    def test_visit_not_found(self):
        service = _make_service(visit=None)
        with pytest.raises(NotFoundError):
            service.record_visit_services(1, [{"service_name": "Dressing"}])

    def test_line_without_name_or_service_rejected(self):
        service = _make_service(visit=VISIT)
        service._active_visit_billing = MagicMock(return_value=None)
        with pytest.raises(BadRequestError):
            service.record_visit_services(1, [{"quantity": 1}])

    def test_unknown_billable_service_rejected(self):
        service = _make_service(visit=VISIT, svc=None)
        service._active_visit_billing = MagicMock(return_value=None)
        with pytest.raises(BadRequestError):
            service.record_visit_services(1, [{"billable_service_id": 555}])


class TestCustomLine:
    def test_records_custom_line_with_provenance(self):
        service = _make_service(visit=VISIT)
        service._active_visit_billing = MagicMock(return_value=None)
        billing = SimpleNamespace(id=7, status=str(BillingStatus.OPEN))
        service.repository.create_billing.return_value = billing

        result = service.record_visit_services(
            1,
            [{"service_name": "Wound Dressing", "quantity": 2, "unit_price": "1500"}],
            service_delivery_point_id=8,
            rendered_by_user_id=42,
        )

        # A fresh charge sheet was opened because none was active.
        service.repository.create_billing.assert_called_once()
        service.repository.add_item.assert_called_once()
        kwargs = service.repository.add_item.call_args.kwargs
        assert kwargs["service_name"] == "Wound Dressing"
        assert kwargs["quantity"] == Decimal("2")
        assert kwargs["unit_price"] == Decimal("1500")
        assert kwargs["service_delivery_point_id"] == 8
        assert kwargs["rendered_by_user_id"] == 42
        assert kwargs["source_reference"] == "QUEUE-SDP-8"
        assert result["recorded"] == 1
        assert "billing_summary" in result

    def test_source_reference_without_sdp(self):
        service = _make_service(visit=VISIT)
        service._active_visit_billing = MagicMock(return_value=None)
        service.repository.create_billing.return_value = SimpleNamespace(
            id=7, status=str(BillingStatus.OPEN)
        )
        service.record_visit_services(1, [{"service_name": "Injection"}])
        assert service.repository.add_item.call_args.kwargs["source_reference"] == "QUEUE"


class TestBillableServiceDefaults:
    def test_resolves_name_code_and_price_from_catalogue(self):
        svc = SimpleNamespace(
            id=3, name="Malaria RDT", code="LAB-MAL", default_price=Decimal("2500"),
            is_deleted=False,
        )
        service = _make_service(visit=VISIT, svc=svc)
        service._active_visit_billing = MagicMock(return_value=None)
        service.repository.create_billing.return_value = SimpleNamespace(
            id=7, status=str(BillingStatus.OPEN)
        )

        service.record_visit_services(
            1, [{"billable_service_id": 3, "quantity": 1}],
            service_delivery_point_id=8,
        )

        kwargs = service.repository.add_item.call_args.kwargs
        assert kwargs["service_name"] == "Malaria RDT"
        assert kwargs["service_code"] == "LAB-MAL"
        assert kwargs["unit_price"] == Decimal("2500")
        assert kwargs["billable_service_id"] == 3

    def test_explicit_price_overrides_catalogue(self):
        svc = SimpleNamespace(
            id=3, name="Malaria RDT", code="LAB-MAL", default_price=Decimal("2500"),
            is_deleted=False,
        )
        service = _make_service(visit=VISIT, svc=svc)
        service._active_visit_billing = MagicMock(return_value=None)
        service.repository.create_billing.return_value = SimpleNamespace(
            id=7, status=str(BillingStatus.OPEN)
        )
        service.record_visit_services(
            1, [{"billable_service_id": 3, "unit_price": "1800"}]
        )
        assert service.repository.add_item.call_args.kwargs["unit_price"] == Decimal("1800")


class TestChargeSheetReuse:
    def test_reuses_open_charge_sheet(self):
        service = _make_service(visit=VISIT)
        open_billing = SimpleNamespace(id=5, status=str(BillingStatus.OPEN))
        service._active_visit_billing = MagicMock(return_value=open_billing)

        service.record_visit_services(1, [{"service_name": "Dressing"}])

        # Existing OPEN sheet reused — no new billing created.
        service.repository.create_billing.assert_not_called()
        assert service.repository.add_item.call_args.kwargs["billing"] is open_billing

    def test_opens_new_sheet_when_existing_is_finalised(self):
        service = _make_service(visit=VISIT)
        finalised = SimpleNamespace(id=5, status="INVOICED")
        service._active_visit_billing = MagicMock(return_value=finalised)
        service.repository.create_billing.return_value = SimpleNamespace(
            id=9, status=str(BillingStatus.OPEN)
        )

        service.record_visit_services(1, [{"service_name": "Dressing"}])

        service.repository.create_billing.assert_called_once()
        assert service.repository.add_item.call_args.kwargs["billing"].id == 9


class TestMultipleLines:
    def test_records_each_line(self):
        service = _make_service(visit=VISIT)
        service._active_visit_billing = MagicMock(return_value=SimpleNamespace(
            id=5, status=str(BillingStatus.OPEN)))
        result = service.record_visit_services(
            1,
            [
                {"service_name": "Dressing", "unit_price": "1000"},
                {"service_name": "Injection", "unit_price": "500"},
                {"service_name": "Consult", "unit_price": "3000"},
            ],
        )
        assert service.repository.add_item.call_count == 3
        assert result["recorded"] == 3
