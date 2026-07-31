# app/schemas/approval_schemas.py
from __future__ import annotations

"""
Schemas for the generic approval engine:
RequestType → ApprovalFlow → ApprovalStep, and the runtime
ApprovalRequest → ApprovalLog.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import (
    ApprovalApproverKind,
    ApprovalDynamicApprover,
    ApprovalLogAction,
    ApprovalRequestStatus,
    ApprovalStepDecisionRule,
)


# ── Request types ────────────────────────────────────────────────────

class RequestTypeCreateSchema(BaseModel):
    code: str = Field(..., min_length=2, max_length=60)
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    is_active: bool = True


class RequestTypeReadSchema(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


# ── Steps ────────────────────────────────────────────────────────────

class ApprovalStepBase(BaseModel):
    step_order: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=180)
    approver_kind: ApprovalApproverKind
    approver_user_id: Optional[int] = None
    approver_role_id: Optional[int] = None
    approver_department_id: Optional[int] = None
    dynamic_token: Optional[ApprovalDynamicApprover] = None
    decision_rule: ApprovalStepDecisionRule = ApprovalStepDecisionRule.ANY_OF
    required_approvals: int = Field(1, ge=1)
    allow_self_approval: bool = False
    is_active: bool = True


class ApprovalStepCreateSchema(ApprovalStepBase):
    pass


class ApprovalStepReadSchema(ApprovalStepBase):
    id: int
    flow_id: int
    model_config = ConfigDict(from_attributes=True)


# ── Flows ────────────────────────────────────────────────────────────

class ApprovalFlowCreateSchema(BaseModel):
    request_type: str = Field(..., description="RequestType code, e.g. PAYROLL_RUN")
    code: str = Field(..., min_length=2, max_length=80)
    name: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = None
    is_default: bool = False
    is_active: bool = True
    steps: List[ApprovalStepCreateSchema] = Field(default_factory=list)


class ApprovalFlowUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    # When provided, replaces the flow's steps wholesale.
    steps: Optional[List[ApprovalStepCreateSchema]] = None


class ApprovalFlowReadSchema(BaseModel):
    id: int
    request_type_id: int
    request_type_code: Optional[str] = None
    code: str
    name: str
    description: Optional[str] = None
    is_default: bool
    is_active: bool
    steps: List[ApprovalStepReadSchema] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


# ── Runtime request + logs ───────────────────────────────────────────

class ApprovalRequestCreateSchema(BaseModel):
    request_type: str = Field(..., description="RequestType code")
    subject_id: Optional[int] = None
    flow_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    payload: Optional[dict] = None
    department_id: Optional[int] = None
    facility_id: Optional[int] = None
    requester_staff_profile_id: Optional[int] = None
    assigned_approver_user_id: Optional[int] = None


class ApprovalDecisionCreateSchema(BaseModel):
    action: ApprovalLogAction
    comment: Optional[str] = None


class ApprovalLogReadSchema(BaseModel):
    id: int
    step_order: Optional[int] = None
    step_name: Optional[str] = None
    action: ApprovalLogAction
    actor_user_id: Optional[int] = None
    actor_name: Optional[str] = None
    actor_photo_url: Optional[str] = None
    actor_signature_url: Optional[str] = None
    comment: Optional[str] = None
    resulting_status: Optional[str] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestReadSchema(BaseModel):
    id: int
    request_type_code: str
    flow_id: Optional[int] = None
    flow_name: Optional[str] = None
    subject_id: Optional[int] = None
    requester_user_id: int
    requester_name: Optional[str] = None
    requester_photo_url: Optional[str] = None
    requester_signature_url: Optional[str] = None
    assigned_approver_user_id: Optional[int] = None
    assigned_approver_name: Optional[str] = None
    assigned_approver_photo_url: Optional[str] = None
    assigned_approver_signature_url: Optional[str] = None
    title: str
    description: Optional[str] = None
    payload: Optional[dict] = None
    status: ApprovalRequestStatus
    current_step_order: Optional[int] = None
    current_step_name: Optional[str] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    decision_summary: Optional[str] = None
    steps: List[ApprovalStepReadSchema] = Field(default_factory=list)
    logs: List[ApprovalLogReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestListResponse(BaseModel):
    success: bool = True
    message: str = "Approval requests fetched."
    items: List[ApprovalRequestReadSchema]
    count: int
    meta: dict
