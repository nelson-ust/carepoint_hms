# app/services/saas_auth_service.py
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.enums import TwoFactorPurpose, TwoFactorType, UserStatus
from app.core.exceptions import BadRequestError, NotFoundError, UnauthorizedError, ValidationError
from app.core.security import (
    create_access_token,
    create_otp_challenge_payload,
    create_refresh_token,
    create_reset_token,
    get_password_hash,
    validate_password_strength,
    verify_two_factor_code,
    verify_user_password,
)
from app.models.all_models import SaaSAdmin, SaaSAdminSession, SaaSAdminTwoFactorChallenge, Tenant
from app.schemas.saas_auth_schemas import SaaSAdminLoginSchema
from app.schemas.auth_schemas import (
    ForgotPasswordSchema, 
    ResetPasswordSchema, 
    OTPResendSchema, 
    OTPVerifySchema,
    ChangePasswordSchema
)

try:
    from app.utils.email_utils import send_email
except Exception:
    send_email = None


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
            "user": admin,
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

    def forgot_password(self, payload: ForgotPasswordSchema) -> dict[str, Any]:
        """
        Start password reset flow for SaaS Admin.
        """
        admin = self.db.query(SaaSAdmin).filter(SaaSAdmin.email == payload.identifier.lower().strip()).first()
        if not admin:
            return {
                "success": True,
                "message": "If the account exists, password reset instructions have been sent.",
            }

        challenge = self._create_and_send_otp_challenge(
            admin=admin,
            purpose=TwoFactorPurpose.PASSWORD_RESET,
        )
        self.db.commit()

        return {
            "success": True,
            "message": "If the account exists, password reset instructions have been sent.",
            "challenge_reference": str(challenge.id),
            "delivery_method": str(challenge.challenge_type),
        }

    def reset_password(self, payload: ResetPasswordSchema) -> dict[str, Any]:
        """
        Complete password reset for SaaS Admin using a reset token.
        """
        from app.core.security import decode_token, validate_token_type
        try:
            # We expect a 'reset' type token
            token_payload = validate_token_type(payload.reset_token, "reset")
            admin_id = token_payload.get("sub")
            if not admin_id or not token_payload.get("is_saas_admin"):
                 raise BadRequestError(message="Invalid SaaS reset token.")
            
            admin = self.db.query(SaaSAdmin).filter(SaaSAdmin.id == int(admin_id)).first()
        except Exception as exc:
             raise BadRequestError(message=f"Invalid or expired reset token: {str(exc)}")

        if not admin:
            raise NotFoundError(message="SaaS Admin not found.")

        validate_password_strength(payload.new_password)
        
        admin.password_hash = get_password_hash(payload.new_password)
        self.db.add(admin)
        
        # Revoke all admin sessions
        self.db.query(SaaSAdminSession).filter(SaaSAdminSession.saas_admin_id == admin.id).update({"is_revoked": True})
        
        # Mark all reset challenges as verified for this user
        self.db.query(SaaSAdminTwoFactorChallenge).filter(
            SaaSAdminTwoFactorChallenge.saas_admin_id == admin.id,
            SaaSAdminTwoFactorChallenge.purpose == TwoFactorPurpose.PASSWORD_RESET
        ).update({"is_verified": True, "verified_at": datetime.now(timezone.utc)})

        self.db.commit()

        return {
            "success": True,
            "message": "Password reset successful.",
        }

    def change_password(self, admin_id: int, payload: ChangePasswordSchema) -> dict[str, Any]:
        """
        Change password for an authenticated SaaS Admin.
        """
        admin = self.db.query(SaaSAdmin).filter(SaaSAdmin.id == admin_id).first()
        if not admin:
            raise NotFoundError(message="SaaS Admin not found.")

        if not verify_user_password(payload.current_password, admin.password_hash):
            raise UnauthorizedError(message="Incorrect current password.")

        validate_password_strength(payload.new_password)
        
        admin.password_hash = get_password_hash(payload.new_password)
        self.db.add(admin)
        self.db.commit()

        return {
            "success": True,
            "message": "Password changed successfully.",
        }

    def resend_otp(self, payload: OTPResendSchema) -> dict[str, Any]:
        """
        Resend OTP for SaaS Admin.
        """
        admin = self.db.query(SaaSAdmin).filter(
            (SaaSAdmin.email == payload.identifier.lower().strip()) if payload.identifier else (SaaSAdmin.id == payload.user_id)
        ).first()

        if not admin:
            # For security, don't reveal if user exists
            return {
                "success": True,
                "message": "If the account exists, a new verification code has been sent.",
            }

        purpose_str = payload.purpose or "LOGIN"
        purpose = TwoFactorPurpose(purpose_str)

        challenge = self._create_and_send_otp_challenge(
            admin=admin,
            purpose=purpose,
        )
        self.db.commit()

        return {
            "success": True,
            "message": "If the account exists, a new verification code has been sent.",
            "challenge_reference": str(challenge.id),
            "delivery_method": str(challenge.challenge_type),
        }

    def verify_otp(self, payload: OTPVerifySchema) -> dict[str, Any]:
        """
        Verify an OTP for a SaaS Admin.
        """
        # Resolve challenge
        challenge = None
        if payload.challenge_reference:
            challenge = self.db.query(SaaSAdminTwoFactorChallenge).filter(
                SaaSAdminTwoFactorChallenge.id == int(payload.challenge_reference)
            ).first()
        
        if not challenge and payload.identifier:
            # Try latest open challenge for this admin
            admin = self.db.query(SaaSAdmin).filter(SaaSAdmin.email == payload.identifier.lower().strip()).first()
            if admin:
                challenge = self.db.query(SaaSAdminTwoFactorChallenge).filter(
                    SaaSAdminTwoFactorChallenge.saas_admin_id == admin.id,
                    SaaSAdminTwoFactorChallenge.is_verified == False,
                    SaaSAdminTwoFactorChallenge.purpose == payload.purpose
                ).order_by(SaaSAdminTwoFactorChallenge.date_created.desc()).first()

        if not challenge:
            raise NotFoundError(message="Challenge not found.")

        # Verify OTP
        verify_two_factor_code(
            plain_code=payload.otp_code,
            stored_code_hash=challenge.code_hash,
            expires_at=challenge.expires_at,
            attempt_count=challenge.attempt_count,
            max_attempts=challenge.max_attempts,
        )

        # Mark as verified
        challenge.is_verified = True
        challenge.verified_at = datetime.now(timezone.utc)
        self.db.add(challenge)
        
        admin = challenge.saas_admin
        
        # If purpose was password reset, issue a reset token
        tokens = None
        if str(challenge.purpose) == str(TwoFactorPurpose.PASSWORD_RESET):
            reset_token = create_reset_token(
                subject=str(admin.id),
                extra_claims={"is_saas_admin": True}
            )
            tokens = {
                "reset_token": reset_token,
                "token_type": "bearer"
            }

        self.db.commit()

        return {
            "success": True,
            "message": "Verification successful.",
            "verified": True,
            "user": admin,
            "tokens": tokens,
        }

    def _create_and_send_otp_challenge(
        self,
        *,
        admin: SaaSAdmin,
        purpose: TwoFactorPurpose,
        challenge_type: Optional[TwoFactorType] = None,
    ) -> SaaSAdminTwoFactorChallenge:
        """
        Create challenge record in Master DB and dispatch OTP.
        """
        resolved_type = challenge_type or TwoFactorType.EMAIL
        destination = admin.email

        payload = create_otp_challenge_payload(
            user_id=admin.id,
            challenge_type=str(resolved_type),
            purpose=str(purpose),
            destination=destination,
        )

        challenge = SaaSAdminTwoFactorChallenge(
            saas_admin_id=admin.id,
            challenge_type=resolved_type,
            purpose=purpose,
            destination=destination,
            code_hash=payload["code_hash"],
            expires_at=payload["expires_at"],
            max_attempts=payload["max_attempts"],
        )
        self.db.add(challenge)
        self.db.flush()

        # Send Styled Email
        try:
            from app.utils.email_utils import send_otp_email
            send_otp_email(destination, payload['plain_code'], purpose.value)
        except Exception:
            # Fallback to plain send_email if styled fails
            if send_email:
                message = f"Your verification code is: {payload['plain_code']}."
                send_email(
                    subject="Carepoint HMS Verification",
                    recipients=[destination],
                    body_text=message,
                )

        return challenge
