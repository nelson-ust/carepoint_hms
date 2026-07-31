from __future__ import annotations

"""
app.api.v1.endpoints.visit_flow_routes

FastAPI routes for reusable visit flow templates and runtime visit flow steps.

Purpose
-------
This module exposes API endpoints for:

- managing VisitFlowTemplate records
- managing VisitFlowTemplateStep records
- managing VisitFlowStep records
- creating template + template steps + runtime steps in one endpoint

Security
--------
These endpoints are intended for authorized administrative / workflow
configuration users and are protected with the admin dependency.
"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser, require_plan_feature
from app.schemas.visit_flow_schemas import (
    VisitFlowActionResponseSchema,
    VisitFlowCombinedCreateResultSchema,
    VisitFlowCombinedCreateSchema,
    VisitFlowStepCreateSchema,
    VisitFlowStepListResponseSchema,
    VisitFlowStepReadSchema,
    VisitFlowStepUpdateSchema,
    VisitFlowTemplateCreateSchema,
    VisitFlowTemplateListResponseSchema,
    VisitFlowTemplateReadSchema,
    VisitFlowTemplateStepCreateSchema,
    VisitFlowTemplateStepReadSchema,
    VisitFlowTemplateStepUpdateSchema,
    VisitFlowTemplateUpdateSchema,
    VisitFlowTemplateUpdateSchema,
)
from app.seeds.clinical_flow_seed import seed_standard_visit_flow
from app.services.visit_flow_service import VisitFlowService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/visit-flows",
    tags=["Visit Flow Management"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)


@router.post(
    "/seed-standard",
    status_code=status.HTTP_200_OK,
    summary="Seed the standard outpatient clinical pathway",
)
def seed_standard_pathway(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create the default sequential outpatient pathway template for this tenant
    (Registration → Triage → Consultation → Laboratory → Radiology → Pharmacy →
    Billing), mapped to the tenant's configured service delivery points.

    Idempotent — if the standard template already exists it is returned as-is.
    """
    return seed_standard_visit_flow(db)


def get_visit_flow_service(
    db: Annotated[Session, Depends(get_db)],
) -> VisitFlowService:
    """
    Dependency provider for the visit flow service.
    """
    return VisitFlowService(db)


# ============================================================
# TEMPLATE ROUTES
# ============================================================

@router.post(
    "/templates",
    response_model=VisitFlowTemplateReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create visit flow template",
)
def create_template(
    payload: VisitFlowTemplateCreateSchema,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Create a reusable visit flow template.
    """
    return service.create_template(payload)


@router.get(
    "/templates",
    response_model=VisitFlowTemplateListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List visit flow templates",
)
def list_templates(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=1000, description="Pagination size."),
    code: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
):
    """
    Return a paginated list of reusable visit flow templates.

    Readable by any authenticated clinical/reception user so they can pick a
    care pathway when starting a visit. If the tenant has no templates yet and
    no filters are applied, the standard outpatient pathway is seeded on the
    fly (idempotent, best-effort) so the picker is never empty when service
    delivery points exist.
    """
    items, total = service.list_templates(
        skip=skip,
        limit=limit,
        code=code,
        name=name,
    )

    if total == 0 and not code and not name:
        try:
            seed_standard_visit_flow(db)
        except Exception:  # pragma: no cover - seeding must never break listing
            pass
        else:
            items, total = service.list_templates(
                skip=skip, limit=limit, code=code, name=name,
            )

    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Visit flow templates fetched successfully.",
    )


@router.get(
    "/templates/{template_id}",
    response_model=VisitFlowTemplateReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get visit flow template",
)
def get_template(
    template_id: int,
    _: CurrentActiveUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Return a reusable visit flow template with ordered steps. Readable by any
    authenticated user so the care-pathway picker can preview steps.
    """
    return service.get_template(template_id)


@router.put(
    "/templates/{template_id}",
    response_model=VisitFlowTemplateReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update visit flow template",
)
def update_template(
    template_id: int,
    payload: VisitFlowTemplateUpdateSchema,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Update a reusable visit flow template.
    """
    return service.update_template(template_id, payload)


@router.delete(
    "/templates/{template_id}",
    response_model=VisitFlowActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Delete visit flow template",
)
def delete_template(
    template_id: int,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Soft-delete a reusable visit flow template.
    """
    template = service.delete_template(template_id)
    return {
        "success": True,
        "message": f"Visit flow template '{template.code}' deleted successfully.",
    }


# ============================================================
# TEMPLATE STEP ROUTES
# ============================================================

@router.post(
    "/template-steps",
    response_model=VisitFlowTemplateStepReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create visit flow template step",
)
def create_template_step(
    payload: VisitFlowTemplateStepCreateSchema,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Create a reusable visit flow template step.
    """
    return service.create_template_step(payload)


@router.put(
    "/template-steps/{template_step_id}",
    response_model=VisitFlowTemplateStepReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update visit flow template step",
)
def update_template_step(
    template_step_id: int,
    payload: VisitFlowTemplateStepUpdateSchema,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Update a reusable visit flow template step.
    """
    return service.update_template_step(template_step_id, payload)


@router.delete(
    "/template-steps/{template_step_id}",
    response_model=VisitFlowActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Delete visit flow template step",
)
def delete_template_step(
    template_step_id: int,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Soft-delete a reusable visit flow template step.
    """
    step = service.delete_template_step(template_step_id)
    return {
        "success": True,
        "message": f"Visit flow template step '{step.id}' deleted successfully.",
    }


# ============================================================
# RUNTIME VISIT STEP ROUTES
# ============================================================

@router.post(
    "/visit-steps",
    response_model=VisitFlowStepReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create runtime visit flow step",
)
def create_visit_step(
    payload: VisitFlowStepCreateSchema,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Create a runtime visit flow step for a specific visit.
    """
    return service.create_visit_step(payload)


@router.get(
    "/visit-steps",
    response_model=VisitFlowStepListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List runtime visit flow steps",
)
def list_visit_steps(
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
    visit_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(50, ge=1, le=1000, description="Pagination size."),
):
    """
    Return a paginated list of runtime visit flow steps.
    """
    items, total = service.list_visit_steps(
        visit_id=visit_id,
        skip=skip,
        limit=limit,
    )

    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Visit flow steps fetched successfully.",
    )


@router.get(
    "/visit-steps/{visit_step_id}",
    response_model=VisitFlowStepReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get runtime visit flow step",
)
def get_visit_step(
    visit_step_id: int,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Return a runtime visit flow step.
    """
    return service.get_visit_step(visit_step_id)


@router.put(
    "/visit-steps/{visit_step_id}",
    response_model=VisitFlowStepReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update runtime visit flow step",
)
def update_visit_step(
    visit_step_id: int,
    payload: VisitFlowStepUpdateSchema,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Update a runtime visit flow step.
    """
    return service.update_visit_step(visit_step_id, payload)


@router.delete(
    "/visit-steps/{visit_step_id}",
    response_model=VisitFlowActionResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Delete runtime visit flow step",
)
def delete_visit_step(
    visit_step_id: int,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Soft-delete a runtime visit flow step.
    """
    step = service.delete_visit_step(visit_step_id)
    return {
        "success": True,
        "message": f"Visit flow step '{step.id}' deleted successfully.",
    }


# ============================================================
# COMBINED CREATE ROUTE
# ============================================================

@router.post(
    "/combined-create",
    response_model=VisitFlowCombinedCreateResultSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create template, template steps, and visit steps together",
)
def create_combined_flow_records(
    payload: VisitFlowCombinedCreateSchema,
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Create VisitFlowTemplate, VisitFlowTemplateStep, and VisitFlowStep
    together in a single transaction.
    """
    result = service.create_combined_flow_records(payload)

    return {
        "success": True,
        "message": result["message"],
        "template": result["template"],
        "created_template_steps": result["created_template_steps"],
        "created_visit_steps": result["created_visit_steps"],
    }