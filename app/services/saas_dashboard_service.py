# app/services/saas_dashboard_service.py
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal

from app.models.all_models import Tenant, TenantSubscription, SubscriptionPlan, SaaSNotification
from app.core.enums import UserStatus, SubscriptionStatus, SubscriptionInterval
from app.schemas.saas_dashboard_schemas import (
    SaaSDashboardMetricsSchema,
    MetricBreakdown,
    RecentNotificationSchema
)

class SaaSDashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_dashboard_metrics(self) -> SaaSDashboardMetricsSchema:
        # Total Tenants
        total_tenants = self.db.query(func.count(Tenant.id)).scalar() or 0
        active_tenants = self.db.query(func.count(Tenant.id)).filter(Tenant.status == UserStatus.ACTIVE).scalar() or 0
        pending_tenants = self.db.query(func.count(Tenant.id)).filter(Tenant.status == UserStatus.PENDING).scalar() or 0
        suspended_tenants = self.db.query(func.count(Tenant.id)).filter(Tenant.status == UserStatus.SUSPENDED).scalar() or 0

        # Total MRR
        # Sum of price from Active Subscriptions joined with SubscriptionPlan
        mrr_result = (
            self.db.query(func.sum(SubscriptionPlan.price))
            .join(TenantSubscription, TenantSubscription.plan_id == SubscriptionPlan.id)
            .filter(TenantSubscription.status == SubscriptionStatus.ACTIVE)
            .scalar()
        )
        total_mrr = mrr_result if mrr_result else Decimal("0.00")

        # Subscription Breakdown
        breakdown_query = (
            self.db.query(SubscriptionPlan.name, func.count(TenantSubscription.id))
            .join(TenantSubscription, TenantSubscription.plan_id == SubscriptionPlan.id)
            .filter(TenantSubscription.status == SubscriptionStatus.ACTIVE)
            .group_by(SubscriptionPlan.name)
            .all()
        )
        subscription_breakdown = [
            MetricBreakdown(label=name, count=count) for name, count in breakdown_query
        ]

        # Recent Notifications
        recent_notifs = (
            self.db.query(SaaSNotification)
            .order_by(SaaSNotification.date_created.desc())
            .limit(10)
            .all()
        )
        
        recent_notifications = [
            RecentNotificationSchema(
                id=notif.id,
                subject=notif.subject,
                body=notif.body,
                status=notif.status.name if hasattr(notif.status, 'name') else str(notif.status),
                is_read=notif.is_read,
                created_at=notif.date_created.isoformat() if getattr(notif, 'date_created', None) else ""
            ) for notif in recent_notifs
        ]

        return SaaSDashboardMetricsSchema(
            total_tenants=total_tenants,
            active_tenants=active_tenants,
            pending_tenants=pending_tenants,
            suspended_tenants=suspended_tenants,
            total_mrr=total_mrr,
            subscription_breakdown=subscription_breakdown,
            recent_notifications=recent_notifications
        )


    # ------------------------------------------------------------------
    # Ecosystem analytics — the shape the SaaS Overview page consumes.
    # Computed from real tenant / subscription / notification data, with
    # graceful fallbacks so a fresh platform still renders meaningfully.
    # ------------------------------------------------------------------
    def get_ecosystem_metrics(self) -> dict:
        from datetime import datetime, timezone
        import calendar

        def _as_utc(dt):
            if dt is None:
                return None
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        ACTIVE_STATES = [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]

        total_tenants = self.db.query(func.count(Tenant.id)).filter(
            Tenant.is_deleted.is_(False)).scalar() or 0
        active_tenants = self.db.query(func.count(Tenant.id)).filter(
            Tenant.is_deleted.is_(False), Tenant.status == UserStatus.ACTIVE).scalar() or 0

        sub_rows = (
            self.db.query(
                TenantSubscription.tenant_id,
                SubscriptionPlan.name.label("plan_name"),
                SubscriptionPlan.price,
                SubscriptionPlan.annual_price,
                SubscriptionPlan.interval,
                TenantSubscription.start_date,
            )
            .join(SubscriptionPlan, SubscriptionPlan.id == TenantSubscription.plan_id)
            .filter(TenantSubscription.status.in_(ACTIVE_STATES),
                    TenantSubscription.is_deleted.is_(False))
            .all()
        )

        def monthly_of(price, annual_price, interval) -> float:
            base = float(price or 0)
            if interval == SubscriptionInterval.YEARLY:
                return (float(annual_price) if annual_price else base) / 12.0
            return base

        mrr = sum(monthly_of(r.price, r.annual_price, r.interval) for r in sub_rows)
        total_arr = round(mrr * 12.0, 2)

        # Plan distribution (percentages of active subscriptions).
        counts: dict[str, int] = {}
        for r in sub_rows:
            counts[r.plan_name] = counts.get(r.plan_name, 0) + 1
        total_subs = sum(counts.values())
        plan_distribution = []
        if total_subs > 0:
            for name, c in sorted(counts.items(), key=lambda kv: -kv[1]):
                plan_distribution.append({"name": name, "value": round(c * 100.0 / total_subs, 1)})
        elif total_tenants > 0:
            plan_distribution = [{"name": "No active plan", "value": 100.0}]

        # Top tenants by annualized revenue.
        tenant_rev: dict[int, float] = {}
        for r in sub_rows:
            tenant_rev[r.tenant_id] = tenant_rev.get(r.tenant_id, 0.0) + monthly_of(r.price, r.annual_price, r.interval) * 12.0
        tenants = (self.db.query(Tenant).filter(Tenant.is_deleted.is_(False))
                   .order_by(Tenant.date_created.desc()).limit(100).all())
        top = [{"id": t.id, "name": t.name, "code": t.code,
                "revenue": round(tenant_rev.get(t.id, 0.0), 2), "growth": 0.0} for t in tenants]
        top.sort(key=lambda x: x["revenue"], reverse=True)
        top_tenants = top[:5]

        # Recent activity: SaaS notifications, else recent tenant onboardings.
        recent_activities = []
        try:
            notifs = (self.db.query(SaaSNotification)
                      .order_by(SaaSNotification.date_created.desc()).limit(8).all())
        except Exception:
            notifs = []
        for n in notifs:
            recent_activities.append({
                "id": str(n.id),
                "action": (n.subject or (n.body[:60] if n.body else "Notification")),
                "tenant": "Platform",
                "timestamp": (_as_utc(n.date_created) or now).isoformat(),
                "status": "SUCCESS",
            })
        if not recent_activities:
            for t in tenants[:8]:
                recent_activities.append({
                    "id": f"tenant-{t.id}",
                    "action": "Tenant onboarded",
                    "tenant": t.name,
                    "timestamp": (_as_utc(t.date_created) or now).isoformat(),
                    "status": "SUCCESS",
                })

        # Revenue trend — cumulative MRR and tenant count over the last 6 months.
        tenant_created = [_as_utc(row[0]) for row in self.db.query(Tenant.date_created)
                          .filter(Tenant.is_deleted.is_(False)).all()]
        sub_started = [(_as_utc(r.start_date), monthly_of(r.price, r.annual_price, r.interval)) for r in sub_rows]

        months = []
        yy, mm = now.year, now.month
        for _ in range(6):
            months.append((yy, mm))
            mm -= 1
            if mm == 0:
                mm, yy = 12, yy - 1
        months.reverse()

        trend = []
        for (y, m) in months:
            last_day = calendar.monthrange(y, m)[1]
            month_end = datetime(y, m, last_day, 23, 59, 59, tzinfo=timezone.utc)
            cum_tenants = sum(1 for d in tenant_created if d and d <= month_end)
            cum_mrr = sum(v for (sd, v) in sub_started if sd and sd <= month_end)
            trend.append({"month": calendar.month_abbr[m], "revenue": round(cum_mrr, 2), "users": cum_tenants})

        net_expansion = 0.0
        if len(trend) >= 2 and trend[-2]["revenue"] > 0:
            net_expansion = round((trend[-1]["revenue"] / trend[-2]["revenue"] - 1) * 100, 1)

        platform_uptime = 100.0
        try:
            from app.services.monitoring_service import monitoring_service
            platform_uptime = round(float(str(monitoring_service.get_uptime_display()).replace("%", "").strip()), 2)
        except Exception:
            platform_uptime = 100.0

        return {
            "total_arr": total_arr,
            "total_mrr": round(mrr, 2),
            "active_tenants": active_tenants,
            "total_tenants": total_tenants,
            "platform_uptime": platform_uptime,
            "net_expansion": net_expansion,
            "revenue_trend": trend,
            "plan_distribution": plan_distribution,
            "recent_activities": recent_activities,
            "top_tenants": top_tenants,
        }
