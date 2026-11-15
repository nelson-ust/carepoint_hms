from fastapi import Depends, Request
from sqlalchemy.orm import Session
from app.core.database import get_master_db
from app.core.multitenancy import get_current_tenant_id
from app.services.subscription_service import SubscriptionService
from app.dependencies.auth import get_optional_token_payload
from app.core.exceptions import LicenseError
from typing import Annotated, Optional

def get_subscription_service(db: Annotated[Session, Depends(get_master_db)]) -> SubscriptionService:
    return SubscriptionService(db)

def require_plan_feature(feature_name: str):
    def _dependency(
        request: Request,
        tenant_id: Annotated[int, Depends(get_current_tenant_id)],
        service: Annotated[SubscriptionService, Depends(get_subscription_service)],
        payload: Annotated[Optional[dict], Depends(get_optional_token_payload)] = None
    ):
        # Skip feature gate for synthetic/test tenants
        if not tenant_id:
            return

        # Offline entitlement gate (edge installs): a lapsed or tampered signed
        # lease blocks non-care features. Clinical/emergency features are never
        # blocked. Fails open on any internal error so care is never broken.
        try:
            from app.core.config import settings as _settings
            from app.core import tenant_mode
            if tenant_mode.enforce_lease() and getattr(_settings, "LICENSE_OFFLINE_ENFORCED", True):
                from app.services import entitlement_service
                if entitlement_service.license_gate(feature_name) == "block":
                    raise LicenseError()
        except LicenseError:
            raise
        except Exception:
            pass
            
        # Extract user_id from token payload if available
        user_id = payload.get("sub") if payload else None
        if user_id:
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                user_id = None

        service.require_feature(
            tenant_id=tenant_id,
            feature_name=feature_name,
            user_id=user_id,
            path=str(request.url.path),
            method=request.method,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
    return _dependency

