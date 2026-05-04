"""
Medication adherence service.

Owns four flows:

1. **Profile + schedule materialisation** — when a Prescription is
   issued, an entry is added to :class:`MedicationProfile` and a
   :class:`MedicationSchedule` is created with the prescribed
   frequency.
2. **Dose generation** — every day the scheduler walks active
   schedules and materialises :class:`MedicationDose` rows for the
   coming horizon.
3. **Confirmation** — the patient (or a caregiver) flips a dose to
   TAKEN / MISSED / SKIPPED / DELAYED and may capture a reason.
4. **Adherence rollup + alerts** — a daily job aggregates dose
   outcomes per (patient, schedule, period) into
   :class:`AdherenceSnapshot` rows and emits :class:`AdherenceAlert`
   when adherence drops below a threshold or refills are overdue.

Reminders and clinician notifications go through the unified
:class:`NotificationDispatcher` so they automatically respect tenant
per-event channel routing and quiet hours.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    AdherenceAlertSeverity,
    AdherenceLevel,
    MedicationDoseStatus,
    MedicationFrequency,
    MedicationScheduleStatus,
    NotificationEvent,
    RefillStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    AdherenceAlert,
    AdherenceSnapshot,
    MedicationDose,
    MedicationProfile,
    MedicationSchedule,
    Prescription,
    PrescriptionItem,
    RefillRecord,
)


logger = logging.getLogger(__name__)


DEFAULT_FREQUENCY_TIMES: dict[MedicationFrequency, list[str]] = {
    MedicationFrequency.DAILY: ["08:00"],
    MedicationFrequency.TWICE_DAILY: ["08:00", "20:00"],
    MedicationFrequency.THREE_TIMES_DAILY: ["08:00", "14:00", "20:00"],
    MedicationFrequency.FOUR_TIMES_DAILY: ["08:00", "12:00", "16:00", "20:00"],
    MedicationFrequency.EVERY_4_HOURS: ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"],
    MedicationFrequency.EVERY_6_HOURS: ["00:00", "06:00", "12:00", "18:00"],
    MedicationFrequency.EVERY_8_HOURS: ["08:00", "16:00", "00:00"],
    MedicationFrequency.EVERY_12_HOURS: ["08:00", "20:00"],
    MedicationFrequency.WEEKLY: ["08:00"],
    MedicationFrequency.BIWEEKLY: ["08:00"],
    MedicationFrequency.MONTHLY: ["08:00"],
}


class MedicationAdherenceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # PROFILE / SCHEDULE
    # ------------------------------------------------------------------

    def materialise_profile_from_prescription(
        self, prescription_id: int
    ) -> list[MedicationProfile]:
        prescription = (
            self.db.query(Prescription)
            .filter(Prescription.id == prescription_id, Prescription.is_deleted.is_(False))
            .first()
        )
        if prescription is None:
            raise NotFoundError(message="Prescription not found.")

        items = (
            self.db.query(PrescriptionItem)
            .filter(
                PrescriptionItem.prescription_id == prescription.id,
                PrescriptionItem.is_deleted.is_(False),
            )
            .all()
        )

        out: list[MedicationProfile] = []
        for item in items:
            existing = (
                self.db.query(MedicationProfile)
                .filter(MedicationProfile.prescription_item_id == item.id)
                .first()
            )
            if existing is not None:
                out.append(existing)
                continue
            patient_id = (
                getattr(prescription, "patient_id", None)
                or getattr(item, "patient_id", None)
            )
            if not patient_id:
                continue
            profile = MedicationProfile(
                patient_id=patient_id,
                drug_id=getattr(item, "drug_id", None),
                drug_name_snapshot=getattr(item, "drug_name", None) or "Unknown",
                prescription_id=prescription.id,
                prescription_item_id=item.id,
                consultation_id=getattr(prescription, "consultation_id", None),
                prescribing_doctor_id=getattr(prescription, "prescribed_by_id", None),
                dosage=getattr(item, "dosage", None),
                frequency_code=getattr(item, "frequency", None),
                route=getattr(item, "route", None),
                duration=getattr(item, "duration", None),
                instructions=getattr(item, "instructions", None),
                started_on=(
                    getattr(prescription, "prescribed_at", datetime.utcnow()).date()
                    if getattr(prescription, "prescribed_at", None)
                    else None
                ),
                is_active=True,
            )
            self.db.add(profile)
            out.append(profile)

        self.db.commit()
        return out

    def create_schedule(
        self,
        *,
        medication_profile_id: int,
        frequency: MedicationFrequency,
        start_date: date,
        end_date: Optional[date] = None,
        custom_times: Optional[list[str]] = None,
        interval_hours: Optional[int] = None,
        timezone_name: Optional[str] = None,
        refill_due_date: Optional[date] = None,
        review_date: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> MedicationSchedule:
        profile = (
            self.db.query(MedicationProfile)
            .filter(MedicationProfile.id == medication_profile_id)
            .first()
        )
        if profile is None:
            raise NotFoundError(message="Medication profile not found.")

        if frequency == MedicationFrequency.CUSTOM and not custom_times:
            raise BadRequestError(message="custom_times is required when frequency is CUSTOM.")

        rec = MedicationSchedule(
            medication_profile_id=profile.id,
            patient_id=profile.patient_id,
            frequency=frequency,
            custom_times=custom_times,
            interval_hours=interval_hours,
            timezone=timezone_name,
            start_date=start_date,
            end_date=end_date,
            refill_due_date=refill_due_date,
            review_date=review_date,
            status=MedicationScheduleStatus.ACTIVE,
            notes=notes,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    # ------------------------------------------------------------------
    # DOSE GENERATION
    # ------------------------------------------------------------------

    def generate_doses(self, schedule: MedicationSchedule, *, through: date) -> int:
        if schedule.status != MedicationScheduleStatus.ACTIVE:
            return 0

        start = schedule.last_generated_through or schedule.start_date
        if start < schedule.start_date:
            start = schedule.start_date
        if schedule.end_date and through > schedule.end_date:
            through = schedule.end_date
        if start > through:
            return 0

        times = self._resolve_times(schedule)
        created = 0
        cursor = start
        while cursor <= through:
            for hhmm in times:
                hour, minute = (int(x) for x in hhmm.split(":"))
                fire_at = datetime.combine(cursor, time(hour=hour, minute=minute))
                exists = (
                    self.db.query(MedicationDose)
                    .filter(
                        MedicationDose.schedule_id == schedule.id,
                        MedicationDose.scheduled_for == fire_at,
                    )
                    .first()
                )
                if exists is not None:
                    continue
                dose = MedicationDose(
                    schedule_id=schedule.id,
                    patient_id=schedule.patient_id,
                    scheduled_for=fire_at,
                )
                self.db.add(dose)
                created += 1
            cursor += timedelta(days=1)

        schedule.last_generated_through = through
        self.db.commit()
        return created

    def _resolve_times(self, schedule: MedicationSchedule) -> list[str]:
        if schedule.custom_times:
            return list(schedule.custom_times)
        return DEFAULT_FREQUENCY_TIMES.get(schedule.frequency, ["08:00"])

    # ------------------------------------------------------------------
    # CONFIRMATION
    # ------------------------------------------------------------------

    def confirm_dose(
        self,
        dose_id: int,
        *,
        status: MedicationDoseStatus,
        confirmed_by_user_id: Optional[int] = None,
        source: Optional[str] = "PATIENT_PORTAL",
        miss_reason: Optional[str] = None,
        taken_at: Optional[datetime] = None,
    ) -> MedicationDose:
        dose = self.db.query(MedicationDose).filter(MedicationDose.id == dose_id).first()
        if dose is None:
            raise NotFoundError(message="Medication dose not found.")
        dose.status = status
        dose.confirmed_by_user_id = confirmed_by_user_id
        dose.confirmation_source = source
        dose.miss_reason = miss_reason
        if status == MedicationDoseStatus.TAKEN:
            dose.taken_at = taken_at or datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(dose)
        return dose

    # ------------------------------------------------------------------
    # ADHERENCE ROLLUP
    # ------------------------------------------------------------------

    def compute_adherence(
        self,
        *,
        patient_id: int,
        schedule_id: Optional[int] = None,
        period_start: date,
        period_end: date,
    ) -> AdherenceSnapshot:
        q = self.db.query(MedicationDose).filter(
            MedicationDose.patient_id == patient_id,
            MedicationDose.scheduled_for >= datetime.combine(period_start, time.min),
            MedicationDose.scheduled_for <= datetime.combine(period_end, time.max),
            MedicationDose.is_deleted.is_(False),
        )
        if schedule_id is not None:
            q = q.filter(MedicationDose.schedule_id == schedule_id)
        doses = q.all()

        scheduled = len(doses)
        taken = sum(1 for d in doses if d.status == MedicationDoseStatus.TAKEN)
        missed = sum(1 for d in doses if d.status == MedicationDoseStatus.MISSED)
        skipped = sum(1 for d in doses if d.status == MedicationDoseStatus.SKIPPED)
        delayed = sum(1 for d in doses if d.status == MedicationDoseStatus.DELAYED)

        pct = Decimal("0.00")
        if scheduled:
            pct = (
                (Decimal(taken) + Decimal(delayed) * Decimal("0.5"))
                / Decimal(scheduled)
                * Decimal(100)
            ).quantize(Decimal("0.01"))

        if scheduled == 0:
            level = AdherenceLevel.UNKNOWN
        elif pct >= 95:
            level = AdherenceLevel.EXCELLENT
        elif pct >= 80:
            level = AdherenceLevel.GOOD
        elif pct >= 60:
            level = AdherenceLevel.FAIR
        else:
            level = AdherenceLevel.POOR

        snap = AdherenceSnapshot(
            patient_id=patient_id,
            schedule_id=schedule_id,
            period_start=period_start,
            period_end=period_end,
            doses_scheduled=scheduled,
            doses_taken=taken,
            doses_missed=missed,
            doses_skipped=skipped,
            doses_delayed=delayed,
            adherence_pct=pct,
            level=level,
        )
        self.db.add(snap)
        self.db.commit()
        self.db.refresh(snap)
        return snap

    def raise_alert_if_needed(self, snapshot: AdherenceSnapshot) -> Optional[AdherenceAlert]:
        if snapshot.level not in {AdherenceLevel.POOR, AdherenceLevel.FAIR}:
            return None
        sev = (
            AdherenceAlertSeverity.CRITICAL
            if snapshot.level == AdherenceLevel.POOR
            else AdherenceAlertSeverity.WARNING
        )
        alert = AdherenceAlert(
            patient_id=snapshot.patient_id,
            schedule_id=snapshot.schedule_id,
            severity=sev,
            title=f"Patient adherence: {snapshot.level.value} ({snapshot.adherence_pct}%)",
            message=(
                f"Period {snapshot.period_start}–{snapshot.period_end}: "
                f"{snapshot.doses_taken}/{snapshot.doses_scheduled} doses taken, "
                f"{snapshot.doses_missed} missed, {snapshot.doses_skipped} skipped."
            ),
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)

        try:
            from app.models.all_models import Role, User, UserRoleAssociation
            from app.services.notification_dispatcher import NotificationDispatcher

            care_team = (
                self.db.query(User)
                .join(UserRoleAssociation, UserRoleAssociation.user_id == User.id)
                .join(Role, Role.id == UserRoleAssociation.role_id)
                .filter(
                    Role.code.in_(["DOCTOR", "NURSE", "PHARMACIST", "TENANT_ADMIN"]),
                    User.is_deleted.is_(False),
                )
                .all()
            )
            if care_team:
                NotificationDispatcher(self.db).dispatch(
                    event=NotificationEvent.SYSTEM_ALERT,
                    recipients=care_team,
                    subject=alert.title,
                    body=alert.message or "",
                    context={"patient_id": snapshot.patient_id, "alert_id": alert.id},
                )
        except Exception as exc:
            logger.warning("Adherence alert dispatch failed: %s", exc)

        return alert

    # ------------------------------------------------------------------
    # REFILLS
    # ------------------------------------------------------------------

    def upsert_refill(
        self,
        *,
        schedule: MedicationSchedule,
        due_date: date,
        prescription_item_id: Optional[int] = None,
    ) -> RefillRecord:
        existing = (
            self.db.query(RefillRecord)
            .filter(
                RefillRecord.schedule_id == schedule.id,
                RefillRecord.status.in_(
                    [RefillStatus.DUE_SOON, RefillStatus.DUE, RefillStatus.OVERDUE]
                ),
            )
            .first()
        )
        if existing is not None:
            existing.due_date = due_date
            self.db.commit()
            return existing
        rec = RefillRecord(
            patient_id=schedule.patient_id,
            schedule_id=schedule.id,
            prescription_item_id=prescription_item_id,
            due_date=due_date,
            status=RefillStatus.DUE_SOON,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def sweep_overdue_refills(self) -> int:
        today = date.today()
        targets = (
            self.db.query(RefillRecord)
            .filter(
                RefillRecord.status.in_([RefillStatus.DUE_SOON, RefillStatus.DUE]),
                RefillRecord.due_date <= today,
                RefillRecord.is_deleted.is_(False),
            )
            .all()
        )
        for r in targets:
            r.status = RefillStatus.OVERDUE
        if targets:
            self.db.commit()
        return len(targets)
