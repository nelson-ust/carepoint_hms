# app/api/v1/endpoints/lab_result_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.lab_result_schema import (
    LabResultActionResponseSchema,
    LabResultEnterSchema,
    LabResultReadSchema,
    LabResultReleaseSchema,
    LabResultUpdateSchema,
    LabResultVerifySchema,
)
from app.services.lab_result_service import LabResultService

router = APIRouter(
    prefix="/lab/results", 
    tags=["Laboratory - Results"],
    dependencies=[Depends(require_plan_feature("laboratory"))]
)


def get_lab_result_service(db: Annotated[Session, Depends(get_db)]) -> LabResultService:
    return LabResultService(db)


@router.post(
    "/",
    response_model=LabResultActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Enter a lab result",
)
def enter_result(
    payload: LabResultEnterSchema,
    actor: CurrentActiveUser,
    service: Annotated[LabResultService, Depends(get_lab_result_service)],
    _: Annotated[User, Depends(require_permission("LAB_RESULT_ENTER"))],
):
    result = service.enter_result(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Lab result recorded.", "result": result}


@router.put(
    "/{result_id}",
    response_model=LabResultActionResponseSchema,
    summary="Update a (still editable) lab result",
)
def update_result(
    result_id: int,
    payload: LabResultUpdateSchema,
    actor: CurrentActiveUser,
    service: Annotated[LabResultService, Depends(get_lab_result_service)],
    _: Annotated[User, Depends(require_permission("LAB_RESULT_ENTER"))],
):
    result = service.update_result(result_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Lab result updated.", "result": result}


@router.post(
    "/{result_id}/verify",
    response_model=LabResultActionResponseSchema,
    summary="Verify a lab result (four-eyes rule)",
)
def verify_result(
    result_id: int,
    payload: LabResultVerifySchema,
    actor: CurrentActiveUser,
    service: Annotated[LabResultService, Depends(get_lab_result_service)],
    _: Annotated[User, Depends(require_permission("LAB_RESULT_VERIFY"))],
):
    result = service.verify_result(result_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Lab result verified.", "result": result}


@router.post(
    "/{result_id}/release",
    response_model=LabResultActionResponseSchema,
    summary="Release a verified lab result",
)
def release_result(
    result_id: int,
    payload: LabResultReleaseSchema,
    actor: CurrentActiveUser,
    service: Annotated[LabResultService, Depends(get_lab_result_service)],
    _: Annotated[User, Depends(require_permission("LAB_RESULT_RELEASE"))],
):
    result = service.release_result(result_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Lab result released.", "result": result}


@router.post(
    "/{result_id}/cancel",
    response_model=LabResultActionResponseSchema,
    summary="Cancel a result that is still editable",
)
def cancel_result(
    result_id: int,
    actor: CurrentActiveUser,
    service: Annotated[LabResultService, Depends(get_lab_result_service)],
    _: Annotated[User, Depends(require_permission("LAB_RESULT_ENTER"))],
    reason: Optional[str] = Query(None, max_length=500),
):
    result = service.cancel_result(result_id, reason=reason, actor_user_id=actor.id)
    return {"success": True, "message": "Lab result cancelled.", "result": result}


@router.get(
    "/{result_id}",
    response_model=LabResultReadSchema,
    summary="Get a lab result",
)
def get_result(
    result_id: int,
    _: Annotated[User, Depends(require_permission("LAB_RESULT_ENTER", "LAB_RESULT_VERIFY", "LAB_RESULT_RELEASE"))],
    service: Annotated[LabResultService, Depends(get_lab_result_service)],
):
    return service.get(result_id)


@router.get(
    "/by-item/{item_id}",
    response_model=LabResultReadSchema,
    summary="Get a lab result by order-item id",
)
def get_by_item(
    item_id: int,
    _: Annotated[User, Depends(require_permission("LAB_RESULT_ENTER", "LAB_RESULT_VERIFY", "LAB_RESULT_RELEASE"))],
    service: Annotated[LabResultService, Depends(get_lab_result_service)],
):
    result = service.get_by_order_item(item_id)
    if result is None:
        return {
            "id": 0,
            "lab_order_item_id": item_id,
            "entered_by_staff_id": None,
            "verified_by_staff_id": None,
            "result_status": "PENDING",
            "result_value": None,
            "result_text": None,
            "unit_of_measure": None,
            "reference_range": None,
            "interpretation": None,
            "entered_at": None,
            "verified_at": None,
            "released_at": None,
        }
    return result


# ---------------------------------------------------------------------------
# Branded lab report PDF (staff)
# ---------------------------------------------------------------------------

@router.get(
    "/orders/{order_id}/report.pdf",
    summary="Branded laboratory report PDF for a released order",
)
def lab_order_report_pdf(
    order_id: int,
    actor: CurrentActiveUser,
    service: Annotated[LabResultService, Depends(get_lab_result_service)],
    db: Annotated[Session, Depends(get_db)],
):
    from fastapi import Response
    from app.api.v1.endpoints.hr_routes import _load_tenant_logo_path
    from app.core.multitenancy import get_current_tenant
    from app.utils.lab_report_pdf import build_lab_report_pdf

    data = service.get_order_report_data(order_id)
    hospital = "Hospital"
    contact = None
    try:
        tenant = get_current_tenant()
        if tenant is not None:
            hospital = getattr(tenant, "name", None) or hospital
            contact = getattr(tenant, "contact_email", None) or getattr(tenant, "billing_email", None)
    except Exception:
        pass

    logo_path = _load_tenant_logo_path(db)
    try:
        pdf_bytes = build_lab_report_pdf(
            hospital_name=hospital, hospital_contact=contact,
            lab_name="Medical Laboratory", logo_path=logo_path,
            patient=data["patient"], visit_number=data["visit_number"],
            order_no=data["order_no"], ordered_at=data["ordered_at"],
            reported_at=data["reported_at"], rows=data["rows"],
            interpretation=data["interpretation"],
            scientist_name=data["scientist_name"],
            approved_by=data["approved_by"], verify_code=data["verify_code"],
        )
    finally:
        if logo_path:
            try:
                import os as _os
                _os.remove(logo_path)
            except OSError:
                pass
    safe = "".join(ch for ch in data["order_no"] if ch.isalnum() or ch in "-_")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="lab-report-{safe}.pdf"'})
