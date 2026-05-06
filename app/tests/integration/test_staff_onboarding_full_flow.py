from __future__ import annotations

import pytest
from io import BytesIO
import uuid
from app.tests.conftest import HAS_TEST_DB
from app.core.enums import OnboardingDocumentType, OnboardingInvitationStatus

pytestmark = pytest.mark.skipif(
    not HAS_TEST_DB,
    reason="CAREPOINT_HMS_DATABASE_URL not configured for integration tests.",
)

def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

class TestStaffOnboardingFullFlow:
    """
    Comprehensive integration test for the Staff Onboarding process.
    
    Flow:
    1.  HR staff Login (using admin_user acting as HR).
    2.  HR populates minimal staff record (creating a staff profile).
    3.  HR drafts a secured Onboarding Link.
    4.  HR sends the Onboarding Link (token generated).
    5.  New Staff uses the token to access their session (Public).
    6.  New Staff updates their demographic records (Public).
    7.  New Staff uploads relevant documents (Public).
    8.  Onboarding is marked as complete.
    """

    def test_full_onboarding_lifecycle(self, client, admin_user):
        # ── STEP 1: HR Staff Login ──────────────────────────────────────────
        # We explicitly perform a login to get the access token.
        login_data = {
            "identifier": admin_user["username"],
            "password": admin_user["password"]
        }
        # In this system, login might be at /api/v1/auth/login
        login_res = client.post("/api/v1/auth/login", json=login_data)
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        
        access_token = login_res.json()["tokens"]["access_token"]
        hr_headers = {"Authorization": f"Bearer {access_token}"}

        # ── STEP 2: Populate Minimal Staff Record ───────────────────────────
        # HR creates the User account and the linked StaffProfile.
        staff_no = _unique("STF")
        username = _unique("candidate")
        email = f"{username}@example.com"
        
        staff_payload = {
            "username": username,
            "email": email,
            "password": "S3cure!Password2026",
            "first_name": "New",
            "last_name": "Hire",
            "staff_profile": {
                "staff_no": staff_no,
                "job_title": "Registered Nurse"
            }
        }
        
        # POST /api/v1/staff creates both User and StaffProfile
        staff_res = client.post("/api/v1/staff", json=staff_payload, headers=hr_headers)
        assert staff_res.status_code == 201, f"Staff creation failed: {staff_res.text}"
        
        staff_profile_id = staff_res.json()["staff_profile"]["id"]
        
        # ── STEP 3: Draft Onboarding Invitation ────────────────────────────
        # HR prepares the invitation.
        invite_payload = {
            "staff_profile_id": staff_profile_id,
            "candidate_email": email,
            "candidate_phone": "+2348011223344",
            "notes": "Onboarding for new nurse hire.",
            "expiry_days": 7
        }
        
        draft_res = client.post("/api/v1/onboarding/invitations", json=invite_payload, headers=hr_headers)
        assert draft_res.status_code == 201
        invitation_id = draft_res.json()["invitation"]["id"]
        assert draft_res.json()["invitation"]["status"] == OnboardingInvitationStatus.DRAFT.name

        # ── STEP 4: Send Onboarding Link ────────────────────────────────────
        # Generate token and set status to PENDING.
        send_res = client.post(f"/api/v1/onboarding/invitations/{invitation_id}/send", headers=hr_headers)
        assert send_res.status_code == 200
        token = send_res.json()["token"]
        assert token is not None

        # ── STEP 5: New Staff access Session (Public) ──────────────────────
        # No auth header needed; just the token.
        session_res = client.get(f"/api/v1/onboarding/session?token={token}")
        assert session_res.status_code == 200
        assert session_res.json()["invitation"]["status"] == OnboardingInvitationStatus.PENDING.name

        # ── STEP 6: New Staff Updates Demographic Records (Public) ─────────
        # Candidate fills the "Self-service" form.
        completion_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "1995-08-15",
            "gender": "MALE",
            "marital_status": "SINGLE",
            "nationality": "Nigerian",
            "address_line_1": "10 Admiralty Way",
            "city": "Lekki",
            "state_region": "Lagos",
            "country": "Nigeria",
            "emergency_contact_name": "Jane Doe",
            "emergency_contact_phone": "+2347012345678"
        }
        
        # ── STEP 7: New Staff Uploads Documents (Public) ───────────────────
        # Upload CV and ID.
        for doc_type in [OnboardingDocumentType.CV, OnboardingDocumentType.GOVERNMENT_ID]:
            data = {
                "token": token,
                "document_type": doc_type.value
            }
            files = {
                "file": (f"{doc_type.name.lower()}.pdf", BytesIO(b"dummy document content"), "application/pdf")
            }
            upload_res = client.post("/api/v1/onboarding/upload", data=data, files=files)
            assert upload_res.status_code == 200
            assert upload_res.json()["success"] is True

        # Complete the process.
        complete_res = client.post(f"/api/v1/onboarding/complete?token={token}", json=completion_payload)
        assert complete_res.status_code == 200
        assert complete_res.json()["success"] is True

        # ── STEP 8: Verification ───────────────────────────────────────────
        # HR verifies the invitation is now COMPLETED.
        list_res = client.get("/api/v1/onboarding/invitations", headers=hr_headers)
        assert list_res.status_code == 200
        
        invitations = list_res.json()["items"]
        final_invite = next(i for i in invitations if i["id"] == invitation_id)
        assert final_invite["status"] == OnboardingInvitationStatus.COMPLETED.name
        
        # Verify StaffProfile is also updated.
        # HR checks the staff details.
        # staff_res.json()["id"] is the user_id.
        user_id = staff_res.json()["id"]
        check_staff_res = client.get(f"/api/v1/staff/{user_id}", headers=hr_headers)
        assert check_staff_res.status_code == 200
        # The profile update should be reflected.
        assert check_staff_res.json()["user"]["first_name"] == "John"
        assert check_staff_res.json()["user"]["last_name"] == "Doe"
