"""
HR / staff-management endpoints.

Six router groups, all mounted under /api/v1/hr:

* /hr/onboarding      — onboarding/offboarding checklists + status
* /hr/roster          — duty roster + assignments + shifts
* /hr/attendance      — clock in/out, attendance feed
* /hr/timesheets      — generate, submit, approve, lock
* /hr/leave           — leave types, requests, balances, holidays
* /hr/payroll         — payroll runs, lines, salary, overtime, loans
* /hr/people          — generic CRUD for documents, licences, training,
                        appraisals, tasks, announcements, incidents,
                        requests, audit log
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.core.exceptions import BadRequestError, NotFoundError
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser, require_plan_feature

from app.core.enums import (
    AttendanceMethod,
    DisciplinaryActionKind,
    EmploymentStatus,
    EmploymentType,
    LeaveStatus,
    LeaveTypeKind,
    OvertimeStatus,
    PayrollCalcMethod,
    PayrollComponentType,
    PayrollLineStatus,
    PayrollRunStatus,
    StaffDocumentCategory,
    StaffIncidentSeverity,
    StaffLoanStatus,
    StaffRequestStatus,
    StaffRequestType,
    StaffShiftType,
    StaffTaskPriority,
    StaffTaskStatus,
    TimesheetStatus,
)
from app.models.all_models import (
    AppraisalCycle,
    AppraisalKPI,
    AttendanceRecord,
    DisciplinaryActionRecord,
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
    StaffAnnouncement,
    StaffAppraisal,
    StaffAuditLog,
    StaffDocument,
    StaffEmploymentContract,
    StaffIncident,
    StaffLicense,
    StaffLoan,
    StaffLoanRepayment,
    StaffOffboardingChecklistItem,
    StaffOnboardingChecklistItem,
    StaffProfile,
    StaffRequest,
    StaffSalary,
    StaffStatusHistory,
    StaffTask,
    Timesheet,
    TimesheetEntry,
    TrainingRecord,
    TrainingSession,
)
from app.services.hr_service import (
    AttendanceService,
    DutyRosterService,
    LeaveService,
    OvertimeService,
    PayrollComponentService,
    PayrollService,
    StaffLicenseService,
    StaffLoanService,
    StaffOnboardingService,
    TimesheetService,
)


router = APIRouter(
    prefix="/hr", 
    tags=["HR - Staff Management"],
    dependencies=[Depends(require_plan_feature("hr"))]
)



# ===========================================================================
# Common helpers
# ===========================================================================


def _ok(rec) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in rec.__table__.columns:
        v = getattr(rec, col.name, None)
        if isinstance(v, (date, datetime)):
            v = v.isoformat()
        elif isinstance(v, Decimal):
            v = str(v)
        out[col.name] = v
    return out


def _run_out(run) -> dict[str, Any]:
    """Serialize a PayrollRun and surface its posting-account code/name."""
    out = _ok(run)
    acct = getattr(run, "account", None)
    out["account_code"] = getattr(acct, "code", None) if acct else None
    out["account_name"] = getattr(acct, "name", None) if acct else None
    return out


# ===========================================================================
# Onboarding / offboarding / status
# ===========================================================================


class TransitionStatusSchema(BaseModel):
    to_status: EmploymentStatus
    reason: Optional[str] = None
    exit_date: Optional[date] = None


@router.post(
    "/onboarding/{staff_profile_id}/seed",
    summary="Seed the default onboarding checklist for a staff profile",
    status_code=status.HTTP_201_CREATED,
)
def seed_onboarding(
    staff_profile_id: int,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    items = StaffOnboardingService(db, actor_user_id=getattr(actor, "id", None)).seed_onboarding_checklist(staff_profile_id)
    return [_ok(i) for i in items]


@router.post(
    "/onboarding/items/{item_id}/complete",
    summary="Mark an onboarding checklist item complete",
)
def complete_onboarding_item(
    item_id: int,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(
        StaffOnboardingService(db, actor_user_id=getattr(actor, "id", None)).complete_onboarding_item(item_id)
    )


@router.post(
    "/offboarding/{staff_profile_id}/seed",
    summary="Seed the default offboarding checklist",
    status_code=status.HTTP_201_CREATED,
)
def seed_offboarding(
    staff_profile_id: int,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    items = StaffOnboardingService(db, actor_user_id=getattr(actor, "id", None)).seed_offboarding_checklist(staff_profile_id)
    return [_ok(i) for i in items]


@router.post(
    "/offboarding/items/{item_id}/complete",
    summary="Mark an offboarding checklist item complete",
)
def complete_offboarding_item(
    item_id: int,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(
        StaffOnboardingService(db, actor_user_id=getattr(actor, "id", None)).complete_offboarding_item(item_id)
    )


@router.post(
    "/profiles/{staff_profile_id}/status",
    summary="Transition employment status (active / on-leave / suspended / resigned / terminated / retired / transferred)",
)
def transition_status(
    staff_profile_id: int,
    payload: TransitionStatusSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    sp = StaffOnboardingService(db, actor_user_id=getattr(actor, "id", None)).transition_status(
        staff_profile_id,
        to_status=payload.to_status,
        reason=payload.reason,
        exit_date=payload.exit_date,
    )
    return _ok(sp)


@router.get(
    "/profiles/{staff_profile_id}/status-history",
    summary="Status-transition history for a staff member",
)
def status_history(
    staff_profile_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return [
        _ok(r)
        for r in db.query(StaffStatusHistory)
        .filter(StaffStatusHistory.staff_profile_id == staff_profile_id)
        .order_by(StaffStatusHistory.changed_at.desc())
        .all()
    ]


# ===========================================================================
# Contracts / documents / licenses
# ===========================================================================


class ContractCreateSchema(BaseModel):
    staff_profile_id: int
    employment_type: str = "PERMANENT"
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    facility_id: Optional[int] = None
    salary_grade: Optional[str] = None
    salary_step: Optional[str] = None
    base_salary_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    probation_period_months: Optional[int] = None
    is_renewal: bool = False
    renewed_from_contract_id: Optional[int] = None
    notes: Optional[str] = None


@router.post(
    "/contracts",
    summary="Create an employment contract",
    status_code=status.HTTP_201_CREATED,
)
def create_contract(
    payload: ContractCreateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = StaffEmploymentContract(**payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


@router.get(
    "/contracts",
    summary="List contracts",
)
def list_contracts(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    staff_profile_id: Optional[int] = None,
    is_active: Optional[bool] = None,
):
    q = db.query(StaffEmploymentContract).filter(StaffEmploymentContract.is_deleted.is_(False))
    if staff_profile_id is not None:
        q = q.filter(StaffEmploymentContract.staff_profile_id == staff_profile_id)
    if is_active is not None:
        q = q.filter(StaffEmploymentContract.is_active.is_(is_active))
    return [_ok(r) for r in q.order_by(StaffEmploymentContract.id.desc()).all()]


class DocumentCreateSchema(BaseModel):
    staff_profile_id: int
    category: StaffDocumentCategory = StaffDocumentCategory.OTHER
    title: str
    description: Optional[str] = None
    file_url: Optional[str] = None
    s3_key: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    issued_on: Optional[date] = None
    expires_on: Optional[date] = None
    is_confidential: bool = True


@router.post(
    "/documents",
    summary="Upload metadata for a staff document",
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    payload: DocumentCreateSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = StaffDocument(uploaded_by_user_id=getattr(actor, "id", None), **payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


@router.get(
    "/documents",
    summary="List staff documents",
)
def list_documents(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    staff_profile_id: Optional[int] = None,
    category: Optional[StaffDocumentCategory] = None,
):
    q = db.query(StaffDocument).filter(StaffDocument.is_deleted.is_(False))
    if staff_profile_id is not None:
        q = q.filter(StaffDocument.staff_profile_id == staff_profile_id)
    if category is not None:
        q = q.filter(StaffDocument.category == category)
    return [_ok(r) for r in q.order_by(StaffDocument.id.desc()).all()]


class LicenseCreateSchema(BaseModel):
    staff_profile_id: int
    license_type: str
    license_number: str
    issuing_body: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    document_id: Optional[int] = None


@router.post(
    "/licenses",
    summary="Register a staff license / credential",
    status_code=status.HTTP_201_CREATED,
)
def create_license(
    payload: LicenseCreateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(StaffLicenseService(db).add(**payload.model_dump()))


@router.get(
    "/licenses",
    summary="List staff licenses",
)
def list_licenses(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    staff_profile_id: Optional[int] = None,
):
    q = db.query(StaffLicense).filter(StaffLicense.is_deleted.is_(False))
    if staff_profile_id is not None:
        q = q.filter(StaffLicense.staff_profile_id == staff_profile_id)
    return [_ok(r) for r in q.order_by(StaffLicense.expiry_date.asc()).all()]


@router.post(
    "/licenses/sweep-expiries",
    summary="Flip expired licenses to EXPIRED and near-expiry to PENDING_RENEWAL",
)
def sweep_license_expiries(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return StaffLicenseService(db).sweep_expiries()


# ===========================================================================
# Roster / shift / duty assignments
# ===========================================================================


class ShiftTemplateCreateSchema(BaseModel):
    code: str
    name: str
    shift_type: StaffShiftType = StaffShiftType.MORNING
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    break_minutes: int = 0
    grace_minutes: int = 10
    crosses_midnight: bool = False
    overtime_after_minutes: Optional[int] = None
    department_id: Optional[int] = None
    is_clinical: bool = True


@router.post(
    "/roster/shift-templates",
    summary="Create a shift template",
    status_code=status.HTTP_201_CREATED,
)
def create_shift_template(
    payload: ShiftTemplateCreateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = ShiftTemplate(**payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


@router.get(
    "/roster/shift-templates",
    summary="List shift templates",
)
def list_shift_templates(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    only_active: bool = True,
):
    q = db.query(ShiftTemplate).filter(ShiftTemplate.is_deleted.is_(False))
    if only_active:
        q = q.filter(ShiftTemplate.is_active.is_(True))
    return [_ok(r) for r in q.order_by(ShiftTemplate.code.asc()).all()]


class RosterCreateSchema(BaseModel):
    name: str
    facility_id: Optional[int] = None
    department_id: Optional[int] = None
    service_delivery_point_id: Optional[int] = None
    period_start: date
    period_end: date
    notes: Optional[str] = None


@router.post(
    "/roster/rosters",
    summary="Create a roster window",
    status_code=status.HTTP_201_CREATED,
)
def create_roster(
    payload: RosterCreateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(DutyRosterService(db).create_roster(**payload.model_dump()))


class AssignmentCreateSchema(BaseModel):
    roster_id: int
    staff_profile_id: int
    starts_at: datetime
    ends_at: datetime
    shift_type: StaffShiftType = StaffShiftType.MORNING
    shift_template_id: Optional[int] = None
    is_on_call: bool = False
    notes: Optional[str] = None


@router.post(
    "/roster/assignments",
    summary="Add an assignment to a roster (with double-booking prevention)",
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    payload: AssignmentCreateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(DutyRosterService(db).add_assignment(**payload.model_dump()))


class SwapAssignmentSchema(BaseModel):
    new_staff_profile_id: int


@router.post(
    "/roster/assignments/{assignment_id}/swap",
    summary="Swap an assignment with another staff member",
)
def swap_assignment(
    assignment_id: int,
    payload: SwapAssignmentSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(
        DutyRosterService(db).swap_assignment(
            assignment_id,
            new_staff_profile_id=payload.new_staff_profile_id,
            approved_by_user_id=getattr(actor, "id", None) or 0,
        )
    )


@router.get(
    "/roster/assignments",
    summary="List duty assignments",
)
def list_assignments(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    staff_profile_id: Optional[int] = None,
    roster_id: Optional[int] = None,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
):
    q = db.query(DutyAssignment).filter(DutyAssignment.is_deleted.is_(False))
    if staff_profile_id is not None:
        q = q.filter(DutyAssignment.staff_profile_id == staff_profile_id)
    if roster_id is not None:
        q = q.filter(DutyAssignment.roster_id == roster_id)
    if from_dt is not None:
        q = q.filter(DutyAssignment.ends_at >= from_dt)
    if to_dt is not None:
        q = q.filter(DutyAssignment.starts_at <= to_dt)
    return [_ok(r) for r in q.order_by(DutyAssignment.starts_at.asc()).limit(500).all()]


# ===========================================================================
# Attendance
# ===========================================================================


class ClockInSchema(BaseModel):
    staff_profile_id: int
    method: AttendanceMethod = AttendanceMethod.MANUAL
    device_identifier: Optional[str] = None
    location: Optional[str] = None
    when: Optional[datetime] = None


@router.post(
    "/attendance/clock-in",
    summary="Record clock-in",
    status_code=status.HTTP_201_CREATED,
)
def clock_in(
    payload: ClockInSchema,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(AttendanceService(db).clock_in(**payload.model_dump()))


class ClockOutSchema(BaseModel):
    attendance_record_id: int
    when: Optional[datetime] = None


@router.post(
    "/attendance/clock-out",
    summary="Record clock-out",
)
def clock_out(
    payload: ClockOutSchema,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(AttendanceService(db).clock_out(**payload.model_dump()))


@router.get(
    "/attendance",
    summary="List attendance records",
)
def list_attendance(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    staff_profile_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
):
    q = db.query(AttendanceRecord).filter(AttendanceRecord.is_deleted.is_(False))
    if staff_profile_id is not None:
        q = q.filter(AttendanceRecord.staff_profile_id == staff_profile_id)
    if from_date is not None:
        q = q.filter(AttendanceRecord.work_date >= from_date)
    if to_date is not None:
        q = q.filter(AttendanceRecord.work_date <= to_date)
    return [_ok(r) for r in q.order_by(AttendanceRecord.work_date.desc()).limit(500).all()]


# ===========================================================================
# Timesheets
# ===========================================================================


class TimesheetGenerateSchema(BaseModel):
    staff_profile_id: int
    period_start: date
    period_end: date


@router.post(
    "/timesheets/generate",
    summary="Generate a timesheet from attendance",
    status_code=status.HTTP_201_CREATED,
)
def generate_timesheet(
    payload: TimesheetGenerateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(TimesheetService(db).generate(**payload.model_dump()))


@router.post(
    "/timesheets/{timesheet_id}/submit",
    summary="Submit a draft timesheet for approval",
)
def submit_timesheet(
    timesheet_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(TimesheetService(db).submit(timesheet_id))


@router.post(
    "/timesheets/{timesheet_id}/approve",
    summary="Approve a submitted timesheet",
)
def approve_timesheet(
    timesheet_id: int,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(
        TimesheetService(db).approve(
            timesheet_id, approved_by_user_id=getattr(actor, "id", None) or 0
        )
    )


@router.post(
    "/timesheets/{timesheet_id}/lock",
    summary="Lock an approved timesheet (post-payroll)",
)
def lock_timesheet(
    timesheet_id: int,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(TimesheetService(db).lock(timesheet_id))


@router.get(
    "/timesheets",
    summary="List timesheets",
)
def list_timesheets(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    staff_profile_id: Optional[int] = None,
    timesheet_status: Optional[TimesheetStatus] = None,
):
    q = db.query(Timesheet).filter(Timesheet.is_deleted.is_(False))
    if staff_profile_id is not None:
        q = q.filter(Timesheet.staff_profile_id == staff_profile_id)
    if timesheet_status is not None:
        q = q.filter(Timesheet.status == timesheet_status)
    return [_ok(r) for r in q.order_by(Timesheet.id.desc()).limit(500).all()]


# ===========================================================================
# Leave + holidays
# ===========================================================================


class LeaveTypeCreateSchema(BaseModel):
    code: str
    name: str
    kind: LeaveTypeKind = LeaveTypeKind.OTHER
    default_annual_days: Optional[Decimal] = None
    is_paid: bool = True
    requires_approval: bool = True


@router.post(
    "/leave/types",
    summary="Create a leave type",
    status_code=status.HTTP_201_CREATED,
)
def create_leave_type(
    payload: LeaveTypeCreateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = LeaveType(**payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


@router.get(
    "/leave/types",
    summary="List leave types",
)
def list_leave_types(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return [_ok(r) for r in db.query(LeaveType).filter(LeaveType.is_deleted.is_(False)).all()]


class LeaveRequestCreateSchema(BaseModel):
    staff_profile_id: int
    leave_type_id: int
    start_date: date
    end_date: date
    reason: Optional[str] = None
    cover_staff_id: Optional[int] = None
    handover_notes: Optional[str] = None


@router.post(
    "/leave/requests",
    summary="Submit a leave request",
    status_code=status.HTTP_201_CREATED,
)
def submit_leave(
    payload: LeaveRequestCreateSchema,
    actor: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(
        LeaveService(db, actor_user_id=getattr(actor, "id", None)).request_leave(**payload.model_dump())
    )


class LeaveDecisionSchema(BaseModel):
    approve: bool
    note: Optional[str] = None


@router.post(
    "/leave/requests/{request_id}/decide",
    summary="Approve or reject a leave request",
)
def decide_leave(
    request_id: int,
    payload: LeaveDecisionSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(
        LeaveService(db, actor_user_id=getattr(actor, "id", None)).decide(
            request_id,
            approve=payload.approve,
            decided_by_user_id=getattr(actor, "id", None) or 0,
            note=payload.note,
        )
    )


@router.get(
    "/leave/requests",
    summary="List leave requests",
)
def list_leave_requests(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    staff_profile_id: Optional[int] = None,
    leave_status: Optional[LeaveStatus] = None,
):
    q = db.query(LeaveRequest).filter(LeaveRequest.is_deleted.is_(False))
    if staff_profile_id is not None:
        q = q.filter(LeaveRequest.staff_profile_id == staff_profile_id)
    if leave_status is not None:
        q = q.filter(LeaveRequest.status == leave_status)
    return [_ok(r) for r in q.order_by(LeaveRequest.id.desc()).all()]


@router.get(
    "/leave/balances",
    summary="List leave balances",
)
def list_leave_balances(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    staff_profile_id: Optional[int] = None,
    year: Optional[int] = None,
):
    q = db.query(LeaveBalance).filter(LeaveBalance.is_deleted.is_(False))
    if staff_profile_id is not None:
        q = q.filter(LeaveBalance.staff_profile_id == staff_profile_id)
    if year is not None:
        q = q.filter(LeaveBalance.year == year)
    return [_ok(r) for r in q.order_by(LeaveBalance.year.desc()).all()]


@router.post(
    "/leave/holidays",
    summary="Configure a public holiday",
    status_code=status.HTTP_201_CREATED,
)
def create_holiday(
    payload: dict,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = PublicHoliday(**payload)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


@router.get(
    "/leave/holidays",
    summary="List public holidays",
)
def list_holidays(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    year: Optional[int] = None,
):
    q = db.query(PublicHoliday).filter(PublicHoliday.is_deleted.is_(False))
    if year is not None:
        q = q.filter(
            PublicHoliday.holiday_date >= date(year, 1, 1),
            PublicHoliday.holiday_date <= date(year, 12, 31),
        )
    return [_ok(r) for r in q.order_by(PublicHoliday.holiday_date.asc()).all()]


# ===========================================================================
# Payroll / overtime / loans / salary
# ===========================================================================


class PayrollRunCreateSchema(BaseModel):
    code: str
    period_start: date
    period_end: date
    facility_id: Optional[int] = None
    department_id: Optional[int] = None
    account_id: int = Field(..., description="Chart-of-accounts account this payroll run posts to.")


@router.post(
    "/payroll/runs",
    summary="Create a payroll run (DRAFT)",
    status_code=status.HTTP_201_CREATED,
)
def create_payroll_run(
    payload: PayrollRunCreateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _run_out(PayrollService(db).create_run(**payload.model_dump()))


@router.post(
    "/payroll/runs/{run_id}/calculate",
    summary="Calculate payroll lines for the run",
)
def calculate_payroll(
    run_id: int,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _run_out(PayrollService(db).calculate(run_id))


@router.post(
    "/payroll/runs/{run_id}/submit-approval",
    summary="Submit a calculated payroll run into the approval engine",
)
def submit_payroll_for_approval(
    run_id: int,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _run_out(
        PayrollService(db).submit_for_approval(
            run_id, requester_user_id=getattr(actor, "id", None) or 0
        )
    )


@router.post(
    "/payroll/runs/{run_id}/lock",
    summary="Lock a payroll run + its timesheets",
)
def lock_payroll(
    run_id: int,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _run_out(PayrollService(db).lock(run_id))


@router.get(
    "/payroll/runs",
    summary="List payroll runs",
)
def list_payroll_runs(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    run_status: Optional[PayrollRunStatus] = None,
):
    q = db.query(PayrollRun).filter(PayrollRun.is_deleted.is_(False))
    if run_status is not None:
        q = q.filter(PayrollRun.status == run_status)
    return [_run_out(r) for r in q.order_by(PayrollRun.id.desc()).all()]


@router.get(
    "/payroll/runs/{run_id}/lines",
    summary="List payroll lines for a run",
)
def list_payroll_lines(
    run_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return [
        _ok(r)
        for r in db.query(PayrollLine)
        .filter(PayrollLine.payroll_run_id == run_id, PayrollLine.is_deleted.is_(False))
        .all()
    ]


# ===========================================================================
# Pension providers (PFAs)
# ===========================================================================


class PensionProviderCreateSchema(BaseModel):
    code: str = Field(..., min_length=2, max_length=60)
    name: str = Field(..., min_length=2, max_length=200)
    pfa_license_no: Optional[str] = Field(None, max_length=80)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=40)
    address: Optional[str] = None
    bank_name: Optional[str] = Field(None, max_length=120)
    bank_account_no: Optional[str] = Field(None, max_length=40)
    note: Optional[str] = None


class PensionProviderUpdateSchema(BaseModel):
    code: Optional[str] = Field(None, min_length=2, max_length=60)
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    pfa_license_no: Optional[str] = Field(None, max_length=80)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=40)
    address: Optional[str] = None
    bank_name: Optional[str] = Field(None, max_length=120)
    bank_account_no: Optional[str] = Field(None, max_length=40)
    is_active: Optional[bool] = None
    note: Optional[str] = None


@router.get("/pension-providers", summary="List pension providers (PFAs)")
def list_pension_providers(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    from sqlalchemy import func
    from app.models.all_models import PensionProvider, StaffProfile as _SP

    providers = (
        db.query(PensionProvider)
        .filter(PensionProvider.is_deleted.is_(False))
        .order_by(PensionProvider.name)
        .all()
    )
    counts: dict[int, int] = {}
    for pid, n in (
        db.query(_SP.pension_provider_id, func.count(_SP.id))
        .filter(_SP.is_deleted.is_(False), _SP.pension_provider_id.isnot(None))
        .group_by(_SP.pension_provider_id)
        .all()
    ):
        counts[pid] = n
    out = []
    for pv in providers:
        row = _ok(pv)
        row["staff_count"] = counts.get(pv.id, 0)
        out.append(row)
    return out


@router.post(
    "/pension-providers",
    summary="Create a pension provider",
    status_code=status.HTTP_201_CREATED,
)
def create_pension_provider(
    payload: PensionProviderCreateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    from app.core.exceptions import AlreadyExistsError
    from app.models.all_models import PensionProvider

    code = payload.code.strip().upper()
    if db.query(PensionProvider).filter(PensionProvider.code == code).first():
        raise AlreadyExistsError(message=f"A pension provider with code '{code}' already exists.")
    pv = PensionProvider(**{**payload.model_dump(), "code": code})
    db.add(pv)
    db.commit()
    db.refresh(pv)
    return _ok(pv)


@router.patch("/pension-providers/{provider_id}", summary="Update a pension provider")
def update_pension_provider(
    provider_id: int,
    payload: PensionProviderUpdateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    from app.core.exceptions import AlreadyExistsError, NotFoundError
    from app.models.all_models import PensionProvider

    pv = (
        db.query(PensionProvider)
        .filter(PensionProvider.id == provider_id, PensionProvider.is_deleted.is_(False))
        .first()
    )
    if pv is None:
        raise NotFoundError(message="Pension provider not found.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("code"):
        new_code = data["code"].strip().upper()
        clash = (
            db.query(PensionProvider)
            .filter(PensionProvider.code == new_code, PensionProvider.id != provider_id)
            .first()
        )
        if clash is not None:
            raise AlreadyExistsError(message=f"A pension provider with code '{new_code}' already exists.")
        data["code"] = new_code
    for k, v in data.items():
        setattr(pv, k, v)
    db.commit()
    db.refresh(pv)
    return _ok(pv)


# ===========================================================================
# Payroll component catalog / templates / line component breakdown
# ===========================================================================


class PayrollComponentCreateSchema(BaseModel):
    code: str = Field(..., min_length=2, max_length=60)
    name: str = Field(..., min_length=2, max_length=150)
    component_type: PayrollComponentType
    calc_method: PayrollCalcMethod = PayrollCalcMethod.FIXED_AMOUNT
    default_amount: Optional[Decimal] = Field(None, ge=0)
    default_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    is_taxable: bool = True
    is_tax_relief: bool = False
    gl_account_id: Optional[int] = None
    display_order: int = 0
    description: Optional[str] = None


class PayrollComponentUpdateSchema(BaseModel):
    code: Optional[str] = Field(None, min_length=2, max_length=60)
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    component_type: Optional[PayrollComponentType] = None
    calc_method: Optional[PayrollCalcMethod] = None
    default_amount: Optional[Decimal] = Field(None, ge=0)
    default_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    is_taxable: Optional[bool] = None
    is_tax_relief: Optional[bool] = None
    is_active: Optional[bool] = None
    gl_account_id: Optional[int] = None
    display_order: Optional[int] = None
    description: Optional[str] = None


class ComponentTemplateCreateSchema(BaseModel):
    code: str = Field(..., min_length=2, max_length=60)
    name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = None


class ComponentTemplateUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TemplateItemSchema(BaseModel):
    component_id: int
    amount: Optional[Decimal] = Field(None, ge=0)
    percent: Optional[Decimal] = Field(None, ge=0, le=100)


class TemplateItemsReplaceSchema(BaseModel):
    items: list[TemplateItemSchema]


class TemplateApplySchema(BaseModel):
    staff_profile_ids: list[int] = Field(..., min_length=1)
    effective_from: Optional[date] = None


def _template_out(tpl) -> dict[str, Any]:
    out = _ok(tpl)
    out["items"] = [
        {
            "id": it.id,
            "component_id": it.component_id,
            "code": it.component.code if it.component else None,
            "name": it.component.name if it.component else None,
            "component_type": (
                it.component.component_type.value
                if it.component and it.component.component_type else None
            ),
            "amount": str(it.amount) if it.amount is not None else None,
            "percent": str(it.percent) if it.percent is not None else None,
            "display_order": it.display_order,
        }
        for it in (tpl.items or [])
        if not it.is_deleted
    ]
    return out


@router.get(
    "/payroll/components",
    summary="List payroll components (the pay element catalog)",
)
def list_payroll_components(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return [_ok(c) for c in PayrollComponentService(db).list_components()]


@router.post(
    "/payroll/components",
    summary="Create a payroll component",
    status_code=status.HTTP_201_CREATED,
)
def create_payroll_component(
    payload: PayrollComponentCreateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(PayrollComponentService(db).create_component(**payload.model_dump()))


@router.patch(
    "/payroll/components/{component_id}",
    summary="Update a payroll component",
)
def update_payroll_component(
    component_id: int,
    payload: PayrollComponentUpdateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(
        PayrollComponentService(db).update_component(
            component_id, **payload.model_dump(exclude_unset=True)
        )
    )


@router.get(
    "/payroll/component-templates",
    summary="List payroll component templates (reusable pay structures)",
)
def list_component_templates(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return [_template_out(t) for t in PayrollComponentService(db).list_templates()]


@router.post(
    "/payroll/component-templates",
    summary="Create a payroll component template",
    status_code=status.HTTP_201_CREATED,
)
def create_component_template(
    payload: ComponentTemplateCreateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _template_out(PayrollComponentService(db).create_template(**payload.model_dump()))


@router.patch(
    "/payroll/component-templates/{template_id}",
    summary="Update a payroll component template",
)
def update_component_template(
    template_id: int,
    payload: ComponentTemplateUpdateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _template_out(
        PayrollComponentService(db).update_template(
            template_id, **payload.model_dump(exclude_unset=True)
        )
    )


@router.put(
    "/payroll/component-templates/{template_id}/items",
    summary="Replace a template's component items",
)
def replace_component_template_items(
    template_id: int,
    payload: TemplateItemsReplaceSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _template_out(
        PayrollComponentService(db).replace_items(
            template_id, [i.model_dump() for i in payload.items]
        )
    )


@router.post(
    "/payroll/component-templates/{template_id}/apply",
    summary="Apply a template to staff (writes a fresh versioned salary structure each)",
)
def apply_component_template(
    template_id: int,
    payload: TemplateApplySchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return PayrollComponentService(db).apply_template(
        template_id,
        staff_profile_ids=payload.staff_profile_ids,
        effective_from=payload.effective_from,
    )


@router.get(
    "/payroll/lines/{line_id}/components",
    summary="Normalized component breakdown for one payslip line",
)
def list_payroll_line_components(
    line_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return [_ok(c) for c in PayrollComponentService(db).list_line_components(line_id)]


class OvertimeCreateSchema(BaseModel):
    staff_profile_id: int
    work_date: date
    hours: Decimal = Field(..., ge=0)
    multiplier: Decimal = Decimal("1.5")
    reason: Optional[str] = None


@router.post(
    "/overtime",
    summary="Submit an overtime claim",
    status_code=status.HTTP_201_CREATED,
)
def submit_overtime(
    payload: OvertimeCreateSchema,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(OvertimeService(db).submit(**payload.model_dump()))


class OvertimeDecisionSchema(BaseModel):
    approve: bool


@router.post(
    "/overtime/{record_id}/decide",
    summary="Approve or reject an overtime claim",
)
def decide_overtime(
    record_id: int,
    payload: OvertimeDecisionSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(
        OvertimeService(db).decide(
            record_id,
            approve=payload.approve,
            approved_by_user_id=getattr(actor, "id", None) or 0,
        )
    )


class LoanCreateSchema(BaseModel):
    staff_profile_id: int
    principal_amount: Decimal = Field(..., gt=0)
    repayment_count: int = Field(..., gt=0)
    interest_percent: Decimal = Decimal("0")
    currency: str = "NGN"
    starts_on: Optional[date] = None
    note: Optional[str] = None


@router.post(
    "/loans",
    summary="Request a staff loan / advance",
    status_code=status.HTTP_201_CREATED,
)
def request_loan(
    payload: LoanCreateSchema,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(StaffLoanService(db).create(**payload.model_dump()))


@router.post(
    "/loans/{loan_id}/approve",
    summary="Approve a loan request",
)
def approve_loan(
    loan_id: int,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(
        StaffLoanService(db).approve(loan_id, approved_by_user_id=getattr(actor, "id", None) or 0)
    )


class LoanRepaymentSchema(BaseModel):
    amount: Decimal = Field(..., gt=0)
    payroll_line_id: Optional[int] = None
    note: Optional[str] = None


@router.post(
    "/loans/{loan_id}/repay",
    summary="Post a loan repayment",
    status_code=status.HTTP_201_CREATED,
)
def repay_loan(
    loan_id: int,
    payload: LoanRepaymentSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(StaffLoanService(db).repay(loan_id=loan_id, **payload.model_dump()))


class StaffSalarySchema(BaseModel):
    staff_profile_id: int
    grade_id: Optional[int] = None
    step_id: Optional[int] = None
    base_amount: Decimal = Field(..., ge=0)
    currency: str = "NGN"
    allowances: Optional[list[dict]] = None
    deductions: Optional[list[dict]] = None
    annual_rent: Optional[Decimal] = Field(None, ge=0, description="Declared annual rent — drives NTA-2025 rent relief in PAYE.")
    effective_from: date
    effective_to: Optional[date] = None


@router.post(
    "/payroll/salary",
    summary="Configure a staff member's salary",
    status_code=status.HTTP_201_CREATED,
)
def set_staff_salary(
    payload: StaffSalarySchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(PayrollService(db).set_staff_salary(**payload.model_dump()))


@router.get(
    "/payroll/salary",
    summary="List every staff member with their current salary mapping",
)
def list_staff_salaries(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return PayrollService(db).list_staff_salaries()


# ===========================================================================
# Staff records — HR directory with employment, banking and compensation
# ===========================================================================


class StaffRecordUpdateSchema(BaseModel):
    """Fields an HR administrator may update on a staff member."""

    # Job & employment
    job_title: Optional[str] = Field(None, max_length=150)
    designation: Optional[str] = Field(None, max_length=150)
    specialty: Optional[str] = Field(None, max_length=150)
    department_id: Optional[int] = None
    employment_type: Optional[EmploymentType] = None
    employment_status: Optional[EmploymentStatus] = None
    hire_date: Optional[date] = None
    confirmation_date: Optional[date] = None
    probation_end_date: Optional[date] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    exit_date: Optional[date] = None
    exit_reason: Optional[str] = None
    supervisor_staff_id: Optional[int] = None
    # Personal & contact
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    marital_status: Optional[str] = Field(None, max_length=20)
    nationality: Optional[str] = Field(None, max_length=80)
    address_line_1: Optional[str] = Field(None, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state_region: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=80)
    personal_email: Optional[str] = Field(None, max_length=255)
    personal_phone: Optional[str] = Field(None, max_length=40)
    # Next of kin & emergency contact
    next_of_kin_name: Optional[str] = Field(None, max_length=150)
    next_of_kin_relationship: Optional[str] = Field(None, max_length=80)
    next_of_kin_phone: Optional[str] = Field(None, max_length=40)
    emergency_contact_name: Optional[str] = Field(None, max_length=150)
    emergency_contact_phone: Optional[str] = Field(None, max_length=40)
    # Bank & statutory
    bank_name: Optional[str] = Field(None, max_length=120)
    bank_account_no: Optional[str] = Field(None, max_length=40)
    bank_account_name: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=80)
    pension_pin: Optional[str] = Field(None, max_length=80)
    pension_provider_id: Optional[int] = None
    nhf_no: Optional[str] = Field(None, max_length=80)
    # Compensation — any of these creates a new versioned StaffSalary record.
    base_salary_amount: Optional[Decimal] = Field(None, ge=0)
    salary_currency: Optional[str] = Field(None, min_length=3, max_length=3)
    salary_grade_id: Optional[int] = None
    salary_step_id: Optional[int] = None
    salary_effective_from: Optional[date] = None
    # Full salary structure — earnings and non-statutory deductions.
    # Each item: {"type_code": str, "label": str, "amount": number}.
    allowances: Optional[list[dict]] = None
    deductions: Optional[list[dict]] = None


@router.get(
    "/staff-records",
    summary="HR staff directory: employment, banking and compensation per staff member",
)
def list_staff_records(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    search: Optional[str] = None,
):
    from app.models.all_models import Department, User

    staff = (
        db.query(StaffProfile)
        .filter(StaffProfile.is_deleted.is_(False))
        .order_by(StaffProfile.staff_no)
        .all()
    )
    user_ids = [sp.user_id for sp in staff if sp.user_id]
    users = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )
    departments = {
        d.id: d.name
        for d in db.query(Department).filter(Department.is_deleted.is_(False)).all()
    }
    from app.models.all_models import PensionProvider as _PP
    providers = {
        p.id: p.name
        for p in db.query(_PP).filter(_PP.is_deleted.is_(False)).all()
    }

    active = (
        db.query(StaffSalary)
        .filter(StaffSalary.is_active.is_(True), StaffSalary.is_deleted.is_(False))
        .all()
    )
    sal_by_staff: dict[int, StaffSalary] = {}
    for sal in active:
        cur = sal_by_staff.get(sal.staff_profile_id)
        if cur is None or (sal.effective_from or date.min) >= (cur.effective_from or date.min):
            sal_by_staff[sal.staff_profile_id] = sal

    q = (search or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for sp in staff:
        u = users.get(sp.user_id) if sp.user_id else None
        name = None
        if u is not None:
            name = f"{getattr(u, 'first_name', '') or ''} {getattr(u, 'last_name', '') or ''}".strip() or None
        sal = sal_by_staff.get(sp.id)
        row: dict[str, Any] = {
            "staff_profile_id": sp.id,
            "user_id": sp.user_id,
            "staff_no": sp.staff_no,
            "staff_name": name,
            "email": getattr(u, "email", None) if u else None,
            "job_title": sp.job_title,
            "designation": sp.designation,
            "specialty": sp.specialty,
            "department_id": sp.department_id,
            "department_name": departments.get(sp.department_id) if sp.department_id else None,
            "employment_type": sp.employment_type.value if sp.employment_type else None,
            "employment_status": sp.employment_status.value if sp.employment_status else None,
            "hire_date": sp.hire_date.isoformat() if sp.hire_date else None,
            "confirmation_date": sp.confirmation_date.isoformat() if sp.confirmation_date else None,
            "probation_end_date": sp.probation_end_date.isoformat() if sp.probation_end_date else None,
            "contract_start_date": sp.contract_start_date.isoformat() if sp.contract_start_date else None,
            "contract_end_date": sp.contract_end_date.isoformat() if sp.contract_end_date else None,
            "exit_date": sp.exit_date.isoformat() if sp.exit_date else None,
            "exit_reason": sp.exit_reason,
            "supervisor_staff_id": sp.supervisor_staff_id,
            "date_of_birth": sp.date_of_birth.isoformat() if sp.date_of_birth else None,
            "gender": sp.gender,
            "marital_status": sp.marital_status,
            "nationality": sp.nationality,
            "address_line_1": sp.address_line_1,
            "address_line_2": sp.address_line_2,
            "city": sp.city,
            "state_region": sp.state_region,
            "country": sp.country,
            "personal_email": sp.personal_email,
            "personal_phone": sp.personal_phone,
            "next_of_kin_name": sp.next_of_kin_name,
            "next_of_kin_relationship": sp.next_of_kin_relationship,
            "next_of_kin_phone": sp.next_of_kin_phone,
            "emergency_contact_name": sp.emergency_contact_name,
            "emergency_contact_phone": sp.emergency_contact_phone,
            "has_salary": sal is not None,
            "salary_grade_id": sal.grade_id if sal else None,
            "salary_step_id": sal.step_id if sal else None,
            "salary_grade": sp.salary_grade,
            "salary_step": sp.salary_step,
            "base_salary_amount": (
                str(sal.base_amount)
                if sal
                else (str(sp.base_salary_amount) if sp.base_salary_amount is not None else None)
            ),
            "salary_currency": (sal.currency if sal else sp.salary_currency) or "NGN",
            "salary_effective_from": (
                sal.effective_from.isoformat() if sal and sal.effective_from else None
            ),
            "allowances": (sal.allowances if sal and sal.allowances else []),
            "deductions": (sal.deductions if sal and sal.deductions else []),
            "bank_name": sp.bank_name,
            "bank_account_no": sp.bank_account_no,
            "bank_account_name": sp.bank_account_name,
            "tax_id": sp.tax_id,
            "pension_pin": sp.pension_pin,
            "pension_provider_id": sp.pension_provider_id,
            "pension_provider_name": providers.get(sp.pension_provider_id)
            if sp.pension_provider_id else None,
            "nhf_no": sp.nhf_no,
        }
        if q:
            hay = " ".join(
                str(v)
                for v in (name, sp.staff_no, sp.job_title, row["email"], row["department_name"])
                if v
            ).lower()
            if q not in hay:
                continue
        rows.append(row)
    return rows


@router.patch(
    "/staff-records/{staff_profile_id}",
    summary="HR update of a staff member's employment, banking or compensation fields",
)
def update_staff_record(
    staff_profile_id: int,
    payload: StaffRecordUpdateSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    from app.core.exceptions import BadRequestError, NotFoundError
    from app.models.all_models import Department, SalaryGrade, SalaryStep

    sp = (
        db.query(StaffProfile)
        .filter(StaffProfile.id == staff_profile_id, StaffProfile.is_deleted.is_(False))
        .first()
    )
    if sp is None:
        raise NotFoundError(message="Staff profile not found.")

    data = payload.model_dump(exclude_unset=True)

    if data.get("department_id") is not None:
        dept = (
            db.query(Department)
            .filter(Department.id == data["department_id"], Department.is_deleted.is_(False))
            .first()
        )
        if dept is None:
            raise BadRequestError(message="Department not found.")

    if data.get("pension_provider_id") is not None:
        from app.models.all_models import PensionProvider as _PP
        pv = (
            db.query(_PP)
            .filter(_PP.id == data["pension_provider_id"], _PP.is_deleted.is_(False))
            .first()
        )
        if pv is None:
            raise BadRequestError(message="Pension provider not found.")

    if data.get("supervisor_staff_id") is not None:
        if data["supervisor_staff_id"] == staff_profile_id:
            raise BadRequestError(message="A staff member cannot supervise themselves.")
        sup = (
            db.query(StaffProfile)
            .filter(StaffProfile.id == data["supervisor_staff_id"],
                    StaffProfile.is_deleted.is_(False))
            .first()
        )
        if sup is None:
            raise BadRequestError(message="Supervisor staff profile not found.")

    # Employment-status changes go through the audited transition service
    # (writes a StaffStatusHistory row and deactivates the user on exits).
    new_status = data.pop("employment_status", None)

    for f in (
        "job_title", "designation", "specialty", "department_id", "employment_type",
        "hire_date", "confirmation_date", "probation_end_date",
        "contract_start_date", "contract_end_date", "exit_date", "exit_reason",
        "supervisor_staff_id",
        "date_of_birth", "gender", "marital_status", "nationality",
        "address_line_1", "address_line_2", "city", "state_region", "country",
        "personal_email", "personal_phone",
        "next_of_kin_name", "next_of_kin_relationship", "next_of_kin_phone",
        "emergency_contact_name", "emergency_contact_phone",
        "bank_name", "bank_account_no", "bank_account_name",
        "tax_id", "pension_pin", "pension_provider_id", "nhf_no",
    ):
        if f in data:
            setattr(sp, f, data[f])

    # Compensation: any base/grade/step/currency/allowance/deduction change
    # writes a fresh versioned StaffSalary record (closing the prior one) so
    # the complete salary STRUCTURE is captured and the pay history is kept.
    salary_fields = (
        "base_salary_amount", "salary_currency", "salary_grade_id",
        "salary_step_id", "allowances", "deductions",
    )
    salary_touched = any(f in data for f in salary_fields)

    if salary_touched:
        # Prior active salary is the source we carry forward from when the
        # caller changes only part of the structure (e.g. adds an allowance
        # without re-stating the base amount).
        current = (
            db.query(StaffSalary)
            .filter(
                StaffSalary.staff_profile_id == sp.id,
                StaffSalary.is_active.is_(True),
                StaffSalary.is_deleted.is_(False),
            )
            .order_by(StaffSalary.effective_from.desc())
            .first()
        )

        base = data.get("base_salary_amount")
        if base is None:
            base = current.base_amount if current else sp.base_salary_amount
        if base is None:
            raise BadRequestError(
                message="A base salary is required before a salary structure can be set."
            )

        allowances = data["allowances"] if "allowances" in data else (
            current.allowances if current else None
        )
        deductions = data["deductions"] if "deductions" in data else (
            current.deductions if current else None
        )
        grade_id = data.get("salary_grade_id")
        if grade_id is None and current is not None:
            grade_id = current.grade_id
        step_id = data.get("salary_step_id")
        if step_id is None and current is not None:
            step_id = current.step_id
        currency = (
            data.get("salary_currency")
            or (current.currency if current else None)
            or sp.salary_currency
            or "NGN"
        )

        PayrollService(db).set_staff_salary(
            staff_profile_id=sp.id,
            base_amount=base,
            grade_id=grade_id,
            step_id=step_id,
            currency=currency,
            allowances=allowances,
            deductions=deductions,
            effective_from=data.get("salary_effective_from") or date.today(),
        )
    else:
        # Pure non-salary update — persist the profile field changes above.
        db.commit()

    if new_status is not None and new_status != sp.employment_status:
        StaffOnboardingService(db).transition_status(
            sp.id, to_status=new_status, reason="Updated from HR staff records"
        )

    db.refresh(sp)
    return _ok(sp)


@router.post(
    "/payroll/runs/{run_id}/pay",
    summary="Mark an approved payroll run as paid (settles loans + overtime)",
)
def pay_payroll(
    run_id: int,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _run_out(
        PayrollService(db).mark_paid(run_id, actor_user_id=getattr(actor, "id", None))
    )


# ---------------------------------------------------------------------------
# Payroll one-off inputs (bonus / arrears / 13th month / ad-hoc deductions)
# ---------------------------------------------------------------------------


class OneOffCreateSchema(BaseModel):
    staff_profile_id: int
    kind: str = Field("BONUS", description="BONUS | ARREARS | THIRTEENTH_MONTH | OTHER_EARNING | OTHER_DEDUCTION")
    amount: float = Field(..., gt=0)
    is_taxable: bool = True
    note: Optional[str] = Field(None, max_length=255)


_ONEOFF_KINDS = {"BONUS", "ARREARS", "THIRTEENTH_MONTH", "OTHER_EARNING", "OTHER_DEDUCTION"}


@router.post("/payroll/runs/{run_id}/one-offs", summary="Add a one-off earning/deduction to a run")
def add_one_off(run_id: int, payload: OneOffCreateSchema, actor: AdminUser,
                db: Annotated[Session, Depends(get_db)]):
    from app.models.all_models import PayrollOneOff, PayrollRun
    run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    if run is None:
        raise NotFoundError(message="Payroll run not found.")
    if run.status not in (PayrollRunStatus.DRAFT, PayrollRunStatus.CALCULATED):
        raise BadRequestError(message="One-offs can only be added before approval; recalculate afterwards.")
    kind = payload.kind.strip().upper()
    if kind not in _ONEOFF_KINDS:
        raise BadRequestError(message=f"kind must be one of {sorted(_ONEOFF_KINDS)}.")
    oo = PayrollOneOff(payroll_run_id=run_id, staff_profile_id=payload.staff_profile_id,
                       kind=kind, amount=Decimal(str(payload.amount)),
                       is_taxable=payload.is_taxable, note=payload.note)
    db.add(oo)
    db.commit()
    db.refresh(oo)
    return {"success": True, "one_off": {"id": oo.id, "staff_profile_id": oo.staff_profile_id,
                                          "kind": oo.kind, "amount": str(oo.amount),
                                          "is_taxable": oo.is_taxable, "note": oo.note}}


@router.get("/payroll/runs/{run_id}/one-offs", summary="List one-offs on a run")
def list_one_offs(run_id: int, actor: AdminUser, db: Annotated[Session, Depends(get_db)]):
    from app.models.all_models import PayrollOneOff, StaffProfile
    rows = (db.query(PayrollOneOff, StaffProfile)
            .join(StaffProfile, StaffProfile.id == PayrollOneOff.staff_profile_id)
            .filter(PayrollOneOff.payroll_run_id == run_id,
                    PayrollOneOff.is_deleted.is_(False)).all())
    items = []
    for oo, sp in rows:
        items.append({"id": oo.id, "staff_profile_id": oo.staff_profile_id,
                      "staff_no": sp.staff_no, "kind": oo.kind, "amount": str(oo.amount),
                      "is_taxable": oo.is_taxable, "note": oo.note})
    return {"success": True, "items": items}


@router.delete("/payroll/one-offs/{one_off_id}", summary="Remove a one-off")
def delete_one_off(one_off_id: int, actor: AdminUser, db: Annotated[Session, Depends(get_db)]):
    from app.models.all_models import PayrollOneOff
    oo = db.query(PayrollOneOff).filter(PayrollOneOff.id == one_off_id).first()
    if oo is None:
        raise NotFoundError(message="One-off not found.")
    oo.is_deleted = True
    db.commit()
    return {"success": True, "deleted": one_off_id}


# ---------------------------------------------------------------------------
# Payroll documents: payslip PDF, bank + statutory remittance schedules
# ---------------------------------------------------------------------------


def _payroll_export_rows(db: Session, run_id: int) -> tuple:
    from app.models.all_models import (
        PayrollLine, PayrollRun, PensionProvider, StaffProfile, User as _User,
    )
    run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
    if run is None:
        raise NotFoundError(message="Payroll run not found.")
    rows = (db.query(PayrollLine, StaffProfile)
            .join(StaffProfile, StaffProfile.id == PayrollLine.staff_profile_id)
            .filter(PayrollLine.payroll_run_id == run_id,
                    PayrollLine.is_deleted.is_(False)).all())
    providers = {
        p.id: p for p in db.query(PensionProvider)
        .filter(PensionProvider.is_deleted.is_(False)).all()
    }
    # Batch-load users once — a per-line query multiplies round-trips and
    # ORM object churn on large runs.
    user_ids = {sp.user_id for _, sp in rows if sp.user_id}
    users = (
        {u.id: u for u in db.query(_User).filter(_User.id.in_(user_ids)).all()}
        if user_ids else {}
    )
    out = []
    for line, sp in rows:
        user = users.get(sp.user_id) if sp.user_id else None
        name = " ".join(x for x in [getattr(user, "first_name", None) or "",
                                    getattr(user, "last_name", None) or ""] if x).strip()             or getattr(user, "username", None) or sp.staff_no
        bd = line.breakdown_json or {}
        out.append({
            "staff_number": sp.staff_no, "staff_name": name,
            "bank_name": sp.bank_name, "bank_account_no": sp.bank_account_no,
            "bank_account_name": sp.bank_account_name or name,
            "tax_id": sp.tax_id, "pension_pin": sp.pension_pin, "nhf_number": sp.nhf_no,
            "base_salary": line.base_salary, "net_pay": line.net_pay,
            "gross_pay": line.gross_pay,
            "paye_amount": line.paye_amount, "pension_amount": line.pension_amount,
            "pension_employer": bd.get("pension_employer"),
            "nsitf_employer": bd.get("nsitf_employer"),
            "pension_provider": (
                providers[sp.pension_provider_id].name
                if sp.pension_provider_id in providers else None
            ),
            "pension_provider_code": (
                providers[sp.pension_provider_id].code
                if sp.pension_provider_id in providers else None
            ),
            "pfa_license_no": (
                providers[sp.pension_provider_id].pfa_license_no
                if sp.pension_provider_id in providers else None
            ),
            "taxable_gross": bd.get("taxable_gross"), "nhf_amount": line.nhf_amount,
            "line": line, "staff": sp, "user": user,
        })
    return run, out


def _csv_response(content: bytes, filename: str):
    from fastapi import Response
    return Response(content=content, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/payroll/runs/{run_id}/exports/bank-schedule", summary="Bank transfer schedule (CSV)")
def bank_schedule(run_id: int, actor: AdminUser, db: Annotated[Session, Depends(get_db)]):
    from app.utils.payroll_docs import bank_schedule_csv
    run, rows = _payroll_export_rows(db, run_id)
    return _csv_response(bank_schedule_csv(rows), f"bank-schedule-{run.code}.csv")


@router.get("/payroll/runs/{run_id}/exports/paye", summary="PAYE remittance schedule (CSV)")
def paye_schedule(run_id: int, actor: AdminUser, db: Annotated[Session, Depends(get_db)]):
    from app.utils.payroll_docs import paye_schedule_csv
    run, rows = _payroll_export_rows(db, run_id)
    return _csv_response(paye_schedule_csv(rows), f"paye-schedule-{run.code}.csv")


@router.get("/payroll/runs/{run_id}/exports/pension", summary="Pension remittance schedule (CSV)")
def pension_schedule(run_id: int, actor: AdminUser, db: Annotated[Session, Depends(get_db)]):
    from app.utils.payroll_docs import pension_schedule_csv
    run, rows = _payroll_export_rows(db, run_id)
    return _csv_response(pension_schedule_csv(rows), f"pension-schedule-{run.code}.csv")


@router.get("/payroll/runs/{run_id}/exports/nhf", summary="NHF remittance schedule (CSV)")
def nhf_schedule(run_id: int, actor: AdminUser, db: Annotated[Session, Depends(get_db)]):
    from app.utils.payroll_docs import nhf_schedule_csv
    run, rows = _payroll_export_rows(db, run_id)
    return _csv_response(nhf_schedule_csv(rows), f"nhf-schedule-{run.code}.csv")


@router.get("/payroll/runs/{run_id}/exports/nsitf", summary="NSITF remittance schedule (CSV, employer 1%)")
def nsitf_schedule(run_id: int, actor: AdminUser, db: Annotated[Session, Depends(get_db)]):
    from app.utils.payroll_docs import nsitf_schedule_csv
    run, rows = _payroll_export_rows(db, run_id)
    return _csv_response(nsitf_schedule_csv(rows), f"nsitf-schedule-{run.code}.csv")


def _load_tenant_logo_path(db: Session) -> Optional[str]:
    """Best-effort: resolve the tenant's branding logo (TenantSetting.logo_url)
    to a temp PNG path for PDF rendering. Handles data URIs, http(s) URLs,
    /uploads paths and plain filesystem paths. Returns None when unavailable."""
    import base64
    import io as _io
    import os as _os
    import tempfile
    from urllib.parse import urlparse

    try:
        from app.models.all_models import TenantSetting
        setting = db.query(TenantSetting).filter(TenantSetting.is_deleted.is_(False)).first()
        url = getattr(setting, "logo_url", None) if setting else None
        if not url:
            return None
        u = str(url).strip()
        raw: Optional[bytes] = None
        if u.startswith("data:"):
            raw = base64.b64decode(u.split(",", 1)[1]) if "," in u else None
        elif u.startswith("http://") or u.startswith("https://"):
            import httpx
            resp = httpx.get(u, timeout=6.0, follow_redirects=True)
            if resp.status_code < 400:
                raw = resp.content
        elif u.startswith("file://"):
            with open(urlparse(u).path, "rb") as fh:
                raw = fh.read()
        elif u.startswith("/uploads/"):
            from app.core.config import settings as _settings
            base = getattr(_settings, "UPLOADS_DIR", None) or _os.path.join(_os.getcwd(), "uploads")
            local = _os.path.join(base, u[len("/uploads/"):])
            if _os.path.exists(local):
                with open(local, "rb") as fh:
                    raw = fh.read()
        elif _os.path.exists(u):
            with open(u, "rb") as fh:
                raw = fh.read()
        if not raw:
            return None
        from PIL import Image
        img = Image.open(_io.BytesIO(raw)).convert("RGBA")
        img.thumbnail((400, 400))
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        fd, path = tempfile.mkstemp(suffix=".png", prefix="paysliplogo_")
        _os.close(fd)
        bg.save(path, format="PNG")
        return path
    except Exception:
        return None


@router.get("/payroll/lines/{line_id}/payslip", summary="Payslip PDF for one staff member")
def payslip_pdf(line_id: int, actor: AdminUser, db: Annotated[Session, Depends(get_db)]):
    from fastapi import Response
    from app.models.all_models import Department, PayrollLine, PayrollRun, StaffProfile, User as _User
    from app.utils.payroll_docs import build_payslip_pdf
    from app.core.multitenancy import get_current_tenant

    line = db.query(PayrollLine).filter(PayrollLine.id == line_id,
                                        PayrollLine.is_deleted.is_(False)).first()
    if line is None:
        raise NotFoundError(message="Payroll line not found.")
    run = db.query(PayrollRun).filter(PayrollRun.id == line.payroll_run_id).first()
    sp = db.query(StaffProfile).filter(StaffProfile.id == line.staff_profile_id).first()
    user = db.query(_User).filter(_User.id == sp.user_id).first() if sp and sp.user_id else None
    dept = db.query(Department).filter(Department.id == sp.department_id).first()         if sp and sp.department_id else None

    name = " ".join(x for x in [getattr(user, "first_name", None) or "",
                                getattr(user, "last_name", None) or ""] if x).strip()         or getattr(user, "username", None) or (sp.staff_no if sp else "Staff")
    hospital = "Hospital"
    try:
        tenant = get_current_tenant()
        if tenant and getattr(tenant, "name", None):
            hospital = tenant.name
    except Exception:
        pass

    logo_path = _load_tenant_logo_path(db)
    try:
        pdf_bytes = build_payslip_pdf(
            hospital_name=hospital, staff_name=name,
            staff_number=sp.staff_no if sp else None,
            department=dept.name if dept else None,
            period_label=f"{run.period_start} – {run.period_end}" if run else "",
            logo_path=logo_path,
            line={
                "base_salary": line.base_salary, "overtime_amount": line.overtime_amount,
                "gross_pay": line.gross_pay, "paye_amount": line.paye_amount,
                "pension_amount": line.pension_amount, "nhf_amount": line.nhf_amount,
                "loan_repayment_amount": line.loan_repayment_amount,
                "other_deductions": line.other_deductions,
                "total_deductions": line.total_deductions, "net_pay": line.net_pay,
                "breakdown_json": line.breakdown_json,
            })
    finally:
        if logo_path:
            try:
                import os as _os
                _os.remove(logo_path)
            except OSError:
                pass
    safe = "".join(ch for ch in ((sp.staff_no if sp else "payslip")) if ch.isalnum() or ch in "-_")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="payslip-{safe}.pdf"'})


# ===========================================================================
# Tasks / announcements / incidents / requests / appraisals / training
# ===========================================================================


class StaffTaskCreateSchema(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to_staff_id: Optional[int] = None
    related_patient_id: Optional[int] = None
    department_id: Optional[int] = None
    facility_id: Optional[int] = None
    priority: StaffTaskPriority = StaffTaskPriority.MEDIUM
    due_date: Optional[datetime] = None


@router.post(
    "/tasks",
    summary="Assign a staff task",
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    payload: StaffTaskCreateSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = StaffTask(assigned_by_user_id=getattr(actor, "id", None), **payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


@router.get("/tasks", summary="List staff tasks")
def list_tasks(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    assigned_to_staff_id: Optional[int] = None,
    task_status: Optional[StaffTaskStatus] = None,
):
    q = db.query(StaffTask).filter(StaffTask.is_deleted.is_(False))
    if assigned_to_staff_id is not None:
        q = q.filter(StaffTask.assigned_to_staff_id == assigned_to_staff_id)
    if task_status is not None:
        q = q.filter(StaffTask.status == task_status)
    return [_ok(r) for r in q.order_by(StaffTask.id.desc()).limit(500).all()]


class StaffAnnouncementSchema(BaseModel):
    title: str
    body: str
    audience: Optional[str] = None
    facility_id: Optional[int] = None
    department_id: Optional[int] = None
    role_codes: Optional[list[str]] = None
    channels: Optional[list[str]] = None
    is_pinned: bool = False


@router.post(
    "/announcements",
    summary="Send an announcement",
    status_code=status.HTTP_201_CREATED,
)
def send_announcement(
    payload: StaffAnnouncementSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = StaffAnnouncement(
        sent_by_user_id=getattr(actor, "id", None),
        sent_at=datetime.utcnow(),
        **payload.model_dump(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


@router.get("/announcements", summary="List announcements")
def list_announcements(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    return [_ok(r) for r in db.query(StaffAnnouncement).filter(StaffAnnouncement.is_deleted.is_(False)).order_by(StaffAnnouncement.id.desc()).all()]


class IncidentCreateSchema(BaseModel):
    staff_profile_id: int
    title: str
    description: str
    severity: StaffIncidentSeverity = StaffIncidentSeverity.LOW
    occurred_on: Optional[date] = None
    confidential_notes: Optional[str] = None


@router.post(
    "/incidents",
    summary="Record a staff incident",
    status_code=status.HTTP_201_CREATED,
)
def create_incident(
    payload: IncidentCreateSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    data = payload.model_dump()
    if data.get("occurred_on") is None:
        data["occurred_on"] = date.today()
    rec = StaffIncident(reported_by_user_id=getattr(actor, "id", None), **data)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


class DisciplinaryActionSchema(BaseModel):
    incident_id: int
    staff_profile_id: int
    kind: DisciplinaryActionKind = DisciplinaryActionKind.WRITTEN_WARNING
    issued_on: Optional[date] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    note: Optional[str] = None


@router.post(
    "/incidents/actions",
    summary="Record a disciplinary action",
    status_code=status.HTTP_201_CREATED,
)
def create_disciplinary_action(
    payload: DisciplinaryActionSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    data = payload.model_dump()
    if data.get("issued_on") is None:
        data["issued_on"] = date.today()
    rec = DisciplinaryActionRecord(issued_by_user_id=getattr(actor, "id", None), **data)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


class StaffRequestCreateSchema(BaseModel):
    staff_profile_id: int
    request_type: StaffRequestType = StaffRequestType.OTHER
    title: str
    description: Optional[str] = None
    payload: Optional[dict] = None


@router.post(
    "/requests",
    summary="Submit a generic staff request",
    status_code=status.HTTP_201_CREATED,
)
def create_staff_request(
    payload: StaffRequestCreateSchema,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = StaffRequest(
        status=StaffRequestStatus.PENDING,
        submitted_at=datetime.utcnow(),
        **payload.model_dump(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


class RequestDecisionSchema(BaseModel):
    approve: bool
    note: Optional[str] = None


@router.post(
    "/requests/{request_id}/decide",
    summary="Approve / reject a staff request",
)
def decide_staff_request(
    request_id: int,
    payload: RequestDecisionSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = db.query(StaffRequest).filter(StaffRequest.id == request_id).first()
    if rec is None:
        return {}
    rec.status = StaffRequestStatus.APPROVED if payload.approve else StaffRequestStatus.REJECTED
    rec.decided_at = datetime.utcnow()
    rec.decided_by_user_id = getattr(actor, "id", None)
    rec.decision_note = payload.note
    db.commit()
    db.refresh(rec)
    return _ok(rec)


class AppraisalCycleSchema(BaseModel):
    name: str
    period_start: date
    period_end: date
    self_assessment_due_on: Optional[date] = None
    supervisor_review_due_on: Optional[date] = None
    moderation_due_on: Optional[date] = None


@router.post(
    "/appraisals/cycles",
    summary="Create an appraisal cycle",
    status_code=status.HTTP_201_CREATED,
)
def create_appraisal_cycle(
    payload: AppraisalCycleSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = AppraisalCycle(**payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


class TrainingRecordSchema(BaseModel):
    staff_profile_id: int
    title: str
    completed_on: Optional[date] = None
    expires_on: Optional[date] = None
    certificate_no: Optional[str] = None
    issuing_body: Optional[str] = None
    score: Optional[Decimal] = None
    document_id: Optional[int] = None


@router.post(
    "/training/records",
    summary="Record a completed training",
    status_code=status.HTTP_201_CREATED,
)
def create_training_record(
    payload: TrainingRecordSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = TrainingRecord(**payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


# ===========================================================================
# Reports + audit
# ===========================================================================


@router.get(
    "/reports/headcount",
    summary="Headcount summary by department / facility / employment status",
)
def headcount_report(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    from sqlalchemy import func

    rows = (
        db.query(
            StaffProfile.department_id,
            StaffProfile.facility_id,
            StaffProfile.employment_status,
            func.count(StaffProfile.id).label("count"),
        )
        .filter(StaffProfile.is_deleted.is_(False))
        .group_by(
            StaffProfile.department_id,
            StaffProfile.facility_id,
            StaffProfile.employment_status,
        )
        .all()
    )
    return [
        {
            "department_id": r.department_id,
            "facility_id": r.facility_id,
            "employment_status": str(getattr(r.employment_status, "value", r.employment_status)),
            "count": int(r.count),
        }
        for r in rows
    ]


@router.get(
    "/audit-log",
    summary="Read the staff audit log",
)
def list_audit_log(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    entity: Optional[str] = None,
    entity_id: Optional[int] = None,
):
    q = db.query(StaffAuditLog).filter(StaffAuditLog.is_deleted.is_(False))
    if entity is not None:
        q = q.filter(StaffAuditLog.entity == entity)
    if entity_id is not None:
        q = q.filter(StaffAuditLog.entity_id == entity_id)
    return [_ok(r) for r in q.order_by(StaffAuditLog.occurred_at.desc()).limit(500).all()]
