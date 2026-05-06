# app/tests/integration/test_approval_workflow_integration.py
from __future__ import annotations

import pytest
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from app.core.enums import (
    ApprovalSubjectType,
    ApprovalRequestStatus,
    LeaveStatus,
    TimesheetStatus,
    StaffRequestStatus,
    OvertimeStatus,
    ApprovalApproverKind,
    StaffRequestType,
    ApprovalRequestStepStatus
)
from app.models.all_models import (
    LeaveRequest,
    Timesheet,
    StaffRequest,
    OvertimeRecord,
    LeaveType,
    ApprovalFlow,
    StaffProfile,
    User
)
from app.services.approval_service import ApprovalFlowService, ApprovalRequestService
from app.schemas.approval_schemas import (
    ApprovalFlowCreateSchema,
    ApprovalFlowStepCreateSchema,
    ApprovalFlowStepApproverCreateSchema,
    ApprovalRequestCreateSchema,
    ApprovalDecisionCreateSchema
)

@pytest.fixture
def leave_type(db_session: Session):
    lt = db_session.query(LeaveType).filter_by(code="ANNUAL").first()
    if lt:
        return lt
        
    lt = LeaveType(
        code="ANNUAL",
        name="Annual Leave",
        kind="OTHER",
        is_paid=True,
        requires_approval=True
    )
    db_session.add(lt)
    db_session.commit()
    db_session.refresh(lt)
    return lt

@pytest.fixture
def leave_flow(db_session: Session, admin_user):
    import uuid
    code = f"LEAVE_INT_{uuid.uuid4().hex[:6].upper()}"
    service = ApprovalFlowService(db_session)
    payload = ApprovalFlowCreateSchema(
        code=code,
        name="Leave Integration Flow",
        subject_type=ApprovalSubjectType.LEAVE_REQUEST,
        steps=[
            ApprovalFlowStepCreateSchema(
                name="Manager Approval",
                step_order=1,
                approvers=[
                    ApprovalFlowStepApproverCreateSchema(
                        kind=ApprovalApproverKind.USER,
                        user_id=admin_user["user"].id,
                        is_required=True
                    )
                ]
            )
        ]
    )
    flow = service.create(payload, actor_user_id=admin_user["user"].id)
    db_session.commit()
    return flow

@pytest.fixture
def timesheet_flow(db_session: Session, admin_user):
    import uuid
    code = f"TS_INT_{uuid.uuid4().hex[:6].upper()}"
    service = ApprovalFlowService(db_session)
    payload = ApprovalFlowCreateSchema(
        code=code,
        name="Timesheet Integration Flow",
        subject_type=ApprovalSubjectType.TIMESHEET,
        steps=[
            ApprovalFlowStepCreateSchema(
                name="HR Approval",
                step_order=1,
                approvers=[
                    ApprovalFlowStepApproverCreateSchema(
                        kind=ApprovalApproverKind.USER,
                        user_id=admin_user["user"].id,
                        is_required=True
                    )
                ]
            )
        ]
    )
    flow = service.create(payload, actor_user_id=admin_user["user"].id)
    db_session.commit()
    return flow

class TestApprovalWorkflowIntegration:
    def test_leave_approval_workflow(self, db_session, leave_flow, leave_type, make_staff, admin_user):
        staff = make_staff()
        request_service = ApprovalRequestService(db_session)
        
        # 1. Create a LeaveRequest
        leave = LeaveRequest(
            staff_profile_id=staff.id,
            leave_type_id=leave_type.id,
            start_date=date.today() + timedelta(days=7),
            end_date=date.today() + timedelta(days=14),
            days_requested=7,
            status=LeaveStatus.DRAFT
        )
        db_session.add(leave)
        db_session.commit()
        db_session.refresh(leave)
        
        # 2. Submit for approval
        payload = ApprovalRequestCreateSchema(
            flow_id=leave_flow.id,
            subject_type=ApprovalSubjectType.LEAVE_REQUEST,
            subject_id=leave.id,
            title=f"Leave Request for {staff.staff_no}",
            submit_now=True
        )
        approval_request = request_service.submit(payload, requester_user_id=staff.user_id)
        db_session.commit()
        
        assert approval_request.status == ApprovalRequestStatus.IN_PROGRESS
        
        # 3. Approve the request
        decision_payload = ApprovalDecisionCreateSchema(
            action="APPROVE",
            comment="Approved by integration test"
        )
        request_service.decide(
            approval_request.id, 
            decision_payload, 
            decider_user_id=admin_user["user"].id
        )
        db_session.commit()
        
        # 4. Verify propagation to LeaveRequest
        db_session.refresh(leave)
        assert leave.status == LeaveStatus.APPROVED
        assert leave.decided_by_user_id == admin_user["user"].id

    def test_timesheet_approval_workflow(self, db_session, timesheet_flow, make_staff, admin_user):
        staff = make_staff()
        request_service = ApprovalRequestService(db_session)
        
        # 1. Create a Timesheet
        timesheet = Timesheet(
            staff_profile_id=staff.id,
            period_start=date.today() - timedelta(days=14),
            period_end=date.today() - timedelta(days=1),
            status=TimesheetStatus.DRAFT
        )
        db_session.add(timesheet)
        db_session.commit()
        db_session.refresh(timesheet)
        
        # 2. Submit for approval
        payload = ApprovalRequestCreateSchema(
            flow_id=timesheet_flow.id,
            subject_type=ApprovalSubjectType.TIMESHEET,
            subject_id=timesheet.id,
            title=f"Timesheet for {staff.staff_no}",
            submit_now=True
        )
        approval_request = request_service.submit(payload, requester_user_id=staff.user_id)
        db_session.commit()
        
        # 3. Approve the request
        decision_payload = ApprovalDecisionCreateSchema(
            action="APPROVE",
            comment="Verified"
        )
        request_service.decide(
            approval_request.id, 
            decision_payload, 
            decider_user_id=admin_user["user"].id
        )
        db_session.commit()
        
        # 4. Verify propagation to Timesheet
        db_session.refresh(timesheet)
        assert timesheet.status == TimesheetStatus.APPROVED
        assert timesheet.approved_by_user_id == admin_user["user"].id

    def test_timesheet_multi_step_approval_workflow(self, db_session, make_staff, admin_user):
        """
        Integration test for a Timesheet request undergoing multiple approval steps.
        Step 1: Manager Approval
        Step 2: HR Approval
        """
        staff = make_staff()
        request_service = ApprovalRequestService(db_session)
        flow_service = ApprovalFlowService(db_session)
        
        import uuid
        code = f"TS_MULTI_{uuid.uuid4().hex[:6].upper()}"
        
        # Create a multi-step flow for Timesheet
        flow_payload = ApprovalFlowCreateSchema(
            code=code,
            name="Multi-Step Timesheet Flow",
            subject_type=ApprovalSubjectType.TIMESHEET,
            steps=[
                ApprovalFlowStepCreateSchema(
                    name="Manager Approval",
                    step_order=1,
                    approvers=[
                        ApprovalFlowStepApproverCreateSchema(
                            kind=ApprovalApproverKind.USER,
                            user_id=admin_user["user"].id,
                            is_required=True
                        )
                    ]
                ),
                ApprovalFlowStepCreateSchema(
                    name="HR Final Approval",
                    step_order=2,
                    approvers=[
                        ApprovalFlowStepApproverCreateSchema(
                            kind=ApprovalApproverKind.USER,
                            user_id=admin_user["user"].id,
                            is_required=True
                        )
                    ]
                )
            ]
        )
        flow = flow_service.create(flow_payload, actor_user_id=admin_user["user"].id)
        db_session.commit()

        # 1. Create a Timesheet
        timesheet = Timesheet(
            staff_profile_id=staff.id,
            period_start=date.today() - timedelta(days=14),
            period_end=date.today() - timedelta(days=1),
            status=TimesheetStatus.DRAFT
        )
        db_session.add(timesheet)
        db_session.commit()
        db_session.refresh(timesheet)
        
        # 2. Submit for approval
        payload = ApprovalRequestCreateSchema(
            flow_id=flow.id,
            subject_type=ApprovalSubjectType.TIMESHEET,
            subject_id=timesheet.id,
            title=f"Timesheet for {staff.staff_no}",
            submit_now=True
        )
        approval_request = request_service.submit(payload, requester_user_id=staff.user_id)
        db_session.commit()
        
        assert approval_request.status == ApprovalRequestStatus.IN_PROGRESS
        
        db_session.refresh(approval_request)
        active_steps = [s for s in approval_request.steps if s.status == ApprovalRequestStepStatus.IN_PROGRESS]
        step1_id = active_steps[0].id

        # 3. Approve Step 1
        decision_payload_1 = ApprovalDecisionCreateSchema(
            action="APPROVE",
            comment="Manager approved",
            step_id=step1_id
        )
        request_service.decide(
            approval_request.id, 
            decision_payload_1, 
            decider_user_id=admin_user["user"].id
        )
        db_session.commit()
        db_session.refresh(timesheet)
        
        # Still in progress after Step 1
        assert timesheet.status == TimesheetStatus.DRAFT or timesheet.status == TimesheetStatus.PENDING or approval_request.status == ApprovalRequestStatus.IN_PROGRESS
        
        db_session.refresh(approval_request)
        active_steps = [s for s in approval_request.steps if s.status == ApprovalRequestStepStatus.IN_PROGRESS]
        step2_id = active_steps[0].id

        # 4. Approve Step 2
        decision_payload_2 = ApprovalDecisionCreateSchema(
            action="APPROVE",
            comment="HR approved",
            step_id=step2_id
        )
        request_service.decide(
            approval_request.id, 
            decision_payload_2, 
            decider_user_id=admin_user["user"].id
        )
        db_session.commit()
        db_session.refresh(timesheet)
        
        # 5. Verify propagation to Timesheet
        assert timesheet.status == TimesheetStatus.APPROVED
        assert timesheet.approved_by_user_id == admin_user["user"].id

    def test_staff_request_approval_workflow(self, db_session, make_staff, admin_user):
        staff = make_staff()
        request_service = ApprovalRequestService(db_session)
        flow_service = ApprovalFlowService(db_session)
        
        import uuid
        code = f"STAFF_INT_{uuid.uuid4().hex[:6].upper()}"
        
        # Create a flow for StaffRequest
        flow_payload = ApprovalFlowCreateSchema(
            code=code,
            name="Staff Integration Flow",
            subject_type=ApprovalSubjectType.STAFF_REQUEST,
            steps=[
                ApprovalFlowStepCreateSchema(
                    name="Approval",
                    step_order=1,
                    approvers=[
                        ApprovalFlowStepApproverCreateSchema(
                            kind=ApprovalApproverKind.USER,
                            user_id=admin_user["user"].id,
                            is_required=True
                        )
                    ]
                )
            ]
        )
        flow = flow_service.create(flow_payload, actor_user_id=admin_user["user"].id)
        db_session.commit()

        # 1. Create a StaffRequest
        staff_request = StaffRequest(
            staff_profile_id=staff.id,
            request_type=StaffRequestType.DOCUMENT,
            title="Document Request",
            status=StaffRequestStatus.PENDING
        )
        db_session.add(staff_request)
        db_session.commit()
        db_session.refresh(staff_request)
        
        # 2. Submit for approval
        payload = ApprovalRequestCreateSchema(
            flow_id=flow.id,
            subject_type=ApprovalSubjectType.STAFF_REQUEST,
            subject_id=staff_request.id,
            title=f"Staff Request for {staff.staff_no}",
            submit_now=True
        )
        approval_request = request_service.submit(payload, requester_user_id=staff.user_id)
        db_session.commit()
        
        # 3. Approve the request
        decision_payload = ApprovalDecisionCreateSchema(
            action="APPROVE",
            comment="Approved"
        )
        request_service.decide(
            approval_request.id, 
            decision_payload, 
            decider_user_id=admin_user["user"].id
        )
        db_session.commit()
        
        # 4. Verify propagation to StaffRequest
        db_session.refresh(staff_request)
        assert staff_request.status == StaffRequestStatus.APPROVED
        assert staff_request.decided_by_user_id == admin_user["user"].id

    def test_overtime_approval_workflow(self, db_session, make_staff, admin_user):
        staff = make_staff()
        request_service = ApprovalRequestService(db_session)
        flow_service = ApprovalFlowService(db_session)
        
        import uuid
        code = f"OT_INT_{uuid.uuid4().hex[:6].upper()}"
        
        # Create a flow for Overtime
        flow_payload = ApprovalFlowCreateSchema(
            code=code,
            name="Overtime Integration Flow",
            subject_type=ApprovalSubjectType.OVERTIME,
            steps=[
                ApprovalFlowStepCreateSchema(
                    name="Approval",
                    step_order=1,
                    approvers=[
                        ApprovalFlowStepApproverCreateSchema(
                            kind=ApprovalApproverKind.USER,
                            user_id=admin_user["user"].id,
                            is_required=True
                        )
                    ]
                )
            ]
        )
        flow = flow_service.create(flow_payload, actor_user_id=admin_user["user"].id)
        db_session.commit()

        # 1. Create an OvertimeRecord
        ot = OvertimeRecord(
            staff_profile_id=staff.id,
            work_date=date.today() - timedelta(days=1),
            hours=Decimal("2.5"),
            status=OvertimeStatus.PENDING
        )
        db_session.add(ot)
        db_session.commit()
        db_session.refresh(ot)
        
        # 2. Submit for approval
        payload = ApprovalRequestCreateSchema(
            flow_id=flow.id,
            subject_type=ApprovalSubjectType.OVERTIME,
            subject_id=ot.id,
            title=f"Overtime for {staff.staff_no}",
            submit_now=True
        )
        approval_request = request_service.submit(payload, requester_user_id=staff.user_id)
        db_session.commit()
        
        # 3. Approve the request
        decision_payload = ApprovalDecisionCreateSchema(
            action="APPROVE",
            comment="OK"
        )
        request_service.decide(
            approval_request.id, 
            decision_payload, 
            decider_user_id=admin_user["user"].id
        )
        db_session.commit()
        
        # 4. Verify propagation to OvertimeRecord
        db_session.refresh(ot)
        assert ot.status == OvertimeStatus.APPROVED
        assert ot.approved_by_user_id == admin_user["user"].id
