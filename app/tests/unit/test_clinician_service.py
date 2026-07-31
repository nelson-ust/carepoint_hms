from __future__ import annotations

"""
Unit tests for ClinicianService.
"""

from unittest.mock import MagicMock

import pytest

from app.core.exceptions import NotFoundError
from app.services.clinician_service import ClinicianService


class TestClinicianService:
    @pytest.fixture
    def db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, db):
        return ClinicianService(db)

    def test_list_clinicians_delegates_to_repository(self, service):
        """
        Verify that list_clinicians correctly delegates to the repository.
        """
        service.repository.list_clinicians = MagicMock(return_value=([], 0))
        items, total = service.list_clinicians(skip=10, limit=5, specialty="Cardiology")

        service.repository.list_clinicians.assert_called_once_with(
            skip=10, limit=5, specialty="Cardiology", search=None
        )
        assert items == []
        assert total == 0

    def test_get_clinician_returns_clinician_when_found(self, service):
        """
        Verify that get_clinician returns the expected staff profile.
        """
        mock_clinician = MagicMock()
        service.repository.get_clinician_by_id = MagicMock(return_value=mock_clinician)

        result = service.get_clinician(42)

        service.repository.get_clinician_by_id.assert_called_once_with(42)
        assert result == mock_clinician

    def test_get_clinician_raises_not_found_when_missing(self, service):
        """
        Verify that get_clinician raises a NotFoundError for invalid IDs.
        """
        service.repository.get_clinician_by_id = MagicMock(return_value=None)

        with pytest.raises(NotFoundError) as exc:
            service.get_clinician(999)

        assert "Clinician not found" in str(exc.value)
        assert exc.value.detail["clinician_id"] == 999
