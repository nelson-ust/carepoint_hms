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
from app.core.enums import LabResultStatus, OrderStatus, ServicePointType
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
from app.utils.visit_routing import route_visit_to_next_sdp, validate_visit_sdp_activity


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

        # Enforce SDP validation and get current step
        current_step = validate_visit_sdp_activity(
            self.db,
            visit_id=item.lab_order.visit_id,
            required_sdp_types=[ServicePointType.LABORATORY],
            activity_name="Lab Result entry",
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
                visit_flow_step_id=current_step.id,
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
            result.visit_flow_step_id = current_step.id
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

    def get_order_report_data(self, order_id: int, *,
                              restrict_patient_id: Optional[int] = None) -> dict:
        """Everything the branded lab-report PDF needs, for RELEASED results
        only. When ``restrict_patient_id`` is given (patient-portal calls),
        the order must belong to that patient."""
        from app.core.enums import LabResultStatus as _LRS
        from app.models.all_models import (
            LabOrder, Patient, StaffProfile, User, Visit,
        )
        from app.utils.lab_report_pdf import verification_code

        order = (
            self.db.query(LabOrder)
            .filter(LabOrder.id == order_id, LabOrder.is_deleted.is_(False))
            .first()
        )
        if order is None:
            raise NotFoundError(message="Lab order not found.")

        visit = self.db.query(Visit).filter(Visit.id == order.visit_id).first()
        patient = (
            self.db.query(Patient).filter(Patient.id == visit.patient_id).first()
            if visit else None
        )
        if restrict_patient_id is not None and (
            patient is None or patient.id != restrict_patient_id
        ):
            raise NotFoundError(message="Lab order not found.")

        rows: list[dict] = []
        interpretations: list[str] = []
        scientist_ids: set[int] = set()
        approver_ids: set[int] = set()
        reported_at = None
        for item in (order.items or []):
            result = getattr(item, "result", None)
            if result is None or getattr(result, "released_at", None) is None:
                continue
            if getattr(result, "result_status", None) not in (
                _LRS.RELEASED, getattr(_LRS, "VERIFIED", None),
            ):
                # released_at stamped is authoritative; keep row regardless of
                # enum spelling differences.
                pass
            catalog = getattr(item, "lab_test_catalog", None)
            rows.append({
                "test": getattr(catalog, "name", None) or f"Test #{item.lab_test_catalog_id}",
                "result": result.result_value or result.result_text or "-",
                "unit": result.unit_of_measure
                or getattr(catalog, "unit_of_measure", None) or "",
                "reference_range": result.reference_range
                or getattr(catalog, "reference_range", None) or "",
                "specimen": item.specimen_id
                or getattr(catalog, "sample_type", None) or "",
                "collected_at": item.sample_collected_at,
            })
            if result.interpretation:
                interpretations.append(result.interpretation)
            if result.entered_by_staff_id:
                scientist_ids.add(result.entered_by_staff_id)
            if result.verified_by_staff_id:
                approver_ids.add(result.verified_by_staff_id)
            if result.released_at and (reported_at is None or result.released_at > reported_at):
                reported_at = result.released_at

        if not rows:
            raise BadRequestError(
                message="No released results on this order yet — the report "
                        "becomes available once the laboratory releases results."
            )

        def _staff_display(ids: set[int]) -> Optional[str]:
            if not ids:
                return None
            pairs = (
                self.db.query(StaffProfile, User)
                .outerjoin(User, User.id == StaffProfile.user_id)
                .filter(StaffProfile.id.in_(ids)).all()
            )
            names = []
            for sp, u in pairs:
                n = (f"{getattr(u, 'first_name', '') or ''} "
                     f"{getattr(u, 'last_name', '') or ''}").strip()
                names.append(n or sp.staff_no)
            return ", ".join(sorted(set(names))) or None

        patient_name = ""
        if patient is not None:
            patient_name = " ".join(
                x for x in (patient.first_name, getattr(patient, "middle_name", None),
                            getattr(patient, "last_name", None)) if x
            )

        def _ev(v):
            return getattr(v, "value", v)

        return {
            "order": order,
            "order_no": order.order_no,
            "visit_number": getattr(visit, "visit_number", None) if visit else None,
            "ordered_at": order.ordered_at,
            "reported_at": reported_at,
            "patient": {
                "id": getattr(patient, "id", None),
                "name": patient_name or "-",
                "hospital_number": getattr(patient, "hospital_number", None),
                "date_of_birth": str(getattr(patient, "date_of_birth", "") or "") or None,
                "gender": str(_ev(getattr(patient, "gender", "")) or "") or None,
                "blood_group": str(_ev(getattr(patient, "blood_group", "")) or "") or None,
                "genotype": str(_ev(getattr(patient, "genotype", "")) or "") or None,
            },
            "rows": rows,
            "interpretation": "\n".join(interpretations) or None,
            "scientist_name": _staff_display(scientist_ids),
            "approved_by": _staff_display(approver_ids),
            "verify_code": verification_code(order.order_no,
                                             salt=str(reported_at or "")),
        }

    def list_released_orders_for_patient(self, patient_id: int) -> list[dict]:
        """Patient-portal listing: released lab orders with per-test rows."""
        from app.models.all_models import LabOrder, Visit

        orders = (
            self.db.query(LabOrder)
            .join(Visit, Visit.id == LabOrder.visit_id)
            .filter(Visit.patient_id == patient_id,
                    LabOrder.is_deleted.is_(False))
            .order_by(LabOrder.ordered_at.desc())
            .all()
        )
        out: list[dict] = []
        for order in orders:
            released = []
            for item in (order.items or []):
                result = getattr(item, "result", None)
                if result is None or getattr(result, "released_at", None) is None:
                    continue
                catalog = getattr(item, "lab_test_catalog", None)
                released.append({
                    "test": getattr(catalog, "name", None) or "Test",
                    "result": result.result_value or result.result_text or "-",
                    "unit": result.unit_of_measure or getattr(catalog, "unit_of_measure", None),
                    "reference_range": result.reference_range
                    or getattr(catalog, "reference_range", None),
                    "released_at": result.released_at,
                })
            if released:
                out.append({
                    "order_id": order.id,
                    "order_no": order.order_no,
                    "ordered_at": order.ordered_at,
                    "visit_id": order.visit_id,
                    "results": released,
                })
        return out

    def get(self, result_id: int) -> LabResult:
        return self.repository.get_required_by_id(result_id)

    def get_by_order_item(self, item_id: int) -> Optional[LabResult]:
        return self.repository.get_by_order_item(item_id)
