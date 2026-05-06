# app/services/approval_service.py
from __future__ import annotations

"""
Approval engine service layer.

Two services exposed:

* :class:`ApprovalFlowService` — admin CRUD over flow definitions.
* :class:`ApprovalRequestService` — operator runtime: submit a request,
  approve / reject / delegate / comment / cancel, plus admin-only
  reopen / force-close, plus a scheduler-friendly sweep that expires
  stale requests.

Engine semantics
----------------
1. ``submit()`` materialises an ``ApprovalRequest`` from a flow.
   Every flow step is snapshotted onto an ``ApprovalRequestStep`` row
   so the request's behaviour is frozen even if the flow is edited
   later. Each step's optional ``condition`` JSON is evaluated against
   the request payload; steps whose condition is False are immediately
   marked SKIPPED. Eligible approvers are resolved per step via
   :func:`~app.utils.approval_utils.resolve_step_approvers`.

2. After the snapshot pass, the engine activates the first work unit:
   either a single sequential step, or every step inside the lowest
   ``parallel_group``. Active steps move PENDING → IN_PROGRESS.

3. ``decide()`` records one approval/rejection/delegation against an
   IN_PROGRESS step on which the caller is eligible. The step's tally
   is updated and :func:`evaluate_step_outcome` decides whether the
   step is APPROVED, REJECTED, or still IN_PROGRESS. A REJECT on any
   step rejects the whole request.

4. When a step becomes APPROVED the engine looks for the next work
   unit. With parallel groups the request only advances past the
   group when *every* member is APPROVED or SKIPPED.

5. ``_finalize_subject`` propagates the terminal status onto the
   linked domain row (LeaveRequest, StaffRequest, Timesheet,
   OvertimeRecord). Hook failures do not roll the approval back;
   they're recorded in ``decision_summary``.

Audit
-----
Every recorded decision and lifecycle transition is also written to
``StaffAuditLog`` for tenant-side audit reporting.

Notifications
-------------
Best-effort dispatch to :class:`NotificationService` when available.
Notification errors never block the approval flow.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    ApprovalDecisionAction,
    ApprovalRequestStatus,
    ApprovalRequestStepStatus,
    ApprovalSubjectType,
    LeaveStatus,
    OvertimeStatus,
    StaffRequestStatus,
    TimesheetStatus,
)
from app.core.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)
from app.models.all_models import (
    ApprovalFlow,
    ApprovalRequest,
    ApprovalRequestStep,
    LeaveRequest,
    OvertimeRecord,
    StaffAuditLog,
    StaffProfile,
    StaffRequest,
    Timesheet,
    User,
)
from app.repositories.approval_repository import (
    ApprovalFlowRepository,
    ApprovalQueryRepository,
    ApprovalRequestRepository,
)
from app.schemas.approval_schemas import (
    ApprovalCommentCreateSchema,
    ApprovalDecisionCreateSchema,
    ApprovalFlowCreateSchema,
    ApprovalFlowUpdateSchema,
    ApprovalRequestCreateSchema,
)
from app.utils.approval_utils import (
    evaluate_condition,
    evaluate_step_outcome,
    resolve_step_approvers,
    serialize_approver_specs,
)


logger = logging.getLogger(__name__)


# ============================================================
# FLOW SERVICE
# ============================================================


class ApprovalFlowService:
    """Admin-facing CRUD for flow definitions."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.flow_repo = ApprovalFlowRepository(db)

    def list_flows(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        subject_type: Optional[ApprovalSubjectType] = None,
        search: Optional[str] = None,
        active_only: bool = True,
    ) -> tuple[list[ApprovalFlow], int]:
        return self.flow_repo.list_flows(
            skip=skip,
            limit=limit,
            subject_type=subject_type,
            search=search,
            active_only=active_only,
        )

    def get(self, flow_id: int) -> ApprovalFlow:
        return self.flow_repo.get_required_by_id(flow_id)

    def create(
        self,
        payload: ApprovalFlowCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ApprovalFlow:
        steps_payload = [s.model_dump() for s in payload.steps]
        flow = self.flow_repo.create_flow_with_steps(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            subject_type=payload.subject_type,
            is_default=payload.is_default,
            sla_hours=payload.sla_hours,
            auto_cancel_after_hours=payload.auto_cancel_after_hours,
            notify_on_submit=payload.notify_on_submit,
            notify_on_decision=payload.notify_on_decision,
            steps_payload=steps_payload,
            actor_user_id=actor_user_id,
        )
        self.db.commit()
        return self.flow_repo.get_required_by_id(flow.id)

    def update(
        self,
        flow_id: int,
        payload: ApprovalFlowUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ApprovalFlow:
        flow = self.flow_repo.get_required_by_id(flow_id)
        updates = payload.model_dump(exclude_unset=True)
        flow = self.flow_repo.update_flow(
            flow, actor_user_id=actor_user_id, **updates
        )
        self.db.commit()
        return self.flow_repo.get_required_by_id(flow.id)

    def soft_delete(
        self, flow_id: int, *, actor_user_id: Optional[int] = None
    ) -> ApprovalFlow:
        flow = self.flow_repo.get_required_by_id(flow_id)
        flow = self.flow_repo.soft_delete_flow(flow, actor_user_id=actor_user_id)
        self.db.commit()
        return flow


# ============================================================
# REQUEST SERVICE
# ============================================================


class ApprovalRequestService:
    """Runtime engine: submit, decide, comment, list, expire."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.flow_repo = ApprovalFlowRepository(db)
        self.request_repo = ApprovalRequestRepository(db)
        self.query_repo = ApprovalQueryRepository(db)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_flow(
        self,
        *,
        flow_id: Optional[int],
        flow_code: Optional[str],
        subject_type: ApprovalSubjectType,
    ) -> ApprovalFlow:
        if flow_id:
            flow = self.flow_repo.get_required_by_id(flow_id)
            if flow.subject_type != subject_type:
                raise BadRequestError(
                    message="Flow subject_type does not match the request subject_type.",
                    detail={
                        "flow_subject_type": str(flow.subject_type),
                        "request_subject_type": str(subject_type),
                    },
                )
            if not flow.is_active or flow.is_deleted:
                raise BadRequestError(
                    message="The selected approval flow is not active.",
                    detail={"flow_id": flow_id},
                )
            return flow

        if flow_code:
            flow = self.flow_repo.get_by_code(
                subject_type=subject_type, code=flow_code
            )
            if not flow:
                raise NotFoundError(
                    message="No approval flow with the provided code for this subject type.",
                    detail={"subject_type": str(subject_type), "flow_code": flow_code},
                )
            if not flow.is_active or flow.is_deleted:
                raise BadRequestError(
                    message="The selected approval flow is not active.",
                    detail={"flow_code": flow_code},
                )
            return flow

        flow = self.flow_repo.get_default_for_subject(subject_type)
        if not flow:
            raise NotFoundError(
                message="No default approval flow configured for this subject type.",
                detail={"subject_type": str(subject_type)},
            )
        return flow

    def _resolve_requester_context(
        self, requester_user_id: int
    ) -> tuple[Optional[StaffProfile], Optional[int], Optional[int]]:
        user = (
            self.db.query(User)
            .filter(User.id == requester_user_id)
            .first()
        )
        if not user:
            raise NotFoundError(
                message="Requester user not found.",
                detail={"user_id": requester_user_id},
            )
        staff = (
            self.db.query(StaffProfile)
            .filter(StaffProfile.user_id == requester_user_id)
            .first()
        )
        department_id = (
            (staff.department_id if staff else None) or user.department_id
        )
        facility_id = (
            (staff.facility_id if staff else None) or user.facility_id
        )
        return staff, department_id, facility_id

    def _build_condition_context(
        self,
        request: ApprovalRequest,
    ) -> dict[str, Any]:
        """Context dict exposed to step ``condition`` expressions."""
        return {
            "payload": request.payload or {},
            "request": {
                "subject_type": str(request.subject_type),
                "subject_id": request.subject_id,
                "priority": request.priority,
                "title": request.title,
                "department_id": request.department_id,
                "facility_id": request.facility_id,
                "requester_user_id": request.requester_user_id,
            },
        }

    def _is_runnable(self, step: ApprovalRequestStep) -> bool:
        return step.status in (
            ApprovalRequestStepStatus.PENDING,
            ApprovalRequestStepStatus.IN_PROGRESS,
        )

    # ------------------------------------------------------------------
    # Step activation (sequential + parallel-group aware)
    # ------------------------------------------------------------------

    def _activate_step(
        self,
        step: ApprovalRequestStep,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ApprovalRequestStep:
        return self.request_repo.update_request_step(
            step,
            actor_user_id=actor_user_id,
            status=ApprovalRequestStepStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
        )

    def _open_next_unit(
        self,
        request: ApprovalRequest,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Optional[list[ApprovalRequestStep]]:
        """
        Activate the next runnable work unit.

        A "unit" is either a single PENDING step (sequential) or every
        PENDING step that shares the lowest-ordered ``parallel_group``.
        Optional steps with no eligible approvers are auto-SKIPPED in
        place and the function recurses to find the next unit.

        Returns the list of newly-activated steps, or None when the
        request has no runnable steps left (caller should finalize).
        """
        steps = self.request_repo.get_steps(request.id)
        # Find the lowest-order step that is still PENDING.
        next_step: Optional[ApprovalRequestStep] = None
        for step in steps:
            if step.status == ApprovalRequestStepStatus.PENDING:
                next_step = step
                break

        if next_step is None:
            return None

        # Skip optional steps with no eligible approvers and recurse.
        if next_step.is_optional and not (next_step.eligible_user_ids or []):
            self.request_repo.update_request_step(
                next_step,
                actor_user_id=actor_user_id,
                status=ApprovalRequestStepStatus.SKIPPED,
                completed_at=datetime.now(timezone.utc),
            )
            return self._open_next_unit(request, actor_user_id=actor_user_id)

        if next_step.parallel_group:
            unit = [
                s for s in steps
                if s.parallel_group == next_step.parallel_group
                and s.status == ApprovalRequestStepStatus.PENDING
            ]
        else:
            unit = [next_step]

        opened: list[ApprovalRequestStep] = []
        for s in unit:
            opened.append(self._activate_step(s, actor_user_id=actor_user_id))

        # Reflect the most recent activation on the request header.
        first = sorted(opened, key=lambda s: s.step_order)[0]
        self.request_repo.update_request(
            request,
            actor_user_id=actor_user_id,
            current_step_id=first.id,
            status=ApprovalRequestStatus.IN_PROGRESS,
        )
        return opened

    def _unit_is_complete(
        self,
        request_id: int,
        completed_step: ApprovalRequestStep,
    ) -> bool:
        """Return True when the step's parallel-group is fully resolved."""
        if not completed_step.parallel_group:
            return True
        siblings = (
            self.db.query(ApprovalRequestStep)
            .filter(
                ApprovalRequestStep.request_id == request_id,
                ApprovalRequestStep.parallel_group == completed_step.parallel_group,
                ApprovalRequestStep.is_deleted.is_(False),
            )
            .all()
        )
        return all(
            s.status
            in (
                ApprovalRequestStepStatus.APPROVED,
                ApprovalRequestStepStatus.SKIPPED,
            )
            for s in siblings
        )

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    def submit(
        self,
        payload: ApprovalRequestCreateSchema,
        *,
        requester_user_id: int,
        actor_user_id: Optional[int] = None,
    ) -> ApprovalRequest:
        flow = self._resolve_flow(
            flow_id=payload.flow_id,
            flow_code=payload.flow_code,
            subject_type=payload.subject_type,
        )
        flow_steps = self.flow_repo.get_steps(flow.id)
        if not flow_steps:
            raise BadRequestError(
                message="The selected approval flow has no steps configured.",
                detail={"flow_id": flow.id},
            )

        staff, department_id, facility_id = self._resolve_requester_context(
            requester_user_id
        )

        request = self.request_repo.create_request(
            flow_id=flow.id,
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            requester_user_id=requester_user_id,
            requester_staff_profile_id=staff.id if staff else None,
            department_id=payload.department_id or department_id,
            facility_id=payload.facility_id or facility_id,
            title=payload.title,
            description=payload.description,
            payload=payload.payload,
            priority=payload.priority,
            actor_user_id=actor_user_id or requester_user_id,
        )

        if flow.auto_cancel_after_hours:
            self.request_repo.update_request(
                request,
                actor_user_id=actor_user_id or requester_user_id,
                expires_at=datetime.now(timezone.utc)
                + timedelta(hours=int(flow.auto_cancel_after_hours)),
            )

        # Materialise per-request step rows. Each step is evaluated
        # against the condition DSL — false-condition steps are
        # snapshotted as SKIPPED so they're visible in audit but never
        # block progress.
        warnings: list[str] = []
        condition_ctx = self._build_condition_context(request)

        for flow_step in flow_steps:
            condition_ok = evaluate_condition(flow_step.condition, condition_ctx)
            initial_status = (
                ApprovalRequestStepStatus.PENDING
                if condition_ok
                else ApprovalRequestStepStatus.SKIPPED
            )

            if condition_ok:
                approvers = self.flow_repo.get_step_approvers(flow_step.id)
                eligible_user_ids = resolve_step_approvers(
                    self.db,
                    approvers=approvers,
                    requester_user_id=requester_user_id,
                    allow_self_approval=flow_step.allow_self_approval,
                )
                if not eligible_user_ids and not flow_step.is_optional:
                    warnings.append(
                        f"Step '{flow_step.name}' (#{flow_step.step_order}) "
                        "has no eligible approvers."
                    )
                approver_specs = serialize_approver_specs(approvers)
            else:
                # Snapshot what would have applied even when skipped, for audit.
                approvers = self.flow_repo.get_step_approvers(flow_step.id)
                eligible_user_ids = []
                approver_specs = serialize_approver_specs(approvers)

            self.request_repo.create_request_step(
                request_id=request.id,
                flow_step=flow_step,
                eligible_user_ids=eligible_user_ids,
                approver_specs=approver_specs,
                initial_status=initial_status,
                actor_user_id=actor_user_id or requester_user_id,
            )

        if warnings:
            self.request_repo.update_request(
                request,
                actor_user_id=actor_user_id or requester_user_id,
                decision_summary="; ".join(warnings),
            )

        if payload.submit_now:
            request = self.request_repo.update_request(
                request,
                actor_user_id=actor_user_id or requester_user_id,
                status=ApprovalRequestStatus.PENDING,
                submitted_at=datetime.now(timezone.utc),
            )
            opened = self._open_next_unit(
                request, actor_user_id=actor_user_id or requester_user_id
            )
            if opened is None:
                # Every step was SKIPPED — the flow has nothing to ask
                # for, so we approve straight away.
                self._approve_request(
                    request,
                    actor_user_id=actor_user_id or requester_user_id,
                )
            else:
                for s in opened:
                    self._notify_safe(
                        "approval_step_opened", request=request, step=s
                    )
                self._notify_safe(
                    "approval_submitted", request=request, step=opened[0]
                )

        self._audit(
            "approval.submit",
            request=request,
            actor_user_id=actor_user_id or requester_user_id,
        )
        self.db.commit()
        return self.request_repo.get_required_by_id(request.id)

    # ------------------------------------------------------------------
    # Decide
    # ------------------------------------------------------------------

    def decide(
        self,
        request_id: int,
        payload: ApprovalDecisionCreateSchema,
        *,
        decider_user_id: int,
        actor_user_id: Optional[int] = None,
    ):
        request = self.request_repo.get_required_by_id(request_id)
        if request.status not in (
            ApprovalRequestStatus.PENDING,
            ApprovalRequestStatus.IN_PROGRESS,
        ):
            raise BadRequestError(
                message="This request is not awaiting decisions.",
                detail={"request_id": request_id, "status": str(request.status)},
            )

        active_steps = self.request_repo.get_active_steps(request_id)
        if not active_steps:
            raise BadRequestError(
                message="No active step is open for decisioning.",
                detail={"request_id": request_id},
            )

        # Resolve which step the caller is acting on. With parallel
        # groups multiple steps may be active for the same user; require
        # an explicit step_id when ambiguous.
        candidate_steps = [
            s for s in active_steps
            if decider_user_id in (s.eligible_user_ids or [])
        ]
        if not candidate_steps:
            raise ForbiddenError(
                message="You are not an eligible approver for any active step on this request.",
                detail={"request_id": request_id},
            )

        if payload.step_id:
            target = next(
                (s for s in candidate_steps if s.id == payload.step_id),
                None,
            )
            if not target:
                raise BadRequestError(
                    message=(
                        "The provided step_id is not active or you are "
                        "not eligible to decide on it."
                    ),
                    detail={
                        "request_id": request_id,
                        "step_id": payload.step_id,
                    },
                )
            active_step = target
        else:
            if len(candidate_steps) > 1:
                raise BadRequestError(
                    message=(
                        "Multiple active steps are available to you on "
                        "this request. Provide step_id to disambiguate."
                    ),
                    detail={
                        "request_id": request_id,
                        "candidate_step_ids": [s.id for s in candidate_steps],
                    },
                )
            active_step = candidate_steps[0]

        if self.request_repo.has_user_decided(
            step_id=active_step.id, user_id=decider_user_id
        ):
            raise BadRequestError(
                message="You have already recorded a decision on this step.",
                detail={
                    "request_id": request_id,
                    "step_id": active_step.id,
                },
            )

        decision = self.request_repo.record_decision(
            request_id=request_id,
            request_step_id=active_step.id,
            decided_by_user_id=decider_user_id,
            action=payload.action,
            comment=payload.comment,
            delegated_to_user_id=payload.delegated_to_user_id,
            actor_user_id=actor_user_id or decider_user_id,
        )

        # Delegation extends eligibility but does not advance the step.
        if payload.action == ApprovalDecisionAction.DELEGATE:
            new_eligible = list(active_step.eligible_user_ids or [])
            if (
                payload.delegated_to_user_id
                and payload.delegated_to_user_id not in new_eligible
            ):
                new_eligible.append(payload.delegated_to_user_id)
            self.request_repo.update_request_step(
                active_step,
                actor_user_id=actor_user_id or decider_user_id,
                eligible_user_ids=new_eligible,
            )
            self._audit(
                "approval.delegate",
                request=request,
                actor_user_id=actor_user_id or decider_user_id,
                payload={
                    "step_id": active_step.id,
                    "delegated_to_user_id": payload.delegated_to_user_id,
                },
            )
            self.db.commit()
            return decision, self.request_repo.get_required_by_id(request_id)

        # APPROVE / REJECT bumps tallies and re-evaluates the step.
        if payload.action == ApprovalDecisionAction.APPROVE:
            active_step = self.request_repo.update_request_step(
                active_step,
                actor_user_id=actor_user_id or decider_user_id,
                approvals_received=active_step.approvals_received + 1,
            )
        elif payload.action == ApprovalDecisionAction.REJECT:
            active_step = self.request_repo.update_request_step(
                active_step,
                actor_user_id=actor_user_id or decider_user_id,
                rejections_received=active_step.rejections_received + 1,
            )

        outcome = evaluate_step_outcome(
            decision_rule=active_step.decision_rule,
            required_approvals=active_step.required_approvals,
            approvals_received=active_step.approvals_received,
            rejections_received=active_step.rejections_received,
            eligible_count=len(active_step.eligible_user_ids or []),
            required_approver_count=sum(
                1
                for spec in (active_step.approver_specs or [])
                if spec.get("is_required")
            ),
        )

        if outcome == ApprovalRequestStepStatus.APPROVED:
            active_step = self.request_repo.update_request_step(
                active_step,
                actor_user_id=actor_user_id or decider_user_id,
                status=ApprovalRequestStepStatus.APPROVED,
                completed_at=datetime.now(timezone.utc),
            )
            self._audit(
                "approval.step_approved",
                request=request,
                actor_user_id=actor_user_id or decider_user_id,
                payload={"step_id": active_step.id},
            )
            if self._unit_is_complete(request_id, active_step):
                opened = self._open_next_unit(
                    request,
                    actor_user_id=actor_user_id or decider_user_id,
                )
                if opened is None:
                    self._approve_request(
                        request,
                        actor_user_id=actor_user_id or decider_user_id,
                    )
                else:
                    for s in opened:
                        self._notify_safe(
                            "approval_step_opened", request=request, step=s
                        )
        elif outcome == ApprovalRequestStepStatus.REJECTED:
            active_step = self.request_repo.update_request_step(
                active_step,
                actor_user_id=actor_user_id or decider_user_id,
                status=ApprovalRequestStepStatus.REJECTED,
                completed_at=datetime.now(timezone.utc),
            )
            self._audit(
                "approval.step_rejected",
                request=request,
                actor_user_id=actor_user_id or decider_user_id,
                payload={"step_id": active_step.id, "comment": payload.comment},
            )
            self._reject_request(
                request,
                actor_user_id=actor_user_id or decider_user_id,
                reason=payload.comment,
            )
        # else step stays IN_PROGRESS waiting for more approvers.

        self.db.commit()
        return decision, self.request_repo.get_required_by_id(request_id)

    def _approve_request(
        self,
        request: ApprovalRequest,
        *,
        actor_user_id: Optional[int] = None,
    ) -> None:
        request = self.request_repo.update_request(
            request,
            actor_user_id=actor_user_id,
            status=ApprovalRequestStatus.APPROVED,
            completed_at=datetime.now(timezone.utc),
            current_step_id=None,
        )
        warning = self._finalize_subject(
            request, final=ApprovalRequestStatus.APPROVED
        )
        if warning:
            self.request_repo.update_request(
                request,
                actor_user_id=actor_user_id,
                decision_summary=(
                    (request.decision_summary + "; " if request.decision_summary else "")
                    + warning
                ),
            )
        self._audit(
            "approval.approved",
            request=request,
            actor_user_id=actor_user_id,
        )
        self._notify_safe("approval_finalized", request=request)

    def _reject_request(
        self,
        request: ApprovalRequest,
        *,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> None:
        request = self.request_repo.update_request(
            request,
            actor_user_id=actor_user_id,
            status=ApprovalRequestStatus.REJECTED,
            completed_at=datetime.now(timezone.utc),
            current_step_id=None,
            decision_summary=reason or request.decision_summary,
        )
        warning = self._finalize_subject(
            request, final=ApprovalRequestStatus.REJECTED
        )
        if warning:
            self.request_repo.update_request(
                request,
                actor_user_id=actor_user_id,
                decision_summary=(
                    (request.decision_summary + "; " if request.decision_summary else "")
                    + warning
                ),
            )
        self._audit(
            "approval.rejected",
            request=request,
            actor_user_id=actor_user_id,
            payload={"reason": reason},
        )
        self._notify_safe("approval_finalized", request=request)

    # ------------------------------------------------------------------
    # Subject-type finalization hooks
    # ------------------------------------------------------------------

    def _finalize_subject(
        self,
        request: ApprovalRequest,
        *,
        final: ApprovalRequestStatus,
    ) -> Optional[str]:
        """Propagate the approval outcome onto the linked domain row."""
        if not request.subject_id:
            return None

        approved = final == ApprovalRequestStatus.APPROVED
        actor = request.updated_by_id
        now = datetime.now(timezone.utc)

        try:
            if request.subject_type == ApprovalSubjectType.LEAVE_REQUEST:
                row = (
                    self.db.query(LeaveRequest)
                    .filter(LeaveRequest.id == request.subject_id)
                    .first()
                )
                if not row:
                    return f"LeaveRequest #{request.subject_id} not found for finalization."
                row.status = LeaveStatus.APPROVED if approved else LeaveStatus.REJECTED
                row.decided_at = now
                row.decided_by_user_id = actor
                self.db.add(row)
                return None

            if request.subject_type == ApprovalSubjectType.STAFF_REQUEST:
                row = (
                    self.db.query(StaffRequest)
                    .filter(StaffRequest.id == request.subject_id)
                    .first()
                )
                if not row:
                    return f"StaffRequest #{request.subject_id} not found for finalization."
                row.status = (
                    StaffRequestStatus.APPROVED if approved else StaffRequestStatus.REJECTED
                )
                row.decided_at = now
                row.decided_by_user_id = actor
                self.db.add(row)
                return None

            if request.subject_type == ApprovalSubjectType.OVERTIME:
                row = (
                    self.db.query(OvertimeRecord)
                    .filter(OvertimeRecord.id == request.subject_id)
                    .first()
                )
                if not row:
                    return f"OvertimeRecord #{request.subject_id} not found for finalization."
                row.status = (
                    OvertimeStatus.APPROVED if approved else OvertimeStatus.REJECTED
                )
                row.approved_at = now if approved else None
                row.approved_by_user_id = actor if approved else None
                self.db.add(row)
                return None

            if request.subject_type == ApprovalSubjectType.TIMESHEET:
                row = (
                    self.db.query(Timesheet)
                    .filter(Timesheet.id == request.subject_id)
                    .first()
                )
                if not row:
                    return f"Timesheet #{request.subject_id} not found for finalization."
                row.status = (
                    TimesheetStatus.APPROVED if approved else TimesheetStatus.REJECTED
                )
                row.approved_at = now if approved else None
                row.approved_by_user_id = actor if approved else None
                self.db.add(row)
                return None

            # REIMBURSEMENT / SALARY_ADVANCE / PROCUREMENT / GENERIC: no
            # backing tables in the codebase yet. Module owners can wire
            # finalization here when those models land — the ApprovalRequest
            # row already carries subject_id + payload for them to read.
            return None
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "Approval finalization hook raised for subject_type=%s subject_id=%s",
                request.subject_type,
                request.subject_id,
            )
            return f"Finalization hook failed: {exc!s}"

    # ------------------------------------------------------------------
    # Comments / cancellation / queries
    # ------------------------------------------------------------------

    def add_comment(
        self,
        request_id: int,
        payload: ApprovalCommentCreateSchema,
        *,
        author_user_id: int,
        actor_user_id: Optional[int] = None,
    ):
        self.request_repo.get_required_by_id(request_id)  # existence check
        comment = self.request_repo.add_comment(
            request_id=request_id,
            author_user_id=author_user_id,
            body=payload.body,
            actor_user_id=actor_user_id or author_user_id,
        )
        self.db.commit()
        return comment

    def cancel(
        self,
        request_id: int,
        *,
        actor_user_id: int,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        request = self.request_repo.get_required_by_id(request_id)
        if request.requester_user_id != actor_user_id:
            raise ForbiddenError(
                message="Only the requester can cancel an approval request.",
                detail={"request_id": request_id},
            )
        if request.status not in (
            ApprovalRequestStatus.DRAFT,
            ApprovalRequestStatus.PENDING,
            ApprovalRequestStatus.IN_PROGRESS,
        ):
            raise BadRequestError(
                message="This request can no longer be cancelled.",
                detail={"status": str(request.status)},
            )
        request = self.request_repo.update_request(
            request,
            actor_user_id=actor_user_id,
            status=ApprovalRequestStatus.CANCELLED,
            completed_at=datetime.now(timezone.utc),
            current_step_id=None,
            decision_summary=reason or "Cancelled by requester.",
        )
        self._audit(
            "approval.cancelled",
            request=request,
            actor_user_id=actor_user_id,
            payload={"reason": reason},
        )
        self.db.commit()
        self._notify_safe("approval_cancelled", request=request)
        return self.request_repo.get_required_by_id(request_id)

    def admin_force_close(
        self,
        request_id: int,
        *,
        actor_user_id: int,
        approve: bool,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """Admin override: mark a request APPROVED or REJECTED outright."""
        request = self.request_repo.get_required_by_id(request_id)
        if request.status in (
            ApprovalRequestStatus.APPROVED,
            ApprovalRequestStatus.REJECTED,
            ApprovalRequestStatus.CANCELLED,
        ):
            raise BadRequestError(
                message="This request is already in a terminal state.",
                detail={"status": str(request.status)},
            )

        # Close every still-active step so audit reflects the override.
        for step in self.request_repo.get_active_steps(request_id):
            self.request_repo.update_request_step(
                step,
                actor_user_id=actor_user_id,
                status=(
                    ApprovalRequestStepStatus.APPROVED
                    if approve
                    else ApprovalRequestStepStatus.REJECTED
                ),
                completed_at=datetime.now(timezone.utc),
            )

        if approve:
            self._approve_request(request, actor_user_id=actor_user_id)
        else:
            self._reject_request(
                request, actor_user_id=actor_user_id, reason=reason
            )
        self._audit(
            "approval.admin_force_close",
            request=request,
            actor_user_id=actor_user_id,
            payload={"approve": approve, "reason": reason},
        )
        self.db.commit()
        return self.request_repo.get_required_by_id(request_id)

    def admin_reopen_step(
        self,
        request_id: int,
        step_id: int,
        *,
        actor_user_id: int,
    ) -> ApprovalRequest:
        """Admin override: re-open a previously closed step on an in-flight request."""
        request = self.request_repo.get_required_by_id(request_id)
        step = self.request_repo.get_step_required(step_id)
        if step.request_id != request_id:
            raise BadRequestError(
                message="Step does not belong to this request.",
                detail={"request_id": request_id, "step_id": step_id},
            )
        if request.status in (
            ApprovalRequestStatus.APPROVED,
            ApprovalRequestStatus.REJECTED,
            ApprovalRequestStatus.CANCELLED,
        ):
            raise BadRequestError(
                message="Cannot reopen a step on a finalized request.",
                detail={"status": str(request.status)},
            )

        # Reset the step. Existing decisions stay for audit; counters reset.
        self.request_repo.update_request_step(
            step,
            actor_user_id=actor_user_id,
            status=ApprovalRequestStepStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            approvals_received=0,
            rejections_received=0,
        )
        self.request_repo.update_request(
            request,
            actor_user_id=actor_user_id,
            current_step_id=step.id,
            status=ApprovalRequestStatus.IN_PROGRESS,
        )
        self._audit(
            "approval.step_reopened",
            request=request,
            actor_user_id=actor_user_id,
            payload={"step_id": step.id},
        )
        self.db.commit()
        return self.request_repo.get_required_by_id(request_id)

    def get(self, request_id: int) -> ApprovalRequest:
        return self.request_repo.get_required_by_id(request_id)

    def list_my_pending(
        self,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        subject_type: Optional[ApprovalSubjectType] = None,
    ) -> tuple[list[ApprovalRequest], int]:
        return self.query_repo.list_pending_for_user(
            user_id=user_id,
            skip=skip,
            limit=limit,
            subject_type=subject_type,
        )

    def list_requests(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        requester_user_id: Optional[int] = None,
        subject_type: Optional[ApprovalSubjectType] = None,
        statuses: Optional[list[ApprovalRequestStatus]] = None,
        flow_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> tuple[list[ApprovalRequest], int]:
        return self.query_repo.list_requests(
            skip=skip,
            limit=limit,
            requester_user_id=requester_user_id,
            subject_type=subject_type,
            statuses=statuses,
            flow_id=flow_id,
            search=search,
        )

    # ------------------------------------------------------------------
    # Scheduler entry point
    # ------------------------------------------------------------------

    def expire_stale_requests(self, *, batch_limit: int = 200) -> int:
        """
        Auto-cancel in-flight requests whose ``expires_at`` has passed.

        Wired into the per-tenant scheduler tick. Returns the number of
        requests transitioned to EXPIRED.
        """
        now = datetime.now(timezone.utc)
        candidates = (
            self.db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.is_deleted.is_(False),
                ApprovalRequest.status.in_(
                    [
                        ApprovalRequestStatus.PENDING,
                        ApprovalRequestStatus.IN_PROGRESS,
                    ]
                ),
                ApprovalRequest.expires_at.is_not(None),
                ApprovalRequest.expires_at <= now,
            )
            .order_by(ApprovalRequest.expires_at.asc())
            .limit(batch_limit)
            .all()
        )
        if not candidates:
            return 0

        transitioned = 0
        for request in candidates:
            try:
                # Close any still-active steps without recording decisions.
                for step in self.request_repo.get_active_steps(request.id):
                    self.request_repo.update_request_step(
                        step,
                        status=ApprovalRequestStepStatus.SKIPPED,
                        completed_at=now,
                    )
                self.request_repo.update_request(
                    request,
                    status=ApprovalRequestStatus.EXPIRED,
                    completed_at=now,
                    current_step_id=None,
                    decision_summary=(
                        (request.decision_summary + "; " if request.decision_summary else "")
                        + "Auto-expired due to SLA breach."
                    ),
                )
                self._audit("approval.expired", request=request)
                self._notify_safe("approval_expired", request=request)
                transitioned += 1
            except Exception:  # pragma: no cover - defensive
                logger.exception(
                    "Failed to auto-expire approval request id=%s", request.id
                )

        if transitioned:
            self.db.commit()
        return transitioned

    # ------------------------------------------------------------------
    # Audit + notification fan-out
    # ------------------------------------------------------------------

    def _audit(
        self,
        action: str,
        *,
        request: ApprovalRequest,
        actor_user_id: Optional[int] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        try:
            self.db.add(
                StaffAuditLog(
                    actor_user_id=actor_user_id,
                    entity="approval_request",
                    entity_id=request.id,
                    action=action[:20],
                    after_data={
                        "request_id": request.id,
                        "status": str(request.status),
                        "subject_type": str(request.subject_type),
                        "subject_id": request.subject_id,
                        "extra": payload or {},
                    },
                    occurred_at=datetime.now(timezone.utc),
                )
            )
            self.db.flush()
        except Exception:
            logger.debug(
                "StaffAuditLog write failed for action=%s", action, exc_info=True
            )

    def _notify_safe(self, event: str, **kwargs: Any) -> None:
        """Best-effort notification dispatch. Never raises."""
        try:
            from app.services.notification_service import NotificationService  # type: ignore[import-not-found]
        except Exception:
            return

        try:
            ns = NotificationService(self.db)
            request: Optional[ApprovalRequest] = kwargs.get("request")
            if not request:
                return
            template_code = {
                "approval_submitted": "APPROVAL_SUBMITTED",
                "approval_step_opened": "APPROVAL_STEP_OPENED",
                "approval_finalized": "APPROVAL_FINALIZED",
                "approval_cancelled": "APPROVAL_CANCELLED",
                "approval_expired": "APPROVAL_EXPIRED",
            }.get(event)
            if not template_code:
                return
            dispatch = getattr(ns, "dispatch_by_code", None)
            if not callable(dispatch):
                return
            dispatch(
                template_code=template_code,
                user_id=request.requester_user_id,
                context={
                    "request_id": request.id,
                    "title": request.title,
                    "status": str(request.status),
                    "subject_type": str(request.subject_type),
                },
            )
        except Exception:
            logger.debug(
                "Approval notification dispatch failed for event=%s; ignored.",
                event,
                exc_info=True,
            )
