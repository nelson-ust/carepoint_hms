# app/tests/unit/test_finance_dashboard.py
"""Tests for the consolidated Finance command-center dashboard endpoint
(GET /accounting-ext/finance-dashboard)."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.enums import InvoiceStatus, PaymentStatus
from app.dependencies.auth import get_current_active_user
from app.models.base import TenantBase
from app.models.all_models import Invoice, Patient, Payment, User


class _NullTenantRepo:
    def __init__(self, _db): pass
    def get_tenant_by_code(self, *_a, **_k): return None
    def get_tenant_by_domain(self, *_a, **_k): return None
    def get_tenant_by_id(self, *_a, **_k): return None


@contextmanager
def _null_master_db():
    yield None


@pytest.fixture(autouse=True)
def _stub_tenant_resolution(monkeypatch):
    import app.middleware.tenant_middleware as tm
    monkeypatch.setattr(tm, "get_master_db_context", _null_master_db)
    monkeypatch.setattr(tm, "TenantRepository", _NullTenantRepo)
    yield


@pytest.fixture(scope="module")
def client_and_session():
    from app.main import app
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TenantBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()

    def override_get_db():
        yield session

    stub = User(username="fin", email="fin@example.com", password_hash="x",
                first_name="F", last_name="Admin", is_superuser=True)
    session.add(stub)
    session.flush()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_active_user] = lambda: stub
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client, session
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_active_user, None)
        session.close()


def _seed(session):
    now = datetime.now(timezone.utc)
    p = Patient(global_patient_id="GP-FIN-1", hospital_number="HN-FIN-1",
                first_name="Fin", last_name="Patient")
    session.add(p)
    session.flush()

    # An overdue, partly-unpaid invoice.
    inv = Invoice(
        patient_id=p.id, invoice_no="INV-FIN-1", status=InvoiceStatus.ISSUED,
        invoice_date=now, due_date=now - timedelta(days=45),
        subtotal_amount=Decimal("100000"), total_amount=Decimal("100000"),
        amount_paid=Decimal("30000"), balance_due=Decimal("70000"),
    )
    session.add(inv)
    session.flush()

    pay = Payment(invoice_id=inv.id, payment_reference="PAY-FIN-1",
                  amount=Decimal("30000"), payment_status=PaymentStatus.SUCCESSFUL,
                  paid_at=now, currency="NGN")
    session.add(pay)
    session.commit()


def test_finance_dashboard_requires_auth():
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as anon:
        assert anon.get("/api/v1/accounting-ext/finance-dashboard").status_code in (401, 403)


def test_finance_dashboard_aggregates(client_and_session):
    client, session = client_and_session
    _seed(session)

    r = client.get("/api/v1/accounting-ext/finance-dashboard")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    k = data["kpis"]

    # Billed revenue and collections picked up for the current year.
    assert float(k["revenue_billed_ytd"]) >= 100000
    assert float(k["collected_ytd"]) >= 30000

    # Receivables + overdue reflect the unpaid balance.
    assert float(k["ar_outstanding"]) >= 70000
    assert float(k["ar_overdue"]) >= 70000

    # The 45-day-overdue balance lands in an aged bucket, not "current".
    assert float(data["ar_aging"]["d31_60"]) >= 70000
    assert float(data["ar_aging"]["current"]) == 0

    # An overdue-invoice alert is surfaced.
    assert any("overdue" in a["title"].lower() for a in data["alerts"])

    # Structural fields present.
    assert "trend" in data and isinstance(data["trend"], list)
    assert "ar_segments" in data
    assert set(["cash_on_hand", "ap_outstanding", "net_working_position"]).issubset(k.keys())
