from __future__ import annotations

"""
app.services.service_delivery_service

Service layer for service delivery point configuration and retrieval.

Purpose
-------
This module implements business logic for:

- creating service delivery points
- retrieving service delivery points
- filtering/listing service delivery points
- updating service delivery points
- activating/deactivating service delivery points
- soft-deleting service delivery points

Business rules
--------------
- service delivery point code must be unique
- service point type must resolve to a valid enum value
- queue_prefix should default sensibly when omitted
- at least one of supports_walk_in or supports_appointments should be enabled
- inactive points should not be presented as operationally available
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import ServicePointType
from app.core.exceptions import AlreadyExistsError, BadRequestError, NotFoundError
from app.repositories.service_delivery_point_repository import ServiceDeliveryRepository
from app.schemas.service_delivery_point_schemas import (
    ServiceDeliveryPointCreateSchema,
    ServiceDeliveryPointStatusToggleSchema,
    ServiceDeliveryPointUpdateSchema,
)


class ServiceDeliveryService:
    """
    Service layer for service delivery point operations.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ServiceDeliveryRepository(db)

    # ============================================================
    # CREATE
    # ============================================================

    def create_service_delivery_point(
        self,
        payload: ServiceDeliveryPointCreateSchema,
    ):
        """
        Create a new service delivery point.

        Business rules
        --------------
        - code must be unique
        - service_point_type must be valid
        - at least one of walk-in or appointment support must be enabled
        """
        if self.repository.code_exists(payload.code):
            raise AlreadyExistsError(
                message="A service delivery point with this code already exists.",
                detail={"code": payload.code},
            )

        self._validate_operational_support_flags(
            supports_appointments=payload.supports_appointments,
            supports_walk_in=payload.supports_walk_in,
        )

        service_point_type = self._resolve_service_point_type(payload.service_point_type)
        queue_prefix = payload.queue_prefix or self._default_queue_prefix(payload.code)

        record = self.repository.create_service_delivery_point(
            name=payload.name,
            code=payload.code,
            service_point_type=service_point_type,
            department_id=payload.department_id,
            location_description=payload.location_description,
            queue_prefix=queue_prefix,
            supports_appointments=payload.supports_appointments,
            supports_walk_in=payload.supports_walk_in,
            is_active=payload.is_active,
        )
        self.db.commit()
        return self.repository.get_by_id(record.id)

    # ============================================================
    # READ
    # ============================================================

    def get_service_delivery_point(self, service_delivery_point_id: int):
        """
        Return a single service delivery point by ID.
        """
        record = self.repository.get_by_id(service_delivery_point_id)
        if not record:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"service_delivery_point_id": service_delivery_point_id},
            )
        return record

    def get_service_delivery_point_by_code(self, code: str):
        """
        Return a single service delivery point by code.
        """
        record = self.repository.get_by_code(code.strip().upper())
        if not record:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"code": code},
            )
        return record

    def queue_stats(self) -> dict:
        """
        Live queue metrics per service delivery point: how many tickets are
        currently WAITING / CALLED / SERVING, plus how many were issued today.
        Powers the operational counters on the Service Points page.
        """
        from datetime import datetime, timezone

        from sqlalchemy import Date, cast, func

        from app.core.enums import QueueStatus
        from app.models.all_models import QueueTicket

        today = datetime.now(timezone.utc).date()

        def _val(st) -> str:
            return st.value if hasattr(st, "value") else str(st)

        points: dict[int, dict] = {}

        status_rows = (
            self.db.query(
                QueueTicket.service_delivery_point_id,
                QueueTicket.status,
                func.count(QueueTicket.id),
            )
            .filter(QueueTicket.is_deleted.is_(False))
            .group_by(QueueTicket.service_delivery_point_id, QueueTicket.status)
            .all()
        )
        for sdp_id, st, cnt in status_rows:
            p = points.setdefault(
                sdp_id,
                {"service_delivery_point_id": sdp_id, "waiting": 0, "called": 0, "serving": 0, "total_today": 0},
            )
            v = _val(st)
            if v == QueueStatus.WAITING.value:
                p["waiting"] += int(cnt)
            elif v == QueueStatus.CALLED.value:
                p["called"] += int(cnt)
            elif v == QueueStatus.SERVING.value:
                p["serving"] += int(cnt)

        total_today = 0
        today_rows = (
            self.db.query(
                QueueTicket.service_delivery_point_id,
                func.count(QueueTicket.id),
            )
            .filter(
                QueueTicket.is_deleted.is_(False),
                cast(QueueTicket.date_created, Date) == today,
            )
            .group_by(QueueTicket.service_delivery_point_id)
            .all()
        )
        for sdp_id, cnt in today_rows:
            p = points.setdefault(
                sdp_id,
                {"service_delivery_point_id": sdp_id, "waiting": 0, "called": 0, "serving": 0, "total_today": 0},
            )
            p["total_today"] = int(cnt)
            total_today += int(cnt)

        return {
            "success": True,
            "total_today": total_today,
            "points": list(points.values()),
        }

    def list_service_delivery_points(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        name: Optional[str] = None,
        code: Optional[str] = None,
        service_point_type: Optional[str] = None,
        department_id: Optional[int] = None,
        supports_appointments: Optional[bool] = None,
        supports_walk_in: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ):
        """
        Return paginated service delivery points with optional filters.
        """
        resolved_type = (
            self._resolve_service_point_type(service_point_type)
            if service_point_type is not None
            else None
        )

        normalized_code = code.strip().upper() if code else None

        return self.repository.list_service_delivery_points(
            skip=skip,
            limit=limit,
            name=name,
            code=normalized_code,
            service_point_type=resolved_type,
            department_id=department_id,
            supports_appointments=supports_appointments,
            supports_walk_in=supports_walk_in,
            is_active=is_active,
        )

    def list_active_service_delivery_points(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        service_point_type: Optional[str] = None,
        department_id: Optional[int] = None,
    ):
        """
        Return paginated active service delivery points.
        """
        resolved_type = (
            self._resolve_service_point_type(service_point_type)
            if service_point_type is not None
            else None
        )

        return self.repository.list_active_service_delivery_points(
            skip=skip,
            limit=limit,
            service_point_type=resolved_type,
            department_id=department_id,
        )

    # ============================================================
    # UPDATE
    # ============================================================

    def update_service_delivery_point(
        self,
        service_delivery_point_id: int,
        payload: ServiceDeliveryPointUpdateSchema,
    ):
        """
        Update a service delivery point.
        """
        record = self.repository.get_by_id(service_delivery_point_id)
        if not record:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"service_delivery_point_id": service_delivery_point_id},
            )

        if payload.code is not None and payload.code != record.code:
            if self.repository.code_exists(payload.code):
                raise AlreadyExistsError(
                    message="A service delivery point with this code already exists.",
                    detail={"code": payload.code},
                )
            record.code = payload.code

        if payload.name is not None:
            record.name = payload.name

        if payload.service_point_type is not None:
            record.service_point_type = self._resolve_service_point_type(
                payload.service_point_type
            )

        if payload.department_id is not None:
            record.department_id = payload.department_id

        if payload.location_description is not None:
            record.location_description = payload.location_description

        if payload.queue_prefix is not None:
            record.queue_prefix = payload.queue_prefix or self._default_queue_prefix(
                record.code
            )

        new_supports_appointments = (
            payload.supports_appointments
            if payload.supports_appointments is not None
            else record.supports_appointments
        )
        new_supports_walk_in = (
            payload.supports_walk_in
            if payload.supports_walk_in is not None
            else record.supports_walk_in
        )

        self._validate_operational_support_flags(
            supports_appointments=new_supports_appointments,
            supports_walk_in=new_supports_walk_in,
        )

        if payload.supports_appointments is not None:
            record.supports_appointments = payload.supports_appointments

        if payload.supports_walk_in is not None:
            record.supports_walk_in = payload.supports_walk_in

        if payload.is_active is not None:
            record.is_active = payload.is_active

        updated = self.repository.update_service_delivery_point(record)
        self.db.commit()
        return self.repository.get_by_id(updated.id)

    # ============================================================
    # STATUS TOGGLE
    # ============================================================

    def set_active_status(
        self,
        service_delivery_point_id: int,
        payload: ServiceDeliveryPointStatusToggleSchema,
    ):
        """
        Activate or deactivate a service delivery point.
        """
        record = self.repository.get_by_id(service_delivery_point_id)
        if not record:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"service_delivery_point_id": service_delivery_point_id},
            )

        updated = self.repository.set_active_status(
            record,
            is_active=payload.is_active,
        )
        self.db.commit()
        return self.repository.get_by_id(updated.id)

    # ============================================================
    # DELETE
    # ============================================================

    def delete_service_delivery_point(self, service_delivery_point_id: int):
        """
        Soft-delete a service delivery point.

        Notes
        -----
        This currently performs a simple soft delete.
        Later, you may want to block deletion if the point is already referenced
        by visits, appointments, queue tickets, or flow steps.
        """
        record = self.repository.get_by_id(service_delivery_point_id)
        if not record:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"service_delivery_point_id": service_delivery_point_id},
            )

        deleted = self.repository.soft_delete_service_delivery_point(record)
        self.db.commit()
        return deleted

    # ============================================================
    # OPERATIONAL HELPERS
    # ============================================================

    def supports_walk_in(self, service_delivery_point_id: int) -> bool:
        """
        Return whether a point supports walk-in routing.
        """
        record = self.get_service_delivery_point(service_delivery_point_id)
        return bool(record.is_active and record.supports_walk_in)

    def supports_appointments(self, service_delivery_point_id: int) -> bool:
        """
        Return whether a point supports appointment routing.
        """
        record = self.get_service_delivery_point(service_delivery_point_id)
        return bool(record.is_active and record.supports_appointments)

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _resolve_service_point_type(
        self,
        value: Optional[str | ServicePointType],
    ) -> ServicePointType:
        """
        Normalize service point type to ServicePointType enum.
        """
        if isinstance(value, ServicePointType):
            return value

        if value is None:
            raise BadRequestError(message="service_point_type is required.")

        normalized = str(value).strip().upper()

        try:
            return ServicePointType[normalized]
        except KeyError:
            for member in ServicePointType:
                if str(member.value).strip().upper() == normalized:
                    return member

        allowed = ", ".join(member.name for member in ServicePointType)
        raise BadRequestError(
            message=f"Unsupported service_point_type: {value}",
            detail={"allowed_values": allowed},
        )

    def _default_queue_prefix(self, code: str) -> str:
        """
        Build a default queue prefix from the service-point code.
        """
        normalized = code.strip().upper()
        return normalized[:6] if normalized else "QUEUE"

    def _validate_operational_support_flags(
        self,
        *,
        supports_appointments: bool,
        supports_walk_in: bool,
    ) -> None:
        """
        Validate that a service delivery point remains operationally usable.
        """
        if not supports_appointments and not supports_walk_in:
            raise BadRequestError(
                message=(
                    "A service delivery point must support at least one of "
                    "appointments or walk-ins."
                )
            )