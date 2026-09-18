# carepoint_hms/app/models/telemedicine_models.py
from __future__ import annotations

"""
Telemedicine ORM models for Carepoint HMS.

Registered on ``TenantBase.metadata`` via a tail import in
``app.models.all_models`` (mirrors finance_models / home_health_models).

A ``TelemedicineSession`` is a virtual encounter between a patient and a
clinician. It carries its own video room (Jitsi by default — embeddable and
credential-free — but the provider is configurable), an in-session secure
chat, and SOAP consultation notes, so a telemedicine visit is a first-class
part of the record rather than a bolt-on. Sessions can stand alone or link to
an appointment, a home visit or a care plan.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    TelemedicineModality,
    TelemedicineProvider,
    TelemedicineSenderRole,
    TelemedicineStatus,
)
from app.models.base import TenantTable


class TelemedicineSession(TenantTable):
    """A virtual (video/audio/chat) consultation."""

    session_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    clinician_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True, index=True)

    appointment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("appointment.id"), nullable=True, index=True)
    home_visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("home_visit.id"), nullable=True, index=True)
    care_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("care_plan.id"), nullable=True, index=True)

    modality: Mapped[TelemedicineModality] = mapped_column(
        Enum(TelemedicineModality), default=TelemedicineModality.VIDEO, nullable=False, index=True
    )
    status: Mapped[TelemedicineStatus] = mapped_column(
        Enum(TelemedicineStatus), default=TelemedicineStatus.SCHEDULED, nullable=False, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Video room
    provider: Mapped[TelemedicineProvider] = mapped_column(
        Enum(TelemedicineProvider), default=TelemedicineProvider.JITSI, nullable=False
    )
    room_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    room_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timings
    scheduled_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    scheduled_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    waiting_since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    patient_joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    clinician_joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # SOAP consultation notes
    subjective_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objective_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assessment_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    follow_up_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient")  # type: ignore[name-defined]
    clinician_staff: Mapped[Optional["StaffProfile"]] = relationship("StaffProfile")  # type: ignore[name-defined]
    messages: Mapped[list["TelemedicineMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="TelemedicineMessage.sent_at"
    )


class TelemedicineMessage(TenantTable):
    """A secure chat message within a telemedicine session."""

    session_id: Mapped[int] = mapped_column(ForeignKey("telemedicine_session.id"), nullable=False, index=True)
    sender_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    sender_role: Mapped[TelemedicineSenderRole] = mapped_column(
        Enum(TelemedicineSenderRole), default=TelemedicineSenderRole.SYSTEM, nullable=False
    )
    sender_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    attachment_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    session: Mapped["TelemedicineSession"] = relationship(back_populates="messages")
