# app/api/v1/endpoints/ortho_routes.py
from __future__ import annotations

"""
FastAPI routes for the Orthopaedics clinic module.

Sub-routes
----------
- /orthopaedics/assessments              -- musculoskeletal assessments
- /orthopaedics/assessments/{id}/fractures        -- fracture records
- /orthopaedics/assessments/{id}/immobilisations  -- cast / splint episodes
- /orthopaedics/procedures               -- treatment plan procedures
- /orthopaedics/worklist                 -- recent encounters
- /orthopaedics/stats                    -- dashboard aggregates

Permission codes: ORTHO_READ (view) | ORTHO_MANAGE (write).
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
from app.services.ortho_service import OrthoService
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/orthopaedics", tags=["Orthopaedics Clinic"])

Reader = Annotated[User, Depends(require_permission("ORTHO_READ", "ORTHO_MANAGE"))]
Manager = Annotated[User, Depends(require_permission("ORTHO_MANAGE"))]
Db = Annotated[Session, Depends(get_db)]


class AssessmentCreateSchema(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    consultation_id: Optional[int] = None
    clinician_staff_id: Optional[int] = None
    region: Optional[str] = None
    laterality: Optional[str] = "NOT_APPLICABLE"
    chief_complaint: Optional[str] = None
    mechanism_of_injury: Optional[str] = None
    injury_date: Optional[date] = None
    pain_score: Optional[int] = Field(None, ge=0, le=10)
    rom_note: Optional[str] = None
    neurovascular_note: Optional[str] = None
    special_tests: Optional[str] = None
    provisional_diagnosis: Optional[str] = None
    imaging_modality: Optional[str] = None
    imaging_findings: Optional[str] = None
    plan_note: Optional[str] = None
    note: Optional[str] = None


class AssessmentUpdateSchema(BaseModel):
    clinician_staff_id: Optional[int] = None
    region: Optional[str] = None
    laterality: Optional[str] = None
    chief_complaint: Optional[str] = None
    mechanism_of_injury: Optional[str] = None
    injury_date: Optional[date] = None
    pain_score: Optional[int] = Field(None, ge=0, le=10)
    rom_note: Optional[str] = None
    neurovascular_note: Optional[str] = None
    special_tests: Optional[str] = None
    provisional_diagnosis: Optional[str] = None
    imaging_modality: Optional[str] = None
    imaging_findings: Optional[str] = None
    plan_note: Optional[str] = None
    note: Optional[str] = None
    status: Optional[str] = None


class FractureCreateSchema(BaseModel):
    bone: str
    side: Optional[str] = "NOT_APPLICABLE"
    pattern: Optional[str] = None
    classification: Optional[str] = None
    is_open: Optional[bool] = False
    is_displaced: Optional[bool] = False
    management: Optional[str] = None
    note: Optional[str] = None


class ImmobilisationCreateSchema(BaseModel):
    device_type: str
    body_part: Optional[str] = None
    side: Optional[str] = "NOT_APPLICABLE"
    applied_date: Optional[date] = None
    expected_removal_date: Optional[date] = None
    removed_date: Optional[date] = None
    note: Optional[str] = None


class RemoveImmobilisationSchema(BaseModel):
    removed_date: Optional[date] = None


class ProcedureCreateSchema(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    assessment_id: Optional[int] = None
    procedure_code: Optional[str] = None
    procedure_name: str
    laterality: Optional[str] = "NOT_APPLICABLE"
    status: Optional[str] = "PLANNED"
    cost: Optional[Decimal] = Field(None, ge=0)
    planned_date: Optional[date] = None
    performed_date: Optional[date] = None
    performed_by_staff_id: Optional[int] = None
    note: Optional[str] = None


class ProcedureUpdateSchema(BaseModel):
    procedure_code: Optional[str] = None
    procedure_name: Optional[str] = None
    laterality: Optional[str] = None
    status: Optional[str] = None
    cost: Optional[Decimal] = Field(None, ge=0)
    planned_date: Optional[date] = None
    performed_date: Optional[date] = None
    note: Optional[str] = None


@router.get("/assessments", summary="List orthopaedic assessments")
def list_assessments(actor: Reader, db: Db,
                     patient_id: Optional[int] = Query(None),
                     skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    items, total = OrthoService(db).list_assessments(patient_id=patient_id, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Assessments retrieved.")


@router.post("/assessments", status_code=status.HTTP_201_CREATED, summary="Create assessment")
def create_assessment(payload: AssessmentCreateSchema, actor: Manager, db: Db):
    data = OrthoService(db).create_assessment(payload.model_dump(), actor)
    return {"success": True, "message": "Assessment created.", "data": data}


@router.get("/assessments/{aid}", summary="Assessment detail")
def get_assessment(aid: int, actor: Reader, db: Db):
    return {"success": True, "data": OrthoService(db).get_assessment(aid)}


@router.patch("/assessments/{aid}", summary="Update assessment")
def update_assessment(aid: int, payload: AssessmentUpdateSchema, actor: Manager, db: Db):
    data = OrthoService(db).update_assessment(aid, payload.model_dump(exclude_unset=True))
    return {"success": True, "message": "Assessment updated.", "data": data}


@router.post("/assessments/{aid}/fractures", summary="Add fracture record")
def add_fracture(aid: int, payload: FractureCreateSchema, actor: Manager, db: Db):
    data = OrthoService(db).add_fracture(aid, payload.model_dump())
    return {"success": True, "message": "Fracture recorded.", "data": data}


@router.delete("/fractures/{frac_id}", summary="Remove fracture record")
def delete_fracture(frac_id: int, actor: Manager, db: Db):
    data = OrthoService(db).delete_fracture(frac_id)
    return {"success": True, "message": "Fracture removed.", "data": data}


@router.post("/assessments/{aid}/immobilisations", summary="Add immobilisation")
def add_immobilisation(aid: int, payload: ImmobilisationCreateSchema, actor: Manager, db: Db):
    data = OrthoService(db).add_immobilisation(aid, payload.model_dump())
    return {"success": True, "message": "Immobilisation recorded.", "data": data}


@router.post("/immobilisations/{immob_id}/remove", summary="Mark immobilisation removed")
def remove_immobilisation(immob_id: int, payload: RemoveImmobilisationSchema, actor: Manager, db: Db):
    rd = payload.removed_date.isoformat() if payload.removed_date else None
    data = OrthoService(db).remove_immobilisation(immob_id, rd)
    return {"success": True, "message": "Immobilisation removed.", "data": data}


@router.get("/procedures", summary="List orthopaedic procedures")
def list_procedures(actor: Reader, db: Db,
                    patient_id: Optional[int] = Query(None),
                    status_filter: Optional[str] = Query(None, alias="status"),
                    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    items, total = OrthoService(db).list_procedures(
        patient_id=patient_id, status=status_filter, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Procedures retrieved.")


@router.post("/procedures", status_code=status.HTTP_201_CREATED, summary="Add procedure")
def create_procedure(payload: ProcedureCreateSchema, actor: Manager, db: Db):
    data = OrthoService(db).create_procedure(payload.model_dump(), actor)
    return {"success": True, "message": "Procedure added.", "data": data}


@router.patch("/procedures/{proc_id}", summary="Update procedure")
def update_procedure(proc_id: int, payload: ProcedureUpdateSchema, actor: Manager, db: Db):
    data = OrthoService(db).update_procedure(proc_id, payload.model_dump(exclude_unset=True), actor)
    return {"success": True, "message": "Procedure updated.", "data": data}


@router.get("/worklist", summary="Recent orthopaedic encounters")
def worklist(actor: Reader, db: Db, limit: int = Query(50, ge=1, le=200)):
    return {"success": True, "items": OrthoService(db).worklist(limit=limit)}


@router.get("/stats", summary="Orthopaedics dashboard aggregates")
def stats(actor: Reader, db: Db):
    return {"success": True, "data": OrthoService(db).stats()}
