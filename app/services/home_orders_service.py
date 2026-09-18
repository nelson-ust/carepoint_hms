# app/services/home_orders_service.py
from __future__ import annotations

"""Home lab order and home medication order services."""

import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    AlertSeverity,
    AlertType,
    HomeLabOrderStatus,
    HomeMedicationStatus,
)
from app.core.exceptions import BadRequestError
from app.core.logger import get_logger
from app.repositories.home_orders_repository import (
    HomeLabRepository,
    HomeMedicationRepository,
)
from app.services.clinical_alert_service import ClinicalAlertService

logger = get_logger(__name__)


def _code(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"


class HomeLabService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = HomeLabRepository(db)

    def create(self, payload, *, actor_user_id: Optional[int] = None):
        self.repo.get_required_patient(payload.patient_id)
        for it in payload.items:
            if not self.repo.catalog(it.lab_test_catalog_id):
                raise BadRequestError(message="Unknown lab test.", detail={"lab_test_catalog_id": it.lab_test_catalog_id})
        code = _code("HLB")
        while self.repo.code_exists(code):
            code = _code("HLB")
        order = self.repo.create_order(
            order_no=code, patient_id=payload.patient_id, home_visit_id=payload.home_visit_id,
            care_plan_id=payload.care_plan_id, status=HomeLabOrderStatus.REQUESTED, priority=payload.priority,
            clinical_note=payload.clinical_note, collection_address=payload.collection_address,
            scheduled_collection_at=payload.scheduled_collection_at, ordered_at=datetime.now(timezone.utc),
            created_by_id=actor_user_id,
        )
        for it in payload.items:
            cat = self.repo.catalog(it.lab_test_catalog_id)
            self.repo.add_item(
                home_lab_order_id=order.id, lab_test_catalog_id=it.lab_test_catalog_id,
                status=HomeLabOrderStatus.REQUESTED, result_unit=getattr(cat, "unit_of_measure", None),
                reference_range=getattr(cat, "reference_range", None),
            )
        self.db.commit()
        self.db.refresh(order)
        return self.repo.decorate(order)

    def get(self, oid: int):
        return self.repo.decorate(self.repo.get(oid))

    def list(self, **kwargs):
        items, total = self.repo.list(**kwargs)
        for o in items:
            self.repo.decorate(o)
        return items, total

    def change_status(self, oid: int, payload, *, actor_user_id: Optional[int] = None):
        o = self.repo.get(oid)
        target = payload.status
        now = datetime.now(timezone.utc)
        if target == HomeLabOrderStatus.SAMPLE_COLLECTED:
            o.sample_collected_at = now
            o.collected_by_staff_id = o.collected_by_staff_id
        elif target == HomeLabOrderStatus.RECEIVED:
            o.received_at = now
        elif target == HomeLabOrderStatus.RESULTED:
            o.resulted_at = now
        o.status = target
        for it in o.items:
            if it.status != HomeLabOrderStatus.RESULTED and target != HomeLabOrderStatus.RESULTED:
                it.status = target
        self.db.commit()
        self.db.refresh(o)
        return self.repo.decorate(o)

    def enter_result(self, item_id: int, payload, *, actor_user_id: Optional[int] = None):
        it = self.repo.get_item(item_id)
        it.result_value = payload.result_value
        if payload.result_unit:
            it.result_unit = payload.result_unit
        if payload.reference_range:
            it.reference_range = payload.reference_range
        it.is_abnormal = payload.is_abnormal
        it.interpretation = payload.interpretation
        it.resulted_at = datetime.now(timezone.utc)
        it.status = HomeLabOrderStatus.RESULTED
        order = self.repo.get(it.home_lab_order_id)
        if all(x.status == HomeLabOrderStatus.RESULTED for x in order.items):
            order.status = HomeLabOrderStatus.RESULTED
            order.resulted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(order)
        if payload.is_abnormal:
            try:
                cat = it.lab_test_catalog
                ClinicalAlertService(self.db).raise_alert(
                    patient_id=order.patient_id,
                    alert_type=AlertType.ABNORMAL_VITALS,
                    severity=AlertSeverity.WARNING,
                    title=f"Abnormal home lab result — {getattr(cat,'name','test')}",
                    message=f"{getattr(cat,'name','Test')}: {payload.result_value or ''} {it.result_unit or ''} (ref {it.reference_range or 'n/a'}).",
                    care_plan_id=order.care_plan_id, home_visit_id=order.home_visit_id,
                    dedupe_key=f"home_lab:{item_id}",
                )
            except Exception as exc:
                logger.warning("Abnormal lab alert failed for item %s: %s", item_id, exc)
        return self.repo.decorate(order)


class HomeMedicationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = HomeMedicationRepository(db)

    def create(self, payload, *, actor_user_id: Optional[int] = None):
        self.repo.get_required_patient(payload.patient_id)
        for it in payload.items:
            if not self.repo.drug(it.drug_id):
                raise BadRequestError(message="Unknown drug.", detail={"drug_id": it.drug_id})
        code = _code("HMD")
        while self.repo.code_exists(code):
            code = _code("HMD")
        order = self.repo.create_order(
            order_no=code, patient_id=payload.patient_id, home_visit_id=payload.home_visit_id,
            care_plan_id=payload.care_plan_id, status=HomeMedicationStatus.PRESCRIBED, note=payload.note,
            delivery_address=payload.delivery_address, prescribed_at=datetime.now(timezone.utc),
            created_by_id=actor_user_id,
        )
        for it in payload.items:
            self.repo.add_item(
                home_medication_order_id=order.id, drug_id=it.drug_id, dosage=it.dosage,
                frequency=it.frequency, duration=it.duration, route=it.route, quantity=it.quantity,
                instructions=it.instructions,
            )
        self.db.commit()
        self.db.refresh(order)
        return self.repo.decorate(order)

    def get(self, oid: int):
        return self.repo.decorate(self.repo.get(oid))

    def list(self, **kwargs):
        items, total = self.repo.list(**kwargs)
        for o in items:
            self.repo.decorate(o)
        return items, total

    def dispense(self, oid: int, payload, *, actor_user_id: Optional[int] = None):
        o = self.repo.get(oid)
        if o.status not in (HomeMedicationStatus.PRESCRIBED,):
            raise BadRequestError(message="Only a prescribed order can be dispensed.")
        o.status = HomeMedicationStatus.DISPENSED
        o.dispensed_at = datetime.now(timezone.utc)
        o.dispensed_by_staff_id = payload.dispensed_by_staff_id
        qmap = payload.quantities or {}
        for it in o.items:
            it.quantity_dispensed = qmap.get(it.id, it.quantity)
        if payload.note:
            o.note = (o.note or "") + f"\n[Dispense] {payload.note}"
        self.db.commit()
        self.db.refresh(o)
        return self.repo.decorate(o)

    def deliver(self, oid: int, payload, *, mark_delivered: bool, actor_user_id: Optional[int] = None):
        o = self.repo.get(oid)
        if mark_delivered:
            o.status = HomeMedicationStatus.DELIVERED
            o.delivered_at = datetime.now(timezone.utc)
            o.delivered_by_staff_id = payload.delivered_by_staff_id
        else:
            o.status = HomeMedicationStatus.OUT_FOR_DELIVERY
        if payload.courier_name:
            o.courier_name = payload.courier_name
        if payload.delivery_tracking_ref:
            o.delivery_tracking_ref = payload.delivery_tracking_ref
        self.db.commit()
        self.db.refresh(o)
        return self.repo.decorate(o)

    def change_status(self, oid: int, payload, *, actor_user_id: Optional[int] = None):
        o = self.repo.get(oid)
        o.status = payload.status
        if payload.status == HomeMedicationStatus.DELIVERED and not o.delivered_at:
            o.delivered_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(o)
        return self.repo.decorate(o)
