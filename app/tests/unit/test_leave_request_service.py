import pytest
from datetime import date, timedelta
from decimal import Decimal
from fastapi import HTTPException

from app.core.enums import LeaveStatus, ApprovalSubjectType, LeaveTypeKind
from app.models.all_models import LeaveRequest, LeaveType
from app.schemas.leave_request_schemas import (
    LeaveRequestCreateSchema, 
    LeaveRequestUpdateSchema, 
    LeaveRequestSubmitSchema
)
from app.services.leave_request_service import LeaveRequestService
from app.services.approval_service import ApprovalFlowService
from app.schemas.approval_schemas import (
    ApprovalFlowCreateSchema, 
    ApprovalFlowStepCreateSchema, 
    ApprovalFlowStepApproverCreateSchema
)

@pytest.fixture
def leave_request_service(db_session):
    return LeaveRequestService(db_session)

@pytest.fixture
def test_leave_type(db_session):
    import uuid
    code = f"TEST_LEAVE_{uuid.uuid4().hex[:6]}"
    lt = LeaveType(code=code, name="Test Leave", kind=LeaveTypeKind.ANNUAL)
    db_session.add(lt)
    db_session.commit()
    db_session.refresh(lt)
    return lt

def test_create_leave_request(leave_request_service, make_staff, test_leave_type):
    staff = make_staff()
    payload = LeaveRequestCreateSchema(
        staff_profile_id=staff.id,
        leave_type_id=test_leave_type.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        days_requested=Decimal("2.00"),
        reason="Vacation"
    )
    
    leave_req = leave_request_service.create_leave_request(payload)
    
    assert leave_req.id is not None
    assert leave_req.staff_profile_id == staff.id
    assert leave_req.status == LeaveStatus.DRAFT
    assert leave_req.reason == "Vacation"
    assert leave_req.days_requested == Decimal("2.00")

def test_update_leave_request(leave_request_service, make_staff, test_leave_type):
    staff = make_staff()
    payload = LeaveRequestCreateSchema(
        staff_profile_id=staff.id,
        leave_type_id=test_leave_type.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        days_requested=Decimal("2.00"),
        reason="Vacation"
    )
    leave_req = leave_request_service.create_leave_request(payload)
    
    update_payload = LeaveRequestUpdateSchema(
        reason="Updated reason",
        days_requested=Decimal("3.00")
    )
    
    updated = leave_request_service.update_leave_request(leave_req.id, update_payload)
    
    assert updated.reason == "Updated reason"
    assert updated.days_requested == Decimal("3.00")

def test_submit_leave_request(db_session, leave_request_service, make_staff, test_leave_type, admin_user):
    staff = make_staff()
    payload = LeaveRequestCreateSchema(
        staff_profile_id=staff.id,
        leave_type_id=test_leave_type.id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        days_requested=Decimal("2.00"),
        reason="Vacation"
    )
    leave_req = leave_request_service.create_leave_request(payload)
    
    # Create an ApprovalFlow for LEAVE_REQUEST
    flow_service = ApprovalFlowService(db_session)
    import uuid
    code = f"LEAVE_FLOW_{uuid.uuid4().hex[:6]}"
    flow_payload = ApprovalFlowCreateSchema(
        code=code,
        name="Leave Flow",
        subject_type=ApprovalSubjectType.LEAVE_REQUEST,
        steps=[
            ApprovalFlowStepCreateSchema(
                name="Manager Review",
                step_order=1,
                approvers=[
                    ApprovalFlowStepApproverCreateSchema(
                        approver_kind="USER",
                        user_id=admin_user["user"].id
                    )
                ]
            )
        ]
    )
    flow = flow_service.create(flow_payload, actor_user_id=admin_user["user"].id)
    db_session.commit()
    
    submit_payload = LeaveRequestSubmitSchema(
        flow_id=flow.id,
        title="Leave request title"
    )
    
    submitted = leave_request_service.submit_leave_request(leave_req.id, submit_payload, user_id=staff.user_id)
    
    assert submitted.id == leave_req.id
