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
from app.core.dependencies import AdminUser
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
)
from app.services.visit_flow_service import VisitFlowService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/visit-flows",
    tags=["Visit Flow Management"],
)


def get_visit_flow_service(
    db: Annotated[Session, Depends(get_db)],
) -> VisitFlowService:
    """
    Dependency provider for the visit flow service.
    """
    return VisitFlowService(db)


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def _safe_enum(value) -> Optional[str]:
    """
    Convert enum-like values to strings safely.
    """
    if value is None:
        return None
    return str(value)


def _serialize_service_delivery_point(service_point) -> Optional[dict[str, Any]]:
    """
    Serialize a lightweight service delivery point payload.
    """
    if not service_point:
        return None

    return {
        "id": service_point.id,
        "name": service_point.name,
        "code": service_point.code,
        "service_point_type": _safe_enum(getattr(service_point, "service_point_type", None)),
        "department_id": getattr(service_point, "department_id", None),
        "location_description": getattr(service_point, "location_description", None),
        "queue_prefix": getattr(service_point, "queue_prefix", None),
        "supports_appointments": getattr(service_point, "supports_appointments", False),
        "supports_walk_in": getattr(service_point, "supports_walk_in", False),
    }


def _serialize_template_step(step) -> dict[str, Any]:
    """
    Serialize a reusable visit flow template step.
    """
    return {
        "id": step.id,
        "template_id": step.template_id,
        "service_delivery_point_id": step.service_delivery_point_id,
        "step_order": step.step_order,
        "is_required": step.is_required,
        "notes": step.notes,
        "service_delivery_point": _serialize_service_delivery_point(
            getattr(step, "service_delivery_point", None)
        ),
        "created_at": step.created_at,
        "updated_at": step.updated_at,
    }


def _serialize_template(template) -> dict[str, Any]:
    """
    Serialize a reusable visit flow template.
    """
    return {
        "id": template.id,
        "name": template.name,
        "code": template.code,
        "description": template.description,
        "steps": [
            _serialize_template_step(step)
            for step in (template.steps or [])
        ],
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def _serialize_runtime_step(step) -> dict[str, Any]:
    """
    Serialize a runtime visit flow step.
    """
    return {
        "id": step.id,
        "visit_id": step.visit_id,
        "service_delivery_point_id": step.service_delivery_point_id,
        "step_order": step.step_order,
        "status": _safe_enum(step.status),
        "is_current": step.is_current,
        "is_required": step.is_required,
        "is_skipped": step.is_skipped,
        "routed_by_id": step.routed_by_id,
        "started_at": step.started_at,
        "completed_at": step.completed_at,
        "notes": step.notes,
        "service_delivery_point": _serialize_service_delivery_point(
            getattr(step, "service_delivery_point", None)
        ),
        "created_at": step.created_at,
        "updated_at": step.updated_at,
    }


def _serialize_template_list_step(step) -> dict[str, Any]:
    """
    Serialize a template step for the list view (flat).
    """
    sdp = getattr(step, "service_delivery_point", None)
    return {
        "id": step.id,
        "template_id": step.template_id,
        "service_delivery_point_id": step.service_delivery_point_id,
        "service_delivery_point_name": getattr(sdp, "name", None) if sdp else None,
        "step_order": step.step_order,
        "notes": step.notes,
    }


def _serialize_template_list_item(template) -> dict[str, Any]:
    """
    Serialize a template list item with flat steps.
    """
    return {
        "id": template.id,
        "name": template.name,
        "code": template.code,
        "description": template.description,
        "associated_visit_flow_templates_steps": [
            _serialize_template_list_step(step)
            for step in (template.steps or [])
        ],
    }


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
    template = service.create_template(payload)
    return _serialize_template(template)


@router.get(
    "/templates",
    response_model=VisitFlowTemplateListResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="List visit flow templates",
)
def list_templates(
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
    skip: int = Query(0, ge=0, description="Pagination offset."),
    limit: int = Query(20, ge=1, le=100, description="Pagination size."),
    code: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
):
    """
    Return a paginated list of reusable visit flow templates.
    """
    items, total = service.list_templates(
        skip=skip,
        limit=limit,
        code=code,
        name=name,
    )

    return paginate_response(
        items=[_serialize_template_list_item(item) for item in items],
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
    _: AdminUser,
    service: Annotated[VisitFlowService, Depends(get_visit_flow_service)],
):
    """
    Return a reusable visit flow template with ordered steps.
    """
    template = service.get_template(template_id)
    return _serialize_template(template)


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
    template = service.update_template(template_id, payload)
    return _serialize_template(template)


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
    step = service.create_template_step(payload)
    return _serialize_template_step(step)


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
    step = service.update_template_step(template_step_id, payload)
    return _serialize_template_step(step)


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
    step = service.create_visit_step(payload)
    return _serialize_runtime_step(step)


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
    limit: int = Query(50, ge=1, le=200, description="Pagination size."),
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
        items=[_serialize_runtime_step(item) for item in items],
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
    step = service.get_visit_step(visit_step_id)
    return _serialize_runtime_step(step)


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
    step = service.update_visit_step(visit_step_id, payload)
    return _serialize_runtime_step(step)


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
        "template": _serialize_template(result["template"]) if result["template"] else None,
        "created_template_steps": [
            _serialize_template_step(step)
            for step in result["created_template_steps"]
        ],
        "created_visit_steps": [
            _serialize_runtime_step(step)
            for step in result["created_visit_steps"]
        ],
    }