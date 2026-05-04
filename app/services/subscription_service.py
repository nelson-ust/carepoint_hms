# app/services/subscription_service.py
from typing import Optional
from sqlalchemy.orm import Session
from app.models.all_models import Tenant, SubscriptionPlan, TenantSubscription
from app.core.enums import SubscriptionStatus
from app.core.exceptions import ForbiddenError

class SubscriptionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_plan(self, tenant_id: int) -> Optional[SubscriptionPlan]:
        """
        Retrieve the currently active subscription plan for a tenant.
        """
        subscription = self.db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == tenant_id,
            TenantSubscription.status == SubscriptionStatus.ACTIVE,
            TenantSubscription.is_active == True
        ).first()
        
        return subscription.plan if subscription else None

    def check_feature_access(self, tenant_id: int, feature_name: str) -> bool:
        """
        Check if a tenant has access to a specific feature based on their plan.
        """
        plan = self.get_active_plan(tenant_id)
        if not plan:
            # Maybe fallback to a default free plan?
            return False
            
        return getattr(plan, f"has_{feature_name}", False)

    def require_feature(self, tenant_id: int, feature_name: str):
        """
        Raise ForbiddenError if the tenant doesn't have access to the feature.
        """
        if not self.check_feature_access(tenant_id, feature_name):
            raise ForbiddenError(
                message=f"Feature '{feature_name}' is not included in your current subscription plan."
            )

    def check_user_limit(self, tenant_id: int, current_user_count: int):
        plan = self.get_active_plan(tenant_id)
        if plan and current_user_count >= plan.max_users:
            raise ForbiddenError(message="User limit reached for your current subscription plan.")

    def check_facility_limit(self, tenant_id: int, current_facility_count: int):
        plan = self.get_active_plan(tenant_id)
        if plan and current_facility_count >= plan.max_facilities:
            raise ForbiddenError(message="Facility limit reached for your current subscription plan.")
