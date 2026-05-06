from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.schemas.timesheet_schemas import (
    TimesheetCreateSchema,
    TimesheetReadSchema,
    TimesheetUpdateSchema,
    TimesheetSubmitSchema
)
from app.services.timesheet_service import TimesheetService

router = APIRouter(
    prefix="/timesheets",
    tags=["Timesheets"],
)

def get_timesheet_service(db: Annotated[Session, Depends(get_db)]) -> TimesheetService:
    return TimesheetService(db)

@router.post(
    "",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new timesheet",
)
def create_timesheet(
    payload: TimesheetCreateSchema,
    service: Annotated[TimesheetService, Depends(get_timesheet_service)],
    current_user: CurrentActiveUser,
):
    timesheet = service.create_timesheet(payload)
    return {
        "success": True,
        "message": "Timesheet created successfully.",
        "timesheet": TimesheetReadSchema.model_validate(timesheet),
    }

@router.get(
    "",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List timesheets",
)
def list_timesheets(
    service: Annotated[TimesheetService, Depends(get_timesheet_service)],
    current_user: CurrentActiveUser,
    staff_profile_id: int = Query(None, description="Filter by staff profile ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    items, total = service.list_timesheets(staff_profile_id=staff_profile_id, skip=skip, limit=limit)
    return {
        "success": True,
        "total": total,
        "items": [TimesheetReadSchema.model_validate(t) for t in items],
    }

@router.get(
    "/{timesheet_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get timesheet by ID",
)
def get_timesheet(
    timesheet_id: int,
    service: Annotated[TimesheetService, Depends(get_timesheet_service)],
    current_user: CurrentActiveUser,
):
    timesheet = service.get_timesheet(timesheet_id)
    return {
        "success": True,
        "timesheet": TimesheetReadSchema.model_validate(timesheet),
    }

@router.put(
    "/{timesheet_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Update a timesheet",
)
def update_timesheet(
    timesheet_id: int,
    payload: TimesheetUpdateSchema,
    service: Annotated[TimesheetService, Depends(get_timesheet_service)],
    current_user: CurrentActiveUser,
):
    timesheet = service.update_timesheet(timesheet_id, payload)
    return {
        "success": True,
        "message": "Timesheet updated successfully.",
        "timesheet": TimesheetReadSchema.model_validate(timesheet),
    }

@router.delete(
    "/{timesheet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a timesheet",
)
def delete_timesheet(
    timesheet_id: int,
    service: Annotated[TimesheetService, Depends(get_timesheet_service)],
    current_user: CurrentActiveUser,
):
    service.delete_timesheet(timesheet_id)

@router.post(
    "/{timesheet_id}/submit",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Submit a timesheet for approval",
)
def submit_timesheet(
    timesheet_id: int,
    payload: TimesheetSubmitSchema,
    service: Annotated[TimesheetService, Depends(get_timesheet_service)],
    current_user: CurrentActiveUser,
):
    timesheet = service.submit_timesheet(timesheet_id, payload, user_id=current_user.id)
    return {
        "success": True,
        "message": "Timesheet submitted for approval.",
        "timesheet": TimesheetReadSchema.model_validate(timesheet),
    }
