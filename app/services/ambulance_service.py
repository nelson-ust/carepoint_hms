# app/services/ambulance_service.py
from __future__ import annotations

"""
Service layer for the ambulance / emergency-transport module (Stage 15).

Responsibilities
----------------
- Fleet master-data operations.
- Driver assignment + license validity tracking.
- Equipment assignment + expiry tracking.
- Maintenance lifecycle (SCHEDULED → IN_PROGRESS → COMPLETED / CANCELLED).
- Dispatch lifecycle (PENDING → ASSIGNED → EN_ROUTE → ARRIVED →
  PATIENT_PICKED → COMPLETED, with CANCELLED as a terminal escape hatch).
- Readiness computation (status + drivers + equipment + maintenance).
- Incident reports tied to dispatches.

Auditing
--------
Every state-changing operation emits a SecurityEvent so on-call dashboards
can correlate clinical / operational changes with the audit trail.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    AmbulanceDispatchStatus,
    AmbulanceStatus,
    MaintenanceStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    Ambulance,
    AmbulanceDispatch,
    AmbulanceDriver,
    AmbulanceEquipment,
    AmbulanceIncidentReport,
    AmbulanceMaintenance,
)
from app.repositories.ambulance_repository import (
    AmbulanceDispatchRepository,
    AmbulanceDriverRepository,
    AmbulanceEquipmentRepository,
    AmbulanceIncidentReportRepository,
    AmbulanceMaintenanceRepository,
    AmbulanceRepository,
)
from app.schemas.ambulance_schemas import (
    AmbulanceCreateSchema,
    AmbulanceDispatchAssignSchema,
    AmbulanceDispatchCreateSchema,
    AmbulanceDispatchTransitionSchema,
    AmbulanceDriverCreateSchema,
    AmbulanceDriverUpdateSchema,
    AmbulanceEquipmentCreateSchema,
    AmbulanceEquipmentUpdateSchema,
    AmbulanceIncidentReportCreateSchema,
    AmbulanceMaintenanceCreateSchema,
    AmbulanceMaintenanceUpdateSchema,
    AmbulanceStatusUpdateSchema,
    AmbulanceUpdateSchema,
)
from app.utils.security_event_util import record_security_event


class AmbulanceService:
    """Top-level service for fleet + dispatch operations."""

    def __init__(self, db: Session) -> None:
        # Repositories share the same session so transactions stay atomic.
        self.db = db
        self.repository = AmbulanceRepository(db)
        self.driver_repository = AmbulanceDriverRepository(db)
        self.equipment_repository = AmbulanceEquipmentRepository(db)
        self.maintenance_repository = AmbulanceMaintenanceRepository(db)
        self.dispatch_repository = AmbulanceDispatchRepository(db)
        self.incident_repository = AmbulanceIncidentReportRepository(db)

    # ============================================================
    # FLEET CRUD
    # ============================================================

    def list_ambulances(self, *, skip=0, limit=50, status: Optional[str] = None):
        status_enum = AmbulanceStatus(status.strip().upper()) if status else None
        return self.repository.list_ambulances(skip=skip, limit=limit, status=status_enum)

    def get(self, ambulance_id: int) -> Ambulance:
        return self.repository.get_required_by_id(ambulance_id)

    def create(self, payload: AmbulanceCreateSchema) -> Ambulance:
        a = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(a.id)

    def update(self, ambulance_id: int, payload: AmbulanceUpdateSchema) -> Ambulance:
        a = self.repository.get_required_by_id(ambulance_id)
        updated = self.repository.update(a, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def update_status(
        self,
        ambulance_id: int,
        payload: AmbulanceStatusUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Ambulance:
        """Manually move an ambulance to AVAILABLE / OUT_OF_SERVICE / etc."""
        a = self.repository.get_required_by_id(ambulance_id)
        new_status = AmbulanceStatus(payload.new_status)

        # Refuse a manual transition into AVAILABLE while dispatch is mid-flight.
        if (
            new_status == AmbulanceStatus.AVAILABLE
            and self.dispatch_repository.has_active_for_ambulance(a.id)
        ):
            raise BadRequestError(
                message="Cannot mark ambulance AVAILABLE while it has an active dispatch.",
                detail={"ambulance_id": a.id},
            )

        previous = a.status
        a.status = new_status
        self.repository.update(a)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type=f"AMBULANCE_STATUS_{new_status}",
            severity="INFO",
            event_detail=f"Ambulance {a.code} moved from {previous} to {new_status}.",
            event_metadata={"ambulance_id": a.id, "reason": payload.reason},
        )
        self.db.commit()
        return self.repository.get_required_by_id(a.id)

    def soft_delete(self, ambulance_id: int) -> Ambulance:
        a = self.repository.get_required_by_id(ambulance_id)
        if self.dispatch_repository.has_active_for_ambulance(a.id):
            raise BadRequestError(
                message="Cannot retire an ambulance with active dispatches.",
                detail={"ambulance_id": a.id},
            )
        a = self.repository.soft_delete(a)
        self.db.commit()
        return a

    # ============================================================
    # DRIVERS
    # ============================================================

    def list_drivers(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        ambulance_id: Optional[int] = None,
    ):
        return self.driver_repository.list_drivers(skip=skip, limit=limit, ambulance_id=ambulance_id)

    def create_driver(self, payload: AmbulanceDriverCreateSchema) -> AmbulanceDriver:
        if payload.ambulance_id is not None:
            # Existence check; helpful 404 vs FK error.
            self.repository.get_required_by_id(payload.ambulance_id)
        # If marked primary, demote any existing primary on the same ambulance.
        if payload.is_primary_driver and payload.ambulance_id is not None:
            existing_primary = self.driver_repository.primary_driver_for(payload.ambulance_id)
            if existing_primary is not None:
                existing_primary.is_primary_driver = False
                self.driver_repository.update(existing_primary)

        d = self.driver_repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.driver_repository.get_required_by_id(d.id)

    def update_driver(
        self,
        driver_id: int,
        payload: AmbulanceDriverUpdateSchema,
    ) -> AmbulanceDriver:
        d = self.driver_repository.get_required_by_id(driver_id)
        updates = payload.model_dump(exclude_unset=True)

        # Reassignment guards: if moving to a new ambulance, validate it.
        new_amb_id = updates.get("ambulance_id")
        if new_amb_id is not None and new_amb_id != d.ambulance_id:
            self.repository.get_required_by_id(new_amb_id)
        # If promoted to primary, demote the current primary on the target.
        if updates.get("is_primary_driver") and (new_amb_id or d.ambulance_id):
            target_amb = new_amb_id or d.ambulance_id
            existing = self.driver_repository.primary_driver_for(target_amb)
            if existing is not None and existing.id != d.id:
                existing.is_primary_driver = False
                self.driver_repository.update(existing)

        updated = self.driver_repository.update(d, **updates)
        self.db.commit()
        return self.driver_repository.get_required_by_id(updated.id)

    def soft_delete_driver(self, driver_id: int) -> AmbulanceDriver:
        d = self.driver_repository.get_required_by_id(driver_id)
        d = self.driver_repository.soft_delete(d)
        self.db.commit()
        return d

    # ============================================================
    # EQUIPMENT
    # ============================================================

    def list_equipment(self, ambulance_id: int) -> list[AmbulanceEquipment]:
        # Ensures the ambulance exists for clean 404 semantics.
        self.repository.get_required_by_id(ambulance_id)
        return self.equipment_repository.list_for_ambulance(ambulance_id)

    def add_equipment(self, payload: AmbulanceEquipmentCreateSchema) -> AmbulanceEquipment:
        self.repository.get_required_by_id(payload.ambulance_id)
        e = self.equipment_repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.equipment_repository.get_required_by_id(e.id)

    def update_equipment(
        self,
        equipment_id: int,
        payload: AmbulanceEquipmentUpdateSchema,
    ) -> AmbulanceEquipment:
        e = self.equipment_repository.get_required_by_id(equipment_id)
        updated = self.equipment_repository.update(e, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.equipment_repository.get_required_by_id(updated.id)

    def soft_delete_equipment(self, equipment_id: int) -> AmbulanceEquipment:
        e = self.equipment_repository.get_required_by_id(equipment_id)
        e = self.equipment_repository.soft_delete(e)
        self.db.commit()
        return e

    # ============================================================
    # MAINTENANCE
    # ============================================================

    def list_maintenance(self, ambulance_id: int) -> list[AmbulanceMaintenance]:
        self.repository.get_required_by_id(ambulance_id)
        return self.maintenance_repository.list_for_ambulance(ambulance_id)

    def schedule_maintenance(
        self,
        payload: AmbulanceMaintenanceCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> AmbulanceMaintenance:
        a = self.repository.get_required_by_id(payload.ambulance_id)
        m = self.maintenance_repository.create(**payload.model_dump(exclude_unset=True))

        # Best-practice: when scheduling, mark vehicle UNDER_MAINTENANCE if not
        # currently dispatched. Operators can still flip back later.
        if not self.dispatch_repository.has_active_for_ambulance(a.id):
            a.status = AmbulanceStatus.UNDER_MAINTENANCE
            self.repository.update(a)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="AMBULANCE_MAINTENANCE_SCHEDULED",
            severity="INFO",
            event_detail=f"Maintenance scheduled for ambulance {a.code}.",
            event_metadata={"ambulance_id": a.id, "maintenance_id": m.id},
        )
        self.db.commit()
        return self.maintenance_repository.get_required_by_id(m.id)

    def update_maintenance(
        self,
        maintenance_id: int,
        payload: AmbulanceMaintenanceUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> AmbulanceMaintenance:
        m = self.maintenance_repository.get_required_by_id(maintenance_id)
        new_status = payload.maintenance_status

        updates = payload.model_dump(exclude_unset=True)
        if new_status is not None:
            updates["maintenance_status"] = MaintenanceStatus(new_status)
        m = self.maintenance_repository.update(m, **updates)

        # When marking COMPLETED, automatically restore ambulance availability
        # if no other open maintenance and no active dispatch.
        if new_status == "COMPLETED":
            still_open = self.maintenance_repository.list_open_for_ambulance(m.ambulance_id)
            if not still_open:
                a = self.repository.get_required_by_id(m.ambulance_id)
                if not self.dispatch_repository.has_active_for_ambulance(a.id):
                    a.status = AmbulanceStatus.AVAILABLE
                    self.repository.update(a)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type=f"AMBULANCE_MAINTENANCE_{new_status or 'UPDATED'}",
            severity="INFO",
            event_detail=f"Maintenance {m.id} updated.",
            event_metadata={"maintenance_id": m.id, "ambulance_id": m.ambulance_id},
        )
        self.db.commit()
        return self.maintenance_repository.get_required_by_id(m.id)

    # ============================================================
    # READINESS
    # ============================================================

    def compute_readiness(self, ambulance_id: int) -> dict:
        """
        Derived readiness state. ``ready=True`` only when every check passes.

        Reasons returned in the response let the dispatcher fix the gap
        before paging the next nearest ambulance.
        """
        a = self.repository.get_required_by_id(ambulance_id)
        reasons: list[str] = []

        if a.status != AmbulanceStatus.AVAILABLE:
            reasons.append(f"Status is {a.status} (must be AVAILABLE).")

        # Drivers: at least one assigned + non-expired license.
        drivers = self.driver_repository.list_for_ambulance(ambulance_id)
        primary = next((d for d in drivers if d.is_primary_driver), None)
        today = datetime.now(timezone.utc).date()
        if not drivers:
            reasons.append("No driver assigned.")
        else:
            valid_drivers = [
                d for d in drivers
                if d.license_expiry_date is None or d.license_expiry_date >= today
            ]
            if not valid_drivers:
                reasons.append("All drivers have expired licenses.")

        # Equipment expiry.
        expired = self.equipment_repository.list_expired_for_ambulance(ambulance_id)
        if expired:
            reasons.append(f"{len(expired)} equipment item(s) past expiry.")

        # Open maintenance.
        open_maint = self.maintenance_repository.list_open_for_ambulance(ambulance_id)
        if open_maint:
            reasons.append(f"{len(open_maint)} open maintenance record(s).")

        return {
            "ambulance_id": a.id,
            "ready": not reasons,
            "reasons": reasons,
            "primary_driver_id": primary.id if primary else None,
            "expired_equipment_ids": [e.id for e in expired],
            "open_maintenance_ids": [m.id for m in open_maint],
        }

    # ============================================================
    # DISPATCH
    # ============================================================

    def list_dispatches(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        ambulance_id: Optional[int] = None,
        status: Optional[str] = None,
        active_only: bool = False,
    ):
        status_enum = AmbulanceDispatchStatus(status.strip().upper()) if status else None
        return self.dispatch_repository.list_dispatches(
            skip=skip, limit=limit,
            ambulance_id=ambulance_id, status=status_enum, active_only=active_only,
        )

    def get_dispatch(self, dispatch_id: int) -> AmbulanceDispatch:
        return self.dispatch_repository.get_required_by_id(dispatch_id)

    def create_dispatch(
        self,
        payload: AmbulanceDispatchCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> AmbulanceDispatch:
        """
        Open a new dispatch ticket.

        - With ambulance_id supplied: status starts at ASSIGNED and the
          ambulance is moved to DISPATCHED.
        - Without ambulance_id: status starts at PENDING (awaiting assignment).
        """
        ambulance: Optional[Ambulance] = None
        driver: Optional[AmbulanceDriver] = None

        if payload.ambulance_id is not None:
            ambulance = self.repository.get_required_by_id(payload.ambulance_id)
            if self.dispatch_repository.has_active_for_ambulance(ambulance.id):
                raise BadRequestError(
                    message="Ambulance already has an active dispatch.",
                    detail={"ambulance_id": ambulance.id},
                )
            if ambulance.status not in {AmbulanceStatus.AVAILABLE, AmbulanceStatus.DISPATCHED}:
                raise BadRequestError(
                    message="Ambulance is not in a dispatchable state.",
                    detail={"ambulance_id": ambulance.id, "status": str(ambulance.status)},
                )

        if payload.driver_id is not None:
            driver = self.driver_repository.get_required_by_id(payload.driver_id)
            # Driver must already be assigned to the named ambulance.
            if (
                ambulance is not None
                and driver.ambulance_id is not None
                and driver.ambulance_id != ambulance.id
            ):
                raise BadRequestError(
                    message="Driver is assigned to a different ambulance.",
                    detail={"driver_id": driver.id, "ambulance_id": ambulance.id},
                )

        # Persist the dispatch row. The ambulance_id column is NOT NULL on the
        # model, so we require it at creation time when omitted.
        if payload.ambulance_id is None:
            raise BadRequestError(
                message="ambulance_id is required at dispatch creation; assign later via assignment endpoint.",
            )

        requested_at = payload.requested_at or datetime.now(timezone.utc)
        initial_status = (
            AmbulanceDispatchStatus.ASSIGNED
            if payload.ambulance_id and payload.driver_id
            else AmbulanceDispatchStatus.PENDING
        )

        d = self.dispatch_repository.create(
            ambulance_id=payload.ambulance_id,
            driver_id=payload.driver_id,
            patient_id=payload.patient_id,
            visit_id=payload.visit_id,
            dispatch_status=initial_status,
            pickup_location=payload.pickup_location,
            destination_location=payload.destination_location,
            incident_description=payload.incident_description,
            requested_at=requested_at,
            assigned_at=datetime.now(timezone.utc) if initial_status == AmbulanceDispatchStatus.ASSIGNED else None,
        )

        # Mark ambulance as DISPATCHED when an actual driver was attached.
        if ambulance is not None and initial_status == AmbulanceDispatchStatus.ASSIGNED:
            ambulance.status = AmbulanceStatus.DISPATCHED
            self.repository.update(ambulance)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="AMBULANCE_DISPATCH_CREATED",
            severity="WARNING",
            event_detail=f"Dispatch {d.dispatch_no} opened.",
            event_metadata={
                "dispatch_id": d.id,
                "ambulance_id": d.ambulance_id,
                "driver_id": d.driver_id,
                "patient_id": d.patient_id,
                "visit_id": d.visit_id,
            },
        )
        self.db.commit()
        return self.dispatch_repository.get_required_by_id(d.id)

    def assign_dispatch(
        self,
        dispatch_id: int,
        payload: AmbulanceDispatchAssignSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> AmbulanceDispatch:
        """Move PENDING → ASSIGNED."""
        d = self.dispatch_repository.get_required_by_id(dispatch_id)
        if d.dispatch_status not in {AmbulanceDispatchStatus.PENDING}:
            raise BadRequestError(
                message="Only PENDING dispatches can be assigned.",
                detail={"status": str(d.dispatch_status)},
            )
        ambulance = self.repository.get_required_by_id(payload.ambulance_id)
        if self.dispatch_repository.has_active_for_ambulance(ambulance.id):
            raise BadRequestError(
                message="Target ambulance already has an active dispatch.",
                detail={"ambulance_id": ambulance.id},
            )
        if payload.driver_id is not None:
            self.driver_repository.get_required_by_id(payload.driver_id)

        d.ambulance_id = ambulance.id
        d.driver_id = payload.driver_id
        d.dispatch_status = AmbulanceDispatchStatus.ASSIGNED
        d.assigned_at = datetime.now(timezone.utc)
        self.dispatch_repository.save(d)

        ambulance.status = AmbulanceStatus.DISPATCHED
        self.repository.update(ambulance)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="AMBULANCE_DISPATCH_ASSIGNED",
            severity="INFO",
            event_detail=f"Dispatch {d.dispatch_no} assigned.",
            event_metadata={"dispatch_id": d.id, "ambulance_id": ambulance.id, "driver_id": payload.driver_id},
        )
        self.db.commit()
        return self.dispatch_repository.get_required_by_id(d.id)

    def _transition_dispatch(
        self,
        dispatch_id: int,
        *,
        new_status: AmbulanceDispatchStatus,
        valid_from: set[AmbulanceDispatchStatus],
        timestamp_field: Optional[str],
        ambulance_status: Optional[AmbulanceStatus],
        event_type: str,
        actor_user_id: Optional[int],
    ) -> AmbulanceDispatch:
        """
        Generic helper for the dispatch lifecycle transitions.

        Centralizes the validation + audit pattern so the public methods
        below stay declarative.
        """
        d = self.dispatch_repository.get_required_by_id(dispatch_id)
        if d.dispatch_status not in valid_from:
            raise BadRequestError(
                message=f"Dispatch must be in {sorted(s.value for s in valid_from)} to perform this transition.",
                detail={"status": str(d.dispatch_status), "target": str(new_status)},
            )

        d.dispatch_status = new_status
        if timestamp_field is not None:
            setattr(d, timestamp_field, datetime.now(timezone.utc))
        self.dispatch_repository.save(d)

        # Mirror change to the ambulance's operational status when relevant.
        if ambulance_status is not None and d.ambulance_id is not None:
            a = self.repository.get_required_by_id(d.ambulance_id)
            a.status = ambulance_status
            self.repository.update(a)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type=event_type,
            severity="INFO",
            event_detail=f"Dispatch {d.dispatch_no} -> {new_status.value}.",
            event_metadata={"dispatch_id": d.id},
        )
        self.db.commit()
        return self.dispatch_repository.get_required_by_id(d.id)

    def depart_dispatch(
        self, dispatch_id: int, payload: AmbulanceDispatchTransitionSchema, *, actor_user_id=None,
    ) -> AmbulanceDispatch:
        """ASSIGNED → EN_ROUTE."""
        return self._transition_dispatch(
            dispatch_id,
            new_status=AmbulanceDispatchStatus.EN_ROUTE,
            valid_from={AmbulanceDispatchStatus.ASSIGNED},
            timestamp_field="departed_at",
            ambulance_status=AmbulanceStatus.IN_TRANSIT,
            event_type="AMBULANCE_DISPATCH_DEPARTED",
            actor_user_id=actor_user_id,
        )

    def arrive_dispatch(
        self, dispatch_id: int, payload: AmbulanceDispatchTransitionSchema, *, actor_user_id=None,
    ) -> AmbulanceDispatch:
        """EN_ROUTE → ARRIVED."""
        return self._transition_dispatch(
            dispatch_id,
            new_status=AmbulanceDispatchStatus.ARRIVED,
            valid_from={AmbulanceDispatchStatus.EN_ROUTE},
            timestamp_field="arrived_at",
            ambulance_status=None,
            event_type="AMBULANCE_DISPATCH_ARRIVED",
            actor_user_id=actor_user_id,
        )

    def patient_picked_dispatch(
        self, dispatch_id: int, payload: AmbulanceDispatchTransitionSchema, *, actor_user_id=None,
    ) -> AmbulanceDispatch:
        """ARRIVED → PATIENT_PICKED."""
        return self._transition_dispatch(
            dispatch_id,
            new_status=AmbulanceDispatchStatus.PATIENT_PICKED,
            valid_from={AmbulanceDispatchStatus.ARRIVED},
            timestamp_field=None,
            ambulance_status=AmbulanceStatus.IN_TRANSIT,
            event_type="AMBULANCE_DISPATCH_PATIENT_PICKED",
            actor_user_id=actor_user_id,
        )

    def complete_dispatch(
        self, dispatch_id: int, payload: AmbulanceDispatchTransitionSchema, *, actor_user_id=None,
    ) -> AmbulanceDispatch:
        """PATIENT_PICKED / ARRIVED → COMPLETED + ambulance back to AVAILABLE."""
        return self._transition_dispatch(
            dispatch_id,
            new_status=AmbulanceDispatchStatus.COMPLETED,
            valid_from={
                AmbulanceDispatchStatus.PATIENT_PICKED,
                AmbulanceDispatchStatus.ARRIVED,
            },
            timestamp_field="completed_at",
            ambulance_status=AmbulanceStatus.AVAILABLE,
            event_type="AMBULANCE_DISPATCH_COMPLETED",
            actor_user_id=actor_user_id,
        )

    def cancel_dispatch(
        self, dispatch_id: int, payload: AmbulanceDispatchTransitionSchema, *, actor_user_id=None,
    ) -> AmbulanceDispatch:
        """Any non-terminal → CANCELLED + ambulance back to AVAILABLE."""
        return self._transition_dispatch(
            dispatch_id,
            new_status=AmbulanceDispatchStatus.CANCELLED,
            valid_from={
                AmbulanceDispatchStatus.PENDING,
                AmbulanceDispatchStatus.ASSIGNED,
                AmbulanceDispatchStatus.EN_ROUTE,
                AmbulanceDispatchStatus.ARRIVED,
                AmbulanceDispatchStatus.PATIENT_PICKED,
            },
            timestamp_field="completed_at",
            ambulance_status=AmbulanceStatus.AVAILABLE,
            event_type="AMBULANCE_DISPATCH_CANCELLED",
            actor_user_id=actor_user_id,
        )

    # ============================================================
    # INCIDENT REPORTS
    # ============================================================

    def list_incidents(self, dispatch_id: int) -> list[AmbulanceIncidentReport]:
        # Existence check yields a clean 404 if the dispatch is missing.
        self.dispatch_repository.get_required_by_id(dispatch_id)
        return self.incident_repository.list_for_dispatch(dispatch_id)

    def file_incident(
        self,
        payload: AmbulanceIncidentReportCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> AmbulanceIncidentReport:
        d = self.dispatch_repository.get_required_by_id(payload.dispatch_id)
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("incident_date", datetime.now(timezone.utc))

        i = self.incident_repository.create(**data)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="AMBULANCE_INCIDENT_FILED",
            severity="WARNING",
            event_detail=f"Incident filed against dispatch {d.dispatch_no}.",
            event_metadata={"dispatch_id": d.id, "incident_id": i.id, "severity": str(i.severity)},
        )
        self.db.commit()
        return self.incident_repository.get_required_by_id(i.id)
