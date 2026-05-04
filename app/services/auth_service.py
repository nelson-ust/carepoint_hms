from __future__ import annotations

"""
app.services.auth_service

Service layer for authentication, token issuance, password management,
OTP verification, email/phone verification, and optional two-factor
authentication for Carepoint HMS.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session
from app.core.multitenancy import get_current_tenant_id, get_current_tenant_code
from app.services.tenant_usage_service import TenantUsageService

from app.core.config import settings
from app.core.enums import TwoFactorPurpose, TwoFactorType, UserStatus
from app.core.exceptions import BadRequestError, NotFoundError, UnauthorizedError, ValidationError
from app.core.security import (
    assert_login_password,
    assert_user_is_active,
    build_login_result,
    build_post_2fa_access_token,
    create_otp_challenge_payload,
    decode_token,
    get_password_hash,
    validate_password_strength,
    validate_token_type,
    verify_two_factor_code,
    verify_user_password,
)
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth_schemas import (
    ChangePasswordSchema,
    EmailVerificationConfirmSchema,
    EmailVerificationRequestSchema,
    ForgotPasswordSchema,
    LoginSchema,
    OTPResendSchema,
    OTPVerifySchema,
    PhoneVerificationConfirmSchema,
    PhoneVerificationRequestSchema,
    RefreshTokenRequestSchema,
    ResetPasswordSchema,
    TwoFactorSetupSchema,
    TwoFactorVerifySchema,
)
from app.utils.security_event_util import record_security_event
from app.models.all_models import Patient

try:
    from app.utils.email_utils import send_email
except Exception:
    send_email = None

try:
    from app.utils.sms_util import send_sms, send_whatsapp_message
except Exception:
    send_sms = None
    send_whatsapp_message = None


class AuthService:
    """
    Service layer for auth and identity workflows.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AuthRepository(db)

    # ============================================================
    # LOGIN / REFRESH / LOGOUT
    # ============================================================

    def login(
        self,
        payload: LoginSchema,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Authenticate a user by username, email, or phone number.

        Flow
        ----
        - resolve user by identifier
        - ensure user is not currently locked out
        - ensure user status allows login
        - validate password (failure increments lockout counter)
        - if 2FA is enabled, create challenge and return pending-2FA response
        - else build tokens, persist UserSession, audit, return success
        """
        now = datetime.now(timezone.utc)
        
        # 0. Handle Tenant Auto-Discovery if context is missing
        if get_current_tenant_id() is None:
            self._discover_and_set_tenant(payload.identifier)

        user = self.repository.get_user_with_roles_by_identifier(payload.identifier)

        if not user:
            record_security_event(
                self.db,
                event_type="LOGIN_FAILURE_UNKNOWN_USER",
                severity="WARNING",
                event_detail=f"Login attempted with unknown identifier '{payload.identifier}'.",
                ip_address=ip_address,
                user_agent=user_agent,
                event_metadata={"identifier": payload.identifier},
            )
            self.db.commit()
            raise UnauthorizedError(message="Invalid credentials.")

        # Check current lockout window before status validation so locked
        # users see a clear message even if status was set to LOCKED.
        if self._is_user_locked(user, now=now):
            self._log_security_event_for_user(
                user,
                event_type="LOGIN_BLOCKED_LOCKED",
                severity="WARNING",
                detail=f"Login blocked: user {user.username} is locked until {user.locked_until}.",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"locked_until": user.locked_until.isoformat() if user.locked_until else None},
            )
            self.db.commit()
            raise UnauthorizedError(
                message="Account is locked due to repeated failed login attempts. Please try again later.",
                detail={
                    "locked_until": user.locked_until.isoformat() if user.locked_until else None,
                },
            )

        # Status check (ACTIVE-only access).
        try:
            assert_user_is_active(status=str(user.status))
        except UnauthorizedError:
            self._log_security_event_for_user(
                user,
                event_type="LOGIN_BLOCKED_INACTIVE",
                severity="WARNING",
                detail=f"Login blocked for {user.username}: status={user.status}.",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"status": str(user.status)},
            )
            self.db.commit()
            raise

        # Verify password and apply lockout policy on failure.
        if not verify_user_password(payload.password, user.password_hash):
            self._handle_failed_login(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                now=now,
            )
            self.db.commit()
            raise UnauthorizedError(message="Invalid credentials.")

        # Successful credentials: reset lockout state.
        self.repository.reset_failed_login_attempts(user)

        roles = self._extract_role_codes(user)
        primary_role = roles[0] if roles else None

        if user.is_two_factor_enabled:
            challenge = self._create_and_send_two_factor_challenge(user=user)
            self._log_security_event_for_user(
                user,
                event_type="TWO_FACTOR_CHALLENGE_ISSUED",
                severity="INFO",
                detail=f"2FA challenge issued to {user.username}.",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "challenge_id": challenge.id,
                    "challenge_type": str(challenge.challenge_type),
                    "purpose": str(challenge.purpose),
                },
            )
            self.db.commit()

            return {
                "success": True,
                "message": "Login successful. Two-factor verification is required.",
                "user_id": user.id,
                "identifier": payload.identifier,
                "two_factor_required": True,
                "two_factor_method": str(challenge.challenge_type),
                "challenge_reference": str(challenge.id),
            }

        login_result = build_login_result(
            user_id=user.id,
            role=primary_role,
            roles=roles,
            two_factor_verified=False,
            tenant_id=get_current_tenant_id(),
            tenant_code=get_current_tenant_code(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.repository.create_user_session(**login_result["session_payload"])
        self.repository.update_last_login(user, when=now)

        # Increment login usage
        tenant_id = get_current_tenant_id()
        if tenant_id:
            try:
                TenantUsageService.increment_login_usage(tenant_id)
            except Exception as exc:
                # Log but don't fail login
                print(f"Failed to increment login usage for tenant {tenant_id}: {exc}")

        self.db.commit()

        return {
            "success": True,
            "message": "Login successful.",
            "user": self._serialize_auth_user(user),
            "tokens": {
                "access_token": login_result["access_token"],
                "refresh_token": login_result["refresh_token"],
                "token_type": login_result["token_type"],
                "expires_in": None,
                "refresh_expires_in": None,
                "two_factor_required": False,
                "two_factor_verified": False,
            },
        }

    def refresh_access_token(self, payload: RefreshTokenRequestSchema) -> dict[str, Any]:
        """
        Refresh the access token using a valid refresh token.

        Also ensures the refresh-token-backed session has not been revoked.
        """
        refresh_payload = validate_token_type(payload.refresh_token, "refresh")
        refresh_jti = refresh_payload.get("jti")
        subject = refresh_payload.get("sub")

        if not refresh_jti or not subject:
            raise UnauthorizedError(message="Invalid refresh token.")

        session = self.repository.get_session_by_refresh_jti(refresh_jti)
        if not session:
            raise UnauthorizedError(message="Session not found for refresh token.")

        if session.revoked_at is not None or session.is_current is False:
            raise UnauthorizedError(message="Session has been revoked.")

        user = self.repository.get_user_with_roles_by_id(int(subject))
        if not user:
            raise NotFoundError(message="User not found.")

        assert_user_is_active(status=str(user.status))

        roles = self._extract_role_codes(user)
        primary_role = roles[0] if roles else None

        access_token, access_payload = build_post_2fa_access_token(
            user_id=user.id,
            role=primary_role,
            roles=roles,
            tenant_id=get_current_tenant_id(),
            tenant_code=get_current_tenant_code(),
        )

        session.session_token_jti = access_payload["jti"]
        session.expires_at = datetime.fromtimestamp(access_payload["exp"], tz=timezone.utc)
        self.repository.save_session(session)
        self.db.commit()

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": None,
        }

    def logout(
        self,
        *,
        refresh_token: Optional[str] = None,
        all_sessions: bool = False,
        current_user_id: Optional[int] = None,
        access_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Logout current session or all sessions.

        Supported modes
        ---------------
        - revoke by refresh token
        - revoke current session by access token
        - revoke all sessions for current user
        """
        if all_sessions:
            if current_user_id is None:
                raise BadRequestError(message="current_user_id is required for all_sessions logout.")
            self.repository.revoke_all_user_sessions(
                current_user_id,
                when=datetime.now(timezone.utc),
            )
            self.db.commit()
            return {"success": True, "message": "Logout successful for all active sessions."}

        revoked_any = False

        if refresh_token:
            payload = validate_token_type(refresh_token, "refresh")
            refresh_jti = payload.get("jti")
            if refresh_jti:
                session = self.repository.get_session_by_refresh_jti(refresh_jti)
                if session:
                    self.repository.revoke_session(session, when=datetime.now(timezone.utc))
                    revoked_any = True

        if access_token:
            payload = validate_token_type(access_token, "access")
            session_jti = payload.get("jti")
            if session_jti:
                session = self.repository.get_session_by_session_jti(session_jti)
                if session:
                    self.repository.revoke_session(session, when=datetime.now(timezone.utc))
                    revoked_any = True

        self.db.commit()
        return {
            "success": True,
            "message": "Logout successful." if revoked_any or not refresh_token else "Logout request processed.",
        }

    def get_authenticated_profile(self, user_id: int) -> dict[str, Any]:
        """
        Return the authenticated user profile for /auth/me.
        """
        user = self.repository.get_authenticated_profile(user_id)
        if not user:
            raise NotFoundError(message="Authenticated user not found.")

        return {
            "success": True,
            "message": "Authenticated user fetched successfully.",
            "user": self._serialize_authenticated_profile(user),
            "session": None,
        }

    # ============================================================
    # PASSWORD MANAGEMENT
    # ============================================================

    def change_password(self, user_id: int, payload: ChangePasswordSchema) -> dict[str, Any]:
        """
        Change password for an authenticated user.

        Enforces:
        - current password matches
        - new password is different from current
        - password meets strength rules
        - password is not in the user's recent password history
        """
        user = self.repository.get_user_by_id(user_id)
        if not user:
            raise NotFoundError(message="User not found.")

        assert_login_password(
            plain_password=payload.current_password,
            stored_password_hash=user.password_hash,
        )

        if payload.current_password == payload.new_password:
            raise ValidationError(message="New password must be different from current password.")

        validate_password_strength(payload.new_password)
        self._enforce_password_history(user.id, current_hash=user.password_hash, new_password=payload.new_password)

        new_hash = get_password_hash(payload.new_password)
        # Snapshot the old hash to history before replacing.
        if user.password_hash:
            self.repository.insert_password_history(
                user_id=user.id,
                password_hash=user.password_hash,
                when=datetime.now(timezone.utc),
            )
        self.repository.update_password_hash(user, new_hash)
        self.repository.update_password_changed_at(user, when=datetime.now(timezone.utc))

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="PASSWORD_CHANGED",
            severity="INFO",
            event_detail=f"Password changed by user {user.username}.",
        )

        self.db.commit()

        return {
            "success": True,
            "message": "Password changed successfully.",
        }

    def forgot_password(self, payload: ForgotPasswordSchema) -> dict[str, Any]:
        """
        Start password reset flow.

        Current implementation
        ----------------------
        Creates a PASSWORD_RESET OTP challenge and dispatches it to the best
        available destination.
        """
        user = self.repository.get_user_by_identifier(payload.identifier)
        if not user:
            return {
                "success": True,
                "message": "If the account exists, password reset instructions have been sent.",
            }

        challenge = self._create_and_send_otp_challenge(
            user=user,
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
        Complete password reset using a token.

        Expected token
        --------------
        A JWT token whose subject is the user ID.
        """
        token_payload = decode_token(payload.reset_token)
        user_id = token_payload.get("sub")
        if not user_id:
            raise BadRequestError(message="Invalid reset token.")

        user = self.repository.get_user_by_id(int(user_id))
        if not user:
            raise NotFoundError(message="User not found.")

        validate_password_strength(payload.new_password)
        self._enforce_password_history(
            user.id,
            current_hash=user.password_hash,
            new_password=payload.new_password,
        )

        new_hash = get_password_hash(payload.new_password)
        if user.password_hash:
            self.repository.insert_password_history(
                user_id=user.id,
                password_hash=user.password_hash,
                when=datetime.now(timezone.utc),
            )
        self.repository.update_password_hash(user, new_hash)
        self.repository.update_password_changed_at(user, when=datetime.now(timezone.utc))
        self.repository.revoke_all_user_sessions(user.id, when=datetime.now(timezone.utc))

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="PASSWORD_RESET_BY_USER",
            severity="WARNING",
            event_detail=f"Password reset completed for {user.username} via reset token.",
        )

        self.db.commit()

        return {
            "success": True,
            "message": "Password reset successful.",
        }

    # ============================================================
    # OTP / TWO-FACTOR
    # ============================================================

    def verify_otp(self, payload: OTPVerifySchema) -> dict[str, Any]:
        """
        Generic OTP verification for supported purposes.

        Supported purposes include:
        - LOGIN_2FA
        - EMAIL_VERIFICATION
        - PHONE_VERIFICATION
        - PASSWORD_RESET
        """
        challenge = self._resolve_challenge(
            challenge_reference=payload.challenge_reference,
            user_id=payload.user_id,
            identifier=payload.identifier,
            purpose=payload.purpose,
        )
        self._verify_and_complete_challenge(challenge=challenge, plain_code=payload.otp_code)

        user = self.repository.get_user_with_roles_by_id(challenge.user_id)
        if not user:
            raise NotFoundError(message="User not found.")

        purpose = str(challenge.purpose)
        if purpose == str(TwoFactorPurpose.EMAIL_VERIFICATION):
            self.repository.mark_email_verified(user, verified=True)
        elif purpose == str(TwoFactorPurpose.PHONE_VERIFICATION):
            self.repository.mark_phone_verified(user, verified=True)

        self.db.commit()
        return {
            "success": True,
            "message": "Verification successful.",
            "verified": True,
            "user": self._serialize_auth_user(user),
            "tokens": None,
        }

    def resend_otp(self, payload: OTPResendSchema) -> dict[str, Any]:
        """
        Resend OTP for supported purposes.
        """
        user = None
        if payload.user_id is not None:
            user = self.repository.get_user_by_id(payload.user_id)
        elif payload.identifier:
            user = self.repository.get_user_by_identifier(payload.identifier)

        if not user:
            raise NotFoundError(message="User not found.")

        purpose = self._resolve_two_factor_purpose(payload.purpose or "LOGIN_2FA")
        challenge_type = self._resolve_two_factor_type_from_user_or_request(
            user=user,
            requested=payload.delivery_method,
        )

        challenge = self._create_and_send_otp_challenge(
            user=user,
            purpose=purpose,
            challenge_type=challenge_type,
        )
        self.db.commit()

        return {
            "success": True,
            "message": "OTP resent successfully.",
            "challenge_reference": str(challenge.id),
            "delivery_method": str(challenge.challenge_type),
        }

    def setup_two_factor(self, user_id: int, payload: TwoFactorSetupSchema) -> dict[str, Any]:
        """
        Enable or disable 2FA for a user.

        Since the current User model only stores the master flag and detailed
        delivery methods live on challenges/policies outside the User table,
        this method persists the master enable/disable state.
        """
        user = self.repository.get_user_by_id(user_id)
        if not user:
            raise NotFoundError(message="User not found.")

        if not payload.enable_two_factor:
            self.repository.disable_two_factor(user)
            self.db.commit()
            return {
                "success": True,
                "message": "Two-factor authentication disabled successfully.",
                "two_factor_enabled": False,
                "method": None,
                "setup_secret": None,
                "provisioning_uri": None,
                "qr_code_data": None,
            }

        self.repository.configure_two_factor(
            user,
            is_two_factor_enabled=True,
        )
        self.db.commit()

        return {
            "success": True,
            "message": "Two-factor authentication configured successfully.",
            "two_factor_enabled": True,
            "method": payload.method,
            "setup_secret": None,
            "provisioning_uri": None,
            "qr_code_data": None,
        }

    def verify_two_factor(
        self,
        payload: TwoFactorVerifySchema,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Verify login 2FA and issue final tokens + session.
        """
        challenge = self._resolve_challenge(
            challenge_reference=payload.challenge_reference,
            user_id=payload.user_id,
            identifier=payload.identifier,
            purpose="LOGIN_2FA",
        )
        self._verify_and_complete_challenge(challenge=challenge, plain_code=payload.otp_code)

        user = self.repository.get_user_with_roles_by_id(challenge.user_id)
        if not user:
            raise NotFoundError(message="User not found.")

        roles = self._extract_role_codes(user)
        primary_role = roles[0] if roles else None

        access_token, access_payload = build_post_2fa_access_token(
            user_id=user.id,
            role=primary_role,
            roles=roles,
            tenant_id=get_current_tenant_id(),
            tenant_code=get_current_tenant_code(),
        )

        refresh_result = build_login_result(
            user_id=user.id,
            role=primary_role,
            roles=roles,
            two_factor_verified=True,
            tenant_id=get_current_tenant_id(),
            tenant_code=get_current_tenant_code(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        session_payload = refresh_result["session_payload"]
        session_payload["session_token_jti"] = access_payload["jti"]

        self.repository.create_user_session(**session_payload)
        self.repository.update_last_login(user, when=datetime.now(timezone.utc))

        # Increment login usage
        tenant_id = get_current_tenant_id()
        if tenant_id:
            try:
                TenantUsageService.increment_login_usage(tenant_id)
            except Exception as exc:
                print(f"Failed to increment login usage for tenant {tenant_id}: {exc}")

        self.db.commit()

        return {
            "success": True,
            "message": "Verification successful.",
            "verified": True,
            "user": self._serialize_auth_user(user),
            "tokens": {
                "access_token": access_token,
                "refresh_token": refresh_result["refresh_token"],
                "token_type": "bearer",
                "expires_in": None,
                "refresh_expires_in": None,
                "two_factor_required": True,
                "two_factor_verified": True,
            },
        }

    # ============================================================
    # EMAIL / PHONE VERIFICATION
    # ============================================================

    def request_email_verification(self, payload: EmailVerificationRequestSchema) -> dict[str, Any]:
        """
        Request email verification OTP.
        """
        user = None
        if payload.user_id is not None:
            user = self.repository.get_user_by_id(payload.user_id)
        elif payload.email is not None:
            user = self.repository.get_user_by_email(str(payload.email))

        if not user:
            raise NotFoundError(message="User not found.")
        if not user.email:
            raise BadRequestError(message="User does not have an email address.")

        challenge = self._create_and_send_otp_challenge(
            user=user,
            purpose=TwoFactorPurpose.EMAIL_VERIFICATION,
            challenge_type=TwoFactorType.EMAIL,
        )
        self.db.commit()

        return {
            "success": True,
            "message": "Email verification instructions sent successfully.",
            "challenge_reference": str(challenge.id),
            "delivery_method": str(challenge.challenge_type),
        }

    def confirm_email_verification(self, payload: EmailVerificationConfirmSchema) -> dict[str, Any]:
        """
        Confirm email verification using a token.

        Expected token
        --------------
        A JWT token whose subject is the user ID.
        """
        token_payload = decode_token(payload.token)
        user_id = token_payload.get("sub")
        if not user_id:
            raise BadRequestError(message="Invalid email verification token.")

        user = self.repository.get_user_by_id(int(user_id))
        if not user:
            raise NotFoundError(message="User not found.")

        self.repository.mark_email_verified(user, verified=True)
        self.db.commit()

        return {
            "success": True,
            "message": "Email verified successfully.",
        }

    def request_phone_verification(self, payload: PhoneVerificationRequestSchema) -> dict[str, Any]:
        """
        Request phone verification OTP.
        """
        user = None
        if payload.user_id is not None:
            user = self.repository.get_user_by_id(payload.user_id)
        elif payload.phone_number:
            user = self.repository.get_user_by_phone_number(payload.phone_number)

        if not user:
            raise NotFoundError(message="User not found.")
        if not user.phone_number:
            raise BadRequestError(message="User does not have a phone number.")

        challenge = self._create_and_send_otp_challenge(
            user=user,
            purpose=TwoFactorPurpose.PHONE_VERIFICATION,
            challenge_type=TwoFactorType.SMS,
        )
        self.db.commit()

        return {
            "success": True,
            "message": "Phone verification code sent successfully.",
            "challenge_reference": str(challenge.id),
            "delivery_method": str(challenge.challenge_type),
        }

    def confirm_phone_verification(self, payload: PhoneVerificationConfirmSchema) -> dict[str, Any]:
        """
        Confirm phone verification using challenge reference + OTP.
        """
        if payload.challenge_reference and payload.otp_code:
            challenge = self._resolve_challenge(
                challenge_reference=payload.challenge_reference,
                user_id=None,
                identifier=None,
                purpose="PHONE_VERIFICATION",
            )
            self._verify_and_complete_challenge(challenge=challenge, plain_code=payload.otp_code)

            user = self.repository.get_user_by_id(challenge.user_id)
            if not user:
                raise NotFoundError(message="User not found.")

            self.repository.mark_phone_verified(user, verified=True)
            self.db.commit()

            return {
                "success": True,
                "message": "Phone verified successfully.",
            }

        if payload.token:
            token_payload = decode_token(payload.token)
            user_id = token_payload.get("sub")
            if not user_id:
                raise BadRequestError(message="Invalid phone verification token.")

            user = self.repository.get_user_by_id(int(user_id))
            if not user:
                raise NotFoundError(message="User not found.")

            self.repository.mark_phone_verified(user, verified=True)
            self.db.commit()

            return {
                "success": True,
                "message": "Phone verified successfully.",
            }

        raise BadRequestError(message="Provide token or challenge_reference with otp_code.")

    def request_patient_portal_otp(
        self,
        identifier: str,
        delivery_method: str = "EMAIL"
    ) -> dict[str, Any]:
        """
        Request a 5-digit OTP for patient portal login.
        """
        user = self.repository.get_user_by_identifier(identifier)
        if not user:
            # Mask user existence
            return {
                "success": True,
                "message": "If the account exists, a verification code has been sent.",
            }

        challenge_type = self._resolve_two_factor_type(delivery_method)
        destination = self._resolve_destination_for_type(user=user, challenge_type=challenge_type)
        
        if not destination:
            raise BadRequestError(f"User does not have a valid {delivery_method} configured.")

        # Override for 5-digit OTP
        payload = create_otp_challenge_payload(
            user_id=user.id,
            challenge_type=str(challenge_type),
            purpose=str(TwoFactorPurpose.PATIENT_PORTAL_LOGIN),
            destination=destination,
            otp_length=5, # Enforce 5-digit as requested
        )

        challenge = self.repository.create_two_factor_challenge(
            user_id=payload["user_id"],
            challenge_type=challenge_type,
            purpose=TwoFactorPurpose.PATIENT_PORTAL_LOGIN,
            destination=payload["destination"],
            code_hash=payload["code_hash"],
            expires_at=payload["expires_at"],
            max_attempts=payload["max_attempts"],
        )

        self._dispatch_otp(
            challenge_type=challenge_type,
            destination=destination,
            plain_code=payload["plain_code"],
            purpose="Patient Portal Login",
        )

        self.db.commit()

        return {
            "success": True,
            "message": "If the account exists, a verification code has been sent.",
            "challenge_reference": str(challenge.id),
        }

    def verify_patient_portal_otp(
        self,
        identifier: str,
        otp_code: str,
        challenge_reference: Optional[str] = None,
        *,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Verify a patient portal OTP and issue tokens.
        """
        challenge = self._resolve_challenge(
            challenge_reference=challenge_reference,
            user_id=None,
            identifier=identifier,
            purpose="PATIENT_PORTAL_LOGIN",
        )
        self._verify_and_complete_challenge(challenge=challenge, plain_code=otp_code)

        user = self.repository.get_user_with_roles_by_id(challenge.user_id)
        if not user:
            raise NotFoundError(message="User not found.")

        # Ensure user is linked to a patient
        patient = self.db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient:
             raise UnauthorizedError("This account is not registered as a patient.")

        roles = self._extract_role_codes(user)
        primary_role = roles[0] if roles else None

        # Issue standard tokens
        login_result = build_login_result(
            user_id=user.id,
            role=primary_role,
            roles=roles,
            two_factor_verified=True, # OTP verification counts as 2FA verified
            tenant_id=get_current_tenant_id(),
            tenant_code=get_current_tenant_code(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.repository.create_user_session(**login_result["session_payload"])
        self.repository.update_last_login(user, when=datetime.now(timezone.utc))
        self.db.commit()

        return {
            "success": True,
            "message": "Login successful.",
            "user": self._serialize_auth_user(user),
            "tokens": {
                "access_token": login_result["access_token"],
                "refresh_token": login_result["refresh_token"],
                "token_type": login_result["token_type"],
                "expires_in": None,
                "refresh_expires_in": None,
                "two_factor_required": False,
                "two_factor_verified": True,
            },
        }

    # ============================================================
    # INTERNAL HELPERS
    # ============================================================

    def _create_and_send_two_factor_challenge(self, *, user) -> Any:
        """
        Create and dispatch login 2FA challenge.
        """
        challenge_type = self._resolve_two_factor_type_from_user_or_request(user=user, requested=None)
        return self._create_and_send_otp_challenge(
            user=user,
            purpose=TwoFactorPurpose.LOGIN,
            challenge_type=challenge_type,
        )

    def _create_and_send_otp_challenge(
        self,
        *,
        user,
        purpose,
        challenge_type=None,
    ) -> Any:
        """
        Create challenge DB record and dispatch the plain OTP.
        """
        resolved_type = challenge_type or self._resolve_two_factor_type_from_user_or_request(
            user=user,
            requested=None,
        )
        destination = self._resolve_destination_for_type(user=user, challenge_type=resolved_type)

        payload = create_otp_challenge_payload(
            user_id=user.id,
            challenge_type=str(resolved_type),
            purpose=str(purpose),
            destination=destination,
        )

        challenge = self.repository.create_two_factor_challenge(
            user_id=payload["user_id"],
            challenge_type=resolved_type,
            purpose=purpose,
            destination=payload["destination"],
            code_hash=payload["code_hash"],
            expires_at=payload["expires_at"],
            max_attempts=payload["max_attempts"],
        )

        self._dispatch_otp(
            challenge_type=resolved_type,
            destination=destination,
            plain_code=payload["plain_code"],
            purpose=str(purpose),
        )

        return challenge

    def _verify_and_complete_challenge(self, *, challenge, plain_code: str) -> None:
        """
        Verify OTP against stored challenge and mark it verified.
        """
        try:
            verify_two_factor_code(
                plain_code=plain_code,
                stored_code_hash=challenge.code_hash,
                expires_at=challenge.expires_at,
                attempt_count=challenge.attempt_count,
                max_attempts=challenge.max_attempts,
            )
        except Exception as exc:
            self.repository.increment_two_factor_attempt_count(challenge)
            self.db.flush()
            record_security_event(
                self.db,
                user_id=challenge.user_id,
                event_type="TWO_FACTOR_FAILURE",
                severity="WARNING",
                event_detail=f"OTP verification failed for challenge {challenge.id}.",
                event_metadata={
                    "challenge_id": challenge.id,
                    "purpose": str(challenge.purpose),
                    "attempt_count": int(challenge.attempt_count or 0),
                    "reason": str(exc),
                },
            )
            self.db.flush()
            raise

        self.repository.mark_two_factor_challenge_verified(
            challenge,
            when=datetime.now(timezone.utc),
        )
        record_security_event(
            self.db,
            user_id=challenge.user_id,
            event_type="TWO_FACTOR_SUCCESS",
            severity="INFO",
            event_detail=f"OTP verified for challenge {challenge.id}.",
            event_metadata={
                "challenge_id": challenge.id,
                "purpose": str(challenge.purpose),
            },
        )

    def _resolve_challenge(
        self,
        *,
        challenge_reference: Optional[str],
        user_id: Optional[int],
        identifier: Optional[str],
        purpose: Optional[str],
    ) -> Any:
        """
        Resolve a challenge by ID first, then by latest open challenge.
        """
        resolved_purpose = self._resolve_two_factor_purpose(purpose) if purpose else None

        if challenge_reference:
            try:
                challenge_id = int(str(challenge_reference).strip())
            except ValueError as exc:
                raise BadRequestError(message="challenge_reference must be a valid numeric challenge ID.") from exc

            challenge = self.repository.get_two_factor_challenge_by_id(challenge_id)
            if not challenge:
                raise NotFoundError(message="Two-factor challenge not found.")
            if resolved_purpose is not None and challenge.purpose != resolved_purpose:
                raise BadRequestError(message="Challenge purpose does not match the requested purpose.")
            return challenge

        target_user = None
        if user_id is not None:
            target_user = self.repository.get_user_by_id(user_id)
        elif identifier:
            target_user = self.repository.get_user_by_identifier(identifier)

        if not target_user:
            raise NotFoundError(message="User not found for challenge resolution.")

        challenge = self.repository.get_latest_open_two_factor_challenge(
            user_id=target_user.id,
            purpose=resolved_purpose,
        )
        if not challenge:
            raise NotFoundError(message="Open challenge not found.")

        return challenge

    def _dispatch_otp(
        self,
        *,
        challenge_type,
        destination: Optional[str],
        plain_code: str,
        purpose: str,
    ) -> None:
        """
        Send OTP using configured transport.
        """
        if not destination:
            raise BadRequestError(message="No valid destination available for OTP delivery.")

        message = f"Your verification code is: {plain_code}. Purpose: {purpose}."

        challenge_type_str = str(challenge_type).upper()

        if "EMAIL" in challenge_type_str:
            # Prefer the tenant's own configured email system (so OTPs come
            # from a sender the tenant controls); fall back to the
            # platform-wide ``send_email`` helper only when no tenant
            # configuration is available.
            try:
                from app.services.tenant_email_service import send_tenant_email

                ok = send_tenant_email(
                    self.db,
                    subject="Verification Code",
                    recipients=[destination],
                    body_text=message,
                )
                if ok:
                    return
            except Exception as exc:
                # Best-effort fallback below.
                pass

            if send_email is None:
                raise BadRequestError(message="Email delivery helper is not configured.")
            send_email(
                subject="Verification Code",
                recipients=[destination],
                body_text=message,
            )
            return

        if "SMS" in challenge_type_str:
            if send_sms is None:
                raise BadRequestError(message="SMS delivery helper is not configured.")
            send_sms(to=destination, body=message)
            return

        if "WHATSAPP" in challenge_type_str:
            if send_whatsapp_message is None:
                raise BadRequestError(message="WhatsApp delivery helper is not configured.")
            send_whatsapp_message(to=destination, body=message)
            return

        raise BadRequestError(
            message=f"Unsupported OTP challenge type: {challenge_type_str}",
        )

    def _resolve_destination_for_type(self, *, user, challenge_type) -> Optional[str]:
        """
        Resolve target destination from user based on challenge type.
        """
        challenge_type_str = str(challenge_type).upper()

        if "EMAIL" in challenge_type_str:
            return getattr(user, "email", None)
        if "SMS" in challenge_type_str or "WHATSAPP" in challenge_type_str:
            return getattr(user, "phone_number", None)

        return None

    def _resolve_two_factor_type_from_user_or_request(self, *, user, requested: Optional[str]) -> Any:
        """
        Resolve TwoFactorType from explicit request or available user contact info.
        """
        if requested:
            return self._resolve_two_factor_type(requested)

        if getattr(user, "email", None):
            return TwoFactorType.EMAIL
        if getattr(user, "phone_number", None):
            return TwoFactorType.SMS

        raise BadRequestError(message="No supported two-factor destination is available for this user.")

    def _resolve_two_factor_type(self, value: str) -> Any:
        """
        Normalize external string to TwoFactorType enum.
        """
        normalized = str(value).strip().upper()
        for member in TwoFactorType:
            if member.name == normalized or str(member.value).upper() == normalized:
                return member

        raise BadRequestError(
            message=f"Unsupported two-factor type: {value}",
        )

    def _resolve_two_factor_purpose(self, value: str) -> Any:
        """
        Normalize external string to TwoFactorPurpose enum.

        Accepts a small set of legacy aliases (e.g. LOGIN_2FA -> LOGIN) so
        existing client integrations continue to work after the enum was
        consolidated.
        """
        normalized = str(value).strip().upper()
        legacy_aliases = {
            "LOGIN_2FA": "LOGIN",
            "TWO_FACTOR_LOGIN": "LOGIN",
        }
        normalized = legacy_aliases.get(normalized, normalized)

        for member in TwoFactorPurpose:
            if member.name == normalized or str(member.value).upper() == normalized:
                return member

        raise BadRequestError(
            message=f"Unsupported two-factor purpose: {value}",
        )

    # ============================================================
    # LOCKOUT / FAILED LOGIN HELPERS
    # ============================================================

    def _is_user_locked(self, user, *, now: Optional[datetime] = None) -> bool:
        """
        Return True when the user is currently within a lockout window.
        """
        if user is None:
            return False

        # An explicit LOCKED status counts as locked even without a window.
        if str(user.status).upper() == "LOCKED":
            # If a lockout window exists and has already elapsed, auto-clear it.
            if user.locked_until is None:
                return True
            current = now or datetime.now(timezone.utc)
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if current >= locked_until:
                # Auto-recover: clear lockout window and let status validation
                # decide. Service-level callers may decide to revert status.
                self.repository.reset_failed_login_attempts(user)
                self.repository.update_user_status(user, UserStatus.ACTIVE)
                return False
            return True

        if user.locked_until is None:
            return False

        current = now or datetime.now(timezone.utc)
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        if current >= locked_until:
            # Lockout window expired — clear counters proactively.
            self.repository.reset_failed_login_attempts(user)
            return False

        return True

    def _handle_failed_login(
        self,
        *,
        user,
        ip_address: Optional[str],
        user_agent: Optional[str],
        now: datetime,
    ) -> None:
        """
        Record a failed login attempt and, if the threshold is exceeded,
        lock the user account for the configured cooldown.
        """
        self.repository.increment_failed_login_attempts(user, when=now)

        max_attempts = int(getattr(settings, "LOGIN_MAX_FAILED_ATTEMPTS", 5))
        cooldown_minutes = int(getattr(settings, "LOGIN_LOCKOUT_MINUTES", 30))

        self._log_security_event_for_user(
            user,
            event_type="LOGIN_FAILURE",
            severity="WARNING",
            detail=(
                f"Failed login for {user.username} (attempt "
                f"{user.failed_login_attempts}/{max_attempts})."
            ),
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={
                "failed_login_attempts": int(user.failed_login_attempts or 0),
                "max_attempts": max_attempts,
            },
        )

        if user.failed_login_attempts >= max_attempts:
            locked_until = now + timedelta(minutes=cooldown_minutes)
            self.repository.lock_user(
                user,
                until=locked_until,
                status_value=UserStatus.LOCKED,
            )
            self._log_security_event_for_user(
                user,
                event_type="ACCOUNT_LOCKED",
                severity="CRITICAL",
                detail=(
                    f"Account {user.username} locked after "
                    f"{user.failed_login_attempts} failed attempts."
                ),
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "locked_until": locked_until.isoformat(),
                    "cooldown_minutes": cooldown_minutes,
                },
            )

    def _log_security_event_for_user(
        self,
        user,
        *,
        event_type: str,
        severity: str = "INFO",
        detail: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Convenience wrapper around `record_security_event` for a known user.
        """
        record_security_event(
            self.db,
            user_id=getattr(user, "id", None),
            event_type=event_type,
            severity=severity,
            event_detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
            event_metadata=metadata,
        )

    # ============================================================
    # PASSWORD HISTORY ENFORCEMENT
    # ============================================================

    def _enforce_password_history(
        self,
        user_id: int,
        *,
        current_hash: Optional[str],
        new_password: str,
    ) -> None:
        """
        Reject the new password if it matches the user's current password or
        any of the most recent N hashes in PasswordHistory.
        """
        history_limit = int(getattr(settings, "PASSWORD_HISTORY_LIMIT", 5))
        if history_limit <= 0:
            return

        recent_hashes = self.repository.get_recent_password_hashes(user_id, limit=history_limit)
        candidate_hashes = list(recent_hashes)
        if current_hash and current_hash not in candidate_hashes:
            candidate_hashes.insert(0, current_hash)

        for stored_hash in candidate_hashes:
            try:
                if verify_user_password(new_password, stored_hash):
                    raise ValidationError(
                        message="New password cannot match a recently used password.",
                        detail={"history_limit": history_limit},
                    )
            except ValidationError:
                raise
            except Exception:
                # If a stored hash format is incompatible, skip rather than block.
                continue

    def _extract_role_codes(self, user) -> list[str]:
        """
        Extract role codes from user.user_roles.
        """
        role_codes: list[str] = []

        for user_role in getattr(user, "user_roles", []) or []:
            role = getattr(user_role, "role", None)
            if role is None:
                continue

            value = getattr(role, "code", None) or getattr(role, "name", None)
            if value:
                normalized = str(value).strip().upper()
                if normalized not in role_codes:
                    role_codes.append(normalized)

        return role_codes

    def _serialize_auth_user(self, user) -> dict[str, Any]:
        """
        Serialize lightweight auth user payload.
        """
        return {
            "id": user.id,
            "username": user.username,
            "email": getattr(user, "email", None),
            "phone_number": getattr(user, "phone_number", None),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "middle_name": getattr(user, "middle_name", None),
            "status": str(getattr(user, "status", None)) if getattr(user, "status", None) is not None else None,
            "is_superuser": getattr(user, "is_superuser", False),
            "is_email_verified": getattr(user, "is_email_verified", False),
            "is_phone_verified": getattr(user, "is_phone_verified", False),
            "is_two_factor_enabled": getattr(user, "is_two_factor_enabled", False),
        }

    def _serialize_authenticated_profile(self, user) -> dict[str, Any]:
        """
        Serialize authenticated profile payload.
        """
        roles: list[dict[str, Any]] = []
        for user_role in getattr(user, "user_roles", []) or []:
            role = getattr(user_role, "role", None)
            if role is None:
                continue

            role_payload = {
                "id": role.id,
                "name": role.name,
                "code": getattr(role, "code", None),
                "description": getattr(role, "description", None),
            }
            if role_payload not in roles:
                roles.append(role_payload)

        return {
            "id": user.id,
            "username": user.username,
            "email": getattr(user, "email", None),
            "phone_number": getattr(user, "phone_number", None),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "middle_name": getattr(user, "middle_name", None),
            "status": str(getattr(user, "status", None)) if getattr(user, "status", None) is not None else None,
            "is_superuser": getattr(user, "is_superuser", False),
            "is_email_verified": getattr(user, "is_email_verified", False),
            "is_phone_verified": getattr(user, "is_phone_verified", False),
            "is_two_factor_enabled": getattr(user, "is_two_factor_enabled", False),
            "two_factor_method": None,
            "two_factor_email_enabled": False,
            "two_factor_sms_enabled": False,
            "two_factor_whatsapp_enabled": False,
            "two_factor_authenticator_enabled": False,
            "roles": roles,
            "created_at": getattr(user, "created_at", None),
            "updated_at": getattr(user, "updated_at", None),
        }
    def _discover_and_set_tenant(self, identifier: str) -> None:
        """
        Attempt to resolve and set the tenant context based on the login identifier.
        This allows login to work on IP addresses or main domains by 'discovering'
        the tenant from the user's email domain or slug.
        """
        from app.repositories.tenant_repository import TenantRepository
        from app.core.multitenancy import set_current_tenant, get_current_tenant_db_url
        from app.core.database import get_engine_for_url
        from sqlalchemy.orm import Session
        
        # 1. Search for tenant in the current (Master) database
        repo = TenantRepository(self.db)
        tenant = None
        
        domain = None
        if "@" in identifier:
            domain = identifier.split("@")[-1].strip().lower()
            
        if domain:
            # Try exact domain match
            tenant = repo.get_tenant_by_domain(domain)
            if not tenant:
                # Try by slug extracted from domain (stnicholas.com -> stnicholas)
                slug = domain.split(".")[0]
                tenant = repo.get_tenant_by_slug(slug)
        
        if not tenant:
            # Try the identifier itself as a slug (for cases like 'stadmin')
            # or if the user typed the tenant code directly.
            tenant = repo.get_tenant_by_slug(identifier.strip().lower())

        if tenant:
            # Set the global context for this request
            set_current_tenant(tenant)
            
            # Switch the database session to the tenant's database
            tenant_db_url = get_current_tenant_db_url()
            if tenant_db_url:
                engine = get_engine_for_url(tenant_db_url)
                # We create a new session bound to the tenant's engine
                # Note: The original Master session will be closed by FastAPI's dependency cleanup.
                # We replace our references so the rest of the login flow uses the tenant DB.
                new_session = Session(bind=engine, expire_on_commit=False)
                self.db = new_session
                self.repository.db = new_session
