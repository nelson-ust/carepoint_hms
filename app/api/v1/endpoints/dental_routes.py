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
    catalog_id: Optional[int] = None
    tooth_number: Optional[int] = None
    surfaces: Optional[str] = None
    procedure_code: Optional[str] = None
    # Optional when a catalogue entry is selected (name is copied from it).
    procedure_name: Optional[str] = None
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


# ======================================================================
# PROCEDURE CATALOGUE (price list)
# ======================================================================


class CatalogCreateSchema(BaseModel):
    code: Optional[str] = None
    name: str
    category: Optional[str] = None
    default_cost: Decimal = Field(0, ge=0)
    tooth_specific: bool = False
    billable_service_id: Optional[int] = None
    is_active: bool = True
    description: Optional[str] = None


class CatalogUpdateSchema(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    default_cost: Optional[Decimal] = Field(None, ge=0)
    tooth_specific: Optional[bool] = None
    billable_service_id: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None


@router.get("/catalog", summary="List dental procedure catalogue (price list)")
def list_catalog(actor: Reader, db: Db,
                 search: Optional[str] = Query(None),
                 category: Optional[str] = Query(None),
                 active_only: bool = Query(False),
                 skip: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500)):
    items, total = DentalService(db).list_catalog(
        search=search, category=category, active_only=active_only, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Dental catalogue retrieved.")


@router.post("/catalog", status_code=status.HTTP_201_CREATED, summary="Add catalogue procedure")
def create_catalog(payload: CatalogCreateSchema, actor: Manager, db: Db):
    data = DentalService(db).create_catalog(payload.model_dump())
    return {"success": True, "message": "Catalogue procedure added.", "data": data}


@router.patch("/catalog/{cat_id}", summary="Update catalogue procedure")
def update_catalog(cat_id: int, payload: CatalogUpdateSchema, actor: Manager, db: Db):
    data = DentalService(db).update_catalog(cat_id, payload.model_dump(exclude_unset=True))
    return {"success": True, "message": "Catalogue procedure updated.", "data": data}


@router.delete("/catalog/{cat_id}", summary="Remove catalogue procedure")
def delete_catalog(cat_id: int, actor: Manager, db: Db):
    DentalService(db).delete_catalog(cat_id)
    return {"success": True, "message": "Catalogue procedure removed."}


# ======================================================================
# RECALLS (preventive-care follow-ups)
# ======================================================================


class RecallCreateSchema(BaseModel):
    patient_id: int
    chart_id: Optional[int] = None
    recall_type: Optional[str] = None
    due_date: date
    interval_months: Optional[int] = Field(None, ge=0, le=120)
    status: Optional[str] = "DUE"
    note: Optional[str] = None


class RecallUpdateSchema(BaseModel):
    recall_type: Optional[str] = None
    due_date: Optional[date] = None
    interval_months: Optional[int] = Field(None, ge=0, le=120)
    status: Optional[str] = None
    note: Optional[str] = None
    chart_id: Optional[int] = None


@router.get("/recalls", summary="List dental recalls")
def list_recalls(actor: Reader, db: Db,
                 patient_id: Optional[int] = Query(None),
                 status_filter: Optional[str] = Query(None, alias="status"),
                 due_before: Optional[date] = Query(None),
                 skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    items, total = DentalService(db).list_recalls(
        patient_id=patient_id, status=status_filter, due_before=due_before,
        skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Dental recalls retrieved.")


@router.post("/recalls", status_code=status.HTTP_201_CREATED, summary="Create dental recall")
def create_recall(payload: RecallCreateSchema, actor: Manager, db: Db):
    data = DentalService(db).create_recall(payload.model_dump(), actor)
    return {"success": True, "message": "Recall created.", "data": data}


@router.patch("/recalls/{recall_id}", summary="Update dental recall")
def update_recall(recall_id: int, payload: RecallUpdateSchema, actor: Manager, db: Db):
    data = DentalService(db).update_recall(recall_id, payload.model_dump(exclude_unset=True))
    return {"success": True, "message": "Recall updated.", "data": data}


# ======================================================================
# TREATMENT-PLAN BILLING
# ======================================================================


class BillChartSchema(BaseModel):
    procedure_ids: Optional[list[int]] = None


@router.post("/charts/{chart_id}/bill", summary="Bill a chart's procedures to the visit charge sheet")
def bill_chart(chart_id: int, payload: BillChartSchema, actor: Manager, db: Db):
    data = DentalService(db).bill_chart(
        chart_id, procedure_ids=payload.procedure_ids, actor=actor)
    return {"success": True,
            "message": f"{data['billed_count']} procedure(s) billed.", "data": data}
