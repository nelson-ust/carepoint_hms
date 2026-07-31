# app/api/v1/endpoints/procedure_routes.py
from __future__ import annotations

"""
FastAPI routes for clinical procedure orders.

Two routers:
- ``/procedures`` — master catalog
- ``/procedure-orders`` — per-visit ordered procedures
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.procedure_schema import (
    ProcedureCatalogActionResponseSchema,
    ProcedureCatalogCreateSchema,
    ProcedureCatalogListResponseSchema,
    ProcedureCatalogReadSchema,
    ProcedureCatalogUpdateSchema,
    ProcedureOrderActionResponseSchema,
    ProcedureOrderCreateSchema,
    ProcedureOrderListResponseSchema,
    ProcedureOrderReadSchema,
    ProcedureOrderTransitionSchema,
)
from app.services.procedure_service import (
    ProcedureCatalogService,
    ProcedureOrderService,
)
from app.utils.pagination import paginate_response

catalog_router = APIRouter(
    prefix="/procedures", 
    tags=["Procedures - Catalog"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)
order_router = APIRouter(
    prefix="/procedure-orders", 
    tags=["Procedures - Orders"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)


def get_catalog_service(db: Annotated[Session, Depends(get_db)]) -> ProcedureCatalogService:
    return ProcedureCatalogService(db)


def get_order_service(db: Annotated[Session, Depends(get_db)]) -> ProcedureOrderService:
    return ProcedureOrderService(db)


def _catalog_dict(p) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "description": p.description,
        "default_price": p.default_price,
        "created_at": getattr(p, "created_at", None),
        "updated_at": getattr(p, "updated_at", None),
    }


def _order_dict(o) -> dict:
    return {
        "id": o.id,
        "visit_id": o.visit_id,
        "consultation_id": o.consultation_id,
        "procedure_catalog_id": o.procedure_catalog_id,
        "ordered_by_staff_id": o.ordered_by_staff_id,
        "performed_by_staff_id": o.performed_by_staff_id,
        "status": str(o.status),
        "findings": o.findings,
        "notes": o.notes,
        "ordered_at": o.ordered_at,
        "performed_at": o.performed_at,
        "created_at": getattr(o, "created_at", None),
        "updated_at": getattr(o, "updated_at", None),
    }


# ============================================================
# CATALOG
# ============================================================


@catalog_router.get(
    "/",
    response_model=ProcedureCatalogListResponseSchema,
    summary="List procedures (catalog)",
)
def list_procedures(
    _: Annotated[User, Depends(require_permission("PROCEDURE_ORDER", "PROCEDURE_PERFORM"))],
    service: Annotated[ProcedureCatalogService, Depends(get_catalog_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None),
):
    items, total = service.list_procedures(skip=skip, limit=limit, search=search)
    return paginate_response(
        items=[_catalog_dict(p) for p in items],
        total=total, skip=skip, limit=limit,
        message="Procedures fetched successfully.",
    )


@catalog_router.post(
    "/",
    response_model=ProcedureCatalogActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a procedure",
)
def create_procedure(
    payload: ProcedureCatalogCreateSchema,
    _: Annotated[User, Depends(require_permission("PROCEDURE_MANAGE"))],
    service: Annotated[ProcedureCatalogService, Depends(get_catalog_service)],
):
    p = service.create(payload)
    return {"success": True, "message": "Procedure created.", "procedure": _catalog_dict(p)}


@catalog_router.get(
    "/{procedure_id}",
    response_model=ProcedureCatalogReadSchema,
    summary="Get a procedure",
)
def get_procedure(
    procedure_id: int,
    _: Annotated[User, Depends(require_permission("PROCEDURE_ORDER", "PROCEDURE_PERFORM"))],
    service: Annotated[ProcedureCatalogService, Depends(get_catalog_service)],
):
    return _catalog_dict(service.get(procedure_id))


@catalog_router.put(
    "/{procedure_id}",
    response_model=ProcedureCatalogActionResponseSchema,
    summary="Update a procedure",
)
def update_procedure(
    procedure_id: int,
    payload: ProcedureCatalogUpdateSchema,
    _: Annotated[User, Depends(require_permission("PROCEDURE_MANAGE"))],
    service: Annotated[ProcedureCatalogService, Depends(get_catalog_service)],
):
    p = service.update(procedure_id, payload)
    return {"success": True, "message": "Procedure updated.", "procedure": _catalog_dict(p)}


@catalog_router.delete(
    "/{procedure_id}",
    summary="Soft-delete a procedure",
)
def soft_delete_procedure(
    procedure_id: int,
    _: Annotated[User, Depends(require_permission("PROCEDURE_MANAGE"))],
    service: Annotated[ProcedureCatalogService, Depends(get_catalog_service)],
):
    p = service.soft_delete(procedure_id)
    return {"success": True, "message": "Procedure deactivated.", "procedure_id": p.id}


# ============================================================
# ORDERS
# ============================================================


@order_router.get(
    "/visits/{visit_id}",
    response_model=ProcedureOrderListResponseSchema,
    summary="List procedure orders for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("PROCEDURE_ORDER", "PROCEDURE_PERFORM", "VISIT_READ"))],
    service: Annotated[ProcedureOrderService, Depends(get_order_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=[_order_dict(o) for o in items],
        total=total, skip=skip, limit=limit,
        message="Procedure orders fetched successfully.",
    )


@order_router.get(
    "/worklist",
    response_model=ProcedureOrderListResponseSchema,
    summary="Procedure-room worklist (open orders)",
)
def list_worklist(
    _: Annotated[User, Depends(require_permission("PROCEDURE_PERFORM"))],
    service: Annotated[ProcedureOrderService, Depends(get_order_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
):
    items, total = service.list_open(skip=skip, limit=limit)
    return paginate_response(
        items=[_order_dict(o) for o in items],
        total=total, skip=skip, limit=limit,
        message="Procedure worklist fetched successfully.",
    )


@order_router.post(
    "/",
    response_model=ProcedureOrderActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Order a procedure",
)
def order_procedure(
    payload: ProcedureOrderCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("PROCEDURE_ORDER"))],
    service: Annotated[ProcedureOrderService, Depends(get_order_service)],
):
    o = service.order_procedure(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Procedure ordered.", "order": _order_dict(o)}


@order_router.get(
    "/{order_id}",
    response_model=ProcedureOrderReadSchema,
    summary="Get a procedure order",
)
def get_order(
    order_id: int,
    _: Annotated[User, Depends(require_permission("PROCEDURE_ORDER", "PROCEDURE_PERFORM"))],
    service: Annotated[ProcedureOrderService, Depends(get_order_service)],
):
    return _order_dict(service.get(order_id))


@order_router.post(
    "/{order_id}/start",
    response_model=ProcedureOrderActionResponseSchema,
    summary="Start a procedure",
)
def start_procedure(
    order_id: int,
    payload: ProcedureOrderTransitionSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("PROCEDURE_PERFORM"))],
    service: Annotated[ProcedureOrderService, Depends(get_order_service)],
):
    o = service.start_procedure(order_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Procedure started.", "order": _order_dict(o)}


@order_router.post(
    "/{order_id}/complete",
    response_model=ProcedureOrderActionResponseSchema,
    summary="Complete a procedure",
)
def complete_procedure(
    order_id: int,
    payload: ProcedureOrderTransitionSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("PROCEDURE_PERFORM"))],
    service: Annotated[ProcedureOrderService, Depends(get_order_service)],
):
    o = service.complete_procedure(order_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Procedure completed.", "order": _order_dict(o)}


@order_router.post(
    "/{order_id}/cancel",
    response_model=ProcedureOrderActionResponseSchema,
    summary="Cancel a procedure order",
)
def cancel_procedure(
    order_id: int,
    payload: ProcedureOrderTransitionSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("PROCEDURE_ORDER"))],
    service: Annotated[ProcedureOrderService, Depends(get_order_service)],
):
    o = service.cancel_procedure(order_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Procedure cancelled.", "order": _order_dict(o)}
