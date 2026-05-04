from __future__ import annotations

"""
app.repositories.service_delivery_repository

Repository layer for service delivery point configuration and retrieval.

Purpose
-------
This module centralizes direct database operations for:

- creating service delivery points
- retrieving service delivery points
- filtering/listing service delivery points
- updating service delivery points
- soft-deleting service delivery points
- toggling active status
- checking uniqueness by code

Domain summary
--------------
A ServiceDeliveryPoint represents an operational workstation or routing node
used by appointments, visits, queue tickets, and visit flow steps.

Examples
--------
- registration desk
- triage point
- clinic / consultation room
- laboratory desk
- pharmacy counter
- cashier / billing desk
- ward station
- emergency point
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.all_models import ServiceDeliveryPoint


class ServiceDeliveryRepository:
    """
    Repository for service delivery point persistence and query operations.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the repository with an active SQLAlchemy session.

        Args:
            db: Active SQLAlchemy session.
        """
        self.db = db

    # ============================================================
    # BASIC LOOKUPS
    # ============================================================

    def get_by_id(self, service_delivery_point_id: int) -> Optional[ServiceDeliveryPoint]:
        """
        Return a service delivery point by ID if not soft-deleted.

        Args:
            service_delivery_point_id: Primary key of the service delivery point.

        Returns:
            Optional[ServiceDeliveryPoint]: Matching record or None.
        """
        return (
            self.db.query(ServiceDeliveryPoint)
            .filter(
                ServiceDeliveryPoint.id == service_delivery_point_id,
                ServiceDeliveryPoint.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_code(self, code: str) -> Optional[ServiceDeliveryPoint]:
        """
        Return a service delivery point by unique code if not soft-deleted.

        Args:
            code: Unique code of the service delivery point.

        Returns:
            Optional[ServiceDeliveryPoint]: Matching record or None.
        """
        return (
            self.db.query(ServiceDeliveryPoint)
            .filter(
                ServiceDeliveryPoint.code == code,
                ServiceDeliveryPoint.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, service_delivery_point_id: int) -> ServiceDeliveryPoint:
        """
        Return a service delivery point by ID or raise ValueError.

        Args:
            service_delivery_point_id: Primary key of the service delivery point.

        Returns:
            ServiceDeliveryPoint: Matching record.

        Raises:
            ValueError: If the record is not found.
        """
        record = self.get_by_id(service_delivery_point_id)
        if not record:
            raise ValueError(
                f"ServiceDeliveryPoint with id={service_delivery_point_id} was not found."
            )
        return record

    # ============================================================
    # CREATE
    # ============================================================

    def create_service_delivery_point(
        self,
        *,
        name: str,
        code: str,
        service_point_type,
        department_id: Optional[int] = None,
        location_description: Optional[str] = None,
        queue_prefix: Optional[str] = None,
        supports_appointments: bool = False,
        supports_walk_in: bool = True,
        is_active: bool = True,
    ) -> ServiceDeliveryPoint:
        """
        Create and persist a new service delivery point.

        Args:
            name: Display name.
            code: Unique code.
            service_point_type: Enum or compatible value for service point type.
            department_id: Optional owning department ID.
            location_description: Optional physical/operational description.
            queue_prefix: Optional queue prefix.
            supports_appointments: Whether appointment-based routing is supported.
            supports_walk_in: Whether walk-in routing is supported.
            is_active: Operational active flag.

        Returns:
            ServiceDeliveryPoint: Persisted record.
        """
        record = ServiceDeliveryPoint(
            name=name,
            code=code,
            service_point_type=service_point_type,
            department_id=department_id,
            location_description=location_description,
            queue_prefix=queue_prefix,
            supports_appointments=supports_appointments,
            supports_walk_in=supports_walk_in,
            is_active=is_active,
        )
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    # ============================================================
    # LIST / FILTER
    # ============================================================

    def list_service_delivery_points(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        name: Optional[str] = None,
        code: Optional[str] = None,
        service_point_type=None,
        department_id: Optional[int] = None,
        supports_appointments: Optional[bool] = None,
        supports_walk_in: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> tuple[list[ServiceDeliveryPoint], int]:
        """
        Return paginated service delivery points with optional filters.

        Args:
            skip: Pagination offset.
            limit: Pagination size.
            name: Optional name filter (partial match).
            code: Optional exact code filter.
            service_point_type: Optional service point type filter.
            department_id: Optional department filter.
            supports_appointments: Optional appointment-support filter.
            supports_walk_in: Optional walk-in-support filter.
            is_active: Optional active-status filter.

        Returns:
            tuple[list[ServiceDeliveryPoint], int]:
                - list of matching records
                - total count
        """
        query = self.db.query(ServiceDeliveryPoint).filter(
            ServiceDeliveryPoint.is_deleted.is_(False)
        )

        if name:
            query = query.filter(ServiceDeliveryPoint.name.ilike(f"%{name.strip()}%"))

        if code:
            query = query.filter(ServiceDeliveryPoint.code == code)

        if service_point_type is not None:
            query = query.filter(ServiceDeliveryPoint.service_point_type == service_point_type)

        if department_id is not None:
            query = query.filter(ServiceDeliveryPoint.department_id == department_id)

        if supports_appointments is not None:
            query = query.filter(
                ServiceDeliveryPoint.supports_appointments == supports_appointments
            )

        if supports_walk_in is not None:
            query = query.filter(
                ServiceDeliveryPoint.supports_walk_in == supports_walk_in
            )

        if is_active is not None:
            query = query.filter(ServiceDeliveryPoint.is_active == is_active)

        total = query.with_entities(func.count(ServiceDeliveryPoint.id)).scalar() or 0

        items = (
            query.order_by(ServiceDeliveryPoint.name.asc(), ServiceDeliveryPoint.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, int(total)

    def list_active_service_delivery_points(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        service_point_type=None,
        department_id: Optional[int] = None,
    ) -> tuple[list[ServiceDeliveryPoint], int]:
        """
        Return paginated active service delivery points.

        Args:
            skip: Pagination offset.
            limit: Pagination size.
            service_point_type: Optional type filter.
            department_id: Optional department filter.

        Returns:
            tuple[list[ServiceDeliveryPoint], int]:
                - list of active records
                - total count
        """
        return self.list_service_delivery_points(
            skip=skip,
            limit=limit,
            service_point_type=service_point_type,
            department_id=department_id,
            is_active=True,
        )

    # ============================================================
    # UPDATE
    # ============================================================

    def update_service_delivery_point(
        self,
        record: ServiceDeliveryPoint,
    ) -> ServiceDeliveryPoint:
        """
        Persist updates to an existing service delivery point.

        Args:
            record: ORM instance to persist.

        Returns:
            ServiceDeliveryPoint: Updated record.
        """
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def set_active_status(
        self,
        record: ServiceDeliveryPoint,
        *,
        is_active: bool,
    ) -> ServiceDeliveryPoint:
        """
        Update active status of a service delivery point.

        Args:
            record: ORM instance.
            is_active: New active flag.

        Returns:
            ServiceDeliveryPoint: Updated record.
        """
        record.is_active = is_active
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    # ============================================================
    # DELETE
    # ============================================================

    def soft_delete_service_delivery_point(
        self,
        record: ServiceDeliveryPoint,
    ) -> ServiceDeliveryPoint:
        """
        Soft-delete a service delivery point.

        Args:
            record: ORM instance to soft-delete.

        Returns:
            ServiceDeliveryPoint: Soft-deleted record.
        """
        record.is_deleted = True
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    # ============================================================
    # EXISTENCE / UNIQUENESS HELPERS
    # ============================================================

    def code_exists(self, code: str) -> bool:
        """
        Return whether a service delivery point code already exists.

        Args:
            code: Candidate code.

        Returns:
            bool: True if an active non-deleted record already uses the code.
        """
        count = (
            self.db.query(func.count(ServiceDeliveryPoint.id))
            .filter(
                ServiceDeliveryPoint.code == code,
                ServiceDeliveryPoint.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )
        return count > 0

    def name_exists_in_department(
        self,
        *,
        name: str,
        department_id: Optional[int],
    ) -> bool:
        """
        Return whether a service delivery point name already exists in a department.

        Args:
            name: Candidate name.
            department_id: Department scope.

        Returns:
            bool: True if a non-deleted record matches the same name in the department.
        """
        query = self.db.query(func.count(ServiceDeliveryPoint.id)).filter(
            ServiceDeliveryPoint.name == name,
            ServiceDeliveryPoint.is_deleted.is_(False),
        )

        if department_id is None:
            query = query.filter(ServiceDeliveryPoint.department_id.is_(None))
        else:
            query = query.filter(ServiceDeliveryPoint.department_id == department_id)

        count = query.scalar() or 0
        return count > 0

    # ============================================================
    # OPERATIONAL HELPERS
    # ============================================================

    def supports_walk_in(self, service_delivery_point_id: int) -> bool:
        """
        Check whether a service delivery point supports walk-in routing.

        Args:
            service_delivery_point_id: Primary key.

        Returns:
            bool: True if walk-in is supported.
        """
        record = self.get_by_id(service_delivery_point_id)
        return bool(record and record.supports_walk_in and record.is_active)

    def supports_appointments(self, service_delivery_point_id: int) -> bool:
        """
        Check whether a service delivery point supports appointment routing.

        Args:
            service_delivery_point_id: Primary key.

        Returns:
            bool: True if appointment support is enabled.
        """
        record = self.get_by_id(service_delivery_point_id)
        return bool(record and record.supports_appointments and record.is_active)