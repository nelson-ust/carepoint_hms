import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.enums import LeaveStatus, ApprovalSubjectType
from app.services.approval_service import ApprovalFlowService
from app.schemas.approval_schemas import (
    ApprovalFlowCreateSchema, 
    ApprovalFlowStepCreateSchema, 
    ApprovalFlowStepApproverCreateSchema
)

@pytest.fixture
def test_leave_type(db_session):
    from app.models.all_models import LeaveType, LeaveTypeKind
    # Ensure code is unique in case of test re-runs on same db
    import uuid
    code = f"TEST_LT_{uuid.uuid4().hex[:6]}"
    lt = LeaveType(code=code, name="Test Leave API", kind=LeaveTypeKind.ANNUAL)
    db_session.add(lt)
    db_session.commit()
    db_session.refresh(lt)
    return lt

@pytest.fixture
def auth_headers(client: TestClient, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": admin_user["email"], "password": admin_user["password"]}
    )
    assert response.status_code == 200
    token = response.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}

class TestLeaveRequestRoutes:
    def test_create_leave_request_endpoint(self, client: TestClient, auth_headers, make_staff, test_leave_type):
        staff = make_staff()
        payload = {
            "staff_profile_id": staff.id,
            "leave_type_id": test_leave_type.id,
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=2)),
            "days_requested": "2.00",
            "reason": "API test reason"
        }
        
        response = client.post("/api/v1/leave-requests", json=payload, headers=auth_headers)
        
        assert response.status_code == 201
        assert response.json()["success"] is True
        assert response.json()["leave_request"]["reason"] == "API test reason"
        assert float(response.json()["leave_request"]["days_requested"]) == 2.0

    def test_list_leave_requests_endpoint(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/leave-requests", headers=auth_headers)
        assert response.status_code == 200
        assert "items" in response.json()

    def test_submit_leave_request_endpoint(self, client: TestClient, auth_headers, db_session: Session, make_staff, admin_user, test_leave_type):
        staff = make_staff()
        
        # Create Leave Request
        create_payload = {
            "staff_profile_id": staff.id,
            "leave_type_id": test_leave_type.id,
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=2)),
            "days_requested": "2.00"
        }
        create_resp = client.post("/api/v1/leave-requests", json=create_payload, headers=auth_headers)
        assert create_resp.status_code == 201
        request_id = create_resp.json()["leave_request"]["id"]
        
        # Create Approval Flow
        admin_id = admin_user["user"].id
        flow_service = ApprovalFlowService(db_session)
        
        import uuid
        code = f"API_LR_{uuid.uuid4().hex[:6]}"
        flow_payload = ApprovalFlowCreateSchema(
            code=code,
            name="API Leave Flow",
            subject_type=ApprovalSubjectType.LEAVE_REQUEST,
            steps=[
                ApprovalFlowStepCreateSchema(
                    name="Step 1",
                    step_order=1,
                    approvers=[
                        ApprovalFlowStepApproverCreateSchema(
                            approver_kind="USER",
                            user_id=admin_id
                        )
                    ]
                )
            ]
        )
        flow = flow_service.create(flow_payload, actor_user_id=admin_id)
        db_session.commit()
        
        # Submit
        submit_payload = {
            "flow_id": flow.id,
            "title": "API Submission Leave"
        }
        
        response = client.post(f"/api/v1/leave-requests/{request_id}/submit", json=submit_payload, headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json()["success"] is True
