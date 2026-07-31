"""Unit tests for Shift Management services (mock-based)."""
from __future__ import annotations

from datetime import time, date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import StaffShiftType, ShiftStatus
from app.services.shift_service import (
    ShiftDefinitionService,
    StaffShiftAssignmentService,
    ShiftSwapRequestService,
)


# ── ShiftDefinitionService ───────────────────────────────────────────

class TestShiftDefinitionService:
    def test_get_raises_404_when_not_found(self):
        db = MagicMock()
        svc = ShiftDefinitionService(db)
        svc.repository = MagicMock()
        svc.repository.get_by_id.return_value = None

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.get(999)
        assert exc_info.value.status_code == 404

    def test_get_delegates_to_repository(self):
        db = MagicMock()
        svc = ShiftDefinitionService(db)
        svc.repository = MagicMock()
        defn = SimpleNamespace(id=1, name="Morning")
        svc.repository.get_by_id.return_value = defn

        result = svc.get(1)
        svc.repository.get_by_id.assert_called_once_with(1)
        assert result.name == "Morning"

    def test_create_delegates_to_repository(self):
        db = MagicMock()
        svc = ShiftDefinitionService(db)
        svc.repository = MagicMock()
        # create() now validates that the selected unit (SDP) belongs to the
        # chosen department. Satisfy that lookup with a matching unit.
        unit = SimpleNamespace(id=2, department_id=1)
        db.scalars.return_value.first.return_value = unit
        payload = MagicMock(department_id=1, service_delivery_point_id=2)
        svc.create(payload)
        svc.repository.create.assert_called_once_with(payload)

    def test_delete_raises_404_when_not_found(self):
        db = MagicMock()
        svc = ShiftDefinitionService(db)
        svc.repository = MagicMock()
        svc.repository.get_by_id.return_value = None

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.delete(999)
        assert exc_info.value.status_code == 404

    def test_list_definitions_delegates(self):
        db = MagicMock()
        svc = ShiftDefinitionService(db)
        svc.repository = MagicMock()
        svc.repository.list_definitions.return_value = ([], 0)

        items, total = svc.list_definitions(department_id=1)
        # The repository call now carries the service_delivery_point_id filter
        # (None here) between department_id and the pagination args.
        svc.repository.list_definitions.assert_called_once_with(1, None, 0, 100)
        assert total == 0


# ── StaffShiftAssignmentService ──────────────────────────────────────

class TestStaffShiftAssignmentService:
    def test_get_raises_404_when_not_found(self):
        db = MagicMock()
        svc = StaffShiftAssignmentService(db)
        svc.repository = MagicMock()
        svc.repository.get_by_id.return_value = None

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.get(999)
        assert exc_info.value.status_code == 404

    def test_create_validates_definition_exists(self):
        db = MagicMock()
        svc = StaffShiftAssignmentService(db)
        svc.repository = MagicMock()
        svc.definition_repo = MagicMock()
        svc.definition_repo.get_by_id.return_value = None

        payload = MagicMock(shift_definition_id=999)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.create(payload)
        assert exc_info.value.status_code == 400

    def test_check_in_rejects_non_scheduled(self):
        db = MagicMock()
        svc = StaffShiftAssignmentService(db)
        svc.repository = MagicMock()
        assignment = SimpleNamespace(
            id=1, status=ShiftStatus.COMPLETED, check_in_at=None
        )
        svc.repository.get_by_id.return_value = assignment

        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="scheduled"):
            svc.check_in(1)

    def test_check_in_transitions_to_on_duty(self):
        db = MagicMock()
        svc = StaffShiftAssignmentService(db)
        svc.repository = MagicMock()
        assignment = SimpleNamespace(
            id=1, status=ShiftStatus.SCHEDULED, check_in_at=None, check_out_at=None
        )
        svc.repository.get_by_id.return_value = assignment

        result = svc.check_in(1)
        assert result.status == ShiftStatus.ON_DUTY
        assert result.check_in_at is not None

    def test_check_out_rejects_non_on_duty(self):
        db = MagicMock()
        svc = StaffShiftAssignmentService(db)
        svc.repository = MagicMock()
        assignment = SimpleNamespace(
            id=1, status=ShiftStatus.SCHEDULED, check_out_at=None
        )
        svc.repository.get_by_id.return_value = assignment

        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="on-duty"):
            svc.check_out(1)

    def test_check_out_transitions_to_completed(self):
        db = MagicMock()
        svc = StaffShiftAssignmentService(db)
        svc.repository = MagicMock()
        assignment = SimpleNamespace(
            id=1, status=ShiftStatus.ON_DUTY, check_in_at=datetime.now(timezone.utc), check_out_at=None
        )
        svc.repository.get_by_id.return_value = assignment

        result = svc.check_out(1)
        assert result.status == ShiftStatus.COMPLETED
        assert result.check_out_at is not None

    def test_delete_rejects_active_shift(self):
        db = MagicMock()
        svc = StaffShiftAssignmentService(db)
        svc.repository = MagicMock()
        assignment = SimpleNamespace(id=1, status=ShiftStatus.ON_DUTY)
        svc.repository.get_by_id.return_value = assignment

        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="Cannot delete"):
            svc.delete(1)


# ── ShiftSwapRequestService ─────────────────────────────────────────

class TestShiftSwapRequestService:
    def test_get_raises_404_when_not_found(self):
        db = MagicMock()
        svc = ShiftSwapRequestService(db)
        svc.repository = MagicMock()
        svc.repository.get_by_id.return_value = None

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            svc.get(999)
        assert exc_info.value.status_code == 404

    def test_approve_rejects_non_pending(self):
        db = MagicMock()
        svc = ShiftSwapRequestService(db)
        svc.repository = MagicMock()
        swap = SimpleNamespace(id=1, status="APPROVED")
        svc.repository.get_by_id.return_value = swap

        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="pending"):
            svc.approve(1, decided_by=1)

    def test_approve_transitions_status(self):
        db = MagicMock()
        svc = ShiftSwapRequestService(db)
        svc.repository = MagicMock()
        swap = SimpleNamespace(
            id=1, status="PENDING", decided_by_user_id=None, decided_at=None
        )
        svc.repository.get_by_id.return_value = swap

        result = svc.approve(1, decided_by=42)
        assert result.status == "APPROVED"
        assert result.decided_by_user_id == 42

    def test_reject_transitions_status(self):
        db = MagicMock()
        svc = ShiftSwapRequestService(db)
        svc.repository = MagicMock()
        swap = SimpleNamespace(
            id=1, status="PENDING", decided_by_user_id=None, decided_at=None
        )
        svc.repository.get_by_id.return_value = swap

        result = svc.reject(1, decided_by=42)
        assert result.status == "REJECTED"
        assert result.decided_by_user_id == 42
