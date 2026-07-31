# app/services/approval_service.py
from __future__ import annotations

"""
Generic approval engine.

RequestType → ApprovalFlow → ApprovalStep define *what* needs approving and
*by whom*. Submitting a subject creates an ApprovalRequest that walks the
flow's ordered steps; every action taken on a step writes an ApprovalLog row.
When the request reaches a terminal state, the outcome is propagated to the
originating domain row via ``_finalize_subject``.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import (
    ApprovalApproverKind,
    ApprovalDynamicApprover,
    ApprovalLogAction,
    ApprovalRequestStatus,
    ApprovalStepDecisionRule,
    RequestTypeCode,
)
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.all_models import (
    ApprovalFlow,
    ApprovalLog,
    ApprovalRequest,
    ApprovalStep,
    Role,
    RequestType,
    StaffProfile,
    User,
    UserRoleAssociation,
)

logger = logging.getLogger(__name__)


def _bulk_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    s = str(value).strip().upper()
    if s in ("YES", "Y", "TRUE", "1"):
        return True
    if s in ("NO", "N", "FALSE", "0"):
        return False
    return default


def _bulk_int(value: Any) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    return int(float(str(value).strip()))


def _bulk_result(total: int, created: int, errors: list[dict[str, Any]], *, noun: str) -> dict[str, Any]:
    failed = len(errors)
    plural = noun + "s"
    if created and not failed:
        message = f"All {created} {plural} imported successfully."
    elif created and failed:
        message = f"Imported {created} {plural}; {failed} row(s) had problems."
    elif not created and failed:
        message = f"No {plural} imported — all {failed} row(s) had problems."
    else:
        message = "The file had no data rows to import."
    return {
        "success": failed == 0 and created > 0,
        "message": message,
        "total_rows": total,
        "created": created,
        "failed": failed,
        "errors": errors,
    }

# Role-code fallbacks used to resolve DYNAMIC approver tokens.
_DYNAMIC_ROLE_FALLBACK: dict[ApprovalDynamicApprover, tuple[str, ...]] = {
    ApprovalDynamicApprover.DEPARTMENT_HEAD: ("DEPARTMENT_HEAD", "DEPT_HEAD", "HOD"),
    ApprovalDynamicApprover.FACILITY_HEAD: ("FACILITY_HEAD", "HOSPITAL_ADMIN", "ADMINISTRATOR", "ADMIN"),
    ApprovalDynamicApprover.HR_HEAD: ("HR_HEAD", "HR_MANAGER", "CHIEF_HR_OFFICER"),
    ApprovalDynamicApprover.FINANCE_HEAD: ("FINANCE_HEAD", "FINANCE_MANAGER", "CFO", "ADMIN"),
    ApprovalDynamicApprover.REQUESTER_MANAGER: ("DEPARTMENT_HEAD", "DEPT_HEAD", "HOD", "HR_MANAGER"),
}


# ============================================================
# Request types
# ============================================================


class RequestTypeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    #: Canonical built-in request types (mirrors db_sync._BUILTIN_REQUEST_TYPES).
    BUILTINS: tuple[tuple[str, str], ...] = (
        ("PAYROLL_RUN", "Payroll Run"),
        ("LEAVE_REQUEST", "Leave Request"),
        ("TIMESHEET", "Timesheet"),
        ("OVERTIME", "Overtime"),
        ("REIMBURSEMENT", "Reimbursement"),
        ("SALARY_ADVANCE", "Salary Advance"),
        ("PROCUREMENT", "Procurement"),
        ("STAFF_REQUEST", "Staff Request"),
        ("GENERIC", "Generic Request"),
    )

    def ensure_builtins(self) -> None:
        """
        Idempotently make sure the canonical built-in request types exist.

        Startup schema sync also seeds these, but that sync can be disabled
        (AUTO_SYNC_TENANT_SCHEMAS=False), so the service self-heals on read:
        any missing built-in is created here. Safe under races — a concurrent
        duplicate insert is rolled back and ignored.
        """
        try:
            have = {
                c for (c,) in self.db.query(RequestType.code)
                .filter(RequestType.is_deleted.is_(False))
                .all()
            }
            missing = [(c, n) for c, n in self.BUILTINS if c not in have]
            if not missing:
                return
            for code, name in missing:
                self.db.add(RequestType(code=code, name=name, is_active=True))
            self.db.commit()
            logger.info("Seeded %d built-in request type(s): %s", len(missing), [c for c, _ in missing])
        except Exception:  # pragma: no cover - defensive (e.g. unique race)
            self.db.rollback()

    def list(self, *, only_active: bool = False) -> list[RequestType]:
        self.ensure_builtins()
        q = self.db.query(RequestType).filter(RequestType.is_deleted.is_(False))
        if only_active:
            q = q.filter(RequestType.is_active.is_(True))
        return q.order_by(RequestType.code.asc()).all()

    def get_by_code(self, code: str) -> Optional[RequestType]:
        return (
            self.db.query(RequestType)
            .filter(RequestType.code == code, RequestType.is_deleted.is_(False))
            .first()
        )

    def get_or_create(self, code: str, *, name: Optional[str] = None) -> RequestType:
        rec = self.get_by_code(code)
        if rec:
            return rec
        rec = RequestType(code=code, name=name or code.replace("_", " ").title(), is_active=True)
        self.db.add(rec)
        self.db.flush()
        return rec

    def create(self, *, code: str, name: str, description: Optional[str] = None, is_active: bool = True) -> RequestType:
        code = code.strip().upper()
        if self.get_by_code(code):
            raise BadRequestError(message=f"Request type '{code}' already exists.")
        rec = RequestType(code=code, name=name.strip(), description=description, is_active=is_active)
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def bulk_create(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Create request types from parsed template rows. Code + Name required; code unique."""
        errors: list[dict[str, Any]] = []
        created = 0
        seen: set[str] = set()
        for entry in rows:
            row_no = entry.get("row")
            data = entry.get("data", {}) or {}
            try:
                code = str(data.get("code") or "").strip().upper()
                name = str(data.get("name") or "").strip()
                if not code:
                    raise ValueError("Code is required.")
                if not name:
                    raise ValueError("Name is required.")
                if code in seen:
                    raise ValueError(f"Duplicate code '{code}' in this file.")
                if self.get_by_code(code):
                    raise ValueError(f"Request type '{code}' already exists.")
                with self.db.begin_nested():
                    rec = RequestType(
                        code=code, name=name,
                        description=data.get("description"),
                        is_active=_bulk_bool(data.get("is_active"), True),
                    )
                    self.db.add(rec)
                    self.db.flush()
                seen.add(code)
                created += 1
            except ValueError as exc:
                errors.append({"row": row_no, "message": str(exc)})
            except Exception as exc:  # pragma: no cover
                errors.append({"row": row_no, "message": f"Could not save this row: {exc}"})
        if created:
            self.db.commit()
        return _bulk_result(len(rows), created, errors, noun="request type")


# ============================================================
# Flows + steps (configuration)
# ============================================================


class ApprovalFlowService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.types = RequestTypeService(db)

    def list_flows(self, *, request_type: Optional[str] = None) -> list[ApprovalFlow]:
        q = self.db.query(ApprovalFlow).filter(ApprovalFlow.is_deleted.is_(False))
        if request_type:
            rt = self.types.get_by_code(request_type)
            q = q.filter(ApprovalFlow.request_type_id == (rt.id if rt else -1))
        return q.order_by(ApprovalFlow.request_type_id.asc(), ApprovalFlow.id.asc()).all()

    def get(self, flow_id: int) -> ApprovalFlow:
        flow = (
            self.db.query(ApprovalFlow)
            .filter(ApprovalFlow.id == flow_id, ApprovalFlow.is_deleted.is_(False))
            .first()
        )
        if flow is None:
            raise NotFoundError(message="Approval flow not found.")
        return flow

    def create(self, data) -> ApprovalFlow:
        rt = self.types.get_or_create(data.request_type)
        if data.is_default:
            self._clear_default(rt.id)
        flow = ApprovalFlow(
            request_type_id=rt.id,
            code=data.code.strip(),
            name=data.name.strip(),
            description=data.description,
            is_default=data.is_default,
            is_active=data.is_active,
        )
        self.db.add(flow)
        self.db.flush()
        for st in sorted(data.steps, key=lambda s: s.step_order):
            self.db.add(self._step_from_schema(flow.id, st))
        self.db.commit()
        self.db.refresh(flow)
        return flow

    def update(self, flow_id: int, data) -> ApprovalFlow:
        flow = self.get(flow_id)
        if data.name is not None:
            flow.name = data.name.strip()
        if data.description is not None:
            flow.description = data.description
        if data.is_active is not None:
            flow.is_active = data.is_active
        if data.is_default is not None:
            if data.is_default:
                self._clear_default(flow.request_type_id)
            flow.is_default = data.is_default
        if data.steps is not None:
            for old in self.db.query(ApprovalStep).filter(ApprovalStep.flow_id == flow.id).all():
                self.db.delete(old)
            self.db.flush()
            for st in sorted(data.steps, key=lambda s: s.step_order):
                self.db.add(self._step_from_schema(flow.id, st))
        self.db.commit()
        self.db.refresh(flow)
        return flow

    def soft_delete(self, flow_id: int) -> None:
        flow = self.get(flow_id)
        flow.is_deleted = True
        flow.is_active = False
        self.db.commit()

    def _clear_default(self, request_type_id: int) -> None:
        for f in (
            self.db.query(ApprovalFlow)
            .filter(ApprovalFlow.request_type_id == request_type_id, ApprovalFlow.is_default.is_(True))
            .all()
        ):
            f.is_default = False

    def _step_from_schema(self, flow_id: int, st) -> ApprovalStep:
        return ApprovalStep(
            flow_id=flow_id,
            step_order=st.step_order,
            name=st.name.strip(),
            approver_kind=st.approver_kind,
            approver_user_id=st.approver_user_id,
            approver_role_id=st.approver_role_id,
            approver_department_id=st.approver_department_id,
            dynamic_token=st.dynamic_token,
            decision_rule=st.decision_rule,
            required_approvals=st.required_approvals,
            allow_self_approval=st.allow_self_approval,
            is_active=st.is_active,
        )

    # ── bulk import ──────────────────────────────────────────────────

    def _resolve_role(self, ref: str):
        ref = str(ref).strip()
        if not ref:
            return None
        return (
            self.db.query(Role).filter(func.upper(Role.code) == ref.upper()).first()
            or self.db.query(Role).filter(func.upper(Role.name) == ref.upper()).first()
        )

    def bulk_create_flows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Create approval flows (no steps) from parsed rows. Request type must already exist."""
        errors: list[dict[str, Any]] = []
        created = 0
        seen: set[tuple[int, str]] = set()
        for entry in rows:
            row_no = entry.get("row")
            data = entry.get("data", {}) or {}
            try:
                rt_code = str(data.get("request_type") or "").strip().upper()
                code = str(data.get("code") or "").strip()
                name = str(data.get("name") or "").strip()
                if not rt_code:
                    raise ValueError("Request Type Code is required.")
                if not code:
                    raise ValueError("Flow Code is required.")
                if not name:
                    raise ValueError("Flow Name is required.")
                rt = self.types.get_by_code(rt_code)
                if not rt and rt_code in {c for c, _ in RequestTypeService.BUILTINS}:
                    # Built-in codes are canonical — create on demand rather
                    # than failing when startup seeding hasn't run.
                    rt = self.types.get_or_create(rt_code)
                if not rt:
                    raise ValueError(f"Unknown request type '{rt_code}'. Upload it first.")
                key = (rt.id, code.upper())
                if key in seen:
                    raise ValueError(f"Duplicate flow '{code}' for '{rt_code}' in this file.")
                existing = (
                    self.db.query(ApprovalFlow)
                    .filter(
                        ApprovalFlow.request_type_id == rt.id,
                        func.upper(ApprovalFlow.code) == code.upper(),
                        ApprovalFlow.is_deleted.is_(False),
                    )
                    .first()
                )
                if existing:
                    raise ValueError(f"Flow '{code}' already exists for '{rt_code}'.")
                is_default = _bulk_bool(data.get("is_default"), False)
                with self.db.begin_nested():
                    if is_default:
                        self._clear_default(rt.id)
                    flow = ApprovalFlow(
                        request_type_id=rt.id,
                        code=code,
                        name=name,
                        description=data.get("description"),
                        is_default=is_default,
                        is_active=_bulk_bool(data.get("is_active"), True),
                    )
                    self.db.add(flow)
                    self.db.flush()
                seen.add(key)
                created += 1
            except ValueError as exc:
                errors.append({"row": row_no, "message": str(exc)})
            except Exception as exc:  # pragma: no cover
                errors.append({"row": row_no, "message": f"Could not save this row: {exc}"})
        if created:
            self.db.commit()
        return _bulk_result(len(rows), created, errors, noun="flow")

    def bulk_create_steps(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """Create approval steps from parsed rows. ROLE and DYNAMIC approvers only."""
        errors: list[dict[str, Any]] = []
        created = 0
        seen: set[tuple[int, int]] = set()
        for entry in rows:
            row_no = entry.get("row")
            data = entry.get("data", {}) or {}
            try:
                rt_code = str(data.get("request_type") or "").strip().upper()
                flow_code = str(data.get("flow_code") or "").strip()
                name = str(data.get("name") or "").strip()
                if not flow_code:
                    raise ValueError("Flow Code is required.")
                if not name:
                    raise ValueError("Step Name is required.")
                try:
                    order = _bulk_int(data.get("step_order"))
                except (TypeError, ValueError):
                    raise ValueError("Step Order must be a whole number.")
                if order is None or order < 1:
                    raise ValueError("Step Order must be a positive whole number.")

                # Resolve the flow (code is unique only within a request type).
                q = self.db.query(ApprovalFlow).filter(
                    func.upper(ApprovalFlow.code) == flow_code.upper(),
                    ApprovalFlow.is_deleted.is_(False),
                )
                if rt_code:
                    rt = self.types.get_by_code(rt_code)
                    if not rt:
                        raise ValueError(f"Unknown request type '{rt_code}'.")
                    q = q.filter(ApprovalFlow.request_type_id == rt.id)
                matches = q.all()
                if not matches:
                    raise ValueError(f"Unknown flow '{flow_code}'. Upload the flow first.")
                if len(matches) > 1:
                    raise ValueError(f"Flow code '{flow_code}' exists under multiple request types — set Request Type Code.")
                flow = matches[0]

                kind_raw = str(data.get("approver_kind") or "").strip().upper()
                if kind_raw not in ("ROLE", "DYNAMIC"):
                    raise ValueError("Approver Kind must be ROLE or DYNAMIC.")

                role_id = None
                token = None
                if kind_raw == "ROLE":
                    role_ref = data.get("approver_role")
                    if not role_ref:
                        raise ValueError("Role is required when Approver Kind is ROLE.")
                    role = self._resolve_role(str(role_ref))
                    if not role:
                        raise ValueError(f"Unknown role '{role_ref}'.")
                    role_id = role.id
                else:
                    tok_raw = str(data.get("dynamic_token") or "").strip().upper()
                    if not tok_raw:
                        raise ValueError("Dynamic Token is required when Approver Kind is DYNAMIC.")
                    try:
                        token = ApprovalDynamicApprover(tok_raw)
                    except ValueError:
                        raise ValueError(f"Unknown Dynamic Token '{tok_raw}'.")

                rule_raw = str(data.get("decision_rule") or "ANY_OF").strip().upper()
                try:
                    rule = ApprovalStepDecisionRule(rule_raw)
                except ValueError:
                    raise ValueError(f"Unknown Decision Rule '{rule_raw}'.")

                try:
                    req_appr = _bulk_int(data.get("required_approvals")) or 1
                except (TypeError, ValueError):
                    raise ValueError("Required Approvals must be a whole number.")
                if req_appr < 1:
                    req_appr = 1

                key = (flow.id, order)
                if key in seen:
                    raise ValueError(f"Duplicate step order {order} for flow '{flow_code}' in this file.")
                dup = (
                    self.db.query(ApprovalStep)
                    .filter(ApprovalStep.flow_id == flow.id, ApprovalStep.step_order == order)
                    .first()
                )
                if dup:
                    raise ValueError(f"Step order {order} already exists on flow '{flow_code}'.")

                with self.db.begin_nested():
                    step = ApprovalStep(
                        flow_id=flow.id,
                        step_order=order,
                        name=name,
                        approver_kind=ApprovalApproverKind(kind_raw),
                        approver_role_id=role_id,
                        dynamic_token=token,
                        decision_rule=rule,
                        required_approvals=req_appr,
                        allow_self_approval=_bulk_bool(data.get("allow_self_approval"), False),
                        is_active=_bulk_bool(data.get("is_active"), True),
                    )
                    self.db.add(step)
                    self.db.flush()
                seen.add(key)
                created += 1
            except ValueError as exc:
                errors.append({"row": row_no, "message": str(exc)})
            except Exception as exc:  # pragma: no cover
                errors.append({"row": row_no, "message": f"Could not save this row: {exc}"})
        if created:
            self.db.commit()
        return _bulk_result(len(rows), created, errors, noun="step")


# ============================================================
# Runtime requests
# ============================================================


class ApprovalRequestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.types = RequestTypeService(db)

    # ---- helpers -----------------------------------------------------

    def _default_flow(self, request_type_id: int) -> Optional[ApprovalFlow]:
        q = self.db.query(ApprovalFlow).filter(
            ApprovalFlow.request_type_id == request_type_id,
            ApprovalFlow.is_active.is_(True),
            ApprovalFlow.is_deleted.is_(False),
        )
        return (
            q.order_by(ApprovalFlow.is_default.desc(), ApprovalFlow.id.asc()).first()
        )

    def _flow_steps(self, flow_id: int) -> list[ApprovalStep]:
        return (
            self.db.query(ApprovalStep)
            .filter(
                ApprovalStep.flow_id == flow_id,
                ApprovalStep.is_active.is_(True),
                ApprovalStep.is_deleted.is_(False),
            )
            .order_by(ApprovalStep.step_order.asc())
            .all()
        )

    def _step_at(self, flow_id: int, step_order: Optional[int]) -> Optional[ApprovalStep]:
        if step_order is None:
            return None
        return next((s for s in self._flow_steps(flow_id) if s.step_order == step_order), None)

    def _next_step_order(self, flow_id: int, current: int) -> Optional[int]:
        higher = [s.step_order for s in self._flow_steps(flow_id) if s.step_order > current]
        return min(higher) if higher else None

    def _users_with_roles(self, role_ids: list[int]) -> set[int]:
        if not role_ids:
            return set()
        rows = (
            self.db.query(UserRoleAssociation.user_id)
            .filter(
                UserRoleAssociation.role_id.in_(role_ids),
                UserRoleAssociation.is_active.is_(True),
                UserRoleAssociation.is_deleted.is_(False),
            )
            .all()
        )
        return {r[0] for r in rows}

    def _role_ids_for_codes(self, codes: tuple[str, ...]) -> list[int]:
        rows = (
            self.db.query(Role.id)
            .filter(Role.code.in_(list(codes)), Role.is_deleted.is_(False))
            .all()
        )
        return [r[0] for r in rows]

    def eligible_user_ids(self, step: ApprovalStep, request: ApprovalRequest) -> set[int]:
        """Resolve the set of user ids allowed to act on a step."""
        if step is None:
            return set()
        kind = step.approver_kind
        if kind == ApprovalApproverKind.USER and step.approver_user_id:
            return {step.approver_user_id}
        if kind == ApprovalApproverKind.ROLE and step.approver_role_id:
            return self._users_with_roles([step.approver_role_id])
        if kind == ApprovalApproverKind.DEPARTMENT and step.approver_department_id:
            rows = (
                self.db.query(StaffProfile.user_id)
                .filter(
                    StaffProfile.department_id == step.approver_department_id,
                    StaffProfile.is_deleted.is_(False),
                )
                .all()
            )
            return {r[0] for r in rows if r[0]}
        if kind == ApprovalApproverKind.DYNAMIC and step.dynamic_token:
            codes = _DYNAMIC_ROLE_FALLBACK.get(step.dynamic_token, ())
            return self._users_with_roles(self._role_ids_for_codes(codes))
        return set()

    def first_step_approvers(self, request_type: str, *, flow_id: Optional[int] = None,
                             exclude_user_id: Optional[int] = None) -> dict:
        """
        Resolve the flow + first active step for a request type and return the
        users eligible to approve that step (for the pre-submit dropdown).
        """
        rt = self.types.get_by_code(str(request_type).strip().upper())
        if rt is None:
            raise NotFoundError(message=f"Request type '{request_type}' not found.")
        flow = None
        if flow_id:
            flow = self.db.query(ApprovalFlow).filter(
                ApprovalFlow.id == flow_id, ApprovalFlow.is_deleted.is_(False)).first()
        if flow is None:
            flow = self._default_flow(rt.id)
        if flow is None:
            raise NotFoundError(message=f"No approval flow is configured for {rt.code}.")
        steps = self._flow_steps(flow.id)
        if not steps:
            return {"flow_id": flow.id, "flow_name": flow.name, "step_order": None,
                    "step_name": None, "approvers": []}
        step = steps[0]
        ids = self.eligible_user_ids(step, None)
        if exclude_user_id and not step.allow_self_approval:
            ids = ids - {exclude_user_id}
        users = (
            self.db.query(User).filter(User.id.in_(ids)).all() if ids else []
        )
        approvers = sorted(
            (
                {
                    "user_id": u.id,
                    "name": f"{u.first_name} {u.last_name}".strip() or u.username,
                    "email": u.email,
                }
                for u in users
            ),
            key=lambda a: a["name"].lower(),
        )
        return {"flow_id": flow.id, "flow_name": flow.name, "step_order": step.step_order,
                "step_name": step.name, "approvers": approvers}

    def _staff_display(self, staff_profile_id: Optional[int]) -> Optional[str]:
        if not staff_profile_id:
            return None
        sp = self.db.query(StaffProfile).filter(StaffProfile.id == staff_profile_id).first()
        if sp is None:
            return None
        u = self.db.query(User).filter(User.id == sp.user_id).first() if sp.user_id else None
        if u is None:
            return f"Staff #{staff_profile_id}"
        return f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username

    def _subject_snapshot(self, code: str, subject_id: Optional[int]) -> Optional[dict]:
        """
        Human-readable snapshot of the originating domain record, captured at
        submission time and stored on ``ApprovalRequest.payload``. This makes
        the generic Request row self-describing — approvers see WHAT they are
        approving on the request page and in the notification emails, and the
        snapshot survives even if the domain row is later edited.
        """
        if not subject_id:
            return None
        try:
            if code == RequestTypeCode.LEAVE_REQUEST:
                from app.models.all_models import LeaveRequest, LeaveType
                row = self.db.query(LeaveRequest).filter(LeaveRequest.id == subject_id).first()
                if row is None:
                    return None
                lt = self.db.query(LeaveType).filter(LeaveType.id == row.leave_type_id).first()
                return {
                    "staff": self._staff_display(row.staff_profile_id),
                    "leave_type": (lt.name if lt else f"#{row.leave_type_id}"),
                    "start_date": str(row.start_date),
                    "end_date": str(row.end_date),
                    "leave_days": str(row.days_requested or ""),
                    "reason": row.reason or "",
                }

            if code == RequestTypeCode.TIMESHEET:
                from app.models.all_models import Timesheet, TimesheetEntry
                row = self.db.query(Timesheet).filter(Timesheet.id == subject_id).first()
                if row is None:
                    return None
                leave_days = (
                    self.db.query(TimesheetEntry)
                    .filter(TimesheetEntry.timesheet_id == row.id, TimesheetEntry.is_leave.is_(True))
                    .count()
                )
                return {
                    "staff": self._staff_display(row.staff_profile_id),
                    "period": f"{row.period_start} → {row.period_end}",
                    "regular_hours": str(row.total_regular_hours or 0),
                    "overtime_hours": str(row.total_overtime_hours or 0),
                    "absence_days": str(row.absence_days or 0),
                    "leave_days": str(leave_days),
                    "notes": row.notes or "",
                }

            if code == RequestTypeCode.SALARY_ADVANCE:
                from app.models.all_models import SalaryAdvance
                row = self.db.query(SalaryAdvance).filter(SalaryAdvance.id == subject_id).first()
                if row is None:
                    return None
                return {
                    "staff": self._staff_display(row.staff_profile_id),
                    "amount": f"₦{row.amount:,.2f}",
                    "repayment_month": str(row.repayment_month),
                    "reason": row.reason or "",
                }

            if code == RequestTypeCode.REIMBURSEMENT:
                from app.models.all_models import ReimbursementRequest
                row = self.db.query(ReimbursementRequest).filter(ReimbursementRequest.id == subject_id).first()
                if row is None:
                    return None
                return {
                    "staff": self._staff_display(row.staff_profile_id),
                    "expense_date": str(row.expense_date),
                    "amount": f"₦{row.amount:,.2f}",
                    "category": row.category,
                    "description": row.description or "",
                    "receipt": row.receipt_url or "",
                }

            if code == RequestTypeCode.PAYROLL_RUN:
                from app.models.all_models import PayrollRun
                row = self.db.query(PayrollRun).filter(PayrollRun.id == subject_id).first()
                if row is None:
                    return None
                out = {"payroll_period": f"{getattr(row, 'period_start', '')} → {getattr(row, 'period_end', '')}"}
                for attr, label in (("total_gross", "total_gross"), ("total_net", "total_net"),
                                    ("total_deductions", "total_deductions"), ("staff_count", "staff_count")):
                    val = getattr(row, attr, None)
                    if val is not None:
                        out[label] = f"₦{val:,.2f}" if "total" in attr else str(val)
                return out

            if code == RequestTypeCode.OVERTIME:
                from app.models.all_models import OvertimeRecord
                row = self.db.query(OvertimeRecord).filter(OvertimeRecord.id == subject_id).first()
                if row is None:
                    return None
                return {
                    "staff": self._staff_display(getattr(row, "staff_profile_id", None)),
                    "date": str(getattr(row, "work_date", "") or getattr(row, "date", "")),
                    "hours": str(getattr(row, "hours", "") or ""),
                }
            return None
        except Exception as exc:  # pragma: no cover - snapshot must never break submit
            logger.warning("Subject snapshot failed for %s #%s: %s", code, subject_id, exc)
            return None

    def _is_superuser(self, user_id: int) -> bool:
        u = self.db.query(User).filter(User.id == user_id).first()
        return bool(u and getattr(u, "is_superuser", False))

    # ---- submit ------------------------------------------------------

    def submit(self, data, *, requester_user_id: int) -> Optional[ApprovalRequest]:
        """
        Create an approval request for a subject. Best-effort: never raises into
        the caller's main transaction — if no flow is configured yet, the
        request is parked as PENDING for later configuration.
        """
        # Validate the hand-picked first-step approver BEFORE the defensive
        # try-block so a bad selection surfaces as a clean 400 to the caller.
        assigned_id = getattr(data, "assigned_approver_user_id", None)
        if assigned_id:
            info = self.first_step_approvers(data.request_type, flow_id=data.flow_id)
            valid_ids = {a["user_id"] for a in info["approvers"]}
            if assigned_id not in valid_ids:
                raise BadRequestError(
                    message="The selected approver is not eligible for the first approval step.")
            if assigned_id == requester_user_id:
                raise BadRequestError(message="You cannot assign yourself as the approver.")

        try:
            rt = self.types.get_or_create(data.request_type)
            flow = self.db.query(ApprovalFlow).filter(ApprovalFlow.id == data.flow_id).first() if data.flow_id else None
            if flow is None:
                flow = self._default_flow(rt.id)

            requester_staff = data.requester_staff_profile_id
            if requester_staff is None:
                sp = self.db.query(StaffProfile).filter(StaffProfile.user_id == requester_user_id).first()
                requester_staff = sp.id if sp else None

            # Self-describing Request row: when the caller didn't provide a
            # payload, snapshot the originating domain record so approvers can
            # see exactly what they are approving.
            payload = data.payload or self._subject_snapshot(rt.code, data.subject_id)

            req = ApprovalRequest(
                request_type_id=rt.id,
                request_type_code=rt.code,
                flow_id=flow.id if flow else None,
                subject_id=data.subject_id,
                requester_user_id=requester_user_id,
                requester_staff_profile_id=requester_staff,
                department_id=data.department_id,
                facility_id=data.facility_id,
                title=data.title,
                description=data.description,
                payload=payload,
                assigned_approver_user_id=assigned_id,
                status=ApprovalRequestStatus.PENDING,
                submitted_at=datetime.now(timezone.utc),
            )

            if flow is None:
                # No approval flow configured for this request type yet — there
                # is nothing to route to, so skip tracking (best-effort). Admins
                # configure a flow in the UI, after which submissions are routed.
                logger.info("No approval flow configured for request type %s; skipping.", rt.code)
                return None

            steps = self._flow_steps(flow.id)
            if not steps:
                # Flow with no steps → nothing to approve → auto-approve.
                req.status = ApprovalRequestStatus.APPROVED
                req.completed_at = datetime.now(timezone.utc)
                self.db.add(req)
                self.db.flush()
                self._log(req, None, None, ApprovalLogAction.SUBMIT, requester_user_id,
                          comment="Submitted.", resulting_status=req.status.value)
                self._finalize_subject(req, final=ApprovalRequestStatus.APPROVED)
                self.db.commit()
                self.db.refresh(req)
                return req

            req.status = ApprovalRequestStatus.IN_PROGRESS
            req.current_step_order = steps[0].step_order
            self.db.add(req)
            self.db.flush()
            self._log(req, steps[0].step_order, steps[0].name, ApprovalLogAction.SUBMIT,
                      requester_user_id, comment="Submitted for approval.",
                      resulting_status=req.status.value)
            self.db.commit()
            self.db.refresh(req)
            # Best-effort submission emails (approver + requester).
            try:
                from app.services.approval_notifications import send_submission_emails
                send_submission_emails(self.db, req, first_step=steps[0])
            except Exception as exc:  # pragma: no cover - never break submit
                logger.warning("Approval submission emails failed for request %s: %s", req.id, exc)
            return req
        except Exception as exc:  # pragma: no cover - defensive; never break caller
            logger.exception("Approval submit failed for %s: %s", getattr(data, "request_type", "?"), exc)
            self.db.rollback()
            return None

    # ---- decide ------------------------------------------------------

    def decide(self, request_id: int, data, *, actor_user_id: int) -> ApprovalRequest:
        req = self.get(request_id)
        if data.action == ApprovalLogAction.COMMENT:
            self._log(req, req.current_step_order, self._current_step_name(req),
                      ApprovalLogAction.COMMENT, actor_user_id, comment=data.comment,
                      resulting_status=req.status.value)
            self.db.commit()
            self.db.refresh(req)
            return req

        if data.action == ApprovalLogAction.CANCEL:
            return self.cancel(request_id, actor_user_id=actor_user_id, comment=data.comment)

        if req.status != ApprovalRequestStatus.IN_PROGRESS:
            raise BadRequestError(message=f"Request is not awaiting decisions (status {req.status}).")

        step = self._step_at(req.flow_id, req.current_step_order)
        if step is None:
            raise BadRequestError(message="No active step to act on.")

        eligible = self.eligible_user_ids(step, req)
        first = self._flow_steps(req.flow_id)
        if (req.assigned_approver_user_id and first
                and step.step_order == first[0].step_order):
            # The requester hand-picked the first-step approver — only that
            # user (or a superuser) may action step one.
            eligible = {req.assigned_approver_user_id}
        is_super = self._is_superuser(actor_user_id)
        if not is_super and eligible and actor_user_id not in eligible:
            raise ForbiddenError(message="You are not an approver for the current step.")
        if not step.allow_self_approval and actor_user_id == req.requester_user_id and not is_super:
            raise ForbiddenError(message="You cannot approve your own request.")

        if data.action == ApprovalLogAction.RETURN:
            # "Return for correction": terminal for THIS request, but the
            # subject row is reset to DRAFT so the requester can fix and
            # resubmit (a resubmission opens a fresh ApprovalRequest).
            self._log(req, step.step_order, step.name, ApprovalLogAction.RETURN, actor_user_id,
                      comment=data.comment, resulting_status=ApprovalRequestStatus.RETURNED.value)
            req.status = ApprovalRequestStatus.RETURNED
            req.current_step_order = None
            req.completed_at = datetime.now(timezone.utc)
            req.decision_summary = f"Returned for correction at step {step.step_order} ({step.name})."
            self._finalize_subject(req, final=ApprovalRequestStatus.RETURNED)
            self.db.commit()
            self.db.refresh(req)
            return req

        if data.action == ApprovalLogAction.REJECT:
            self._log(req, step.step_order, step.name, ApprovalLogAction.REJECT, actor_user_id,
                      comment=data.comment, resulting_status=ApprovalRequestStatus.REJECTED.value)
            req.status = ApprovalRequestStatus.REJECTED
            req.current_step_order = None
            req.completed_at = datetime.now(timezone.utc)
            req.decision_summary = f"Rejected at step {step.step_order} ({step.name})."
            self._finalize_subject(req, final=ApprovalRequestStatus.REJECTED)
            self.db.commit()
            self.db.refresh(req)
            return req

        # APPROVE
        self._log(req, step.step_order, step.name, ApprovalLogAction.APPROVE, actor_user_id,
                  comment=data.comment, resulting_status=req.status.value)

        if self._step_satisfied(req, step, eligible):
            nxt = self._next_step_order(req.flow_id, step.step_order)
            if nxt is None:
                req.status = ApprovalRequestStatus.APPROVED
                req.current_step_order = None
                req.completed_at = datetime.now(timezone.utc)
                req.decision_summary = "Fully approved."
                self._finalize_subject(req, final=ApprovalRequestStatus.APPROVED)
            else:
                req.current_step_order = nxt
        self.db.commit()
        self.db.refresh(req)
        return req

    def _step_satisfied(self, req: ApprovalRequest, step: ApprovalStep, eligible: set[int]) -> bool:
        approvals = {
            l.actor_user_id
            for l in req.logs
            if l.step_order == step.step_order and l.action == ApprovalLogAction.APPROVE and l.actor_user_id
        }
        n = len(approvals)
        rule = step.decision_rule
        if rule == ApprovalStepDecisionRule.ANY_OF:
            return n >= 1
        if rule == ApprovalStepDecisionRule.ALL_OF:
            need = len(eligible) if eligible else 1
            return n >= need
        if rule == ApprovalStepDecisionRule.N_OF_M:
            return n >= max(1, step.required_approvals or 1)
        return n >= 1

    def cancel(self, request_id: int, *, actor_user_id: int, comment: Optional[str] = None) -> ApprovalRequest:
        req = self.get(request_id)
        if req.status in (ApprovalRequestStatus.APPROVED, ApprovalRequestStatus.REJECTED, ApprovalRequestStatus.CANCELLED):
            raise BadRequestError(message=f"Cannot cancel a request in status {req.status}.")
        req.status = ApprovalRequestStatus.CANCELLED
        req.current_step_order = None
        req.completed_at = datetime.now(timezone.utc)
        self._log(req, None, None, ApprovalLogAction.CANCEL, actor_user_id, comment=comment,
                  resulting_status=req.status.value)
        self._finalize_subject(req, final=ApprovalRequestStatus.CANCELLED)
        self.db.commit()
        self.db.refresh(req)
        return req

    # ---- queries -----------------------------------------------------

    def get(self, request_id: int) -> ApprovalRequest:
        req = (
            self.db.query(ApprovalRequest)
            .filter(ApprovalRequest.id == request_id, ApprovalRequest.is_deleted.is_(False))
            .first()
        )
        if req is None:
            raise NotFoundError(message="Approval request not found.")
        return req

    def list_requests(self, *, request_type: Optional[str] = None, status=None,
                      requester_user_id: Optional[int] = None, skip: int = 0, limit: int = 50):
        q = self.db.query(ApprovalRequest).filter(ApprovalRequest.is_deleted.is_(False))
        if request_type:
            q = q.filter(ApprovalRequest.request_type_code == request_type)
        if status is not None:
            q = q.filter(ApprovalRequest.status == status)
        if requester_user_id is not None:
            q = q.filter(ApprovalRequest.requester_user_id == requester_user_id)
        total = q.count()
        rows = q.order_by(ApprovalRequest.id.desc()).offset(skip).limit(limit).all()
        return rows, total

    def list_my_pending(self, user_id: int) -> list[ApprovalRequest]:
        rows = (
            self.db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.is_deleted.is_(False),
                ApprovalRequest.status == ApprovalRequestStatus.IN_PROGRESS,
            )
            .order_by(ApprovalRequest.id.desc())
            .all()
        )
        out = []
        is_super = self._is_superuser(user_id)
        for req in rows:
            step = self._step_at(req.flow_id, req.current_step_order)
            if step is None:
                continue
            eligible = self.eligible_user_ids(step, req)
            first = self._flow_steps(req.flow_id)
            if (req.assigned_approver_user_id and first
                    and step.step_order == first[0].step_order):
                eligible = {req.assigned_approver_user_id}
            if is_super or user_id in eligible:
                out.append(req)
        return out

    def steps_for(self, req: ApprovalRequest) -> list[ApprovalStep]:
        if not req.flow_id:
            return []
        return self._flow_steps(req.flow_id)

    def _current_step_name(self, req: ApprovalRequest) -> Optional[str]:
        step = self._step_at(req.flow_id, req.current_step_order)
        return step.name if step else None

    # ---- logging + finalize -----------------------------------------

    def _log(self, req, step_order, step_name, action, actor_user_id, *, comment=None, resulting_status=None):
        self.db.add(ApprovalLog(
            request_id=req.id,
            step_order=step_order,
            step_name=step_name,
            action=action,
            actor_user_id=actor_user_id,
            comment=comment,
            resulting_status=resulting_status,
        ))
        self.db.flush()

    def _finalize_subject(self, request: ApprovalRequest, *, final: ApprovalRequestStatus) -> None:
        """Propagate a terminal approval outcome onto the originating domain row."""
        if not request.subject_id:
            return
        approved = final == ApprovalRequestStatus.APPROVED
        returned = final == ApprovalRequestStatus.RETURNED
        now = datetime.now(timezone.utc)
        code = request.request_type_code
        try:
            if code == RequestTypeCode.PAYROLL_RUN:
                from app.models.all_models import PayrollRun
                from app.core.enums import PayrollRunStatus
                run = self.db.query(PayrollRun).filter(PayrollRun.id == request.subject_id).first()
                if run is None:
                    return
                if approved:
                    run.status = PayrollRunStatus.APPROVED
                    run.approved_at = now
                    run.approved_by_user_id = request.requester_user_id
                elif returned:
                    run.status = PayrollRunStatus.DRAFT
                    run.note = (run.note or "") + "\nReturned for correction."
                else:
                    run.status = PayrollRunStatus.CANCELLED
                    run.note = (run.note or "") + f"\nApproval {final.value.lower()}."
                self.db.add(run)
                return

            if code == RequestTypeCode.LEAVE_REQUEST:
                from app.models.all_models import LeaveRequest
                from app.core.enums import LeaveStatus
                row = self.db.query(LeaveRequest).filter(LeaveRequest.id == request.subject_id).first()
                if row:
                    if returned:
                        row.status = LeaveStatus.DRAFT
                    else:
                        row.status = LeaveStatus.APPROVED if approved else LeaveStatus.REJECTED
                        row.decided_at = now
                    self.db.add(row)
                return

            if code == RequestTypeCode.OVERTIME:
                from app.models.all_models import OvertimeRecord
                from app.core.enums import OvertimeStatus
                row = self.db.query(OvertimeRecord).filter(OvertimeRecord.id == request.subject_id).first()
                if row:
                    if returned:
                        row.status = OvertimeStatus.PENDING  # no DRAFT state on overtime
                        row.approved_at = None
                    else:
                        row.status = OvertimeStatus.APPROVED if approved else OvertimeStatus.REJECTED
                        row.approved_at = now if approved else None
                    self.db.add(row)
                return

            if code == RequestTypeCode.TIMESHEET:
                from app.models.all_models import Timesheet
                from app.core.enums import TimesheetStatus
                row = self.db.query(Timesheet).filter(Timesheet.id == request.subject_id).first()
                if row:
                    if returned:
                        row.status = TimesheetStatus.DRAFT
                    else:
                        row.status = TimesheetStatus.APPROVED if approved else TimesheetStatus.REJECTED
                    self.db.add(row)
                return

            if code == RequestTypeCode.SALARY_ADVANCE:
                from app.models.all_models import SalaryAdvance
                from app.core.enums import SalaryAdvanceStatus
                row = self.db.query(SalaryAdvance).filter(SalaryAdvance.id == request.subject_id).first()
                if row:
                    if returned:
                        row.status = SalaryAdvanceStatus.DRAFT
                    else:
                        row.status = SalaryAdvanceStatus.APPROVED if approved else SalaryAdvanceStatus.REJECTED
                        if approved:
                            row.approved_at = now
                    self.db.add(row)
                return

            if code == RequestTypeCode.REIMBURSEMENT:
                from app.models.all_models import ReimbursementRequest
                from app.core.enums import ReimbursementStatus
                row = self.db.query(ReimbursementRequest).filter(ReimbursementRequest.id == request.subject_id).first()
                if row:
                    if returned:
                        row.status = ReimbursementStatus.DRAFT
                        row.decision_note = "Returned for correction."
                    else:
                        row.status = ReimbursementStatus.APPROVED if approved else ReimbursementStatus.REJECTED
                        row.decided_at = now
                    self.db.add(row)
                return
            # PROCUREMENT / STAFF_REQUEST / GENERIC: subject rows (where
            # present) can read the request outcome; no-op here.
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Finalize hook failed for %s #%s: %s", code, request.subject_id, exc)
            return
