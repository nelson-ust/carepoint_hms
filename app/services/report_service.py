from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import date, datetime
from typing import Optional

from app.models.all_models import Invoice, Payment, Patient, Visit, Admission, StaffProfile, Tenant, TenantSubscription, TenantUsage
from app.schemas.report_schemas import TenantFinancialSummary, TenantOperationalSummary, PlatformDashboardSchema
from app.core.database import get_master_db_context

class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def get_tenant_financial_summary(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> TenantFinancialSummary:
        """
        Aggregates financial data for the current tenant.
        """
        query_invoices = self.db.query(
            func.sum(Invoice.total_amount).label("total_invoiced"),
            func.sum(Invoice.amount_paid).label("total_paid")
        )
        
        query_payments = self.db.query(func.sum(Payment.amount).label("total_revenue"))
        
        if start_date:
            query_invoices = query_invoices.filter(Invoice.invoice_date >= start_date)
            query_payments = query_payments.filter(Payment.paid_at >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            query_invoices = query_invoices.filter(Invoice.invoice_date <= end_date)
            query_payments = query_payments.filter(Payment.paid_at <= datetime.combine(end_date, datetime.max.time()))

        inv_stats = query_invoices.first()
        pay_stats = query_payments.first()

        return TenantFinancialSummary(
            total_revenue=float(pay_stats.total_revenue or 0),
            total_invoiced=float(inv_stats.total_invoiced or 0),
            total_paid=float(inv_stats.total_paid or 0)
        )

    def get_tenant_operational_summary(self) -> TenantOperationalSummary:
        """
        Aggregates operational metrics for the current tenant.
        """
        return TenantOperationalSummary(
            total_patients=self.db.query(Patient).count(),
            total_active_visits=self.db.query(Visit).filter(Visit.is_active.is_(True)).count(),
            total_admissions=self.db.query(Admission).count(),
            total_staff=self.db.query(StaffProfile).count()
        )

    def get_platform_admin_stats(self) -> PlatformDashboardSchema:
        """
        Aggregates platform-wide metrics for SaaS admins.
        Connects to Master DB.
        """
        with get_master_db_context() as master_db:
            total_tenants = master_db.query(Tenant).count()
            active_tenants = master_db.query(Tenant).filter(Tenant.status == "ACTIVE").count()
            
            # Aggregate usage metrics
            usage_stats = master_db.query(
                func.sum(TenantUsage.api_call_count).label("total_api_calls"),
                func.sum(TenantUsage.transaction_count).label("total_transactions")
            ).first()

            return PlatformDashboardSchema(
                total_tenants=total_tenants,
                active_tenants=active_tenants,
                total_revenue_platform=0.0, # Would require summing subscriptions
                total_api_calls=usage_stats.total_api_calls or 0,
                system_health_status="HEALTHY"
            )
