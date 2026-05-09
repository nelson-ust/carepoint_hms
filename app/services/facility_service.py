from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.all_models import (
    Facility, FacilityNetwork, FacilityServiceArea, 
    TenantSubscription, SubscriptionPlan
)
from app.schemas.facility_schemas import (
    FacilityCreate, FacilityUpdate,
    FacilityNetworkCreate, FacilityNetworkUpdate,
    FacilityServiceAreaCreate, FacilityServiceAreaUpdate
)
from app.repositories.facility_repository import FacilityRepository
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.multitenancy import get_current_tenant_id
from app.core.database import get_master_db_context
from app.core.enums import SubscriptionStatus

class FacilityService:
    """
    Service layer for managing hospital facilities, networks, and service areas.
    Implements business logic, validation, and coordinates with the repository layer.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the service with a repository instance.
        """
        self.db = db
        self.repo = FacilityRepository(db)

    # --- FACILITY BUSINESS LOGIC ---

    def list_facilities(self) -> List[Facility]:
        """
        Retrieve all facilities.
        """
        return self.repo.list_facilities()

    def get_facility(self, facility_id: int) -> Facility:
        """
        Get details of a specific facility. Raises NotFoundError if not found.
        """
        facility = self.repo.get_facility(facility_id)
        if not facility:
            raise NotFoundError(message="Facility not found.")
        return facility

    def create_facility(self, payload: FacilityCreate) -> Facility:
        """
        Create a new facility with subscription-quota validation.
        """
        # 1. Enforce max_facilities limit from subscription
        tenant_id = get_current_tenant_id()
        if tenant_id:
            with get_master_db_context() as master_db:
                sub = (
                    master_db.query(TenantSubscription)
                    .join(SubscriptionPlan)
                    .filter(
                        TenantSubscription.tenant_id == tenant_id,
                        TenantSubscription.status == SubscriptionStatus.ACTIVE
                    )
                    .first()
                )
                
                if not sub or not sub.plan:
                    raise BadRequestError(message="Active subscription required to manage branches.")
                
                current_count = self.db.query(func.count(Facility.id)).scalar() or 0
                if current_count >= sub.plan.max_facilities:
                    raise BadRequestError(
                        message=f"Facility limit reached. Your plan allows a maximum of {sub.plan.max_facilities} branches.",
                        detail={"max_facilities": sub.plan.max_facilities, "current_count": current_count}
                    )

        # 2. Check for unique code
        if self.repo.get_facility_by_code(payload.code):
            raise BadRequestError(message=f"Facility with code '{payload.code}' already exists.")

        # 3. Validate network if provided
        if payload.network_id:
            self.get_network(payload.network_id)

        facility = Facility(
            code=payload.code,
            name=payload.name,
            facility_type=payload.facility_type,
            status=payload.status,
            phone_number=payload.phone_number,
            email=payload.email,
            website=payload.website,
            address_line_1=payload.address_line_1,
            address_line_2=payload.address_line_2,
            city=payload.city,
            state=payload.state,
            country=payload.country,
            postal_code=payload.postal_code,
            timezone=payload.timezone,
            network_id=payload.network_id,
            parent_facility_id=payload.parent_facility_id
        )
        return self.repo.create_facility(facility)

    def update_facility(self, facility_id: int, payload: FacilityUpdate) -> Facility:
        """
        Update an existing facility's details.
        """
        facility = self.get_facility(facility_id)
        update_data = payload.model_dump(exclude_unset=True)
        
        for key, value in update_data.items():
            setattr(facility, key, value)
        
        self.repo.update_facility()
        self.db.refresh(facility)
        return facility

    def delete_facility(self, facility_id: int) -> None:
        """
        Remove a facility.
        """
        facility = self.get_facility(facility_id)
        self.repo.delete_facility(facility)


    # --- FACILITY NETWORK BUSINESS LOGIC ---

    def list_networks(self) -> List[FacilityNetwork]:
        """
        Retrieve all hospital networks.
        """
        return self.repo.list_networks()

    def get_network(self, network_id: int) -> FacilityNetwork:
        """
        Get a specific network. Raises NotFoundError if not found.
        """
        network = self.repo.get_network(network_id)
        if not network:
            raise NotFoundError(message="Hospital network not found.")
        return network

    def create_network(self, payload: FacilityNetworkCreate) -> FacilityNetwork:
        """
        Create a new hospital network.
        """
        if self.repo.get_network_by_code(payload.code):
            raise BadRequestError(message=f"Network with code '{payload.code}' already exists.")
            
        network = FacilityNetwork(
            name=payload.name,
            code=payload.code,
            description=payload.description,
            head_office_facility_id=payload.head_office_facility_id
        )
        return self.repo.create_network(network)

    def update_network(self, network_id: int, payload: FacilityNetworkUpdate) -> FacilityNetwork:
        """
        Update network details.
        """
        network = self.get_network(network_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(network, key, value)
        self.repo.update_network()
        self.db.refresh(network)
        return network

    def delete_network(self, network_id: int) -> None:
        """
        Delete a network.
        """
        network = self.get_network(network_id)
        self.repo.delete_network(network)


    # --- FACILITY SERVICE AREA BUSINESS LOGIC ---

    def list_service_areas(self, facility_id: Optional[int] = None) -> List[FacilityServiceArea]:
        """
        Retrieve service areas, optionally for a specific facility.
        """
        return self.repo.list_service_areas(facility_id)

    def get_service_area(self, area_id: int) -> FacilityServiceArea:
        """
        Get a specific service area.
        """
        area = self.repo.get_service_area(area_id)
        if not area:
            raise NotFoundError(message="Facility service area not found.")
        return area

    def create_service_area(self, payload: FacilityServiceAreaCreate) -> FacilityServiceArea:
        """
        Create a new catchment area for a facility.
        """
        # Ensure facility exists
        self.get_facility(payload.facility_id)
        
        area = FacilityServiceArea(
            facility_id=payload.facility_id,
            area_name=payload.area_name,
            region_code=payload.region_code,
            notes=payload.notes
        )
        return self.repo.create_service_area(area)

    def update_service_area(self, area_id: int, payload: FacilityServiceAreaUpdate) -> FacilityServiceArea:
        """
        Update service area details.
        """
        area = self.get_service_area(area_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(area, key, value)
        self.repo.update_service_area()
        self.db.refresh(area)
        return area

    def delete_service_area(self, area_id: int) -> None:
        """
        Delete a service area record.
        """
        area = self.get_service_area(area_id)
        self.repo.delete_service_area(area)
