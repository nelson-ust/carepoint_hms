"""Unit tests for DoctorCalendarService."""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from app.core.enums import AppointmentSlotStatus, DoctorAvailabilityType
from app.core.exceptions import BadRequestError
from app.services.doctor_calendar_service import DoctorCalendarService


class TestHHMMValidation:
    def test_accepts_valid_hhmm(self):
        DoctorCalendarService._validate_hhmm("08:00", "x")
        DoctorCalendarService._validate_hhmm("23:59", "x")
        DoctorCalendarService._validate_hhmm("00:00", "x")

    def test_rejects_bad_format(self):
        with pytest.raises(BadRequestError):
            DoctorCalendarService._validate_hhmm("8am", "x")

    def test_rejects_out_of_range(self):
        with pytest.raises(BadRequestError):
            DoctorCalendarService._validate_hhmm("25:00", "x")
        with pytest.raises(BadRequestError):
            DoctorCalendarService._validate_hhmm("12:60", "x")


class TestCreateTemplateValidation:
    def test_invalid_weekday(self):
        svc = DoctorCalendarService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.create_template(
                staff_profile_id=1,
                weekday=7,
                start_time="09:00",
                end_time="17:00",
            )

    def test_start_after_end(self):
        svc = DoctorCalendarService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.create_template(
                staff_profile_id=1,
                weekday=1,
                start_time="17:00",
                end_time="09:00",
            )

    def test_slot_duration_out_of_range(self):
        svc = DoctorCalendarService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.create_template(
                staff_profile_id=1,
                weekday=1,
                start_time="09:00",
                end_time="17:00",
                slot_duration_minutes=300,
            )


class TestIsBlocked:
    def test_blocked_window_overlaps_slot(self):
        slot_start = datetime(2026, 1, 1, 10, 0)
        slot_end = datetime(2026, 1, 1, 10, 30)
        time_off = MagicMock()
        time_off.availability_type = DoctorAvailabilityType.BLOCKED
        time_off.starts_at = datetime(2026, 1, 1, 9, 0)
        time_off.ends_at = datetime(2026, 1, 1, 11, 0)
        assert DoctorCalendarService._is_blocked([time_off], slot_start, slot_end) is True

    def test_window_outside_slot(self):
        slot_start = datetime(2026, 1, 1, 10, 0)
        slot_end = datetime(2026, 1, 1, 10, 30)
        time_off = MagicMock()
        time_off.availability_type = DoctorAvailabilityType.BLOCKED
        time_off.starts_at = datetime(2026, 1, 1, 12, 0)
        time_off.ends_at = datetime(2026, 1, 1, 13, 0)
        assert DoctorCalendarService._is_blocked([time_off], slot_start, slot_end) is False

    def test_non_blocked_type_ignored(self):
        slot_start = datetime(2026, 1, 1, 10, 0)
        slot_end = datetime(2026, 1, 1, 10, 30)
        time_off = MagicMock()
        time_off.availability_type = DoctorAvailabilityType.OVERRIDE
        time_off.starts_at = datetime(2026, 1, 1, 9, 0)
        time_off.ends_at = datetime(2026, 1, 1, 11, 0)
        assert DoctorCalendarService._is_blocked([time_off], slot_start, slot_end) is False


class TestMaterialiseValidation:
    def test_through_before_from(self):
        svc = DoctorCalendarService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.materialise_slots(
                staff_profile_id=1,
                from_date=date(2026, 2, 1),
                through_date=date(2026, 1, 1),
            )
