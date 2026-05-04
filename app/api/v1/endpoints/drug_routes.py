# app/api/v1/endpoints/drug_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.drug_schema import (
    DrugActionResponseSchema,
    DrugCategoryActionResponseSchema,
    DrugCategoryCreateSchema,
    DrugCategoryListResponseSchema,
    DrugCategoryReadSchema,
    DrugCategoryUpdateSchema,
    DrugCreateSchema,
    DrugListResponseSchema,
    DrugReadSchema,
    DrugUpdateSchema,
)
from app.services.drug_service import DrugCategoryService, DrugService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/drugs", 
    tags=["Drugs"],
    dependencies=[Depends(require_plan_feature("pharmacy"))]
)


def get_drug_service(db: Annotated[Session, Depends(get_db)]) -> DrugService:
    return DrugService(db)


def get_drug_category_service(db: Annotated[Session, Depends(get_db)]) -> DrugCategoryService:
    return DrugCategoryService(db)


def _serialize_drug(d) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "generic_name": d.generic_name,
        "brand_name": d.brand_name,
        "strength": d.strength,
        "dosage_form": d.dosage_form,
        "pack_size": d.pack_size,
        "sku": d.sku,
        "drug_category_id": d.drug_category_id,
        "unit_price": d.unit_price,
        "reorder_level": d.reorder_level,
        "is_controlled": bool(d.is_controlled),
        "created_at": getattr(d, "created_at", None),
        "updated_at": getattr(d, "updated_at", None),
    }


def _serialize_category(c) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "code": c.code,
        "description": c.description,
        "created_at": getattr(c, "created_at", None),
        "updated_at": getattr(c, "updated_at", None),
    }


# ---------- DRUG CATEGORIES ----------

@router.get(
    "/categories",
    response_model=DrugCategoryListResponseSchema,
    summary="List drug categories",
)
def list_categories(
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_WRITE", "PRESCRIPTION_DISPENSE", "INVENTORY_READ"))],
    service: Annotated[DrugCategoryService, Depends(get_drug_category_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
):
    items, total = service.list(skip=skip, limit=limit, search=search)
    return paginate_response(
        items=[_serialize_category(c) for c in items],
        total=total, skip=skip, limit=limit,
        message="Drug categories fetched successfully.",
    )


@router.post(
    "/categories",
    response_model=DrugCategoryActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a drug category",
)
def create_category(
    payload: DrugCategoryCreateSchema,
    _: Annotated[User, Depends(require_permission("PHARMACY_STOCK_MANAGE", "INVENTORY_MANAGE"))],
    service: Annotated[DrugCategoryService, Depends(get_drug_category_service)],
):
    cat = service.create(payload)
    return {"success": True, "message": "Drug category created.", "category": _serialize_category(cat)}


@router.put(
    "/categories/{cat_id}",
    response_model=DrugCategoryActionResponseSchema,
    summary="Update a drug category",
)
def update_category(
    cat_id: int,
    payload: DrugCategoryUpdateSchema,
    _: Annotated[User, Depends(require_permission("PHARMACY_STOCK_MANAGE", "INVENTORY_MANAGE"))],
    service: Annotated[DrugCategoryService, Depends(get_drug_category_service)],
):
    cat = service.update(cat_id, payload)
    return {"success": True, "message": "Drug category updated.", "category": _serialize_category(cat)}


@router.delete(
    "/categories/{cat_id}",
    summary="Soft-delete a drug category",
)
def delete_category(
    cat_id: int,
    _: Annotated[User, Depends(require_permission("PHARMACY_STOCK_MANAGE", "INVENTORY_MANAGE"))],
    service: Annotated[DrugCategoryService, Depends(get_drug_category_service)],
):
    cat = service.soft_delete(cat_id)
    return {"success": True, "message": "Drug category deactivated.", "category_id": cat.id}


# ---------- DRUGS ----------

@router.get(
    "/",
    response_model=DrugListResponseSchema,
    summary="List drugs",
)
def list_drugs(
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_WRITE", "PRESCRIPTION_DISPENSE", "INVENTORY_READ"))],
    service: Annotated[DrugService, Depends(get_drug_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    is_controlled: Optional[bool] = Query(None),
):
    items, total = service.list(
        skip=skip, limit=limit, search=search,
        category_id=category_id, is_controlled=is_controlled,
    )
    return paginate_response(
        items=[_serialize_drug(d) for d in items],
        total=total, skip=skip, limit=limit,
        message="Drugs fetched successfully.",
    )


@router.post(
    "/",
    response_model=DrugActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a drug",
)
def create_drug(
    payload: DrugCreateSchema,
    _: Annotated[User, Depends(require_permission("PHARMACY_STOCK_MANAGE", "INVENTORY_MANAGE"))],
    service: Annotated[DrugService, Depends(get_drug_service)],
):
    drug = service.create(payload)
    return {"success": True, "message": "Drug created.", "drug": _serialize_drug(drug)}


@router.get(
    "/{drug_id}",
    response_model=DrugReadSchema,
    summary="Get a drug",
)
def get_drug(
    drug_id: int,
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_WRITE", "PRESCRIPTION_DISPENSE", "INVENTORY_READ"))],
    service: Annotated[DrugService, Depends(get_drug_service)],
):
    return _serialize_drug(service.get(drug_id))


@router.put(
    "/{drug_id}",
    response_model=DrugActionResponseSchema,
    summary="Update a drug",
)
def update_drug(
    drug_id: int,
    payload: DrugUpdateSchema,
    _: Annotated[User, Depends(require_permission("PHARMACY_STOCK_MANAGE", "INVENTORY_MANAGE"))],
    service: Annotated[DrugService, Depends(get_drug_service)],
):
    drug = service.update(drug_id, payload)
    return {"success": True, "message": "Drug updated.", "drug": _serialize_drug(drug)}


@router.delete(
    "/{drug_id}",
    summary="Soft-delete a drug",
)
def delete_drug(
    drug_id: int,
    _: Annotated[User, Depends(require_permission("PHARMACY_STOCK_MANAGE", "INVENTORY_MANAGE"))],
    service: Annotated[DrugService, Depends(get_drug_service)],
):
    drug = service.soft_delete(drug_id)
    return {"success": True, "message": "Drug deactivated.", "drug_id": drug.id}
