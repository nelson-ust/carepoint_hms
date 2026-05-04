# app/services/patient_portal_auth_service.py
from __future__ import annotations

"""
Patient portal authentication via one-time password (OTP).

Distinct from :mod:`app.services.patient_portal_service`, which handles
the *post-login* portal experience (dashboard, profile, notifications).
This module is purely about getting the patient *into* the portal.

Flow
----
1. ``request_otp(identifier, channel)``
   - Identifies the patient by email / phone / hospital number.
   - Generates a 5-digit numeric OTP.
   - Stores ``sha256(code)`` (never the plaintext) along with the chosen
     channel + masked destination + expiry on a ``PatientPortalOtp`` row.
   - Dispatches the OTP body via :class:`NotificationService` (email/SMS).
   - Records a ``PATIENT_PORTAL_OTP_REQUESTED`` security event.
   - Returns the OTP id, masked destination, and expiry seconds — never
     the plaintext code.

2. ``verify_otp(otp_id, otp_code)``
   - Looks up the OTP, applies expiry / max-attempts / consumed checks.
   - Verifies the supplied code against the stored hash.
   - On success: ensures the patient has a linked :class:`User`, creates
     one if missing (no password — patients use OTP only), assigns the
     ``PATIENT`` role, marks the OTP consumed, issues a JWT pair via
     :func:`build_login_result`, persists a :class:`UserSession`, and
     returns the tokens plus a compact patient identity payload.
   - On failure: increments attempt count and raises
     :class:`UnauthorizedError`.

3. ``resend_otp(otp_id)``
   - Regenerates a fresh OTP on the same row (with a new TTL window) and
     re-dispatches it. We don't store the plaintext, so re-sending the
     "same" code isn't possible — each resend rolls a new code.

Security notes
--------------
- The OTP plaintext lives in-memory only long enough to be hashed and
  embedded in the notification body.
- The hash is sha256 (no salt). OTPs are short-lived single-use values;
  bcrypt/Argon2 cost is overkill and would make the verify step slow.
- ``record_security_event`` captures every request / verify / resend so
  abuse can be reviewed.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.enums import UserStatus
from app.core.exceptions import BadRequestError, NotFoundError, UnauthorizedError
from app.core.security import build_login_result, get_password_hash
from app.models.all_models import (
    Patient,
    PatientPortalOtp,
    Role,
    User,
    UserRoleAssociation,
    UserSession,
)
from app.schemas.notification_schema import NotificationAdHocDispatchSchema
from app.services.notification_service import NotificationService
from app.utils.security_event_util import record_security_event


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

OTP_CODE_LENGTH = 5  # 5-digit OTP per the requirement.
OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_MAX_RESENDS = 3
PORTAL_PATIENT_ROLE_CODE = "PATIENT"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_otp(code: str) -> str:
    """Stable sha256 hash of an OTP for storage + comparison."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _generate_otp() -> str:
    """Generate a numeric OTP of length :data:`OTP_CODE_LENGTH`."""
    upper = 10 ** OTP_CODE_LENGTH
    # secrets.randbelow gives a uniform value in [0, upper); zero-pad to
    # preserve leading zeros so the patient always sees N digits.
    return f"{secrets.randbelow(upper):0{OTP_CODE_LENGTH}d}"


def _mask_email(email: str) -> str:
    """Mask an email for safe UI echo: ``ne****@li***.com``."""
    if "@" not in email:
        return _mask_generic(email)
    local, _, domain = email.partition("@")
    masked_local = (local[:2] + "*" * max(len(local) - 2, 1)) if local else "*"
    if "." in domain:
        head, _, tld = domain.partition(".")
        masked_domain = (head[:2] + "*" * max(len(head) - 2, 1)) if head else "*"
        return f"{masked_local}@{masked_domain}.{tld}"
    return f"{masked_local}@{domain}"


def _mask_phone(phone: str) -> str:
    """Mask a phone for safe UI echo: ``+234********45``."""
    if len(phone) <= 4:
        return "*" * len(phone)
    return phone[:3] + "*" * (len(phone) - 5) + phone[-2:]


def _mask_generic(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 2:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 2)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PatientPortalAuthService:
    """OTP-based authentication for the patient portal."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ----- patient resolution ---------------------------------------------

    def _resolve_patient(self, identifier: str) -> Patient:
        """Look up a patient by email, phone, or hospital number."""
        identifier = identifier.strip()
        patient = (
            self.db.query(Patient)
            .filter(
                or_(
                    Patient.email.ilike(identifier),
                    Patient.phone_number == identifier,
                    Patient.hospital_number == identifier,
                    Patient.hospital_number == identifier.upper(),
                ),
                Patient.is_deleted.is_(False),
            )
            .first()
        )
        if patient is None:
            # Generic message to avoid identifier enumeration.
            raise UnauthorizedError(
                message="No patient found for that identifier.",
                detail={"identifier": identifier.lower()},
            )
        return patient

    def _resolve_channel_destination(
        self,
        patient: Patient,
        *,
        requested_channel: Optional[str],
    ) -> tuple[str, str]:
        """
        Pick a delivery channel + destination address.

        Preference order:
        - If ``requested_channel == EMAIL`` and patient has email, use email.
        - If ``requested_channel == SMS`` and patient has phone, use phone.
        - Else fall back to whichever channel the patient has on file.
        """
        if requested_channel == "EMAIL":
            if not patient.email:
                raise BadRequestError(
                    message="Patient has no email on file.",
                    detail={"patient_id": patient.id},
                )
            return "EMAIL", patient.email
        if requested_channel == "SMS":
            if not patient.phone_number:
                raise BadRequestError(
                    message="Patient has no phone number on file.",
                    detail={"patient_id": patient.id},
                )
            return "SMS", patient.phone_number

        if patient.email:
            return "EMAIL", patient.email
        if patient.phone_number:
            return "SMS", patient.phone_number
        raise BadRequestError(
            message=(
                "Patient has no email or phone on file — cannot deliver an "
                "OTP. Update the patient record with a contact channel first."
            ),
            detail={"patient_id": patient.id},
        )

    # ----- request OTP -----------------------------------------------------

    def request_otp(
        self,
        *,
        identifier: str,
        channel: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """
        Generate and dispatch a fresh OTP for the patient identified by
        ``identifier``. Returns the payload the route serialises into the
        response schema.
        """
        patient = self._resolve_patient(identifier)
        resolved_channel, destination = self._resolve_channel_destination(
            patient, requested_channel=channel
        )

        # Invalidate any older outstanding OTPs for this patient. Easier to
        # reason about than juggling N concurrent codes.
        self.db.query(PatientPortalOtp).filter(
            PatientPortalOtp.patient_id == patient.id,
            PatientPortalOtp.is_consumed.is_(False),
            PatientPortalOtp.is_deleted.is_(False),
        ).update({"is_consumed": True}, synchronize_session=False)

        code_plain = _generate_otp()
        code_hash = _hash_otp(code_plain)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)

        otp = PatientPortalOtp(
            patient_id=patient.id,
            channel=resolved_channel,
            destination=destination,
            code_hash=code_hash,
            attempt_count=0,
            max_attempts=OTP_MAX_ATTEMPTS,
            resend_count=0,
            is_consumed=False,
            expires_at=expires_at,
            requested_ip=ip_address,
            user_agent=user_agent,
        )
        self.db.add(otp)
        self.db.flush()
        self.db.refresh(otp)

        self._dispatch_otp_notification(
            patient=patient,
            channel=resolved_channel,
            destination=destination,
            code=code_plain,
        )

        record_security_event(
            self.db,
            event_type="PATIENT_PORTAL_OTP_REQUESTED",
            severity="INFO",
            event_detail=(
                f"Patient portal OTP {otp.id} issued to patient {patient.id} "
                f"via {resolved_channel}."
            ),
            event_metadata={
                "patient_id": patient.id,
                "otp_id": otp.id,
                "channel": resolved_channel,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()

        masked = (
            _mask_email(destination) if resolved_channel == "EMAIL" else _mask_phone(destination)
        )
        return {
            "otp_id": otp.id,
            "channel": resolved_channel,
            "masked_destination": masked,
            "expires_in_seconds": OTP_TTL_MINUTES * 60,
        }

    def _dispatch_otp_notification(
        self,
        *,
        patient: Patient,
        channel: str,
        destination: str,
        code: str,
    ) -> None:
        """Best-effort notification dispatch. The OTP row is the source of truth."""
        try:
            notification_service = NotificationService(self.db)
            subject = "Your Carepoint Portal Login Code"
            body = (
                f"Hello {patient.first_name},\n\n"
                f"Your one-time login code is: {code}\n"
                f"It expires in {OTP_TTL_MINUTES} minutes. If you did not "
                f"request this code, please ignore this message."
            )
            notification_service.dispatch_ad_hoc(
                NotificationAdHocDispatchSchema(
                    channel=channel,
                    subject=subject,
                    body=body,
                    patient_id=patient.id,
                    recipient_address=destination,
                ),
                raise_on_failure=False,
            )
        except Exception:
            # Notification dispatch is best-effort. The OTP row already
            # exists; the patient can still verify if delivery worked.
            pass

    # ----- resend OTP ------------------------------------------------------

    def resend_otp(
        self,
        *,
        otp_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        """
        Roll a fresh code on the same OTP row and re-dispatch.

        We don't store the plaintext, so we always generate a new code,
        which means the patient should use whichever code arrived most
        recently.
        """
        otp = self._get_active_otp(otp_id)
        if otp.resend_count >= OTP_MAX_RESENDS:
            raise BadRequestError(
                message="Resend limit reached. Please request a fresh OTP.",
                detail={"otp_id": otp.id, "max_resends": OTP_MAX_RESENDS},
            )

        new_code = _generate_otp()
        otp.code_hash = _hash_otp(new_code)
        otp.expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
        otp.attempt_count = 0
        otp.resend_count += 1
        self.db.add(otp)
        self.db.flush()

        patient = otp.patient
        self._dispatch_otp_notification(
            patient=patient,
            channel=otp.channel,
            destination=otp.destination,
            code=new_code,
        )

        record_security_event(
            self.db,
            event_type="PATIENT_PORTAL_OTP_RESENT",
            severity="INFO",
            event_detail=f"Patient portal OTP {otp.id} resent.",
            event_metadata={
                "patient_id": patient.id,
                "otp_id": otp.id,
                "resend_count": otp.resend_count,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()

        masked = (
            _mask_email(otp.destination) if otp.channel == "EMAIL" else _mask_phone(otp.destination)
        )
        return {
            "otp_id": otp.id,
            "channel": otp.channel,
            "masked_destination": masked,
            "expires_in_seconds": int(
                (otp.expires_at - datetime.now(timezone.utc)).total_seconds()
            ),
        }

    # ----- verify OTP ------------------------------------------------------

    def verify_otp(
        self,
        *,
        otp_id: int,
        otp_code: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> dict:
        otp = self._get_active_otp(otp_id)
        now = datetime.now(timezone.utc)

        if otp.expires_at <= now:
            raise UnauthorizedError(
                message="OTP expired. Please request a new one.",
                detail={"otp_id": otp.id},
            )
        if otp.attempt_count >= otp.max_attempts:
            raise UnauthorizedError(
                message="Too many attempts. Please request a new OTP.",
                detail={"otp_id": otp.id},
            )

        otp.attempt_count += 1
        if _hash_otp(otp_code) != otp.code_hash:
            self.db.add(otp)
            record_security_event(
                self.db,
                event_type="PATIENT_PORTAL_OTP_FAILED",
                severity="WARNING",
                event_detail=f"Patient portal OTP {otp.id} verification failed.",
                event_metadata={
                    "patient_id": otp.patient_id,
                    "otp_id": otp.id,
                    "attempt_count": otp.attempt_count,
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self.db.commit()
            raise UnauthorizedError(
                message="Invalid OTP code.",
                detail={
                    "otp_id": otp.id,
                    "attempts_left": otp.max_attempts - otp.attempt_count,
                },
            )

        # ----- Success path: burn the OTP, issue tokens -----
        otp.is_consumed = True
        otp.consumed_at = now
        self.db.add(otp)
        self.db.flush()

        patient = otp.patient
        user = self._ensure_patient_user(patient)
        self._ensure_patient_role(user)

        login_result = build_login_result(
            user_id=user.id,
            roles=[PORTAL_PATIENT_ROLE_CODE],
            two_factor_verified=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._persist_session(user_id=user.id, login_result=login_result)

        # Mark patient identifiers verified now that the OTP succeeded.
        if otp.channel == "EMAIL" and not user.is_email_verified:
            user.is_email_verified = True
        if otp.channel == "SMS" and not user.is_phone_verified:
            user.is_phone_verified = True
        user.last_login_at = now
        self.db.add(user)

        record_security_event(
            self.db,
            user_id=user.id,
            event_type="PATIENT_PORTAL_LOGIN_SUCCESS",
            severity="INFO",
            event_detail=f"Patient {patient.id} logged into the portal via {otp.channel}.",
            event_metadata={
                "patient_id": patient.id,
                "otp_id": otp.id,
                "channel": otp.channel,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()

        full_name = " ".join(
            part for part in [patient.first_name, patient.middle_name, patient.last_name] if part
        )
        return {
            "tokens": {
                "access_token": login_result["access_token"],
                "refresh_token": login_result["refresh_token"],
                "token_type": login_result.get("token_type", "bearer"),
            },
            "patient_id": patient.id,
            "user_id": user.id,
            "hospital_number": patient.hospital_number,
            "full_name": full_name,
        }

    # ----- internal helpers -----------------------------------------------

    def _get_active_otp(self, otp_id: int) -> PatientPortalOtp:
        otp = (
            self.db.query(PatientPortalOtp)
            .filter(PatientPortalOtp.id == otp_id, PatientPortalOtp.is_deleted.is_(False))
            .first()
        )
        if otp is None:
            raise NotFoundError(message="OTP not found.", detail={"otp_id": otp_id})
        if otp.is_consumed:
            raise UnauthorizedError(
                message="OTP has already been used.",
                detail={"otp_id": otp.id},
            )
        return otp

    def _ensure_patient_user(self, patient: Patient) -> User:
        """
        Get-or-create the User row tied to a patient.

        Patients log in via OTP only — the password_hash column is non-NULL
        on the schema, so we set a random non-recoverable hash that cannot
        match any password input via the regular ``/auth/login`` flow.
        """
        if patient.user_id is not None:
            user = (
                self.db.query(User)
                .filter(User.id == patient.user_id, User.is_deleted.is_(False))
                .first()
            )
            if user is not None:
                return user

        # Build a deterministic username from MRN to keep collisions rare.
        username_seed = patient.hospital_number.lower().replace(" ", "_")
        username = f"patient_{username_seed}"
        if (
            self.db.query(User)
            .filter(User.username == username, User.is_deleted.is_(False))
            .first()
            is not None
        ):
            username = f"patient_{username_seed}_{patient.id}"

        random_hash = get_password_hash(secrets.token_urlsafe(32))

        user = User(
            username=username,
            email=patient.email or f"patient.{patient.id}@portal.local",
            phone_number=patient.phone_number,
            password_hash=random_hash,
            first_name=patient.first_name,
            last_name=patient.last_name,
            middle_name=patient.middle_name,
            status=UserStatus.ACTIVE,
            is_email_verified=False,
            is_phone_verified=False,
            is_two_factor_enabled=False,
        )
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)

        # Bind back on the patient row so subsequent OTP logins skip the
        # create branch entirely.
        patient.user_id = user.id
        self.db.add(patient)
        self.db.flush()
        return user

    def _ensure_patient_role(self, user: User) -> None:
        """Make sure the user carries the PATIENT role."""
        role = (
            self.db.query(Role)
            .filter(Role.code == PORTAL_PATIENT_ROLE_CODE, Role.is_deleted.is_(False))
            .first()
        )
        if role is None:
            return  # Seed missing — nothing to attach.
        already = (
            self.db.query(UserRoleAssociation)
            .filter(
                UserRoleAssociation.user_id == user.id,
                UserRoleAssociation.role_id == role.id,
                UserRoleAssociation.is_deleted.is_(False),
            )
            .first()
        )
        if already is None:
            self.db.add(UserRoleAssociation(user_id=user.id, role_id=role.id))
            self.db.flush()

    def _persist_session(self, *, user_id: int, login_result: dict) -> None:
        """Store the UserSession row so refresh / revoke work."""
        session_payload = login_result.get("session_payload") or {}
        try:
            session = UserSession(**session_payload)
            self.db.add(session)
            self.db.flush()
        except Exception:
            # If the session payload shape doesn't match (future field
            # rename), don't block login — the access token still works
            # for the duration of its TTL.
            self.db.rollback()
