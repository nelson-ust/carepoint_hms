from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime

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

class ClinicalAnalyticsSummary(BaseModel):
    total_diagnoses: int
    top_diagnoses: List[dict]  # e.g. [{"name": "Malaria", "count": 120}]
    visit_trends: List[dict]    # e.g. [{"date": "2023-01-01", "count": 45}]
    mortality_rate: float = 0.0

class InventorySummary(BaseModel):
    total_items: int
    low_stock_items: int
    total_stock_value: float
    recent_stock_movements: List[dict]

class WorkforceSummary(BaseModel):
    total_staff: int
    staff_by_department: List[dict]
    active_shifts_today: int
    attendance_rate: float = 0.0

class AggregationSummaryReport(BaseModel):
    generated_at: datetime
    financial: TenantFinancialSummary
    clinical: ClinicalAnalyticsSummary
    inventory: InventorySummary
    workforce: WorkforceSummary
    tenant_logo_url: Optional[str] = None

class ReportDownloadSchema(BaseModel):
    report_id: str
    report_name: str
    file_type: str # "pdf" or "excel"
    download_url: str
    size_mb: float
    generated_at: datetime

class PlatformDashboardSchema(BaseModel):
    total_tenants: int
    active_tenants: int
    total_revenue_platform: float
    total_api_calls: int
    system_health_status: str
