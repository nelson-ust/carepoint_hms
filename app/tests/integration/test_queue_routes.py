# app/tests/integration/test_queue_routes.py
from __future__ import annotations

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
def test_visit(client, auth_header):
    # Create patient with unique names + force_create
    hospital_number = _unique("QUEUE-PAT")
    p_payload = {
        "first_name": _unique("Queue"),
        "last_name": _unique("Patient"),
        "hospital_number": hospital_number,
        "gender": "FEMALE"
    }
    p_res = client.post(
        "/api/v1/patients/?force_create_if_possible_duplicate=true",
        json=p_payload, headers=auth_header,
    )
    patient_id = p_res.json()["patient_id"]

    # Get SDP
    sdp_res = client.get("/api/v1/service-delivery-points/", headers=auth_header)
    sdps = sdp_res.json()["items"]
    if sdps:
        sdp_id = sdps[0]["id"]
    else:
        sdp_payload = {
            "name": "Queue Clinic",
            "code": _unique("SDP-QUEUE"),
            "service_point_type": "CLINIC"
        }
        sdp_res = client.post("/api/v1/service-delivery-points/", json=sdp_payload, headers=auth_header)
        sdp_id = sdp_res.json()["id"]

    # Initiate visit
    init_payload = {
        "patient_id": patient_id,
        "first_service_delivery_point_id": sdp_id,
        "create_queue_ticket": True
    }
    v_res = client.post("/api/v1/visits/initiate", json=init_payload, headers=auth_header)
    return v_res.json()

class TestQueueLifecycle:
    def test_get_worklist_includes_history_fields(self, client, auth_header, test_visit):
        sdp_id = test_visit["visit"]["first_service_delivery_point_id"]
        response = client.get(f"/api/v1/queue/service-points/{sdp_id}/worklist", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        
        # Check that previous_steps field exists in serialized tickets
        tickets = data.get("waiting", [])
        if tickets:
            assert "previous_steps" in tickets[0]
            assert isinstance(tickets[0]["previous_steps"], list)

    def test_call_ticket(self, client, auth_header, test_visit):
        ticket_id = test_visit["first_queue_ticket"]["id"]
        response = client.post(f"/api/v1/queue/tickets/{ticket_id}/call", json={}, headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["ticket"]["status"] == "CALLED"
        assert "previous_steps" in data["ticket"]

    def test_start_serving_ticket(self, client, auth_header, test_visit):
        ticket_id = test_visit["first_queue_ticket"]["id"]
        # Must call first
        client.post(f"/api/v1/queue/tickets/{ticket_id}/call", json={}, headers=auth_header)
        
        response = client.post(f"/api/v1/queue/tickets/{ticket_id}/serve", json={}, headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["ticket"]["status"] == "SERVING"

    def test_complete_ticket(self, client, auth_header, test_visit):
        ticket_id = test_visit["first_queue_ticket"]["id"]
        # Transition: WAITING -> CALLED -> SERVING -> SERVED
        client.post(f"/api/v1/queue/tickets/{ticket_id}/call", json={}, headers=auth_header)
        client.post(f"/api/v1/queue/tickets/{ticket_id}/serve", json={}, headers=auth_header)
        
        response = client.post(f"/api/v1/queue/tickets/{ticket_id}/complete", json={}, headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["ticket"]["status"] == "SERVED"

    def test_complete_and_route_populates_history_field(self, client, auth_header, test_visit):
        ticket_id = test_visit["first_queue_ticket"]["id"]
        
        # Create target SDP (Laboratory)
        sdp_payload = {
            "name": "Central Laboratory",
            "code": _unique("LAB"),
            "service_point_type": "LABORATORY"
        }
        sdp_res = client.post("/api/v1/service-delivery-points/", json=sdp_payload, headers=auth_header)
        target_sdp_id = sdp_res.json()["id"]

        # Serve and Route
        client.post(f"/api/v1/queue/tickets/{ticket_id}/call", json={}, headers=auth_header)
        client.post(f"/api/v1/queue/tickets/{ticket_id}/serve", json={}, headers=auth_header)
        
        payload = {"target_service_delivery_point_id": target_sdp_id}
        route_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/complete-and-route", json=payload, headers=auth_header)
        assert route_res.status_code == 200
        new_ticket = route_res.json()["ticket"]
        
        # Verify history field exists
        assert "previous_steps" in new_ticket
        assert isinstance(new_ticket["previous_steps"], list)
