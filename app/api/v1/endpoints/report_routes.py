from typing import Annotated, Optional, List
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date

from app.core.database import get_db, get_master_db
from app.schemas.report_schemas import (
    TenantFinancialSummary, TenantOperationalSummary, PlatformDashboardSchema,
    ClinicalAnalyticsSummary, InventorySummary, WorkforceSummary, AggregationSummaryReport
)
from app.services.report_service import ReportService
from app.dependencies.role import require_permission
from app.core.dependencies import CurrentSaaSAdmin

router = APIRouter(prefix="/reports", tags=["Reporting & Analytics"])

@router.get("/financial-summary", response_model=TenantFinancialSummary)
def get_financial_summary(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("REPORT_READ"))],
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    """Get financial summary for the current tenant."""
    return ReportService(db).get_tenant_financial_summary(start_date, end_date)

@router.get("/clinical-summary", response_model=ClinicalAnalyticsSummary)
def get_clinical_summary(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("REPORT_READ"))]
):
    """Get clinical analytics (diagnoses, visit trends) for the current tenant."""
    return ReportService(db).get_clinical_summary()

@router.get("/inventory-summary", response_model=InventorySummary)
def get_inventory_summary(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("REPORT_READ"))]
):
    """Get inventory & supply summary for the current tenant."""
    return ReportService(db).get_inventory_summary()

@router.get("/workforce-summary", response_model=WorkforceSummary)
def get_workforce_summary(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("REPORT_READ"))]
):
    """Get workforce reports (staff counts, shifts) for the current tenant."""
    return ReportService(db).get_workforce_summary()

@router.get("/aggregation-summary", response_model=AggregationSummaryReport)
def get_aggregation_summary(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("REPORT_READ"))]
):
    """Get a comprehensive aggregation summary report for the dashboard."""
    return ReportService(db).get_aggregation_summary()

@router.post("/generate")
def generate_report(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("REPORT_GENERATE"))],
    report_type: str = Query(..., pattern="^(financial|clinical|inventory|workforce|comprehensive)$"),
    file_type: str = Query("pdf", pattern="^(pdf|excel)$")
):
    """
    Generate a report on the fly and stream it to the client.
    Does not use S3; generates directly from the Tenant Database.
    """
    buffer, filename = ReportService(db).generate_on_the_fly_report(report_type, file_type)
    
    media_type = "application/pdf" if file_type == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return StreamingResponse(
        buffer,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/operational-summary", response_model=TenantOperationalSummary)
def get_operational_summary(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("REPORT_READ"))]
):
    """Get basic operational metrics for the current tenant."""
    return ReportService(db).get_tenant_operational_summary()

@router.get("/platform-overview", response_model=PlatformDashboardSchema, tags=["SaaS Admin"])
def get_platform_overview(
    db: Annotated[Session, Depends(get_master_db)],
    _: CurrentSaaSAdmin
):
    """Get platform-wide overview for SaaS Admins."""
    return ReportService(db).get_platform_admin_stats()
