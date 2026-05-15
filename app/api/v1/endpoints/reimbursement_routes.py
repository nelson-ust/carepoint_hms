from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.schemas.reimbursement_schemas import (
    ReimbursementCreateSchema,
    ReimbursementReadSchema,
    ReimbursementUpdateSchema,
    ReimbursementSubmitSchema
)
from app.services.reimbursement_service import ReimbursementService

router = APIRouter(
    prefix="/reimbursements",
    tags=["Reimbursements"],
    dependencies=[Depends(require_plan_feature("hr"))]
)

def get_reimbursement_service(db: Annotated[Session, Depends(get_db)]) -> ReimbursementService:
    return ReimbursementService(db)

@router.post(
    "",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new reimbursement request",
)
def create_reimbursement(
    payload: ReimbursementCreateSchema,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    req = service.create_reimbursement(payload)
    return {
        "success": True,
        "message": "Reimbursement request created successfully.",
        "reimbursement": ReimbursementReadSchema.model_validate(req),
    }

@router.get(
    "",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List reimbursement requests",
)
def list_reimbursements(
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
    staff_profile_id: int = Query(None, description="Filter by staff profile ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    items, total = service.list_reimbursements(staff_profile_id=staff_profile_id, skip=skip, limit=limit)
    return {
        "success": True,
        "total": total,
        "items": [ReimbursementReadSchema.model_validate(req) for req in items],
    }

@router.get(
    "/{request_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get reimbursement request by ID",
)
def get_reimbursement(
    request_id: int,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    req = service.get_reimbursement(request_id)
    return {
        "success": True,
        "reimbursement": ReimbursementReadSchema.model_validate(req),
    }

@router.put(
    "/{request_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Update a reimbursement request",
)
def update_reimbursement(
    request_id: int,
    payload: ReimbursementUpdateSchema,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    req = service.update_reimbursement(request_id, payload)
    return {
        "success": True,
        "message": "Reimbursement request updated successfully.",
        "reimbursement": ReimbursementReadSchema.model_validate(req),
    }

@router.delete(
    "/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a reimbursement request",
)
def delete_reimbursement(
    request_id: int,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    service.delete_reimbursement(request_id)

@router.post(
    "/{request_id}/submit",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Submit a reimbursement request for approval",
)
def submit_reimbursement(
    request_id: int,
    payload: ReimbursementSubmitSchema,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    req = service.submit_reimbursement(request_id, payload, user_id=current_user.id)
    return {
        "success": True,
        "message": "Reimbursement request submitted for approval.",
        "reimbursement": ReimbursementReadSchema.model_validate(req),
    }
