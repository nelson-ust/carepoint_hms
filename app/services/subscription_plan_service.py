# app/services/subscription_plan_service.py
from typing import List
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import SubscriptionPlan
from app.schemas.subscription_schemas import SubscriptionPlanCreateSchema, SubscriptionPlanUpdateSchema

# Every module feature flag on a plan. The Trial plan always has them all on.
PLAN_FEATURE_FLAGS = (
    "has_clinical", "has_inpatient", "has_laboratory", "has_pharmacy",
    "has_inventory", "has_billing", "has_reporting", "has_appointments",
    "has_patient_portal", "has_insurance", "has_radiology", "has_surgical",
    "has_hr", "has_dietary", "has_ambulance", "has_mortuary", "has_compliance",
    "has_dental", "has_eye", "has_ortho",
)


def _enforce_trial_all_modules(plan) -> None:
    """The Trial plan is a full-feature trial — force every module on."""
    if (getattr(plan, "code", "") or "").upper() == "TRIAL":
        for flag in PLAN_FEATURE_FLAGS:
            setattr(plan, flag, True)

class SubscriptionPlanService:
    def __init__(self, db: Session):
        self.db = db

    def list_plans(self, include_inactive: bool = False) -> List[SubscriptionPlan]:
        query = self.db.query(SubscriptionPlan)
        if not include_inactive:
            query = query.filter(SubscriptionPlan.is_active == True)
        return query.order_by(SubscriptionPlan.price.asc()).all()

    def get_plan(self, plan_id: int) -> SubscriptionPlan:
        plan = self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise NotFoundError(message="Subscription plan not found.")
        return plan

    def create_plan(self, payload: SubscriptionPlanCreateSchema) -> SubscriptionPlan:
        existing = self.db.query(SubscriptionPlan).filter(
            (SubscriptionPlan.code == payload.code) | (SubscriptionPlan.name == payload.name)
        ).first()
        
        if existing:
            raise BadRequestError(message="A plan with this name or code already exists.")
            
        plan = SubscriptionPlan(**payload.model_dump())
        _enforce_trial_all_modules(plan)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def update_plan(self, plan_id: int, payload: SubscriptionPlanUpdateSchema) -> SubscriptionPlan:
        plan = self.get_plan(plan_id)
        
        update_data = payload.model_dump(exclude_unset=True)
        
        if "name" in update_data:
            existing = self.db.query(SubscriptionPlan).filter(
                SubscriptionPlan.name == update_data["name"],
                SubscriptionPlan.id != plan_id
            ).first()
            if existing:
                raise BadRequestError(message="A plan with this name already exists.")
                
        for key, value in update_data.items():
            setattr(plan, key, value)

        _enforce_trial_all_modules(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan
