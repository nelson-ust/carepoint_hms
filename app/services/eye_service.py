# app/services/eye_service.py
from __future__ import annotations

"""
Service layer for the Eye / Ophthalmology clinic module.

Covers the ophthalmic examination (visual acuity, refraction, intraocular
pressure, anterior / posterior segment findings) and the dispensed spectacle
prescription, so a standalone eye clinic can run its clinical encounter on the
shared patient / visit / billing backbone.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.enums import EncounterStatus, SpectacleLensType, StockMovementType
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    ContactLensPrescription,
    EyeExam,
    EyeRecall,
    InventoryStockItem,
    OpticalOrder,
    OpticalOrderItem,
    OpticalProduct,
    Patient,
    SpectaclePrescription,
    StaffProfile,
    StockMovement,
    User,
)

_CL_NUM = (
    "od_sphere", "od_cyl", "od_add", "od_base_curve", "od_diameter",
    "os_sphere", "os_cyl", "os_add", "os_base_curve", "os_diameter",
)
_CL_INT = ("od_axis", "os_axis")
_CL_STR = ("modality", "od_brand", "os_brand", "notes")

_OPTICAL_ITEM_TYPES = {"FRAME", "LENS", "COATING", "SERVICE", "OTHER"}
_OPTICAL_STATUSES = {"PENDING", "ORDERED", "READY", "COLLECTED", "CANCELLED"}

_EYE_NUM_FIELDS = (
    "ref_sphere_od", "ref_sphere_os", "ref_cyl_od", "ref_cyl_os",
    "ref_add_od", "ref_add_os", "iop_od", "iop_os",
)
_EYE_INT_FIELDS = ("ref_axis_od", "ref_axis_os")
_EYE_STR_FIELDS = (
    "chief_complaint", "history_note", "external_note",
    "va_dist_unaided_od", "va_dist_unaided_os", "va_dist_aided_od", "va_dist_aided_os",
    "va_near_od", "va_near_os", "pinhole_od", "pinhole_os", "iop_method",
    "anterior_od", "anterior_os", "posterior_od", "posterior_os",
    "impression", "plan_note",
)
_RX_NUM = ("od_sphere", "od_cyl", "od_add", "os_sphere", "os_cyl", "os_add")
_RX_INT = ("od_axis", "os_axis")


def _d(v) -> Optional[str]:
    return None if v is None else str(v)


def _age(dob: Optional[date]) -> Optional[int]:
    if not dob:
        return None
    t = date.today()
    return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))


class EyeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _staff_id_for_user(self, actor) -> Optional[int]:
        uid = getattr(actor, "id", None)
        if uid is None:
            return None
        sp = self.db.query(StaffProfile).filter(StaffProfile.user_id == uid).first()
        return sp.id if sp else None

    def _staff_name(self, staff_id: Optional[int]) -> Optional[str]:
        if not staff_id:
            return None
        row = (self.db.query(User.first_name, User.last_name)
               .join(StaffProfile, StaffProfile.user_id == User.id)
               .filter(StaffProfile.id == staff_id).first())
        return f"{row[0]} {row[1]}" if row else None

    def _patient_brief(self, patient_id: int) -> dict:
        p = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if not p:
            return {"id": patient_id, "name": "Unknown", "hospital_number": None}
        return {
            "id": p.id, "name": f"{p.first_name} {p.last_name}",
            "hospital_number": p.hospital_number,
            "gender": getattr(p.gender, "value", p.gender) if p.gender else None,
            "age": _age(p.date_of_birth), "phone_number": p.phone_number,
        }

    def _rx_dict(self, r: SpectaclePrescription) -> dict:
        d = {
            "id": r.id, "patient_id": r.patient_id, "exam_id": r.exam_id,
            "prescriber_staff_id": r.prescriber_staff_id,
            "prescriber": self._staff_name(r.prescriber_staff_id),
            "prescribed_date": r.prescribed_date.isoformat() if r.prescribed_date else None,
            "pd": r.pd, "lens_type": getattr(r.lens_type, "value", r.lens_type),
            "usage": r.usage, "notes": r.notes,
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        }
        for f in _RX_NUM:
            d[f] = _d(getattr(r, f))
        for f in _RX_INT:
            d[f] = getattr(r, f)
        return d

    def _exam_dict(self, e: EyeExam, *, full: bool = False) -> dict:
        d = {
            "id": e.id, "patient_id": e.patient_id, "visit_id": e.visit_id,
            "consultation_id": e.consultation_id,
            "clinician_staff_id": e.clinician_staff_id,
            "clinician": self._staff_name(e.clinician_staff_id),
            "status": getattr(e.status, "value", e.status),
            "examined_at": e.examined_at.isoformat() if e.examined_at else None,
            "created_at": e.created_at.isoformat() if getattr(e, "created_at", None) else None,
            "patient": self._patient_brief(e.patient_id),
        }
        for f in _EYE_STR_FIELDS:
            d[f] = getattr(e, f)
        for f in _EYE_NUM_FIELDS:
            d[f] = _d(getattr(e, f))
        for f in _EYE_INT_FIELDS:
            d[f] = getattr(e, f)
        if full:
            rxs = (self.db.query(SpectaclePrescription)
                   .filter(SpectaclePrescription.is_deleted.is_(False),
                           SpectaclePrescription.exam_id == e.id)
                   .order_by(SpectaclePrescription.id.desc()).all())
            d["prescriptions"] = [self._rx_dict(r) for r in rxs]
        return d

    def list_exams(self, *, patient_id: Optional[int], skip: int, limit: int):
        q = self.db.query(EyeExam).filter(EyeExam.is_deleted.is_(False))
        if patient_id:
            q = q.filter(EyeExam.patient_id == patient_id)
        total = q.count()
        rows = q.order_by(EyeExam.id.desc()).offset(skip).limit(limit).all()
        return [self._exam_dict(e) for e in rows], total

    def get_exam(self, exam_id: int) -> dict:
        e = (self.db.query(EyeExam)
             .options(selectinload(EyeExam.prescriptions))
             .filter(EyeExam.id == exam_id, EyeExam.is_deleted.is_(False)).first())
        if not e:
            raise NotFoundError("Eye exam not found.")
        return self._exam_dict(e, full=True)

    def _coerce(self, data: dict) -> dict:
        out = {}
        for f in _EYE_STR_FIELDS:
            if f in data:
                out[f] = data[f]
        for f in _EYE_NUM_FIELDS:
            if f in data and data[f] is not None:
                out[f] = Decimal(str(data[f]))
        for f in _EYE_INT_FIELDS:
            if f in data and data[f] is not None:
                out[f] = int(data[f])
        return out

    def create_exam(self, data: dict, actor) -> dict:
        patient_id = data.get("patient_id")
        if not patient_id:
            raise BadRequestError("patient_id is required.")
        if not self.db.query(Patient.id).filter(Patient.id == patient_id,
                                                Patient.is_deleted.is_(False)).first():
            raise NotFoundError("Patient not found.")
        e = EyeExam(
            patient_id=patient_id, visit_id=data.get("visit_id"),
            consultation_id=data.get("consultation_id"),
            clinician_staff_id=data.get("clinician_staff_id") or self._staff_id_for_user(actor),
            examined_at=datetime.now(timezone.utc),
            **self._coerce(data),
        )
        self.db.add(e)
        self.db.commit()
        self.db.refresh(e)
        return self._exam_dict(e, full=True)

    def update_exam(self, exam_id: int, data: dict) -> dict:
        e = self.db.query(EyeExam).filter(
            EyeExam.id == exam_id, EyeExam.is_deleted.is_(False)).first()
        if not e:
            raise NotFoundError("Eye exam not found.")
        for f, v in self._coerce(data).items():
            setattr(e, f, v)
        if data.get("clinician_staff_id"):
            e.clinician_staff_id = data["clinician_staff_id"]
        if data.get("status"):
            e.status = EncounterStatus(data["status"])
        self.db.commit()
        self.db.refresh(e)
        return self._exam_dict(e, full=True)

    def list_prescriptions(self, *, patient_id: Optional[int], skip: int, limit: int):
        q = self.db.query(SpectaclePrescription).filter(
            SpectaclePrescription.is_deleted.is_(False))
        if patient_id:
            q = q.filter(SpectaclePrescription.patient_id == patient_id)
        total = q.count()
        rows = q.order_by(SpectaclePrescription.id.desc()).offset(skip).limit(limit).all()
        return [self._rx_dict(r) for r in rows], total

    def get_prescription(self, rx_id: int) -> dict:
        r = self.db.query(SpectaclePrescription).filter(
            SpectaclePrescription.id == rx_id,
            SpectaclePrescription.is_deleted.is_(False)).first()
        if not r:
            raise NotFoundError("Prescription not found.")
        d = self._rx_dict(r)
        d["patient"] = self._patient_brief(r.patient_id)
        return d

    def create_prescription(self, data: dict, actor) -> dict:
        if not data.get("patient_id"):
            raise BadRequestError("patient_id is required.")
        kwargs = {}
        for f in _RX_NUM:
            if data.get(f) is not None:
                kwargs[f] = Decimal(str(data[f]))
        for f in _RX_INT:
            if data.get(f) is not None:
                kwargs[f] = int(data[f])
        r = SpectaclePrescription(
            patient_id=data["patient_id"], exam_id=data.get("exam_id"),
            prescriber_staff_id=data.get("prescriber_staff_id") or self._staff_id_for_user(actor),
            prescribed_date=data.get("prescribed_date") or date.today(),
            pd=data.get("pd"),
            lens_type=SpectacleLensType(data.get("lens_type") or "SINGLE_VISION"),
            usage=data.get("usage"), notes=data.get("notes"),
            **kwargs,
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return self._rx_dict(r)

    def worklist(self, *, limit: int = 50):
        rows = (self.db.query(EyeExam).filter(EyeExam.is_deleted.is_(False))
                .order_by(EyeExam.id.desc()).limit(limit).all())
        return [self._exam_dict(e) for e in rows]

    def stats(self) -> dict:
        exams = self.db.query(func.count(EyeExam.id)).filter(
            EyeExam.is_deleted.is_(False)).scalar() or 0
        open_exams = self.db.query(func.count(EyeExam.id)).filter(
            EyeExam.is_deleted.is_(False),
            EyeExam.status == EncounterStatus.OPEN).scalar() or 0
        rx = self.db.query(func.count(SpectaclePrescription.id)).filter(
            SpectaclePrescription.is_deleted.is_(False)).scalar() or 0
        raised_iop = self.db.query(func.count(EyeExam.id)).filter(
            EyeExam.is_deleted.is_(False),
            (func.coalesce(EyeExam.iop_od, 0) > 21) | (func.coalesce(EyeExam.iop_os, 0) > 21)
        ).scalar() or 0
        cl_rx = self.db.query(func.count(ContactLensPrescription.id)).filter(
            ContactLensPrescription.is_deleted.is_(False)).scalar() or 0
        orders_open = self.db.query(func.count(OpticalOrder.id)).filter(
            OpticalOrder.is_deleted.is_(False),
            OpticalOrder.status.in_(["PENDING", "ORDERED", "READY"])).scalar() or 0
        recalls_due = self.db.query(func.count(EyeRecall.id)).filter(
            EyeRecall.is_deleted.is_(False),
            EyeRecall.status.in_(["DUE", "SCHEDULED"]),
            EyeRecall.due_date <= date.today()).scalar() or 0
        return {
            "exams_total": exams, "exams_open": open_exams,
            "prescriptions_total": rx, "raised_iop_flagged": raised_iop,
            "contact_lens_rx_total": cl_rx, "optical_orders_open": orders_open,
            "recalls_due": recalls_due,
            "optical_products": self.db.query(func.count(OpticalProduct.id)).filter(
                OpticalProduct.is_deleted.is_(False)).scalar() or 0,
            "optical_low_stock": self.db.query(func.count(OpticalProduct.id)).filter(
                OpticalProduct.is_deleted.is_(False),
                OpticalProduct.reorder_level.isnot(None),
                OpticalProduct.quantity_on_hand <= OpticalProduct.reorder_level).scalar() or 0,
        }

    # ======================================================================
    # CONTACT-LENS PRESCRIPTIONS
    # ======================================================================
    def _cl_dict(self, r: ContactLensPrescription) -> dict:
        d = {
            "id": r.id, "patient_id": r.patient_id, "exam_id": r.exam_id,
            "prescriber_staff_id": r.prescriber_staff_id,
            "prescriber": self._staff_name(r.prescriber_staff_id),
            "prescribed_date": r.prescribed_date.isoformat() if r.prescribed_date else None,
            "modality": r.modality, "od_brand": r.od_brand, "os_brand": r.os_brand,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        }
        for f in _CL_NUM:
            d[f] = _d(getattr(r, f))
        for f in _CL_INT:
            d[f] = getattr(r, f)
        return d

    def list_contact_lens(self, *, patient_id: Optional[int], skip: int, limit: int):
        q = self.db.query(ContactLensPrescription).filter(
            ContactLensPrescription.is_deleted.is_(False))
        if patient_id:
            q = q.filter(ContactLensPrescription.patient_id == patient_id)
        total = q.count()
        rows = q.order_by(ContactLensPrescription.id.desc()).offset(skip).limit(limit).all()
        return [self._cl_dict(r) for r in rows], total

    def create_contact_lens(self, data: dict, actor) -> dict:
        if not data.get("patient_id"):
            raise BadRequestError("patient_id is required.")
        kwargs = {}
        for f in _CL_NUM:
            if data.get(f) is not None:
                kwargs[f] = Decimal(str(data[f]))
        for f in _CL_INT:
            if data.get(f) is not None:
                kwargs[f] = int(data[f])
        for f in _CL_STR:
            if data.get(f) is not None:
                kwargs[f] = data[f]
        r = ContactLensPrescription(
            patient_id=data["patient_id"], exam_id=data.get("exam_id"),
            prescriber_staff_id=data.get("prescriber_staff_id") or self._staff_id_for_user(actor),
            prescribed_date=data.get("prescribed_date") or date.today(),
            **kwargs,
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return self._cl_dict(r)

    # ======================================================================
    # OPTICAL DISPENSING ORDERS
    # ======================================================================
    def _order_item_dict(self, it: OpticalOrderItem) -> dict:
        return {
            "id": it.id, "item_type": it.item_type, "stock_item_id": it.stock_item_id,
            "optical_product_id": it.optical_product_id,
            "item_name": it.item_name, "quantity": _d(it.quantity),
            "unit_price": _d(it.unit_price), "line_total": _d(it.line_total),
        }

    def _order_dict(self, o: OpticalOrder, *, full: bool = True) -> dict:
        d = {
            "id": o.id, "order_no": o.order_no, "patient_id": o.patient_id,
            "exam_id": o.exam_id, "spectacle_prescription_id": o.spectacle_prescription_id,
            "visit_id": o.visit_id, "dispensed_by_staff_id": o.dispensed_by_staff_id,
            "dispensed_by": self._staff_name(o.dispensed_by_staff_id),
            "status": o.status, "subtotal": _d(o.subtotal),
            "discount_amount": _d(o.discount_amount), "total_amount": _d(o.total_amount),
            "note": o.note,
            "ordered_at": o.ordered_at.isoformat() if o.ordered_at else None,
            "ready_at": o.ready_at.isoformat() if o.ready_at else None,
            "collected_at": o.collected_at.isoformat() if o.collected_at else None,
            "billed_at": o.billed_at.isoformat() if o.billed_at else None,
            "is_billed": o.billed_at is not None,
            "created_at": o.created_at.isoformat() if getattr(o, "created_at", None) else None,
            "patient": self._patient_brief(o.patient_id),
        }
        if full:
            items = [it for it in o.items if not it.is_deleted] if o.items else []
            d["items"] = [self._order_item_dict(it) for it in items]
        return d

    def _next_order_no(self) -> str:
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        count = (self.db.query(func.count(OpticalOrder.id))
                 .filter(OpticalOrder.created_at >= start).scalar() or 0)
        return f"OPT-{today.strftime('%Y%m%d')}-{count + 1:04d}"

    def list_orders(self, *, patient_id: Optional[int] = None, status: Optional[str] = None,
                    skip: int = 0, limit: int = 100):
        q = self.db.query(OpticalOrder).filter(OpticalOrder.is_deleted.is_(False))
        if patient_id:
            q = q.filter(OpticalOrder.patient_id == patient_id)
        if status:
            q = q.filter(OpticalOrder.status == status.upper())
        total = q.count()
        rows = (q.options(selectinload(OpticalOrder.items))
                .order_by(OpticalOrder.id.desc()).offset(skip).limit(limit).all())
        return [self._order_dict(o) for o in rows], total

    def get_order(self, order_id: int) -> dict:
        o = (self.db.query(OpticalOrder)
             .options(selectinload(OpticalOrder.items))
             .filter(OpticalOrder.id == order_id, OpticalOrder.is_deleted.is_(False)).first())
        if not o:
            raise NotFoundError("Optical order not found.")
        return self._order_dict(o)

    def create_order(self, data: dict, actor) -> dict:
        patient_id = data.get("patient_id")
        if not patient_id:
            raise BadRequestError("patient_id is required.")
        lines = data.get("items") or []
        if not lines:
            raise BadRequestError("An optical order needs at least one item.")
        if not self.db.query(Patient.id).filter(
                Patient.id == patient_id, Patient.is_deleted.is_(False)).first():
            raise NotFoundError("Patient not found.")

        order = OpticalOrder(
            order_no=self._next_order_no(), patient_id=patient_id,
            exam_id=data.get("exam_id"),
            spectacle_prescription_id=data.get("spectacle_prescription_id"),
            visit_id=data.get("visit_id"),
            dispensed_by_staff_id=self._staff_id_for_user(actor),
            status=(data.get("status") or "PENDING").upper(),
            note=data.get("note"),
        )
        subtotal = Decimal("0.00")
        items: list[OpticalOrderItem] = []
        for raw in lines:
            name = (raw.get("item_name") or "").strip()
            itype = (raw.get("item_type") or "OTHER").upper()
            price = raw.get("unit_price")
            prod_id = raw.get("optical_product_id")
            if prod_id:
                product = self.db.query(OpticalProduct).filter(
                    OpticalProduct.id == prod_id,
                    OpticalProduct.is_deleted.is_(False)).first()
                if not product:
                    raise NotFoundError(f"Optical product #{prod_id} not found.")
                if not name:
                    name = product.name
                if price in (None, ""):
                    price = product.sell_price
                if product.category in _OPTICAL_ITEM_TYPES:
                    itype = product.category
            if not name:
                raise BadRequestError("Each item needs a name.")
            if itype not in _OPTICAL_ITEM_TYPES:
                itype = "OTHER"
            qty = Decimal(str(raw.get("quantity") or 1))
            price = Decimal(str(price or 0))
            line_total = (qty * price).quantize(Decimal("0.01"))
            subtotal += line_total
            items.append(OpticalOrderItem(
                item_type=itype, optical_product_id=prod_id,
                stock_item_id=raw.get("stock_item_id"),
                item_name=name, quantity=qty, unit_price=price, line_total=line_total,
            ))
        discount = Decimal(str(data.get("discount_amount") or 0))
        total = (subtotal - discount).quantize(Decimal("0.01"))
        if total < 0:
            raise BadRequestError("Discount cannot exceed the order subtotal.")
        order.subtotal = subtotal.quantize(Decimal("0.01"))
        order.discount_amount = discount
        order.total_amount = total
        order.items = items
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return self.get_order(order.id)

    def _commit_stock(self, order: OpticalOrder) -> None:
        """Decrement linked inventory stock for the order's items (once)."""
        if order.stock_committed_at is not None:
            return
        now = datetime.now(timezone.utc)
        for it in order.items:
            if it.is_deleted:
                continue
            if it.optical_product_id:
                prod = self.db.query(OpticalProduct).filter(
                    OpticalProduct.id == it.optical_product_id,
                    OpticalProduct.is_deleted.is_(False)).first()
                if prod is not None:
                    prod.quantity_on_hand = Decimal(str(prod.quantity_on_hand or 0)) - Decimal(str(it.quantity))
            if not it.stock_item_id:
                continue
            stock = self.db.query(InventoryStockItem).filter(
                InventoryStockItem.id == it.stock_item_id,
                InventoryStockItem.is_deleted.is_(False)).first()
            if stock is None:
                continue
            stock.quantity_on_hand = Decimal(str(stock.quantity_on_hand or 0)) - Decimal(str(it.quantity))
            self.db.add(StockMovement(
                store_id=stock.store_id, stock_item_id=stock.id,
                performed_by_staff_id=order.dispensed_by_staff_id,
                movement_type=StockMovementType.DISPENSE,
                reference_no=order.order_no, quantity=Decimal(str(it.quantity)),
                balance_after=stock.quantity_on_hand, movement_date=now,
                note=f"Optical dispense {order.order_no}",
            ))
        order.stock_committed_at = now

    def update_order_status(self, order_id: int, status: str, actor=None) -> dict:
        o = (self.db.query(OpticalOrder)
             .options(selectinload(OpticalOrder.items))
             .filter(OpticalOrder.id == order_id, OpticalOrder.is_deleted.is_(False)).first())
        if not o:
            raise NotFoundError("Optical order not found.")
        status = (status or "").upper()
        if status not in _OPTICAL_STATUSES:
            raise BadRequestError(f"Invalid status: {status}.")
        now = datetime.now(timezone.utc)
        o.status = status
        if status == "ORDERED" and o.ordered_at is None:
            o.ordered_at = now
        elif status == "READY" and o.ready_at is None:
            o.ready_at = now
        elif status == "COLLECTED":
            if o.collected_at is None:
                o.collected_at = now
            # Dispensing the order consumes any linked stock.
            self._commit_stock(o)
        self.db.commit()
        return self.get_order(o.id)

    def bill_order(self, order_id: int, *, actor=None) -> dict:
        """Push an optical order's total onto the patient's visit charge sheet."""
        from app.services.billing_service import BillingService

        o = (self.db.query(OpticalOrder)
             .options(selectinload(OpticalOrder.items))
             .filter(OpticalOrder.id == order_id, OpticalOrder.is_deleted.is_(False)).first())
        if not o:
            raise NotFoundError("Optical order not found.")
        if o.billed_at is not None:
            raise BadRequestError("This order has already been billed.")
        if not o.visit_id:
            raise BadRequestError(
                "This order is not linked to a visit, so it cannot be billed. "
                "Attach it to a visit first.")
        items = []
        for it in o.items:
            if it.is_deleted:
                continue
            items.append({
                "service_name": f"{it.item_type.title()}: {it.item_name}",
                "service_code": None, "quantity": it.quantity,
                "unit_price": it.unit_price, "discount_amount": 0,
            })
        if not items:
            raise BadRequestError("This order has no items to bill.")
        actor_user_id = getattr(actor, "id", None)
        summary = BillingService(self.db).record_visit_services(
            o.visit_id, items, rendered_by_user_id=actor_user_id)
        o.billed_at = datetime.now(timezone.utc)
        self.db.commit()
        return {"order": self.get_order(o.id), "billing": summary}

    # ======================================================================
    # RECALLS
    # ======================================================================
    def _recall_dict(self, r: EyeRecall) -> dict:
        today = date.today()
        overdue = r.status in ("DUE", "SCHEDULED") and r.due_date is not None and r.due_date < today
        return {
            "id": r.id, "patient_id": r.patient_id, "exam_id": r.exam_id,
            "recall_type": r.recall_type,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "interval_months": r.interval_months, "status": r.status, "note": r.note,
            "created_by_staff_id": r.created_by_staff_id,
            "created_by": self._staff_name(r.created_by_staff_id),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "is_overdue": bool(overdue), "patient": self._patient_brief(r.patient_id),
        }

    def list_recalls(self, *, patient_id: Optional[int] = None, status: Optional[str] = None,
                     due_before: Optional[date] = None, skip: int = 0, limit: int = 100):
        q = self.db.query(EyeRecall).filter(EyeRecall.is_deleted.is_(False))
        if patient_id:
            q = q.filter(EyeRecall.patient_id == patient_id)
        if status:
            q = q.filter(EyeRecall.status == status.upper())
        if due_before:
            q = q.filter(EyeRecall.due_date <= due_before)
        total = q.count()
        rows = q.order_by(EyeRecall.due_date.asc()).offset(skip).limit(limit).all()
        return [self._recall_dict(r) for r in rows], total

    def create_recall(self, data: dict, actor) -> dict:
        patient_id = data.get("patient_id")
        if not patient_id:
            raise BadRequestError("patient_id is required.")
        if not data.get("due_date"):
            raise BadRequestError("due_date is required.")
        if not self.db.query(Patient.id).filter(
                Patient.id == patient_id, Patient.is_deleted.is_(False)).first():
            raise NotFoundError("Patient not found.")
        r = EyeRecall(
            patient_id=patient_id, exam_id=data.get("exam_id"),
            recall_type=(data.get("recall_type") or None),
            due_date=data["due_date"], interval_months=data.get("interval_months"),
            status=(data.get("status") or "DUE").upper(), note=data.get("note"),
            created_by_staff_id=self._staff_id_for_user(actor),
        )
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return self._recall_dict(r)

    def update_recall(self, recall_id: int, data: dict) -> dict:
        r = self.db.query(EyeRecall).filter(
            EyeRecall.id == recall_id, EyeRecall.is_deleted.is_(False)).first()
        if not r:
            raise NotFoundError("Recall not found.")
        for f in ("recall_type", "due_date", "interval_months", "note", "exam_id"):
            if f in data and data[f] is not None:
                setattr(r, f, data[f])
        if data.get("status"):
            r.status = data["status"].upper()
            if r.status == "COMPLETED" and r.completed_at is None:
                r.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(r)
        return self._recall_dict(r)

    # ======================================================================
    # OPTICAL INVENTORY (frames, lenses, products)
    # ======================================================================
    def _product_dict(self, p: OpticalProduct) -> dict:
        qoh = Decimal(str(p.quantity_on_hand or 0))
        low = p.reorder_level is not None and qoh <= Decimal(str(p.reorder_level))
        return {
            "id": p.id, "category": p.category, "name": p.name, "brand": p.brand,
            "sku": p.sku, "spec": p.spec, "unit_cost": _d(p.unit_cost),
            "sell_price": _d(p.sell_price), "quantity_on_hand": _d(p.quantity_on_hand),
            "reorder_level": _d(p.reorder_level), "is_active": p.is_active,
            "note": p.note, "is_low_stock": bool(low),
        }

    def list_products(self, *, search=None, category=None, active_only=False,
                      low_stock=False, skip=0, limit=300):
        q = self.db.query(OpticalProduct).filter(OpticalProduct.is_deleted.is_(False))
        if active_only:
            q = q.filter(OpticalProduct.is_active.is_(True))
        if category:
            q = q.filter(OpticalProduct.category == category.upper())
        if low_stock:
            q = q.filter(OpticalProduct.reorder_level.isnot(None),
                         OpticalProduct.quantity_on_hand <= OpticalProduct.reorder_level)
        if search:
            like = f"%{search.strip()}%"
            q = q.filter(OpticalProduct.name.ilike(like) |
                         OpticalProduct.brand.ilike(like) |
                         OpticalProduct.sku.ilike(like))
        total = q.count()
        rows = (q.order_by(OpticalProduct.category, OpticalProduct.name)
                .offset(skip).limit(limit).all())
        return [self._product_dict(r) for r in rows], total

    def create_product(self, data: dict) -> dict:
        if not data.get("name"):
            raise BadRequestError("name is required.")
        p = OpticalProduct(
            category=(data.get("category") or "FRAME").upper(),
            name=data["name"].strip(), brand=(data.get("brand") or None),
            sku=(data.get("sku") or None), spec=(data.get("spec") or None),
            unit_cost=Decimal(str(data["unit_cost"])) if data.get("unit_cost") not in (None, "") else None,
            sell_price=Decimal(str(data.get("sell_price") or 0)),
            quantity_on_hand=Decimal(str(data.get("quantity_on_hand") or 0)),
            reorder_level=Decimal(str(data["reorder_level"])) if data.get("reorder_level") not in (None, "") else None,
            is_active=data.get("is_active", True), note=(data.get("note") or None),
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return self._product_dict(p)

    def update_product(self, pid: int, data: dict) -> dict:
        p = self.db.query(OpticalProduct).filter(
            OpticalProduct.id == pid, OpticalProduct.is_deleted.is_(False)).first()
        if not p:
            raise NotFoundError("Optical product not found.")
        for f in ("name", "brand", "sku", "spec", "is_active", "note"):
            if f in data and data[f] is not None:
                setattr(p, f, data[f])
        if data.get("category"):
            p.category = data["category"].upper()
        for f in ("unit_cost", "sell_price", "reorder_level"):
            if data.get(f) not in (None, ""):
                setattr(p, f, Decimal(str(data[f])))
        self.db.commit()
        self.db.refresh(p)
        return self._product_dict(p)

    def adjust_product_stock(self, pid: int, delta, note=None) -> dict:
        p = self.db.query(OpticalProduct).filter(
            OpticalProduct.id == pid, OpticalProduct.is_deleted.is_(False)).first()
        if not p:
            raise NotFoundError("Optical product not found.")
        p.quantity_on_hand = Decimal(str(p.quantity_on_hand or 0)) + Decimal(str(delta))
        if note:
            p.note = note
        self.db.commit()
        self.db.refresh(p)
        return self._product_dict(p)

    def delete_product(self, pid: int) -> None:
        p = self.db.query(OpticalProduct).filter(
            OpticalProduct.id == pid, OpticalProduct.is_deleted.is_(False)).first()
        if not p:
            raise NotFoundError("Optical product not found.")
        p.is_deleted = True
        self.db.commit()
