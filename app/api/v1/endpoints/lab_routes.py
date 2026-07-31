# app/api/v1/endpoints/lab_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.lab_schema import (
    LabTestCatalogActionResponseSchema,
    LabTestCatalogCreateSchema,
    LabTestCatalogListResponseSchema,
    LabTestCatalogReadSchema,
    LabTestCatalogUpdateSchema,
)
from app.services.lab_service import LabCatalogService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/lab/tests",
    tags=["Laboratory - Catalog"],
    dependencies=[Depends(require_plan_feature("laboratory"))]
)


def get_lab_service(db: Annotated[Session, Depends(get_db)]) -> LabCatalogService:
    return LabCatalogService(db)


@router.get(
    "/",
    response_model=LabTestCatalogListResponseSchema,
    summary="List lab tests",
)
def list_tests(
    _: Annotated[User, Depends(require_permission("LAB_ORDER_CREATE", "LAB_RESULT_ENTER"))],
    service: Annotated[LabCatalogService, Depends(get_lab_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None),
):
    items, total = service.list_tests(skip=skip, limit=limit, search=search)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Lab tests fetched successfully.",
    )


@router.post(
    "/",
    response_model=LabTestCatalogActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add a lab test",
)
def create_test(
    payload: LabTestCatalogCreateSchema,
    _: Annotated[User, Depends(require_permission("LAB_ORDER_CREATE"))],
    service: Annotated[LabCatalogService, Depends(get_lab_service)],
):
    test = service.create(payload)
    return {"success": True, "message": "Lab test added.", "lab_test": test}


@router.get(
    "/{test_id}",
    response_model=LabTestCatalogReadSchema,
    summary="Get a lab test",
)
def get_test(
    test_id: int,
    _: Annotated[User, Depends(require_permission("LAB_ORDER_CREATE", "LAB_RESULT_ENTER"))],
    service: Annotated[LabCatalogService, Depends(get_lab_service)],
):
    return service.get(test_id)


@router.put(
    "/{test_id}",
    response_model=LabTestCatalogActionResponseSchema,
    summary="Update a lab test",
)
def update_test(
    test_id: int,
    payload: LabTestCatalogUpdateSchema,
    _: Annotated[User, Depends(require_permission("LAB_ORDER_CREATE"))],
    service: Annotated[LabCatalogService, Depends(get_lab_service)],
):
    test = service.update(test_id, payload)
    return {"success": True, "message": "Lab test updated.", "lab_test": test}


@router.delete(
    "/{test_id}",
    summary="Soft-delete a lab test",
)
def delete_test(
    test_id: int,
    _: Annotated[User, Depends(require_permission("LAB_ORDER_CREATE"))],
    service: Annotated[LabCatalogService, Depends(get_lab_service)],
):
    test = service.soft_delete(test_id)
    return {"success": True, "message": "Lab test deactivated.", "lab_test_id": test.id}
