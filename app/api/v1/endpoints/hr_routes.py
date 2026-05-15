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
    LeaveStatus,
    LeaveTypeKind,
    OvertimeStatus,
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
    return _ok(PayrollService(db).create_run(**payload.model_dump()))


@router.post(
    "/payroll/runs/{run_id}/calculate",
    summary="Calculate payroll lines for the run",
)
def calculate_payroll(
    run_id: int,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(PayrollService(db).calculate(run_id))


@router.post(
    "/payroll/runs/{run_id}/approve",
    summary="Approve a calculated payroll run",
)
def approve_payroll(
    run_id: int,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(PayrollService(db).approve(run_id, approved_by_user_id=getattr(actor, "id", None) or 0))


@router.post(
    "/payroll/runs/{run_id}/lock",
    summary="Lock a payroll run + its timesheets",
)
def lock_payroll(
    run_id: int,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return _ok(PayrollService(db).lock(run_id))


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
    return [_ok(r) for r in q.order_by(PayrollRun.id.desc()).all()]


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
    rec = StaffSalary(**payload.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _ok(rec)


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
