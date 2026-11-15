# app/tests/unit/test_eye_service.py
"""Endpoint + service tests for the Eye / Ophthalmology clinic module."""
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
    p = Patient(global_patient_id=f"GP-EYE-{n}", hospital_number=f"HN-EYE-{n}",
                first_name="Eye", last_name=f"Patient{n}")
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

    stub = User(username="eye", email="eye@example.com", password_hash="x",
                first_name="E", last_name="Admin", is_superuser=True)
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


def test_eye_endpoints_require_auth():
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as anon:
        assert anon.get("/api/v1/eye-clinic/exams").status_code in (401, 403)


def test_eye_exam_and_prescription_flow(client_and_session):
    client, session = client_and_session
    pid = _make_patient(session, 1)

    # Create an exam with acuity + refraction + IOP
    r = client.post("/api/v1/eye-clinic/exams", json={
        "patient_id": pid, "chief_complaint": "Blurred distance vision",
        "va_dist_unaided_od": "6/12", "va_dist_unaided_os": "6/9",
        "ref_sphere_od": "-1.25", "ref_cyl_od": "-0.50", "ref_axis_od": 180,
        "iop_od": "16", "iop_os": "15", "iop_method": "GOLDMANN"})
    assert r.status_code == 201, r.text
    exam = r.json()["data"]
    assert exam["status"] == "OPEN"
    assert exam["va_dist_unaided_od"] == "6/12"
    assert exam["ref_axis_od"] == 180
    eid = exam["id"]

    # Update the exam (subjective refraction + impression)
    r = client.patch(f"/api/v1/eye-clinic/exams/{eid}", json={
        "impression": "Myopic astigmatism OU", "ref_sphere_os": "-0.75"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["impression"] == "Myopic astigmatism OU"

    # Issue a spectacle prescription
    r = client.post("/api/v1/eye-clinic/prescriptions", json={
        "patient_id": pid, "exam_id": eid,
        "od_sphere": "-1.25", "od_cyl": "-0.50", "od_axis": 180,
        "os_sphere": "-0.75", "pd": "63", "lens_type": "SINGLE_VISION",
        "usage": "Constant"})
    assert r.status_code == 201, r.text
    rx = r.json()["data"]
    assert rx["lens_type"] == "SINGLE_VISION"
    assert rx["od_axis"] == 180

    # Exam detail now carries the prescription
    r = client.get(f"/api/v1/eye-clinic/exams/{eid}")
    assert r.status_code == 200
    assert len(r.json()["data"]["prescriptions"]) == 1


def test_eye_stats_flag_raised_iop(client_and_session):
    client, session = client_and_session
    pid = _make_patient(session, 2)
    # IOP > 21 should be flagged
    client.post("/api/v1/eye-clinic/exams", json={"patient_id": pid, "iop_od": "28"})
    r = client.get("/api/v1/eye-clinic/stats")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["exams_total"] >= 1
    assert data["raised_iop_flagged"] >= 1


def test_eye_error_responses(client_and_session):
    client, _ = client_and_session
    assert client.get("/api/v1/eye-clinic/exams/999999").status_code == 404
    assert client.post("/api/v1/eye-clinic/exams", json={}).status_code == 422
    assert client.post("/api/v1/eye-clinic/exams", json={"patient_id": 777777}).status_code == 404
