# app/schemas/approval_schemas.py
from __future__ import annotations

"""
Pydantic schemas for the Approval Engine.

Covers tenant-managed flow definitions (``ApprovalFlow`` /
``ApprovalFlowStep`` / ``ApprovalFlowStepApprover``) plus runtime
``ApprovalRequest`` / ``ApprovalRequestStep`` / ``ApprovalDecision`` /
``ApprovalComment``.

Naming follows existing project conventions:
    *CreateSchema, *UpdateSchema, *ReadSchema, *ListResponseSchema,
    *ActionResponseSchema.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import (
    ApprovalApproverKind,
    ApprovalDecisionAction,
    ApprovalDynamicApprover,
    ApprovalRequestStatus,
    ApprovalRequestStepStatus,
    ApprovalStepDecisionRule,
    ApprovalSubjectType,
)


# ============================================================
# FLOW STEP APPROVER
# ============================================================


class ApprovalFlowStepApproverCreateSchema(BaseModel):
    """Approver target attached to a step.

    Set exactly one of ``user_id`` / ``role_id`` / ``department_id`` /
    ``dynamic_token`` based on ``approver_kind``.
    """
    approver_kind: ApprovalApproverKind
    user_id: Optional[int] = None
    role_id: Optional[int] = None
    department_id: Optional[int] = None
    dynamic_token: Optional[ApprovalDynamicApprover] = None
    is_required: bool = False
    notes: Optional[str] = Field(None, max_length=500)

    @model_validator(mode="after")
    def _validate_target_for_kind(self) -> "ApprovalFlowStepApproverCreateSchema":
        kind = self.approver_kind
        if kind == ApprovalApproverKind.USER and not self.user_id:
            raise ValueError("user_id is required when approver_kind=USER.")
        if kind == ApprovalApproverKind.ROLE and not self.role_id:
            raise ValueError("role_id is required when approver_kind=ROLE.")
        if kind == ApprovalApproverKind.DEPARTMENT and not self.department_id:
            raise ValueError("department_id is required when approver_kind=DEPARTMENT.")
        if kind == ApprovalApproverKind.DYNAMIC and not self.dynamic_token:
            raise ValueError("dynamic_token is required when approver_kind=DYNAMIC.")
        return self


class ApprovalFlowStepApproverReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_id: int
    approver_kind: ApprovalApproverKind
    user_id: Optional[int] = None
    role_id: Optional[int] = None
    department_id: Optional[int] = None
    dynamic_token: Optional[ApprovalDynamicApprover] = None
    is_required: bool
    notes: Optional[str] = None


# ============================================================
# FLOW STEP
# ============================================================


class ApprovalFlowStepCreateSchema(BaseModel):
    step_order: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = Field(None, max_length=2000)
    decision_rule: ApprovalStepDecisionRule = ApprovalStepDecisionRule.ANY_OF
    required_approvals: int = Field(1, ge=1)
    allow_self_approval: bool = False
    sla_hours: Optional[int] = Field(None, ge=0)
    is_optional: bool = False
    approvers: list[ApprovalFlowStepApproverCreateSchema] = Field(
        default_factory=list,
        description="Approver targets for the step. At least one is required.",
    )

    @model_validator(mode="after")
    def _validate_step(self) -> "ApprovalFlowStepCreateSchema":
        if not self.approvers:
            raise ValueError("Each step must define at least one approver.")
        if self.decision_rule == ApprovalStepDecisionRule.N_OF_M:
            if self.required_approvals < 1:
                raise ValueError(
                    "N_OF_M requires required_approvals >= 1."
                )
        if self.decision_rule == ApprovalStepDecisionRule.ALL_OF:
            required_count = sum(1 for a in self.approvers if a.is_required)
            if required_count == 0:
                raise ValueError(
                    "ALL_OF rule requires at least one approver with is_required=True."
                )
        return self


class ApprovalFlowStepUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=180)
    description: Optional[str] = Field(None, max_length=2000)
    decision_rule: Optional[ApprovalStepDecisionRule] = None
    required_approvals: Optional[int] = Field(None, ge=1)
    allow_self_approval: Optional[bool] = None
    sla_hours: Optional[int] = Field(None, ge=0)
    is_optional: Optional[bool] = None


class ApprovalFlowStepReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    flow_id: int
    step_order: int
    name: str
    description: Optional[str] = None
    decision_rule: ApprovalStepDecisionRule
    required_approvals: int
    allow_self_approval: bool
    sla_hours: Optional[int] = None
    is_optional: bool
    approvers: list[ApprovalFlowStepApproverReadSchema] = Field(default_factory=list)


# ============================================================
# FLOW
# ============================================================


class ApprovalFlowCreateSchema(BaseModel):
    code: str = Field(..., min_length=1, max_length=80)
    name: str = Field(..., min_length=1, max_length=180)
    description: Optional[str] = Field(None, max_length=2000)
    subject_type: ApprovalSubjectType
    is_default: bool = False
    sla_hours: Optional[int] = Field(None, ge=0)
    auto_cancel_after_hours: Optional[int] = Field(None, ge=0)
    notify_on_submit: bool = True
    notify_on_decision: bool = True
    steps: list[ApprovalFlowStepCreateSchema] = Field(
        ...,
        description="Ordered list of steps; must contain at least one step.",
    )

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "_")

    @model_validator(mode="after")
    def _validate_steps(self) -> "ApprovalFlowCreateSchema":
        if not self.steps:
            raise ValueError("A flow must contain at least one step.")
        orders = [s.step_order for s in self.steps]
        if len(set(orders)) != len(orders):
            raise ValueError("step_order values must be unique within a flow.")
        return self


class ApprovalFlowUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=180)
    description: Optional[str] = Field(None, max_length=2000)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    sla_hours: Optional[int] = Field(None, ge=0)
    auto_cancel_after_hours: Optional[int] = Field(None, ge=0)
    notify_on_submit: Optional[bool] = None
    notify_on_decision: Optional[bool] = None


class ApprovalFlowReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: Optional[str] = None
    subject_type: ApprovalSubjectType
    is_default: bool
    is_active: bool
    version: int
    sla_hours: Optional[int] = None
    auto_cancel_after_hours: Optional[int] = None
    notify_on_submit: bool
    notify_on_decision: bool
    steps: list[ApprovalFlowStepReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ApprovalFlowListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Approval flows fetched successfully."
    items: list[ApprovalFlowReadSchema]
    count: int
    meta: dict


class ApprovalFlowActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    flow: ApprovalFlowReadSchema


# ============================================================
# REQUEST
# ============================================================


class ApprovalRequestCreateSchema(BaseModel):
    """Submit a new approval request.

    Either ``flow_id`` or ``flow_code`` must be provided. ``subject_type``
    must match the chosen flow. ``subject_id`` is the FK to the
    underlying domain row (e.g. LeaveRequest.id) when applicable.
    """
    flow_id: Optional[int] = None
    flow_code: Optional[str] = Field(None, max_length=80)
    subject_type: ApprovalSubjectType
    subject_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=4000)
    payload: Optional[dict[str, Any]] = None
    priority: Optional[str] = Field(None, max_length=20)
    department_id: Optional[int] = None
    facility_id: Optional[int] = None
    submit_now: bool = Field(
        True,
        description=(
            "If True, the request is moved from DRAFT to PENDING immediately "
            "and the first step is opened. Set False to keep as DRAFT."
        ),
    )

    @model_validator(mode="after")
    def _validate_flow_ref(self) -> "ApprovalRequestCreateSchema":
        if not self.flow_id and not self.flow_code:
            # Allowed: caller can omit both and the engine will pick the
            # default flow for the subject_type.
            return self
        return self

    @field_validator("flow_code")
    @classmethod
    def _normalize_flow_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip().upper().replace(" ", "_")


class ApprovalDecisionCreateSchema(BaseModel):
    action: ApprovalDecisionAction
    comment: Optional[str] = Field(None, max_length=2000)
    delegated_to_user_id: Optional[int] = None

    @model_validator(mode="after")
    def _validate_action_targets(self) -> "ApprovalDecisionCreateSchema":
        if self.action == ApprovalDecisionAction.DELEGATE and not self.delegated_to_user_id:
            raise ValueError("delegated_to_user_id is required when action=DELEGATE.")
        if self.action == ApprovalDecisionAction.REJECT and not self.comment:
            raise ValueError("A comment is required when rejecting an approval step.")
        return self


class ApprovalCommentCreateSchema(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class ApprovalDecisionReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    request_step_id: int
    decided_by_user_id: int
    action: ApprovalDecisionAction
    comment: Optional[str] = None
    delegated_to_user_id: Optional[int] = None
    decided_at: datetime


class ApprovalRequestStepReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    flow_step_id: int
    step_order: int
    name: str
    decision_rule: ApprovalStepDecisionRule
    required_approvals: int
    is_optional: bool
    status: ApprovalRequestStepStatus
    approvals_received: int
    rejections_received: int
    eligible_user_ids: Optional[list[int]] = None
    approver_specs: Optional[list[dict[str, Any]]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    decisions: list[ApprovalDecisionReadSchema] = Field(default_factory=list)


class ApprovalCommentReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_id: int
    author_user_id: int
    body: str
    posted_at: datetime


class ApprovalRequestReadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    flow_id: int
    subject_type: ApprovalSubjectType
    subject_id: Optional[int] = None
    requester_user_id: int
    requester_staff_profile_id: Optional[int] = None
    department_id: Optional[int] = None
    facility_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    priority: Optional[str] = None
    status: ApprovalRequestStatus
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    current_step_id: Optional[int] = None
    decision_summary: Optional[str] = None
    steps: list[ApprovalRequestStepReadSchema] = Field(default_factory=list)
    comments: list[ApprovalCommentReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ApprovalRequestListResponseSchema(BaseModel):
    success: bool = True
    message: str = "Approval requests fetched successfully."
    items: list[ApprovalRequestReadSchema]
    count: int
    meta: dict


class ApprovalRequestActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    request: ApprovalRequestReadSchema


class ApprovalDecisionActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    decision: ApprovalDecisionReadSchema
    request: ApprovalRequestReadSchema


class ApprovalCommentActionResponseSchema(BaseModel):
    success: bool = True
    message: str
    comment: ApprovalCommentReadSchema
