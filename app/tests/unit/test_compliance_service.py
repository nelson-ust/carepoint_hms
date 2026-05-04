"""Unit tests for ComplianceRecordService, AccreditationService, IncidentReportService, InfectionControlService."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.compliance_service import (
    ComplianceRecordService,
    AccreditationService,
    IncidentReportService,
    InfectionControlService,
    QualityImprovementProjectService,
)


class TestComplianceRecordGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = ComplianceRecordService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestComplianceRecordSoftDelete:
    def test_soft_deletes(self):
        db = MagicMock()
        svc = ComplianceRecordService(db)
        svc.repository = MagicMock()
        svc.repository.get_required_by_id.return_value = SimpleNamespace(id=1)
        svc.soft_delete(1)
        db.commit.assert_called_once()


class TestAccreditationGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = AccreditationService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestIncidentReportGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = IncidentReportService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestInfectionControlGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = InfectionControlService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)


class TestQualityImprovementGet:
    def test_delegates_to_repository(self):
        db = MagicMock()
        svc = QualityImprovementProjectService(db)
        svc.repository = MagicMock()
        svc.get(42)
        svc.repository.get_required_by_id.assert_called_once_with(42)
