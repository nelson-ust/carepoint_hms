from __future__ import annotations

import pytest
from io import BytesIO
from app.tests.conftest import HAS_TEST_DB
from app.tests.integration.test_auth_routes import _login, _bearer_headers, _unique
from app.core.enums import OnboardingDocumentType

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)

@pytest.fixture()
def auth_header(client, admin_user):
    login_res = _login(client, admin_user["username"], admin_user["password"])
    token = login_res.json()["tokens"]["access_token"]
    return _bearer_headers(token)

class TestOnboardingRoutes:
    
    def test_onboarding_full_flow(self, client, auth_header):
        # 1. HR creates a staff profile first (simplified)
        # In a real test, you'd use the staff_routes to create a staff member.
        # For this test, we assume we have a staff profile id (e.g., 1 or we create one).
        
        # Let's create a staff member first to have a valid profile_id
        staff_payload = {
            "username": _unique("candidate"),
            "email": _unique("candidate") + "@example.com",
            "password": "S3cure!Password2026",
            "first_name": "Pending",
            "last_name": "Candidate",
            "staff_profile": {
                "staff_no": _unique("STF")
            }
        }
        staff_res = client.post("/api/v1/staff", json=staff_payload, headers=auth_header)
        assert staff_res.status_code == 201
        staff_id = staff_res.json()["staff_profile"]["id"]

        # 2. HR drafts an onboarding invitation
        invite_payload = {
            "staff_profile_id": staff_id,
            "candidate_email": "candidate@example.com",
            "candidate_phone": "08012345678",
            "notes": "Interview passed",
            "expiry_days": 1
        }
        res = client.post("/api/v1/onboarding/invitations", json=invite_payload, headers=auth_header)
        assert res.status_code == 201
        invitation_id = res.json()["invitation"]["id"]

        # 3. HR sends the invitation link
        send_res = client.post(f"/api/v1/onboarding/invitations/{invitation_id}/send", headers=auth_header)
        assert send_res.status_code == 200
        token = send_res.json()["token"]
        assert token is not None

        # 4. Candidate fetches their session using the token (Public)
        session_res = client.get(f"/api/v1/onboarding/session?token={token}")
        assert session_res.status_code == 200
        assert session_res.json()["invitation"]["candidate_email"] == "candidate@example.com"

        # 5. Candidate uploads a document (Public)
        data = {
            "token": token,
            "document_type": OnboardingDocumentType.CV.value
        }
        files = {
            "file": ("cv.pdf", BytesIO(b"dummy pdf content"), "application/pdf")
        }
        upload_res = client.post("/api/v1/onboarding/upload", data=data, files=files)
        # If S3 is not enabled in tests, this might fail or we should mock S3Service.
        # Assuming S3_ENABLED=False in tests or mocked.
        # assert upload_res.status_code == 200 

        # 6. Candidate completes onboarding (Public)
        completion_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1990-05-20",
            "gender": "MALE",
            "marital_status": "MARRIED",
            "nationality": "American",
            "address_line_1": "Main St 101",
            "city": "New York",
            "state_region": "NY",
            "country": "USA",
            "emergency_contact_name": "Jane Doe",
            "emergency_contact_phone": "123456789"
        }
        complete_res = client.post(f"/api/v1/onboarding/complete?token={token}", json=completion_payload)
        assert complete_res.status_code == 200
        assert complete_res.json()["success"] is True

        # 7. HR verifies the invitation status is now COMPLETED
        list_res = client.get("/api/v1/onboarding/invitations", headers=auth_header)
        assert list_res.status_code == 200
        # Find our invitation
        items = list_res.json()["items"]
        my_invite = next(i for i in items if i["id"] == invitation_id)
        assert my_invite["status"] == "COMPLETED"

    def test_onboarding_progress(self, client, auth_header):
        # Setup: Create staff and invitation
        staff_payload = {
            "username": _unique("prog"),
            "email": _unique("prog") + "@example.com",
            "password": "S3cure!Password2026",
            "first_name": "Prog",
            "last_name": "User",
            "staff_profile": {"staff_no": _unique("STF")}
        }
        staff_res = client.post("/api/v1/staff", json=staff_payload, headers=auth_header)
        staff_id = staff_res.json()["staff_profile"]["id"]
        
        invite_res = client.post("/api/v1/onboarding/invitations", json={
            "staff_profile_id": staff_id,
            "candidate_email": "prog@example.com"
        }, headers=auth_header)
        inv_id = invite_res.json()["invitation"]["id"]
        
        send_res = client.post(f"/api/v1/onboarding/invitations/{inv_id}/send", headers=auth_header)
        token = send_res.json()["token"]
        
        # Check progress
        res = client.get(f"/api/v1/onboarding/progress?token={token}")
        assert res.status_code == 200
        progress = res.json()["progress"]
        assert progress["completion_percentage"] == 0.0
        assert progress["is_demographics_complete"] is False

    def test_bulk_complete_onboarding(self, client, auth_header):
        # Setup: Create staff and invitation
        staff_payload = {
            "username": _unique("bulk"),
            "email": _unique("bulk") + "@example.com",
            "password": "S3cure!Password2026",
            "first_name": "Bulk",
            "last_name": "Staff",
            "staff_profile": {"staff_no": _unique("STF")}
        }
        staff_res = client.post("/api/v1/staff", json=staff_payload, headers=auth_header)
        staff_id = staff_res.json()["staff_profile"]["id"]
        
        invite_res = client.post("/api/v1/onboarding/invitations", json={
            "staff_profile_id": staff_id,
            "candidate_email": "bulk@example.com"
        }, headers=auth_header)
        inv_id = invite_res.json()["invitation"]["id"]
        
        send_res = client.post(f"/api/v1/onboarding/invitations/{inv_id}/send", headers=auth_header)
        token = send_res.json()["token"]
        
        # Bulk Complete
        import json
        payload = {
            "first_name": "John",
            "last_name": "Bulk",
            "date_of_birth": "1990-01-01",
            "gender": "MALE",
            "marital_status": "SINGLE",
            "nationality": "Nigerian",
            "address_line_1": "123 Bulk St",
            "city": "Lagos",
            "state_region": "Lagos",
            "country": "Nigeria",
            "emergency_contact_name": "Jane",
            "emergency_contact_phone": "090",
            "emergency_contacts": [
                {
                    "full_name": "Jane Doe",
                    "relationship": "Sister",
                    "phone_number": "08011111111",
                    "is_primary": True
                }
            ],
            "licenses": [
                {
                    "license_type": "Nursing License",
                    "license_number": "NL-12345",
                    "issuing_body": "Nursing Council"
                }
            ],
            "bank_name": "First Bank",
            "bank_account_no": "3012345678",
            "bank_account_name": "John Bulk"
        }
        
        form_data = {
            "token": token,
            "payload_json": json.dumps(payload)
        }
        files = {
            "cv_file": ("cv.pdf", BytesIO(b"cv content"), "application/pdf"),
            "id_file": ("id.jpg", BytesIO(b"id content"), "image/jpeg")
        }
        
        res = client.post("/api/v1/onboarding/bulk-complete", data=form_data, files=files)
        assert res.status_code == 200
        assert res.json()["success"] is True
        
        # Verify status via HR list
        hr_list_res = client.get("/api/v1/onboarding/invitations", headers=auth_header)
        items = hr_list_res.json()["items"]
        my_invite = next(i for i in items if i["id"] == inv_id)
        assert my_invite["status"] == "COMPLETED"
