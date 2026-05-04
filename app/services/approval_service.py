# app/services/approval_service.py
from __future__ import annotations

"""
Approval engine service layer.

Two services exposed:

* :class:`ApprovalFlowService` — admin CRUD over flow definitions.
* :class:`ApprovalRequestService` — operator runtime: submit a request,
  approve / reject / delegate a step, comment, query inboxes.

Engine semantics
----------------
1. ``submit()`` materialises an ``ApprovalRequest`` from a flow,
   snapshots every step + approver target, resolves the eligible-user
   set for each step, opens the first step (PENDING → IN_PROGRESS), and
   records the submission timestamp.
2. ``decide()`` records an :class:`~app.models.all_models.ApprovalDecision`
   on the active step. The step's tally is updated and the
   :func:`~app.utils.approval_utils.evaluate_step_outcome` rule decides
   whether the step is APPROVED, REJECTED, or still IN_PROGRESS.
3. When the active step becomes APPROVED the engine advances to the
   next non-optional step. When it becomes REJECTED the whole request
   is rejected.
4. Subject-type finalization hooks (``_finalize_subject``) propagate the
   final status onto the underlying domain row when one is linked
   (LeaveRequest, StaffRequest, Timesheet, ...). Hook failures do not
   roll the approval back; they are recorded in ``decision_summary``.

Notifications
-------------
The service makes a best-effort call to
:class:`~app.services.notification_service.NotificationService` when one
can be imported. Notification failures never block the approval flow;
they are swallowed and logged.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    ApprovalDecisionAction,
    ApprovalRequestStatus,
    ApprovalRequestStepStatus,
    ApprovalSubjectType,
    LeaveStatus,
    StaffRequestStatus,
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
    StaffProfile,
    StaffRequest,
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
    """Runtime engine: submit, decide, comment, list."""

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

    def _open_step(
        self,
        request: ApprovalRequest,
        request_step: ApprovalRequestStep,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ApprovalRequestStep:
        request_step = self.request_repo.update_request_step(
            request_step,
            actor_user_id=actor_user_id,
            status=ApprovalRequestStepStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
        )
        self.request_repo.update_request(
            request,
            actor_user_id=actor_user_id,
            current_step_id=request_step.id,
            status=ApprovalRequestStatus.IN_PROGRESS,
        )
        return request_step

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

        # Materialise per-request step rows with eligible-user snapshots.
        warnings: list[str] = []
        first_runtime_step: Optional[ApprovalRequestStep] = None
        for flow_step in flow_steps:
            approvers = self.flow_repo.get_step_approvers(flow_step.id)
            eligible_user_ids = resolve_step_approvers(
                self.db,
                approvers=approvers,
                requester_user_id=requester_user_id,
                allow_self_approval=flow_step.allow_self_approval,
            )
            if not eligible_user_ids and not flow_step.is_optional:
                warnings.append(
                    f"Step '{flow_step.name}' (#{flow_step.step_order}) has no eligible approvers."
                )

            runtime_step = self.request_repo.create_request_step(
                request_id=request.id,
                flow_step=flow_step,
                eligible_user_ids=eligible_user_ids,
                approver_specs=serialize_approver_specs(approvers),
                actor_user_id=actor_user_id or requester_user_id,
            )
            if first_runtime_step is None:
                first_runtime_step = runtime_step

        if warnings:
            request = self.request_repo.update_request(
                request,
                actor_user_id=actor_user_id or requester_user_id,
                decision_summary="; ".join(warnings),
            )

        if payload.submit_now:
            if first_runtime_step is None:
                raise BadRequestError(
                    message="Failed to materialise approval steps for this flow.",
                    detail={"flow_id": flow.id},
                )
            request = self.request_repo.update_request(
                request,
                actor_user_id=actor_user_id or requester_user_id,
                status=ApprovalRequestStatus.PENDING,
                submitted_at=datetime.now(timezone.utc),
            )
            self._open_step(
                request,
                first_runtime_step,
                actor_user_id=actor_user_id or requester_user_id,
            )
            self._notify_safe(
                "approval_submitted",
                request=request,
                step=first_runtime_step,
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

        active_step = self.request_repo.get_active_step(request_id)
        if not active_step:
            raise BadRequestError(
                message="No active step is open for decisioning.",
                detail={"request_id": request_id},
            )

        eligible = active_step.eligible_user_ids or []
        if decider_user_id not in eligible:
            raise ForbiddenError(
                message="You are not an eligible approver for this step.",
                detail={
                    "request_id": request_id,
                    "step_id": active_step.id,
                },
            )

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
            self._advance_or_finalize(
                request, active_step, actor_user_id=actor_user_id or decider_user_id
            )
        elif outcome == ApprovalRequestStepStatus.REJECTED:
            active_step = self.request_repo.update_request_step(
                active_step,
                actor_user_id=actor_user_id or decider_user_id,
                status=ApprovalRequestStepStatus.REJECTED,
                completed_at=datetime.now(timezone.utc),
            )
            self._reject_request(
                request,
                actor_user_id=actor_user_id or decider_user_id,
                reason=payload.comment,
            )
        # Otherwise the step stays IN_PROGRESS waiting for more approvers.

        self.db.commit()
        return decision, self.request_repo.get_required_by_id(request_id)

    def _advance_or_finalize(
        self,
        request: ApprovalRequest,
        completed_step: ApprovalRequestStep,
        *,
        actor_user_id: Optional[int] = None,
    ) -> None:
        # Find the next non-skipped step in step_order.
        steps = self.request_repo.get_steps(request.id)
        next_step: Optional[ApprovalRequestStep] = None
        for step in steps:
            if step.step_order <= completed_step.step_order:
                continue
            if step.status == ApprovalRequestStepStatus.SKIPPED:
                continue
            next_step = step
            break

        if next_step is None:
            self._approve_request(request, actor_user_id=actor_user_id)
            return

        # Skip optional steps that have no eligible approvers.
        if next_step.is_optional and not (next_step.eligible_user_ids or []):
            self.request_repo.update_request_step(
                next_step,
                actor_user_id=actor_user_id,
                status=ApprovalRequestStepStatus.SKIPPED,
                completed_at=datetime.now(timezone.utc),
            )
            self._advance_or_finalize(
                request, next_step, actor_user_id=actor_user_id
            )
            return

        self._open_step(request, next_step, actor_user_id=actor_user_id)
        self._notify_safe(
            "approval_step_opened", request=request, step=next_step
        )

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
        """
        Propagate the approval outcome onto the linked domain row.

        Returns a warning string when finalization couldn't be applied
        (e.g. the linked row is missing); ``None`` on success or when
        no subject is linked.
        """
        if not request.subject_id:
            return None

        try:
            if request.subject_type == ApprovalSubjectType.LEAVE_REQUEST:
                row = (
                    self.db.query(LeaveRequest)
                    .filter(LeaveRequest.id == request.subject_id)
                    .first()
                )
                if not row:
                    return f"LeaveRequest #{request.subject_id} not found for finalization."
                row.status = (
                    LeaveStatus.APPROVED
                    if final == ApprovalRequestStatus.APPROVED
                    else LeaveStatus.REJECTED
                )
                row.decided_at = datetime.now(timezone.utc)
                row.decided_by_user_id = request.updated_by_id
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
                    StaffRequestStatus.APPROVED
                    if final == ApprovalRequestStatus.APPROVED
                    else StaffRequestStatus.REJECTED
                )
                row.decided_at = datetime.now(timezone.utc)
                row.decided_by_user_id = request.updated_by_id
                self.db.add(row)
                return None

            # TIMESHEET / REIMBURSEMENT / OVERTIME / SALARY_ADVANCE /
            # PROCUREMENT subjects: leave the hook open for module-owners
            # to extend. We don't auto-update those tables here because
            # their schema varies and we don't want to dictate behavior.
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
        self.db.commit()
        self._notify_safe("approval_cancelled", request=request)
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
    # Notification fan-out
    # ------------------------------------------------------------------

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
            }.get(event)
            if not template_code:
                return
            # NotificationService.dispatch_by_code is the convention used
            # elsewhere; gracefully no-op when the template isn't seeded.
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
