"""Unit tests for AppointmentExtensionService."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.core.enums import AppointmentRecurrence, AppointmentReminderRule
from app.core.exceptions import BadRequestError
from app.services.appointment_extension_service import (
    RULE_OFFSETS_MINUTES,
    AppointmentExtensionService,
)


class TestReminderOffsets:
    def test_h24_offset(self):
        assert RULE_OFFSETS_MINUTES[AppointmentReminderRule.H24_BEFORE] == 24 * 60

    def test_h2_offset(self):
        assert RULE_OFFSETS_MINUTES[AppointmentReminderRule.H2_BEFORE] == 120

    def test_m15_offset(self):
        assert RULE_OFFSETS_MINUTES[AppointmentReminderRule.M15_BEFORE] == 15


class TestLogCancellationValidation:
    def test_rejects_unknown_action(self):
        svc = AppointmentExtensionService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.log_cancellation(appointment_id=1, action="UNKNOWN")

    def test_accepts_known_actions(self):
        # Mock db session so we don't try to commit.
        db = MagicMock()
        svc = AppointmentExtensionService(db)
        for action in ("CANCELLED", "RESCHEDULED", "NO_SHOW"):
            # Should not raise.
            svc.log_cancellation(appointment_id=1, action=action)


class TestCreateRecurrenceValidation:
    def test_requires_occurrences_or_until(self):
        svc = AppointmentExtensionService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.create_recurrence(
                parent_appointment_id=1,
                recurrence=AppointmentRecurrence.WEEKLY,
            )

    def test_accepts_with_occurrences(self):
        db = MagicMock()
        svc = AppointmentExtensionService(db)
        svc.create_recurrence(
            parent_appointment_id=1,
            recurrence=AppointmentRecurrence.WEEKLY,
            occurrences=4,
        )
