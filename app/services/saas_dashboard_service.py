# app/services/saas_dashboard_service.py
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal

from app.models.all_models import Tenant, TenantSubscription, SubscriptionPlan, SaaSNotification
from app.core.enums import UserStatus, SubscriptionStatus
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
