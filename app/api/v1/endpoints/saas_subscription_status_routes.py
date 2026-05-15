# app/api/v1/endpoints/saas_subscription_status_routes.py
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.multitenancy import get_current_tenant_id
from app.core.exceptions import ForbiddenError
from app.dependencies.subscription import get_subscription_service
from app.services.subscription_service import SubscriptionService
from app.schemas.subscription_schemas import SubscriptionStatusSchema
from app.models.all_models import TenantSubscription, SubscriptionPlan

router = APIRouter(prefix="/saas", tags=["SaaS - Subscription Status"])

@router.get(
    "/subscription-status",
    response_model=SubscriptionStatusSchema,
    summary="Get the current subscription status and enabled features for the tenant",
)
def get_subscription_status(
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[Session, Depends(get_master_db)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)]
):
    """
    Returns the current subscription plan details and a list of all enabled 
    features (computed from plan defaults + tenant overrides).
    Used by the frontend to conditionally render gated features.
    """
    if not tenant_id:
        raise ForbiddenError(message="Tenant context is required.")

    # 1. Fetch active subscription
    from app.core.enums import SubscriptionStatus
    sub = db.query(TenantSubscription).filter(
        TenantSubscription.tenant_id == tenant_id,
        TenantSubscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING])
    ).first()

    if not sub or not sub.plan:
        raise ForbiddenError(message="No active subscription found for this tenant.")

    plan = sub.plan
    
    # 2. Compute enabled features
    feature_flags = [
        "clinical", "inpatient", "laboratory", "pharmacy", "inventory",
        "billing", "reporting", "appointments", "patient_portal",
        "insurance", "radiology", "surgical", "hr", "dietary",
        "ambulance", "compliance"
    ]
    
    enabled_features = []
    for feature in feature_flags:
        if service.check_feature_access(tenant_id, feature):
            enabled_features.append(feature)

    return SubscriptionStatusSchema(
        tenant_id=tenant_id,
        plan_name=plan.name,
        plan_code=plan.code,
        subscription_status=sub.status,
        expires_at=sub.end_date,
        enabled_features=enabled_features,
        max_users=plan.max_users,
        max_facilities=plan.max_facilities
    )
