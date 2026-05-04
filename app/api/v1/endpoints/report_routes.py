from typing import Annotated, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date

from app.core.database import get_db, get_master_db
from app.schemas.report_schemas import TenantFinancialSummary, TenantOperationalSummary, PlatformDashboardSchema
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
    """
    Get financial summary for the current tenant.
    """
    return ReportService(db).get_tenant_financial_summary(start_date, end_date)

@router.get("/operational-summary", response_model=TenantOperationalSummary)
def get_operational_summary(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("REPORT_READ"))]
):
    """
    Get operational metrics (patients, visits, staff) for the current tenant.
    """
    return ReportService(db).get_tenant_operational_summary()

@router.get("/platform-overview", response_model=PlatformDashboardSchema, tags=["SaaS Admin"])
def get_platform_overview(
    db: Annotated[Session, Depends(get_master_db)],
    _: CurrentSaaSAdmin
):
    """
    Get platform-wide overview for SaaS Admins.
    """
    return ReportService(db).get_platform_admin_stats()
