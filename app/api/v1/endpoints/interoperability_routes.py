# app/api/v1/endpoints/interoperability_routes.py
from __future__ import annotations

"""
Cross-tenant interoperability routes: request a patient's records from another
hospital, approve/deny/retrieve them (consent + approval gated), plus partner
directory and cross-tenant patient lookup.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.core.exceptions import BadRequestError
from app.core.multitenancy import get_current_tenant_id
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.interoperability_schemas import (
    DataRequestApproveSchema,
    DataRequestCreateSchema,
    DataRequestDenySchema,
)
from app.services.interoperability_service import InteroperabilityService

router = APIRouter(
    prefix="/interoperability",
    tags=["Interoperability"],
    dependencies=[Depends(require_plan_feature("clinical"))],
)


def get_service(db: Annotated[Session, Depends(get_db)]) -> InteroperabilityService:
    return InteroperabilityService(db)


def _require_tenant() -> int:
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise BadRequestError(message="You must belong to a hospital to use interoperability.")
    return tenant_id


# ---------- Partner directory + patient lookup ----------

@router.get("/partners", summary="List partner hospitals")
def list_partners(
    actor: CurrentActiveUser,
    service: Annotated[InteroperabilityService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
):
    tenant_id = _require_tenant()
    return {"success": True, "items": service.list_partner_tenants(exclude_tenant_id=tenant_id)}


@router.get("/patient-lookup", summary="Confirm a patient exists at a partner hospital")
def patient_lookup(
    actor: CurrentActiveUser,
    service: Annotated[InteroperabilityService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
    holding_tenant_id: int = Query(...),
    patient_global_id: str = Query(..., min_length=1),
):
    _require_tenant()
    return service.lookup_patient(holding_tenant_id=holding_tenant_id, patient_global_id=patient_global_id)


# ---------- Data-exchange requests ----------

@router.post("/data-requests", status_code=status.HTTP_201_CREATED, summary="Request a patient's records from another hospital")
def create_data_request(
    payload: DataRequestCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[InteroperabilityService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_CREATE"))],
):
    tenant_id = _require_tenant()
    facility_id = getattr(getattr(actor, "staff_profile", None), "facility_id", None)
    req = service.create_request(
        requesting_tenant_id=tenant_id,
        requesting_facility_id=facility_id,
        holding_tenant_id=payload.holding_tenant_id,
        patient_global_id=payload.patient_global_id,
        patient_display_name=payload.patient_display_name,
        purpose=payload.purpose,
        scope=payload.scope,
        requested_by_user_id=actor.id,
    )
    return {"success": True, "message": "Data request submitted.", "request": req}


@router.get("/data-requests/outgoing", summary="Data requests we have sent to other hospitals")
def list_outgoing(
    actor: CurrentActiveUser,
    service: Annotated[InteroperabilityService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
    status_filter: Optional[str] = Query(None, alias="status"),
):
    tenant_id = _require_tenant()
    return {"success": True, "items": service.list_outgoing(requesting_tenant_id=tenant_id, status=status_filter)}


@router.get("/data-requests/incoming", summary="Data requests other hospitals have sent to us")
def list_incoming(
    actor: CurrentActiveUser,
    service: Annotated[InteroperabilityService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
    status_filter: Optional[str] = Query(None, alias="status"),
):
    tenant_id = _require_tenant()
    return {"success": True, "items": service.list_incoming(holding_tenant_id=tenant_id, status=status_filter)}


@router.post("/data-requests/{request_id}/approve", summary="Approve a data request (confirms consent + shares the record)")
def approve_data_request(
    request_id: int,
    payload: DataRequestApproveSchema,
    actor: CurrentActiveUser,
    service: Annotated[InteroperabilityService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_CREATE"))],
):
    tenant_id = _require_tenant()
    req = service.approve_request(
        request_id=request_id,
        holding_tenant_id=tenant_id,
        approver_user_id=actor.id,
        consent_confirmed=payload.consent_confirmed,
        consent_reference=payload.consent_reference,
        access_expiry_days=payload.access_expiry_days,
    )
    return {"success": True, "message": "Request approved; record shared.", "request": req}


@router.post("/data-requests/{request_id}/deny", summary="Deny a data request")
def deny_data_request(
    request_id: int,
    payload: DataRequestDenySchema,
    actor: CurrentActiveUser,
    service: Annotated[InteroperabilityService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_CREATE"))],
):
    tenant_id = _require_tenant()
    req = service.deny_request(request_id=request_id, holding_tenant_id=tenant_id, reason=payload.reason, actor_user_id=actor.id)
    return {"success": True, "message": "Request denied.", "request": req}


@router.post("/data-requests/{request_id}/cancel", summary="Cancel a data request we sent")
def cancel_data_request(
    request_id: int,
    actor: CurrentActiveUser,
    service: Annotated[InteroperabilityService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_CREATE"))],
):
    tenant_id = _require_tenant()
    req = service.cancel_request(request_id=request_id, requesting_tenant_id=tenant_id, actor_user_id=actor.id)
    return {"success": True, "message": "Request cancelled.", "request": req}


@router.get("/data-requests/{request_id}/record", summary="Retrieve the shared patient record")
def retrieve_record(
    request_id: int,
    actor: CurrentActiveUser,
    service: Annotated[InteroperabilityService, Depends(get_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
):
    tenant_id = _require_tenant()
    return service.retrieve_payload(request_id=request_id, requesting_tenant_id=tenant_id, actor_user_id=actor.id)
