"""
Support-access grants.

Platform admins are walled off from tenant data by default. To inspect or
operate on a tenant's database, a SaaS admin must hold an active
:class:`SupportAccessGrant` for that tenant. The grant is requested by the
admin (or auto-created by SUPER_ADMIN), approved by the tenant, and runs
for a bounded window. Every grant carries a reason and is stored in the
master DB so support sessions are fully auditable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import SaaSRole, SupportAccessStatus
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.all_models import SaaSAdmin, SupportAccessGrant, Tenant


# Maximum time window a grant can stay active before expiring automatically.
MAX_GRANT_HOURS = 24 * 7  # one week


class SupportAccessService:
    """
    Manage controlled tenant-access for platform administrators.

    Operates against the **master** database.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_grants(
        self,
        *,
        tenant_id: Optional[int] = None,
        admin_id: Optional[int] = None,
        status: Optional[SupportAccessStatus] = None,
    ) -> list[SupportAccessGrant]:
        q = self.db.query(SupportAccessGrant).filter(
            SupportAccessGrant.is_deleted.is_(False)
        )
        if tenant_id is not None:
            q = q.filter(SupportAccessGrant.tenant_id == tenant_id)
        if admin_id is not None:
            q = q.filter(SupportAccessGrant.saas_admin_id == admin_id)
        if status is not None:
            q = q.filter(SupportAccessGrant.status == status)
        return q.order_by(SupportAccessGrant.id.desc()).all()

    def get_grant(self, grant_id: int) -> SupportAccessGrant:
        grant = (
            self.db.query(SupportAccessGrant)
            .filter(
                SupportAccessGrant.id == grant_id,
                SupportAccessGrant.is_deleted.is_(False),
            )
            .first()
        )
        if not grant:
            raise NotFoundError(message="Support access grant not found.")
        return grant

    def has_active_grant(self, *, admin_id: int, tenant_id: int) -> bool:
        """Return ``True`` if there is a usable grant right now."""
        return self._active_grant(admin_id=admin_id, tenant_id=tenant_id) is not None

    def _active_grant(self, *, admin_id: int, tenant_id: int) -> Optional[SupportAccessGrant]:
        now = datetime.now(timezone.utc)
        return (
            self.db.query(SupportAccessGrant)
            .filter(
                SupportAccessGrant.saas_admin_id == admin_id,
                SupportAccessGrant.tenant_id == tenant_id,
                SupportAccessGrant.status == SupportAccessStatus.APPROVED,
                SupportAccessGrant.is_deleted.is_(False),
                SupportAccessGrant.valid_from <= now,
                SupportAccessGrant.valid_until > now,
            )
            .first()
        )

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def request_grant(
        self,
        *,
        admin: SaaSAdmin,
        tenant_id: int,
        reason: str,
        valid_hours: int = 4,
        permissions: Optional[list[str]] = None,
    ) -> SupportAccessGrant:
        if not reason or not reason.strip():
            raise BadRequestError(message="A reason is required to request support access.")
        if valid_hours <= 0 or valid_hours > MAX_GRANT_HOURS:
            raise BadRequestError(
                message=f"valid_hours must be between 1 and {MAX_GRANT_HOURS}.",
            )

        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError(message="Tenant not found.")

        now = datetime.now(timezone.utc)
        # SUPER_ADMIN can self-approve immediately; others stay REQUESTED.
        platform_role = str(getattr(admin.platform_role, "value", admin.platform_role) or "").upper()
        is_super = bool(admin.is_superuser) or platform_role == "SUPER_ADMIN"
        status = SupportAccessStatus.APPROVED if is_super else SupportAccessStatus.REQUESTED

        grant = SupportAccessGrant(
            saas_admin_id=admin.id,
            tenant_id=tenant_id,
            reason=reason.strip(),
            status=status,
            valid_from=now,
            valid_until=now + timedelta(hours=valid_hours),
            requested_by_admin_id=admin.id,
            permissions={"actions": list(permissions or ["read"])},
            approved_at=now if is_super else None,
        )
        self.db.add(grant)
        self.db.commit()
        self.db.refresh(grant)
        return grant

    def approve_grant(
        self,
        grant_id: int,
        *,
        approver_user_id: Optional[int] = None,
    ) -> SupportAccessGrant:
        grant = self.get_grant(grant_id)
        if grant.status not in {SupportAccessStatus.REQUESTED, SupportAccessStatus.REVOKED}:
            raise BadRequestError(message=f"Grant cannot be approved from state {grant.status}.")
        grant.status = SupportAccessStatus.APPROVED
        grant.approved_at = datetime.now(timezone.utc)
        grant.approved_by_tenant_user_id = approver_user_id
        self.db.commit()
        self.db.refresh(grant)
        return grant

    def revoke_grant(self, grant_id: int) -> SupportAccessGrant:
        grant = self.get_grant(grant_id)
        if grant.status not in {SupportAccessStatus.APPROVED, SupportAccessStatus.REQUESTED}:
            return grant
        grant.status = SupportAccessStatus.REVOKED
        grant.revoked_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(grant)
        return grant

    def assert_can_access_tenant(self, *, admin: SaaSAdmin, tenant_id: int) -> SupportAccessGrant:
        """
        Raise :class:`ForbiddenError` unless the admin has an active grant
        for ``tenant_id``. SUPER_ADMIN bypass is intentionally NOT applied —
        even superusers must hold an explicit grant so audit trails stay
        accurate.
        """
        active = self._active_grant(admin_id=admin.id, tenant_id=tenant_id)
        if active is not None:
            return active
        raise ForbiddenError(
            message=(
                "You do not currently hold an active support-access grant for "
                "this tenant. Request one first."
            ),
            detail={"tenant_id": tenant_id},
        )

    # ------------------------------------------------------------------
    # SWEEPS
    # ------------------------------------------------------------------

    def expire_due_grants(self) -> int:
        """Mark expired APPROVED/REQUESTED grants as EXPIRED. Returns count."""
        now = datetime.now(timezone.utc)
        due = (
            self.db.query(SupportAccessGrant)
            .filter(
                SupportAccessGrant.status.in_(
                    [SupportAccessStatus.APPROVED, SupportAccessStatus.REQUESTED]
                ),
                SupportAccessGrant.valid_until <= now,
                SupportAccessGrant.is_deleted.is_(False),
            )
            .all()
        )
        for g in due:
            g.status = SupportAccessStatus.EXPIRED
        if due:
            self.db.commit()
        return len(due)
