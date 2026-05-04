# app/repositories/compliance_repository.py
from __future__ import annotations

"""
Repository layer for the compliance / governance module (Stage 18).

Persists:
- ``ComplianceRecord``        — periodic compliance obligations
- ``Accreditation``           — facility / department accreditations
- ``IncidentReport``          — incidents (patient safety + operational)
- ``InfectionControlLog``     — surveillance log
- ``QualityImprovementProject`` — improvement initiatives

Repository methods are deliberately small and side-effect-free; service-layer
orchestration (alerts, dashboard aggregation, security audit) lives in
``app/services/compliance_service.py``.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import (
    AccreditationStatus,
    ComplianceStatus,
    IncidentSeverity,
    QualityProjectStatus,
)
from app.core.exceptions import NotFoundError
from app.models.all_models import (
    Accreditation,
    ComplianceRecord,
    IncidentReport,
    InfectionControlLog,
    QualityImprovementProject,
)
from app.utils.helpers import generate_uuid_str


# ============================================================
# COMPLIANCE RECORD
# ============================================================


class ComplianceRecordRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, record_id: int) -> Optional[ComplianceRecord]:
        return (
            self.db.query(ComplianceRecord)
            .filter(ComplianceRecord.id == record_id, ComplianceRecord.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, record_id: int) -> ComplianceRecord:
        r = self.get_by_id(record_id)
        if not r:
            raise NotFoundError(message="Compliance record not found.", detail={"record_id": record_id})
        return r

    def list_records(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        department_id: Optional[int] = None,
        status: Optional[ComplianceStatus] = None,
        compliance_area: Optional[str] = None,
    ) -> tuple[list[ComplianceRecord], int]:
        query = self.db.query(ComplianceRecord).filter(ComplianceRecord.is_deleted.is_(False))
        if department_id is not None:
            query = query.filter(ComplianceRecord.department_id == department_id)
        if status is not None:
            query = query.filter(ComplianceRecord.status == status)
        if compliance_area:
            query = query.filter(ComplianceRecord.compliance_area == compliance_area)
        total = query.with_entities(func.count(ComplianceRecord.id)).scalar() or 0
        items = (
            query.order_by(ComplianceRecord.due_date.asc().nullslast(), ComplianceRecord.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def count_overdue(self, *, today: Optional[date] = None) -> int:
        """Records with a due date in the past that aren't COMPLIANT."""
        d = today or datetime.now(timezone.utc).date()
        return int(
            self.db.query(func.count(ComplianceRecord.id))
            .filter(
                ComplianceRecord.is_deleted.is_(False),
                ComplianceRecord.due_date.isnot(None),
                ComplianceRecord.due_date < d,
                ComplianceRecord.status != ComplianceStatus.COMPLIANT,
            )
            .scalar()
            or 0
        )

    def count_due_within(self, days: int = 30) -> int:
        """Records with a due date in the next N days, not yet COMPLIANT."""
        today = datetime.now(timezone.utc).date()
        horizon = today + timedelta(days=days)
        return int(
            self.db.query(func.count(ComplianceRecord.id))
            .filter(
                ComplianceRecord.is_deleted.is_(False),
                ComplianceRecord.due_date.isnot(None),
                ComplianceRecord.due_date >= today,
                ComplianceRecord.due_date <= horizon,
                ComplianceRecord.status != ComplianceStatus.COMPLIANT,
            )
            .scalar()
            or 0
        )

    def create(self, **kwargs) -> ComplianceRecord:
        if isinstance(kwargs.get("status"), str):
            kwargs["status"] = ComplianceStatus(kwargs["status"])
        r = ComplianceRecord(**kwargs)
        self.db.add(r)
        self.db.flush()
        self.db.refresh(r)
        return r

    def update(self, r: ComplianceRecord, **kwargs) -> ComplianceRecord:
        if isinstance(kwargs.get("status"), str):
            kwargs["status"] = ComplianceStatus(kwargs["status"])
        for field, value in kwargs.items():
            if value is not None:
                setattr(r, field, value)
        self.db.add(r)
        self.db.flush()
        self.db.refresh(r)
        return r

    def soft_delete(self, r: ComplianceRecord) -> ComplianceRecord:
        r.is_deleted = True
        self.db.add(r)
        self.db.flush()
        return r


# ============================================================
# ACCREDITATION
# ============================================================


class AccreditationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, acc_id: int) -> Optional[Accreditation]:
        return (
            self.db.query(Accreditation)
            .filter(Accreditation.id == acc_id, Accreditation.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, acc_id: int) -> Accreditation:
        a = self.get_by_id(acc_id)
        if not a:
            raise NotFoundError(message="Accreditation not found.", detail={"accreditation_id": acc_id})
        return a

    def list_accreditations(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        department_id: Optional[int] = None,
        status: Optional[AccreditationStatus] = None,
    ) -> tuple[list[Accreditation], int]:
        query = self.db.query(Accreditation).filter(Accreditation.is_deleted.is_(False))
        if department_id is not None:
            query = query.filter(Accreditation.department_id == department_id)
        if status is not None:
            query = query.filter(Accreditation.status == status)
        total = query.with_entities(func.count(Accreditation.id)).scalar() or 0
        items = (
            query.order_by(Accreditation.expiry_date.asc().nullslast(), Accreditation.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def count_expired(self) -> int:
        today = datetime.now(timezone.utc).date()
        return int(
            self.db.query(func.count(Accreditation.id))
            .filter(
                Accreditation.is_deleted.is_(False),
                Accreditation.expiry_date.isnot(None),
                Accreditation.expiry_date < today,
            )
            .scalar()
            or 0
        )

    def count_expiring_within(self, days: int = 90) -> int:
        today = datetime.now(timezone.utc).date()
        horizon = today + timedelta(days=days)
        return int(
            self.db.query(func.count(Accreditation.id))
            .filter(
                Accreditation.is_deleted.is_(False),
                Accreditation.expiry_date.isnot(None),
                Accreditation.expiry_date >= today,
                Accreditation.expiry_date <= horizon,
            )
            .scalar()
            or 0
        )

    def create(self, **kwargs) -> Accreditation:
        if isinstance(kwargs.get("status"), str):
            kwargs["status"] = AccreditationStatus(kwargs["status"])
        a = Accreditation(**kwargs)
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a

    def update(self, a: Accreditation, **kwargs) -> Accreditation:
        if isinstance(kwargs.get("status"), str):
            kwargs["status"] = AccreditationStatus(kwargs["status"])
        for field, value in kwargs.items():
            if value is not None:
                setattr(a, field, value)
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a

    def soft_delete(self, a: Accreditation) -> Accreditation:
        a.is_deleted = True
        self.db.add(a)
        self.db.flush()
        return a


# ============================================================
# INCIDENT REPORT
# ============================================================


class IncidentReportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, incident_id: int) -> Optional[IncidentReport]:
        return (
            self.db.query(IncidentReport)
            .filter(IncidentReport.id == incident_id, IncidentReport.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, incident_id: int) -> IncidentReport:
        i = self.get_by_id(incident_id)
        if not i:
            raise NotFoundError(message="Incident report not found.", detail={"incident_id": incident_id})
        return i

    def list_incidents(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        department_id: Optional[int] = None,
        severity: Optional[IncidentSeverity] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        follow_up_required: Optional[bool] = None,
    ) -> tuple[list[IncidentReport], int]:
        query = self.db.query(IncidentReport).filter(IncidentReport.is_deleted.is_(False))
        if department_id is not None:
            query = query.filter(IncidentReport.department_id == department_id)
        if severity is not None:
            query = query.filter(IncidentReport.severity == severity)
        if from_dt is not None:
            query = query.filter(IncidentReport.incident_date >= from_dt)
        if to_dt is not None:
            query = query.filter(IncidentReport.incident_date < to_dt)
        if follow_up_required is not None:
            query = query.filter(IncidentReport.follow_up_required.is_(follow_up_required))
        total = query.with_entities(func.count(IncidentReport.id)).scalar() or 0
        items = (
            query.order_by(IncidentReport.incident_date.desc(), IncidentReport.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def count_open_by_severity(self, severity: IncidentSeverity) -> int:
        """Count incidents that still require follow-up at a given severity."""
        return int(
            self.db.query(func.count(IncidentReport.id))
            .filter(
                IncidentReport.is_deleted.is_(False),
                IncidentReport.severity == severity,
                IncidentReport.follow_up_required.is_(True),
            )
            .scalar()
            or 0
        )

    def generate_incident_no(self) -> str:
        return f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create(self, **kwargs) -> IncidentReport:
        kwargs.setdefault("incident_no", self.generate_incident_no())
        kwargs.setdefault("incident_date", datetime.now(timezone.utc))
        if isinstance(kwargs.get("severity"), str):
            kwargs["severity"] = IncidentSeverity(kwargs["severity"])
        i = IncidentReport(**kwargs)
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i

    def update(self, i: IncidentReport, **kwargs) -> IncidentReport:
        if isinstance(kwargs.get("severity"), str):
            kwargs["severity"] = IncidentSeverity(kwargs["severity"])
        for field, value in kwargs.items():
            if value is not None:
                setattr(i, field, value)
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i


# ============================================================
# INFECTION CONTROL
# ============================================================


class InfectionControlLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, log_id: int) -> Optional[InfectionControlLog]:
        return (
            self.db.query(InfectionControlLog)
            .filter(InfectionControlLog.id == log_id, InfectionControlLog.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, log_id: int) -> InfectionControlLog:
        l = self.get_by_id(log_id)
        if not l:
            raise NotFoundError(message="Infection control log not found.", detail={"log_id": log_id})
        return l

    def list_logs(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        department_id: Optional[int] = None,
        infection_type: Optional[str] = None,
    ) -> tuple[list[InfectionControlLog], int]:
        query = self.db.query(InfectionControlLog).filter(InfectionControlLog.is_deleted.is_(False))
        if department_id is not None:
            query = query.filter(InfectionControlLog.department_id == department_id)
        if infection_type:
            query = query.filter(InfectionControlLog.infection_type == infection_type)
        total = query.with_entities(func.count(InfectionControlLog.id)).scalar() or 0
        items = (
            query.order_by(InfectionControlLog.log_date.desc(), InfectionControlLog.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def create(self, **kwargs) -> InfectionControlLog:
        l = InfectionControlLog(**kwargs)
        self.db.add(l)
        self.db.flush()
        self.db.refresh(l)
        return l


# ============================================================
# QUALITY IMPROVEMENT
# ============================================================


class QualityImprovementProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, project_id: int) -> Optional[QualityImprovementProject]:
        return (
            self.db.query(QualityImprovementProject)
            .filter(
                QualityImprovementProject.id == project_id,
                QualityImprovementProject.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, project_id: int) -> QualityImprovementProject:
        p = self.get_by_id(project_id)
        if not p:
            raise NotFoundError(message="Quality project not found.", detail={"project_id": project_id})
        return p

    def list_projects(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        department_id: Optional[int] = None,
        status: Optional[QualityProjectStatus] = None,
    ) -> tuple[list[QualityImprovementProject], int]:
        query = self.db.query(QualityImprovementProject).filter(
            QualityImprovementProject.is_deleted.is_(False)
        )
        if department_id is not None:
            query = query.filter(QualityImprovementProject.department_id == department_id)
        if status is not None:
            query = query.filter(QualityImprovementProject.status == status)
        total = query.with_entities(func.count(QualityImprovementProject.id)).scalar() or 0
        items = (
            query.order_by(QualityImprovementProject.start_date.desc().nullslast(), QualityImprovementProject.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def count_active(self) -> int:
        return int(
            self.db.query(func.count(QualityImprovementProject.id))
            .filter(
                QualityImprovementProject.is_deleted.is_(False),
                QualityImprovementProject.status == QualityProjectStatus.ACTIVE,
            )
            .scalar()
            or 0
        )

    def create(self, **kwargs) -> QualityImprovementProject:
        if isinstance(kwargs.get("status"), str):
            kwargs["status"] = QualityProjectStatus(kwargs["status"])
        p = QualityImprovementProject(**kwargs)
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p

    def update(self, p: QualityImprovementProject, **kwargs) -> QualityImprovementProject:
        if isinstance(kwargs.get("status"), str):
            kwargs["status"] = QualityProjectStatus(kwargs["status"])
        for field, value in kwargs.items():
            if value is not None:
                setattr(p, field, value)
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p
