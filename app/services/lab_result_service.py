# app/services/lab_result_service.py
from __future__ import annotations

"""
Service layer for LabResult lifecycle.

Lifecycle
---------
PENDING -> ENTERED -> VERIFIED -> RELEASED
ENTERED -> CANCELLED
VERIFIED -> RELEASED (auto, optional, via LAB_RESULT_AUTO_RELEASE)
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import LabResultStatus, OrderStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import LabResult
from app.repositories.lab_order_repository import LabOrderRepository
from app.repositories.lab_result_repository import LabResultRepository
from app.schemas.lab_result_schema import (
    LabResultEnterSchema,
    LabResultReleaseSchema,
    LabResultUpdateSchema,
    LabResultVerifySchema,
)
from app.utils.security_event_util import record_security_event
from app.utils.visit_routing import route_visit_to_next_sdp


class LabResultService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = LabResultRepository(db)
        self.order_repo = LabOrderRepository(db)

    # ============================================================
    # ENTER
    # ============================================================

    def enter_result(
        self,
        payload: LabResultEnterSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> LabResult:
        item = self.order_repo.get_required_item_by_id(payload.lab_order_item_id)
        if item.status in {OrderStatus.COMPLETED, OrderStatus.CANCELLED}:
            raise BadRequestError(
                message="Cannot enter a result for a closed order item.",
                detail={"status": str(item.status)},
            )

        existing = self.repository.get_by_order_item(item.id)
        if existing is not None and existing.result_status not in {
            LabResultStatus.PENDING,
            LabResultStatus.ENTERED,
        }:
            raise BadRequestError(
                message="Result is no longer editable.",
                detail={"status": str(existing.result_status)},
            )

        if existing is None:
            test = self.order_repo.get_test(item.lab_test_catalog_id)
            unit = payload.unit_of_measure or (test.unit_of_measure if test else None)
            ref_range = payload.reference_range or (test.reference_range if test else None)
            result = self.repository.create(
                lab_order_item_id=item.id,
                entered_by_staff_id=payload.entered_by_staff_id,
                result_status=LabResultStatus.ENTERED,
                result_value=payload.result_value,
                result_text=payload.result_text,
                unit_of_measure=unit,
                reference_range=ref_range,
                interpretation=payload.interpretation,
                entered_at=datetime.now(timezone.utc),
            )
        else:
            result = existing
            result.result_status = LabResultStatus.ENTERED
            result.entered_by_staff_id = payload.entered_by_staff_id or result.entered_by_staff_id
            result.result_value = payload.result_value or result.result_value
            result.result_text = payload.result_text or result.result_text
            result.unit_of_measure = payload.unit_of_measure or result.unit_of_measure
            result.reference_range = payload.reference_range or result.reference_range
            result.interpretation = payload.interpretation or result.interpretation
            result.entered_at = result.entered_at or datetime.now(timezone.utc)
            self.repository.save(result)

        # Move the order item forward.
        item.status = OrderStatus.IN_PROGRESS
        self.order_repo.save_item(item)
        self.order_repo.recompute_order_status(
            self.order_repo.get_required_by_id(item.lab_order_id)
        )

        self.db.commit()
        return self.repository.get_required_by_id(result.id)

    # ============================================================
    # UPDATE
    # ============================================================

    def update_result(
        self,
        result_id: int,
        payload: LabResultUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> LabResult:
        result = self.repository.get_required_by_id(result_id)
        if result.result_status not in {LabResultStatus.PENDING, LabResultStatus.ENTERED}:
            raise BadRequestError(
                message="Result can only be edited while in PENDING/ENTERED state.",
                detail={"status": str(result.result_status)},
            )
        for field, value in payload.model_dump(exclude_unset=True).items():
            if value is not None:
                setattr(result, field, value)
        self.repository.save(result)
        self.db.commit()
        return self.repository.get_required_by_id(result.id)

    # ============================================================
    # VERIFY
    # ============================================================

    def verify_result(
        self,
        result_id: int,
        payload: LabResultVerifySchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> LabResult:
        result = self.repository.get_required_by_id(result_id)
        if result.result_status != LabResultStatus.ENTERED:
            raise BadRequestError(
                message="Only entered results can be verified.",
                detail={"status": str(result.result_status)},
            )
        if payload.verified_by_staff_id and payload.verified_by_staff_id == result.entered_by_staff_id:
            raise BadRequestError(
                message="A different staff member must verify the result (four-eyes rule).",
                detail={"entered_by_staff_id": result.entered_by_staff_id},
            )

        result.result_status = LabResultStatus.VERIFIED
        result.verified_by_staff_id = payload.verified_by_staff_id
        result.verified_at = datetime.now(timezone.utc)
        if payload.verification_note:
            result.interpretation = (
                (result.interpretation + "\n" if result.interpretation else "")
                + f"[VERIFY] {payload.verification_note}"
            ).strip()
        self.repository.save(result)

        # Mark order item as RESULT_READY.
        item = self.order_repo.get_required_item_by_id(result.lab_order_item_id)
        item.status = OrderStatus.RESULT_READY
        self.order_repo.save_item(item)
        self.order_repo.recompute_order_status(
            self.order_repo.get_required_by_id(item.lab_order_id)
        )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="LAB_RESULT_VERIFIED",
            severity="INFO",
            event_detail=f"Lab result {result.id} verified.",
            event_metadata={"result_id": result.id},
        )

        if bool(getattr(settings, "LAB_RESULT_AUTO_RELEASE", False)):
            return self.release_result(
                result.id,
                LabResultReleaseSchema(release_note="Auto-released after verification."),
                actor_user_id=actor_user_id,
            )

        self.db.commit()
        return self.repository.get_required_by_id(result.id)

    # ============================================================
    # RELEASE
    # ============================================================

    def release_result(
        self,
        result_id: int,
        payload: LabResultReleaseSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> LabResult:
        result = self.repository.get_required_by_id(result_id)
        if result.result_status != LabResultStatus.VERIFIED:
            raise BadRequestError(
                message="Only verified results can be released.",
                detail={"status": str(result.result_status)},
            )

        result.result_status = LabResultStatus.RELEASED
        result.released_at = datetime.now(timezone.utc)
        if payload.release_note:
            result.interpretation = (
                (result.interpretation + "\n" if result.interpretation else "")
                + f"[RELEASE] {payload.release_note}"
            ).strip()
        self.repository.save(result)

        # Item moves to COMPLETED on release.
        item = self.order_repo.get_required_item_by_id(result.lab_order_item_id)
        item.status = OrderStatus.COMPLETED
        self.order_repo.save_item(item)
        order = self.order_repo.get_required_by_id(item.lab_order_id)
        self.order_repo.recompute_order_status(order)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="LAB_RESULT_RELEASED",
            severity="INFO",
            event_detail=f"Lab result {result.id} released.",
            event_metadata={
                "result_id": result.id,
                "notify_clinician": bool(payload.notify_clinician),
                "route_to_service_delivery_point_id": getattr(
                    payload, "route_to_service_delivery_point_id", None
                ),
            },
        )

        # ----- Best-effort notification to the ordering clinician ---------
        if payload.notify_clinician:
            try:
                from app.services.notification_service import NotificationService
                from app.schemas.notification_schema import NotificationDispatchSchema

                visit = order.visit  # eagerly available via relationship
                ns = NotificationService(self.db)
                ns.dispatch_from_template(
                    NotificationDispatchSchema(
                        template_code="LAB_RESULT_RELEASED",
                        user_id=order.ordered_by_staff_id,
                        patient_id=visit.patient_id if visit is not None else None,
                        context={
                            "order_no": order.order_no,
                            "lab_order_item_id": item.id,
                            "result_id": result.id,
                        },
                    ),
                    actor_user_id=actor_user_id,
                )
            except Exception:
                # Notifications are best-effort. The release stands.
                pass

        # ----- Best-effort notification to the patient ---------
        try:
            from app.services.notification_service import NotificationService
            from app.schemas.notification_schema import NotificationDispatchSchema

            visit = order.visit
            if visit and visit.patient_id:
                ns = NotificationService(self.db)
                ns.dispatch_from_template(
                    NotificationDispatchSchema(
                        template_code="PATIENT_LAB_RESULT_READY",
                        patient_id=visit.patient_id,
                        context={
                            "test_name": item.service_name or "Lab Test",
                            "date": result.released_at.strftime("%Y-%m-%d %H:%M") if result.released_at else "N/A"
                        },
                    ),
                    actor_user_id=actor_user_id,
                )
        except Exception as e:
            print(f"Error sending patient lab notification: {e}")
            pass

        # ----- Route the patient back to the originating clinic SDP -------
        target_sdp_id = getattr(payload, "route_to_service_delivery_point_id", None)
        if target_sdp_id is not None and order.visit_id is not None:
            try:
                route_visit_to_next_sdp(
                    self.db,
                    visit_id=order.visit_id,
                    target_service_delivery_point_id=target_sdp_id,
                    routed_by_id=actor_user_id,
                    notes=f"Routed back to clinic after lab release {result.id}.",
                )
            except Exception:
                # Routing failure should not block the release. The release stands.
                pass

        self.db.commit()
        return self.repository.get_required_by_id(result.id)

    def cancel_result(
        self,
        result_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> LabResult:
        result = self.repository.get_required_by_id(result_id)
        if result.result_status not in {LabResultStatus.PENDING, LabResultStatus.ENTERED}:
            raise BadRequestError(
                message="Only pending or entered results can be cancelled.",
                detail={"status": str(result.result_status)},
            )
        result.result_status = LabResultStatus.CANCELLED
        if reason:
            result.interpretation = (
                (result.interpretation + "\n" if result.interpretation else "")
                + f"[CANCELLED] {reason}"
            ).strip()
        self.repository.save(result)
        self.db.commit()
        return self.repository.get_required_by_id(result.id)

    # ============================================================
    # READS
    # ============================================================

    def get(self, result_id: int) -> LabResult:
        return self.repository.get_required_by_id(result_id)

    def get_by_order_item(self, item_id: int) -> Optional[LabResult]:
        return self.repository.get_by_order_item(item_id)
