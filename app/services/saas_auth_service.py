# app/services/saas_auth_service.py
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_user_password,
)
from app.models.all_models import SaaSAdmin, SaaSAdminSession, Tenant
from app.schemas.saas_auth_schemas import SaaSAdminLoginSchema


class SaaSAuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def login(
        self,
        payload: SaaSAdminLoginSchema,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Authenticate a SaaS Admin against the Master Database.
        """
        now = datetime.now(timezone.utc)

        admin = self.db.query(SaaSAdmin).filter(SaaSAdmin.email == payload.email.lower().strip()).first()
        if not admin:
            raise UnauthorizedError(message="Invalid credentials.")

        if not admin.is_active:
            raise UnauthorizedError(message="Account is inactive.")

        if not verify_user_password(payload.password, admin.password_hash):
            raise UnauthorizedError(message="Invalid credentials.")

        # Build tokens
        # Note: SaaS Admins have no tenant_id and a specific 'SAAS_ADMIN' role representation.
        access_token, access_payload = create_access_token(
            subject=str(admin.id),
            role="SAAS_ADMIN",
            roles=["SAAS_ADMIN"],
            tenant_id=None,
            two_factor_verified=False,
            extra_claims={"is_saas_admin": True}
        )
        refresh_token, refresh_payload = create_refresh_token(
            subject=str(admin.id),
            role="SAAS_ADMIN",
            roles=["SAAS_ADMIN"],
            tenant_id=None,
        )

        # Create session
        session = SaaSAdminSession(
            saas_admin_id=admin.id,
            access_jti=access_payload["jti"],
            refresh_jti=refresh_payload["jti"],
            ip_address=ip_address,
            user_agent=user_agent,
            is_revoked=False,
            expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
        )
        self.db.add(session)
        self.db.commit()

        return {
            "success": True,
            "message": "SaaS Admin login successful.",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "admin_id": admin.id,
            "email": admin.email,
            "first_name": admin.first_name,
            "last_name": admin.last_name,
        }

    def impersonate_tenant(
        self,
        admin_id: int,
        tenant_code: str,
    ) -> dict[str, Any]:
        """
        Generate impersonation tokens for a SaaS Admin to access a specific tenant.
        """
        admin = self.db.query(SaaSAdmin).filter(SaaSAdmin.id == admin_id).first()
        if not admin or not admin.is_active:
            raise UnauthorizedError(message="Invalid or inactive SaaS Admin.")

        tenant = self.db.query(Tenant).filter(Tenant.code == tenant_code.lower().strip()).first()
        if not tenant:
            raise UnauthorizedError(message="Tenant not found.")

        # Give them TENANT_ADMIN role to have full access inside the tenant context
        access_token, access_payload = create_access_token(
            subject=str(admin.id),
            role="TENANT_ADMIN",
            roles=["TENANT_ADMIN"],
            tenant_id=tenant.id,
            two_factor_verified=False,
            extra_claims={"is_saas_admin": True, "is_impersonated": True}
        )
        refresh_token, _ = create_refresh_token(
            subject=str(admin.id),
            role="TENANT_ADMIN",
            roles=["TENANT_ADMIN"],
            tenant_id=tenant.id,
        )

        return {
            "success": True,
            "message": f"Successfully impersonated tenant {tenant_code}.",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "tenant_code": tenant.code,
            "tenant_name": tenant.name,
        }

