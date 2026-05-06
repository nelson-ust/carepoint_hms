# app/utils/approval_utils.py
from __future__ import annotations

"""
Helpers for the Approval Engine.

Two responsibilities:

1. Resolve the *eligible approver user IDs* for an
   ``ApprovalFlowStep``: given a step's approver targets (USER / ROLE /
   DEPARTMENT / DYNAMIC), return the set of User IDs who may act.

2. Evaluate a step's decision rule (ANY_OF / ALL_OF / N_OF_M) against
   the running tally of approvals/rejections recorded so far on an
   ``ApprovalRequestStep``.

The resolver is deliberately defensive: it returns an empty list when a
target can't be resolved, instead of raising. The service layer treats
an empty eligible-user set on the *active* step as a configuration
error and surfaces it to the operator via the request's
``decision_summary``.
"""

from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    ApprovalApproverKind,
    ApprovalDynamicApprover,
    ApprovalRequestStepStatus,
    ApprovalStepDecisionRule,
)
from app.models.all_models import (
    ApprovalFlowStepApprover,
    Department,
    Role,
    StaffProfile,
    User,
    UserRoleAssociation,
)


# ---------------------------------------------------------------------
# Dynamic-token → role-code fallback
# ---------------------------------------------------------------------
#
# For DYNAMIC tokens that don't map to a structural relationship (e.g.
# REQUESTER_MANAGER does), we look up users whose role code matches one
# of these. Tenants can override by configuring an explicit USER/ROLE
# approver row instead.

_DYNAMIC_ROLE_CODE_FALLBACK: dict[ApprovalDynamicApprover, tuple[str, ...]] = {
    ApprovalDynamicApprover.DEPARTMENT_HEAD: ("DEPARTMENT_HEAD", "DEPT_HEAD", "HOD"),
    ApprovalDynamicApprover.FACILITY_HEAD: ("FACILITY_HEAD", "HOSPITAL_ADMIN", "ADMINISTRATOR"),
    ApprovalDynamicApprover.HR_HEAD: ("HR_HEAD", "HR_MANAGER", "CHIEF_HR_OFFICER"),
    ApprovalDynamicApprover.FINANCE_HEAD: ("FINANCE_HEAD", "FINANCE_MANAGER", "CFO"),
}


# ---------------------------------------------------------------------
# Resolution context
# ---------------------------------------------------------------------


class _RequesterContext:
    """Cached lookup of requester attributes used during resolution."""

    __slots__ = ("user", "staff_profile", "department_id", "facility_id")

    def __init__(self, db: Session, user_id: int) -> None:
        self.user = db.query(User).filter(User.id == user_id).first()
        self.staff_profile: Optional[StaffProfile] = None
        if self.user:
            self.staff_profile = (
                db.query(StaffProfile)
                .filter(StaffProfile.user_id == user_id)
                .first()
            )
        self.department_id = (
            (self.staff_profile.department_id if self.staff_profile else None)
            or (self.user.department_id if self.user else None)
        )
        self.facility_id = (
            (self.staff_profile.facility_id if self.staff_profile else None)
            or (self.user.facility_id if self.user else None)
        )


# ---------------------------------------------------------------------
# Approver resolution
# ---------------------------------------------------------------------


def _users_with_role_codes(
    db: Session, role_codes: Iterable[str]
) -> list[int]:
    """Return active user IDs holding any role whose code matches."""
    role_codes = [c.strip().upper() for c in role_codes if c]
    if not role_codes:
        return []

    role_id_rows = (
        db.query(Role.id)
        .filter(Role.code.in_(role_codes), Role.is_deleted.is_(False))
        .all()
    )
    role_ids = [r[0] for r in role_id_rows]
    if not role_ids:
        return []

    rows = (
        db.query(UserRoleAssociation.user_id)
        .filter(
            UserRoleAssociation.role_id.in_(role_ids),
            UserRoleAssociation.is_deleted.is_(False),
            UserRoleAssociation.is_active.is_(True),
        )
        .all()
    )
    return sorted({r[0] for r in rows})


def _users_in_department(db: Session, department_id: int) -> list[int]:
    """Return active user IDs assigned to the given department."""
    rows = (
        db.query(StaffProfile.user_id)
        .filter(
            StaffProfile.department_id == department_id,
            StaffProfile.is_deleted.is_(False),
            StaffProfile.is_active.is_(True),
        )
        .all()
    )
    user_ids = {r[0] for r in rows}
    # Also include Users whose department_id directly matches (covers the
    # "user without a staff profile" case).
    rows2 = (
        db.query(User.id)
        .filter(
            User.department_id == department_id,
            User.is_deleted.is_(False),
            User.is_active.is_(True),
        )
        .all()
    )
    user_ids.update(r[0] for r in rows2)
    return sorted(user_ids)


def _users_for_role(db: Session, role_id: int) -> list[int]:
    """Return active user IDs holding a specific role row."""
    rows = (
        db.query(UserRoleAssociation.user_id)
        .filter(
            UserRoleAssociation.role_id == role_id,
            UserRoleAssociation.is_deleted.is_(False),
            UserRoleAssociation.is_active.is_(True),
        )
        .all()
    )
    return sorted({r[0] for r in rows})


def _resolve_dynamic(
    db: Session,
    token: ApprovalDynamicApprover,
    ctx: _RequesterContext,
) -> list[int]:
    """Resolve a dynamic token to user IDs."""
    if ctx.user is None:
        return []

    if token == ApprovalDynamicApprover.REQUESTER_MANAGER:
        if ctx.staff_profile and ctx.staff_profile.supervisor_staff_id:
            row = (
                db.query(StaffProfile.user_id)
                .filter(StaffProfile.id == ctx.staff_profile.supervisor_staff_id)
                .first()
            )
            return [row[0]] if row else []
        return []

    role_codes = _DYNAMIC_ROLE_CODE_FALLBACK.get(token, ())
    candidates = _users_with_role_codes(db, role_codes)

    # Scope DEPARTMENT_HEAD to the requester's department when possible.
    if token == ApprovalDynamicApprover.DEPARTMENT_HEAD and ctx.department_id:
        in_dept = set(_users_in_department(db, ctx.department_id))
        scoped = [u for u in candidates if u in in_dept]
        if scoped:
            return scoped

    # Scope FACILITY_HEAD to the requester's facility when possible.
    if token == ApprovalDynamicApprover.FACILITY_HEAD and ctx.facility_id:
        rows = (
            db.query(User.id)
            .filter(
                User.facility_id == ctx.facility_id,
                User.is_deleted.is_(False),
                User.is_active.is_(True),
            )
            .all()
        )
        scoped_ids = {r[0] for r in rows}
        scoped = [u for u in candidates if u in scoped_ids]
        if scoped:
            return scoped

    return candidates


def resolve_step_approvers(
    db: Session,
    *,
    approvers: list[ApprovalFlowStepApprover],
    requester_user_id: int,
    allow_self_approval: bool,
) -> list[int]:
    """
    Return the de-duplicated list of user IDs eligible to act on a step.

    The result honours ``allow_self_approval``: when False the requester
    is removed from the eligible set even if they technically match one
    of the approver targets (e.g. a manager submitting their own leave).
    """
    if not approvers:
        return []

    ctx = _RequesterContext(db, requester_user_id)

    eligible: set[int] = set()
    for approver in approvers:
        if approver.is_deleted or not approver.is_active:
            continue

        kind = approver.approver_kind

        if kind == ApprovalApproverKind.USER and approver.user_id:
            eligible.add(approver.user_id)
        elif kind == ApprovalApproverKind.ROLE and approver.role_id:
            eligible.update(_users_for_role(db, approver.role_id))
        elif kind == ApprovalApproverKind.DEPARTMENT and approver.department_id:
            eligible.update(_users_in_department(db, approver.department_id))
        elif kind == ApprovalApproverKind.DYNAMIC and approver.dynamic_token:
            eligible.update(_resolve_dynamic(db, approver.dynamic_token, ctx))

    if not allow_self_approval:
        eligible.discard(requester_user_id)

    return sorted(eligible)


def serialize_approver_specs(
    approvers: list[ApprovalFlowStepApprover],
) -> list[dict]:
    """Return a JSON-friendly snapshot of approver targets for audit."""
    out: list[dict] = []
    for a in approvers:
        out.append(
            {
                "id": a.id,
                "approver_kind": str(a.approver_kind),
                "user_id": a.user_id,
                "role_id": a.role_id,
                "department_id": a.department_id,
                "dynamic_token": str(a.dynamic_token) if a.dynamic_token else None,
                "is_required": bool(a.is_required),
            }
        )
    return out


# ---------------------------------------------------------------------
# Decision rule evaluation
# ---------------------------------------------------------------------


def evaluate_step_outcome(
    *,
    decision_rule: ApprovalStepDecisionRule,
    required_approvals: int,
    approvals_received: int,
    rejections_received: int,
    eligible_count: int,
    required_approver_count: int,
) -> ApprovalRequestStepStatus:
    """
    Decide whether a step should remain PENDING/IN_PROGRESS, transition
    to APPROVED, or transition to REJECTED, given the current tally.

    Rules
    -----
    * Any rejection on a step rejects the step. Whole-request rejection
      is handled at the service layer.
    * ANY_OF: 1 approval is enough.
    * ALL_OF: every is_required approver must approve. If
      ``required_approver_count`` is 0 (e.g. nobody marked required),
      ALL_OF degenerates to ANY_OF.
    * N_OF_M: ``required_approvals`` approvals are enough.
    """
    if rejections_received > 0:
        return ApprovalRequestStepStatus.REJECTED

    if eligible_count == 0:
        # Engine treats an unresolved step as still pending; the service
        # writes the warning into request.decision_summary.
        return ApprovalRequestStepStatus.PENDING

    if decision_rule == ApprovalStepDecisionRule.ANY_OF:
        if approvals_received >= 1:
            return ApprovalRequestStepStatus.APPROVED

    elif decision_rule == ApprovalStepDecisionRule.ALL_OF:
        target = required_approver_count if required_approver_count > 0 else 1
        if approvals_received >= target:
            return ApprovalRequestStepStatus.APPROVED

    elif decision_rule == ApprovalStepDecisionRule.N_OF_M:
        target = max(1, required_approvals)
        # Cap at the number of available approvers so misconfigured
        # required_approvals=10 against eligible_count=2 still resolves.
        target = min(target, eligible_count)
        if approvals_received >= target:
            return ApprovalRequestStepStatus.APPROVED

    return ApprovalRequestStepStatus.IN_PROGRESS


# ---------------------------------------------------------------------
# Condition DSL
# ---------------------------------------------------------------------
#
# Steps may carry an optional ``condition`` JSON expression evaluated at
# submit time. If the condition is False the step is auto-SKIPPED for
# that request. The DSL deliberately avoids any code-execution surface:
# it is a tiny declarative tree.
#
# Leaf:    {"field": "amount", "op": "gt", "value": 1000}
# Compose: {"all": [<expr>, <expr>, ...]}
#          {"any": [<expr>, ...]}
#          {"not": <expr>}
#
# ``field`` is a dotted path looked up against a context dict.  By
# default the lookup root is the request payload, but the engine also
# exposes ``request`` (subject_type, priority, requester_user_id,
# department_id, facility_id) so flows can branch on those fields too:
#
#     {"field": "request.priority", "op": "eq", "value": "URGENT"}
#     {"all": [
#         {"field": "amount", "op": "gt", "value": 1000},
#         {"field": "request.department_id", "op": "eq", "value": 7}
#     ]}
#
# Supported ops: eq, ne, gt, gte, lt, lte, in, not_in, exists, missing,
# truthy, falsy.

_LEAF_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in",
             "exists", "missing", "truthy", "falsy"}


def _resolve_path(path: str, context: dict[str, Any]) -> tuple[bool, Any]:
    """Return ``(found, value)`` for a dotted path lookup."""
    if not path:
        return False, None
    parts = path.split(".")
    node: Any = context
    # Bare names look up against the payload first, then fall back to
    # the top-level context (so {"field": "amount"} works even though
    # technically that's payload.amount).
    if parts[0] not in context and "payload" in context and isinstance(
        context.get("payload"), dict
    ):
        node = context["payload"]
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return False, None
    return True, node


def _evaluate_leaf(expr: dict[str, Any], context: dict[str, Any]) -> bool:
    op = (expr.get("op") or "").lower()
    if op not in _LEAF_OPS:
        # Unknown op -> safest behaviour is "treat as not matching"
        # rather than raising, so a misconfigured condition doesn't
        # block in-flight submissions.
        return False

    field = expr.get("field")
    if field is None:
        return False

    found, value = _resolve_path(str(field), context)

    if op == "exists":
        return found
    if op == "missing":
        return not found
    if op == "truthy":
        return bool(value) if found else False
    if op == "falsy":
        return (not bool(value)) if found else True

    target = expr.get("value")

    if not found:
        # Comparators against a missing field never match.
        return False

    try:
        if op == "eq":
            return value == target
        if op == "ne":
            return value != target
        if op == "gt":
            return value > target
        if op == "gte":
            return value >= target
        if op == "lt":
            return value < target
        if op == "lte":
            return value <= target
        if op == "in":
            return value in (target or [])
        if op == "not_in":
            return value not in (target or [])
    except TypeError:
        # Mismatched types between value and target — treat as no-match.
        return False
    return False


def evaluate_condition(
    expr: Optional[dict[str, Any]],
    context: dict[str, Any],
) -> bool:
    """
    Evaluate a step ``condition`` against a context dict.

    A missing/None expression is treated as ``True`` so steps without
    conditions always run. Errors and unknown shapes default to False
    so a malformed condition can't accidentally let a sensitive step
    through.
    """
    if not expr:
        return True

    if not isinstance(expr, dict):
        return False

    if "all" in expr:
        clauses = expr["all"] or []
        if not isinstance(clauses, list):
            return False
        return all(evaluate_condition(c, context) for c in clauses)

    if "any" in expr:
        clauses = expr["any"] or []
        if not isinstance(clauses, list):
            return False
        return any(evaluate_condition(c, context) for c in clauses)

    if "not" in expr:
        return not evaluate_condition(expr["not"], context)

    if "field" in expr or "op" in expr:
        return _evaluate_leaf(expr, context)

    return False
