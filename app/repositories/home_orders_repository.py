# app/repositories/home_orders_repository.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.all_models import Drug, LabTestCatalog, Patient
from app.models.home_health_models import (
    HomeLabOrder,
    HomeLabOrderItem,
    HomeMedicationItem,
    HomeMedicationOrder,
)


class _Base:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_patient(self, patient_id: int) -> Patient:
        p = (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
            .first()
        )
        if not p:
            raise NotFoundError(message="Patient not found.", detail={"patient_id": patient_id})
        return p

    def patient_name(self, patient_id: int) -> Optional[str]:
        row = self.db.query(Patient.first_name, Patient.last_name).filter(Patient.id == patient_id).first()
        return " ".join(x for x in [row[0], row[1]] if x).strip() if row else None


class HomeLabRepository(_Base):
    def catalog(self, cid: int) -> Optional[LabTestCatalog]:
        return self.db.query(LabTestCatalog).filter(LabTestCatalog.id == cid).first()

    def create_order(self, **kwargs) -> HomeLabOrder:
        o = HomeLabOrder(**kwargs)
        self.db.add(o)
        self.db.flush()
        return o

    def add_item(self, **kwargs) -> HomeLabOrderItem:
        it = HomeLabOrderItem(**kwargs)
        self.db.add(it)
        self.db.flush()
        return it

    def get(self, oid: int) -> HomeLabOrder:
        o = (
            self.db.query(HomeLabOrder)
            .filter(HomeLabOrder.id == oid, HomeLabOrder.is_deleted.is_(False))
            .first()
        )
        if not o:
            raise NotFoundError(message="Home lab order not found.", detail={"id": oid})
        return o

    def get_item(self, item_id: int) -> HomeLabOrderItem:
        it = (
            self.db.query(HomeLabOrderItem)
            .filter(HomeLabOrderItem.id == item_id, HomeLabOrderItem.is_deleted.is_(False))
            .first()
        )
        if not it:
            raise NotFoundError(message="Lab order item not found.", detail={"item_id": item_id})
        return it

    def code_exists(self, code: str) -> bool:
        return self.db.query(HomeLabOrder.id).filter(HomeLabOrder.order_no == code).first() is not None

    def list(self, *, patient_id=None, home_visit_id=None, care_plan_id=None, status=None, skip=0, limit=50):
        q = self.db.query(HomeLabOrder).filter(HomeLabOrder.is_deleted.is_(False))
        if patient_id:
            q = q.filter(HomeLabOrder.patient_id == patient_id)
        if home_visit_id:
            q = q.filter(HomeLabOrder.home_visit_id == home_visit_id)
        if care_plan_id:
            q = q.filter(HomeLabOrder.care_plan_id == care_plan_id)
        if status:
            q = q.filter(HomeLabOrder.status == status)
        total = q.with_entities(func.count(HomeLabOrder.id)).scalar() or 0
        items = q.order_by(HomeLabOrder.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def decorate(self, order: HomeLabOrder) -> HomeLabOrder:
        order.patient_name = self.patient_name(order.patient_id)
        for it in order.items:
            cat = it.lab_test_catalog
            it.test_name = getattr(cat, "name", None)
            it.test_code = getattr(cat, "code", None)
        return order


class HomeMedicationRepository(_Base):
    def drug(self, did: int) -> Optional[Drug]:
        return self.db.query(Drug).filter(Drug.id == did).first()

    def create_order(self, **kwargs) -> HomeMedicationOrder:
        o = HomeMedicationOrder(**kwargs)
        self.db.add(o)
        self.db.flush()
        return o

    def add_item(self, **kwargs) -> HomeMedicationItem:
        it = HomeMedicationItem(**kwargs)
        self.db.add(it)
        self.db.flush()
        return it

    def get(self, oid: int) -> HomeMedicationOrder:
        o = (
            self.db.query(HomeMedicationOrder)
            .filter(HomeMedicationOrder.id == oid, HomeMedicationOrder.is_deleted.is_(False))
            .first()
        )
        if not o:
            raise NotFoundError(message="Home medication order not found.", detail={"id": oid})
        return o

    def code_exists(self, code: str) -> bool:
        return self.db.query(HomeMedicationOrder.id).filter(HomeMedicationOrder.order_no == code).first() is not None

    def list(self, *, patient_id=None, home_visit_id=None, care_plan_id=None, status=None, skip=0, limit=50):
        q = self.db.query(HomeMedicationOrder).filter(HomeMedicationOrder.is_deleted.is_(False))
        if patient_id:
            q = q.filter(HomeMedicationOrder.patient_id == patient_id)
        if home_visit_id:
            q = q.filter(HomeMedicationOrder.home_visit_id == home_visit_id)
        if care_plan_id:
            q = q.filter(HomeMedicationOrder.care_plan_id == care_plan_id)
        if status:
            q = q.filter(HomeMedicationOrder.status == status)
        total = q.with_entities(func.count(HomeMedicationOrder.id)).scalar() or 0
        items = q.order_by(HomeMedicationOrder.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def decorate(self, order: HomeMedicationOrder) -> HomeMedicationOrder:
        order.patient_name = self.patient_name(order.patient_id)
        for it in order.items:
            d = it.drug
            it.drug_name = getattr(d, "name", None)
            it.drug_strength = getattr(d, "strength", None)
        return order
