# app/api/v1/endpoints/approval_routes.py
from __future__ import annotations

"""
FastAPI routes for the Approval Engine.

Two route groups, all mounted under ``/api/v1/approvals``:

Admin / flow management
    GET    /approvals/flows                       list flows
    POST   /approvals/flows                       create flow + steps + approvers
    GET    /approvals/flows/{flow_id}             read a flow with its steps
    PATCH  /approvals/flows/{flow_id}             update flow metadata
    DELETE /approvals/flows/{flow_id}             soft-delete a flow

Operator / request runtime
    GET    /approvals/requests                    list (filtered) requests
    GET    /approvals/requests/inbox              "awaiting my decision" feed
    GET    /approvals/requests/mine               requests I raised
    POST   /approvals/requests                    submit a new request
    GET    /approvals/requests/{request_id}       full request with steps + comments
    POST   /approvals/requests/{request_id}/decisions   approve / reject / delegate
    POST   /approvals/requests/{request_id}/comments    add a comment thread row
    POST   /approvals/requests/{request_id}/cancel      cancel as requester

Auth model
----------
* Flow CRUD requires ``AdminUser`` (matches existing ``hr_router`` pattern).
* Submitting / commenting / cancelling requires ``CurrentActiveUser``.
* Decisioning requires ``CurrentActiveUser``; the engine itself enforces
  that the caller is in the step's eligible-user set.
"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser
from app.core.enums import (
    ApprovalRequestStatus,
    ApprovalSubjectType,
)
from app.models.all_models import (
    ApprovalFlow,
    ApprovalRequest,
    ApprovalRequestStep,
)
from app.schemas.approval_schemas import (
    ApprovalCommentActionResponseSchema,
    ApprovalCommentCreateSchema,
    ApprovalCommentReadSchema,
    ApprovalDecisionActionResponseSchema,
    ApprovalDecisionCreateSchema,
    ApprovalDecisionReadSchema,
    ApprovalFlowActionResponseSchema,
    ApprovalFlowCreateSchema,
    ApprovalFlowListResponseSchema,
    ApprovalFlowReadSchema,
    ApprovalFlowStepApproverReadSchema,
    ApprovalFlowStepReadSchema,
    ApprovalFlowUpdateSchema,
    ApprovalRequestActionResponseSchema,
    ApprovalRequestCreateSchema,
    ApprovalRequestListResponseSchema,
    ApprovalRequestReadSchema,
    ApprovalRequestStepReadSchema,
)
from app.services.approval_service import (
    ApprovalFlowService,
    ApprovalRequestService,
)
from app.utils.pagination import paginate_response


router = APIRouter(prefix="/approvals", tags=["Approvals"])


# ---------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------


def get_flow_service(
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalFlowService:
    return ApprovalFlowService(db)


def get_request_service(
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalRequestService:
    return ApprovalRequestService(db)


# ---------------------------------------------------------------------
# ORM -> read-schema serialisers
# ---------------------------------------------------------------------


def _flow_to_dict(flow: ApprovalFlow, db: Session) -> dict[str, Any]:
    from app.repositories.approval_repository import ApprovalFlowRepository

    repo = ApprovalFlowRepository(db)
    steps = repo.get_steps(flow.id)
    step_payload: list[dict[str, Any]] = []
    for step in steps:
        approvers = repo.get_step_approvers(step.id)
        step_payload.append(
            {
                "id": step.id,
                "flow_id": step.flow_id,
                "step_order": step.step_order,
                "name": step.name,
                "description": step.description,
                "decision_rule": step.decision_rule,
                "required_approvals": step.required_approvals,
                "allow_self_approval": step.allow_self_approval,
                "sla_hours": step.sla_hours,
                "is_optional": step.is_optional,
                "approvers": [
                    ApprovalFlowStepApproverReadSchema.model_validate(a).model_dump()
                    for a in approvers
                ],
            }
        )
    return {
        "id": flow.id,
        "code": flow.code,
        "name": flow.name,
        "description": flow.description,
        "subject_type": flow.subject_type,
        "is_default": flow.is_default,
        "is_active": flow.is_active,
        "version": flow.version,
        "sla_hours": flow.sla_hours,
        "auto_cancel_after_hours": flow.auto_cancel_after_hours,
        "notify_on_submit": flow.notify_on_submit,
        "notify_on_decision": flow.notify_on_decision,
        "steps": step_payload,
        "created_at": getattr(flow, "created_at", None),
        "updated_at": getattr(flow, "updated_at", None),
    }


def _step_with_decisions(
    step: ApprovalRequestStep, db: Session
) -> dict[str, Any]:
    from app.repositories.approval_repository import ApprovalRequestRepository

    repo = ApprovalRequestRepository(db)
    decisions = repo.get_step_decisions(step.id)
    return {
        "id": step.id,
        "request_id": step.request_id,
        "flow_step_id": step.flow_step_id,
        "step_order": step.step_order,
        "name": step.name,
        "decision_rule": step.decision_rule,
        "required_approvals": step.required_approvals,
        "is_optional": step.is_optional,
        "status": step.status,
        "approvals_received": step.approvals_received,
        "rejections_received": step.rejections_received,
        "eligible_user_ids": step.eligible_user_ids or [],
        "approver_specs": step.approver_specs or [],
        "started_at": step.started_at,
        "completed_at": step.completed_at,
        "decisions": [
            ApprovalDecisionReadSchema.model_validate(d).model_dump()
            for d in decisions
        ],
    }


def _request_to_dict(request: ApprovalRequest, db: Session) -> dict[str, Any]:
    from app.repositories.approval_repository import ApprovalRequestRepository

    repo = ApprovalRequestRepository(db)
    steps = repo.get_steps(request.id)
    comments = repo.get_comments(request.id)
    return {
        "id": request.id,
        "flow_id": request.flow_id,
        "subject_type": request.subject_type,
        "subject_id": request.subject_id,
        "requester_user_id": request.requester_user_id,
        "requester_staff_profile_id": request.requester_staff_profile_id,
        "department_id": request.department_id,
        "facility_id": request.facility_id,
        "title": request.title,
        "description": request.description,
        "payload": request.payload,
        "priority": request.priority,
        "status": request.status,
        "submitted_at": request.submitted_at,
        "completed_at": request.completed_at,
        "expires_at": request.expires_at,
        "current_step_id": request.current_step_id,
        "decision_summary": request.decision_summary,
        "steps": [_step_with_decisions(s, db) for s in steps],
        "comments": [
            ApprovalCommentReadSchema.model_validate(c).model_dump()
            for c in comments
        ],
        "created_at": getattr(request, "created_at", None),
        "updated_at": getattr(request, "updated_at", None),
    }


# =====================================================================
# FLOW MANAGEMENT (admin)
# =====================================================================


@router.get(
    "/flows",
    response_model=ApprovalFlowListResponseSchema,
    summary="List approval flows",
)
def list_flows(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalFlowService, Depends(get_flow_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    subject_type: Optional[ApprovalSubjectType] = None,
    search: Optional[str] = None,
    active_only: bool = Query(True),
):
    flows, total = service.list_flows(
        skip=skip,
        limit=limit,
        subject_type=subject_type,
        search=search,
        active_only=active_only,
    )
    items = [_flow_to_dict(f, db) for f in flows]
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Approval flows fetched successfully.",
    )


@router.post(
    "/flows",
    response_model=ApprovalFlowActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new approval flow with steps and approvers",
)
def create_flow(
    payload: ApprovalFlowCreateSchema,
    current_user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalFlowService, Depends(get_flow_service)],
):
    flow = service.create(payload, actor_user_id=current_user.id)
    return {
        "success": True,
        "message": "Approval flow created successfully.",
        "flow": ApprovalFlowReadSchema.model_validate(_flow_to_dict(flow, db)),
    }


@router.get(
    "/flows/{flow_id}",
    response_model=ApprovalFlowActionResponseSchema,
    summary="Read an approval flow",
)
def get_flow(
    flow_id: int,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalFlowService, Depends(get_flow_service)],
):
    flow = service.get(flow_id)
    return {
        "success": True,
        "message": "Approval flow fetched successfully.",
        "flow": ApprovalFlowReadSchema.model_validate(_flow_to_dict(flow, db)),
    }


@router.patch(
    "/flows/{flow_id}",
    response_model=ApprovalFlowActionResponseSchema,
    summary="Update flow metadata",
)
def update_flow(
    flow_id: int,
    payload: ApprovalFlowUpdateSchema,
    current_user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalFlowService, Depends(get_flow_service)],
):
    flow = service.update(flow_id, payload, actor_user_id=current_user.id)
    return {
        "success": True,
        "message": "Approval flow updated successfully.",
        "flow": ApprovalFlowReadSchema.model_validate(_flow_to_dict(flow, db)),
    }


@router.delete(
    "/flows/{flow_id}",
    response_model=ApprovalFlowActionResponseSchema,
    summary="Soft-delete an approval flow",
)
def delete_flow(
    flow_id: int,
    current_user: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalFlowService, Depends(get_flow_service)],
):
    flow = service.soft_delete(flow_id, actor_user_id=current_user.id)
    return {
        "success": True,
        "message": "Approval flow deleted successfully.",
        "flow": ApprovalFlowReadSchema.model_validate(_flow_to_dict(flow, db)),
    }


# =====================================================================
# REQUEST RUNTIME (any authenticated user)
# =====================================================================


@router.get(
    "/requests",
    response_model=ApprovalRequestListResponseSchema,
    summary="List approval requests",
)
def list_requests(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalRequestService, Depends(get_request_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    subject_type: Optional[ApprovalSubjectType] = None,
    requester_user_id: Optional[int] = None,
    status_in: Annotated[Optional[list[ApprovalRequestStatus]], Query()] = None,
    flow_id: Optional[int] = None,
    search: Optional[str] = None,
):
    requests, total = service.list_requests(
        skip=skip,
        limit=limit,
        requester_user_id=requester_user_id,
        subject_type=subject_type,
        statuses=status_in,
        flow_id=flow_id,
        search=search,
    )
    items = [_request_to_dict(r, db) for r in requests]
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Approval requests fetched successfully.",
    )


@router.get(
    "/requests/inbox",
    response_model=ApprovalRequestListResponseSchema,
    summary="List requests awaiting my decision",
)
def my_inbox(
    current_user: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalRequestService, Depends(get_request_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    subject_type: Optional[ApprovalSubjectType] = None,
):
    requests, total = service.list_my_pending(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        subject_type=subject_type,
    )
    items = [_request_to_dict(r, db) for r in requests]
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Requests awaiting your decision.",
    )


@router.get(
    "/requests/mine",
    response_model=ApprovalRequestListResponseSchema,
    summary="List requests I raised",
)
def my_requests(
    current_user: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalRequestService, Depends(get_request_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    subject_type: Optional[ApprovalSubjectType] = None,
    status_in: Annotated[Optional[list[ApprovalRequestStatus]], Query()] = None,
):
    requests, total = service.list_requests(
        skip=skip,
        limit=limit,
        requester_user_id=current_user.id,
        subject_type=subject_type,
        statuses=status_in,
    )
    items = [_request_to_dict(r, db) for r in requests]
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Your approval requests.",
    )


@router.post(
    "/requests",
    response_model=ApprovalRequestActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new approval request",
)
def submit_request(
    payload: ApprovalRequestCreateSchema,
    current_user: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalRequestService, Depends(get_request_service)],
):
    request = service.submit(
        payload,
        requester_user_id=current_user.id,
        actor_user_id=current_user.id,
    )
    return {
        "success": True,
        "message": "Approval request submitted successfully.",
        "request": ApprovalRequestReadSchema.model_validate(
            _request_to_dict(request, db)
        ),
    }


@router.get(
    "/requests/{request_id}",
    response_model=ApprovalRequestActionResponseSchema,
    summary="Read an approval request with full step + decision history",
)
def read_request(
    request_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalRequestService, Depends(get_request_service)],
):
    request = service.get(request_id)
    return {
        "success": True,
        "message": "Approval request fetched successfully.",
        "request": ApprovalRequestReadSchema.model_validate(
            _request_to_dict(request, db)
        ),
    }


@router.post(
    "/requests/{request_id}/decisions",
    response_model=ApprovalDecisionActionResponseSchema,
    summary="Record an APPROVE / REJECT / DELEGATE on the active step",
)
def record_decision(
    request_id: int,
    payload: ApprovalDecisionCreateSchema,
    current_user: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalRequestService, Depends(get_request_service)],
):
    decision, request = service.decide(
        request_id,
        payload,
        decider_user_id=current_user.id,
        actor_user_id=current_user.id,
    )
    return {
        "success": True,
        "message": "Decision recorded successfully.",
        "decision": ApprovalDecisionReadSchema.model_validate(decision),
        "request": ApprovalRequestReadSchema.model_validate(
            _request_to_dict(request, db)
        ),
    }


@router.post(
    "/requests/{request_id}/comments",
    response_model=ApprovalCommentActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to the request thread",
)
def add_comment(
    request_id: int,
    payload: ApprovalCommentCreateSchema,
    current_user: CurrentActiveUser,
    service: Annotated[ApprovalRequestService, Depends(get_request_service)],
):
    comment = service.add_comment(
        request_id,
        payload,
        author_user_id=current_user.id,
        actor_user_id=current_user.id,
    )
    return {
        "success": True,
        "message": "Comment added successfully.",
        "comment": ApprovalCommentReadSchema.model_validate(comment),
    }


@router.post(
    "/requests/{request_id}/cancel",
    response_model=ApprovalRequestActionResponseSchema,
    summary="Cancel a request you submitted (DRAFT/PENDING/IN_PROGRESS)",
)
def cancel_request(
    request_id: int,
    current_user: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ApprovalRequestService, Depends(get_request_service)],
    reason: Optional[str] = Query(None, max_length=500),
):
    request = service.cancel(
        request_id, actor_user_id=current_user.id, reason=reason
    )
    return {
        "success": True,
        "message": "Approval request cancelled.",
        "request": ApprovalRequestReadSchema.model_validate(
            _request_to_dict(request, db)
        ),
    }
