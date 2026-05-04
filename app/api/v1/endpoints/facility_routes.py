from typing import Annotated, List
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.facility_schemas import FacilityCreate, FacilityUpdate, FacilityRead
from app.services.facility_service import FacilityService
from app.dependencies.role import require_permission

router = APIRouter(prefix="/facilities", tags=["Organization - Facilities/Branches"])

def get_facility_service(db: Annotated[Session, Depends(get_db)]) -> FacilityService:
    return FacilityService(db)

@router.get("", response_model=List[FacilityRead])
def list_facilities(
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_READ"))]
):
    """
    List all facilities/branches for the current tenant.
    """
    return service.list_facilities()

@router.get("/{facility_id}", response_model=FacilityRead)
def get_facility(
    facility_id: int,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_READ"))]
):
    """
    Get details of a specific facility.
    """
    return service.get_facility(facility_id)

@router.post("", response_model=FacilityRead, status_code=status.HTTP_201_CREATED)
def create_facility(
    payload: FacilityCreate,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_CREATE"))]
):
    """
    Create a new facility/branch. 
    Enforces subscription limits.
    """
    return service.create_facility(payload)

@router.put("/{facility_id}", response_model=FacilityRead)
def update_facility(
    facility_id: int,
    payload: FacilityUpdate,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_UPDATE"))]
):
    """
    Update facility details.
    """
    return service.update_facility(facility_id, payload)

@router.delete("/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility(
    facility_id: int,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_DELETE"))]
):
    """
    Delete a facility.
    """
    service.delete_facility(facility_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
