from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, status, Response, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.facility_schemas import (
    FacilityCreate, FacilityUpdate, FacilityRead,
    FacilityNetworkCreate, FacilityNetworkUpdate, FacilityNetworkRead,
    FacilityServiceAreaCreate, FacilityServiceAreaUpdate, FacilityServiceAreaRead
)
from app.services.facility_service import FacilityService
from app.dependencies.role import require_permission

router = APIRouter(prefix="/facilities", tags=["Organization - Facilities/Branches"])

def get_facility_service(db: Annotated[Session, Depends(get_db)]) -> FacilityService:
    """
    Dependency that provides a FacilityService instance.
    """
    return FacilityService(db)

# --- FACILITY ROUTES ---

@router.get("", response_model=List[FacilityRead])
def list_facilities(
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_READ"))]
):
    """
    List all facilities/branches for the current tenant.
    Returns nested network and service area information.
    """
    return service.list_facilities()

@router.get("/{facility_id}", response_model=FacilityRead)
def get_facility(
    facility_id: int,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_READ"))]
):
    """
    Get detailed information about a specific facility by its ID.
    """
    return service.get_facility(facility_id)

@router.post("", response_model=FacilityRead, status_code=status.HTTP_201_CREATED)
def create_facility(
    payload: FacilityCreate,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_CREATE"))]
):
    """
    Provision a new facility/branch. 
    Enforces subscription-based branch limits.
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
    Update basic or operational details of an existing facility.
    """
    return service.update_facility(facility_id, payload)

@router.delete("/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility(
    facility_id: int,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_DELETE"))]
):
    """
    Remove a facility record.
    """
    service.delete_facility(facility_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- FACILITY NETWORK ROUTES ---

@router.get("/networks/all", response_model=List[FacilityNetworkRead])
def list_networks(
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_READ"))]
):
    """
    Retrieve a list of all hospital networks/chains.
    """
    return service.list_networks()

@router.post("/networks/create", response_model=FacilityNetworkRead, status_code=status.HTTP_201_CREATED)
def create_network(
    payload: FacilityNetworkCreate,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_CREATE"))]
):
    """
    Define a new hospital network group.
    """
    return service.create_network(payload)

@router.put("/networks/{network_id}", response_model=FacilityNetworkRead)
def update_network(
    network_id: int,
    payload: FacilityNetworkUpdate,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_UPDATE"))]
):
    """
    Modify an existing network's profile.
    """
    return service.update_network(network_id, payload)

@router.delete("/networks/{network_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_network(
    network_id: int,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_DELETE"))]
):
    """
    Delete a hospital network profile.
    """
    service.delete_network(network_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- FACILITY SERVICE AREA ROUTES ---

@router.get("/service-areas/all", response_model=List[FacilityServiceAreaRead])
def list_service_areas(
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_READ"))],
    facility_id: Optional[int] = Query(None, description="Filter service areas by facility ID")
):
    """
    List catchment areas for one or all facilities.
    """
    return service.list_service_areas(facility_id)

@router.post("/service-areas/create", response_model=FacilityServiceAreaRead, status_code=status.HTTP_201_CREATED)
def create_service_area(
    payload: FacilityServiceAreaCreate,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_CREATE"))]
):
    """
    Register a new service area for a facility.
    """
    return service.create_service_area(payload)

@router.put("/service-areas/{area_id}", response_model=FacilityServiceAreaRead)
def update_service_area(
    area_id: int,
    payload: FacilityServiceAreaUpdate,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_UPDATE"))]
):
    """
    Update service area metadata or notes.
    """
    return service.update_service_area(area_id, payload)

@router.delete("/service-areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_area(
    area_id: int,
    service: Annotated[FacilityService, Depends(get_facility_service)],
    _: Annotated[bool, Depends(require_permission("FACILITY_DELETE"))]
):
    """
    Delete a specific service area record.
    """
    service.delete_service_area(area_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
