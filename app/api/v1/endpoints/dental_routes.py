# app/api/v1/endpoints/dental_routes.py
from __future__ import annotations

"""
FastAPI routes for the Dental clinic module.

Sub-routes
----------
- /dental/charts             -- dental examination / odontogram
- /dental/charts/{id}/teeth  -- bulk upsert tooth findings
- /dental/procedures         -- treatment plan (planned / completed procedures)
- /dental/worklist           -- recent dental encounters
- /dental/stats              -- dashboard aggregates

Permission codes: DENTAL_READ (view) | DENTAL_MANAGE (write).
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
from app.services.dental_service import DentalService
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/dental", tags=["Dental Clinic"])

Reader = Annotated[User, Depends(require_permission("DENTAL_READ", "DENTAL_MANAGE"))]
Manager = Annotated[User, Depends(require_permission("DENTAL_MANAGE"))]
Db = Annotated[Session, Depends(get_db)]


class ChartCreateSchema(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    consultation_id: Optional[int] = None
    clinician_staff_id: Optional[int] = None
    numbering_system: Optional[str] = "FDI"
    dentition: Optional[str] = "PERMANENT"
    chief_complaint: Optional[str] = None
    oral_hygiene: Optional[str] = None
    occlusion_note: Optional[str] = None
    soft_tissue_note: Optional[str] = None
    periodontal_summary: Optional[str] = None
    xray_findings: Optional[str] = None
    note: Optional[str] = None


class ChartUpdateSchema(BaseModel):
    clinician_staff_id: Optional[int] = None
    numbering_system: Optional[str] = None
    dentition: Optional[str] = None
    chief_complaint: Optional[str] = None
    oral_hygiene: Optional[str] = None
    occlusion_note: Optional[str] = None
    soft_tissue_note: Optional[str] = None
    periodontal_summary: Optional[str] = None
    xray_findings: Optional[str] = None
    note: Optional[str] = None
    status: Optional[str] = None


class ToothSchema(BaseModel):
    tooth_number: int
    condition: Optional[str] = "HEALTHY"
    surfaces: Optional[str] = None
    mobility: Optional[int] = Field(None, ge=0, le=3)
    note: Optional[str] = None


class TeethBulkSchema(BaseModel):
    teeth: list[ToothSchema] = Field(..., min_length=1)


class ProcedureCreateSchema(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    chart_id: Optional[int] = None
    tooth_number: Optional[int] = None
    surfaces: Optional[str] = None
    procedure_code: Optional[str] = None
    procedure_name: str
    status: Optional[str] = "PLANNED"
    cost: Optional[Decimal] = Field(None, ge=0)
    planned_date: Optional[date] = None
    performed_date: Optional[date] = None
    performed_by_staff_id: Optional[int] = None
    note: Optional[str] = None


class ProcedureUpdateSchema(BaseModel):
    tooth_number: Optional[int] = None
    surfaces: Optional[str] = None
    procedure_code: Optional[str] = None
    procedure_name: Optional[str] = None
    status: Optional[str] = None
    cost: Optional[Decimal] = Field(None, ge=0)
    planned_date: Optional[date] = None
    performed_date: Optional[date] = None
    note: Optional[str] = None


@router.get("/charts", summary="List dental charts")
def list_charts(actor: Reader, db: Db,
                patient_id: Optional[int] = Query(None),
                skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    items, total = DentalService(db).list_charts(patient_id=patient_id, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Dental charts retrieved.")


@router.post("/charts", status_code=status.HTTP_201_CREATED, summary="Create dental chart")
def create_chart(payload: ChartCreateSchema, actor: Manager, db: Db):
    data = DentalService(db).create_chart(payload.model_dump(), actor)
    return {"success": True, "message": "Dental chart created.", "data": data}


@router.get("/charts/{chart_id}", summary="Dental chart detail")
def get_chart(chart_id: int, actor: Reader, db: Db):
    return {"success": True, "data": DentalService(db).get_chart(chart_id)}


@router.patch("/charts/{chart_id}", summary="Update dental chart")
def update_chart(chart_id: int, payload: ChartUpdateSchema, actor: Manager, db: Db):
    data = DentalService(db).update_chart(chart_id, payload.model_dump(exclude_unset=True))
    return {"success": True, "message": "Dental chart updated.", "data": data}


@router.put("/charts/{chart_id}/teeth", summary="Upsert tooth findings")
def set_teeth(chart_id: int, payload: TeethBulkSchema, actor: Manager, db: Db):
    teeth = [t.model_dump() for t in payload.teeth]
    data = DentalService(db).set_teeth(chart_id, teeth)
    return {"success": True, "message": "Odontogram updated.", "data": data}


@router.get("/procedures", summary="List dental procedures")
def list_procedures(actor: Reader, db: Db,
                    patient_id: Optional[int] = Query(None),
                    status_filter: Optional[str] = Query(None, alias="status"),
                    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    items, total = DentalService(db).list_procedures(
        patient_id=patient_id, status=status_filter, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Dental procedures retrieved.")


@router.post("/procedures", status_code=status.HTTP_201_CREATED, summary="Add dental procedure")
def create_procedure(payload: ProcedureCreateSchema, actor: Manager, db: Db):
    data = DentalService(db).create_procedure(payload.model_dump(), actor)
    return {"success": True, "message": "Procedure added.", "data": data}


@router.patch("/procedures/{proc_id}", summary="Update dental procedure")
def update_procedure(proc_id: int, payload: ProcedureUpdateSchema, actor: Manager, db: Db):
    data = DentalService(db).update_procedure(proc_id, payload.model_dump(exclude_unset=True), actor)
    return {"success": True, "message": "Procedure updated.", "data": data}


@router.get("/worklist", summary="Recent dental encounters")
def worklist(actor: Reader, db: Db, limit: int = Query(50, ge=1, le=200)):
    return {"success": True, "items": DentalService(db).worklist(limit=limit)}


@router.get("/stats", summary="Dental dashboard aggregates")
def stats(actor: Reader, db: Db):
    return {"success": True, "data": DentalService(db).stats()}
