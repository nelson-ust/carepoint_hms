# app/tests/integration/test_clinic_flow_seamless.py
"""
Integration tests for the seamless Service Desk clinic flow.

Covers the behaviour the Service Desk console relies on:
  * a templated visit materialises a flow step for EVERY mapped service
    delivery point up front, and `POST /visits/{id}/advance` walks the patient
    from one desk to the next — raising a WAITING queue ticket at each desk
    (queue-at-every-SDP) until the final stage ends the visit;
  * triage vitals expose the auto-computed MEWS score;
  * `GET /queue/my-service-points` resolves the signed-in provider's assigned
    desk(s) and is empty for an unassigned principal.

These complement the deeper, manually-routed walkthrough in
``test_clinic_visit_workflow.py``.
"""
from __future__ import annotations

import pytest

from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)

API = "/api/v1"


@pytest.fixture()
def auth_header(client, admin_user):
    res = _login(client, admin_user["username"], admin_user["password"])
    token = res.json()["tokens"]["access_token"]
    return _bearer_headers(token)


def _make_sdp(client, headers, name: str, code_prefix: str, sp_type: str) -> int:
    res = client.post(
        f"{API}/service-delivery-points/",
        json={"name": name, "code": _unique(code_prefix), "service_point_type": sp_type,
              "supports_walk_in": True, "supports_appointments": True},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _register_patient(client, headers, **overrides) -> int:
    payload = {
        "first_name": "Flow",
        "last_name": "Patient",
        "gender": "FEMALE",
        "date_of_birth": "1990-01-01",
        "phone_number": "08000000000",
        "hospital_number": _unique("HN-SEAM"),
    }
    payload.update(overrides)
    res = client.post(
        f"{API}/patients/?force_create_if_possible_duplicate=true",
        json=payload, headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["patient_id"]


def _waiting_ticket_for_visit(client, headers, sdp_id: int, visit_id: int):
    """The WAITING queue ticket a visit holds at a given service delivery point."""
    res = client.get(
        f"{API}/queue/service-points/{sdp_id}/tickets?statuses=WAITING",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    for t in res.json()["items"]:
        if t["visit_id"] == visit_id:
            return t
    return None


class TestSeamlessClinicFlow:
    def test_pathway_auto_advance_queues_at_every_sdp(self, client, auth_header):
        # --- Service delivery points: one desk per stage ----------------
        reg = _make_sdp(client, auth_header, "Front Desk", "SDP-REG", "REGISTRATION")
        triage = _make_sdp(client, auth_header, "Triage", "SDP-TRI", "TRIAGE")
        clinic = _make_sdp(client, auth_header, "Consulting Room", "SDP-CLN", "CLINIC")
        lab = _make_sdp(client, auth_header, "Laboratory", "SDP-LAB", "LABORATORY")
        pharmacy = _make_sdp(client, auth_header, "Pharmacy", "SDP-PHA", "PHARMACY")
        cashier = _make_sdp(client, auth_header, "Cashier", "SDP-CSH", "CASHIER")
        ordered = [reg, triage, clinic, lab, pharmacy, cashier]

        # --- A pathway template mapping those desks, in order -----------
        tmpl_res = client.post(
            f"{API}/visit-flows/combined-create",
            json={
                "template": {"name": _unique("Seamless OPD"), "code": _unique("SEAM"), "is_default": False},
                "template_steps": [
                    {"service_delivery_point_id": sdp, "step_order": i + 1}
                    for i, sdp in enumerate(ordered)
                ],
            },
            headers=auth_header,
        )
        assert tmpl_res.status_code == 201, tmpl_res.text
        template_id = tmpl_res.json()["template"]["id"]

        # --- Register a self-pay patient (no insurance override) --------
        patient_id = _register_patient(client, auth_header)

        # --- Initiate the visit on the pathway --------------------------
        init = client.post(
            f"{API}/visits/initiate",
            json={
                "patient_id": patient_id,
                "visit_reason": "Headache, BP review",
                "priority": "NORMAL",
                "first_service_delivery_point_id": reg,
                "visit_flow_template_id": template_id,
            },
            headers=auth_header,
        )
        assert init.status_code == 201, init.text
        visit_id = init.json()["visit"]["id"]

        # Every mapped desk has a flow step up front (queue-at-every-SDP).
        detailed = client.get(f"{API}/visits/{visit_id}/detailed", headers=auth_header)
        assert detailed.status_code == 200, detailed.text
        steps = detailed.json()["flow_steps"]
        assert [s["service_delivery_point_id"] for s in sorted(steps, key=lambda s: s["step_order"])] == ordered

        # The patient is queued at the first desk (Registration).
        assert _waiting_ticket_for_visit(client, auth_header, reg, visit_id) is not None

        # --- Advance through every remaining desk -----------------------
        for sdp in ordered[1:]:
            res = client.post(
                f"{API}/visits/{visit_id}/advance",
                json={"action": "complete"},
                headers=auth_header,
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["next_step"] is not None, f"expected a next step routing to {sdp}"
            assert body["next_step"]["service_delivery_point_id"] == sdp
            # A WAITING ticket was raised at this desk — the patient queues here.
            assert _waiting_ticket_for_visit(client, auth_header, sdp, visit_id) is not None, (
                f"no WAITING ticket at sdp {sdp}"
            )
            assert body["visit"]["current_service_delivery_point_id"] == sdp

        # --- One more advance past the last desk ends the visit ---------
        final = client.post(
            f"{API}/visits/{visit_id}/advance",
            json={"action": "complete"},
            headers=auth_header,
        )
        assert final.status_code == 200, final.text
        fbody = final.json()
        assert fbody["next_step"] is None
        assert fbody["visit"]["status"] == "COMPLETED"
        assert fbody["visit"].get("check_out_time") is not None

    def test_triage_vitals_expose_mews(self, client, auth_header):
        triage = _make_sdp(client, auth_header, "Triage", "SDP-TRI", "TRIAGE")
        patient_id = _register_patient(client, auth_header)
        init = client.post(
            f"{API}/visits/initiate",
            json={
                "patient_id": patient_id,
                "visit_reason": "Fever",
                "priority": "NORMAL",
                "first_service_delivery_point_id": triage,
            },
            headers=auth_header,
        )
        assert init.status_code == 201, init.text
        visit_id = init.json()["visit"]["id"]

        vitals = client.post(
            f"{API}/vital-signs/",
            json={
                "visit_id": visit_id,
                "pulse_rate": 72,
                "respiratory_rate": 16,
                "systolic_bp": 130,
                "diastolic_bp": 84,
                "temperature_celsius": 36.8,
                "oxygen_saturation": 99,
            },
            headers=auth_header,
        )
        assert vitals.status_code == 201, vitals.text
        # RR 15-20 scores 1, all other inputs are normal -> MEWS 1.
        assert vitals.json()["vital_sign"]["mews_score"] == 1

        listed = client.get(f"{API}/vital-signs/visits/{visit_id}", headers=auth_header)
        assert listed.status_code == 200, listed.text
        assert listed.json()["items"][0]["mews_score"] == 1

    def test_my_service_points_resolves_assignment(self, client, auth_header, make_staff, make_user):
        # An admin (no desk assignment) sees none.
        admin_res = client.get(f"{API}/queue/my-service-points", headers=auth_header)
        assert admin_res.status_code == 200, admin_res.text
        assert admin_res.json()["items"] == []

        # A nurse assigned to Triage sees exactly that desk.
        triage = _make_sdp(client, auth_header, "Triage", "SDP-TRI", "TRIAGE")
        nurse = make_staff(job_title="Triage Nurse", user=make_user(role_codes=["NURSE"]))
        assign = client.post(
            f"{API}/service-delivery-points/{triage}/assign-staff",
            json={"staff_profile_ids": [nurse.id]},
            headers=auth_header,
        )
        assert assign.status_code in (200, 201), assign.text

        nurse_login = _login(client, nurse.user.username, "Password123!")
        nurse_header = _bearer_headers(nurse_login.json()["tokens"]["access_token"])

        mine = client.get(f"{API}/queue/my-service-points", headers=nurse_header)
        assert mine.status_code == 200, mine.text
        ids = [p["id"] for p in mine.json()["items"]]
        assert triage in ids
        assert all(p["service_point_type"] == "TRIAGE" for p in mine.json()["items"] if p["id"] == triage)

        # The assigned desk's worklist is reachable for that provider.
        wl = client.get(f"{API}/queue/my-worklist", headers=nurse_header)
        assert wl.status_code == 200, wl.text
        assert wl.json()["service_delivery_point_id"] == triage
