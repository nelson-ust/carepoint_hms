# app/api/v1/endpoints/data_protection_routes.py
from __future__ import annotations

"""Routes for the Data Protection / NDPA module."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.all_models import User
from app.dependencies.role import require_permission
from app.schemas.data_protection_schemas import (
    BreachCreateSchema,
    BreachUpdateSchema,
    ConsentCreateSchema,
    DSRCreateSchema,
    DSRUpdateSchema,
    DPActionResponseSchema,
    DPListResponseSchema,
    DPSettingsSchema,
    RopaCreateSchema,
    RopaUpdateSchema,
)
from app.services.data_protection_service import DataProtectionService
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/data-protection", tags=["Data Protection"])

READ = require_permission("DATA_PROTECTION_READ")
MANAGE = require_permission("DATA_PROTECTION_MANAGE")


def svc(db: Annotated[Session, Depends(get_db)]) -> DataProtectionService:
    return DataProtectionService(db)


def _list(items, builder, msg):
    return paginate_response(items=[builder(i) for i in items], total=len(items), skip=0, limit=len(items) or 1, message=msg)


# ---- dashboard ----
@router.get("/dashboard", response_model=DPActionResponseSchema, summary="NDPA compliance dashboard")
def dashboard(_: Annotated[User, Depends(READ)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Dashboard computed.", "data": s.dashboard()}


# ---- settings ----
@router.get("/settings", response_model=DPActionResponseSchema, summary="Get data-protection settings")
def get_settings(_: Annotated[User, Depends(READ)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Settings fetched.", "data": s.get_settings()}


@router.put("/settings", response_model=DPActionResponseSchema, summary="Update data-protection settings (DPO, policy, retention)")
def update_settings(payload: DPSettingsSchema, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Settings updated.", "data": s.update_settings(payload)}


# ---- consents ----
@router.get("/consents", response_model=DPListResponseSchema, summary="List consent records")
def list_consents(
    _: Annotated[User, Depends(READ)], s: Annotated[DataProtectionService, Depends(svc)],
    patient_id: Optional[int] = Query(None), consent_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"), search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
):
    items, total = s.list_consents(patient_id=patient_id, consent_type=consent_type, status=status_filter, search=search, skip=skip, limit=limit)
    return paginate_response(items=[s.consent_dict(c) for c in items], total=total, skip=skip, limit=limit, message="Consents fetched.")


@router.post("/consents", response_model=DPActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Record consent")
def record_consent(payload: ConsentCreateSchema, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Consent recorded.", "data": s.consent_dict(s.record_consent(payload))}


@router.post("/consents/{consent_id}/withdraw", response_model=DPActionResponseSchema, summary="Withdraw a consent")
def withdraw_consent(consent_id: int, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Consent withdrawn.", "data": s.consent_dict(s.withdraw_consent(consent_id))}


# ---- data subject requests ----
@router.get("/subject-requests", response_model=DPListResponseSchema, summary="List data-subject requests")
def list_dsr(
    _: Annotated[User, Depends(READ)], s: Annotated[DataProtectionService, Depends(svc)],
    status_filter: Optional[str] = Query(None, alias="status"), request_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
):
    items, total = s.list_dsr(status=status_filter, request_type=request_type, skip=skip, limit=limit)
    return paginate_response(items=[s.dsr_dict(r) for r in items], total=total, skip=skip, limit=limit, message="Requests fetched.")


@router.post("/subject-requests", response_model=DPActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Log a data-subject request")
def create_dsr(payload: DSRCreateSchema, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Request logged.", "data": s.dsr_dict(s.create_dsr(payload))}


@router.put("/subject-requests/{dsr_id}", response_model=DPActionResponseSchema, summary="Update a data-subject request")
def update_dsr(dsr_id: int, payload: DSRUpdateSchema, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Request updated.", "data": s.dsr_dict(s.update_dsr(dsr_id, payload))}


@router.get("/subject-requests/{dsr_id}/export", response_model=DPActionResponseSchema, summary="Export the subject's held data (access / portability)")
def export_dsr(dsr_id: int, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Data export generated.", "data": s.export_subject_data(dsr_id)}


# ---- breaches ----
@router.get("/breaches", response_model=DPListResponseSchema, summary="List data-breach register")
def list_breaches(
    _: Annotated[User, Depends(READ)], s: Annotated[DataProtectionService, Depends(svc)],
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
):
    items, total = s.list_breaches(status=status_filter, skip=skip, limit=limit)
    return paginate_response(items=[s.breach_dict(b) for b in items], total=total, skip=skip, limit=limit, message="Breaches fetched.")


@router.post("/breaches", response_model=DPActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Log a data breach")
def create_breach(payload: BreachCreateSchema, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Breach logged.", "data": s.breach_dict(s.create_breach(payload))}


@router.put("/breaches/{breach_id}", response_model=DPActionResponseSchema, summary="Update a data breach")
def update_breach(breach_id: int, payload: BreachUpdateSchema, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Breach updated.", "data": s.breach_dict(s.update_breach(breach_id, payload))}


@router.post("/breaches/{breach_id}/notify-ndpc", response_model=DPActionResponseSchema, summary="Record NDPC notification for a breach")
def notify_ndpc(breach_id: int, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "NDPC notification recorded.", "data": s.breach_dict(s.notify_ndpc(breach_id))}


# ---- RoPA ----
@router.get("/processing-activities", response_model=DPListResponseSchema, summary="List records of processing activities")
def list_ropa(_: Annotated[User, Depends(READ)], s: Annotated[DataProtectionService, Depends(svc)], skip: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)):
    items, total = s.list_ropa(skip=skip, limit=limit)
    return paginate_response(items=[s.ropa_dict(a) for a in items], total=total, skip=skip, limit=limit, message="Activities fetched.")


@router.post("/processing-activities", response_model=DPActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Add a processing activity")
def create_ropa(payload: RopaCreateSchema, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Processing activity added.", "data": s.ropa_dict(s.create_ropa(payload))}


@router.put("/processing-activities/{ropa_id}", response_model=DPActionResponseSchema, summary="Update a processing activity")
def update_ropa(ropa_id: int, payload: RopaUpdateSchema, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    return {"success": True, "message": "Processing activity updated.", "data": s.ropa_dict(s.update_ropa(ropa_id, payload))}


@router.delete("/processing-activities/{ropa_id}", summary="Remove a processing activity")
def delete_ropa(ropa_id: int, _: Annotated[User, Depends(MANAGE)], s: Annotated[DataProtectionService, Depends(svc)]):
    a = s.delete_ropa(ropa_id)
    return {"success": True, "message": "Processing activity removed.", "id": a.id}
