from typing import List, Optional
from pydantic import BaseModel
from datetime import date

class TenantFinancialSummary(BaseModel):
    total_revenue: float
    total_invoiced: float
    total_paid: float
    currency: str = "NGN"

class TenantOperationalSummary(BaseModel):
    total_patients: int
    total_active_visits: int
    total_admissions: int
    total_staff: int

class PlatformDashboardSchema(BaseModel):
    total_tenants: int
    active_tenants: int
    total_revenue_platform: float
    total_api_calls: int
    system_health_status: str
