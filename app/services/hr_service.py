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
    SalaryAdvanceStatus,
    AppraisalStatus,
    AttendanceMethod,
    EmploymentStatus,
    LeaveStatus,
    LicenseStatus,
    OvertimeStatus,
    PayrollCalcMethod,
    PayrollComponentType,
    PayrollLineStatus,
    PayrollRunStatus,
    StaffLoanStatus,
    StaffShiftType,
    TimesheetStatus,
)
from app.core.exceptions import AlreadyExistsError, BadRequestError, NotFoundError
from sqlalchemy.exc import IntegrityError
from app.models.all_models import (
    Account,
    AttendanceRecord,
    DutyAssignment,
    DutyRoster,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    OvertimeRecord,
    PayrollComponent,
    PayrollComponentTemplate,
    PayrollComponentTemplateItem,
    PayrollLine,
    PayrollLineComponent,
    PayrollRun,
    PublicHoliday,
    ShiftTemplate,
    StaffAuditLog,
    StaffLicense,
    PayrollOneOff,
    SalaryAdvance,
    StaffLoan,
    StaffLoanRepayment,
    StaffOffboardingChecklistItem,
    StaffOnboardingChecklistItem,
    SalaryGrade,
    SalaryStep,
    StaffProfile,
    StaffSalary,
    StaffStatusHistory,
    Timesheet,
    TimesheetEntry,
    User,
)


logger = logging.getLogger(__name__)


def _q(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places))


# ---------------------------------------------------------------------------
# Nigerian PAYE — Nigeria Tax Act 2025 (effective 1 January 2026).
#
# The Act replaces the PITA regime: the Consolidated Relief Allowance (CRA)
# is abolished, the first ₦800,000 of annual taxable income is tax-free, and
# a rent relief (20% of annual rent, capped at ₦500,000) plus statutory
# contributions (pension, NHF, NHIS, life-insurance premiums) are deductible
# before applying the progressive bands below.
PAYE_RENT_RELIEF_RATE = Decimal("0.20")
PAYE_RENT_RELIEF_CAP = Decimal("500000")

#: Progressive annual bands as ``(band_width, rate)`` tuples. ``None`` width
#: marks the final open-ended band. Overridable per-tenant via the
#: StatutoryDeductionConfig row with code ``PAYE`` (bands_json =
#: ``[[width_or_null, rate_percent], ...]``).
PAYE_ANNUAL_BANDS: tuple[tuple[Optional[Decimal], Decimal], ...] = (
    (Decimal("800000"), Decimal("0.00")),    # first ₦800,000 — tax-free
    (Decimal("2200000"), Decimal("0.15")),   # ₦800,001 – ₦3,000,000
    (Decimal("9000000"), Decimal("0.18")),   # ₦3,000,001 – ₦12,000,000
    (Decimal("13000000"), Decimal("0.21")),  # ₦12,000,001 – ₦25,000,000
    (Decimal("25000000"), Decimal("0.23")),  # ₦25,000,001 – ₦50,000,000
    (None, Decimal("0.24")),                 # above ₦50,000,000 (25% — see note)
)
# NOTE: final marginal rate under the Act is 25%.
PAYE_ANNUAL_BANDS = PAYE_ANNUAL_BANDS[:-1] + ((None, Decimal("0.25")),)


def _compute_monthly_paye(
    gross_monthly: Decimal,
    monthly_pension: Decimal = Decimal("0"),
    monthly_nhf: Decimal = Decimal("0"),
    monthly_other_reliefs: Decimal = Decimal("0"),
    annual_rent: Decimal = Decimal("0"),
    bands: Optional[tuple] = None,
) -> Decimal:
    """
    Monthly PAYE under the Nigeria Tax Act 2025.

    1. Annualise gross taxable pay and relief contributions (×12).
    2. Deduct statutory reliefs: pension, NHF, other eligible premiums.
    3. Deduct rent relief = min(20% of annual rent, ₦500,000).
    4. Apply the progressive bands (first ₦800k at 0%).
    5. Monthly PAYE = annual tax / 12.
    """
    gross_annual = max(Decimal("0"), gross_monthly) * Decimal("12")
    reliefs = (max(Decimal("0"), monthly_pension)
               + max(Decimal("0"), monthly_nhf)
               + max(Decimal("0"), monthly_other_reliefs)) * Decimal("12")
    rent_relief = min(PAYE_RENT_RELIEF_CAP,
                      max(Decimal("0"), annual_rent) * PAYE_RENT_RELIEF_RATE)
    taxable = gross_annual - reliefs - rent_relief
    if taxable <= 0:
        return Decimal("0.00")
    tax = Decimal("0")
    remaining = taxable
    for band_width, rate in (bands or PAYE_ANNUAL_BANDS):
        if remaining <= 0:
            break
        chunk = remaining if band_width is None else min(remaining, band_width)
        tax += chunk * rate
        remaining -= chunk
    return (tax / Decimal("12")).quantize(Decimal("0.01"))


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

    def _validate_account(self, account_id: Optional[int]) -> None:
        if account_id is None:
            raise BadRequestError(message="A posting account is required.")
        acct = (
            self.db.query(Account)
            .filter(Account.id == account_id, Account.is_deleted.is_(False))
            .first()
        )
        if acct is None:
            raise BadRequestError(message="The selected account does not exist.")

    def create_run(
        self,
        *,
        code: str,
        period_start: date,
        period_end: date,
        facility_id: Optional[int] = None,
        department_id: Optional[int] = None,
        account_id: Optional[int] = None,
    ) -> PayrollRun:
        code = (code or "").strip()
        if not code:
            raise BadRequestError(message="A run code is required.")
        if period_end < period_start:
            raise BadRequestError(
                message="The period end date cannot precede the start date."
            )
        self._validate_account(account_id)

        existing = (
            self.db.query(PayrollRun).filter(PayrollRun.code == code).first()
        )
        if existing is not None:
            suffix = (
                " (it was archived, but the code is still reserved)"
                if existing.is_deleted
                else f" for {existing.period_start} to {existing.period_end}"
            )
            raise AlreadyExistsError(
                message=(
                    f"A payroll run with code '{code}' already exists{suffix}. "
                    "Choose a different run code, e.g. add a suffix like "
                    f"'{code}-2' for a supplementary run."
                )
            )

        run = PayrollRun(
            code=code,
            period_start=period_start,
            period_end=period_end,
            facility_id=facility_id,
            department_id=department_id,
            account_id=account_id,
            status=PayrollRunStatus.DRAFT,
        )
        self.db.add(run)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise AlreadyExistsError(
                message=f"A payroll run with code '{code}' already exists. Choose a different run code."
            )
        self.db.refresh(run)
        return run

    def submit_for_approval(self, run_id: int, *, requester_user_id: int):
        """
        Route a CALCULATED payroll run into the generic approval engine as a
        PAYROLL_RUN request. The run stays CALCULATED until the approval
        request is fully approved (engine finalize flips it to APPROVED) or
        rejected (flips it to CANCELLED).
        """
        from app.core.enums import RequestTypeCode
        from app.services.approval_service import ApprovalRequestService
        from app.schemas.approval_schemas import ApprovalRequestCreateSchema

        run = self.db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
        if run is None:
            raise NotFoundError(message="Payroll run not found.")
        if run.status != PayrollRunStatus.CALCULATED:
            raise BadRequestError(
                message=f"Only a calculated run can be submitted for approval (status is {run.status})."
            )

        approval = ApprovalRequestService(self.db)
        req = approval.submit(
            ApprovalRequestCreateSchema(
                request_type=RequestTypeCode.PAYROLL_RUN.value,
                subject_id=run.id,
                title=f"Payroll run {run.code} ({run.period_start} - {run.period_end})",
                description=f"Net {run.total_net}; gross {run.total_gross}; deductions {run.total_deductions}.",
                payload={
                    "code": run.code,
                    "total_gross": str(run.total_gross),
                    "total_net": str(run.total_net),
                    "period_start": str(run.period_start),
                    "period_end": str(run.period_end),
                },
                department_id=run.department_id,
                facility_id=run.facility_id,
            ),
            requester_user_id=requester_user_id,
        )
        if req is None:
            raise BadRequestError(
                message="Could not submit for approval. Configure a PAYROLL_RUN approval flow first."
            )
        run.approval_request_id = req.id
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    # ------------------------------------------------------------------
    # Payroll engine helpers
    # ------------------------------------------------------------------
    def _statutory_rate(self, code: str, default: Decimal, *, employer: bool = False) -> Decimal:
        """Effective statutory rate (%→fraction) from StatutoryDeductionConfig,
        falling back to the statutory default when unconfigured."""
        try:
            from app.models.all_models import StatutoryDeductionConfig
            row = (self.db.query(StatutoryDeductionConfig)
                   .filter(StatutoryDeductionConfig.code == code,
                           StatutoryDeductionConfig.is_deleted.is_(False))
                   .order_by(StatutoryDeductionConfig.effective_from.desc())
                   .first())
            if row is not None:
                val = row.employer_rate_percent if employer else row.rate_percent
                if val is not None:
                    return (Decimal(val) / Decimal("100")).quantize(Decimal("0.00001"))
        except Exception:
            pass
        return default

    def _proration_factor(self, staff, run) -> tuple[Decimal, dict]:
        """Calendar-day proration for mid-period joiners/leavers and approved
        unpaid leave. Returns (factor, detail)."""
        period_days = (run.period_end - run.period_start).days + 1
        if period_days <= 0:
            return Decimal("1"), {}
        start = run.period_start
        end = run.period_end
        hire = getattr(staff, "hire_date", None)
        exit_d = getattr(staff, "exit_date", None)
        if hire and hire > start:
            start = hire
        if exit_d and exit_d < end:
            end = exit_d
        if start > end:
            return Decimal("0"), {"reason": "not employed in period"}
        payable_days = (end - start).days + 1

        # Approved unpaid leave overlapping the payable window.
        unpaid_days = 0
        try:
            from app.models.all_models import LeaveRequest, LeaveType
            from app.core.enums import LeaveStatus
            leaves = (self.db.query(LeaveRequest)
                      .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
                      .filter(LeaveRequest.staff_profile_id == staff.id,
                              LeaveRequest.status == LeaveStatus.APPROVED,
                              LeaveType.is_paid.is_(False),
                              LeaveRequest.start_date <= end,
                              LeaveRequest.end_date >= start,
                              LeaveRequest.is_deleted.is_(False))
                      .all())
            for lv in leaves:
                o_start = max(lv.start_date, start)
                o_end = min(lv.end_date, end)
                if o_start <= o_end:
                    unpaid_days += (o_end - o_start).days + 1
        except Exception:
            unpaid_days = 0

        payable_days = max(0, payable_days - unpaid_days)
        factor = (Decimal(payable_days) / Decimal(period_days)).quantize(Decimal("0.0001"))
        detail = {}
        if factor < 1:
            detail = {"period_days": period_days, "payable_days": payable_days,
                      "unpaid_leave_days": unpaid_days,
                      "hire_date": hire.isoformat() if hire else None,
                      "exit_date": exit_d.isoformat() if exit_d else None}
        return factor, detail

    def _allowance_taxability(self) -> dict[str, bool]:
        """Map allowance type_code -> is_taxable (default True)."""
        try:
            from app.models.all_models import AllowanceType
            return {a.code: bool(a.is_taxable) for a in
                    self.db.query(AllowanceType).filter(AllowanceType.is_deleted.is_(False)).all()}
        except Exception:
            return {}

    def calculate(self, run_id: int) -> PayrollRun:
        run = self.db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
        if run is None:
            raise NotFoundError(message="Payroll run not found.")
        if run.status not in (PayrollRunStatus.DRAFT, PayrollRunStatus.CALCULATED):
            raise BadRequestError(message=f"Cannot recalculate a run in status {run.status}.")
        # Recalculation replaces previous results wholesale.
        line_ids = [
            lid for (lid,) in self.db.query(PayrollLine.id)
            .filter(PayrollLine.payroll_run_id == run.id).all()
        ]
        if line_ids:
            (self.db.query(PayrollLineComponent)
             .filter(PayrollLineComponent.payroll_line_id.in_(line_ids))
             .delete(synchronize_session=False))
        self.db.query(PayrollLine).filter(PayrollLine.payroll_run_id == run.id).delete()
        self.db.flush()
        # Component catalog (code -> PayrollComponent) drives taxability,
        # relief flags and display names for the persisted breakdown.
        catalog: dict[str, PayrollComponent] = {
            c.code: c for c in self.db.query(PayrollComponent)
            .filter(PayrollComponent.is_deleted.is_(False)).all()
        }
        taxable_map = self._allowance_taxability()
        pension_rate = self._statutory_rate("PENSION", Decimal("0.08"))
        pension_employer_rate = self._statutory_rate("PENSION", Decimal("0.10"), employer=True)
        nhf_rate = self._statutory_rate("NHF", Decimal("0.025"))
        # NSITF: 1% of monthly emoluments, employer-borne (ECA 2010).
        nsitf_rate = self._statutory_rate("NSITF", Decimal("0.01"), employer=True)
        paye_bands = None
        try:
            from app.models.all_models import StatutoryDeductionConfig
            cfg = (self.db.query(StatutoryDeductionConfig)
                   .filter(StatutoryDeductionConfig.code == "PAYE",
                           StatutoryDeductionConfig.is_deleted.is_(False))
                   .order_by(StatutoryDeductionConfig.effective_from.desc()).first())
            if cfg is not None and cfg.bands_json:
                paye_bands = tuple(
                    ((Decimal(str(w)) if w is not None else None),
                     (Decimal(str(r)) / Decimal("100")))
                    for w, r in cfg.bands_json)
        except Exception:
            paye_bands = None

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

            salary = (
                self.db.query(StaffSalary)
                .filter(
                    StaffSalary.staff_profile_id == s.id,
                    StaffSalary.is_active.is_(True),
                    StaffSalary.is_deleted.is_(False),
                )
                .order_by(StaffSalary.effective_from.desc())
                .first()
            )
            # Prefer the mapped StaffSalary base; fall back to the profile's
            # base_salary_amount so staff configured the older way still pay.
            if salary is not None and salary.base_amount:
                base = Decimal(salary.base_amount)
            else:
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

            # ---- Proration (mid-period joiners/leavers, unpaid leave) ----
            factor, proration_detail = self._proration_factor(s, run)
            if factor <= 0:
                continue  # not employed at all within the period
            base = (base * factor).quantize(Decimal("0.01"))

            # ---- Recurring allowances / deductions (amount or % of base) ----
            # Every element of pay is also captured as a normalized
            # component row (PayrollLineComponent) written after the line.
            comp_rows: list[dict] = []

            def _comp_name(code: str) -> str:
                c = catalog.get(code)
                if c is not None:
                    return c.name
                return code.replace("_", " ").title()

            comp_rows.append({
                "code": "BASIC", "name": _comp_name("BASIC"),
                "type": PayrollComponentType.EARNING, "amount": base,
                "taxable": True,
            })

            allowances_total = Decimal("0")
            taxable_allowances = Decimal("0")
            deductions_total = Decimal("0")
            relief_deductions = Decimal("0")
            if salary is not None:
                for a in (salary.allowances or []):
                    if a.get("percent") not in (None, ""):
                        amt = (base * Decimal(str(a["percent"])) / Decimal("100")).quantize(Decimal("0.01"))
                    else:
                        amt = (Decimal(str(a.get("amount", 0))) * factor).quantize(Decimal("0.01"))
                    allowances_total += amt
                    a_code = str(a.get("type_code") or "ALLOWANCE").upper()
                    cat = catalog.get(a_code)
                    a_taxable = (
                        bool(cat.is_taxable) if cat is not None
                        else taxable_map.get(a.get("type_code"), True)
                    )
                    if a_taxable:
                        taxable_allowances += amt
                    comp_rows.append({
                        "code": a_code, "name": _comp_name(a_code),
                        "type": PayrollComponentType.EARNING, "amount": amt,
                        "taxable": a_taxable,
                    })
                for d in (salary.deductions or []):
                    if d.get("percent") not in (None, ""):
                        amt_d = (base * Decimal(str(d["percent"])) / Decimal("100")).quantize(Decimal("0.01"))
                    else:
                        amt_d = Decimal(str(d.get("amount", 0)))
                    deductions_total += amt_d
                    # NHIS / life-insurance premiums are tax-deductible reliefs
                    # under the Nigeria Tax Act 2025; the catalog can flag
                    # further components as reliefs via is_tax_relief.
                    d_code = str(d.get("type_code") or "DEDUCTION").upper()
                    d_cat = catalog.get(d_code)
                    is_relief = (
                        d_code in {"NHIS", "LIFE_INSURANCE"}
                        or bool(getattr(d_cat, "is_tax_relief", False))
                    )
                    if is_relief:
                        relief_deductions += amt_d
                    comp_rows.append({
                        "code": d_code, "name": _comp_name(d_code),
                        "type": PayrollComponentType.DEDUCTION, "amount": amt_d,
                        "taxable": not is_relief,
                    })

            # ---- One-off inputs for this run (bonus / arrears / 13th month) ----
            bonus_amount = Decimal("0")
            oneoff_earn_taxable = Decimal("0")
            oneoff_deductions = Decimal("0")
            oneoffs = (self.db.query(PayrollOneOff)
                       .filter(PayrollOneOff.payroll_run_id == run.id,
                               PayrollOneOff.staff_profile_id == s.id,
                               PayrollOneOff.is_deleted.is_(False)).all())
            for oo in oneoffs:
                amt = Decimal(oo.amount or 0)
                if oo.kind == "OTHER_DEDUCTION":
                    oneoff_deductions += amt
                    comp_rows.append({
                        "code": "OTHER_DEDUCTION", "name": (oo.note or "One-off deduction"),
                        "type": PayrollComponentType.DEDUCTION, "amount": amt,
                        "taxable": True, "meta": {"one_off_id": oo.id},
                    })
                else:
                    bonus_amount += amt
                    if oo.is_taxable:
                        oneoff_earn_taxable += amt
                    comp_rows.append({
                        "code": str(oo.kind or "BONUS"),
                        "name": (oo.note or str(oo.kind or "Bonus").replace("_", " ").title()),
                        "type": PayrollComponentType.EARNING, "amount": amt,
                        "taxable": bool(oo.is_taxable), "meta": {"one_off_id": oo.id},
                    })

            # ---- Loan repayments due this run ----
            loan_repayment_total = Decimal("0")
            for loan in (
                self.db.query(StaffLoan)
                .filter(
                    StaffLoan.staff_profile_id == s.id,
                    StaffLoan.status == StaffLoanStatus.REPAYING,
                )
                .all()
            ):
                loan_repayment_total += min(
                    Decimal(loan.monthly_repayment_amount or 0),
                    Decimal(loan.outstanding_balance or 0),
                )

            # ---- Salary-advance recovery due this period ----
            advance_recovery_total = Decimal("0")
            due_advances = (self.db.query(SalaryAdvance)
                            .filter(SalaryAdvance.staff_profile_id == s.id,
                                    SalaryAdvance.status == SalaryAdvanceStatus.PAID,  # recovered only once disbursed
                                    SalaryAdvance.recovered_at.is_(None),
                                    SalaryAdvance.repayment_month <= run.period_end,
                                    SalaryAdvance.is_deleted.is_(False)).all())
            for adv in due_advances:
                advance_recovery_total += Decimal(adv.amount or 0)

            gross = base + allowances_total + overtime_amount + bonus_amount

            if overtime_amount > 0:
                comp_rows.append({
                    "code": "OVERTIME", "name": _comp_name("OVERTIME"),
                    "type": PayrollComponentType.EARNING, "amount": overtime_amount,
                    "taxable": True,
                })
            if loan_repayment_total > 0:
                comp_rows.append({
                    "code": "LOAN_REPAYMENT", "name": _comp_name("LOAN_REPAYMENT"),
                    "type": PayrollComponentType.DEDUCTION,
                    "amount": loan_repayment_total, "taxable": True,
                })
            if advance_recovery_total > 0:
                comp_rows.append({
                    "code": "SALARY_ADVANCE", "name": _comp_name("SALARY_ADVANCE"),
                    "type": PayrollComponentType.DEDUCTION,
                    "amount": advance_recovery_total, "taxable": True,
                    "meta": {"advance_ids": [a.id for a in due_advances]},
                })

            # ---- Statutory (Nigeria): pension on emoluments; NHF on basic;
            #      PAYE on taxable earnings only ----
            pension_base = base + allowances_total
            pension = (pension_base * pension_rate).quantize(Decimal("0.01"))
            pension_employer = (pension_base * pension_employer_rate).quantize(Decimal("0.01"))
            taxable_gross = base + taxable_allowances + overtime_amount + oneoff_earn_taxable
            nhf = (base * nhf_rate).quantize(Decimal("0.01"))
            annual_rent = Decimal(str(getattr(salary, "annual_rent", 0) or 0)) if salary else Decimal("0")
            paye = _compute_monthly_paye(
                taxable_gross, monthly_pension=pension, monthly_nhf=nhf,
                monthly_other_reliefs=relief_deductions,
                annual_rent=annual_rent, bands=paye_bands)

            for st_code, st_amt in (("PAYE", paye), ("PENSION", pension), ("NHF", nhf)):
                if st_amt > 0:
                    comp_rows.append({
                        "code": st_code, "name": _comp_name(st_code),
                        "type": PayrollComponentType.STATUTORY, "amount": st_amt,
                        "taxable": False,
                    })
            if pension_employer > 0:
                comp_rows.append({
                    "code": "PENSION_EMPLOYER", "name": _comp_name("PENSION_EMPLOYER"),
                    "type": PayrollComponentType.EMPLOYER_CONTRIBUTION,
                    "amount": pension_employer, "taxable": False,
                })
            # NSITF is employer-borne: reported/remitted but never deducted
            # from the staff member's pay.
            nsitf_employer = (gross * nsitf_rate).quantize(Decimal("0.01"))
            if nsitf_employer > 0:
                comp_rows.append({
                    "code": "NSITF", "name": _comp_name("NSITF"),
                    "type": PayrollComponentType.EMPLOYER_CONTRIBUTION,
                    "amount": nsitf_employer, "taxable": False,
                })

            total_deductions = (paye + pension + nhf + loan_repayment_total
                                + advance_recovery_total + deductions_total + oneoff_deductions)
            net = gross - total_deductions

            line = PayrollLine(
                payroll_run_id=run.id,
                staff_profile_id=s.id,
                timesheet_id=timesheet.id if timesheet else None,
                base_salary=base,
                total_allowances=allowances_total,
                overtime_amount=overtime_amount,
                bonus_amount=bonus_amount,
                gross_pay=gross,
                paye_amount=paye,
                pension_amount=pension,
                nhf_amount=nhf,
                health_insurance_amount=Decimal("0"),
                loan_repayment_amount=loan_repayment_total + advance_recovery_total,
                other_deductions=deductions_total + oneoff_deductions,
                total_deductions=total_deductions,
                net_pay=net,
                breakdown_json={
                    "allowances": (salary.allowances if salary else []),
                    "deductions": (salary.deductions if salary else []),
                    "proration": proration_detail or None,
                    "proration_factor": str(factor),
                    "taxable_gross": str(taxable_gross),
                    "pension_employer": str(pension_employer),
                    "nsitf_employer": str(nsitf_employer),
                    "loan_repayment": str(loan_repayment_total),
                    "advance_recovery": str(advance_recovery_total),
                    "advance_ids": [a.id for a in due_advances],
                    "one_offs": [
                        {"kind": o.kind, "amount": str(o.amount), "taxable": o.is_taxable, "note": o.note}
                        for o in oneoffs
                    ] or None,
                    "no_salary_mapped": salary is None and base == 0,
                    "salary_source": "staff_salary" if salary is not None and salary.base_amount else ("staff_profile" if base > 0 else "none"),
                },
                status=PayrollLineStatus.PENDING,
            )
            self.db.add(line)
            self.db.flush()  # line.id needed for the component rows

            for seq, row in enumerate(comp_rows):
                cat = catalog.get(row["code"])
                self.db.add(PayrollLineComponent(
                    payroll_line_id=line.id,
                    component_id=cat.id if cat is not None else None,
                    code=row["code"],
                    name=row["name"],
                    component_type=row["type"],
                    amount=row["amount"],
                    is_taxable=bool(row.get("taxable", True)),
                    sequence=seq,
                    meta_json=row.get("meta"),
                ))

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

    def mark_paid(self, run_id: int, *, actor_user_id: Optional[int] = None) -> PayrollRun:
        """
        Mark an APPROVED run (and every line) PAID, then settle the flow:
        post loan repayments against the staff's repaying loans and flag the
        approved overtime consumed by each line as PAID.
        """
        run = self.db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
        if run is None:
            raise NotFoundError(message="Payroll run not found.")
        if run.status != PayrollRunStatus.APPROVED:
            raise BadRequestError(message=f"Only an approved run can be marked paid (status is {run.status}).")

        now = datetime.now(timezone.utc)
        lines = self.db.query(PayrollLine).filter(PayrollLine.payroll_run_id == run.id).all()
        for line in lines:
            line.status = PayrollLineStatus.PAID
            line.paid_at = now

            # Settle salary advances withheld on this line.
            adv_ids = (line.breakdown_json or {}).get("advance_ids") or []
            if adv_ids:
                for adv in (self.db.query(SalaryAdvance)
                            .filter(SalaryAdvance.id.in_(adv_ids)).all()):
                    if adv.recovered_at is None:
                        adv.recovered_at = now
                        adv.recovered_in_payroll_line_id = line.id

            # Settle loan repayments withheld on this line.
            remaining = Decimal(line.loan_repayment_amount or 0)
            if remaining > 0:
                loans = (
                    self.db.query(StaffLoan)
                    .filter(
                        StaffLoan.staff_profile_id == line.staff_profile_id,
                        StaffLoan.status == StaffLoanStatus.REPAYING,
                    )
                    .order_by(StaffLoan.id.asc())
                    .all()
                )
                for loan in loans:
                    if remaining <= 0:
                        break
                    outstanding = Decimal(loan.outstanding_balance or 0)
                    if outstanding <= 0:
                        continue
                    pay = min(remaining, outstanding)
                    loan.outstanding_balance = outstanding - pay
                    self.db.add(
                        StaffLoanRepayment(
                            loan_id=loan.id,
                            payroll_line_id=line.id,
                            amount=pay,
                            balance_after=loan.outstanding_balance,
                            note=f"Auto repayment from payroll run {run.code}",
                        )
                    )
                    if loan.outstanding_balance <= 0:
                        loan.status = StaffLoanStatus.COMPLETED
                    remaining -= pay

            # Flag approved, still-unpaid overtime in this period as paid.
            for ot in (
                self.db.query(OvertimeRecord)
                .filter(
                    OvertimeRecord.staff_profile_id == line.staff_profile_id,
                    OvertimeRecord.work_date >= run.period_start,
                    OvertimeRecord.work_date <= run.period_end,
                    OvertimeRecord.status == OvertimeStatus.APPROVED,
                    OvertimeRecord.paid_in_payroll_line_id.is_(None),
                )
                .all()
            ):
                ot.status = OvertimeStatus.PAID
                ot.paid_in_payroll_line_id = line.id

        run.status = PayrollRunStatus.PAID
        run.paid_at = now
        self.db.commit()
        self.db.refresh(run)
        return run

    def set_staff_salary(
        self,
        *,
        staff_profile_id: int,
        base_amount: Decimal,
        grade_id: Optional[int] = None,
        step_id: Optional[int] = None,
        currency: str = "NGN",
        allowances: Optional[list] = None,
        deductions: Optional[list] = None,
        annual_rent: Optional[Decimal] = None,
        effective_from: date,
        effective_to: Optional[date] = None,
    ) -> StaffSalary:
        """
        Map (or re-map) a staff member's salary. Closes any prior active record
        so exactly one salary is effective at a time, and mirrors the base pay
        onto the staff profile so legacy reads and displays stay consistent.
        """
        staff = (
            self.db.query(StaffProfile)
            .filter(StaffProfile.id == staff_profile_id, StaffProfile.is_deleted.is_(False))
            .first()
        )
        if staff is None:
            raise NotFoundError(message="Staff profile not found.")

        # Close previous active salary rows for this staff member.
        for prev in (
            self.db.query(StaffSalary)
            .filter(
                StaffSalary.staff_profile_id == staff_profile_id,
                StaffSalary.is_active.is_(True),
                StaffSalary.is_deleted.is_(False),
            )
            .all()
        ):
            prev.is_active = False
            if prev.effective_to is None:
                prev.effective_to = effective_from

        rec = StaffSalary(
            staff_profile_id=staff_profile_id,
            grade_id=grade_id,
            step_id=step_id,
            base_amount=base_amount,
            currency=currency,
            allowances=allowances or [],
            deductions=deductions or [],
            annual_rent=annual_rent,
            effective_from=effective_from,
            effective_to=effective_to,
            is_active=True,
        )
        self.db.add(rec)

        # Mirror onto the profile (fallback source + directory display).
        staff.base_salary_amount = base_amount
        staff.salary_currency = currency
        if grade_id is not None:
            g = self.db.query(SalaryGrade).filter(SalaryGrade.id == grade_id).first()
            if g is not None:
                staff.salary_grade = g.code
        if step_id is not None:
            st = self.db.query(SalaryStep).filter(SalaryStep.id == step_id).first()
            if st is not None:
                staff.salary_step = st.code

        self.db.commit()
        self.db.refresh(rec)
        return rec

    def list_staff_salaries(self) -> list[dict]:
        """
        One row per active (non-deleted) staff member with their current
        effective salary mapping (or nulls when unmapped) — powers the salary
        mapping screen and surfaces who still needs a salary.
        """
        staff = (
            self.db.query(StaffProfile)
            .filter(StaffProfile.is_deleted.is_(False))
            .all()
        )
        active = (
            self.db.query(StaffSalary)
            .filter(StaffSalary.is_active.is_(True), StaffSalary.is_deleted.is_(False))
            .all()
        )
        by_staff: dict[int, StaffSalary] = {}
        for sal in active:
            cur = by_staff.get(sal.staff_profile_id)
            if cur is None or (sal.effective_from or date.min) >= (cur.effective_from or date.min):
                by_staff[sal.staff_profile_id] = sal

        user_ids = [st.user_id for st in staff if st.user_id]
        users = (
            {u.id: u for u in self.db.query(User).filter(User.id.in_(user_ids)).all()}
            if user_ids
            else {}
        )

        rows: list[dict] = []
        for st in staff:
            u = users.get(st.user_id) if st.user_id else None
            name = None
            if u is not None:
                name = f"{getattr(u, 'first_name', '') or ''} {getattr(u, 'last_name', '') or ''}".strip() or None
            sal = by_staff.get(st.id)
            rows.append(
                {
                    "staff_profile_id": st.id,
                    "staff_no": st.staff_no,
                    "staff_name": name,
                    "job_title": st.job_title,
                    "department_id": st.department_id,
                    "has_salary": sal is not None,
                    "salary_id": sal.id if sal else None,
                    "grade_id": sal.grade_id if sal else None,
                    "step_id": sal.step_id if sal else None,
                    "base_amount": (sal.base_amount if sal else st.base_salary_amount),
                    "currency": (sal.currency if sal else st.salary_currency) or "NGN",
                    "allowances": (sal.allowances if sal else []) or [],
                    "deductions": (sal.deductions if sal else []) or [],
                    "effective_from": sal.effective_from if sal else None,
                    "annual_rent": (str(sal.annual_rent) if sal and sal.annual_rent is not None else None),
                }
            )
        return rows



# ---------------------------------------------------------------------------
# Overtime
# ---------------------------------------------------------------------------


class PayrollComponentService:
    """CRUD + application logic for the payroll component catalog and
    component templates (reusable pay structures)."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Component catalog
    # ------------------------------------------------------------------

    def list_components(self) -> list[PayrollComponent]:
        return (
            self.db.query(PayrollComponent)
            .filter(PayrollComponent.is_deleted.is_(False))
            .order_by(PayrollComponent.component_type,
                      PayrollComponent.display_order,
                      PayrollComponent.code)
            .all()
        )

    def create_component(self, **fields) -> PayrollComponent:
        code = (fields.get("code") or "").strip().upper()
        if not code:
            raise BadRequestError(message="A component code is required.")
        fields["code"] = code
        existing = (
            self.db.query(PayrollComponent)
            .filter(PayrollComponent.code == code)
            .first()
        )
        if existing is not None:
            raise AlreadyExistsError(
                message=f"A payroll component with code '{code}' already exists."
            )
        comp = PayrollComponent(**fields)
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)
        return comp

    def update_component(self, component_id: int, **fields) -> PayrollComponent:
        comp = (
            self.db.query(PayrollComponent)
            .filter(PayrollComponent.id == component_id,
                    PayrollComponent.is_deleted.is_(False))
            .first()
        )
        if comp is None:
            raise NotFoundError(message="Payroll component not found.")
        if "code" in fields and fields["code"]:
            new_code = str(fields["code"]).strip().upper()
            clash = (
                self.db.query(PayrollComponent)
                .filter(PayrollComponent.code == new_code,
                        PayrollComponent.id != component_id)
                .first()
            )
            if clash is not None:
                raise AlreadyExistsError(
                    message=f"A payroll component with code '{new_code}' already exists."
                )
            fields["code"] = new_code
        for k, v in fields.items():
            setattr(comp, k, v)
        self.db.commit()
        self.db.refresh(comp)
        return comp

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def _get_template(self, template_id: int) -> PayrollComponentTemplate:
        tpl = (
            self.db.query(PayrollComponentTemplate)
            .filter(PayrollComponentTemplate.id == template_id,
                    PayrollComponentTemplate.is_deleted.is_(False))
            .first()
        )
        if tpl is None:
            raise NotFoundError(message="Component template not found.")
        return tpl

    def list_templates(self) -> list[PayrollComponentTemplate]:
        return (
            self.db.query(PayrollComponentTemplate)
            .filter(PayrollComponentTemplate.is_deleted.is_(False))
            .order_by(PayrollComponentTemplate.code)
            .all()
        )

    def create_template(self, *, code: str, name: str,
                        description: Optional[str] = None) -> PayrollComponentTemplate:
        code = (code or "").strip().upper()
        if not code:
            raise BadRequestError(message="A template code is required.")
        if (self.db.query(PayrollComponentTemplate)
                .filter(PayrollComponentTemplate.code == code).first()) is not None:
            raise AlreadyExistsError(
                message=f"A component template with code '{code}' already exists."
            )
        tpl = PayrollComponentTemplate(code=code, name=name, description=description)
        self.db.add(tpl)
        self.db.commit()
        self.db.refresh(tpl)
        return tpl

    def update_template(self, template_id: int, **fields) -> PayrollComponentTemplate:
        tpl = self._get_template(template_id)
        for k, v in fields.items():
            setattr(tpl, k, v)
        self.db.commit()
        self.db.refresh(tpl)
        return tpl

    def replace_items(self, template_id: int, items: list[dict]) -> PayrollComponentTemplate:
        """Replace the template's component list wholesale.

        Each item: {"component_id": int, "amount": num|None, "percent": num|None}.
        Statutory components are rejected — they are system-calculated.
        """
        tpl = self._get_template(template_id)
        comp_ids = [int(i["component_id"]) for i in items if i.get("component_id")]
        comps = {
            c.id: c for c in self.db.query(PayrollComponent)
            .filter(PayrollComponent.id.in_(comp_ids),
                    PayrollComponent.is_deleted.is_(False)).all()
        } if comp_ids else {}
        for i in items:
            cid = int(i.get("component_id") or 0)
            comp = comps.get(cid)
            if comp is None:
                raise BadRequestError(message=f"Component id {cid} not found.")
            if comp.is_statutory or comp.component_type in (
                PayrollComponentType.STATUTORY,
                PayrollComponentType.EMPLOYER_CONTRIBUTION,
            ):
                raise BadRequestError(
                    message=f"'{comp.name}' is statutory/system-calculated and "
                            "cannot be placed in a template."
                )
            if i.get("amount") in (None, "") and i.get("percent") in (None, ""):
                raise BadRequestError(
                    message=f"Provide an amount or percent for '{comp.name}'."
                )
        tpl.items.clear()
        self.db.flush()
        for order, i in enumerate(items):
            tpl.items.append(PayrollComponentTemplateItem(
                component_id=int(i["component_id"]),
                amount=(Decimal(str(i["amount"])) if i.get("amount") not in (None, "") else None),
                percent=(Decimal(str(i["percent"])) if i.get("percent") not in (None, "") else None),
                display_order=order,
            ))
        self.db.commit()
        self.db.refresh(tpl)
        return tpl

    def apply_template(self, template_id: int, *,
                       staff_profile_ids: list[int],
                       effective_from: Optional[date] = None) -> dict:
        """Apply a template to staff: writes a fresh versioned StaffSalary
        per staff member whose structure mirrors the template's items.

        A 'BASIC' component item with a fixed amount sets the base pay;
        otherwise each staff member's current base is carried forward.
        EARNING items become allowances; DEDUCTION items become deductions.
        """
        tpl = self._get_template(template_id)
        if not tpl.items:
            raise BadRequestError(message="The template has no components to apply.")
        eff = effective_from or date.today()

        base_override: Optional[Decimal] = None
        allowances: list[dict] = []
        deductions: list[dict] = []
        for item in tpl.items:
            comp = item.component
            if comp is None or not comp.is_active:
                continue
            if comp.code == "BASIC":
                if item.amount is not None:
                    base_override = Decimal(item.amount)
                continue
            entry: dict = {"type_code": comp.code, "label": comp.name}
            if item.percent is not None:
                entry["percent"] = str(item.percent)
            else:
                entry["amount"] = str(item.amount)
            if comp.component_type == PayrollComponentType.EARNING:
                allowances.append(entry)
            elif comp.component_type == PayrollComponentType.DEDUCTION:
                deductions.append(entry)

        payroll = PayrollService(self.db)
        applied, skipped = [], []
        for sid in staff_profile_ids:
            sp = (
                self.db.query(StaffProfile)
                .filter(StaffProfile.id == sid, StaffProfile.is_deleted.is_(False))
                .first()
            )
            if sp is None:
                skipped.append({"staff_profile_id": sid, "reason": "Staff not found."})
                continue
            current = (
                self.db.query(StaffSalary)
                .filter(StaffSalary.staff_profile_id == sid,
                        StaffSalary.is_active.is_(True),
                        StaffSalary.is_deleted.is_(False))
                .order_by(StaffSalary.effective_from.desc())
                .first()
            )
            base = base_override
            if base is None:
                base = (Decimal(current.base_amount) if current and current.base_amount
                        else (Decimal(sp.base_salary_amount) if sp.base_salary_amount else None))
            if base is None:
                skipped.append({
                    "staff_profile_id": sid,
                    "reason": "No base salary on record and the template does not set one.",
                })
                continue
            rec = payroll.set_staff_salary(
                staff_profile_id=sid,
                base_amount=base,
                grade_id=current.grade_id if current else None,
                step_id=current.step_id if current else None,
                currency=(current.currency if current else None) or "NGN",
                allowances=[dict(a) for a in allowances],
                deductions=[dict(d) for d in deductions],
                annual_rent=(current.annual_rent if current else None),
                effective_from=eff,
            )
            rec.component_template_id = tpl.id
            self.db.commit()
            applied.append({"staff_profile_id": sid, "staff_salary_id": rec.id})
        return {"template_id": tpl.id, "applied": applied, "skipped": skipped}

    # ------------------------------------------------------------------
    # Line components
    # ------------------------------------------------------------------

    def list_line_components(self, line_id: int) -> list[PayrollLineComponent]:
        line = self.db.query(PayrollLine).filter(PayrollLine.id == line_id).first()
        if line is None:
            raise NotFoundError(message="Payroll line not found.")
        return (
            self.db.query(PayrollLineComponent)
            .filter(PayrollLineComponent.payroll_line_id == line_id,
                    PayrollLineComponent.is_deleted.is_(False))
            .order_by(PayrollLineComponent.sequence)
            .all()
        )


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
        loan.status = StaffLoanStatus.REPAYING
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
        if loan.status != StaffLoanStatus.REPAYING:
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
