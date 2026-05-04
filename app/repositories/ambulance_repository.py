# app/repositories/ambulance_repository.py
from __future__ import annotations

"""
Repository layer for the ambulance / emergency-transport module (Stage 15).

Houses persistence-only logic for:
- Ambulance fleet master data
- AmbulanceDriver, AmbulanceEquipment, AmbulanceMaintenance, AmbulanceDispatch
- AmbulanceIncidentReport

Service-layer rules (readiness, dispatch lifecycle, incident triage) live in
``app/services/ambulance_service.py``.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.enums import (
    AmbulanceDispatchStatus,
    AmbulanceStatus,
    IncidentSeverity,
    MaintenanceStatus,
)
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import (
    Ambulance,
    AmbulanceDispatch,
    AmbulanceDriver,
    AmbulanceEquipment,
    AmbulanceIncidentReport,
    AmbulanceMaintenance,
)
from app.utils.helpers import generate_uuid_str


# ============================================================
# AMBULANCE
# ============================================================


class AmbulanceRepository:
    """Persistence helpers for the Ambulance fleet."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, ambulance_id: int) -> Optional[Ambulance]:
        return (
            self.db.query(Ambulance)
            .filter(Ambulance.id == ambulance_id, Ambulance.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, ambulance_id: int) -> Ambulance:
        a = self.get_by_id(ambulance_id)
        if not a:
            raise NotFoundError(message="Ambulance not found.", detail={"ambulance_id": ambulance_id})
        return a

    def get_by_code(self, code: str) -> Optional[Ambulance]:
        return (
            self.db.query(Ambulance)
            .filter(
                Ambulance.code == code.strip().upper(),
                Ambulance.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_plate(self, plate: str) -> Optional[Ambulance]:
        return (
            self.db.query(Ambulance)
            .filter(
                Ambulance.plate_number == plate.strip().upper(),
                Ambulance.is_deleted.is_(False),
            )
            .first()
        )

    def list_ambulances(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        status: Optional[AmbulanceStatus] = None,
    ) -> tuple[list[Ambulance], int]:
        query = self.db.query(Ambulance).filter(Ambulance.is_deleted.is_(False))
        if status is not None:
            query = query.filter(Ambulance.status == status)
        total = query.with_entities(func.count(Ambulance.id)).scalar() or 0
        items = (
            query.order_by(Ambulance.code.asc()).offset(skip).limit(limit).all()
        )
        return items, int(total)

    def create(self, **kwargs) -> Ambulance:
        # Defensive uniqueness checks. The DB unique constraints would raise
        # the same error, but our message is friendlier to API consumers.
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(message="Ambulance code already in use.", detail={"code": kwargs["code"]})
        if self.get_by_plate(kwargs["plate_number"]):
            raise AlreadyExistsError(
                message="Plate number already in use.",
                detail={"plate_number": kwargs["plate_number"]},
            )
        a = Ambulance(**kwargs)
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a

    def update(self, a: Ambulance, **kwargs) -> Ambulance:
        for field, value in kwargs.items():
            if value is not None:
                setattr(a, field, value)
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a

    def soft_delete(self, a: Ambulance) -> Ambulance:
        a.is_deleted = True
        self.db.add(a)
        self.db.flush()
        return a


# ============================================================
# DRIVER
# ============================================================


class AmbulanceDriverRepository:
    """Persistence helpers for AmbulanceDriver."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, driver_id: int) -> Optional[AmbulanceDriver]:
        return (
            self.db.query(AmbulanceDriver)
            .filter(AmbulanceDriver.id == driver_id, AmbulanceDriver.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, driver_id: int) -> AmbulanceDriver:
        d = self.get_by_id(driver_id)
        if not d:
            raise NotFoundError(message="Ambulance driver not found.", detail={"driver_id": driver_id})
        return d

    def get_by_license(self, license_no: str) -> Optional[AmbulanceDriver]:
        return (
            self.db.query(AmbulanceDriver)
            .filter(
                AmbulanceDriver.driver_license_no == license_no.strip().upper(),
                AmbulanceDriver.is_deleted.is_(False),
            )
            .first()
        )

    def list_drivers(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        ambulance_id: Optional[int] = None,
    ) -> tuple[list[AmbulanceDriver], int]:
        query = self.db.query(AmbulanceDriver).filter(AmbulanceDriver.is_deleted.is_(False))
        if ambulance_id is not None:
            query = query.filter(AmbulanceDriver.ambulance_id == ambulance_id)
        total = query.with_entities(func.count(AmbulanceDriver.id)).scalar() or 0
        items = (
            query.order_by(AmbulanceDriver.is_primary_driver.desc(), AmbulanceDriver.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def list_for_ambulance(self, ambulance_id: int) -> list[AmbulanceDriver]:
        return (
            self.db.query(AmbulanceDriver)
            .filter(
                AmbulanceDriver.ambulance_id == ambulance_id,
                AmbulanceDriver.is_deleted.is_(False),
            )
            .all()
        )

    def primary_driver_for(self, ambulance_id: int) -> Optional[AmbulanceDriver]:
        return (
            self.db.query(AmbulanceDriver)
            .filter(
                AmbulanceDriver.ambulance_id == ambulance_id,
                AmbulanceDriver.is_deleted.is_(False),
                AmbulanceDriver.is_primary_driver.is_(True),
            )
            .first()
        )

    def create(self, **kwargs) -> AmbulanceDriver:
        if self.get_by_license(kwargs["driver_license_no"]):
            raise AlreadyExistsError(
                message="Driver license number already registered.",
                detail={"driver_license_no": kwargs["driver_license_no"]},
            )
        d = AmbulanceDriver(**kwargs)
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d

    def update(self, d: AmbulanceDriver, **kwargs) -> AmbulanceDriver:
        for field, value in kwargs.items():
            if value is not None:
                setattr(d, field, value)
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d

    def soft_delete(self, d: AmbulanceDriver) -> AmbulanceDriver:
        d.is_deleted = True
        self.db.add(d)
        self.db.flush()
        return d


# ============================================================
# EQUIPMENT
# ============================================================


class AmbulanceEquipmentRepository:
    """Persistence helpers for AmbulanceEquipment."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, eq_id: int) -> Optional[AmbulanceEquipment]:
        return (
            self.db.query(AmbulanceEquipment)
            .filter(
                AmbulanceEquipment.id == eq_id,
                AmbulanceEquipment.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, eq_id: int) -> AmbulanceEquipment:
        e = self.get_by_id(eq_id)
        if not e:
            raise NotFoundError(message="Equipment item not found.", detail={"equipment_id": eq_id})
        return e

    def list_for_ambulance(self, ambulance_id: int) -> list[AmbulanceEquipment]:
        return (
            self.db.query(AmbulanceEquipment)
            .filter(
                AmbulanceEquipment.ambulance_id == ambulance_id,
                AmbulanceEquipment.is_deleted.is_(False),
            )
            .order_by(AmbulanceEquipment.equipment_name.asc())
            .all()
        )

    def list_expired_for_ambulance(self, ambulance_id: int) -> list[AmbulanceEquipment]:
        """Equipment whose expiry_date has passed (used for readiness check)."""
        today = datetime.now(timezone.utc).date()
        return (
            self.db.query(AmbulanceEquipment)
            .filter(
                AmbulanceEquipment.ambulance_id == ambulance_id,
                AmbulanceEquipment.is_deleted.is_(False),
                AmbulanceEquipment.expiry_date.isnot(None),
                AmbulanceEquipment.expiry_date < today,
            )
            .all()
        )

    def create(self, **kwargs) -> AmbulanceEquipment:
        e = AmbulanceEquipment(**kwargs)
        self.db.add(e)
        self.db.flush()
        self.db.refresh(e)
        return e

    def update(self, e: AmbulanceEquipment, **kwargs) -> AmbulanceEquipment:
        for field, value in kwargs.items():
            if value is not None:
                setattr(e, field, value)
        self.db.add(e)
        self.db.flush()
        self.db.refresh(e)
        return e

    def soft_delete(self, e: AmbulanceEquipment) -> AmbulanceEquipment:
        e.is_deleted = True
        self.db.add(e)
        self.db.flush()
        return e


# ============================================================
# MAINTENANCE
# ============================================================


class AmbulanceMaintenanceRepository:
    """Persistence helpers for AmbulanceMaintenance."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, m_id: int) -> Optional[AmbulanceMaintenance]:
        return (
            self.db.query(AmbulanceMaintenance)
            .filter(
                AmbulanceMaintenance.id == m_id,
                AmbulanceMaintenance.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, m_id: int) -> AmbulanceMaintenance:
        m = self.get_by_id(m_id)
        if not m:
            raise NotFoundError(message="Maintenance record not found.", detail={"maintenance_id": m_id})
        return m

    def list_for_ambulance(self, ambulance_id: int) -> list[AmbulanceMaintenance]:
        return (
            self.db.query(AmbulanceMaintenance)
            .filter(
                AmbulanceMaintenance.ambulance_id == ambulance_id,
                AmbulanceMaintenance.is_deleted.is_(False),
            )
            .order_by(AmbulanceMaintenance.maintenance_date.desc())
            .all()
        )

    def list_open_for_ambulance(self, ambulance_id: int) -> list[AmbulanceMaintenance]:
        """Open maintenance is anything still SCHEDULED or IN_PROGRESS."""
        return (
            self.db.query(AmbulanceMaintenance)
            .filter(
                AmbulanceMaintenance.ambulance_id == ambulance_id,
                AmbulanceMaintenance.is_deleted.is_(False),
                AmbulanceMaintenance.maintenance_status.in_(
                    [MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS]
                ),
            )
            .all()
        )

    def create(self, **kwargs) -> AmbulanceMaintenance:
        m = AmbulanceMaintenance(**kwargs)
        self.db.add(m)
        self.db.flush()
        self.db.refresh(m)
        return m

    def update(self, m: AmbulanceMaintenance, **kwargs) -> AmbulanceMaintenance:
        for field, value in kwargs.items():
            if value is not None:
                setattr(m, field, value)
        self.db.add(m)
        self.db.flush()
        self.db.refresh(m)
        return m


# ============================================================
# DISPATCH
# ============================================================


class AmbulanceDispatchRepository:
    """Persistence helpers for AmbulanceDispatch."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, dispatch_id: int) -> Optional[AmbulanceDispatch]:
        return (
            self.db.query(AmbulanceDispatch)
            .options(selectinload(AmbulanceDispatch.incident_reports))
            .filter(
                AmbulanceDispatch.id == dispatch_id,
                AmbulanceDispatch.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, dispatch_id: int) -> AmbulanceDispatch:
        d = self.get_by_id(dispatch_id)
        if not d:
            raise NotFoundError(message="Dispatch not found.", detail={"dispatch_id": dispatch_id})
        return d

    def list_dispatches(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        ambulance_id: Optional[int] = None,
        status: Optional[AmbulanceDispatchStatus] = None,
        active_only: bool = False,
    ) -> tuple[list[AmbulanceDispatch], int]:
        query = self.db.query(AmbulanceDispatch).filter(
            AmbulanceDispatch.is_deleted.is_(False)
        )
        if ambulance_id is not None:
            query = query.filter(AmbulanceDispatch.ambulance_id == ambulance_id)
        if status is not None:
            query = query.filter(AmbulanceDispatch.dispatch_status == status)
        if active_only:
            query = query.filter(
                AmbulanceDispatch.dispatch_status.in_(
                    [
                        AmbulanceDispatchStatus.PENDING,
                        AmbulanceDispatchStatus.ASSIGNED,
                        AmbulanceDispatchStatus.EN_ROUTE,
                        AmbulanceDispatchStatus.ARRIVED,
                        AmbulanceDispatchStatus.PATIENT_PICKED,
                    ]
                )
            )
        total = query.with_entities(func.count(AmbulanceDispatch.id)).scalar() or 0
        items = (
            query.order_by(AmbulanceDispatch.requested_at.desc(), AmbulanceDispatch.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def has_active_for_ambulance(self, ambulance_id: int) -> bool:
        """True when an ambulance is currently mid-dispatch (cannot be re-dispatched)."""
        return bool(
            self.db.query(AmbulanceDispatch.id)
            .filter(
                AmbulanceDispatch.ambulance_id == ambulance_id,
                AmbulanceDispatch.is_deleted.is_(False),
                AmbulanceDispatch.dispatch_status.in_(
                    [
                        AmbulanceDispatchStatus.ASSIGNED,
                        AmbulanceDispatchStatus.EN_ROUTE,
                        AmbulanceDispatchStatus.ARRIVED,
                        AmbulanceDispatchStatus.PATIENT_PICKED,
                    ]
                ),
            )
            .first()
        )

    def generate_dispatch_no(self) -> str:
        return f"DSP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create(self, **kwargs) -> AmbulanceDispatch:
        kwargs.setdefault("dispatch_no", self.generate_dispatch_no())
        d = AmbulanceDispatch(**kwargs)
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d

    def save(self, d: AmbulanceDispatch) -> AmbulanceDispatch:
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d


# ============================================================
# INCIDENT REPORT
# ============================================================


class AmbulanceIncidentReportRepository:
    """Persistence helpers for AmbulanceIncidentReport."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, incident_id: int) -> Optional[AmbulanceIncidentReport]:
        return (
            self.db.query(AmbulanceIncidentReport)
            .filter(
                AmbulanceIncidentReport.id == incident_id,
                AmbulanceIncidentReport.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, incident_id: int) -> AmbulanceIncidentReport:
        i = self.get_by_id(incident_id)
        if not i:
            raise NotFoundError(message="Incident report not found.", detail={"incident_id": incident_id})
        return i

    def list_for_dispatch(self, dispatch_id: int) -> list[AmbulanceIncidentReport]:
        return (
            self.db.query(AmbulanceIncidentReport)
            .filter(
                AmbulanceIncidentReport.dispatch_id == dispatch_id,
                AmbulanceIncidentReport.is_deleted.is_(False),
            )
            .order_by(AmbulanceIncidentReport.incident_date.desc())
            .all()
        )

    def create(self, **kwargs) -> AmbulanceIncidentReport:
        if isinstance(kwargs.get("severity"), str):
            kwargs["severity"] = IncidentSeverity(kwargs["severity"])
        i = AmbulanceIncidentReport(**kwargs)
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i
