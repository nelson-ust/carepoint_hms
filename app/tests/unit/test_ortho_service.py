# app/tests/unit/test_ortho_service.py
"""Endpoint + service tests for the Orthopaedics clinic module."""
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
    p = Patient(global_patient_id=f"GP-ORTHO-{n}", hospital_number=f"HN-ORTHO-{n}",
                first_name="Ortho", last_name=f"Patient{n}")
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

    stub = User(username="ortho", email="ortho@example.com", password_hash="x",
                first_name="O", last_name="Admin", is_superuser=True)
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


def test_ortho_endpoints_require_auth():
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as anon:
        assert anon.get("/api/v1/orthopaedics/assessments").status_code in (401, 403)


def test_ortho_assessment_fracture_cast_flow(client_and_session):
    client, session = client_and_session
    pid = _make_patient(session, 1)

    # Create an assessment
    r = client.post("/api/v1/orthopaedics/assessments", json={
        "patient_id": pid, "region": "Right wrist", "laterality": "RIGHT",
        "chief_complaint": "Fall on outstretched hand", "pain_score": 7})
    assert r.status_code == 201, r.text
    a = r.json()["data"]
    assert a["laterality"] == "RIGHT"
    assert a["pain_score"] == 7
    aid = a["id"]

    # Add a fracture
    r = client.post(f"/api/v1/orthopaedics/assessments/{aid}/fractures", json={
        "bone": "Distal radius", "side": "RIGHT", "pattern": "Transverse",
        "is_displaced": True, "management": "CONSERVATIVE"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert len(data["fractures"]) == 1
    assert data["fractures"][0]["is_displaced"] is True

    # Add an immobilisation (cast)
    r = client.post(f"/api/v1/orthopaedics/assessments/{aid}/immobilisations", json={
        "device_type": "Plaster cast", "body_part": "Forearm", "side": "RIGHT"})
    assert r.status_code == 200, r.text
    cast = r.json()["data"]["immobilisations"][0]
    assert cast["active"] is True
    cast_id = cast["id"]

    # Remove (take off) the cast
    r = client.post(f"/api/v1/orthopaedics/immobilisations/{cast_id}/remove", json={})
    assert r.status_code == 200, r.text
    removed = next(m for m in r.json()["data"]["immobilisations"] if m["id"] == cast_id)
    assert removed["active"] is False
    assert removed["removed_date"] is not None


def test_ortho_procedure_and_stats(client_and_session):
    client, session = client_and_session
    pid = _make_patient(session, 2)
    aid = client.post("/api/v1/orthopaedics/assessments", json={"patient_id": pid}).json()["data"]["id"]

    r = client.post("/api/v1/orthopaedics/procedures", json={
        "patient_id": pid, "assessment_id": aid,
        "procedure_name": "Closed reduction & cast", "laterality": "RIGHT", "cost": 40000})
    assert r.status_code == 201, r.text
    proc = r.json()["data"]
    assert proc["status"] == "PLANNED"

    r = client.patch(f"/api/v1/orthopaedics/procedures/{proc['id']}", json={"status": "COMPLETED"})
    assert r.status_code == 200
    assert r.json()["data"]["performed_date"] is not None

    r = client.get("/api/v1/orthopaedics/stats")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["assessments_total"] >= 1
    assert data["procedures_completed"] >= 1
    assert float(data["completed_revenue"]) >= 40000


def test_ortho_error_responses(client_and_session):
    client, _ = client_and_session
    assert client.get("/api/v1/orthopaedics/assessments/999999").status_code == 404
    assert client.post("/api/v1/orthopaedics/assessments", json={}).status_code == 422
    assert client.post("/api/v1/orthopaedics/assessments", json={"patient_id": 666666}).status_code == 404
