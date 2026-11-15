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
