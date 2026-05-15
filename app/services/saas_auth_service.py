# app/services/saas_auth_service.py
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.cryptography import decrypt_string, encrypt_string
from app.core.enums import TwoFactorPurpose, TwoFactorType, UserStatus
from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
    TokenError,
    UnauthorizedError,
    ValidationError,
)
from app.core.security import (
    build_password_reset_link,
    create_access_token,
    create_otp_challenge_payload,
    create_refresh_token,
    create_reset_token,
    generate_password_reset_token,
    get_password_hash,
    validate_password_strength,
    validate_token_type,
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
        Start the password reset flow for a SaaS Admin (Master DB).

        Generates a short, opaque, single-use reset token. The token is
        encrypted and stored on the admin's ``password_reset_token`` column,
        with ``password_reset_token_expires_at`` bounding its validity. The
        raw token is emailed inside a reset link. The response is always the
        same masked message so the endpoint does not reveal account existence.
        """
        masked_response = {
            "success": True,
            "message": "If the account exists, password reset instructions have been sent.",
        }

        admin = self.db.query(SaaSAdmin).filter(
            SaaSAdmin.email == payload.identifier.lower().strip()
        ).first()
        if not admin or not admin.email:
            return masked_response

        expires_minutes = int(getattr(settings, "PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", 30))

        raw_token = generate_password_reset_token()
        admin.password_reset_token = encrypt_string(raw_token)
        admin.password_reset_token_expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        )
        self.db.add(admin)
        self.db.commit()

        # SaaS admins are not tenant-scoped, so no tenant_code on the link.
        reset_link = build_password_reset_link(raw_token)
        self._send_password_reset_link(
            email=admin.email,
            reset_link=reset_link,
            expires_minutes=expires_minutes,
        )

        return masked_response

    def _match_admin_by_reset_token(self, raw_token: str) -> Optional[SaaSAdmin]:
        """
        Find the SaaS Admin whose stored (encrypted) reset token decrypts to
        ``raw_token``.

        The token is encrypted at rest with a non-deterministic cipher, so it
        cannot be matched with a SQL equality filter — each candidate is
        decrypted and compared in constant time.
        """
        if not raw_token:
            return None
        candidates = (
            self.db.query(SaaSAdmin)
            .filter(SaaSAdmin.password_reset_token.isnot(None))
            .all()
        )
        for candidate in candidates:
            stored = candidate.password_reset_token
            if not stored:
                continue
            try:
                if hmac.compare_digest(decrypt_string(stored), raw_token):
                    return candidate
            except Exception:
                continue
        return None

    def reset_password(self, payload: ResetPasswordSchema) -> dict[str, Any]:
        """
        Complete a SaaS Admin password reset using a reset token.

        Accepted tokens
        ---------------
        - Primary: a short opaque token issued by ``forgot_password``. The
          supplied token is matched against the decrypted value of each
          pending ``password_reset_token`` (must not be expired). It is
          single-use because it is cleared once consumed.
        - Fallback: a legacy JWT ``reset`` token carrying the
          ``is_saas_admin`` claim, kept for backward compatibility.
        """
        raw_token = payload.reset_token

        # Primary: opaque token stored (encrypted) on the admin record.
        admin = self._match_admin_by_reset_token(raw_token)
        used_model_token = admin is not None

        if used_model_token:
            expires_at = admin.password_reset_token_expires_at
            if expires_at is None:
                raise BadRequestError(message="Invalid or expired reset token.")
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= expires_at:
                raise BadRequestError(
                    message="This reset link has expired. Please request a new one.",
                )
        else:
            # Backward-compatible fallback: legacy JWT reset token.
            try:
                token_payload = validate_token_type(raw_token, "reset")
            except TokenError as exc:
                raise BadRequestError(message="Invalid or expired reset token.") from exc

            admin_id = token_payload.get("sub")
            if not admin_id or not token_payload.get("is_saas_admin"):
                raise BadRequestError(message="Invalid SaaS reset token.")

            admin = self.db.query(SaaSAdmin).filter(SaaSAdmin.id == int(admin_id)).first()

        if not admin:
            raise NotFoundError(message="SaaS Admin not found.")

        validate_password_strength(payload.new_password)

        admin.password_hash = get_password_hash(payload.new_password)
        # Clear the reset token so it cannot be reused (single-use).
        admin.password_reset_token = None
        admin.password_reset_token_expires_at = None
        self.db.add(admin)

        # Revoke all admin sessions.
        self.db.query(SaaSAdminSession).filter(
            SaaSAdminSession.saas_admin_id == admin.id
        ).update({"is_revoked": True})

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

    def _send_password_reset_link(
        self,
        *,
        email: str,
        reset_link: str,
        expires_minutes: int,
    ) -> bool:
        """
        Deliver a SaaS Admin password reset link by email.

        SaaS admins are not tenant-scoped, so delivery goes through the
        platform SMTP transport only. Delivery failures are caught (the
        forgot-password endpoint must never reveal whether an account exists)
        but every outcome is logged so an operator can see *why* a reset email
        did not arrive.

        Returns:
            bool: True if the message was accepted by the transport.
        """
        from app.core.logger import get_logger
        from app.utils.email_utils import build_password_reset_email_content, send_email

        logger = get_logger(__name__)
        content = build_password_reset_email_content(reset_link, expires_minutes)

        try:
            result = send_email(
                subject=content["subject"],
                recipients=[email],
                body_text=content["body_text"],
                body_html=content["body_html"],
            )
            if isinstance(result, dict) and result.get("success"):
                logger.info("SaaS password reset link emailed to %s via platform SMTP.", email)
                return True

            detail = (
                result.get("error") or result.get("message")
                if isinstance(result, dict) else result
            )
            logger.error(
                "SaaS password reset email to %s failed via platform SMTP: %s", email, detail
            )
        except Exception as exc:
            logger.error(
                "SaaS password reset email to %s could not be sent — the platform SMTP "
                "transport is not configured (enable EMAILS_ENABLED + SMTP_* settings). "
                "Underlying error: %s",
                email,
                exc,
            )

        return False

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
