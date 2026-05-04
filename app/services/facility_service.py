from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.all_models import Facility, TenantSubscription, SubscriptionPlan
from app.schemas.facility_schemas import FacilityCreate, FacilityUpdate
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.multitenancy import get_current_tenant_id
from app.core.database import get_master_db_context
from app.core.enums import SubscriptionStatus

class FacilityService:
    def __init__(self, db: Session):
        self.db = db

    def list_facilities(self) -> List[Facility]:
        return self.db.query(Facility).all()

    def get_facility(self, facility_id: int) -> Facility:
        facility = self.db.query(Facility).filter(Facility.id == facility_id).first()
        if not facility:
            raise NotFoundError(message="Facility not found.")
        return facility

    def create_facility(self, payload: FacilityCreate) -> Facility:
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

        # 2. Check for unique code/name
        if self.db.query(Facility).filter(Facility.code == payload.code).first():
            raise BadRequestError(message=f"Facility with code '{payload.code}' already exists.")

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
        self.db.add(facility)
        self.db.commit()
        self.db.refresh(facility)
        return facility

    def update_facility(self, facility_id: int, payload: FacilityUpdate) -> Facility:
        facility = self.get_facility(facility_id)
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(facility, key, value)
        
        self.db.commit()
        self.db.refresh(facility)
        return facility

    def delete_facility(self, facility_id: int) -> None:
        facility = self.get_facility(facility_id)
        # Check if there are active dependencies if needed
        self.db.delete(facility)
        self.db.commit()
