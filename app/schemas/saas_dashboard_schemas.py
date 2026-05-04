# app/schemas/saas_dashboard_schemas.py
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal

class MetricBreakdown(BaseModel):
    label: str
    count: int

class RecentNotificationSchema(BaseModel):
    id: int
    subject: Optional[str] = None
    body: str
    status: str
    is_read: bool
    created_at: str

class SaaSDashboardMetricsSchema(BaseModel):
    total_tenants: int
    active_tenants: int
    pending_tenants: int
    suspended_tenants: int
    total_mrr: Decimal
    mrr_currency: str = "NGN"
    subscription_breakdown: List[MetricBreakdown] = []
    recent_notifications: List[RecentNotificationSchema] = []
