import pytest
from fastapi.testclient import TestClient
from datetime import date, datetime, timedelta

def test_patient_identity_flow(client: TestClient, admin_token_headers):
    # 1. Create Insurance Provider
    resp = client.post(
        "/api/v1/patient-master/insurance-providers",
        headers=admin_token_headers,
        json={
            "name": "Reliance HMO",
            "code": "RELIANCE",
            "provider_type": "HMO",
            "contact_person": "John Doe"
        }
    )
    assert resp.status_code == 200
    provider_id = resp.json()["id"]

    # 2. Add Identifier to a Patient (assume patient ID 1 exists from seed)
    resp = client.post(
        "/api/v1/patient-master/1/identifiers",
        headers=admin_token_headers,
        json={
            "identifier_type": "NIN",
            "identifier_value": "12345678901",
            "is_primary": True
        }
    )
    assert resp.status_code == 200

def test_procurement_p2p_flow(client: TestClient, admin_token_headers):
    # 1. Create RFQ (assume requisition item ID 1 exists from seed or created)
    # First create a requisition to get an item ID
    req_resp = client.post(
        "/api/v1/procurements/requisitions",
        headers=admin_token_headers,
        json={
            "facility_id": 1,
            "requested_by_staff_id": 1,
            "items": [
                {
                    "item_name": "Paracetamol",
                    "quantity_requested": 100,
                    "estimated_unit_price": 10.5
                }
            ]
        }
    )
    assert req_resp.status_code == 201
    item_id = req_resp.json()["requisition"]["items"][0]["id"]

    # 2. Create RFQ
    rfq_resp = client.post(
        "/api/v1/procurements/rfqs",
        headers=admin_token_headers,
        json={
            "description": "Monthly Drug Supply",
            "vendor_ids": [],
            "items": [{"requisition_item_id": item_id, "quantity": 100}]
        }
    )
    assert rfq_resp.status_code == 201

    # 3. Create PO (assume supplier ID 1 exists)
    po_resp = client.post(
        "/api/v1/procurements/purchase-orders",
        headers=admin_token_headers,
        json={
            "supplier_id": 1,
            "items": [
                {
                    "item_name": "Paracetamol",
                    "quantity_ordered": 100,
                    "unit_price": 9.5
                }
            ]
        }
    )
    assert po_resp.status_code == 201

def test_hr_payroll_config(client: TestClient, admin_token_headers):
    resp = client.post(
        "/api/v1/hr/payroll-config/allowance-types",
        headers=admin_token_headers,
        json={
            "name": "Housing Allowance",
            "code": "HOU",
            "amount": 50000
        }
    )
    assert resp.status_code == 200

def test_loyalty_network(client: TestClient, admin_token_headers):
    resp = client.post(
        "/api/v1/loyalty-network/programs",
        headers=admin_token_headers,
        json={
            "name": "Platinum Patient",
            "code": "PLAT",
            "points_per_currency_spent": 0.05
        }
    )
    assert resp.status_code == 200
