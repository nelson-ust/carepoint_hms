# app/tests/integration/test_clinic_visit_workflow.py
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

def get_staff_token(client, staff_profile):
    """Log in as a staff user and return auth header."""
    # Assuming default password from conftest.py
    res = _login(client, staff_profile.user.username, "Password123!")
    token = res.json()["tokens"]["access_token"]
    return _bearer_headers(token)

def get_current_ticket(client, headers, sdp_id, visit_id):
    """Find the current WAITING ticket for a visit at an SDP."""
    res = client.get(f"/api/v1/queue/service-points/{sdp_id}/tickets?statuses=WAITING", headers=headers)
    assert res.status_code == 200
    tickets = res.json()["items"]
    for t in tickets:
        if t["visit_id"] == visit_id:
            return t
    return None

class TestClinicVisitWorkflow:
    """
    End-to-end integration test for the full patient visit lifecycle.
    """

    def test_full_patient_visit_workflow(self, client, auth_header, make_staff, make_user):
        # ============================================================
        # 1. STAFF SETUP (Clinical & Admin Actors)
        # ============================================================
        # 1a. Create Service Delivery Points (SDPs)
        triage_sdp_res = client.post("/api/v1/service-delivery-points/", json={
            "name": "Triage Room", "code": _unique("SDP-TRI"), "service_point_type": "TRIAGE"
        }, headers=auth_header)
        assert triage_sdp_res.status_code == 201
        triage_sdp_id = triage_sdp_res.json()["id"]

        consult_sdp_res = client.post("/api/v1/service-delivery-points/", json={
            "name": "Doctor Office", "code": _unique("SDP-DOC"), "service_point_type": "CLINIC"
        }, headers=auth_header)
        assert consult_sdp_res.status_code == 201
        consult_sdp_id = consult_sdp_res.json()["id"]

        billing_sdp_res = client.post("/api/v1/service-delivery-points/", json={
            "name": "Cash Office", "code": _unique("SDP-BIL"), "service_point_type": "CASHIER"
        }, headers=auth_header)
        assert billing_sdp_res.status_code == 201
        billing_sdp_id = billing_sdp_res.json()["id"]

        lab_sdp_res = client.post("/api/v1/service-delivery-points/", json={
            "name": "Main Lab", "code": _unique("SDP-LAB"), "service_point_type": "LABORATORY"
        }, headers=auth_header)
        assert lab_sdp_res.status_code == 201
        lab_sdp_id = lab_sdp_res.json()["id"]

        pharma_sdp_res = client.post("/api/v1/service-delivery-points/", json={
            "name": "Pharmacy Store", "code": _unique("SDP-PHA"), "service_point_type": "PHARMACY"
        }, headers=auth_header)
        assert pharma_sdp_res.status_code == 201
        pharma_sdp_id = pharma_sdp_res.json()["id"]

        # 1b. Create Staff Profiles and Assign to SDPs
        nurse = make_staff(job_title="Triage Nurse", service_delivery_point_id=triage_sdp_id, 
                           user=make_user(role_codes=["NURSE"]))
        doctor = make_staff(job_title="Consulting Doctor", service_delivery_point_id=consult_sdp_id, 
                            user=make_user(role_codes=["DOCTOR"]))
        lab_tech = make_staff(job_title="Lab Technician", service_delivery_point_id=lab_sdp_id, 
                              user=make_user(role_codes=["LAB_SCIENTIST"]))
        pharmacist = make_staff(job_title="Pharmacist", service_delivery_point_id=pharma_sdp_id, 
                                user=make_user(role_codes=["PHARMACIST"]))
        cashier = make_staff(job_title="Cashier", service_delivery_point_id=billing_sdp_id, 
                             user=make_user(role_codes=["CASHIER"]))

        # ============================================================
        # 2. CATALOG SETUP (Tests & Drugs)
        # ============================================================
        # Create a Lab Test
        lab_test_payload = {
            "name": _unique("Malaria Parasite Test"),
            "code": _unique("MP"),
            "sample_type": "BLOOD",
            "default_price": 1500.0
        }
        lt_res = client.post("/api/v1/lab/tests/", json=lab_test_payload, headers=auth_header)
        assert lt_res.status_code == 201
        lab_test_id = lt_res.json()["lab_test"]["id"]

        # Create a Drug
        drug_cat_res = client.post("/api/v1/drugs/categories", json={
            "name": _unique("Antimalarials"), "code": _unique("AMAL")
        }, headers=auth_header)
        assert drug_cat_res.status_code == 201
        drug_cat_id = drug_cat_res.json()["category"]["id"]

        drug_payload = {
            "name": _unique("Artemether-Lumefantrine"),
            "drug_category_id": drug_cat_id,
            "generic_name": "AL",
            "dosage_form": "Tablet",
            "unit_price": 2000.0
        }
        drug_res = client.post("/api/v1/drugs/", json=drug_payload, headers=auth_header)
        assert drug_res.status_code == 201
        drug_id = drug_res.json()["drug"]["id"]

        # Create a Store
        store_res = client.post("/api/v1/inventory/stores", json={
            "name": _unique("Main Pharmacy Store"), "code": _unique("STORE-PHA")
        }, headers=auth_header)
        assert store_res.status_code == 201
        store_id = store_res.json()["store"]["id"]
        
        # Add Stock
        stock_payload = {
            "store_id": store_id,
            "drug_id": drug_id,
            "item_name": "Artemether-Lumefantrine 1 tab",
            "item_type": "DRUG",
            "quantity_on_hand": 100,
            "batch_no": "BATCH-001",
            "expiry_date": "2030-01-01"
        }
        stock_res = client.post("/api/v1/inventory/items", json=stock_payload, headers=auth_header)
        assert stock_res.status_code == 201

        # ============================================================
        # 3. PATIENT REGISTRATION
        # ============================================================
        patient_payload = {
            "first_name": "Integration",
            "last_name": "Patient",
            "gender": "FEMALE",
            "date_of_birth": "1995-05-20",
            "phone_number": "09011223344",
            "hospital_number": _unique("HN-FLOW"),
            "registration_notes": "Registered for end-to-end test."
        }
        reg_res = client.post("/api/v1/patients/?force_create_if_possible_duplicate=true", 
                             json=patient_payload, headers=auth_header)
        assert reg_res.status_code == 201
        patient_id = reg_res.json()["patient_id"]

        # ============================================================
        # 4. VISIT INITIATION (Route to Triage)
        # ============================================================
        init_res = client.post("/api/v1/visits/initiate", json={
            "patient_id": patient_id,
            "visit_reason": "Severe headache and chills",
            "priority": "NORMAL",
            "first_service_delivery_point_id": triage_sdp_id
        }, headers=auth_header)
        assert init_res.status_code == 201
        visit_id = init_res.json()["visit"]["id"]

        # ============================================================
        # 5. TRIAGE & VITALS (Nurse Actions)
        # ============================================================
        nurse_header = get_staff_token(client, nurse)
        
        # Queue: Call & Serve
        ticket = get_current_ticket(client, nurse_header, triage_sdp_id, visit_id)
        assert ticket is not None, "Nurse: Ticket not found for visit"
        ticket_id = ticket["id"]
        
        call_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/call", json={}, headers=nurse_header)
        assert call_res.status_code == 200
        serve_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/serve", json={}, headers=nurse_header)
        assert serve_res.status_code == 200

        # Record Vitals
        vitals_payload = {
            "visit_id": visit_id,
            "recorded_by_staff_id": nurse.id,
            "temperature_celsius": 39.2,
            "pulse_rate": 88,
            "respiratory_rate": 20,
            "systolic_bp": 110,
            "diastolic_bp": 70,
            "pain_score": 6
        }
        vitals_res = client.post("/api/v1/vital-signs/", json=vitals_payload, headers=nurse_header)
        assert vitals_res.status_code == 201

        # Record Triage Assessment
        triage_payload = {
            "visit_id": visit_id,
            "chief_complaint": "High fever and joint pains",
            "priority": "HIGH",
            "assessed_by_staff_id": nurse.id
        }
        triage_res = client.post("/api/v1/triage/", json=triage_payload, headers=nurse_header)
        assert triage_res.status_code == 201

        # Queue: Complete and Route to Consultation
        route_payload = {"target_service_delivery_point_id": consult_sdp_id, "notes": "Vitals recorded"}
        client.post(f"/api/v1/queue/tickets/{ticket_id}/complete-and-route", json=route_payload, headers=nurse_header)

        # ============================================================
        # 6. CONSULTATION, DIAGNOSIS, ORDERS (Doctor Actions)
        # ============================================================
        doctor_header = get_staff_token(client, doctor)

        # Queue: Call & Serve
        ticket = get_current_ticket(client, doctor_header, consult_sdp_id, visit_id)
        assert ticket is not None, "Doctor: Ticket not found for visit"
        ticket_id = ticket["id"]
        
        call_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/call", json={}, headers=doctor_header)
        assert call_res.status_code == 200
        serve_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/serve", json={}, headers=doctor_header)
        assert serve_res.status_code == 200

        # Start Consultation
        consult_payload = {
            "visit_id": visit_id,
            "clinician_staff_id": doctor.id,
            "subjective_note": "Patient presents with high fever for 3 days.",
            "objective_note": "Patient looks pale and febrile."
        }
        consult_res = client.post("/api/v1/consultations/", json=consult_payload, headers=doctor_header)
        assert consult_res.status_code == 201
        consultation_id = consult_res.json()["consultation"]["id"]

        # Record Diagnosis
        diag_payload = {
            "visit_id": visit_id,
            "consultation_id": consultation_id,
            "diagnosis_code": "B54",
            "diagnosis_name": "Unspecified malaria",
            "diagnosis_type": "PROVISIONAL"
        }
        diag_res = client.post("/api/v1/diagnoses/", json=diag_payload, headers=doctor_header)
        assert diag_res.status_code == 201

        # Create Lab Order
        lab_order_payload = {
            "visit_id": visit_id,
            "consultation_id": consultation_id,
            "ordered_by_staff_id": doctor.id,
            "items": [{"lab_test_catalog_id": lab_test_id, "note": "Check for MP"}]
        }
        lo_res = client.post("/api/v1/lab/orders/", json=lab_order_payload, headers=doctor_header)
        assert lo_res.status_code == 201
        lab_order_id = lo_res.json()["lab_order"]["id"]
        lab_order_item_id = lo_res.json()["lab_order"]["items"][0]["id"]

        # Create Prescription
        prescription_payload = {
            "visit_id": visit_id,
            "consultation_id": consultation_id,
            "prescribed_by_staff_id": doctor.id,
            "items": [{
                "drug_id": drug_id,
                "dosage": "1 tab",
                "frequency": "BD",
                "duration": "3 days",
                "quantity_prescribed": 6
            }]
        }
        rx_res = client.post("/api/v1/prescriptions/", json=prescription_payload, headers=doctor_header)
        assert rx_res.status_code == 201
        prescription_id = rx_res.json()["prescription"]["id"]

        # Queue: Complete and Route to Billing
        route_payload = {"target_service_delivery_point_id": billing_sdp_id, "notes": "Proceed to payment"}
        client.post(f"/api/v1/queue/tickets/{ticket_id}/complete-and-route", json=route_payload, headers=doctor_header)

        # ============================================================
        # 7. BILLING & PAYMENT (Cashier Actions)
        # ============================================================
        cashier_header = get_staff_token(client, cashier)

        # Queue: Call & Serve
        ticket = get_current_ticket(client, cashier_header, billing_sdp_id, visit_id)
        assert ticket is not None, "Cashier: Ticket not found for visit"
        ticket_id = ticket["id"]
        
        call_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/call", json={}, headers=cashier_header)
        assert call_res.status_code == 200
        serve_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/serve", json={}, headers=cashier_header)
        assert serve_res.status_code == 200

        # Fetch billings
        billings_res = client.get(f"/api/v1/billing/visits/{visit_id}", headers=cashier_header)
        assert billings_res.status_code == 200, f"Cashier: Failed to fetch billings: {billings_res.text}"
        billings = billings_res.json()["items"]
        
        # Issue Invoices and Receive Payment
        for billing in billings:
            inv_res = client.post("/api/v1/invoices/issue-from-billing", 
                                 json={"billing_id": billing["id"]}, headers=cashier_header)
            invoice_id = inv_res.json()["invoice"]["id"]
            amount = inv_res.json()["invoice"]["total_amount"]
            
            pay_payload = {
                "invoice_id": invoice_id, "payment_method": "CASH",
                "amount": amount, "received_by_staff_id": cashier.id
            }
            client.post("/api/v1/payments/", json=pay_payload, headers=cashier_header)

        # Queue: Complete and Route to Lab
        route_payload = {"target_service_delivery_point_id": lab_sdp_id, "notes": "Payment confirmed"}
        client.post(f"/api/v1/queue/tickets/{ticket_id}/complete-and-route", json=route_payload, headers=cashier_header)

        # ============================================================
        # 8. LABORATORY (Lab Tech Actions)
        # ============================================================
        lab_header = get_staff_token(client, lab_tech)

        # Queue: Call & Serve
        ticket = get_current_ticket(client, lab_header, lab_sdp_id, visit_id)
        assert ticket is not None, "Lab: Ticket not found for visit"
        ticket_id = ticket["id"]
        
        call_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/call", json={}, headers=lab_header)
        assert call_res.status_code == 200
        serve_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/serve", json={}, headers=lab_header)
        assert serve_res.status_code == 200

        # Process Order
        coll_res = client.post(f"/api/v1/lab/orders/items/{lab_order_item_id}/collect-specimen", 
                   json={"specimen_id": "S123", "collected_by_staff_id": lab_tech.id}, headers=lab_header)
        assert coll_res.status_code == 200
        start_res = client.post(f"/api/v1/lab/orders/items/{lab_order_item_id}/start-processing", headers=lab_header)
        assert start_res.status_code == 200
        
        result_payload = {
            "visit_id": visit_id, "lab_order_id": lab_order_id, "lab_order_item_id": lab_order_item_id,
            "test_result": "Positive (+++)", "recorded_by_staff_id": lab_tech.id
        }
        res_res = client.post("/api/v1/lab/results/", json=result_payload, headers=lab_header)
        assert res_res.status_code == 201

        # Queue: Complete and Route to Pharmacy
        route_payload = {"target_service_delivery_point_id": pharma_sdp_id, "notes": "Result ready"}
        route_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/complete-and-route", json=route_payload, headers=lab_header)
        assert route_res.status_code == 200

        # ============================================================
        # 9. PHARMACY (Pharmacist Actions)
        # ============================================================
        pharma_header = get_staff_token(client, pharmacist)

        # Queue: Call & Serve
        ticket = get_current_ticket(client, pharma_header, pharma_sdp_id, visit_id)
        assert ticket is not None, "Pharmacy: Ticket not found for visit"
        ticket_id = ticket["id"]
        
        call_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/call", json={}, headers=pharma_header)
        assert call_res.status_code == 200
        serve_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/serve", json={}, headers=pharma_header)
        assert serve_res.status_code == 200

        # Dispense Drugs
        dispense_payload = {
            "visit_id": visit_id, "prescription_id": prescription_id, "dispensed_by_staff_id": pharmacist.id,
            "items": [{"prescription_item_id": rx_res.json()["prescription"]["items"][0]["id"], "quantity_dispensed": 6}]
        }
        disp_res = client.post("/api/v1/dispenses/", json=dispense_payload, headers=pharma_header)
        assert disp_res.status_code == 201

        # Queue: Complete and Route back to Doctor for finalization
        route_payload = {"target_service_delivery_point_id": consult_sdp_id, "notes": "Meds dispensed"}
        route_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/complete-and-route", json=route_payload, headers=pharma_header)
        assert route_res.status_code == 200

        # ============================================================
        # 10. FINALIZING CONSULTATION & VISIT (Doctor Actions)
        # ============================================================
        doctor_header = get_staff_token(client, doctor) # Reuse doctor token
        
        # Queue: Call & Serve (Second time for doctor)
        ticket = get_current_ticket(client, doctor_header, consult_sdp_id, visit_id)
        assert ticket is not None, "Doctor: Second ticket not found for visit"
        ticket_id = ticket["id"]
        
        call_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/call", json={}, headers=doctor_header)
        assert call_res.status_code == 200
        serve_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/serve", json={}, headers=doctor_header)
        assert serve_res.status_code == 200

        # Update Diagnosis
        diag_id = diag_res.json()["diagnosis"]["id"]
        upd_res = client.put(f"/api/v1/diagnoses/{diag_id}", json={"diagnosis_type": "CONFIRMED"}, headers=doctor_header)
        assert upd_res.status_code == 200
        
        # Finalize Consultation
        finalize_payload = {"assessment_note": "Recovering.", "plan_note": "Follow up in 1 week."}
        fin_res = client.post(f"/api/v1/consultations/{consultation_id}/finalize", json=finalize_payload, headers=doctor_header)
        assert fin_res.status_code == 200
        
        # End Visit via Queue
        end_res = client.post(f"/api/v1/queue/tickets/{ticket_id}/complete-and-end-visit", json={"note": "Flow complete"}, headers=doctor_header)
        assert end_res.status_code == 200

        # Final Verification: Detailed Visit Record
        final_check = client.get(f"/api/v1/visits/{visit_id}/detailed", headers=auth_header)
        data = final_check.json()
        assert data["status"] == "COMPLETED"
        assert len(data["flow_steps"]) >= 2 # Triage and Consultation at least
        assert len(data["queue_tickets"]) >= 2
