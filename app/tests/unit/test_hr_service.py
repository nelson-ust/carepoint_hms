"""Unit tests for HR services."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import BadRequestError
from app.services.hr_service import (
    DEFAULT_OFFBOARDING_ITEMS,
    DEFAULT_ONBOARDING_ITEMS,
    AttendanceService,
    DutyRosterService,
    LeaveService,
    OvertimeService,
    PayrollService,
    StaffLicenseService,
    StaffLoanService,
    StaffOnboardingService,
    TimesheetService,
    _q,
    _serialise,
)


class TestDefaultChecklists:
    def test_onboarding_has_items(self):
        assert len(DEFAULT_ONBOARDING_ITEMS) >= 5

    def test_offboarding_has_items(self):
        assert len(DEFAULT_OFFBOARDING_ITEMS) >= 5


class TestQuantize:
    def test_two_places(self):
        assert _q(Decimal("1.236")) == Decimal("1.24")


class TestServiceConstruction:
    def test_onboarding_service(self):
        svc = StaffOnboardingService(MagicMock(), actor_user_id=1)
        assert svc.actor_user_id == 1

    def test_attendance_service(self):
        svc = AttendanceService(MagicMock())
        assert svc.db is not None

    def test_duty_roster_service(self):
        svc = DutyRosterService(MagicMock())
        assert svc.db is not None


class TestDutyAssignmentValidation:
    def test_ends_before_start_rejected(self):
        # Mock the conflict-detection query to return None so we get
        # past it to the start/end check ... actually start/end is the
        # FIRST check, so we hit it first regardless.
        svc = DutyRosterService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.add_assignment(
                roster_id=1,
                staff_profile_id=1,
                starts_at=datetime(2026, 1, 1, 17),
                ends_at=datetime(2026, 1, 1, 9),
            )


class TestLeaveServiceValidation:
    def test_end_before_start_rejected(self):
        svc = LeaveService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.request_leave(
                staff_profile_id=1,
                leave_type_id=1,
                start_date=date(2026, 1, 10),
                end_date=date(2026, 1, 5),
            )


class TestStaffLoanServiceValidation:
    def test_repayment_count_must_be_positive(self):
        svc = StaffLoanService(MagicMock())
        with pytest.raises(BadRequestError):
            svc.create(
                staff_profile_id=1,
                principal_amount=Decimal("100000"),
                repayment_count=0,
            )


class TestSerialise:
    def test_dates_iso(self):
        class _Col:
            def __init__(self, name):
                self.name = name
        class _Tab:
            columns = [_Col("id"), _Col("hired_on"), _Col("salary")]
        class _Rec:
            __table__ = _Tab()
            id = 1
            hired_on = date(2026, 5, 1)
            salary = Decimal("250000.00")
        out = _serialise(_Rec())
        assert out["hired_on"] == "2026-05-01"
        assert out["salary"] == "250000.00"
