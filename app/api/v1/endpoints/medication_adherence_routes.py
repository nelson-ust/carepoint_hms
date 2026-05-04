"""
Medication-adherence endpoints.

Three audiences:

* **Clinicians / pharmacists** — list profiles, create schedules,
  read alerts, assign follow-ups.
* **Patients (self-service)** — list their own doses, confirm intake.
* **Schedulers / batch jobs** — generate doses, sweep refills.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser
from app.core.enums import (
    AdherenceLevel,
    FollowUpTaskStatus,
    MedicationDoseStatus,
    MedicationFrequency,
    MedicationScheduleStatus,
    RefillStatus,
)
from app.models.all_models import (
    AdherenceAlert,
    AdherenceSnapshot,
    FollowUpTask,
    MedicationDose,
    MedicationProfile,
    MedicationReminderPreference,
    MedicationSchedule,
    RefillRecord,
)
from app.services.medication_adherence_service import MedicationAdherenceService


router = APIRouter(
    prefix="/medication-adherence",
    tags=["Medication Adherence"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ProfileReadSchema(BaseModel):
    id: int
    patient_id: int
    drug_id: Optional[int] = None
    drug_name_snapshot: str
    prescription_id: Optional[int] = None
    prescription_item_id: Optional[int] = None
    consultation_id: Optional[int] = None
    diagnosis_id: Optional[int] = None
    prescribing_doctor_id: Optional[int] = None
    dosage: Optional[str] = None
    frequency_code: Optional[str] = None
    route: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None
    started_on: Optional[date] = None
    ended_on: Optional[date] = None
    is_active: bool
    is_high_risk: bool
    discontinued_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ScheduleCreateSchema(BaseModel):
    medication_profile_id: int
    frequency: MedicationFrequency = MedicationFrequency.DAILY
    start_date: date
    end_date: Optional[date] = None
    custom_times: Optional[list[str]] = None
    interval_hours: Optional[int] = None
    timezone_name: Optional[str] = None
    refill_due_date: Optional[date] = None
    review_date: Optional[date] = None
    notes: Optional[str] = None


class ScheduleReadSchema(BaseModel):
    id: int
    medication_profile_id: int
    patient_id: int
    frequency: MedicationFrequency
    custom_times: Optional[list[str]] = None
    interval_hours: Optional[int] = None
    timezone: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    refill_due_date: Optional[date] = None
    review_date: Optional[date] = None
    status: MedicationScheduleStatus
    last_generated_through: Optional[date] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DoseReadSchema(BaseModel):
    id: int
    schedule_id: int
    patient_id: int
    scheduled_for: datetime
    window_minutes: int
    status: MedicationDoseStatus
    taken_at: Optional[datetime] = None
    confirmation_source: Optional[str] = None
    miss_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DoseConfirmSchema(BaseModel):
    status: MedicationDoseStatus
    miss_reason: Optional[str] = None
    taken_at: Optional[datetime] = None
    source: Optional[str] = "PATIENT_PORTAL"


class ReminderPreferenceSchema(BaseModel):
    enabled: bool = True
    channel_in_app: bool = True
    channel_email: bool = False
    channel_sms: bool = True
    channel_whatsapp: bool = False
    channel_push: bool = False
    advance_minutes: int = Field(15, ge=0, le=1440)
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


class AdherenceComputeSchema(BaseModel):
    patient_id: int
    schedule_id: Optional[int] = None
    period_start: date
    period_end: date


class AdherenceSnapshotReadSchema(BaseModel):
    id: int
    patient_id: int
    schedule_id: Optional[int] = None
    period_start: date
    period_end: date
    doses_scheduled: int
    doses_taken: int
    doses_missed: int
    doses_skipped: int
    doses_delayed: int
    adherence_pct: Decimal
    level: AdherenceLevel

    model_config = ConfigDict(from_attributes=True)


class AlertReadSchema(BaseModel):
    id: int
    patient_id: int
    schedule_id: Optional[int] = None
    severity: str
    title: str
    message: Optional[str] = None
    triggered_at: datetime
    is_acknowledged: bool

    model_config = ConfigDict(from_attributes=True)


class FollowUpCreateSchema(BaseModel):
    patient_id: int
    schedule_id: Optional[int] = None
    alert_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    assigned_to_user_id: Optional[int] = None
    assigned_role: Optional[str] = None


class FollowUpReadSchema(BaseModel):
    id: int
    patient_id: int
    schedule_id: Optional[int] = None
    alert_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    status: FollowUpTaskStatus
    assigned_to_user_id: Optional[int] = None
    outcome_notes: Optional[str] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


def _service(db: Annotated[Session, Depends(get_db)]) -> MedicationAdherenceService:
    return MedicationAdherenceService(db)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


@router.get(
    "/profiles",
    response_model=list[ProfileReadSchema],
    summary="List medication profiles",
)
def list_profiles(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    patient_id: Optional[int] = None,
    only_active: bool = False,
):
    q = db.query(MedicationProfile).filter(MedicationProfile.is_deleted.is_(False))
    if patient_id is not None:
        q = q.filter(MedicationProfile.patient_id == patient_id)
    if only_active:
        q = q.filter(MedicationProfile.is_active.is_(True))
    return q.order_by(MedicationProfile.id.desc()).all()


@router.post(
    "/profiles/from-prescription/{prescription_id}",
    response_model=list[ProfileReadSchema],
    status_code=status.HTTP_201_CREATED,
    summary="Materialise profile entries from a prescription",
)
def materialise_profile(
    prescription_id: int,
    _: CurrentActiveUser,
    service: Annotated[MedicationAdherenceService, Depends(_service)],
):
    return service.materialise_profile_from_prescription(prescription_id)


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


@router.post(
    "/schedules",
    response_model=ScheduleReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a medication schedule",
)
def create_schedule(
    payload: ScheduleCreateSchema,
    _: CurrentActiveUser,
    service: Annotated[MedicationAdherenceService, Depends(_service)],
):
    return service.create_schedule(
        medication_profile_id=payload.medication_profile_id,
        frequency=payload.frequency,
        start_date=payload.start_date,
        end_date=payload.end_date,
        custom_times=payload.custom_times,
        interval_hours=payload.interval_hours,
        timezone_name=payload.timezone_name,
        refill_due_date=payload.refill_due_date,
        review_date=payload.review_date,
        notes=payload.notes,
    )


@router.get(
    "/schedules",
    response_model=list[ScheduleReadSchema],
    summary="List medication schedules",
)
def list_schedules(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    patient_id: Optional[int] = None,
    schedule_status: Optional[MedicationScheduleStatus] = None,
):
    q = db.query(MedicationSchedule).filter(MedicationSchedule.is_deleted.is_(False))
    if patient_id is not None:
        q = q.filter(MedicationSchedule.patient_id == patient_id)
    if schedule_status is not None:
        q = q.filter(MedicationSchedule.status == schedule_status)
    return q.order_by(MedicationSchedule.id.desc()).all()


@router.post(
    "/schedules/{schedule_id}/generate-doses",
    summary="Materialise dose rows for a schedule up to a horizon",
)
def generate_doses(
    schedule_id: int,
    through: date,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[MedicationAdherenceService, Depends(_service)],
):
    sched = db.query(MedicationSchedule).filter(MedicationSchedule.id == schedule_id).first()
    if sched is None:
        return {"created": 0}
    return {"created": service.generate_doses(sched, through=through)}


# ---------------------------------------------------------------------------
# Doses
# ---------------------------------------------------------------------------


@router.get(
    "/doses",
    response_model=list[DoseReadSchema],
    summary="List medication doses",
)
def list_doses(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    patient_id: Optional[int] = None,
    schedule_id: Optional[int] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    dose_status: Optional[MedicationDoseStatus] = None,
):
    q = db.query(MedicationDose).filter(MedicationDose.is_deleted.is_(False))
    if patient_id is not None:
        q = q.filter(MedicationDose.patient_id == patient_id)
    if schedule_id is not None:
        q = q.filter(MedicationDose.schedule_id == schedule_id)
    if from_date is not None:
        q = q.filter(MedicationDose.scheduled_for >= datetime.combine(from_date, datetime.min.time()))
    if to_date is not None:
        q = q.filter(MedicationDose.scheduled_for <= datetime.combine(to_date, datetime.max.time()))
    if dose_status is not None:
        q = q.filter(MedicationDose.status == dose_status)
    return q.order_by(MedicationDose.scheduled_for.desc()).limit(500).all()


@router.post(
    "/doses/{dose_id}/confirm",
    response_model=DoseReadSchema,
    summary="Confirm intake (taken / missed / skipped / delayed / stopped)",
)
def confirm_dose(
    dose_id: int,
    payload: DoseConfirmSchema,
    actor: CurrentActiveUser,
    service: Annotated[MedicationAdherenceService, Depends(_service)],
):
    return service.confirm_dose(
        dose_id,
        status=payload.status,
        confirmed_by_user_id=getattr(actor, "id", None),
        source=payload.source,
        miss_reason=payload.miss_reason,
        taken_at=payload.taken_at,
    )


# ---------------------------------------------------------------------------
# Reminder preferences
# ---------------------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/reminder-preferences",
    response_model=ReminderPreferenceSchema,
    summary="Read reminder preferences for a patient",
)
def read_reminder_prefs(
    patient_id: int,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = (
        db.query(MedicationReminderPreference)
        .filter(MedicationReminderPreference.patient_id == patient_id)
        .first()
    )
    if rec is None:
        return ReminderPreferenceSchema()
    return ReminderPreferenceSchema(
        enabled=rec.enabled,
        channel_in_app=rec.channel_in_app,
        channel_email=rec.channel_email,
        channel_sms=rec.channel_sms,
        channel_whatsapp=rec.channel_whatsapp,
        channel_push=rec.channel_push,
        advance_minutes=rec.advance_minutes,
        quiet_hours_start=rec.quiet_hours_start,
        quiet_hours_end=rec.quiet_hours_end,
    )


@router.put(
    "/patients/{patient_id}/reminder-preferences",
    response_model=ReminderPreferenceSchema,
    summary="Update reminder preferences for a patient",
)
def update_reminder_prefs(
    patient_id: int,
    payload: ReminderPreferenceSchema,
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = (
        db.query(MedicationReminderPreference)
        .filter(MedicationReminderPreference.patient_id == patient_id)
        .first()
    )
    if rec is None:
        rec = MedicationReminderPreference(patient_id=patient_id)
        db.add(rec)
    for f, v in payload.model_dump().items():
        setattr(rec, f, v)
    db.commit()
    db.refresh(rec)
    return payload


# ---------------------------------------------------------------------------
# Adherence rollup
# ---------------------------------------------------------------------------


@router.post(
    "/adherence/compute",
    response_model=AdherenceSnapshotReadSchema,
    summary="Compute and persist an adherence snapshot",
)
def compute_adherence(
    payload: AdherenceComputeSchema,
    _: AdminUser,
    service: Annotated[MedicationAdherenceService, Depends(_service)],
):
    snap = service.compute_adherence(
        patient_id=payload.patient_id,
        schedule_id=payload.schedule_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
    )
    service.raise_alert_if_needed(snap)
    return snap


@router.get(
    "/adherence/snapshots",
    response_model=list[AdherenceSnapshotReadSchema],
    summary="List adherence snapshots",
)
def list_snapshots(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    patient_id: Optional[int] = None,
    level: Optional[AdherenceLevel] = None,
):
    q = db.query(AdherenceSnapshot).filter(AdherenceSnapshot.is_deleted.is_(False))
    if patient_id is not None:
        q = q.filter(AdherenceSnapshot.patient_id == patient_id)
    if level is not None:
        q = q.filter(AdherenceSnapshot.level == level)
    return q.order_by(AdherenceSnapshot.id.desc()).limit(500).all()


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=list[AlertReadSchema],
    summary="List adherence alerts",
)
def list_alerts(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    patient_id: Optional[int] = None,
    only_unacknowledged: bool = True,
):
    q = db.query(AdherenceAlert).filter(AdherenceAlert.is_deleted.is_(False))
    if patient_id is not None:
        q = q.filter(AdherenceAlert.patient_id == patient_id)
    if only_unacknowledged:
        q = q.filter(AdherenceAlert.is_acknowledged.is_(False))
    return q.order_by(AdherenceAlert.triggered_at.desc()).all()


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertReadSchema,
    summary="Acknowledge an alert",
)
def acknowledge_alert(
    alert_id: int,
    actor: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = db.query(AdherenceAlert).filter(AdherenceAlert.id == alert_id).first()
    if rec is None:
        return {}
    rec.is_acknowledged = True
    rec.acknowledged_by_user_id = getattr(actor, "id", None)
    rec.acknowledged_at = datetime.utcnow()
    db.commit()
    db.refresh(rec)
    return rec


# ---------------------------------------------------------------------------
# Refills
# ---------------------------------------------------------------------------


@router.get(
    "/refills",
    summary="List refill records",
)
def list_refills(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    patient_id: Optional[int] = None,
    refill_status: Optional[RefillStatus] = None,
):
    q = db.query(RefillRecord).filter(RefillRecord.is_deleted.is_(False))
    if patient_id is not None:
        q = q.filter(RefillRecord.patient_id == patient_id)
    if refill_status is not None:
        q = q.filter(RefillRecord.status == refill_status)
    return q.order_by(RefillRecord.due_date.asc()).all()


@router.post(
    "/refills/sweep-overdue",
    summary="Flip due refills to OVERDUE",
)
def sweep_refills(
    _: AdminUser,
    service: Annotated[MedicationAdherenceService, Depends(_service)],
):
    return {"marked_overdue": service.sweep_overdue_refills()}


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------


@router.post(
    "/follow-ups",
    response_model=FollowUpReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a follow-up task",
)
def create_follow_up(
    payload: FollowUpCreateSchema,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    rec = FollowUpTask(
        patient_id=payload.patient_id,
        schedule_id=payload.schedule_id,
        alert_id=payload.alert_id,
        assigned_to_user_id=payload.assigned_to_user_id,
        assigned_role=payload.assigned_role,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
        status=FollowUpTaskStatus.OPEN,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.get(
    "/follow-ups",
    response_model=list[FollowUpReadSchema],
    summary="List follow-up tasks",
)
def list_follow_ups(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    patient_id: Optional[int] = None,
    task_status: Optional[FollowUpTaskStatus] = None,
    assigned_to_user_id: Optional[int] = None,
):
    q = db.query(FollowUpTask).filter(FollowUpTask.is_deleted.is_(False))
    if patient_id is not None:
        q = q.filter(FollowUpTask.patient_id == patient_id)
    if task_status is not None:
        q = q.filter(FollowUpTask.status == task_status)
    if assigned_to_user_id is not None:
        q = q.filter(FollowUpTask.assigned_to_user_id == assigned_to_user_id)
    return q.order_by(FollowUpTask.id.desc()).all()


@router.post(
    "/follow-ups/{task_id}/complete",
    response_model=FollowUpReadSchema,
    summary="Close a follow-up task",
)
def complete_follow_up(
    task_id: int,
    outcome_notes: Optional[str] = None,
    _: AdminUser = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
):
    rec = db.query(FollowUpTask).filter(FollowUpTask.id == task_id).first()
    if rec is None:
        return {}
    rec.status = FollowUpTaskStatus.COMPLETED
    rec.outcome_notes = outcome_notes
    rec.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(rec)
    return rec
