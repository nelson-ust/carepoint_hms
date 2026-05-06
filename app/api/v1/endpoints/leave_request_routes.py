from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.schemas.leave_request_schemas import (
    LeaveRequestCreateSchema,
    LeaveRequestReadSchema,
    LeaveRequestUpdateSchema,
    LeaveRequestSubmitSchema
)
from app.services.leave_request_service import LeaveRequestService

router = APIRouter(
    prefix="/leave-requests",
    tags=["Leave Requests"],
)

def get_leave_request_service(db: Annotated[Session, Depends(get_db)]) -> LeaveRequestService:
    return LeaveRequestService(db)

@router.post(
    "",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new leave request",
)
def create_leave_request(
    payload: LeaveRequestCreateSchema,
    service: Annotated[LeaveRequestService, Depends(get_leave_request_service)],
    current_user: CurrentActiveUser,
):
    leave_req = service.create_leave_request(payload)
    return {
        "success": True,
        "message": "Leave request created successfully.",
        "leave_request": LeaveRequestReadSchema.model_validate(leave_req),
    }

@router.get(
    "",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List leave requests",
)
def list_leave_requests(
    service: Annotated[LeaveRequestService, Depends(get_leave_request_service)],
    current_user: CurrentActiveUser,
    staff_profile_id: int = Query(None, description="Filter by staff profile ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    items, total = service.list_leave_requests(staff_profile_id=staff_profile_id, skip=skip, limit=limit)
    return {
        "success": True,
        "total": total,
        "items": [LeaveRequestReadSchema.model_validate(req) for req in items],
    }

@router.get(
    "/{request_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get leave request by ID",
)
def get_leave_request(
    request_id: int,
    service: Annotated[LeaveRequestService, Depends(get_leave_request_service)],
    current_user: CurrentActiveUser,
):
    leave_req = service.get_leave_request(request_id)
    return {
        "success": True,
        "leave_request": LeaveRequestReadSchema.model_validate(leave_req),
    }

@router.put(
    "/{request_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Update a leave request",
)
def update_leave_request(
    request_id: int,
    payload: LeaveRequestUpdateSchema,
    service: Annotated[LeaveRequestService, Depends(get_leave_request_service)],
    current_user: CurrentActiveUser,
):
    leave_req = service.update_leave_request(request_id, payload)
    return {
        "success": True,
        "message": "Leave request updated successfully.",
        "leave_request": LeaveRequestReadSchema.model_validate(leave_req),
    }

@router.delete(
    "/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a leave request",
)
def delete_leave_request(
    request_id: int,
    service: Annotated[LeaveRequestService, Depends(get_leave_request_service)],
    current_user: CurrentActiveUser,
):
    service.delete_leave_request(request_id)

@router.post(
    "/{request_id}/submit",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Submit a leave request for approval",
)
def submit_leave_request(
    request_id: int,
    payload: LeaveRequestSubmitSchema,
    service: Annotated[LeaveRequestService, Depends(get_leave_request_service)],
    current_user: CurrentActiveUser,
):
    leave_req = service.submit_leave_request(request_id, payload, user_id=current_user.id)
    return {
        "success": True,
        "message": "Leave request submitted for approval.",
        "leave_request": LeaveRequestReadSchema.model_validate(leave_req),
    }
