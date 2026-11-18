# app/api/v1/endpoints/eye_routes.py
from __future__ import annotations

"""
FastAPI routes for the Eye / Ophthalmology clinic module.

Sub-routes
----------
- /eye-clinic/exams          -- ophthalmic exams (VA, refraction, IOP, segments)
- /eye-clinic/prescriptions  -- dispensed spectacle prescriptions
- /eye-clinic/worklist       -- recent eye encounters
- /eye-clinic/stats          -- dashboard aggregates

Permission codes: EYE_READ (view) | EYE_MANAGE (write).
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.services.eye_service import EyeService
from app.seeds.eye_flow_seed import describe_eye_flow, seed_eye_visit_flow
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/eye-clinic", tags=["Eye Clinic"])

Reader = Annotated[User, Depends(require_permission("EYE_READ", "EYE_MANAGE"))]
Manager = Annotated[User, Depends(require_permission("EYE_MANAGE"))]
Db = Annotated[Session, Depends(get_db)]


class ExamCreateSchema(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    consultation_id: Optional[int] = None
    clinician_staff_id: Optional[int] = None
    chief_complaint: Optional[str] = None
    history_note: Optional[str] = None
    external_note: Optional[str] = None
    va_dist_unaided_od: Optional[str] = None
    va_dist_unaided_os: Optional[str] = None
    va_dist_aided_od: Optional[str] = None
    va_dist_aided_os: Optional[str] = None
    va_near_od: Optional[str] = None
    va_near_os: Optional[str] = None
    pinhole_od: Optional[str] = None
    pinhole_os: Optional[str] = None
    ref_sphere_od: Optional[Decimal] = None
    ref_sphere_os: Optional[Decimal] = None
    ref_cyl_od: Optional[Decimal] = None
    ref_cyl_os: Optional[Decimal] = None
    ref_axis_od: Optional[int] = Field(None, ge=0, le=180)
    ref_axis_os: Optional[int] = Field(None, ge=0, le=180)
    ref_add_od: Optional[Decimal] = None
    ref_add_os: Optional[Decimal] = None
    iop_od: Optional[Decimal] = Field(None, ge=0, le=90)
    iop_os: Optional[Decimal] = Field(None, ge=0, le=90)
    iop_method: Optional[str] = None
    anterior_od: Optional[str] = None
    anterior_os: Optional[str] = None
    posterior_od: Optional[str] = None
    posterior_os: Optional[str] = None
    impression: Optional[str] = None
    plan_note: Optional[str] = None


class ExamUpdateSchema(ExamCreateSchema):
    patient_id: Optional[int] = None
    status: Optional[str] = None


class PrescriptionCreateSchema(BaseModel):
    patient_id: int
    exam_id: Optional[int] = None
    prescriber_staff_id: Optional[int] = None
    prescribed_date: Optional[date] = None
    od_sphere: Optional[Decimal] = None
    od_cyl: Optional[Decimal] = None
    od_axis: Optional[int] = Field(None, ge=0, le=180)
    od_add: Optional[Decimal] = None
    os_sphere: Optional[Decimal] = None
    os_cyl: Optional[Decimal] = None
    os_axis: Optional[int] = Field(None, ge=0, le=180)
    os_add: Optional[Decimal] = None
    pd: Optional[str] = None
    lens_type: Optional[str] = "SINGLE_VISION"
    usage: Optional[str] = None
    notes: Optional[str] = None


@router.get("/exams", summary="List eye exams")
def list_exams(actor: Reader, db: Db,
               patient_id: Optional[int] = Query(None),
               skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    items, total = EyeService(db).list_exams(patient_id=patient_id, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Eye exams retrieved.")


@router.post("/exams", status_code=status.HTTP_201_CREATED, summary="Create eye exam")
def create_exam(payload: ExamCreateSchema, actor: Manager, db: Db):
    data = EyeService(db).create_exam(payload.model_dump(), actor)
    return {"success": True, "message": "Eye exam created.", "data": data}


@router.get("/exams/{exam_id}", summary="Eye exam detail")
def get_exam(exam_id: int, actor: Reader, db: Db):
    return {"success": True, "data": EyeService(db).get_exam(exam_id)}


@router.patch("/exams/{exam_id}", summary="Update eye exam")
def update_exam(exam_id: int, payload: ExamUpdateSchema, actor: Manager, db: Db):
    data = EyeService(db).update_exam(exam_id, payload.model_dump(exclude_unset=True))
    return {"success": True, "message": "Eye exam updated.", "data": data}


@router.get("/prescriptions", summary="List spectacle prescriptions")
def list_prescriptions(actor: Reader, db: Db,
                       patient_id: Optional[int] = Query(None),
                       skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    items, total = EyeService(db).list_prescriptions(patient_id=patient_id, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Spectacle prescriptions retrieved.")


@router.post("/prescriptions", status_code=status.HTTP_201_CREATED,
             summary="Issue spectacle prescription")
def create_prescription(payload: PrescriptionCreateSchema, actor: Manager, db: Db):
    data = EyeService(db).create_prescription(payload.model_dump(), actor)
    return {"success": True, "message": "Prescription issued.", "data": data}


@router.get("/prescriptions/{rx_id}", summary="Spectacle prescription detail")
def get_prescription(rx_id: int, actor: Reader, db: Db):
    return {"success": True, "data": EyeService(db).get_prescription(rx_id)}


@router.get("/worklist", summary="Recent eye encounters")
def worklist(actor: Reader, db: Db, limit: int = Query(50, ge=1, le=200)):
    return {"success": True, "items": EyeService(db).worklist(limit=limit)}


@router.get("/stats", summary="Eye-clinic dashboard aggregates")
def stats(actor: Reader, db: Db):
    return {"success": True, "data": EyeService(db).stats()}


# ======================================================================
# EYE CLINIC FLOW (dedicated service-delivery pathway)
# ======================================================================


@router.get("/flow", summary="Eye Clinic service-delivery pathway")
def eye_flow(actor: Reader, db: Db):
    return {"success": True, "data": describe_eye_flow(db)}


@router.post("/seed-flow", summary="Seed the dedicated Eye Clinic pathway")
def seed_eye_flow(actor: Manager, db: Db):
    data = seed_eye_visit_flow(db)
    return {
        "success": data.get("created", False) or data.get("template_id") is not None,
        "message": data.get("message", "Eye Clinic pathway processed."),
        "data": data,
    }


# ======================================================================
# CONTACT-LENS PRESCRIPTIONS
# ======================================================================


class ContactLensCreateSchema(BaseModel):
    patient_id: int
    exam_id: Optional[int] = None
    prescriber_staff_id: Optional[int] = None
    prescribed_date: Optional[date] = None
    modality: Optional[str] = None
    od_sphere: Optional[Decimal] = None
    od_cyl: Optional[Decimal] = None
    od_axis: Optional[int] = Field(None, ge=0, le=180)
    od_add: Optional[Decimal] = None
    od_base_curve: Optional[Decimal] = None
    od_diameter: Optional[Decimal] = None
    od_brand: Optional[str] = None
    os_sphere: Optional[Decimal] = None
    os_cyl: Optional[Decimal] = None
    os_axis: Optional[int] = Field(None, ge=0, le=180)
    os_add: Optional[Decimal] = None
    os_base_curve: Optional[Decimal] = None
    os_diameter: Optional[Decimal] = None
    os_brand: Optional[str] = None
    notes: Optional[str] = None


@router.get("/contact-lens", summary="List contact-lens prescriptions")
def list_contact_lens(actor: Reader, db: Db,
                      patient_id: Optional[int] = Query(None),
                      skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    items, total = EyeService(db).list_contact_lens(patient_id=patient_id, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Contact-lens prescriptions retrieved.")


@router.post("/contact-lens", status_code=status.HTTP_201_CREATED, summary="Issue contact-lens prescription")
def create_contact_lens(payload: ContactLensCreateSchema, actor: Manager, db: Db):
    data = EyeService(db).create_contact_lens(payload.model_dump(), actor)
    return {"success": True, "message": "Contact-lens prescription issued.", "data": data}


# ======================================================================
# OPTICAL DISPENSING ORDERS
# ======================================================================


class OpticalItemSchema(BaseModel):
    item_type: str = "OTHER"
    optical_product_id: Optional[int] = None
    stock_item_id: Optional[int] = None
    item_name: Optional[str] = None
    quantity: Decimal = Field(1, gt=0)
    unit_price: Optional[Decimal] = Field(None, ge=0)


class OpticalOrderCreateSchema(BaseModel):
    patient_id: int
    exam_id: Optional[int] = None
    spectacle_prescription_id: Optional[int] = None
    visit_id: Optional[int] = None
    status: Optional[str] = "PENDING"
    discount_amount: Decimal = Field(0, ge=0)
    note: Optional[str] = None
    items: list[OpticalItemSchema] = Field(..., min_length=1)


class OrderStatusSchema(BaseModel):
    status: str


@router.get("/optical-orders", summary="List optical dispensing orders")
def list_optical_orders(actor: Reader, db: Db,
                        patient_id: Optional[int] = Query(None),
                        status_filter: Optional[str] = Query(None, alias="status"),
                        skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=300)):
    items, total = EyeService(db).list_orders(
        patient_id=patient_id, status=status_filter, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Optical orders retrieved.")


@router.post("/optical-orders", status_code=status.HTTP_201_CREATED, summary="Create optical order")
def create_optical_order(payload: OpticalOrderCreateSchema, actor: Manager, db: Db):
    data = EyeService(db).create_order(payload.model_dump(), actor)
    return {"success": True, "message": f"Optical order {data['order_no']} created.", "data": data}


@router.get("/optical-orders/{order_id}", summary="Optical order detail")
def get_optical_order(order_id: int, actor: Reader, db: Db):
    return {"success": True, "data": EyeService(db).get_order(order_id)}


@router.patch("/optical-orders/{order_id}/status", summary="Update optical order status")
def set_optical_order_status(order_id: int, payload: OrderStatusSchema, actor: Manager, db: Db):
    data = EyeService(db).update_order_status(order_id, payload.status, actor)
    return {"success": True, "message": f"Order marked {data['status']}.", "data": data}


@router.post("/optical-orders/{order_id}/bill", summary="Bill an optical order to the visit charge sheet")
def bill_optical_order(order_id: int, actor: Manager, db: Db):
    data = EyeService(db).bill_order(order_id, actor=actor)
    return {"success": True, "message": "Order billed.", "data": data}


# ======================================================================
# OPTICAL INVENTORY (frames, lenses, products)
# ======================================================================


class OpticalProductSchema(BaseModel):
    category: str = "FRAME"
    name: str
    brand: Optional[str] = None
    sku: Optional[str] = None
    spec: Optional[str] = None
    unit_cost: Optional[Decimal] = Field(None, ge=0)
    sell_price: Decimal = Field(0, ge=0)
    quantity_on_hand: Decimal = Field(0, ge=0)
    reorder_level: Optional[Decimal] = Field(None, ge=0)
    is_active: bool = True
    note: Optional[str] = None


class OpticalProductUpdateSchema(BaseModel):
    category: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    spec: Optional[str] = None
    unit_cost: Optional[Decimal] = Field(None, ge=0)
    sell_price: Optional[Decimal] = Field(None, ge=0)
    reorder_level: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None
    note: Optional[str] = None


class StockAdjustSchema(BaseModel):
    delta: Decimal
    note: Optional[str] = None


@router.get("/optical-products", summary="List optical inventory products")
def list_optical_products(actor: Reader, db: Db,
                          search: Optional[str] = Query(None),
                          category: Optional[str] = Query(None),
                          active_only: bool = Query(False),
                          low_stock: bool = Query(False),
                          skip: int = Query(0, ge=0),
                          limit: int = Query(300, ge=1, le=500)):
    items, total = EyeService(db).list_products(
        search=search, category=category, active_only=active_only,
        low_stock=low_stock, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Optical products retrieved.")


@router.post("/optical-products", status_code=status.HTTP_201_CREATED,
             summary="Add an optical product")
def create_optical_product(payload: OpticalProductSchema, actor: Manager, db: Db):
    data = EyeService(db).create_product(payload.model_dump())
    return {"success": True, "message": f"{data['name']} added.", "data": data}


@router.patch("/optical-products/{product_id}", summary="Update an optical product")
def update_optical_product(product_id: int, payload: OpticalProductUpdateSchema,
                           actor: Manager, db: Db):
    data = EyeService(db).update_product(product_id, payload.model_dump(exclude_unset=True))
    return {"success": True, "message": "Product updated.", "data": data}


@router.post("/optical-products/{product_id}/stock", summary="Adjust optical product stock")
def adjust_optical_stock(product_id: int, payload: StockAdjustSchema, actor: Manager, db: Db):
    data = EyeService(db).adjust_product_stock(product_id, payload.delta, note=payload.note)
    return {"success": True, "message": "Stock adjusted.", "data": data}


@router.delete("/optical-products/{product_id}", summary="Retire an optical product")
def delete_optical_product(product_id: int, actor: Manager, db: Db):
    EyeService(db).delete_product(product_id)
    return {"success": True, "message": "Product retired."}


# ======================================================================
# RECALLS
# ======================================================================


class EyeRecallCreateSchema(BaseModel):
    patient_id: int
    exam_id: Optional[int] = None
    recall_type: Optional[str] = None
    due_date: date
    interval_months: Optional[int] = Field(None, ge=0, le=120)
    status: Optional[str] = "DUE"
    note: Optional[str] = None


class EyeRecallUpdateSchema(BaseModel):
    recall_type: Optional[str] = None
    due_date: Optional[date] = None
    interval_months: Optional[int] = Field(None, ge=0, le=120)
    status: Optional[str] = None
    note: Optional[str] = None
    exam_id: Optional[int] = None


@router.get("/recalls", summary="List eye-clinic recalls")
def list_recalls(actor: Reader, db: Db,
                 patient_id: Optional[int] = Query(None),
                 status_filter: Optional[str] = Query(None, alias="status"),
                 due_before: Optional[date] = Query(None),
                 skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    items, total = EyeService(db).list_recalls(
        patient_id=patient_id, status=status_filter, due_before=due_before, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Eye recalls retrieved.")


@router.post("/recalls", status_code=status.HTTP_201_CREATED, summary="Create eye recall")
def create_recall(payload: EyeRecallCreateSchema, actor: Manager, db: Db):
    data = EyeService(db).create_recall(payload.model_dump(), actor)
    return {"success": True, "message": "Recall created.", "data": data}


@router.patch("/recalls/{recall_id}", summary="Update eye recall")
def update_recall(recall_id: int, payload: EyeRecallUpdateSchema, actor: Manager, db: Db):
    data = EyeService(db).update_recall(recall_id, payload.model_dump(exclude_unset=True))
    return {"success": True, "message": "Recall updated.", "data": data}
