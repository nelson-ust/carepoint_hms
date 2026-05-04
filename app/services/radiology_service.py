# app/services/radiology_service.py
from __future__ import annotations

"""
Service layer for the Radiology / RIS module.

Provides four service classes that mirror the lab loop:
- :class:`RadiologyCatalogService`     — catalog CRUD
- :class:`RadiologyOrderService`       — clinician order placement + lifecycle
- :class:`RadiologyExamService`        — execution + PACS image attachment
- :class:`RadiologyReportService`      — radiologist reading with 4-eyes verify
                                          and release-with-notification

Lifecycle:
    Order:  ORDERED → SCHEDULED → IN_PROGRESS → PERFORMED → REPORTED → RELEASED → COMPLETED
    Exam:   SCHEDULED → IN_PROGRESS → PERFORMED
    Report: DRAFT → PRELIMINARY/FINAL → AMENDED (optional, post-release edit)
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    RadiologyExamStatus,
    RadiologyOrderStatus,
    RadiologyReportStatus,
    VisitPriority,
    VisitStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    RadiologyExam,
    RadiologyImage,
    RadiologyOrder,
    RadiologyOrderItem,
    RadiologyProcedureCatalog,
    RadiologyReport,
)
from app.repositories.radiology_repository import (
    RadiologyCatalogRepository,
    RadiologyExamRepository,
    RadiologyImageRepository,
    RadiologyOrderRepository,
    RadiologyReportRepository,
)
from app.schemas.radiology_schemas import (
    RadiologyExamCompleteSchema,
    RadiologyExamScheduleSchema,
    RadiologyExamStartSchema,
    RadiologyImageAttachSchema,
    RadiologyOrderCancelSchema,
    RadiologyOrderCreateSchema,
    RadiologyProcedureCatalogCreateSchema,
    RadiologyProcedureCatalogUpdateSchema,
    RadiologyReportDraftSchema,
    RadiologyReportFinalizeSchema,
    RadiologyReportReleaseSchema,
)
from app.utils.charge_capture import (
    add_charge,
    find_billable_service,
    get_or_create_open_billing,
)
from app.utils.payment_policy import requires_pre_payment
from app.utils.security_event_util import record_security_event
from app.utils.visit_routing import route_visit_to_next_sdp


# ============================================================
# CATALOG SERVICE
# ============================================================


class RadiologyCatalogService:
    """CRUD over the radiology procedure catalog."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = RadiologyCatalogRepository(db)

    def list_procedures(self, *, skip=0, limit=50, modality=None, search=None):
        return self.repository.list_procedures(
            skip=skip, limit=limit, modality=modality, search=search
        )

    def get(self, procedure_id: int) -> RadiologyProcedureCatalog:
        return self.repository.get_required_by_id(procedure_id)

    def create(self, payload: RadiologyProcedureCatalogCreateSchema) -> RadiologyProcedureCatalog:
        data = payload.model_dump(exclude_unset=True)
        # Modality is stored as the enum value string.
        from app.core.enums import RadiologyModality
        if isinstance(data.get("modality"), str):
            data["modality"] = RadiologyModality(data["modality"])
        p = self.repository.create(**data)
        self.db.commit()
        return self.repository.get_required_by_id(p.id)

    def update(
        self,
        procedure_id: int,
        payload: RadiologyProcedureCatalogUpdateSchema,
    ) -> RadiologyProcedureCatalog:
        p = self.repository.get_required_by_id(procedure_id)
        updated = self.repository.update(p, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, procedure_id: int) -> RadiologyProcedureCatalog:
        p = self.repository.get_required_by_id(procedure_id)
        p = self.repository.soft_delete(p)
        self.db.commit()
        return p


# ============================================================
# ORDER SERVICE
# ============================================================


class RadiologyOrderService:
    """Order placement, charge capture, routing."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = RadiologyOrderRepository(db)
        self.catalog_repository = RadiologyCatalogRepository(db)

    def get(self, order_id: int) -> RadiologyOrder:
        return self.repository.get_required_by_id(order_id)

    def list_for_visit(self, visit_id: int, *, skip=0, limit=50):
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)

    def list_worklist(self, *, skip=0, limit=50, statuses: Optional[list[str]] = None):
        normalized = (
            [RadiologyOrderStatus(s.strip().upper()) for s in statuses] if statuses else None
        )
        return self.repository.list_worklist(skip=skip, limit=limit, statuses=normalized)

    def create_order(
        self,
        payload: RadiologyOrderCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> RadiologyOrder:
        """
        Place a radiology order. Creates one BillingItem per procedure
        (idempotent on RAD_ORDER_ITEM:{id}). Routes the patient to cashier
        first if PRE_PAID/HYBRID, otherwise straight to the radiology SDP.
        """
        visit = self.repository.get_visit(payload.visit_id)
        if visit is None:
            raise NotFoundError(message="Visit not found.", detail={"visit_id": payload.visit_id})
        if visit.status in {VisitStatus.COMPLETED, VisitStatus.CANCELLED}:
            raise BadRequestError(
                message="Cannot order radiology on a closed visit.",
                detail={"visit_status": str(visit.status)},
            )

        # Validate every requested procedure exists.
        catalogs_by_id: dict[int, RadiologyProcedureCatalog] = {}
        for entry in payload.items:
            cat = self.catalog_repository.get_required_by_id(entry.procedure_catalog_id)
            catalogs_by_id[cat.id] = cat

        priority = (
            VisitPriority(payload.priority.strip().upper())
            if payload.priority
            else VisitPriority.NORMAL
        )

        order = self.repository.create_order(
            visit_id=visit.id,
            consultation_id=payload.consultation_id,
            facility_id=payload.facility_id,
            ordered_by_staff_id=payload.ordered_by_staff_id,
            priority=priority,
            clinical_indication=payload.clinical_indication,
            pregnancy_screening=payload.pregnancy_screening,
            creatinine_value=payload.creatinine_value,
        )

        # Create per-procedure items + capture per-line charge.
        billing = (
            get_or_create_open_billing(self.db, visit=visit)
            if payload.auto_capture_charge
            else None
        )
        for entry in payload.items:
            cat = catalogs_by_id[entry.procedure_catalog_id]
            item = self.repository.add_item(
                radiology_order_id=order.id,
                procedure_catalog_id=cat.id,
                laterality=entry.laterality,
                notes=entry.notes,
            )
            if billing is not None:
                billable = find_billable_service(self.db, code=f"RAD-{cat.code}")
                add_charge(
                    self.db,
                    billing=billing,
                    service_name=f"Radiology: {cat.name}",
                    service_code=f"RAD-{cat.code}",
                    unit_price=Decimal(cat.default_price or 0),
                    quantity=Decimal("1"),
                    billable_service_id=billable.id if billable else None,
                    source_reference=f"RAD_ORDER_ITEM:{item.id}",
                )

        # Routing — cashier first when pre-payment is required.
        next_sdp_id: Optional[int] = None
        if requires_pre_payment(source="LAB"):
            # Radiology behaves like lab for the gate decision.
            next_sdp_id = (
                payload.route_to_cashier_service_delivery_point_id
                or payload.route_to_radiology_service_delivery_point_id
            )
        else:
            next_sdp_id = (
                payload.route_to_radiology_service_delivery_point_id
                or payload.route_to_cashier_service_delivery_point_id
            )

        if next_sdp_id is not None:
            route_visit_to_next_sdp(
                self.db,
                visit_id=visit.id,
                target_service_delivery_point_id=next_sdp_id,
                routed_by_id=actor_user_id,
                notes="Routed by radiology order.",
            )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="RADIOLOGY_ORDER_CREATED",
            severity="INFO",
            event_detail=f"Radiology order {order.order_no} created for visit {visit.id}.",
            event_metadata={
                "order_id": order.id,
                "visit_id": visit.id,
                "item_count": len(payload.items),
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(order.id)

    def cancel_order(
        self,
        order_id: int,
        payload: RadiologyOrderCancelSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> RadiologyOrder:
        order = self.repository.get_required_by_id(order_id)
        if order.status in {RadiologyOrderStatus.COMPLETED, RadiologyOrderStatus.CANCELLED}:
            raise BadRequestError(
                message="Order is already in a terminal state.",
                detail={"status": str(order.status)},
            )
        for item in self.repository.items_for_order(order.id):
            if item.status not in {RadiologyOrderStatus.COMPLETED, RadiologyOrderStatus.CANCELLED}:
                item.status = RadiologyOrderStatus.CANCELLED
                self.repository.save_item(item)
        order.status = RadiologyOrderStatus.CANCELLED
        self.repository.save(order)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="RADIOLOGY_ORDER_CANCELLED",
            severity="WARNING",
            event_detail=f"Radiology order {order.order_no} cancelled.",
            event_metadata={"order_id": order.id, "reason": payload.reason},
        )
        self.db.commit()
        return self.repository.get_required_by_id(order.id)


# ============================================================
# EXAM SERVICE
# ============================================================


class RadiologyExamService:
    """Schedule, start, complete a radiology exam against an order item."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = RadiologyExamRepository(db)
        self.order_repository = RadiologyOrderRepository(db)
        self.image_repository = RadiologyImageRepository(db)

    def schedule_exam(
        self,
        payload: RadiologyExamScheduleSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> RadiologyExam:
        item = self.order_repository.get_required_item_by_id(payload.order_item_id)
        if self.repository.get_for_order_item(item.id) is not None:
            raise BadRequestError(
                message="An exam already exists for this order item.",
                detail={"order_item_id": item.id},
            )
        exam = self.repository.create(
            order_item_id=item.id,
            facility_id=payload.facility_id,
            machine_identifier=payload.machine_identifier,
            scheduled_at=payload.scheduled_at,
        )
        item.status = RadiologyOrderStatus.SCHEDULED
        self.order_repository.save_item(item)
        self.order_repository.recompute_order_status(
            self.order_repository.get_required_by_id(item.radiology_order_id)
        )
        self.db.commit()
        return self.repository.get_required_by_id(exam.id)

    def start_exam(
        self,
        exam_id: int,
        payload: RadiologyExamStartSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> RadiologyExam:
        exam = self.repository.get_required_by_id(exam_id)
        if exam.status not in {RadiologyExamStatus.SCHEDULED, RadiologyExamStatus.PATIENT_PREP}:
            raise BadRequestError(
                message="Exam cannot be started from its current status.",
                detail={"status": str(exam.status)},
            )
        exam.status = RadiologyExamStatus.IN_PROGRESS
        exam.started_at = datetime.now(timezone.utc)
        if payload.performed_by_staff_id is not None:
            exam.performed_by_staff_id = payload.performed_by_staff_id
        if payload.machine_identifier:
            exam.machine_identifier = payload.machine_identifier
        if payload.contrast_administered is not None:
            exam.contrast_administered = payload.contrast_administered
        if payload.technical_notes:
            exam.technical_notes = payload.technical_notes
        self.repository.save(exam)

        item = self.order_repository.get_required_item_by_id(exam.order_item_id)
        item.status = RadiologyOrderStatus.IN_PROGRESS
        self.order_repository.save_item(item)
        self.order_repository.recompute_order_status(
            self.order_repository.get_required_by_id(item.radiology_order_id)
        )
        self.db.commit()
        return self.repository.get_required_by_id(exam.id)

    def complete_exam(
        self,
        exam_id: int,
        payload: RadiologyExamCompleteSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> RadiologyExam:
        exam = self.repository.get_required_by_id(exam_id)
        if exam.status != RadiologyExamStatus.IN_PROGRESS:
            raise BadRequestError(
                message="Only IN_PROGRESS exams can be completed.",
                detail={"status": str(exam.status)},
            )
        exam.status = RadiologyExamStatus.PERFORMED
        exam.ended_at = datetime.now(timezone.utc)
        if payload.technical_notes:
            exam.technical_notes = payload.technical_notes
        self.repository.save(exam)

        item = self.order_repository.get_required_item_by_id(exam.order_item_id)
        item.status = RadiologyOrderStatus.PERFORMED
        self.order_repository.save_item(item)
        self.order_repository.recompute_order_status(
            self.order_repository.get_required_by_id(item.radiology_order_id)
        )
        self.db.commit()
        return self.repository.get_required_by_id(exam.id)

    def attach_image(
        self,
        payload: RadiologyImageAttachSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> RadiologyImage:
        exam = self.repository.get_required_by_id(payload.exam_id)
        image = self.image_repository.create(
            exam_id=exam.id,
            sop_instance_uid=payload.sop_instance_uid,
            series_instance_uid=payload.series_instance_uid,
            study_instance_uid=payload.study_instance_uid,
            image_url=payload.image_url,
            pacs_archive_id=payload.pacs_archive_id,
            image_count=payload.image_count,
            captured_at=payload.captured_at or datetime.now(timezone.utc),
            notes=payload.notes,
        )
        self.db.commit()
        return image

    def list_images(self, exam_id: int) -> list[RadiologyImage]:
        # Existence check first to give a clean 404.
        self.repository.get_required_by_id(exam_id)
        return self.image_repository.list_for_exam(exam_id)


# ============================================================
# REPORT SERVICE
# ============================================================


class RadiologyReportService:
    """Radiologist reading: draft → finalize → release."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = RadiologyReportRepository(db)
        self.exam_repository = RadiologyExamRepository(db)
        self.order_repository = RadiologyOrderRepository(db)

    def draft_report(
        self,
        payload: RadiologyReportDraftSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> RadiologyReport:
        exam = self.exam_repository.get_required_by_id(payload.exam_id)
        if exam.status != RadiologyExamStatus.PERFORMED:
            raise BadRequestError(
                message="Cannot draft a report for an exam that is not PERFORMED.",
                detail={"status": str(exam.status)},
            )
        existing = self.repository.get_for_exam(exam.id)
        if existing is not None and existing.status not in {
            RadiologyReportStatus.DRAFT,
            RadiologyReportStatus.PRELIMINARY,
        }:
            raise BadRequestError(
                message="Report is no longer editable.",
                detail={"status": str(existing.status)},
            )

        if existing is None:
            report = self.repository.create(
                exam_id=exam.id,
                reported_by_staff_id=payload.reported_by_staff_id,
                findings=payload.findings,
                impression=payload.impression,
                recommendations=payload.recommendations,
            )
        else:
            existing.reported_by_staff_id = (
                payload.reported_by_staff_id or existing.reported_by_staff_id
            )
            existing.findings = payload.findings or existing.findings
            existing.impression = payload.impression or existing.impression
            existing.recommendations = payload.recommendations or existing.recommendations
            self.repository.save(existing)
            report = existing
        self.db.commit()
        return self.repository.get_required_by_id(report.id)

    def finalize_report(
        self,
        report_id: int,
        payload: RadiologyReportFinalizeSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> RadiologyReport:
        """
        Finalize (verify) a draft report. Enforces the four-eyes rule:
        ``verified_by_staff_id`` must differ from ``reported_by_staff_id`` when
        both are set.
        """
        report = self.repository.get_required_by_id(report_id)
        if report.status not in {RadiologyReportStatus.DRAFT, RadiologyReportStatus.PRELIMINARY}:
            raise BadRequestError(
                message="Only DRAFT or PRELIMINARY reports can be finalized.",
                detail={"status": str(report.status)},
            )
        if (
            payload.verified_by_staff_id is not None
            and report.reported_by_staff_id is not None
            and payload.verified_by_staff_id == report.reported_by_staff_id
        ):
            raise BadRequestError(
                message="Verifier must differ from reporter (four-eyes rule).",
                detail={"reported_by_staff_id": report.reported_by_staff_id},
            )

        if payload.findings:
            report.findings = payload.findings
        if payload.impression:
            report.impression = payload.impression
        if payload.recommendations:
            report.recommendations = payload.recommendations
        if payload.verified_by_staff_id is not None:
            report.verified_by_staff_id = payload.verified_by_staff_id
        report.status = RadiologyReportStatus.FINAL
        report.finalized_at = datetime.now(timezone.utc)
        self.repository.save(report)

        # Mark the order item REPORTED.
        exam = self.exam_repository.get_required_by_id(report.exam_id)
        item = self.order_repository.get_required_item_by_id(exam.order_item_id)
        item.status = RadiologyOrderStatus.REPORTED
        self.order_repository.save_item(item)
        self.order_repository.recompute_order_status(
            self.order_repository.get_required_by_id(item.radiology_order_id)
        )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="RADIOLOGY_REPORT_FINALIZED",
            severity="INFO",
            event_detail=f"Radiology report {report.id} finalized.",
            event_metadata={"report_id": report.id, "exam_id": exam.id},
        )
        self.db.commit()
        return self.repository.get_required_by_id(report.id)

    def release_report(
        self,
        report_id: int,
        payload: RadiologyReportReleaseSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> RadiologyReport:
        """
        Release a finalized report. Marks the order item RELEASED and emits
        a notification suitable for downstream subscribers (clinician inbox,
        patient portal, etc.).
        """
        report = self.repository.get_required_by_id(report_id)
        if report.status != RadiologyReportStatus.FINAL:
            raise BadRequestError(
                message="Only FINAL reports can be released.",
                detail={"status": str(report.status)},
            )
        report.released_at = datetime.now(timezone.utc)
        self.repository.save(report)

        exam = self.exam_repository.get_required_by_id(report.exam_id)
        item = self.order_repository.get_required_item_by_id(exam.order_item_id)
        item.status = RadiologyOrderStatus.RELEASED
        self.order_repository.save_item(item)
        order = self.order_repository.get_required_by_id(item.radiology_order_id)
        self.order_repository.recompute_order_status(order)

        # Best-effort downstream notifications (lab parity).
        if payload.notify_clinician:
            try:
                from app.services.notification_service import NotificationService
                from app.schemas.notification_schema import NotificationDispatchSchema

                visit = self.order_repository.get_visit(order.visit_id)
                ns = NotificationService(self.db)
                ns.dispatch_from_template(
                    NotificationDispatchSchema(
                        template_code="RADIOLOGY_REPORT_RELEASED",
                        user_id=order.ordered_by_staff_id,
                        patient_id=visit.patient_id if visit is not None else None,
                        context={
                            "order_no": order.order_no,
                            "exam_id": exam.id,
                            "report_id": report.id,
                        },
                    ),
                    actor_user_id=actor_user_id,
                )
            except Exception:
                # Notifications are best-effort. The report release stands.
                pass

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="RADIOLOGY_REPORT_RELEASED",
            severity="INFO",
            event_detail=f"Radiology report {report.id} released.",
            event_metadata={"report_id": report.id, "exam_id": exam.id},
        )
        self.db.commit()
        return self.repository.get_required_by_id(report.id)

    def get(self, report_id: int) -> RadiologyReport:
        return self.repository.get_required_by_id(report_id)

    def get_for_exam(self, exam_id: int) -> Optional[RadiologyReport]:
        return self.repository.get_for_exam(exam_id)
