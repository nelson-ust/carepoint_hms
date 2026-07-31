# app/api/v1/endpoints/integration_public_routes.py
from __future__ import annotations

"""
Inbound integration API for third-party Hospital Management applications.

Authenticated by API key (``X-API-Key`` header). The key identifies the owning
tenant, so these endpoints operate on that tenant's database. READ scope covers
lookups/exports; WRITE scope covers upserts and data pushes.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.dependencies.api_key_auth import (
    ApiPartner,
    integration_read_ctx,
    integration_write_ctx,
)
from app.schemas.integration_schemas import DataPushSchema, PatientUpsertSchema
from app.services.integration_service import IntegrationService

router = APIRouter(prefix="/integration/v1", tags=["Integration API (partner)"])


@router.get("/ping", summary="Verify an API key and see the connected hospital")
def ping(ctx: Annotated[tuple[ApiPartner, Session], Depends(integration_read_ctx)]):
    partner, _db = ctx
    return {"ok": True, "partner": partner.name, "tenant_id": partner.tenant_id,
            "scopes": sorted(partner.scopes)}


@router.get("/patients", summary="Search patients (READ)")
def search_patients(
    ctx: Annotated[tuple[ApiPartner, Session], Depends(integration_read_ctx)],
    search: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
):
    _partner, db = ctx
    return {"success": True, "items": IntegrationService(db).search_patients(query=search, limit=limit)}


@router.get("/patients/{global_patient_id}/record", summary="Full patient record export (READ)")
def patient_record(
    global_patient_id: str,
    ctx: Annotated[tuple[ApiPartner, Session], Depends(integration_read_ctx)],
):
    _partner, db = ctx
    record = IntegrationService(db).patient_record(global_patient_id=global_patient_id)
    if record is None:
        raise NotFoundError(message="Patient not found.")
    return record


@router.post("/patients", summary="Create or update a patient (WRITE)")
def upsert_patient(
    payload: PatientUpsertSchema,
    ctx: Annotated[tuple[ApiPartner, Session], Depends(integration_write_ctx)],
):
    _partner, db = ctx
    result = IntegrationService(db).upsert_patient(data=payload)
    return {"success": True, "patient": result}


@router.post("/data-push", summary="Push an arbitrary record into the hospital (WRITE)")
def data_push(
    payload: DataPushSchema,
    ctx: Annotated[tuple[ApiPartner, Session], Depends(integration_write_ctx)],
):
    partner, db = ctx
    result = IntegrationService(db).ingest_record(
        partner_id=partner.id, partner_name=partner.name, data=payload)
    return {"success": True, "record": result}
