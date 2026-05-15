# app/services/subscription_service.py
from typing import Optional
from sqlalchemy.orm import Session
from app.models.all_models import Tenant, SubscriptionPlan, TenantSubscription
from app.core.enums import SubscriptionStatus
from app.core.exceptions import ForbiddenError
from datetime import datetime

class SubscriptionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_plan(self, tenant_id: int) -> Optional[SubscriptionPlan]:
        """
        Retrieve the currently active subscription plan for a tenant.
        Includes plans in ACTIVE or TRIALING status.
        """
        subscription = self.db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == tenant_id,
            TenantSubscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]),
            TenantSubscription.is_active == True
        ).first()
        
        return subscription.plan if subscription else None

    def check_feature_access(self, tenant_id: int, feature_name: str) -> bool:
        """
        Check if a tenant has access to a specific feature based on their plan.
        
        Effective access is computed as:
        plan.has_<feature> AND (TenantModuleAccess.is_enabled if exists else True)
        """
        plan = self.get_active_plan(tenant_id)
        if not plan:
            return False
            
        # 1. Check the base plan default
        plan_default = getattr(plan, f"has_{feature_name}", False)
        if not plan_default:
            return False

        # 2. Check for per-tenant overrides (Master DB)
        from app.models.all_models import TenantModuleAccess
        override = self.db.query(TenantModuleAccess).filter(
            TenantModuleAccess.tenant_id == tenant_id,
            TenantModuleAccess.module_code == feature_name,
            TenantModuleAccess.is_deleted.is_(False)
        ).first()

        if override is not None:
            return bool(override.is_enabled)
            
        return True

    def require_feature(
        self, 
        tenant_id: int, 
        feature_name: str,
        user_id: Optional[int] = None,
        path: str = "unknown",
        method: str = "unknown",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """
        Raise ForbiddenError if the tenant doesn't have access to the feature.
        Logs the attempt if it is denied.
        """
        has_access = self.check_feature_access(tenant_id, feature_name)
        
        if not has_access:
            # Log the denial
            self.log_access_attempt(
                tenant_id=tenant_id,
                feature_code=feature_name,
                user_id=user_id,
                path=path,
                method=method,
                ip_address=ip_address,
                user_agent=user_agent,
                is_denied=True,
                reason="Feature flag disabled or plan restriction"
            )
            
            raise ForbiddenError(
                message=f"Access Denied: The '{feature_name}' module is not enabled for your tenant."
            )

    def log_access_attempt(
        self,
        tenant_id: int,
        feature_code: str,
        user_id: Optional[int] = None,
        path: str = "unknown",
        method: str = "unknown",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        is_denied: bool = False,
        reason: Optional[str] = None
    ):
        """
        Record a feature access attempt in the Master DB audit log.
        """
        from app.models.all_models import FeatureAccessAuditLog
        
        audit_log = FeatureAccessAuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            feature_code=feature_code,
            path=path,
            method=method,
            ip_address=ip_address,
            user_agent=user_agent,
            is_denied=is_denied,
            reason=reason,
            date_created=datetime.utcnow(),
            date_updated=datetime.utcnow()
        )
        self.db.add(audit_log)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            # Silently fail logging to avoid breaking the request
            pass


    def check_user_limit(self, tenant_id: int, current_user_count: int):
        plan = self.get_active_plan(tenant_id)
        if plan and current_user_count >= plan.max_users:
            raise ForbiddenError(message="User limit reached for your current subscription plan.")

    def check_facility_limit(self, tenant_id: int, current_facility_count: int):
        plan = self.get_active_plan(tenant_id)
        if plan and current_facility_count >= plan.max_facilities:
            raise ForbiddenError(message="Facility limit reached for your current subscription plan.")
