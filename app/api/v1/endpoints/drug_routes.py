# app/api/v1/endpoints/drug_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from io import BytesIO

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.core.exceptions import BadRequestError
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.drug_schema import (
    DrugActionResponseSchema,
    DrugCategoryActionResponseSchema,
    DrugCategoryCreateSchema,
    DrugCategoryListResponseSchema,
    DrugCategoryUpdateSchema,
    DrugCreateSchema,
    DrugListResponseSchema,
    DrugReadSchema,
    DrugUpdateSchema,
)
from app.services.drug_service import DrugCategoryService, DrugService
from app.utils.drug_import import parse_category_rows, parse_drug_rows
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
    limit: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None),
):
    items, total = service.list(skip=skip, limit=limit, search=search)
    return paginate_response(
        items=items,
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
    return {"success": True, "message": "Drug category created.", "category": cat}


# Static segments declared before "/categories/{cat_id}" so they aren't
# captured as a category id.

@router.get(
    "/categories/template",
    summary="Download the bulk drug-category upload template",
)
def download_category_template(
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_WRITE", "PRESCRIPTION_DISPENSE", "INVENTORY_READ"))],
    service: Annotated[DrugCategoryService, Depends(get_drug_category_service)],
):
    """Return an .xlsx template for bulk-uploading drug categories."""
    content = service.build_import_template()
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="drug_categories_template.xlsx"'},
    )


@router.post(
    "/categories/bulk-upload",
    summary="Bulk-upload drug categories from a filled template",
)
async def bulk_upload_categories(
    _: Annotated[User, Depends(require_permission("PHARMACY_STOCK_MANAGE", "INVENTORY_MANAGE"))],
    service: Annotated[DrugCategoryService, Depends(get_drug_category_service)],
    file: UploadFile = File(..., description="Filled .xlsx template"),
):
    """Import many drug categories at once from a filled template."""
    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".xlsm")):
        raise BadRequestError(message="Please upload the .xlsx template file.")

    content = await file.read()
    if not content:
        raise BadRequestError(message="The uploaded file is empty.")

    try:
        rows = parse_category_rows(content)
    except ValueError as exc:
        raise BadRequestError(message=str(exc))
    except Exception:
        raise BadRequestError(
            message="Could not read the spreadsheet. Please upload the provided .xlsx template."
        )

    return service.bulk_create(rows)


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
    return {"success": True, "message": "Drug category updated.", "category": cat}


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
    limit: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    is_controlled: Optional[bool] = Query(None),
):
    items, total = service.list(
        skip=skip, limit=limit, search=search,
        category_id=category_id, is_controlled=is_controlled,
    )
    return paginate_response(
        items=items,
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
    return {"success": True, "message": "Drug created.", "drug": drug}


# NOTE: these static segments are declared before "/{drug_id}" so they are not
# captured as a drug id.

@router.get(
    "/template",
    summary="Download the bulk drug-upload template",
)
def download_drug_template(
    _: Annotated[User, Depends(require_permission("PRESCRIPTION_WRITE", "PRESCRIPTION_DISPENSE", "INVENTORY_READ"))],
    service: Annotated[DrugService, Depends(get_drug_service)],
):
    """
    Return an .xlsx template with Dosage Form / Controlled dropdowns and a
    Category dropdown sourced from this tenant's drug categories.
    """
    content = service.build_import_template()
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="drugs_template.xlsx"'},
    )


@router.post(
    "/bulk-upload",
    summary="Bulk-upload drugs from a filled template",
)
async def bulk_upload_drugs(
    _: Annotated[User, Depends(require_permission("PHARMACY_STOCK_MANAGE", "INVENTORY_MANAGE"))],
    service: Annotated[DrugService, Depends(get_drug_service)],
    file: UploadFile = File(..., description="Filled .xlsx template"),
):
    """
    Import many drugs at once from a filled template. Each row is validated
    independently; the response lists any rows that were rejected.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".xlsm")):
        raise BadRequestError(message="Please upload the .xlsx template file.")

    content = await file.read()
    if not content:
        raise BadRequestError(message="The uploaded file is empty.")

    try:
        rows = parse_drug_rows(content)
    except ValueError as exc:
        raise BadRequestError(message=str(exc))
    except Exception:
        raise BadRequestError(
            message="Could not read the spreadsheet. Please upload the provided .xlsx template."
        )

    return service.bulk_create(rows)


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
    return service.get(drug_id)


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
    return {"success": True, "message": "Drug updated.", "drug": drug}


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

