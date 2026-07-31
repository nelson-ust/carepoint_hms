"""
Tenant user invitation lifecycle.

The invitation flow has three actors:

* the **inviter** (a tenant admin),
* the **invitee** (a person identified by email or phone number),
* the **system**, which persists a hashed token, sends the invitation
  link, and validates the token when the invitee accepts.

Plain tokens are only ever returned at create time and at resend time so
they can be embedded into a delivery message — they are stored hashed at
rest. Invitations expire after ``INVITATION_EXPIRY_DAYS`` (default 7).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import InvitationStatus, NotificationEvent, UserStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.security import get_password_hash, validate_password_strength
from app.models.all_models import (
    Role,
    User,
    UserInvitation,
    UserRoleAssociation,
)


DEFAULT_EXPIRY_DAYS = 7
TOKEN_BYTES = 32  # → 256 bits of entropy


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _build_accept_url(base_url: str, token: str) -> str:
    """Build the public accept link, embedding the tenant code so the
    anonymous invitee's browser can send X-Tenant-Code (the accept endpoint
    operates on the tenant database and needs the context)."""
    from app.core.multitenancy import get_current_tenant_code

    base = (base_url or "").rstrip("/")
    params = {"token": token}
    tenant_code = get_current_tenant_code()
    if tenant_code:
        params["tenant"] = tenant_code
    qs = urlencode(params)
    return f"{base}/invitations/accept?{qs}"


class InvitationService:
    """
    CRUD + lifecycle for :class:`UserInvitation`.

    Operates on the **tenant** database — invitations are scoped to the
    tenant in which they are issued, which guarantees tenant isolation
    automatically.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.expiry_days = int(getattr(settings, "INVITATION_EXPIRY_DAYS", DEFAULT_EXPIRY_DAYS))

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_invitations(
        self,
        *,
        status: Optional[InvitationStatus] = None,
    ) -> list[UserInvitation]:
        q = self.db.query(UserInvitation).filter(UserInvitation.is_deleted.is_(False))
        if status is not None:
            q = q.filter(UserInvitation.status == status)
        return q.order_by(UserInvitation.id.desc()).all()

    def get_invitation(self, invitation_id: int) -> UserInvitation:
        rec = (
            self.db.query(UserInvitation)
            .filter(
                UserInvitation.id == invitation_id,
                UserInvitation.is_deleted.is_(False),
            )
            .first()
        )
        if not rec:
            raise NotFoundError(message="Invitation not found.")
        return rec

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def create_invitation(
        self,
        *,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role_ids: Optional[list[int]] = None,
        invited_by_user_id: Optional[int] = None,
        expiry_days: Optional[int] = None,
    ) -> tuple[UserInvitation, str]:
        """
        Create a new invitation. Returns ``(record, plain_token)``.

        The plain token must be delivered to the invitee — it is never
        retrievable again.
        """
        if not email and not phone_number:
            raise BadRequestError(message="Either email or phone_number is required.")

        normalized_email = (email or "").strip().lower() or None
        normalized_phone = (phone_number or "").strip() or None

        # Reject if a User already exists with this identifier.
        if normalized_email:
            user_exists = (
                self.db.query(User)
                .filter(User.email == normalized_email, User.is_deleted.is_(False))
                .first()
            )
            if user_exists:
                raise BadRequestError(message="A user with that email already exists.")
        if normalized_phone:
            user_exists = (
                self.db.query(User)
                .filter(User.phone_number == normalized_phone, User.is_deleted.is_(False))
                .first()
            )
            if user_exists:
                raise BadRequestError(message="A user with that phone number already exists.")

        # Reject if there is already a PENDING invitation for the identifier.
        pending = self.db.query(UserInvitation).filter(
            UserInvitation.status == InvitationStatus.PENDING,
            UserInvitation.is_deleted.is_(False),
        )
        if normalized_email:
            pending = pending.filter(UserInvitation.email == normalized_email)
        elif normalized_phone:
            pending = pending.filter(UserInvitation.phone_number == normalized_phone)
        if pending.first() is not None:
            raise BadRequestError(
                message="An active invitation already exists for this identifier. Cancel it first or resend.",
            )

        if role_ids:
            existing_roles = self.db.query(Role).filter(Role.id.in_(role_ids)).all()
            found_ids = {r.id for r in existing_roles}
            missing = sorted(set(role_ids) - found_ids)
            if missing:
                raise BadRequestError(
                    message="One or more roles were not found.",
                    detail={"missing_role_ids": missing},
                )

        days = int(expiry_days or self.expiry_days)
        token = secrets.token_urlsafe(TOKEN_BYTES)
        rec = UserInvitation(
            email=normalized_email,
            phone_number=normalized_phone,
            first_name=first_name,
            last_name=last_name,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=days),
            status=InvitationStatus.PENDING,
            role_ids=list(role_ids) if role_ids else None,
            invited_by_user_id=invited_by_user_id,
            last_sent_at=datetime.now(timezone.utc),
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec, token

    def cancel_invitation(self, invitation_id: int) -> UserInvitation:
        rec = self.get_invitation(invitation_id)
        if rec.status != InvitationStatus.PENDING:
            raise BadRequestError(message=f"Only pending invitations can be cancelled (current: {rec.status}).")
        rec.status = InvitationStatus.CANCELLED
        rec.cancelled_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def resend_invitation(self, invitation_id: int) -> tuple[UserInvitation, str]:
        rec = self.get_invitation(invitation_id)
        if rec.status != InvitationStatus.PENDING:
            raise BadRequestError(
                message=f"Only pending invitations can be resent (current: {rec.status}).",
            )
        token = secrets.token_urlsafe(TOKEN_BYTES)
        rec.token_hash = _hash_token(token)
        rec.last_sent_at = datetime.now(timezone.utc)
        rec.resend_count = (rec.resend_count or 0) + 1
        rec.expires_at = datetime.now(timezone.utc) + timedelta(days=self.expiry_days)
        self.db.commit()
        self.db.refresh(rec)
        return rec, token

    def expire_due_invitations(self) -> int:
        now = datetime.now(timezone.utc)
        due = (
            self.db.query(UserInvitation)
            .filter(
                UserInvitation.status == InvitationStatus.PENDING,
                UserInvitation.expires_at <= now,
                UserInvitation.is_deleted.is_(False),
            )
            .all()
        )
        for inv in due:
            inv.status = InvitationStatus.EXPIRED
        if due:
            self.db.commit()
        return len(due)

    # ------------------------------------------------------------------
    # ACCEPTANCE
    # ------------------------------------------------------------------

    def accept_invitation(
        self,
        *,
        token: str,
        username: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone_number: Optional[str] = None,
    ) -> User:
        """
        Validate the token, create the User, assign roles, and mark the
        invitation as ACCEPTED.

        Raises :class:`BadRequestError` for any token problem so callers
        can surface a single uniform error to the public accept endpoint.
        """
        if not token:
            raise BadRequestError(message="Invitation token is required.")

        validate_password_strength(password)

        rec = (
            self.db.query(UserInvitation)
            .filter(
                UserInvitation.token_hash == _hash_token(token),
                UserInvitation.is_deleted.is_(False),
            )
            .first()
        )
        if not rec:
            raise BadRequestError(message="Invitation token is invalid.")

        now = datetime.now(timezone.utc)
        if rec.status == InvitationStatus.ACCEPTED:
            raise BadRequestError(message="This invitation has already been accepted.")
        if rec.status == InvitationStatus.CANCELLED:
            raise BadRequestError(message="This invitation has been cancelled.")
        if rec.status == InvitationStatus.EXPIRED or rec.expires_at <= now:
            rec.status = InvitationStatus.EXPIRED
            self.db.commit()
            raise BadRequestError(message="This invitation has expired.")

        # Resolve final email/phone — the invitee may pass over any new
        # phone, but the email is fixed by the invitation.
        final_email = rec.email
        final_phone = (phone_number or rec.phone_number) or None

        # Username uniqueness.
        if (
            self.db.query(User)
            .filter(User.username == username, User.is_deleted.is_(False))
            .first()
        ):
            raise BadRequestError(message="That username is already taken.")

        user = User(
            username=username.strip().lower(),
            email=final_email or f"user+{secrets.token_hex(6)}@invite.local",
            phone_number=final_phone,
            password_hash=get_password_hash(password),
            first_name=(first_name or rec.first_name or "").strip() or "User",
            last_name=(last_name or rec.last_name or "").strip() or "Invited",
            status=UserStatus.ACTIVE,
            is_email_verified=bool(final_email),
            is_phone_verified=False,
            is_superuser=False,
        )
        self.db.add(user)
        self.db.flush()

        if rec.role_ids:
            for role_id in rec.role_ids:
                self.db.add(UserRoleAssociation(user_id=user.id, role_id=int(role_id)))

        rec.status = InvitationStatus.ACCEPTED
        rec.accepted_at = now
        rec.accepted_by_user_id = user.id

        self.db.commit()
        self.db.refresh(user)
        return user

    # ------------------------------------------------------------------
    # NOTIFY
    # ------------------------------------------------------------------

    def send_invitation_email(self, rec: UserInvitation, plain_token: str) -> None:
        """
        Best-effort dispatch via :class:`NotificationDispatcher`. Failures
        are swallowed because the plain token has already been returned to
        the inviter (who can copy/paste it manually if delivery fails).
        """
        try:
            from app.services.notification_dispatcher import NotificationDispatcher
        except Exception:
            return

        accept_url = _build_accept_url(
            getattr(settings, "INVITATION_ACCEPT_BASE_URL", ""),
            plain_token,
        )

        dispatcher = NotificationDispatcher(self.db)

        recipients: list[dict] = []
        if rec.email:
            recipients.append({"email_address": rec.email})
        if rec.phone_number:
            recipients.append({"sms_address": rec.phone_number, "whatsapp_address": rec.phone_number})

        if not recipients:
            return

        dispatcher.dispatch(
            event=NotificationEvent.USER_INVITED,
            recipients=recipients,
            subject="You've been invited to CarePoint HMS",
            body=(
                f"Hello{(' ' + rec.first_name) if rec.first_name else ''},\n\n"
                f"You have been invited to CarePoint HMS. Click the link below to "
                f"complete your account setup:\n\n{accept_url}\n\n"
                f"This invitation expires on {rec.expires_at:%Y-%m-%d %H:%M UTC}."
            ),
            context={"invitation_id": rec.id, "expires_at": rec.expires_at.isoformat()},
        )
