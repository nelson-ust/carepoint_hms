# app/dependencies/subscription.py
from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import get_master_db
from app.core.multitenancy import get_current_tenant_id
from app.services.subscription_service import SubscriptionService

def get_subscription_service(db: Annotated[Session, Depends(get_master_db)]) -> SubscriptionService:
    return SubscriptionService(db)

def require_plan_feature(feature_name: str):
    def _dependency(
        tenant_id: Annotated[int, Depends(get_current_tenant_id)],
        service: Annotated[SubscriptionService, Depends(get_subscription_service)]
    ):
        # Skip feature gate for synthetic/test tenants
        if not tenant_id:
            return
        service.require_feature(tenant_id, feature_name)
    return _dependency

