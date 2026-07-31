# app/api/v1/endpoints/medical_access_public_routes.py
from __future__ import annotations

"""
Medical-record access — public, token-authenticated surface.

* Patients review and Approve / Decline a request via a secure token emailed to
  them (no account required).
* The requester consumes the approved one-time link (read-only, single use,
  auto-expiring). Consumption is a POST so email/link scanners can't burn it.
"""

from typing import Optional

from fastapi import APIRouter, Request

from app.schemas.medical_access_schemas import DecisionSchema
from app.services.medical_access_service import MedicalAccessService

router = APIRouter(prefix="/medical-access/public", tags=["Medical Record Sharing (public)"])


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


@router.get("/patient/{token}", summary="View a request as the patient (token)")
def view_as_patient(token: str):
    return {"success": True, "request": MedicalAccessService().get_by_patient_token(token)}


@router.post("/patient/{token}/decision", summary="Patient approves or declines (token)")
def patient_decision(token: str, payload: DecisionSchema, request: Request):
    result = MedicalAccessService().patient_decision_by_token(
        token=token, approve=payload.approve, reason=payload.reason, ip=_ip(request))
    msg = "Thank you — your response has been recorded."
    return {"success": True, "message": msg, "request": result}


@router.post("/link/{token}", summary="Consume the one-time access link (read-only records)")
def consume_link(token: str, request: Request):
    result = MedicalAccessService().consume_link(token=token, ip=_ip(request))
    return {"success": True, **result}
