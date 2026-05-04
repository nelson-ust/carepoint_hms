"""Unit tests for MedicationAdherenceService."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.core.enums import (
    AdherenceLevel,
    MedicationDoseStatus,
    MedicationFrequency,
    MedicationScheduleStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.services.medication_adherence_service import (
    DEFAULT_FREQUENCY_TIMES,
    MedicationAdherenceService,
)


class TestDefaultFrequencyTimes:
    def test_daily_one_time(self):
        assert DEFAULT_FREQUENCY_TIMES[MedicationFrequency.DAILY] == ["08:00"]

    def test_three_times_daily_three_times(self):
        assert len(DEFAULT_FREQUENCY_TIMES[MedicationFrequency.THREE_TIMES_DAILY]) == 3

    def test_every_4_hours_six_times(self):
        assert len(DEFAULT_FREQUENCY_TIMES[MedicationFrequency.EVERY_4_HOURS]) == 6

    def test_all_times_well_formed(self):
        for times in DEFAULT_FREQUENCY_TIMES.values():
            for hhmm in times:
                hour, minute = hhmm.split(":")
                assert 0 <= int(hour) <= 23
                assert 0 <= int(minute) <= 59


class TestResolveTimes:
    def test_uses_custom_when_provided(self):
        svc = MedicationAdherenceService(MagicMock())
        sched = MagicMock(custom_times=["07:00", "19:00"], frequency=MedicationFrequency.CUSTOM)
        assert svc._resolve_times(sched) == ["07:00", "19:00"]

    def test_falls_back_to_default(self):
        svc = MedicationAdherenceService(MagicMock())
        sched = MagicMock(custom_times=None, frequency=MedicationFrequency.TWICE_DAILY)
        assert svc._resolve_times(sched) == DEFAULT_FREQUENCY_TIMES[MedicationFrequency.TWICE_DAILY]


class TestCreateScheduleValidation:
    def test_custom_requires_custom_times(self):
        # The service first checks profile existence; mock it to return a
        # value so the frequency validation is the first thing to fire.
        db = MagicMock()
        profile = MagicMock(id=1, patient_id=1)
        db.query.return_value.filter.return_value.first.return_value = profile
        svc = MedicationAdherenceService(db)
        with pytest.raises(BadRequestError):
            svc.create_schedule(
                medication_profile_id=1,
                frequency=MedicationFrequency.CUSTOM,
                start_date=date(2026, 1, 1),
            )

    def test_missing_profile_raises_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        svc = MedicationAdherenceService(db)
        with pytest.raises(NotFoundError):
            svc.create_schedule(
                medication_profile_id=999,
                frequency=MedicationFrequency.DAILY,
                start_date=date(2026, 1, 1),
            )


class TestGenerateDosesEarlyExits:
    def test_paused_schedule_returns_zero(self):
        svc = MedicationAdherenceService(MagicMock())
        sched = MagicMock()
        sched.status = MedicationScheduleStatus.PAUSED
        assert svc.generate_doses(sched, through=date(2026, 1, 31)) == 0

    def test_window_already_covered(self):
        svc = MedicationAdherenceService(MagicMock())
        sched = MagicMock()
        sched.status = MedicationScheduleStatus.ACTIVE
        sched.last_generated_through = date(2026, 1, 10)
        sched.start_date = date(2026, 1, 1)
        sched.end_date = None
        assert svc.generate_doses(sched, through=date(2026, 1, 5)) == 0


class TestComputeAdherenceBucketing:
    def test_compute_handles_zero_scheduled(self):
        # When no doses exist we expect UNKNOWN bucket.
        from app.models.all_models import AdherenceSnapshot

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        # Deliberately bypass the .add chain; we just need the method
        # to compute bucketing logic correctly.
        svc = MedicationAdherenceService(db)
        snap = svc.compute_adherence(
            patient_id=1,
            schedule_id=None,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 7),
        )
        assert snap.level == AdherenceLevel.UNKNOWN
        assert snap.adherence_pct == Decimal("0.00")
