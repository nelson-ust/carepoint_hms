# app/services/subscription_plan_service.py
from typing import List
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import SubscriptionPlan
from app.schemas.subscription_schemas import SubscriptionPlanCreateSchema, SubscriptionPlanUpdateSchema

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
            
        self.db.commit()
        self.db.refresh(plan)
        return plan
