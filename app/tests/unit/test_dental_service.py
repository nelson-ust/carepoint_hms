# app/tests/unit/test_dental_service.py
"""
Endpoint + service tests for the Dental clinic module.

Runs the real FastAPI app against an in-memory SQLite DB with the full tenant
schema, overriding ``get_db`` and ``get_current_active_user`` (a superuser, so
the DENTAL_* permission deps short-circuit). Mirrors test_finance_endpoints.py.
"""
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.base import TenantBase
from app.models.all_models import Patient, User


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


def _make_patient(session, n=1) -> int:
    p = Patient(
        global_patient_id=f"GP-DENT-{n}",
        hospital_number=f"HN-DENT-{n}",
        first_name="Dental",
        last_name=f"Patient{n}",
    )
    session.add(p)
    session.commit()
    return p.id


@pytest.fixture(scope="module")
def client_and_session():
    from app.main import app

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TenantBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()

    def override_get_db():
        yield session

    stub = User(username="dent", email="dent@example.com", password_hash="x",
                first_name="D", last_name="Admin", is_superuser=True)
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


def test_dental_endpoints_require_auth():
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as anon:
        r = anon.get("/api/v1/dental/charts")
        assert r.status_code in (401, 403)


def test_dental_chart_and_odontogram_flow(client_and_session):
    client, session = client_and_session
    pid = _make_patient(session, 1)

    # Create a chart
    r = client.post("/api/v1/dental/charts", json={"patient_id": pid, "chief_complaint": "Toothache"})
    assert r.status_code == 201, r.text
    chart = r.json()["data"]
    assert chart["status"] == "OPEN"
    assert chart["patient"]["id"] == pid
    cid = chart["id"]

    # List charts for the patient
    r = client.get("/api/v1/dental/charts", params={"patient_id": pid})
    assert r.status_code == 200
    assert any(c["id"] == cid for c in r.json()["items"])

    # Chart a couple of teeth (odontogram upsert)
    r = client.put(f"/api/v1/dental/charts/{cid}/teeth", json={"teeth": [
        {"tooth_number": 36, "condition": "CARIES", "surfaces": "MOD"},
        {"tooth_number": 11, "condition": "CROWN"},
    ]})
    assert r.status_code == 200, r.text
    teeth = {t["tooth_number"]: t for t in r.json()["data"]["teeth"]}
    assert teeth[36]["condition"] == "CARIES"
    assert teeth[36]["surfaces"] == "MOD"
    assert teeth[11]["condition"] == "CROWN"

    # Clearing a tooth (HEALTHY, no surfaces) removes it from the chart
    r = client.put(f"/api/v1/dental/charts/{cid}/teeth", json={"teeth": [
        {"tooth_number": 11, "condition": "HEALTHY"},
    ]})
    assert r.status_code == 200
    nums = {t["tooth_number"] for t in r.json()["data"]["teeth"]}
    assert 11 not in nums and 36 in nums


def test_dental_procedure_lifecycle_and_stats(client_and_session):
    client, session = client_and_session
    pid = _make_patient(session, 2)
    cid = client.post("/api/v1/dental/charts", json={"patient_id": pid}).json()["data"]["id"]

    # Add a planned procedure
    r = client.post("/api/v1/dental/procedures", json={
        "patient_id": pid, "chart_id": cid, "procedure_name": "Composite restoration",
        "tooth_number": 36, "cost": 15000})
    assert r.status_code == 201, r.text
    proc = r.json()["data"]
    assert proc["status"] == "PLANNED"
    assert proc["cost"] == "15000.00" or proc["cost"] == "15000"

    # Complete it -> performed_date auto-set
    r = client.patch(f"/api/v1/dental/procedures/{proc['id']}", json={"status": "COMPLETED"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "COMPLETED"
    assert r.json()["data"]["performed_date"] is not None

    # Stats reflect the completed procedure + revenue
    r = client.get("/api/v1/dental/stats")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["procedures_completed"] >= 1
    assert float(data["completed_revenue"]) >= 15000

    # Worklist lists recent charts
    r = client.get("/api/v1/dental/worklist")
    assert r.status_code == 200
    assert isinstance(r.json()["items"], list)


def test_dental_error_responses(client_and_session):
    client, _ = client_and_session
    # Unknown chart -> 404
    r = client.get("/api/v1/dental/charts/999999")
    assert r.status_code == 404
    # Missing patient_id -> 422 schema validation
    r = client.post("/api/v1/dental/charts", json={})
    assert r.status_code == 422
    # Non-existent patient -> 404 business rule
    r = client.post("/api/v1/dental/charts", json={"patient_id": 888888})
    assert r.status_code == 404
