"""Unit tests for AppointmentService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.appointment_service import AppointmentService


class TestAppointmentGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = AppointmentService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestAppointmentConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = AppointmentService(db)
        assert svc.db is db


class TestAppointmentListAppointments:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = AppointmentService(db)
        svc.repository = MagicMock()
        svc.list_appointments(skip=0, limit=10)
        svc.repository.list_appointments.assert_called_once()
