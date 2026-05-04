"""
HR / staff-management service bundle.

Consolidates the operational logic for the HR vertical so the route
layer stays thin. Each inner service owns one slice:

* :class:`StaffOnboardingService` — onboarding/offboarding checklists
  and employment-status transitions (with audit).
* :class:`DutyRosterService` — roster + duty-assignment management
  with double-booking prevention.
* :class:`AttendanceService` — clock in / clock out, lateness +
  overtime computation, integration with timesheets.
* :class:`TimesheetService` — generate, submit, approve, lock.
* :class:`LeaveService` — leave-request workflow + balance
  enforcement.
* :class:`PayrollService` — payroll-run calculation, approval, lock.
* :class:`OvertimeService` — overtime claim approval pipeline.
* :class:`StaffLoanService` — loan request → repayment ledger.
* :class:`StaffLicenseService` — credential expiry monitoring.

Notifications go through :class:`NotificationDispatcher` so they
respect tenant-level email/SMS/WhatsApp/push routing automatically.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.enums import (
    AppraisalStatus,
    AttendanceMethod,
    EmploymentStatus,
    LeaveStatus,
    LicenseStatus,
    OvertimeStatus,
    PayrollLineStatus,
    PayrollRunStatus,
    StaffLoanStatus,
    StaffShiftType,
    TimesheetStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    AttendanceRecord,
    DutyAssignment,
    DutyRoster,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    OvertimeRecord,
    PayrollLine,
    PayrollRun,
    PublicHoliday,
    ShiftTemplate,
    StaffAuditLog,
    StaffLicense,
    StaffLoan,
    StaffLoanRepayment,
    StaffOffboardingChecklistItem,
    StaffOnboardingChecklistItem,
    StaffProfile,
    StaffSalary,
    StaffStatusHistory,
    Timesheet,
    TimesheetEntry,
)


logger = logging.getLogger(__name__)


def _q(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places))


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------


def _audit(
    db: Session,
    *,
    actor_user_id: Optional[int],
    entity: str,
    entity_id: Optional[int],
    action: str,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    db.add(
        StaffAuditLog(
            actor_user_id=actor_user_id,
            entity=entity,
            entity_id=entity_id,
            action=action,
            before_data=before,
            after_data=after,
            ip_address=ip_address,
        )
    )


def _serialise(rec: Any) -> dict:
    out: dict[str, Any] = {}
    for col in rec.__table__.columns:
        v = getattr(rec, col.name, None)
        if isinstance(v, (date, datetime)):
            v = v.isoformat()
        elif isinstance(v, Decimal):
            v = str(v)
        out[col.name] = v
    return out


# ---------------------------------------------------------------------------
# Onboarding / offboarding / status transitions
# ---------------------------------------------------------------------------


DEFAULT_ONBOARDING_ITEMS: list[str] = [
    "Personal details captured",
    "ID and KYC documents uploaded",
    "Contract signed",
    "Department and supervisor assigned",
    "System user account created",
    "Default role / permissions assigned",
    "Email + password handed over",
    "Workstation / tools assigned",
    "Statutory information captured (tax ID, pension PIN, NHF)",
    "Bank account details captured",
    "Orientation completed",
]


DEFAULT_OFFBOARDING_ITEMS: list[str] = [
    "Resignation / termination letter received",
    "Pending duties reassigned",
    "Patients reassigned",
    "Approvals reassigned",
    "Schedule reassigned",
    "Tasks reassigned",
    "Asset return verified",
    "System access revoked",
    "Final payroll processed",
    "Exit interview completed",
    "Clearance signed",
]


class StaffOnboardingService:
    def __init__(self, db: Session, *, actor_user_id: Optional[int] = None) -> None:
        self.db = db
        self.actor_user_id = actor_user_id

    def seed_onboarding_checklist(self, staff_profile_id: int) -> list[StaffOnboardingChecklistItem]:
        out: list[StaffOnboardingChecklistItem] = []
        for idx, title in enumerate(DEFAULT_ONBOARDING_ITEMS):
            existing = (
                self.db.query(StaffOnboardingChecklistItem)
                .filter(
                    StaffOnboardingChecklistItem.staff_profile_id == staff_profile_id,
                    StaffOnboardingChecklistItem.title == title,
                )
                .first()
            )
            if existing is not None:
                out.append(existing)
                continue
            item = StaffOnboardingChecklistItem(
                staff_profile_id=staff_profile_id,
                title=title,
                sort_order=10 * (idx + 1),
                is_required=True,
            )
            self.db.add(item)
            out.append(item)
        self.db.commit()
        return out

    def complete_onboarding_item(self, item_id: int) -> StaffOnboardingChecklistItem:
        item = self.db.query(StaffOnboardingChecklistItem).filter(StaffOnboardingChecklistItem.id == item_id).first()
        if item is None:
            raise NotFoundError(message="Onboarding item not found.")
        item.is_completed = True
        item.completed_at = datetime.now(timezone.utc)
        item.completed_by_user_id = self.actor_user_id

        # If every required item is done, flag the profile.
        outstanding = (
            self.db.query(StaffOnboardingChecklistItem)
            .filter(
                StaffOnboardingChecklistItem.staff_profile_id == item.staff_profile_id,
                StaffOnboardingChecklistItem.is_required.is_(True),
                StaffOnboardingChecklistItem.is_completed.is_(False),
                StaffOnboardingChecklistItem.is_deleted.is_(False),
            )
            .count()
        )
        if outstanding == 0:
            sp = self.db.query(StaffProfile).filter(StaffProfile.id == item.staff_profile_id).first()
            if sp is not None:
                sp.onboarding_completed = True
                sp.onboarded_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(item)
        return item

    def seed_offboarding_checklist(self, staff_profile_id: int) -> list[StaffOffboardingChecklistItem]:
        out: list[StaffOffboardingChecklistItem] = []
        for idx, title in enumerate(DEFAULT_OFFBOARDING_ITEMS):
            existing = (
                self.db.query(StaffOffboardingChecklistItem)
                .filter(
                    StaffOffboardingChecklistItem.staff_profile_id == staff_profile_id,
                    StaffOffboardingChecklistItem.title == title,
                )
                .first()
            )
            if existing is not None:
                out.append(existing)
                continue
            item = StaffOffboardingChecklistItem(
                staff_profile_id=staff_profile_id,
                title=title,
                sort_order=10 * (idx + 1),
                is_required=True,
            )
            self.db.add(item)
            out.append(item)
        self.db.commit()
        return out

    def complete_offboarding_item(self, item_id: int) -> StaffOffboardingChecklistItem:
        item = self.db.query(StaffOffboardingChecklistItem).filter(StaffOffboardingChecklistItem.id == item_id).first()
        if item is None:
            raise NotFoundError(message="Offboarding item not found.")
        item.is_completed = True
        item.completed_at = datetime.now(timezone.utc)
        item.completed_by_user_id = self.actor_user_id
        self.db.commit()
        self.db.refresh(item)
        return item

    def transition_status(
        self,
        staff_profile_id: int,
        *,
        to_status: EmploymentStatus,
        reason: Optional[str] = None,
        exit_date: Optional[date] = None,
    ) -> StaffProfile:
        sp = self.db.query(StaffProfile).filter(StaffProfile.id == staff_profile_id).first()
        if sp is None:
            raise NotFoundError(message="Staff profile not found.")
        before = sp.employment_status
        sp.employment_status = to_status
        if to_status in {
            EmploymentStatus.RESIGNED,
            EmploymentStatus.TERMINATED,
            EmploymentStatus.RETIRED,
            EmploymentStatus.TRANSFERRED,
        }:
            sp.exit_date = exit_date or date.today()
            sp.exit_reason = reason
            # Deactivate the linked user.
            if sp.user is not None:
                sp.user.is_active = False
        self.db.add(
            StaffStatusHistory(
                staff_profile_id=staff_profile_id,
                from_status=before,
                to_status=to_status,
                actor_user_id=self.actor_user_id,
                reason=reason,
            )
        )
        _audit(
            self.db,
            actor_user_id=self.actor_user_id,
            entity="staff_profile",
            entity_id=sp.id,
            action="STATUS_CHANGE",
            before={"employment_status": str(before)},
            after={"employment_status": str(to_status)},
        )
        self.db.commit()
        self.db.refresh(sp)
        return sp


# ---------------------------------------------------------------------------
# Duty roster
# ---------------------------------------------------------------------------


class DutyRosterService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_roster(self, **fields) -> DutyRoster:
        rec = DutyRoster(**fields)
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def add_assignment(
        self,
        *,
        roster_id: int,
        staff_profile_id: int,
        starts_at: datetime,
        ends_at: datetime,
        shift_type: StaffShiftType = StaffShiftType.MORNING,
        shift_template_id: Optional[int] = None,
        is_on_call: bool = False,
        notes: Optional[str] = None,
    ) -> DutyAssignment:
        if ends_at <= starts_at:
            raise BadRequestError(message="ends_at must be after starts_at.")
        # Conflict detection — refuse if the same staff has an overlapping
        # active assignment.
        clash = (
            self.db.query(DutyAssignment)
            .filter(
                DutyAssignment.staff_profile_id == staff_profile_id,
                DutyAssignment.is_deleted.is_(False),
                DutyAssignment.starts_at < ends_at,
                DutyAssignment.ends_at > starts_at,
            )
            .first()
        )
        if clash is not None:
            raise BadRequestError(
                message="Staff is already scheduled in an overlapping window.",
                detail={"conflicting_assignment_id": clash.id},
            )

        rec = DutyAssignment(
            roster_id=roster_id,
            staff_profile_id=staff_profile_id,
            shift_template_id=shift_template_id,
            shift_type=shift_type,
            starts_at=starts_at,
            ends_at=ends_at,
            is_on_call=is_on_call,
            notes=notes,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def swap_assignment(
        self,
        assignment_id: int,
        *,
        new_staff_profile_id: int,
        approved_by_user_id: int,
    ) -> DutyAssignment:
        rec = self.db.query(DutyAssignment).filter(DutyAssignment.id == assignment_id).first()
        if rec is None:
            raise NotFoundError(message="Assignment not found.")
        rec.swapped_with_staff_id = rec.staff_profile_id
        rec.staff_profile_id = new_staff_profile_id
        rec.swap_approved_by_user_id = approved_by_user_id
        self.db.commit()
        self.db.refresh(rec)
        return rec


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------


class AttendanceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def clock_in(
        self,
        *,
        staff_profile_id: int,
        method: AttendanceMethod = AttendanceMethod.MANUAL,
        device_identifier: Optional[str] = None,
        location: Optional[str] = None,
        when: Optional[datetime] = None,
    ) -> AttendanceRecord:
        ts = when or datetime.now(timezone.utc)
        # Look for a duty assignment covering this time.
        duty = (
            self.db.query(DutyAssignment)
            .filter(
                DutyAssignment.staff_profile_id == staff_profile_id,
                DutyAssignment.starts_at <= ts,
                DutyAssignment.ends_at >= ts,
                DutyAssignment.is_deleted.is_(False),
            )
            .order_by(DutyAssignment.starts_at.desc())
            .first()
        )

        late_minutes = 0
        if duty is not None and ts > duty.starts_at:
            late_minutes = int((ts - duty.starts_at).total_seconds() // 60)

        rec = AttendanceRecord(
            staff_profile_id=staff_profile_id,
            duty_assignment_id=duty.id if duty else None,
            work_date=ts.date(),
            clock_in_at=ts,
            method=method,
            device_identifier=device_identifier,
            location=location,
            is_late=late_minutes > 0,
            minutes_late=late_minutes,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def clock_out(
        self,
        *,
        attendance_record_id: int,
        when: Optional[datetime] = None,
    ) -> AttendanceRecord:
        rec = self.db.query(AttendanceRecord).filter(AttendanceRecord.id == attendance_record_id).first()
        if rec is None:
            raise NotFoundError(message="Attendance record not found.")
        ts = when or datetime.now(timezone.utc)
        rec.clock_out_at = ts

        # Compute overtime minutes if a duty assignment is attached.
        duty = (
            self.db.query(DutyAssignment).filter(DutyAssignment.id == rec.duty_assignment_id).first()
            if rec.duty_assignment_id
            else None
        )
        if duty is not None and ts > duty.ends_at:
            rec.minutes_overtime = int((ts - duty.ends_at).total_seconds() // 60)

        self.db.commit()
        self.db.refresh(rec)
        return rec


# ---------------------------------------------------------------------------
# Timesheet
# ---------------------------------------------------------------------------


class TimesheetService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate(
        self,
        *,
        staff_profile_id: int,
        period_start: date,
        period_end: date,
    ) -> Timesheet:
        # Idempotency: re-running on the same period returns the existing row.
        existing = (
            self.db.query(Timesheet)
            .filter(
                Timesheet.staff_profile_id == staff_profile_id,
                Timesheet.period_start == period_start,
                Timesheet.period_end == period_end,
                Timesheet.is_deleted.is_(False),
            )
            .first()
        )
        if existing is not None:
            return existing

        ts = Timesheet(
            staff_profile_id=staff_profile_id,
            period_start=period_start,
            period_end=period_end,
            status=TimesheetStatus.DRAFT,
        )
        self.db.add(ts)
        self.db.flush()

        # Walk attendance records day-by-day and roll up hours.
        attendances = (
            self.db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.staff_profile_id == staff_profile_id,
                AttendanceRecord.work_date >= period_start,
                AttendanceRecord.work_date <= period_end,
                AttendanceRecord.is_deleted.is_(False),
            )
            .all()
        )

        holidays = {
            h.holiday_date
            for h in self.db.query(PublicHoliday)
            .filter(
                PublicHoliday.holiday_date >= period_start,
                PublicHoliday.holiday_date <= period_end,
                PublicHoliday.is_deleted.is_(False),
                PublicHoliday.is_active.is_(True),
            )
            .all()
        }

        per_day: dict[date, dict[str, Decimal]] = {}
        for a in attendances:
            if not a.clock_in_at or not a.clock_out_at:
                continue
            worked_minutes = int((a.clock_out_at - a.clock_in_at).total_seconds() // 60)
            regular_minutes = max(0, worked_minutes - int(a.minutes_overtime or 0))
            day = per_day.setdefault(
                a.work_date,
                {
                    "regular": Decimal("0"),
                    "overtime": Decimal("0"),
                    "night": Decimal("0"),
                    "weekend": Decimal("0"),
                    "holiday": Decimal("0"),
                },
            )
            day["regular"] += _q(Decimal(regular_minutes) / Decimal(60))
            day["overtime"] += _q(Decimal(int(a.minutes_overtime or 0)) / Decimal(60))
            # Heuristic: weekday >= 5 = weekend, between 22:00-06:00 = night.
            if a.work_date.weekday() >= 5:
                day["weekend"] += _q(Decimal(worked_minutes) / Decimal(60))
            if a.work_date in holidays:
                day["holiday"] += _q(Decimal(worked_minutes) / Decimal(60))
            if a.clock_in_at.hour >= 22 or a.clock_out_at.hour <= 6:
                day["night"] += _q(Decimal(worked_minutes) / Decimal(60))

        for d, sums in per_day.items():
            self.db.add(
                TimesheetEntry(
                    timesheet_id=ts.id,
                    work_date=d,
                    regular_hours=sums["regular"],
                    overtime_hours=sums["overtime"],
                    night_hours=sums["night"],
                    weekend_hours=sums["weekend"],
                    holiday_hours=sums["holiday"],
                )
            )
            ts.total_regular_hours = (ts.total_regular_hours or Decimal("0")) + sums["regular"]
            ts.total_overtime_hours = (ts.total_overtime_hours or Decimal("0")) + sums["overtime"]
            ts.total_night_hours = (ts.total_night_hours or Decimal("0")) + sums["night"]
            ts.total_weekend_hours = (ts.total_weekend_hours or Decimal("0")) + sums["weekend"]
            ts.total_holiday_hours = (ts.total_holiday_hours or Decimal("0")) + sums["holiday"]

        self.db.commit()
        self.db.refresh(ts)
        return ts

    def submit(self, timesheet_id: int) -> Timesheet:
        ts = self.db.query(Timesheet).filter(Timesheet.id == timesheet_id).first()
        if ts is None:
            raise NotFoundError(message="Timesheet not found.")
        if ts.status not in {TimesheetStatus.DRAFT, TimesheetStatus.REJECTED}:
            raise BadRequestError(message=f"Cannot submit a timesheet in status {ts.status}.")
        ts.status = TimesheetStatus.SUBMITTED
        ts.submitted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(ts)
        return ts

    def approve(self, timesheet_id: int, *, approved_by_user_id: int) -> Timesheet:
        ts = self.db.query(Timesheet).filter(Timesheet.id == timesheet_id).first()
        if ts is None:
            raise NotFoundError(message="Timesheet not found.")
        if ts.status != TimesheetStatus.SUBMITTED:
            raise BadRequestError(message=f"Cannot approve a timesheet in status {ts.status}.")
        ts.status = TimesheetStatus.APPROVED
        ts.approved_at = datetime.now(timezone.utc)
        ts.approved_by_user_id = approved_by_user_id
        self.db.commit()
        self.db.refresh(ts)
        return ts

    def lock(self, timesheet_id: int) -> Timesheet:
        ts = self.db.query(Timesheet).filter(Timesheet.id == timesheet_id).first()
        if ts is None:
            raise NotFoundError(message="Timesheet not found.")
        ts.status = TimesheetStatus.LOCKED
        ts.locked_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(ts)
        return ts


# ---------------------------------------------------------------------------
# Leave
# ---------------------------------------------------------------------------


class LeaveService:
    def __init__(self, db: Session, *, actor_user_id: Optional[int] = None) -> None:
        self.db = db
        self.actor_user_id = actor_user_id

    def request_leave(
        self,
        *,
        staff_profile_id: int,
        leave_type_id: int,
        start_date: date,
        end_date: date,
        reason: Optional[str] = None,
        cover_staff_id: Optional[int] = None,
        handover_notes: Optional[str] = None,
    ) -> LeaveRequest:
        if end_date < start_date:
            raise BadRequestError(message="end_date must be on or after start_date.")
        days = Decimal((end_date - start_date).days + 1)

        # Refuse if it overlaps an existing approved leave.
        clash = (
            self.db.query(LeaveRequest)
            .filter(
                LeaveRequest.staff_profile_id == staff_profile_id,
                LeaveRequest.status.in_([LeaveStatus.APPROVED, LeaveStatus.PENDING]),
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= start_date,
                LeaveRequest.is_deleted.is_(False),
            )
            .first()
        )
        if clash is not None:
            raise BadRequestError(
                message="Leave window overlaps an existing request.",
                detail={"conflicting_request_id": clash.id},
            )

        rec = LeaveRequest(
            staff_profile_id=staff_profile_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            days_requested=days,
            reason=reason,
            cover_staff_id=cover_staff_id,
            handover_notes=handover_notes,
            status=LeaveStatus.PENDING,
            submitted_at=datetime.now(timezone.utc),
        )
        self.db.add(rec)
        self.db.flush()

        bal = self._get_or_create_balance(staff_profile_id, leave_type_id, start_date.year)
        bal.pending_days = (bal.pending_days or Decimal("0")) + days

        self.db.commit()
        self.db.refresh(rec)
        return rec

    def decide(
        self,
        request_id: int,
        *,
        approve: bool,
        decided_by_user_id: int,
        note: Optional[str] = None,
    ) -> LeaveRequest:
        rec = self.db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if rec is None:
            raise NotFoundError(message="Leave request not found.")
        if rec.status != LeaveStatus.PENDING:
            raise BadRequestError(message=f"Cannot decide a request in status {rec.status}.")
        rec.status = LeaveStatus.APPROVED if approve else LeaveStatus.REJECTED
        rec.decided_at = datetime.now(timezone.utc)
        rec.decided_by_user_id = decided_by_user_id
        rec.decision_note = note

        bal = self._get_or_create_balance(rec.staff_profile_id, rec.leave_type_id, rec.start_date.year)
        bal.pending_days = max(Decimal("0"), (bal.pending_days or Decimal("0")) - (rec.days_requested or Decimal("0")))
        if approve:
            bal.taken_days = (bal.taken_days or Decimal("0")) + (rec.days_requested or Decimal("0"))

        self.db.commit()
        self.db.refresh(rec)
        return rec

    def _get_or_create_balance(self, staff_profile_id: int, leave_type_id: int, year: int) -> LeaveBalance:
        rec = (
            self.db.query(LeaveBalance)
            .filter(
                LeaveBalance.staff_profile_id == staff_profile_id,
                LeaveBalance.leave_type_id == leave_type_id,
                LeaveBalance.year == year,
            )
            .first()
        )
        if rec is None:
            lt = self.db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()
            entitled = lt.default_annual_days if lt and lt.default_annual_days is not None else Decimal("0")
            rec = LeaveBalance(
                staff_profile_id=staff_profile_id,
                leave_type_id=leave_type_id,
                year=year,
                entitled_days=entitled,
            )
            self.db.add(rec)
            self.db.flush()
        return rec


# ---------------------------------------------------------------------------
# Payroll
# ---------------------------------------------------------------------------


class PayrollService:
    def __init__(self, db: Session, *, actor_user_id: Optional[int] = None) -> None:
        self.db = db
        self.actor_user_id = actor_user_id

    def create_run(
        self,
        *,
        code: str,
        period_start: date,
        period_end: date,
        facility_id: Optional[int] = None,
        department_id: Optional[int] = None,
    ) -> PayrollRun:
        run = PayrollRun(
            code=code,
            period_start=period_start,
            period_end=period_end,
            facility_id=facility_id,
            department_id=department_id,
            status=PayrollRunStatus.DRAFT,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def calculate(self, run_id: int) -> PayrollRun:
        run = self.db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
        if run is None:
            raise NotFoundError(message="Payroll run not found.")
        if run.status != PayrollRunStatus.DRAFT:
            raise BadRequestError(message=f"Cannot recalculate a run in status {run.status}.")

        # Resolve eligible staff.
        q = self.db.query(StaffProfile).filter(
            StaffProfile.is_deleted.is_(False),
            StaffProfile.employment_status.in_(
                [EmploymentStatus.ACTIVE, EmploymentStatus.ON_LEAVE, EmploymentStatus.PROBATION]
            ),
        )
        if run.facility_id is not None:
            q = q.filter(StaffProfile.facility_id == run.facility_id)
        if run.department_id is not None:
            q = q.filter(StaffProfile.department_id == run.department_id)
        staff = q.all()

        total_gross = Decimal("0")
        total_ded = Decimal("0")
        total_net = Decimal("0")

        for s in staff:
            existing = (
                self.db.query(PayrollLine)
                .filter(
                    PayrollLine.payroll_run_id == run.id,
                    PayrollLine.staff_profile_id == s.id,
                )
                .first()
            )
            if existing is not None:
                continue

            base = Decimal(s.base_salary_amount or 0)
            timesheet = (
                self.db.query(Timesheet)
                .filter(
                    Timesheet.staff_profile_id == s.id,
                    Timesheet.period_start == run.period_start,
                    Timesheet.period_end == run.period_end,
                    Timesheet.is_deleted.is_(False),
                )
                .first()
            )
            overtime_amount = Decimal("0")
            if timesheet is not None and timesheet.total_overtime_hours:
                # Naive hourly OT pay: base / 173 * 1.5 * hours.
                hourly = base / Decimal("173") if base > 0 else Decimal("0")
                overtime_amount = (hourly * Decimal("1.5") * Decimal(timesheet.total_overtime_hours)).quantize(Decimal("0.01"))

            # Overtime claims explicitly approved.
            for ot in (
                self.db.query(OvertimeRecord)
                .filter(
                    OvertimeRecord.staff_profile_id == s.id,
                    OvertimeRecord.work_date >= run.period_start,
                    OvertimeRecord.work_date <= run.period_end,
                    OvertimeRecord.status == OvertimeStatus.APPROVED,
                    OvertimeRecord.paid_in_payroll_line_id.is_(None),
                )
                .all()
            ):
                hourly = base / Decimal("173") if base > 0 else Decimal("0")
                overtime_amount += (hourly * Decimal(ot.multiplier or 1) * Decimal(ot.hours or 0)).quantize(Decimal("0.01"))

            allowances_total = Decimal("0")
            deductions_total = Decimal("0")
            salary = (
                self.db.query(StaffSalary)
                .filter(
                    StaffSalary.staff_profile_id == s.id,
                    StaffSalary.is_active.is_(True),
                    StaffSalary.is_deleted.is_(False),
                )
                .first()
            )
            if salary is not None:
                for a in (salary.allowances or []):
                    allowances_total += Decimal(str(a.get("amount", 0)))
                for d in (salary.deductions or []):
                    deductions_total += Decimal(str(d.get("amount", 0)))

            # Loan repayments due this run.
            loan_repayment_total = Decimal("0")
            for loan in (
                self.db.query(StaffLoan)
                .filter(
                    StaffLoan.staff_profile_id == s.id,
                    StaffLoan.status == StaffLoanStatus.ACTIVE,
                )
                .all()
            ):
                loan_repayment_total += Decimal(loan.monthly_repayment_amount or 0)

            gross = base + allowances_total + overtime_amount
            paye = (gross * Decimal("0.075")).quantize(Decimal("0.01"))  # placeholder; real PAYE is banded
            pension = (gross * Decimal("0.08")).quantize(Decimal("0.01"))
            nhf = (gross * Decimal("0.025")).quantize(Decimal("0.01"))
            total_deductions = paye + pension + nhf + loan_repayment_total + deductions_total
            net = gross - total_deductions

            line = PayrollLine(
                payroll_run_id=run.id,
                staff_profile_id=s.id,
                timesheet_id=timesheet.id if timesheet else None,
                base_salary=base,
                total_allowances=allowances_total,
                overtime_amount=overtime_amount,
                bonus_amount=Decimal("0"),
                gross_pay=gross,
                paye_amount=paye,
                pension_amount=pension,
                nhf_amount=nhf,
                health_insurance_amount=Decimal("0"),
                loan_repayment_amount=loan_repayment_total,
                other_deductions=deductions_total,
                total_deductions=total_deductions,
                net_pay=net,
                breakdown_json={
                    "allowances": (salary.allowances if salary else []),
                    "deductions": (salary.deductions if salary else []),
                },
                status=PayrollLineStatus.PENDING,
            )
            self.db.add(line)

            total_gross += gross
            total_ded += total_deductions
            total_net += net

        run.total_gross = total_gross
        run.total_deductions = total_ded
        run.total_net = total_net
        run.status = PayrollRunStatus.CALCULATED
        run.calculated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(run)
        return run

    def approve(self, run_id: int, *, approved_by_user_id: int) -> PayrollRun:
        run = self.db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
        if run is None:
            raise NotFoundError(message="Payroll run not found.")
        if run.status != PayrollRunStatus.CALCULATED:
            raise BadRequestError(message=f"Cannot approve a run in status {run.status}.")
        run.status = PayrollRunStatus.APPROVED
        run.approved_at = datetime.now(timezone.utc)
        run.approved_by_user_id = approved_by_user_id
        for line in self.db.query(PayrollLine).filter(PayrollLine.payroll_run_id == run.id).all():
            line.status = PayrollLineStatus.APPROVED
        self.db.commit()
        self.db.refresh(run)
        return run

    def lock(self, run_id: int) -> PayrollRun:
        run = self.db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
        if run is None:
            raise NotFoundError(message="Payroll run not found.")
        run.status = PayrollRunStatus.LOCKED
        run.locked_at = datetime.now(timezone.utc)
        # Lock all timesheets used.
        ts_ids = {
            tid for (tid,) in self.db.query(PayrollLine.timesheet_id).filter(
                PayrollLine.payroll_run_id == run.id, PayrollLine.timesheet_id.isnot(None)
            ).all()
        }
        if ts_ids:
            for ts in self.db.query(Timesheet).filter(Timesheet.id.in_(ts_ids)).all():
                ts.status = TimesheetStatus.LOCKED
                ts.locked_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(run)
        return run


# ---------------------------------------------------------------------------
# Overtime
# ---------------------------------------------------------------------------


class OvertimeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def submit(
        self,
        *,
        staff_profile_id: int,
        work_date: date,
        hours: Decimal,
        multiplier: Decimal = Decimal("1.5"),
        reason: Optional[str] = None,
    ) -> OvertimeRecord:
        rec = OvertimeRecord(
            staff_profile_id=staff_profile_id,
            work_date=work_date,
            hours=hours,
            multiplier=multiplier,
            reason=reason,
            status=OvertimeStatus.PENDING,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def decide(
        self,
        rec_id: int,
        *,
        approve: bool,
        approved_by_user_id: int,
    ) -> OvertimeRecord:
        rec = self.db.query(OvertimeRecord).filter(OvertimeRecord.id == rec_id).first()
        if rec is None:
            raise NotFoundError(message="Overtime record not found.")
        if rec.status != OvertimeStatus.PENDING:
            raise BadRequestError(message=f"Cannot decide an OT record in status {rec.status}.")
        rec.status = OvertimeStatus.APPROVED if approve else OvertimeStatus.REJECTED
        rec.approved_by_user_id = approved_by_user_id
        rec.approved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(rec)
        return rec


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------


class StaffLoanService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        staff_profile_id: int,
        principal_amount: Decimal,
        repayment_count: int,
        interest_percent: Decimal = Decimal("0"),
        currency: str = "NGN",
        starts_on: Optional[date] = None,
        note: Optional[str] = None,
    ) -> StaffLoan:
        if repayment_count <= 0:
            raise BadRequestError(message="repayment_count must be > 0.")
        monthly = (Decimal(principal_amount) / Decimal(repayment_count)).quantize(Decimal("0.01"))
        rec = StaffLoan(
            staff_profile_id=staff_profile_id,
            principal_amount=principal_amount,
            interest_percent=interest_percent,
            currency=currency,
            repayment_count=repayment_count,
            monthly_repayment_amount=monthly,
            outstanding_balance=principal_amount,
            starts_on=starts_on,
            note=note,
            status=StaffLoanStatus.REQUESTED,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def approve(self, loan_id: int, *, approved_by_user_id: int) -> StaffLoan:
        loan = self.db.query(StaffLoan).filter(StaffLoan.id == loan_id).first()
        if loan is None:
            raise NotFoundError(message="Loan not found.")
        if loan.status != StaffLoanStatus.REQUESTED:
            raise BadRequestError(message=f"Cannot approve a loan in status {loan.status}.")
        loan.status = StaffLoanStatus.ACTIVE
        loan.approved_on = date.today()
        loan.approved_by_user_id = approved_by_user_id
        if loan.starts_on is None:
            loan.starts_on = date.today()
        self.db.commit()
        self.db.refresh(loan)
        return loan

    def repay(
        self,
        *,
        loan_id: int,
        amount: Decimal,
        payroll_line_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> StaffLoanRepayment:
        loan = self.db.query(StaffLoan).filter(StaffLoan.id == loan_id).first()
        if loan is None:
            raise NotFoundError(message="Loan not found.")
        if loan.status != StaffLoanStatus.ACTIVE:
            raise BadRequestError(message=f"Cannot post a repayment to a loan in status {loan.status}.")
        loan.outstanding_balance = max(Decimal("0"), Decimal(loan.outstanding_balance or 0) - Decimal(amount))
        rep = StaffLoanRepayment(
            loan_id=loan.id,
            payroll_line_id=payroll_line_id,
            amount=amount,
            balance_after=loan.outstanding_balance,
            note=note,
        )
        self.db.add(rep)
        if loan.outstanding_balance <= Decimal("0"):
            loan.status = StaffLoanStatus.COMPLETED
        self.db.commit()
        self.db.refresh(rep)
        return rep


# ---------------------------------------------------------------------------
# Licences
# ---------------------------------------------------------------------------


class StaffLicenseService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self,
        *,
        staff_profile_id: int,
        license_type: str,
        license_number: str,
        issuing_body: Optional[str] = None,
        issue_date: Optional[date] = None,
        expiry_date: Optional[date] = None,
        document_id: Optional[int] = None,
    ) -> StaffLicense:
        rec = StaffLicense(
            staff_profile_id=staff_profile_id,
            license_type=license_type,
            license_number=license_number,
            issuing_body=issuing_body,
            issue_date=issue_date,
            expiry_date=expiry_date,
            status=LicenseStatus.ACTIVE,
            document_id=document_id,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def sweep_expiries(self) -> dict:
        today = date.today()
        soon = today + timedelta(days=30)
        expired = (
            self.db.query(StaffLicense)
            .filter(
                StaffLicense.status == LicenseStatus.ACTIVE,
                StaffLicense.expiry_date.isnot(None),
                StaffLicense.expiry_date < today,
            )
            .all()
        )
        for r in expired:
            r.status = LicenseStatus.EXPIRED

        # Flag licenses expiring within 30 days as PENDING_RENEWAL.
        warning = (
            self.db.query(StaffLicense)
            .filter(
                StaffLicense.status == LicenseStatus.ACTIVE,
                StaffLicense.expiry_date.isnot(None),
                StaffLicense.expiry_date >= today,
                StaffLicense.expiry_date <= soon,
            )
            .all()
        )
        for r in warning:
            r.status = LicenseStatus.PENDING_RENEWAL
        if expired or warning:
            self.db.commit()
        return {
            "expired": len(expired),
            "pending_renewal": len(warning),
        }
