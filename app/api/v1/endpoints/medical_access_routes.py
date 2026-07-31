# app/api/v1/endpoints/medical_access_routes.py
from __future__ import annotations

"""
Medical-record access requests — hospital (staff, JWT) surface.

* Requesters submit / track / cancel outgoing requests (MEDICAL_ACCESS_REQUEST).
* Holding hospitals review incoming requests and approve / decline
  (MEDICAL_ACCESS_REVIEW). Approval (together with the patient's) mints the
  one-time link.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.core.dependencies import require_permission
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.enums import MedicalAccessRequesterType
from app.core.multitenancy import get_current_tenant_id
from app.core.database import get_master_db_context
from app.models.all_models import User
from app.schemas.medical_access_schemas import AccessRequestCreateSchema, DecisionSchema
from app.services.medical_access_service import MedicalAccessService

router = APIRouter(prefix="/medical-access", tags=["Medical Record Sharing"])

Requester = Annotated[User, Depends(require_permission("MEDICAL_ACCESS_REQUEST"))]
Reviewer = Annotated[User, Depends(require_permission("MEDICAL_ACCESS_REVIEW"))]
AnyParty = Annotated[User, Depends(require_permission("MEDICAL_ACCESS_REQUEST", "MEDICAL_ACCESS_REVIEW"))]


def _tenant_id() -> int:
    tid = get_current_tenant_id()
    if not tid:
        raise BadRequestError(message="A tenant context is required.")
    return tid


def _tenant(tid: int):
    from app.models.all_models import Tenant
    with get_master_db_context() as mdb:
        t = mdb.query(Tenant).filter(Tenant.id == tid).first()
        if t is None:
            return None, None, None
        return t.id, t.name, getattr(t, "billing_email", None)


def _tenant_by_code(code: str):
    from app.models.all_models import Tenant
    with get_master_db_context() as mdb:
        t = mdb.query(Tenant).filter(Tenant.code == (code or "").strip(),
                                     Tenant.is_deleted.is_(False)).first()
        return (t.id, t.name) if t else (None, None)


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.post("/requests", status_code=status.HTTP_201_CREATED, summary="Submit an access request")
def submit(payload: AccessRequestCreateSchema, actor: Requester, request: Request):
    tid = _tenant_id()
    _, my_name, my_email = _tenant(tid)
    holding_id, _holding_name = _tenant_by_code(payload.holding_tenant_code)
    if holding_id is None:
        raise NotFoundError(message="No hospital with that code.")
    result = MedicalAccessService().submit_request(
        requester_type=MedicalAccessRequesterType.HOSPITAL,
        holding_tenant_id=holding_id,
        patient_global_id=payload.patient_global_id,
        reason=payload.reason, scope=payload.scope,
        requesting_tenant_id=tid, requester_name=my_name or "Requesting hospital",
        requester_contact_email=my_email or getattr(actor, "email", None),
        requested_by_user_id=getattr(actor, "id", None),
        requires_patient_approval=payload.requires_patient_approval,
        requires_hospital_approval=payload.requires_hospital_approval,
        link_expiry_hours=payload.link_expiry_hours,
    )
    return {"success": True, "message": "Request submitted. The patient and their hospital have been notified.",
            "request": result}


@router.get("/requests", summary="List incoming or outgoing requests")
def list_requests(actor: AnyParty,
                  direction: str = Query("incoming", pattern="^(incoming|outgoing)$"),
                  status: Optional[str] = Query(None)):
    items = MedicalAccessService().list_for_hospital(tenant_id=_tenant_id(), direction=direction, status=status)
    return {"success": True, "items": items}


@router.get("/requests/{request_id}", summary="Request detail")
def detail(request_id: int, actor: AnyParty):
    return {"success": True, "request": MedicalAccessService().get_detail(request_id=request_id, tenant_id=_tenant_id())}


@router.get("/requests/{request_id}/audit", summary="Full audit trail for a request")
def audit(request_id: int, actor: AnyParty):
    return {"success": True, "items": MedicalAccessService().get_audit(request_id=request_id, tenant_id=_tenant_id())}


@router.post("/requests/{request_id}/hospital-decision", summary="Approve or decline (holding hospital)")
def hospital_decision(request_id: int, payload: DecisionSchema, actor: Reviewer, request: Request):
    display = getattr(actor, "username", None) or getattr(actor, "email", None)
    result = MedicalAccessService().hospital_decision(
        holding_tenant_id=_tenant_id(), request_id=request_id, approve=payload.approve,
        user_id=getattr(actor, "id", None), actor_display=display, reason=payload.reason, ip=_ip(request))
    return {"success": True, "message": "Decision recorded.", "request": result}


@router.post("/requests/{request_id}/retrieve", summary="Open approved records once (requesting hospital)")
def retrieve(request_id: int, actor: Requester, request: Request):
    display = getattr(actor, "username", None) or getattr(actor, "email", None)
    result = MedicalAccessService().retrieve_for_hospital(
        requesting_tenant_id=_tenant_id(), request_id=request_id,
        actor_id=getattr(actor, "id", None), actor_display=display, ip=_ip(request))
    return {"success": True, **result}


@router.post("/requests/{request_id}/cancel", summary="Cancel an outgoing request")
def cancel(request_id: int, actor: Requester):
    result = MedicalAccessService().cancel(request_id=request_id, requesting_tenant_id=_tenant_id(),
                                           user_id=getattr(actor, "id", None))
    return {"success": True, "message": "Request cancelled.", "request": result}
