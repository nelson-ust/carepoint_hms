# app/services/promo_plan_service.py
"""
Promotional plan-move campaigns — the DSTV "occasional / open window" strategy.

A SaaS admin temporarily moves a set of tenants onto a higher plan, free of
charge, for a fixed window. Each member tenant's current subscription keeps its
billing period but its ``plan_id`` is flipped to the target plan and marked
complimentary (so nothing extra is billed). The original plan is recorded on the
member row, so when the window closes every tenant is reverted cleanly.

Reverting happens two ways:
  * automatically, via the hourly scheduler job ``revert_due_campaigns``; and
  * manually, when a SaaS admin reverts a campaign early.

Every member tenant is emailed an announcement on launch.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.core.enums import PromoCampaignStatus, SubscriptionStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logger import get_logger
from app.models.all_models import (
    PromoPlanCampaign,
    PromoPlanMember,
    SubscriptionPlan,
    Tenant,
    TenantSubscription,
)

try:  # email is best-effort — never let a transport failure abort a campaign
    from app.utils.email_utils import send_email
except Exception:  # pragma: no cover
    send_email = None  # type: ignore[assignment]

logger = get_logger(__name__)

_LIVE_STATUSES = [
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.TRIALING,
    SubscriptionStatus.PENDING,
    SubscriptionStatus.PAST_DUE,
    SubscriptionStatus.EXPIRED,
    SubscriptionStatus.SUSPENDED,
]


def _add_months(base: datetime, months: int) -> datetime:
    if not months:
        return base
    idx = base.month - 1 + months
    year = base.year + idx // 12
    month = idx % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)


class PromoPlanService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _current_subscription(self, tenant_id: int) -> Optional[TenantSubscription]:
        return (
            self.db.query(TenantSubscription)
            .filter(
                TenantSubscription.tenant_id == tenant_id,
                TenantSubscription.status.in_(_LIVE_STATUSES),
            )
            .order_by(TenantSubscription.id.desc())
            .first()
        )

    def _active_plan(self, plan_code: str) -> SubscriptionPlan:
        plan = (
            self.db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.code == plan_code.upper().strip(),
                SubscriptionPlan.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not plan:
            raise NotFoundError(message=f"Active subscription plan '{plan_code}' not found.")
        return plan

    def _resolve_tenant_ids(
        self, *, tenant_ids: Optional[Iterable[int]], from_plan_code: Optional[str]
    ) -> list[int]:
        ids: set[int] = set()
        if tenant_ids:
            ids.update(int(t) for t in tenant_ids)
        if from_plan_code:
            src = self._active_plan(from_plan_code)
            rows = (
                self.db.query(TenantSubscription.tenant_id)
                .filter(
                    TenantSubscription.plan_id == src.id,
                    TenantSubscription.status.in_(
                        [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
                    ),
                )
                .all()
            )
            ids.update(r[0] for r in rows)
        if not ids:
            raise BadRequestError(
                message="Select at least one tenant, or a source plan to move everyone from."
            )
        return sorted(ids)

    def _recipients(self, tenant: Tenant) -> list[str]:
        out: list[str] = []
        admin = None
        if tenant.onboarding_data:
            admin = (tenant.onboarding_data or {}).get("admin_email")
        if admin:
            out.append(str(admin).strip().lower())
        if tenant.billing_email:
            b = tenant.billing_email.strip().lower()
            if b and b not in out:
                out.append(b)
        return out

    def _send_launch_email(
        self, tenant: Tenant, *, target_plan: SubscriptionPlan,
        from_plan: Optional[SubscriptionPlan], ends_at: datetime, message: Optional[str],
    ) -> None:
        if send_email is None:
            return
        recipients = self._recipients(tenant)
        if not recipients:
            return
        window = ends_at.strftime("%d %b %Y")
        from_txt = f" from {from_plan.name}" if from_plan else ""
        subject = f"You've been upgraded to {target_plan.name} — on us"
        extra = f"\n\n{message}" if message else ""
        body = (
            f"Hello {tenant.billing_contact_name or tenant.name},\n\n"
            f"Good news! As a valued CarePoint HMS partner, {tenant.name} has been "
            f"temporarily upgraded{from_txt} to the {target_plan.name} plan at no extra "
            f"cost. Enjoy the additional features until {window}, after which your "
            f"workspace returns to your regular plan automatically — no action needed."
            f"{extra}\n\n"
            f"Thank you for being with us.\n\nThe CarePoint HMS Team"
        )
        try:
            send_email(subject=subject, recipients=recipients, body_text=body)
        except Exception as exc:  # pragma: no cover
            logger.warning("Promo launch email to tenant %s failed: %s", tenant.id, exc)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def create_campaign(
        self, *, name: str, target_plan_code: str, days: int = 0, months: int = 0,
        message: Optional[str] = None, tenant_ids: Optional[Iterable[int]] = None,
        from_plan_code: Optional[str] = None, actor=None,
    ) -> PromoPlanCampaign:
        days = max(0, int(days or 0))
        months = max(0, int(months or 0))
        if days == 0 and months == 0:
            raise BadRequestError(message="Specify the promo window (days and/or months).")
        if not (name or "").strip():
            raise BadRequestError(message="Campaign name is required.")

        target = self._active_plan(target_plan_code)
        tids = self._resolve_tenant_ids(tenant_ids=tenant_ids, from_plan_code=from_plan_code)

        now = datetime.now(timezone.utc)
        ends_at = _add_months(now, months) + timedelta(days=days)

        actor_name = None
        if actor is not None:
            fn, ln = getattr(actor, "first_name", None), getattr(actor, "last_name", None)
            actor_name = (f"{fn} {ln}".strip() if (fn or ln) else getattr(actor, "username", None))

        campaign = PromoPlanCampaign(
            name=name.strip(), target_plan_id=target.id, status=PromoCampaignStatus.ACTIVE,
            starts_at=now, ends_at=ends_at, message=(message or None), tenant_count=0,
            created_by_user_id=getattr(actor, "id", None), created_by_name=actor_name,
        )
        self.db.add(campaign)
        self.db.flush()  # need campaign.id for members

        moved: list[tuple[Tenant, Optional[SubscriptionPlan]]] = []
        for tid in tids:
            tenant = self.db.query(Tenant).filter(Tenant.id == tid).first()
            if not tenant:
                continue
            sub = self._current_subscription(tid)
            if not sub or sub.plan_id == target.id:
                continue  # no live sub, or already on the target plan
            from_plan = self.db.query(SubscriptionPlan).filter(
                SubscriptionPlan.id == sub.plan_id).first()
            self.db.add(PromoPlanMember(
                campaign_id=campaign.id, tenant_id=tid, subscription_id=sub.id,
                original_plan_id=sub.plan_id,
                original_is_complimentary=bool(getattr(sub, "is_complimentary", False)),
                is_reverted=False,
            ))
            sub.plan_id = target.id
            sub.is_complimentary = True  # free upgrade for the window
            moved.append((tenant, from_plan))

        if not moved:
            self.db.rollback()
            raise BadRequestError(
                message="No eligible tenants to move (they may already be on the target plan)."
            )

        campaign.tenant_count = len(moved)
        self.db.commit()
        self.db.refresh(campaign)

        for tenant, from_plan in moved:
            self._send_launch_email(
                tenant, target_plan=target, from_plan=from_plan,
                ends_at=ends_at, message=message,
            )
        logger.info("Promo campaign %s launched: %s tenant(s) -> %s until %s",
                    campaign.id, len(moved), target.code, ends_at)
        return campaign

    def _revert_members(self, campaign: PromoPlanCampaign) -> int:
        members = (
            self.db.query(PromoPlanMember)
            .filter(
                PromoPlanMember.campaign_id == campaign.id,
                PromoPlanMember.is_reverted.is_(False),
            )
            .all()
        )
        now = datetime.now(timezone.utc)
        reverted = 0
        for m in members:
            sub = None
            if m.subscription_id:
                sub = self.db.query(TenantSubscription).filter(
                    TenantSubscription.id == m.subscription_id).first()
            if sub is None:
                sub = self._current_subscription(m.tenant_id)
            # Only undo our own change: if the tenant is still on the target plan.
            if sub is not None and sub.plan_id == campaign.target_plan_id:
                sub.plan_id = m.original_plan_id
                sub.is_complimentary = bool(m.original_is_complimentary)
            m.is_reverted = True
            m.reverted_at = now
            reverted += 1
        return reverted

    def revert_campaign(self, campaign_id: int, actor=None) -> PromoPlanCampaign:
        campaign = self.db.query(PromoPlanCampaign).filter(
            PromoPlanCampaign.id == campaign_id).first()
        if not campaign:
            raise NotFoundError(message="Campaign not found.")
        if campaign.status != PromoCampaignStatus.ACTIVE:
            raise BadRequestError(message="This campaign is not active.")
        self._revert_members(campaign)
        campaign.status = PromoCampaignStatus.REVERTED
        campaign.reverted_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(campaign)
        logger.info("Promo campaign %s reverted by %s", campaign.id,
                    getattr(actor, "id", "scheduler"))
        return campaign

    def revert_due_campaigns(self) -> int:
        """Scheduler entry point: revert every active campaign past its window."""
        now = datetime.now(timezone.utc)
        due = (
            self.db.query(PromoPlanCampaign)
            .filter(
                PromoPlanCampaign.status == PromoCampaignStatus.ACTIVE,
                PromoPlanCampaign.ends_at <= now,
            )
            .all()
        )
        count = 0
        for campaign in due:
            try:
                self._revert_members(campaign)
                campaign.status = PromoCampaignStatus.REVERTED
                campaign.reverted_at = now
                self.db.commit()
                count += 1
            except Exception as exc:  # pragma: no cover
                self.db.rollback()
                logger.exception("Auto-revert of campaign %s failed: %s", campaign.id, exc)
        return count

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def _plan_name(self, plan_id: int) -> Optional[str]:
        p = self.db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        return p.name if p else None

    def _serialize(self, c: PromoPlanCampaign) -> dict:
        return {
            "id": c.id,
            "name": c.name,
            "status": getattr(c.status, "value", c.status),
            "target_plan_id": c.target_plan_id,
            "target_plan_name": self._plan_name(c.target_plan_id),
            "starts_at": c.starts_at.isoformat() if c.starts_at else None,
            "ends_at": c.ends_at.isoformat() if c.ends_at else None,
            "reverted_at": c.reverted_at.isoformat() if c.reverted_at else None,
            "tenant_count": c.tenant_count,
            "message": c.message,
            "created_by": c.created_by_name,
            "created_at": c.date_created.isoformat() if getattr(c, "date_created", None) else None,
        }

    def list_campaigns(self) -> list[dict]:
        rows = (
            self.db.query(PromoPlanCampaign)
            .order_by(PromoPlanCampaign.id.desc())
            .all()
        )
        return [self._serialize(c) for c in rows]

    def get_campaign(self, campaign_id: int) -> dict:
        c = self.db.query(PromoPlanCampaign).filter(
            PromoPlanCampaign.id == campaign_id).first()
        if not c:
            raise NotFoundError(message="Campaign not found.")
        data = self._serialize(c)
        members = (
            self.db.query(PromoPlanMember)
            .filter(PromoPlanMember.campaign_id == campaign_id)
            .all()
        )
        data["members"] = [
            {
                "tenant_id": m.tenant_id,
                "original_plan_id": m.original_plan_id,
                "is_reverted": m.is_reverted,
                "reverted_at": m.reverted_at.isoformat() if m.reverted_at else None,
            }
            for m in members
        ]
        return data
