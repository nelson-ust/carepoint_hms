# app/api/v1/endpoints/developer_data_routes.py
from __future__ import annotations

"""
Developer data-exchange API (authenticated by an app API key: ``X-API-Key``).

Every call resolves the holding hospital by its public ``tenant_code`` and is
allowed only when (a) the key carries the required scope AND (b) that hospital
has an APPROVED data grant covering the scope for this app. Reads come from the
hospital's own database.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request

from fastapi import Body

from app.dependencies.developer_auth import require_developer_app
from app.services.developer_service import DeveloperService
from app.services.medical_access_service import MedicalAccessService
from app.core.enums import MedicalAccessRequesterType

router = APIRouter(prefix="/developer/api/v1", tags=["Developer Platform (data)"])

AppPrincipal = Annotated[dict, Depends(require_developer_app)]


@router.get("/ping", summary="Verify an API key")
def ping(principal: AppPrincipal):
    return {"ok": True, "app": principal["app_name"], "organization": principal["organization_name"],
            "environment": principal["environment"], "scopes": sorted(principal["scopes"])}


@router.get("/hospitals/{tenant_code}/patients", summary="Search patients (scope: patient:search)")
def search_patients(
    tenant_code: str,
    principal: AppPrincipal,
    search: Optional[str] = Query(None, description="Name or identifier fragment."),
    limit: int = Query(25, ge=1, le=100),
):
    return {"success": True, **DeveloperService().data_search_patients(
        principal=principal, tenant_code=tenant_code, search=search, limit=limit)}


@router.get("/hospitals/{tenant_code}/patients/{global_patient_id}/medical-history",
            summary="Patient medical history (scope: patient:history:read)")
def medical_history(tenant_code: str, global_patient_id: str, principal: AppPrincipal):
    return {"success": True, "record": DeveloperService().data_medical_history(
        principal=principal, tenant_code=tenant_code, global_patient_id=global_patient_id)}


@router.get("/hospitals/{tenant_code}/patients/{global_patient_id}/baseline-diagnostics",
            summary="Patient baseline diagnostics (scope: diagnostics:read)")
def baseline_diagnostics(tenant_code: str, global_patient_id: str, principal: AppPrincipal):
    return {"success": True, "record": DeveloperService().data_baseline_diagnostics(
        principal=principal, tenant_code=tenant_code, global_patient_id=global_patient_id)}


@router.post("/hospitals/{tenant_code}/patients/{global_patient_id}/medical-history/request",
             summary="Request consent-gated access to a patient's medical history")
def request_medical_history(tenant_code: str, global_patient_id: str, principal: AppPrincipal,
                            reason: str = Body(..., embed=True, min_length=3),
                            scope: str = Body("MEDICAL_HISTORY", embed=True),
                            request: Request = None):
    if "patient:history:read" not in principal["scopes"]:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError(message="Your API key lacks the 'patient:history:read' scope.")
    # Reuse the developer grant check to resolve the holding tenant.
    tenant_id, _tenant_name = DeveloperService()._resolve_grant(
        app_id=principal["app_id"], tenant_code=tenant_code, scope="patient:history:read")
    result = MedicalAccessService().submit_request(
        requester_type=MedicalAccessRequesterType.DEVELOPER,
        holding_tenant_id=tenant_id, patient_global_id=global_patient_id,
        reason=reason, scope=scope,
        requesting_developer_app_id=principal["app_id"],
        requester_name=f"{principal['organization_name']} · {principal['app_name']}",
        requester_contact_email=principal.get("email"),
    )
    return {"success": True,
            "message": "Access requested. The patient and hospital must approve before records are released.",
            "request_no": result["request_no"], "status": result["status"]}


@router.get("/requests/{request_no}",
            summary="Poll a request; once approved the one-time record payload is served")
def poll_request(request_no: str, principal: AppPrincipal, request: Request):
    ip = request.client.host if request and request.client else None
    return {"success": True, **MedicalAccessService().developer_retrieve(
        app_id=principal["app_id"], request_no=request_no, ip=ip)}
