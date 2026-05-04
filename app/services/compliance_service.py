# app/services/compliance_service.py
from __future__ import annotations

"""
Service layer for the compliance / governance module (Stage 18).

Each entity has its own service class to keep the surface readable and the
permission boundary obvious in routes:

- :class:`ComplianceRecordService`
- :class:`AccreditationService`
- :class:`IncidentReportService`        — restricted access at the route layer
- :class:`InfectionControlService`
- :class:`QualityImprovementProjectService`
- :class:`GovernanceDashboardService`   — aggregator for ops dashboards
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    AccreditationStatus,
    ComplianceStatus,
    IncidentSeverity,
    QualityProjectStatus,
)
from app.core.exceptions import BadRequestError
from app.models.all_models import (
    Accreditation,
    ComplianceRecord,
    IncidentReport,
    InfectionControlLog,
    QualityImprovementProject,
)
from app.repositories.compliance_repository import (
    AccreditationRepository,
    ComplianceRecordRepository,
    IncidentReportRepository,
    InfectionControlLogRepository,
    QualityImprovementProjectRepository,
)
from app.schemas.compliance_schemas import (
    AccreditationCreateSchema,
    AccreditationUpdateSchema,
    ComplianceRecordCreateSchema,
    ComplianceRecordUpdateSchema,
    IncidentReportCreateSchema,
    IncidentReportUpdateSchema,
    InfectionControlLogCreateSchema,
    QualityImprovementProjectCreateSchema,
    QualityImprovementProjectUpdateSchema,
)
from app.utils.security_event_util import record_security_event


# ============================================================
# COMPLIANCE RECORD
# ============================================================


class ComplianceRecordService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ComplianceRecordRepository(db)

    def list_records(self, **kwargs):
        status = kwargs.pop("status", None)
        if status is not None:
            kwargs["status"] = ComplianceStatus(status.strip().upper())
        return self.repository.list_records(**kwargs)

    def get(self, record_id: int) -> ComplianceRecord:
        return self.repository.get_required_by_id(record_id)

    def create(
        self,
        payload: ComplianceRecordCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ComplianceRecord:
        r = self.repository.create(**payload.model_dump(exclude_unset=True))
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="COMPLIANCE_RECORD_CREATED",
            severity="INFO",
            event_detail=f"Compliance record '{r.title}' created.",
            event_metadata={"record_id": r.id, "compliance_area": r.compliance_area},
        )
        self.db.commit()
        return self.repository.get_required_by_id(r.id)

    def update(
        self,
        record_id: int,
        payload: ComplianceRecordUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ComplianceRecord:
        r = self.repository.get_required_by_id(record_id)
        previous_status = str(r.status)
        updated = self.repository.update(r, **payload.model_dump(exclude_unset=True))

        # Audit only on status changes — they're the high-signal events.
        if str(updated.status) != previous_status:
            record_security_event(
                self.db,
                user_id=actor_user_id,
                event_type=f"COMPLIANCE_STATUS_{updated.status}",
                severity="INFO",
                event_detail=f"Compliance record {updated.id} status changed.",
                event_metadata={
                    "record_id": updated.id,
                    "from_status": previous_status,
                    "to_status": str(updated.status),
                },
            )
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, record_id: int) -> ComplianceRecord:
        r = self.repository.get_required_by_id(record_id)
        r = self.repository.soft_delete(r)
        self.db.commit()
        return r


# ============================================================
# ACCREDITATION
# ============================================================


class AccreditationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AccreditationRepository(db)

    def list_accreditations(self, **kwargs):
        status = kwargs.pop("status", None)
        if status is not None:
            kwargs["status"] = AccreditationStatus(status.strip().upper())
        return self.repository.list_accreditations(**kwargs)

    def get(self, acc_id: int) -> Accreditation:
        return self.repository.get_required_by_id(acc_id)

    def create(
        self,
        payload: AccreditationCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Accreditation:
        a = self.repository.create(**payload.model_dump(exclude_unset=True))
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="ACCREDITATION_RECORDED",
            severity="INFO",
            event_detail=f"Accreditation '{a.accreditation_name}' recorded.",
            event_metadata={"accreditation_id": a.id, "expiry_date": a.expiry_date.isoformat() if a.expiry_date else None},
        )
        self.db.commit()
        return self.repository.get_required_by_id(a.id)

    def update(self, acc_id: int, payload: AccreditationUpdateSchema) -> Accreditation:
        a = self.repository.get_required_by_id(acc_id)
        updated = self.repository.update(a, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, acc_id: int) -> Accreditation:
        a = self.repository.get_required_by_id(acc_id)
        a = self.repository.soft_delete(a)
        self.db.commit()
        return a


# ============================================================
# INCIDENT REPORT (sensitive — restricted)
# ============================================================


class IncidentReportService:
    """
    Service for incident reports.

    Incidents may name patients / staff and so are gated to staff with the
    ``INCIDENT_READ`` / ``INCIDENT_MANAGE`` permissions at the route layer.
    HIGH and CRITICAL severity incidents trigger CRITICAL-severity security
    events so on-call dashboards see them immediately.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = IncidentReportRepository(db)

    def list_incidents(self, **kwargs):
        severity = kwargs.pop("severity", None)
        if severity is not None:
            kwargs["severity"] = IncidentSeverity(severity.strip().upper())
        return self.repository.list_incidents(**kwargs)

    def get(self, incident_id: int) -> IncidentReport:
        return self.repository.get_required_by_id(incident_id)

    def file_incident(
        self,
        payload: IncidentReportCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> IncidentReport:
        i = self.repository.create(**payload.model_dump(exclude_unset=True))

        # CRITICAL / HIGH incidents are surfaced as CRITICAL audit events so
        # alerting pipelines can pick them up without scanning text.
        sev = str(i.severity)
        severity_label = "CRITICAL" if sev in {"HIGH", "CRITICAL"} else "WARNING"
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INCIDENT_FILED",
            severity=severity_label,
            event_detail=f"Incident {i.incident_no} filed (severity={sev}).",
            event_metadata={
                "incident_id": i.id,
                "incident_no": i.incident_no,
                "severity": sev,
                "patient_id": i.patient_id,
                "visit_id": i.visit_id,
                "department_id": i.department_id,
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(i.id)

    def update(
        self,
        incident_id: int,
        payload: IncidentReportUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> IncidentReport:
        i = self.repository.get_required_by_id(incident_id)
        previous_severity = str(i.severity)
        updated = self.repository.update(i, **payload.model_dump(exclude_unset=True))

        # If severity changed, audit it. This is a sensitive change because
        # severity drives downstream alerting + escalation.
        if str(updated.severity) != previous_severity:
            record_security_event(
                self.db,
                user_id=actor_user_id,
                event_type="INCIDENT_SEVERITY_CHANGED",
                severity="WARNING",
                event_detail=f"Incident {updated.incident_no} severity changed.",
                event_metadata={
                    "incident_id": updated.id,
                    "from_severity": previous_severity,
                    "to_severity": str(updated.severity),
                },
            )
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)


# ============================================================
# INFECTION CONTROL
# ============================================================


class InfectionControlService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InfectionControlLogRepository(db)

    def list_logs(self, **kwargs):
        return self.repository.list_logs(**kwargs)

    def get(self, log_id: int) -> InfectionControlLog:
        return self.repository.get_required_by_id(log_id)

    def create(self, payload: InfectionControlLogCreateSchema) -> InfectionControlLog:
        l = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return l


# ============================================================
# QUALITY IMPROVEMENT
# ============================================================


class QualityImprovementProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = QualityImprovementProjectRepository(db)

    def list_projects(self, **kwargs):
        status = kwargs.pop("status", None)
        if status is not None:
            kwargs["status"] = QualityProjectStatus(status.strip().upper())
        return self.repository.list_projects(**kwargs)

    def get(self, project_id: int) -> QualityImprovementProject:
        return self.repository.get_required_by_id(project_id)

    def create(self, payload: QualityImprovementProjectCreateSchema) -> QualityImprovementProject:
        p = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(p.id)

    def update(
        self,
        project_id: int,
        payload: QualityImprovementProjectUpdateSchema,
    ) -> QualityImprovementProject:
        p = self.repository.get_required_by_id(project_id)
        updated = self.repository.update(p, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)


# ============================================================
# GOVERNANCE DASHBOARD
# ============================================================


class GovernanceDashboardService:
    """Aggregates counts across the governance entities for dashboard tiles."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.compliance_repo = ComplianceRecordRepository(db)
        self.accreditation_repo = AccreditationRepository(db)
        self.incident_repo = IncidentReportRepository(db)
        self.qi_repo = QualityImprovementProjectRepository(db)

    def snapshot(self) -> dict:
        """One read-only call returning all dashboard counts."""
        return {
            "compliance_due_soon": self.compliance_repo.count_due_within(30),
            "compliance_overdue": self.compliance_repo.count_overdue(),
            "accreditations_expiring_soon": self.accreditation_repo.count_expiring_within(90),
            "accreditations_expired": self.accreditation_repo.count_expired(),
            "incidents_open_critical": self.incident_repo.count_open_by_severity(IncidentSeverity.CRITICAL),
            "incidents_open_high": self.incident_repo.count_open_by_severity(IncidentSeverity.HIGH),
            "quality_projects_active": self.qi_repo.count_active(),
        }
