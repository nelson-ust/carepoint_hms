from typing import List, Optional, Type
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select

from app.models.all_models import Facility, FacilityNetwork, FacilityServiceArea

class FacilityRepository:
    """
    Repository layer for managing Facility, FacilityNetwork, and FacilityServiceArea entities.
    Handles direct database interactions and encapsulation of SQLAlchemy queries.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the repository with a database session.
        """
        self.db = db

    # --- FACILITY METHODS ---

    def list_facilities(self) -> List[Facility]:
        """
        Retrieve all facilities for the current tenant.
        """
        return (
            self.db.query(Facility)
            .options(
                joinedload(Facility.network),
                selectinload(Facility.service_areas)
            )
            .all()
        )

    def get_facility(self, facility_id: int) -> Optional[Facility]:
        """
        Retrieve a specific facility by its ID.
        """
        return (
            self.db.query(Facility)
            .options(
                joinedload(Facility.network),
                selectinload(Facility.service_areas)
            )
            .filter(Facility.id == facility_id)
            .first()
        )

    def get_facility_by_code(self, code: str) -> Optional[Facility]:
        """
        Retrieve a facility by its unique code.
        """
        return self.db.query(Facility).filter(Facility.code == code).first()

    def create_facility(self, facility: Facility) -> Facility:
        """
        Persist a new facility to the database.
        """
        self.db.add(facility)
        self.db.commit()
        self.db.refresh(facility)
        return facility

    def update_facility(self) -> None:
        """
        Commit changes made to a facility object.
        """
        self.db.commit()

    def delete_facility(self, facility: Facility) -> None:
        """
        Remove a facility from the database.
        """
        self.db.delete(facility)
        self.db.commit()


    # --- FACILITY NETWORK METHODS ---

    def list_networks(self) -> List[FacilityNetwork]:
        """
        Retrieve all hospital networks.
        """
        return self.db.query(FacilityNetwork).all()

    def get_network(self, network_id: int) -> Optional[FacilityNetwork]:
        """
        Retrieve a specific network by its ID.
        """
        return self.db.query(FacilityNetwork).filter(FacilityNetwork.id == network_id).first()

    def get_network_by_code(self, code: str) -> Optional[FacilityNetwork]:
        """
        Retrieve a network by its unique code.
        """
        return self.db.query(FacilityNetwork).filter(FacilityNetwork.code == code).first()

    def create_network(self, network: FacilityNetwork) -> FacilityNetwork:
        """
        Persist a new hospital network.
        """
        self.db.add(network)
        self.db.commit()
        self.db.refresh(network)
        return network

    def update_network(self) -> None:
        """
        Commit changes to a network object.
        """
        self.db.commit()

    def delete_network(self, network: FacilityNetwork) -> None:
        """
        Remove a hospital network.
        """
        self.db.delete(network)
        self.db.commit()


    # --- FACILITY SERVICE AREA METHODS ---

    def list_service_areas(self, facility_id: Optional[int] = None) -> List[FacilityServiceArea]:
        """
        Retrieve all service areas, optionally filtered by facility.
        """
        query = self.db.query(FacilityServiceArea)
        if facility_id:
            query = query.filter(FacilityServiceArea.facility_id == facility_id)
        return query.all()

    def get_service_area(self, area_id: int) -> Optional[FacilityServiceArea]:
        """
        Retrieve a specific service area by ID.
        """
        return self.db.query(FacilityServiceArea).filter(FacilityServiceArea.id == area_id).first()

    def create_service_area(self, service_area: FacilityServiceArea) -> FacilityServiceArea:
        """
        Persist a new service area record.
        """
        self.db.add(service_area)
        self.db.commit()
        self.db.refresh(service_area)
        return service_area

    def update_service_area(self) -> None:
        """
        Commit changes to a service area object.
        """
        self.db.commit()

    def delete_service_area(self, service_area: FacilityServiceArea) -> None:
        """
        Remove a service area record.
        """
        self.db.delete(service_area)
        self.db.commit()
