# app/tests/unit/test_finance_endpoints.py
"""
Endpoint integration tests for the HMO / banking / accounting-ext APIs.

Runs against the real FastAPI app with dependency overrides:
* ``get_db``  -> an in-memory SQLite session (full tenant schema)
* ``get_current_active_user`` -> a superuser stub (permission deps short-circuit)

Covers, per the definition of done:
* 401 for unauthenticated calls,
* happy paths that round-trip through service + DB,
* typed error responses (AppException -> 4xx JSON with a meaningful message),
* presence in the OpenAPI schema.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from contextlib import contextmanager

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.base import TenantBase
from app.models.all_models import InsuranceProvider, User


# ---------------------------------------------------------------------------
# The TenantMiddleware resolves the tenant from the master (PostgreSQL)
# database on every request; these tests run on SQLite with no master DB, so
# we stub the middleware's module-level collaborators. With no tenant match
# and the TestClient's reserved "testserver" host, the middleware falls
# through to public access — exactly the code path we want.
# ---------------------------------------------------------------------------

class _NullTenantRepo:
    def __init__(self, _db):
        pass

    def get_tenant_by_code(self, *_a, **_k):
        return None

    def get_tenant_by_domain(self, *_a, **_k):
        return None

    def get_tenant_by_id(self, *_a, **_k):
        return None


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

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TenantBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()

    def override_get_db():
        yield session

    stub = User(
        username="tester",
        email="tester@example.com",
        password_hash="x",
        first_name="Test",
        last_name="Admin",
        is_superuser=True,
    )
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


def test_unauthenticated_requests_are_rejected():
    """Without the auth override, protected endpoints refuse anonymous calls."""
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as anon:
        for path in ("/api/v1/hmo/providers",
                     "/api/v1/banking/accounts",
                     "/api/v1/accounting-ext/cost-centers"):
            r = anon.get(path)
            assert r.status_code in (401, 403), f"{path} -> {r.status_code}"


def test_hmo_plan_lifecycle_via_api(client_and_session):
    client, session = client_and_session
    prov = InsuranceProvider(name="API Test HMO", code="API-HMO")
    session.add(prov)
    session.commit()

    r = client.get("/api/v1/hmo/providers")
    assert r.status_code == 200
    assert any(p["name"] == "API Test HMO" for p in r.json()["items"])

    r = client.post("/api/v1/hmo/plans", json={
        "insurance_provider_id": prov.id, "name": "API Gold", "code": "API-G",
        "coverage_type": "FEE_FOR_SERVICE",
        "default_coverage_percent": 90, "default_copay_flat": 500})
    assert r.status_code == 201, r.text
    plan = r.json()["plan"]
    assert plan["default_coverage_percent"].startswith("90")

    r = client.post("/api/v1/hmo/benefits", json={
        "hmo_plan_id": plan["id"], "category": "PHARMACY", "coverage_percent": 50})
    assert r.status_code == 201

    r = client.get(f"/api/v1/hmo/plans/{plan['id']}")
    assert r.status_code == 200
    assert len(r.json()["plan"]["benefits"]) == 1


def test_hmo_error_responses_are_typed(client_and_session):
    client, _ = client_and_session
    # Unknown plan -> 404 with a message, not a bare 500.
    r = client.get("/api/v1/hmo/plans/999999")
    assert r.status_code == 404
    body = r.json()
    assert "not found" in str(body).lower()
    # Invalid payload shape -> 422 from schema validation.
    r = client.post("/api/v1/hmo/capitation/run", json={
        "contract_id": 1, "period_code": "September"})
    assert r.status_code == 422
    # Business-rule violation -> 400 with detail.
    r = client.post("/api/v1/hmo/plans", json={"name": "No provider"})
    assert r.status_code == 400
    assert "required" in str(r.json()).lower()


def test_banking_flow_via_api(client_and_session):
    client, _ = client_and_session
    r = client.post("/api/v1/banking/accounts", json={
        "name": "API GTB", "bank_name": "GTBank",
        "account_number": "0011223344", "is_default": True})
    assert r.status_code == 201, r.text
    acct = r.json()["account"]
    assert acct["account_number_masked"].endswith("3344")
    assert acct["account_number_masked"].startswith("*")

    r = client.post("/api/v1/banking/deposits", json={
        "bank_account_id": acct["id"], "amount": 25000,
        "deposit_date": str(date.today())})
    assert r.status_code == 200, r.text
    assert r.json()["entry"]["status"] == "POSTED"

    r = client.get("/api/v1/banking/accounts")
    assert r.status_code == 200
    row = next(a for a in r.json()["items"] if a["id"] == acct["id"])
    assert Decimal(row["balance"]) == Decimal("25000.00")

    # Transfer to self is a typed 400.
    r = client.post("/api/v1/banking/transfers", json={
        "from_bank_account_id": acct["id"], "to_bank_account_id": acct["id"],
        "amount": 10, "transfer_date": str(date.today())})
    assert r.status_code == 400


def test_accounting_ext_config_and_mapping(client_and_session):
    client, _ = client_and_session
    r = client.post("/api/v1/accounting-ext/seed-default-coa")
    assert r.status_code == 200
    r = client.get("/api/v1/accounting-ext/system-accounts")
    assert r.status_code == 200
    keys = {m["key"] for m in r.json()["items"]}
    assert {"HMO_AR", "CAPITATION_AR", "PHARMACY_COGS", "VAT_PAYABLE"} <= keys

    r = client.put("/api/v1/accounting-ext/config", json={
        "journal_approval_threshold": 500000})
    assert r.status_code == 200
    assert r.json()["config"]["journal_approval_threshold"].startswith("500000")

    # Config change is audited (privileged action -> audit trail).
    r = client.get("/api/v1/accounting-ext/audit-log",
                   params={"entity_type": "accounting_config"})
    assert r.status_code == 200
    assert any(i["action"] == "ACCOUNTING_CONFIG_CHANGED" for i in r.json()["items"])

    r = client.get("/api/v1/accounting-ext/accounts/tree")
    assert r.status_code == 200
    assert len(r.json()["tree"]) > 0

    r = client.get("/api/v1/accounting-ext/reports/ar-segments")
    assert r.status_code == 200
    assert "patient_self_pay" in r.json()


def test_new_endpoints_are_in_openapi_schema(client_and_session):
    client, _ = client_and_session
    schema = client.get("/openapi.json").json()
    for path in ("/api/v1/hmo/providers",
                 "/api/v1/hmo/capitation/run",
                 "/api/v1/hmo/remittances/{advice_id}/allocate",
                 "/api/v1/banking/reconciliations",
                 "/api/v1/accounting-ext/reports/cash-flow",
                 "/api/v1/accounting/journal-entries/{entry_id}/approve"):
        assert path in schema["paths"], f"{path} missing from OpenAPI"


def test_statutory_endpoints(client_and_session):
    client, _ = client_and_session
    r = client.get("/api/v1/statutory/positions")
    assert r.status_code == 200
    types = {p["type"] for p in r.json()["items"]}
    assert {"PAYE", "PENSION", "NHF", "WHT", "VAT"} <= types

    # Record a manual WHT deduction, see it in the register.
    r = client.post("/api/v1/statutory/wht/records", json={
        "payee_name": "API Landlord", "gross_amount": 300000, "rate_percent": 10})
    assert r.status_code == 201, r.text
    assert r.json()["wht_amount"].startswith("30000")
    r = client.get("/api/v1/statutory/wht/register")
    assert any(w["payee_name"] == "API Landlord" for w in r.json()["items"])

    # Remitting with nothing outstanding is a typed 400 with guidance.
    r = client.post("/api/v1/statutory/remittances", json={
        "remittance_type": "NHF", "period_code": "2026-08",
        "paid_at": "2026-09-05"})
    assert r.status_code == 400
    assert "outstanding" in str(r.json()).lower() or "nothing" in str(r.json()).lower()

    # Unknown type & bad period are typed errors too.
    r = client.post("/api/v1/statutory/remittances", json={
        "remittance_type": "FANCY", "period_code": "2026-08", "paid_at": "2026-09-05"})
    assert r.status_code == 400
    r = client.get("/api/v1/statutory/schedules/PAYE", params={"period_code": "2026-08"})
    assert r.status_code == 200
    assert r.json()["count"] == 0
    r = client.get("/api/v1/statutory/schedules/BOGUS", params={"period_code": "2026-08"})
    assert r.status_code == 400
