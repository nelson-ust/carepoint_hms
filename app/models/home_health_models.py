# carepoint_hms/app/models/home_health_models.py
from __future__ import annotations

"""
carepoint_hms.app.models.home_health_models

Home-Health "core spine" ORM models for Carepoint HMS.

This companion module (imported at the tail of ``app.models.all_models``,
mirroring ``finance_models``) registers the home-care tables on
``TenantBase.metadata`` so they are created by ``create_all``,
``db_sync`` and the test harness alongside every other tenant table.

Domains
-------
1. Home Visit management        -> HomeVisit, HomeVisitStatusEvent, HomeVisitNote
2. Care Plan engine             -> CarePlan, CarePlanGoal, CarePlanIntervention,
                                   CareTask, CarePlanProgressNote, CarePlanReview
3. Remote Patient Monitoring    -> MonitoringDevice, MonitoringReading,
                                   MonitoringThreshold
4. Clinical Alerts / Early Warn -> ClinicalAlert, EarlyWarningRule

Design notes
------------
- All tables inherit from ``TenantTable`` (tenant-scoped, audited, soft-delete).
- Relationships to shared entities (Patient, StaffProfile, Facility, User) are
  intentionally one-directional (no ``back_populates``) so this module does not
  need to edit the large shared model classes. Home-health-internal parent/child
  relationships use ``back_populates`` normally.
- Enums live in ``app.core.enums``.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    AlertComparator,
    AlertSeverity,
    AlertStatus,
    AlertType,
    CareFrequency,
    CarePlanGoalStatus,
    CarePlanGoalType,
    CarePlanInterventionStatus,
    CarePlanReviewOutcome,
    CarePlanStatus,
    CareTaskStatus,
    HomeVisitPriority,
    HomeVisitStatus,
    HomeVisitType,
    MonitoringDeviceType,
    MonitoringReadingType,
    MonitoringSource,
)
from app.models.base import TenantTable


# ============================================================
# 1. HOME VISIT MANAGEMENT
# ============================================================


class HomeVisit(TenantTable):
    """
    A scheduled domiciliary (home) visit by a healthcare worker.

    Distinct from the in-facility ``Visit`` model: a HomeVisit carries the
    patient's location, an assigned mobile caregiver, an ETA and a request ->
    completed status lifecycle appropriate to field work.
    """

    visit_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    care_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("care_plan.id"), nullable=True, index=True)

    # Assigned mobile caregiver (nurse / CHW / physiotherapist) — a StaffProfile.
    assigned_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True, index=True
    )
    requested_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)

    visit_type: Mapped[HomeVisitType] = mapped_column(
        Enum(HomeVisitType), default=HomeVisitType.ROUTINE, nullable=False, index=True
    )
    status: Mapped[HomeVisitStatus] = mapped_column(
        Enum(HomeVisitStatus), default=HomeVisitStatus.REQUESTED, nullable=False, index=True
    )
    priority: Mapped[HomeVisitPriority] = mapped_column(
        Enum(HomeVisitPriority), default=HomeVisitPriority.NORMAL, nullable=False, index=True
    )

    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scheduling
    scheduled_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    scheduled_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    eta_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Actual field timings
    en_route_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Location of the patient / visit
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)

    # Recurrence
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    parent_visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("home_visit.id"), nullable=True, index=True)

    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient")  # type: ignore[name-defined]
    assigned_staff: Mapped[Optional["StaffProfile"]] = relationship("StaffProfile")  # type: ignore[name-defined]
    care_plan: Mapped[Optional["CarePlan"]] = relationship("CarePlan", foreign_keys=[care_plan_id])

    status_events: Mapped[list["HomeVisitStatusEvent"]] = relationship(
        back_populates="home_visit",
        cascade="all, delete-orphan",
        order_by="HomeVisitStatusEvent.occurred_at",
    )
    note: Mapped[Optional["HomeVisitNote"]] = relationship(
        back_populates="home_visit",
        cascade="all, delete-orphan",
        uselist=False,
    )


class HomeVisitStatusEvent(TenantTable):
    """
    Immutable audit entry for each home-visit status transition, capturing the
    caregiver's GPS position at the moment of the transition (en route / arrived).
    """

    home_visit_id: Mapped[int] = mapped_column(ForeignKey("home_visit.id"), nullable=False, index=True)
    from_status: Mapped[Optional[HomeVisitStatus]] = mapped_column(Enum(HomeVisitStatus), nullable=True)
    to_status: Mapped[HomeVisitStatus] = mapped_column(Enum(HomeVisitStatus), nullable=False, index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    changed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    home_visit: Mapped["HomeVisit"] = relationship(back_populates="status_events")


class HomeVisitNote(TenantTable):
    """
    Clinical documentation captured during a home visit (one per visit).

    Bundles the field assessment plus a snapshot of vitals recorded at the
    bedside and the caregiver's electronic signature. Detailed longitudinal
    vitals are also stored as ``MonitoringReading`` rows linked to the visit.
    """

    home_visit_id: Mapped[int] = mapped_column(ForeignKey("home_visit.id"), nullable=False, unique=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)

    reason_for_visit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    symptoms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    physical_assessment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nursing_assessment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clinical_observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assessment_diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    procedures_performed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medication_administered: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wound_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    patient_education: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    care_plan_updates: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    follow_up_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Bedside vitals snapshot (nullable — a visit may not capture every field)
    temperature_celsius: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1), nullable=True)
    pulse_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    respiratory_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    systolic_bp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    diastolic_bp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    oxygen_saturation: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    blood_glucose: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    pain_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Checklist of tasks completed on the visit + attachment references (photos/docs)
    checklist: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    attachments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Electronic signature
    signed_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)
    signature_image_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    home_visit: Mapped["HomeVisit"] = relationship(back_populates="note")


# ============================================================
# 2. CARE PLAN ENGINE
# ============================================================


class CarePlan(TenantTable):
    """An individualized, longitudinal plan of care for a patient."""

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    condition: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[CarePlanStatus] = mapped_column(
        Enum(CarePlanStatus), default=CarePlanStatus.DRAFT, nullable=False, index=True
    )
    priority: Mapped[HomeVisitPriority] = mapped_column(
        Enum(HomeVisitPriority), default=HomeVisitPriority.NORMAL, nullable=False
    )

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    lead_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True, index=True)

    review_frequency_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    next_review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)

    patient: Mapped["Patient"] = relationship("Patient")  # type: ignore[name-defined]
    lead_staff: Mapped[Optional["StaffProfile"]] = relationship("StaffProfile")  # type: ignore[name-defined]

    goals: Mapped[list["CarePlanGoal"]] = relationship(
        back_populates="care_plan", cascade="all, delete-orphan"
    )
    interventions: Mapped[list["CarePlanIntervention"]] = relationship(
        back_populates="care_plan", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["CareTask"]] = relationship(
        back_populates="care_plan", cascade="all, delete-orphan"
    )
    progress_notes: Mapped[list["CarePlanProgressNote"]] = relationship(
        back_populates="care_plan", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["CarePlanReview"]] = relationship(
        back_populates="care_plan", cascade="all, delete-orphan"
    )


class CarePlanGoal(TenantTable):
    """A measurable short- or long-term goal within a care plan."""

    care_plan_id: Mapped[int] = mapped_column(ForeignKey("care_plan.id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    goal_type: Mapped[CarePlanGoalType] = mapped_column(
        Enum(CarePlanGoalType), default=CarePlanGoalType.SHORT_TERM, nullable=False
    )
    status: Mapped[CarePlanGoalStatus] = mapped_column(
        Enum(CarePlanGoalStatus), default=CarePlanGoalStatus.PENDING, nullable=False, index=True
    )
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    baseline_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    measure_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    progress_percent: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)

    care_plan: Mapped["CarePlan"] = relationship(back_populates="goals")


class CarePlanIntervention(TenantTable):
    """A planned clinical intervention supporting one or more goals."""

    care_plan_id: Mapped[int] = mapped_column(ForeignKey("care_plan.id"), nullable=False, index=True)
    goal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("care_plan_goal.id"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    assigned_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True, index=True)
    frequency: Mapped[CareFrequency] = mapped_column(
        Enum(CareFrequency), default=CareFrequency.AS_NEEDED, nullable=False
    )
    frequency_detail: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    status: Mapped[CarePlanInterventionStatus] = mapped_column(
        Enum(CarePlanInterventionStatus), default=CarePlanInterventionStatus.PLANNED, nullable=False, index=True
    )

    care_plan: Mapped["CarePlan"] = relationship(back_populates="interventions")


class CareTask(TenantTable):
    """
    A discrete, schedulable task/checklist item derived from an intervention.

    Drives the caregiver task checklist and "missed task" early-warning alerts.
    """

    care_plan_id: Mapped[int] = mapped_column(ForeignKey("care_plan.id"), nullable=False, index=True)
    intervention_id: Mapped[Optional[int]] = mapped_column(ForeignKey("care_plan_intervention.id"), nullable=True, index=True)
    home_visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("home_visit.id"), nullable=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    assigned_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True, index=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    status: Mapped[CareTaskStatus] = mapped_column(
        Enum(CareTaskStatus), default=CareTaskStatus.PENDING, nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)
    completion_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    care_plan: Mapped["CarePlan"] = relationship(back_populates="tasks")


class CarePlanProgressNote(TenantTable):
    """A dated progress note recorded against a care plan (and optionally a goal)."""

    care_plan_id: Mapped[int] = mapped_column(ForeignKey("care_plan.id"), nullable=False, index=True)
    goal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("care_plan_goal.id"), nullable=True, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    progress_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    recorded_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    care_plan: Mapped["CarePlan"] = relationship(back_populates="progress_notes")


class CarePlanReview(TenantTable):
    """A periodic clinical review of a care plan and its outcome decision."""

    care_plan_id: Mapped[int] = mapped_column(ForeignKey("care_plan.id"), nullable=False, index=True)
    reviewed_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)
    review_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome: Mapped[CarePlanReviewOutcome] = mapped_column(
        Enum(CarePlanReviewOutcome), default=CarePlanReviewOutcome.CONTINUE, nullable=False
    )
    next_review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    care_plan: Mapped["CarePlan"] = relationship(back_populates="reviews")


# ============================================================
# 3. REMOTE PATIENT MONITORING
# ============================================================


class MonitoringDevice(TenantTable):
    """A monitoring / connected device assigned to a patient."""

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    device_type: Mapped[MonitoringDeviceType] = mapped_column(
        Enum(MonitoringDeviceType), default=MonitoringDeviceType.OTHER, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    connection_type: Mapped[MonitoringSource] = mapped_column(
        Enum(MonitoringSource), default=MonitoringSource.MANUAL, nullable=False
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship("Patient")  # type: ignore[name-defined]


class MonitoringReading(TenantTable):
    """
    A single remote-monitoring measurement.

    Handles both single-value readings (glucose, SpO2, weight, pulse) and the
    two-part blood-pressure reading via ``systolic``/``diastolic`` plus a
    generic ``primary_value``/``secondary_value`` pair and a ``raw`` payload
    for device-reported extras.
    """

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    care_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("care_plan.id"), nullable=True, index=True)
    home_visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("home_visit.id"), nullable=True, index=True)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("monitoring_device.id"), nullable=True, index=True)

    reading_type: Mapped[MonitoringReadingType] = mapped_column(
        Enum(MonitoringReadingType), nullable=False, index=True
    )
    source: Mapped[MonitoringSource] = mapped_column(
        Enum(MonitoringSource), default=MonitoringSource.MANUAL, nullable=False, index=True
    )

    primary_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    secondary_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    systolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    diastolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    raw: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    is_abnormal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    severity: Mapped[Optional[AlertSeverity]] = mapped_column(Enum(AlertSeverity), nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship("Patient")  # type: ignore[name-defined]
    device: Mapped[Optional["MonitoringDevice"]] = relationship("MonitoringDevice")

    __table_args__ = (
        Index("ix_monitoring_reading_patient_type_time", "patient_id", "reading_type", "recorded_at"),
    )


class MonitoringThreshold(TenantTable):
    """
    Normal / critical bounds for a reading type. A ``patient_id`` of NULL makes
    the row a tenant-wide default; a patient-specific row overrides it.
    """

    patient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patient.id"), nullable=True, index=True)
    reading_type: Mapped[MonitoringReadingType] = mapped_column(
        Enum(MonitoringReadingType), nullable=False, index=True
    )
    unit: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    min_normal: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    max_normal: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    critical_low: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    critical_high: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    # For blood pressure (two components)
    min_normal_secondary: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    max_normal_secondary: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)


# ============================================================
# 4. CLINICAL ALERTS / EARLY WARNING
# ============================================================


class ClinicalAlert(TenantTable):
    """
    A clinical alert raised by the early-warning engine or manually, with an
    escalating severity tier and an acknowledge -> resolve workflow.
    """

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    care_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("care_plan.id"), nullable=True, index=True)
    home_visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("home_visit.id"), nullable=True, index=True)
    reading_id: Mapped[Optional[int]] = mapped_column(ForeignKey("monitoring_reading.id"), nullable=True, index=True)

    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), default=AlertType.OTHER, nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity), default=AlertSeverity.INFORMATION, nullable=False, index=True
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus), default=AlertStatus.OPEN, nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # De-duplication key so repeated identical breaches within a window collapse.
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    assigned_to_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True, index=True)

    acknowledged_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_to_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    resolved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship("Patient")  # type: ignore[name-defined]


class EarlyWarningRule(TenantTable):
    """
    A configurable early-warning rule mapping a reading condition to a severity
    and alert type. Evaluated by the alert engine in addition to thresholds.
    """

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reading_type: Mapped[MonitoringReadingType] = mapped_column(
        Enum(MonitoringReadingType), nullable=False, index=True
    )
    comparator: Mapped[AlertComparator] = mapped_column(Enum(AlertComparator), nullable=False)
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    threshold_value_high: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), default=AlertType.ABNORMAL_VITALS, nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity), default=AlertSeverity.WARNING, nullable=False
    )
    auto_escalate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_roles: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


# ============================================================
# 5. HOME LAB ORDERS (domiciliary sample collection)
#    Reuses the shared LabTestCatalog; kept separate from the
#    in-facility LabOrder (which is visit-bound) so the home
#    logistics — collection at home, transit, result — are modelled
#    faithfully without destabilising the core lab pipeline.
# ============================================================

from app.core.enums import HomeLabOrderStatus, HomeMedicationStatus  # noqa: E402


class HomeLabOrder(TenantTable):
    """A laboratory order raised in the course of home care."""

    order_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    home_visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("home_visit.id"), nullable=True, index=True)
    care_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("care_plan.id"), nullable=True, index=True)
    ordered_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    status: Mapped[HomeLabOrderStatus] = mapped_column(
        Enum(HomeLabOrderStatus), default=HomeLabOrderStatus.REQUESTED, nullable=False, index=True
    )
    clinical_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[HomeVisitPriority] = mapped_column(
        Enum(HomeVisitPriority), default=HomeVisitPriority.NORMAL, nullable=False
    )

    collection_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scheduled_collection_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sample_collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resulted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    patient: Mapped["Patient"] = relationship("Patient")  # type: ignore[name-defined]
    items: Mapped[list["HomeLabOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class HomeLabOrderItem(TenantTable):
    """A single analyte/test on a home lab order, with an inline result."""

    home_lab_order_id: Mapped[int] = mapped_column(ForeignKey("home_lab_order.id"), nullable=False, index=True)
    lab_test_catalog_id: Mapped[int] = mapped_column(ForeignKey("lab_test_catalog.id"), nullable=False, index=True)

    status: Mapped[HomeLabOrderStatus] = mapped_column(
        Enum(HomeLabOrderStatus), default=HomeLabOrderStatus.REQUESTED, nullable=False, index=True
    )
    result_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    result_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_range: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_abnormal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    interpretation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resulted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["HomeLabOrder"] = relationship(back_populates="items")
    lab_test_catalog: Mapped["LabTestCatalog"] = relationship("LabTestCatalog")  # type: ignore[name-defined]


# ============================================================
# 6. HOME MEDICATION ORDERS (dispensing + delivery to the home)
#    Reuses the shared Drug catalog; models dispensing and the
#    last-mile delivery/administration that home care requires.
# ============================================================


class HomeMedicationOrder(TenantTable):
    """A medication supply raised for home delivery / administration."""

    order_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    home_visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("home_visit.id"), nullable=True, index=True)
    care_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("care_plan.id"), nullable=True, index=True)
    prescribed_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    status: Mapped[HomeMedicationStatus] = mapped_column(
        Enum(HomeMedicationStatus), default=HomeMedicationStatus.PRESCRIBED, nullable=False, index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    delivery_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dispensed_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)
    dispensed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    courier_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    delivery_tracking_ref: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)
    prescribed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    patient: Mapped["Patient"] = relationship("Patient")  # type: ignore[name-defined]
    items: Mapped[list["HomeMedicationItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class HomeMedicationItem(TenantTable):
    """A single drug line on a home medication order."""

    home_medication_order_id: Mapped[int] = mapped_column(ForeignKey("home_medication_order.id"), nullable=False, index=True)
    drug_id: Mapped[int] = mapped_column(ForeignKey("drug.id"), nullable=False, index=True)

    dosage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    frequency: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    route: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    quantity_dispensed: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped["HomeMedicationOrder"] = relationship(back_populates="items")
    drug: Mapped["Drug"] = relationship("Drug")  # type: ignore[name-defined]
