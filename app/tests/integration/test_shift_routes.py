# app/tests/integration/test_shift_routes.py
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)


@pytest.fixture()
def auth_header(client, admin_user):
    login_res = _login(client, admin_user["username"], admin_user["password"])
    token = login_res.json()["tokens"]["access_token"]
    return _bearer_headers(token)


@pytest.fixture()
def department_id(db_session):
    """Return the id of the first department (seeded by baseline)."""
    from app.models.all_models import Department
    dept = db_session.query(Department).first()
    if dept is None:
        pytest.skip("No departments seeded")
    return dept.id


class TestShiftDefinitionRoutes:
    def _create_definition(self, client, auth_header, department_id):
        payload = {
            "department_id": department_id,
            "name": _unique("Morning Shift"),
            "code": _unique("MORN"),
            "shift_type": "MORNING",
            "start_time": "07:00:00",
            "end_time": "15:00:00",
            "break_duration_minutes": 30,
        }
        response = client.post("/api/v1/shifts/definitions", json=payload, headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        return data["definition"]

    def test_create_definition(self, client, auth_header, department_id):
        self._create_definition(client, auth_header, department_id)

    def test_list_definitions(self, client, auth_header, department_id):
        self._create_definition(client, auth_header, department_id)
        response = client.get("/api/v1/shifts/definitions", headers=auth_header)
        assert response.status_code == 200
        assert "items" in response.json()
        assert response.json()["count"] >= 1

    def test_get_definition(self, client, auth_header, department_id):
        defn = self._create_definition(client, auth_header, department_id)
        response = client.get(f"/api/v1/shifts/definitions/{defn['id']}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["definition"]["id"] == defn["id"]

    def test_update_definition(self, client, auth_header, department_id):
        defn = self._create_definition(client, auth_header, department_id)
        response = client.patch(
            f"/api/v1/shifts/definitions/{defn['id']}",
            json={"break_duration_minutes": 45},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert response.json()["definition"]["break_duration_minutes"] == 45

    def test_delete_definition(self, client, auth_header, department_id):
        defn = self._create_definition(client, auth_header, department_id)
        response = client.delete(f"/api/v1/shifts/definitions/{defn['id']}", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_reject_anonymous(self, client):
        response = client.get("/api/v1/shifts/definitions")
        assert response.status_code == 401


class TestShiftAssignmentRoutes:
    def _create_definition(self, client, auth_header, department_id):
        payload = {
            "department_id": department_id,
            "name": _unique("Night Shift"),
            "code": _unique("NGT"),
            "shift_type": "NIGHT",
            "start_time": "22:00:00",
            "end_time": "06:00:00",
        }
        resp = client.post("/api/v1/shifts/definitions", json=payload, headers=auth_header)
        assert resp.status_code == 201
        return resp.json()["definition"]

    def _create_assignment(self, client, auth_header, department_id, staff_id):
        defn = self._create_definition(client, auth_header, department_id)
        payload = {
            "staff_profile_id": staff_id,
            "shift_definition_id": defn["id"],
            "shift_date": str(date.today() + timedelta(days=1)),
        }
        resp = client.post("/api/v1/shifts/assignments", json=payload, headers=auth_header)
        assert resp.status_code == 201
        return resp.json()["assignment"]

    def test_create_assignment(self, client, auth_header, department_id, make_staff):
        staff = make_staff()
        self._create_assignment(client, auth_header, department_id, staff.id)

    def test_list_assignments(self, client, auth_header, department_id, make_staff):
        staff = make_staff()
        self._create_assignment(client, auth_header, department_id, staff.id)
        response = client.get("/api/v1/shifts/assignments", headers=auth_header)
        assert response.status_code == 200
        assert response.json()["count"] >= 1

    def test_check_in_check_out(self, client, auth_header, department_id, make_staff):
        staff = make_staff()
        assignment = self._create_assignment(client, auth_header, department_id, staff.id)
        aid = assignment["id"]

        # Check in
        resp = client.post(f"/api/v1/shifts/assignments/{aid}/check-in", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["assignment"]["status"] == "ON_DUTY"

        # Check out
        resp = client.post(f"/api/v1/shifts/assignments/{aid}/check-out", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["assignment"]["status"] == "COMPLETED"

    def test_delete_assignment(self, client, auth_header, department_id, make_staff):
        staff = make_staff()
        assignment = self._create_assignment(client, auth_header, department_id, staff.id)
        resp = client.delete(f"/api/v1/shifts/assignments/{assignment['id']}", headers=auth_header)
        assert resp.status_code == 200


class TestShiftSwapRoutes:
    def _setup_swap(self, client, auth_header, department_id, make_staff):
        staff1 = make_staff()
        staff2 = make_staff()

        # Create a definition and assignment for staff1
        defn_payload = {
            "department_id": department_id,
            "name": _unique("Swap Shift"),
            "code": _unique("SWP"),
            "shift_type": "AFTERNOON",
            "start_time": "14:00:00",
            "end_time": "22:00:00",
        }
        defn_resp = client.post("/api/v1/shifts/definitions", json=defn_payload, headers=auth_header)
        defn = defn_resp.json()["definition"]

        assign_payload = {
            "staff_profile_id": staff1.id,
            "shift_definition_id": defn["id"],
            "shift_date": str(date.today() + timedelta(days=2)),
        }
        assign_resp = client.post("/api/v1/shifts/assignments", json=assign_payload, headers=auth_header)
        assignment = assign_resp.json()["assignment"]

        return assignment, staff2

    def test_create_swap_request(self, client, auth_header, department_id, make_staff):
        assignment, target_staff = self._setup_swap(client, auth_header, department_id, make_staff)
        payload = {
            "requester_assignment_id": assignment["id"],
            "target_staff_id": target_staff.id,
            "reason": "Personal conflict",
        }
        resp = client.post("/api/v1/shifts/swaps", json=payload, headers=auth_header)
        assert resp.status_code == 201
        assert resp.json()["swap_request"]["status"] == "PENDING"

    def test_approve_swap_request(self, client, auth_header, department_id, make_staff):
        assignment, target_staff = self._setup_swap(client, auth_header, department_id, make_staff)
        payload = {
            "requester_assignment_id": assignment["id"],
            "target_staff_id": target_staff.id,
        }
        create_resp = client.post("/api/v1/shifts/swaps", json=payload, headers=auth_header)
        swap_id = create_resp.json()["swap_request"]["id"]

        resp = client.post(f"/api/v1/shifts/swaps/{swap_id}/approve", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["swap_request"]["status"] == "APPROVED"

    def test_reject_swap_request(self, client, auth_header, department_id, make_staff):
        assignment, target_staff = self._setup_swap(client, auth_header, department_id, make_staff)
        payload = {
            "requester_assignment_id": assignment["id"],
            "target_staff_id": target_staff.id,
        }
        create_resp = client.post("/api/v1/shifts/swaps", json=payload, headers=auth_header)
        swap_id = create_resp.json()["swap_request"]["id"]

        resp = client.post(f"/api/v1/shifts/swaps/{swap_id}/reject", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["swap_request"]["status"] == "REJECTED"
