# app/repositories/approval_repository.py
from __future__ import annotations

"""
Persistence helpers for the Approval Engine.

Three repository classes mirror the model split:

* :class:`ApprovalFlowRepository` — flow definitions, steps, approvers
* :class:`ApprovalRequestRepository` — runtime requests, snapshots,
  decisions, comments
* :class:`ApprovalQueryRepository` — list/filter helpers used by the
  service layer to power "my pending approvals" / "requests I raised"
  endpoints

Conventions
-----------
* Repositories ``flush()`` and ``refresh()`` but do not ``commit()``.
  The service layer owns the unit of work.
* Reads exclude soft-deleted rows by default.
* Domain errors are raised via :mod:`app.core.exceptions`.
"""

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.enums import (
    ApprovalApproverKind,
    ApprovalDecisionAction,
    ApprovalRequestStatus,
    ApprovalRequestStepStatus,
    ApprovalStepDecisionRule,
    ApprovalSubjectType,
)
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import (
    ApprovalComment,
    ApprovalDecision,
    ApprovalFlow,
    ApprovalFlowStep,
    ApprovalFlowStepApprover,
    ApprovalRequest,
    ApprovalRequestStep,
)


# ============================================================
# FLOW REPOSITORY
# ============================================================


class ApprovalFlowRepository:
    """CRUD for flow/step/approver definitions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ----- Read --------------------------------------------------------

    def _base_flow_query(self):
        return (
            self.db.query(ApprovalFlow)
            .filter(ApprovalFlow.is_deleted.is_(False))
        )

    def get_by_id(self, flow_id: int) -> Optional[ApprovalFlow]:
        return (
            self._base_flow_query().filter(ApprovalFlow.id == flow_id).first()
        )

    def get_required_by_id(self, flow_id: int) -> ApprovalFlow:
        flow = self.get_by_id(flow_id)
        if not flow:
            raise NotFoundError(
                message="Approval flow not found.",
                detail={"flow_id": flow_id},
            )
        return flow

    def get_by_code(
        self,
        *,
        subject_type: ApprovalSubjectType,
        code: str,
    ) -> Optional[ApprovalFlow]:
        normalized = code.strip().upper().replace(" ", "_")
        return (
            self._base_flow_query()
            .filter(
                ApprovalFlow.subject_type == subject_type,
                func.upper(ApprovalFlow.code) == normalized,
            )
            .first()
        )

    def get_default_for_subject(
        self,
        subject_type: ApprovalSubjectType,
    ) -> Optional[ApprovalFlow]:
        return (
            self._base_flow_query()
            .filter(
                ApprovalFlow.subject_type == subject_type,
                ApprovalFlow.is_default.is_(True),
                ApprovalFlow.is_active.is_(True),
            )
            .first()
        )

    def list_flows(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        subject_type: Optional[ApprovalSubjectType] = None,
        search: Optional[str] = None,
        active_only: bool = True,
    ) -> tuple[list[ApprovalFlow], int]:
        query = self._base_flow_query()
        if active_only:
            query = query.filter(ApprovalFlow.is_active.is_(True))
        if subject_type is not None:
            query = query.filter(ApprovalFlow.subject_type == subject_type)
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(ApprovalFlow.name).like(term),
                    func.lower(ApprovalFlow.code).like(term),
                )
            )
        total = query.with_entities(func.count(ApprovalFlow.id)).scalar() or 0
        items = (
            query.order_by(
                ApprovalFlow.subject_type.asc(),
                ApprovalFlow.code.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def get_steps(self, flow_id: int) -> list[ApprovalFlowStep]:
        return (
            self.db.query(ApprovalFlowStep)
            .filter(
                ApprovalFlowStep.flow_id == flow_id,
                ApprovalFlowStep.is_deleted.is_(False),
            )
            .order_by(ApprovalFlowStep.step_order.asc())
            .all()
        )

    def get_step_required(self, step_id: int) -> ApprovalFlowStep:
        step = (
            self.db.query(ApprovalFlowStep)
            .filter(
                ApprovalFlowStep.id == step_id,
                ApprovalFlowStep.is_deleted.is_(False),
            )
            .first()
        )
        if not step:
            raise NotFoundError(
                message="Approval flow step not found.",
                detail={"step_id": step_id},
            )
        return step

    def get_step_approvers(self, step_id: int) -> list[ApprovalFlowStepApprover]:
        return (
            self.db.query(ApprovalFlowStepApprover)
            .filter(
                ApprovalFlowStepApprover.step_id == step_id,
                ApprovalFlowStepApprover.is_deleted.is_(False),
            )
            .all()
        )

    # ----- Write -------------------------------------------------------

    def create_flow_with_steps(
        self,
        *,
        code: str,
        name: str,
        description: Optional[str],
        subject_type: ApprovalSubjectType,
        is_default: bool,
        sla_hours: Optional[int],
        auto_cancel_after_hours: Optional[int],
        notify_on_submit: bool,
        notify_on_decision: bool,
        steps_payload: list[dict[str, Any]],
        actor_user_id: Optional[int] = None,
    ) -> ApprovalFlow:
        normalized_code = code.strip().upper().replace(" ", "_")
        if self.get_by_code(subject_type=subject_type, code=normalized_code):
            raise AlreadyExistsError(
                message="An approval flow with this code already exists for the subject type.",
                detail={"subject_type": str(subject_type), "code": normalized_code},
            )

        flow = ApprovalFlow(
            code=normalized_code,
            name=name,
            description=description,
            subject_type=subject_type,
            is_default=bool(is_default),
            sla_hours=sla_hours,
            auto_cancel_after_hours=auto_cancel_after_hours,
            notify_on_submit=bool(notify_on_submit),
            notify_on_decision=bool(notify_on_decision),
            created_by_id=actor_user_id,
            updated_by_id=actor_user_id,
        )
        self.db.add(flow)
        self.db.flush()

        # If this flow is is_default, unset other defaults for the subject type.
        if flow.is_default:
            self._clear_other_defaults(subject_type=subject_type, keep_id=flow.id)

        # Create steps + approvers.
        for step_payload in steps_payload:
            approvers = step_payload.pop("approvers", []) or []
            step = ApprovalFlowStep(
                flow_id=flow.id,
                step_order=step_payload["step_order"],
                name=step_payload["name"],
                description=step_payload.get("description"),
                decision_rule=ApprovalStepDecisionRule(step_payload.get("decision_rule") or ApprovalStepDecisionRule.ANY_OF),
                required_approvals=int(step_payload.get("required_approvals", 1) or 1),
                allow_self_approval=bool(step_payload.get("allow_self_approval", False)),
                sla_hours=step_payload.get("sla_hours"),
                is_optional=bool(step_payload.get("is_optional", False)),
                created_by_id=actor_user_id,
                updated_by_id=actor_user_id,
            )
            self.db.add(step)
            self.db.flush()

            for approver_payload in approvers:
                approver = ApprovalFlowStepApprover(
                    step_id=step.id,
                    approver_kind=ApprovalApproverKind(approver_payload["approver_kind"]),
                    user_id=approver_payload.get("user_id"),
                    role_id=approver_payload.get("role_id"),
                    department_id=approver_payload.get("department_id"),
                    dynamic_token=approver_payload.get("dynamic_token"),
                    is_required=bool(approver_payload.get("is_required", False)),
                    notes=approver_payload.get("notes"),
                    created_by_id=actor_user_id,
                    updated_by_id=actor_user_id,
                )
                self.db.add(approver)

        self.db.flush()
        self.db.refresh(flow)
        return flow

    def _clear_other_defaults(
        self,
        *,
        subject_type: ApprovalSubjectType,
        keep_id: int,
    ) -> None:
        rows = (
            self._base_flow_query()
            .filter(
                ApprovalFlow.subject_type == subject_type,
                ApprovalFlow.id != keep_id,
                ApprovalFlow.is_default.is_(True),
            )
            .all()
        )
        for row in rows:
            row.is_default = False
            self.db.add(row)

    def update_flow(
        self,
        flow: ApprovalFlow,
        *,
        actor_user_id: Optional[int] = None,
        **fields: Any,
    ) -> ApprovalFlow:
        for key, value in fields.items():
            if value is None:
                continue
            setattr(flow, key, value)
        flow.updated_by_id = actor_user_id
        self.db.add(flow)
        self.db.flush()
        if flow.is_default:
            self._clear_other_defaults(
                subject_type=flow.subject_type, keep_id=flow.id
            )
            self.db.flush()
        self.db.refresh(flow)
        return flow

    def soft_delete_flow(
        self, flow: ApprovalFlow, *, actor_user_id: Optional[int] = None
    ) -> ApprovalFlow:
        flow.soft_delete(deleted_by_id=actor_user_id)
        self.db.add(flow)
        self.db.flush()
        return flow


# ============================================================
# REQUEST REPOSITORY
# ============================================================


class ApprovalRequestRepository:
    """CRUD for runtime approval requests, steps, decisions, comments."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ----- Read --------------------------------------------------------

    def get_required_by_id(self, request_id: int) -> ApprovalRequest:
        request = (
            self.db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.id == request_id,
                ApprovalRequest.is_deleted.is_(False),
            )
            .first()
        )
        if not request:
            raise NotFoundError(
                message="Approval request not found.",
                detail={"request_id": request_id},
            )
        return request

    def get_by_id(self, request_id: int) -> Optional[ApprovalRequest]:
        return (
            self.db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.id == request_id,
                ApprovalRequest.is_deleted.is_(False),
            )
            .first()
        )

    def get_steps(self, request_id: int) -> list[ApprovalRequestStep]:
        return (
            self.db.query(ApprovalRequestStep)
            .filter(
                ApprovalRequestStep.request_id == request_id,
                ApprovalRequestStep.is_deleted.is_(False),
            )
            .order_by(ApprovalRequestStep.step_order.asc())
            .all()
        )

    def get_step_required(self, step_id: int) -> ApprovalRequestStep:
        step = (
            self.db.query(ApprovalRequestStep)
            .filter(
                ApprovalRequestStep.id == step_id,
                ApprovalRequestStep.is_deleted.is_(False),
            )
            .first()
        )
        if not step:
            raise NotFoundError(
                message="Approval request step not found.",
                detail={"step_id": step_id},
            )
        return step

    def get_active_step(
        self, request_id: int
    ) -> Optional[ApprovalRequestStep]:
        """Backwards-compat helper: return the lowest-ordered active step."""
        steps = self.get_active_steps(request_id)
        return steps[0] if steps else None

    def get_active_steps(
        self, request_id: int
    ) -> list[ApprovalRequestStep]:
        """
        Return all currently active steps for a request, in step_order.

        With parallel-group flows there can be more than one IN_PROGRESS
        step at a time; sequential flows always return at most one row.
        """
        return (
            self.db.query(ApprovalRequestStep)
            .filter(
                ApprovalRequestStep.request_id == request_id,
                ApprovalRequestStep.is_deleted.is_(False),
                ApprovalRequestStep.status.in_(
                    [
                        ApprovalRequestStepStatus.PENDING,
                        ApprovalRequestStepStatus.IN_PROGRESS,
                    ]
                ),
            )
            .order_by(ApprovalRequestStep.step_order.asc())
            .all()
        )

    def get_step_decisions(self, step_id: int) -> list[ApprovalDecision]:
        return (
            self.db.query(ApprovalDecision)
            .filter(
                ApprovalDecision.request_step_id == step_id,
                ApprovalDecision.is_deleted.is_(False),
            )
            .order_by(ApprovalDecision.decided_at.asc())
            .all()
        )

    def has_user_decided(
        self, *, step_id: int, user_id: int
    ) -> bool:
        return (
            self.db.query(ApprovalDecision.id)
            .filter(
                ApprovalDecision.request_step_id == step_id,
                ApprovalDecision.decided_by_user_id == user_id,
                ApprovalDecision.action.in_(
                    [
                        ApprovalDecisionAction.APPROVE,
                        ApprovalDecisionAction.REJECT,
                    ]
                ),
                ApprovalDecision.is_deleted.is_(False),
            )
            .first()
            is not None
        )

    def get_comments(self, request_id: int) -> list[ApprovalComment]:
        return (
            self.db.query(ApprovalComment)
            .filter(
                ApprovalComment.request_id == request_id,
                ApprovalComment.is_deleted.is_(False),
            )
            .order_by(ApprovalComment.posted_at.asc())
            .all()
        )

    # ----- Write -------------------------------------------------------

    def create_request(
        self,
        *,
        flow_id: int,
        subject_type: ApprovalSubjectType,
        subject_id: Optional[int],
        requester_user_id: int,
        requester_staff_profile_id: Optional[int],
        department_id: Optional[int],
        facility_id: Optional[int],
        title: str,
        description: Optional[str],
        payload: Optional[dict],
        priority: Optional[str],
        actor_user_id: Optional[int] = None,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            flow_id=flow_id,
            subject_type=subject_type,
            subject_id=subject_id,
            requester_user_id=requester_user_id,
            requester_staff_profile_id=requester_staff_profile_id,
            department_id=department_id,
            facility_id=facility_id,
            title=title,
            description=description,
            payload=payload,
            priority=priority,
            status=ApprovalRequestStatus.DRAFT,
            created_by_id=actor_user_id,
            updated_by_id=actor_user_id,
        )
        self.db.add(request)
        self.db.flush()
        self.db.refresh(request)
        return request

    def create_request_step(
        self,
        *,
        request_id: int,
        flow_step: ApprovalFlowStep,
        eligible_user_ids: list[int],
        approver_specs: list[dict],
        initial_status: ApprovalRequestStepStatus = ApprovalRequestStepStatus.PENDING,
        actor_user_id: Optional[int] = None,
    ) -> ApprovalRequestStep:
        step = ApprovalRequestStep(
            request_id=request_id,
            flow_step_id=flow_step.id,
            step_order=flow_step.step_order,
            name=flow_step.name,
            decision_rule=flow_step.decision_rule,
            required_approvals=flow_step.required_approvals,
            is_optional=flow_step.is_optional,
            parallel_group=flow_step.parallel_group,
            condition_snapshot=flow_step.condition,
            eligible_user_ids=eligible_user_ids,
            approver_specs=approver_specs,
            status=initial_status,
            created_by_id=actor_user_id,
            updated_by_id=actor_user_id,
        )
        if initial_status == ApprovalRequestStepStatus.SKIPPED:
            step.completed_at = datetime.now(timezone.utc)
        self.db.add(step)
        self.db.flush()
        self.db.refresh(step)
        return step

    def update_request(
        self,
        request: ApprovalRequest,
        *,
        actor_user_id: Optional[int] = None,
        **fields: Any,
    ) -> ApprovalRequest:
        for key, value in fields.items():
            setattr(request, key, value)
        request.updated_by_id = actor_user_id
        self.db.add(request)
        self.db.flush()
        return request

    def update_request_step(
        self,
        step: ApprovalRequestStep,
        *,
        actor_user_id: Optional[int] = None,
        **fields: Any,
    ) -> ApprovalRequestStep:
        for key, value in fields.items():
            setattr(step, key, value)
        step.updated_by_id = actor_user_id
        self.db.add(step)
        self.db.flush()
        return step

    def record_decision(
        self,
        *,
        request_id: int,
        request_step_id: int,
        decided_by_user_id: int,
        action: ApprovalDecisionAction,
        comment: Optional[str],
        delegated_to_user_id: Optional[int] = None,
        actor_user_id: Optional[int] = None,
    ) -> ApprovalDecision:
        decision = ApprovalDecision(
            request_id=request_id,
            request_step_id=request_step_id,
            decided_by_user_id=decided_by_user_id,
            action=action,
            comment=comment,
            delegated_to_user_id=delegated_to_user_id,
            decided_at=datetime.now(timezone.utc),
            created_by_id=actor_user_id,
            updated_by_id=actor_user_id,
        )
        self.db.add(decision)
        self.db.flush()
        self.db.refresh(decision)
        return decision

    def add_comment(
        self,
        *,
        request_id: int,
        author_user_id: int,
        body: str,
        actor_user_id: Optional[int] = None,
    ) -> ApprovalComment:
        comment = ApprovalComment(
            request_id=request_id,
            author_user_id=author_user_id,
            body=body,
            posted_at=datetime.now(timezone.utc),
            created_by_id=actor_user_id,
            updated_by_id=actor_user_id,
        )
        self.db.add(comment)
        self.db.flush()
        self.db.refresh(comment)
        return comment

    def soft_delete_request(
        self,
        request: ApprovalRequest,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ApprovalRequest:
        request.soft_delete(deleted_by_id=actor_user_id)
        self.db.add(request)
        self.db.flush()
        return request


# ============================================================
# QUERY REPOSITORY (list/filter helpers)
# ============================================================


class ApprovalQueryRepository:
    """Read-only filters for the inbox / outbox / status views."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_requests(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        requester_user_id: Optional[int] = None,
        subject_type: Optional[ApprovalSubjectType] = None,
        statuses: Optional[Iterable[ApprovalRequestStatus]] = None,
        flow_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> tuple[list[ApprovalRequest], int]:
        query = self.db.query(ApprovalRequest).filter(
            ApprovalRequest.is_deleted.is_(False)
        )
        if requester_user_id is not None:
            query = query.filter(
                ApprovalRequest.requester_user_id == requester_user_id
            )
        if subject_type is not None:
            query = query.filter(ApprovalRequest.subject_type == subject_type)
        if statuses:
            query = query.filter(ApprovalRequest.status.in_(list(statuses)))
        if flow_id is not None:
            query = query.filter(ApprovalRequest.flow_id == flow_id)
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(func.lower(ApprovalRequest.title).like(term))

        total = query.with_entities(func.count(ApprovalRequest.id)).scalar() or 0
        items = (
            query.order_by(ApprovalRequest.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def list_pending_for_user(
        self,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        subject_type: Optional[ApprovalSubjectType] = None,
    ) -> tuple[list[ApprovalRequest], int]:
        """
        Find requests that have an active step where ``user_id`` is in
        the eligible_user_ids snapshot AND has not yet decided.
        """
        # Pull active steps where the JSON eligible list contains user_id.
        # PostgreSQL JSON containment is handled via ``@>`` but we keep
        # it portable by widening the candidate set with a direct fetch
        # and filtering in Python — the eligible_user_ids list is small.
        active_steps_q = (
            self.db.query(ApprovalRequestStep)
            .filter(
                ApprovalRequestStep.is_deleted.is_(False),
                ApprovalRequestStep.status.in_(
                    [
                        ApprovalRequestStepStatus.PENDING,
                        ApprovalRequestStepStatus.IN_PROGRESS,
                    ]
                ),
            )
        )
        active_steps = active_steps_q.all()

        candidate_request_ids: list[int] = []
        for step in active_steps:
            eligible = step.eligible_user_ids or []
            if user_id in eligible:
                # Skip if the user has already decided.
                already_decided = (
                    self.db.query(ApprovalDecision.id)
                    .filter(
                        ApprovalDecision.request_step_id == step.id,
                        ApprovalDecision.decided_by_user_id == user_id,
                        ApprovalDecision.action.in_(
                            [
                                ApprovalDecisionAction.APPROVE,
                                ApprovalDecisionAction.REJECT,
                            ]
                        ),
                        ApprovalDecision.is_deleted.is_(False),
                    )
                    .first()
                )
                if already_decided is None:
                    candidate_request_ids.append(step.request_id)

        if not candidate_request_ids:
            return [], 0

        query = (
            self.db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.id.in_(set(candidate_request_ids)),
                ApprovalRequest.is_deleted.is_(False),
                ApprovalRequest.status.in_(
                    [
                        ApprovalRequestStatus.PENDING,
                        ApprovalRequestStatus.IN_PROGRESS,
                    ]
                ),
            )
        )
        if subject_type is not None:
            query = query.filter(ApprovalRequest.subject_type == subject_type)

        total = query.with_entities(func.count(ApprovalRequest.id)).scalar() or 0
        items = (
            query.order_by(ApprovalRequest.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)
