from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime
from typing import Optional, Any, Tuple, List
import uuid
import io
import pandas as pd
from fpdf import FPDF

from app.models.all_models import Tenant, TenantSubscription, TenantUsage, TenantSetting, Patient, Visit, Admission, StaffProfile
from app.schemas.report_schemas import (
    TenantFinancialSummary, TenantOperationalSummary, PlatformDashboardSchema,
    ClinicalAnalyticsSummary, InventorySummary, WorkforceSummary, AggregationSummaryReport,
    ReportDownloadSchema
)
from app.repositories.report_repository import ReportRepository
from app.core.database import get_master_db_context

class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReportRepository(db)

    def get_tenant_financial_summary(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> TenantFinancialSummary:
        inv_stats, pay_stats = self.repo.get_financial_stats(start_date, end_date)
        return TenantFinancialSummary(
            total_revenue=float(pay_stats.total_revenue or 0),
            total_invoiced=float(inv_stats.total_invoiced or 0),
            total_paid=float(inv_stats.total_paid or 0)
        )

    def get_clinical_summary(self) -> ClinicalAnalyticsSummary:
        stats = self.repo.get_clinical_stats()
        return ClinicalAnalyticsSummary(**stats)

    def get_inventory_summary(self) -> InventorySummary:
        stats = self.repo.get_inventory_stats()
        return InventorySummary(**stats)

    def get_workforce_summary(self) -> WorkforceSummary:
        stats = self.repo.get_workforce_stats()
        return WorkforceSummary(**stats)

    def get_aggregation_summary(self) -> AggregationSummaryReport:
        settings = self.db.query(TenantSetting).first()
        logo_url = settings.logo_url if settings else None

        return AggregationSummaryReport(
            generated_at=datetime.now(),
            financial=self.get_tenant_financial_summary(),
            clinical=self.get_clinical_summary(),
            inventory=self.get_inventory_summary(),
            workforce=self.get_workforce_summary(),
            tenant_logo_url=logo_url
        )

    def generate_on_the_fly_report(self, report_type: str, file_type: str = "pdf") -> Tuple[io.BytesIO, str]:
        data = {}
        if report_type == "financial":
            data = self.get_tenant_financial_summary().model_dump()
        elif report_type == "clinical":
            data = self.get_clinical_summary().model_dump()
        elif report_type == "inventory":
            data = self.get_inventory_summary().model_dump()
        elif report_type == "workforce":
            data = self.get_workforce_summary().model_dump()
        elif report_type == "comprehensive":
            data = self.get_aggregation_summary().model_dump()

        filename = f"{report_type}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_type}"
        
        if file_type == "pdf":
            buffer = self._generate_pdf(report_type, data)
        else:
            buffer = self._generate_excel(report_type, data)
            
        return buffer, filename

    def _generate_pdf(self, title: str, data: dict) -> io.BytesIO:
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 15, f"{title.upper()} REPORT", ln=True, align='C')
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
        pdf.ln(10)

        # We process the data recursively to build tables
        self._process_data_to_pdf_sections(pdf, data)

        buffer = io.BytesIO()
        pdf_str = pdf.output(dest='S').encode('latin1')
        buffer.write(pdf_str)
        buffer.seek(0)
        return buffer

    def _process_data_to_pdf_sections(self, pdf: FPDF, data: dict, level: int = 0):
        scalars = []
        nested_dicts = []
        nested_lists = []

        for k, v in data.items():
            if isinstance(v, dict):
                nested_dicts.append((k, v))
            elif isinstance(v, list):
                nested_lists.append((k, v))
            else:
                scalars.append([k.replace('_', ' ').title(), str(v)])

        # Draw scalars table first
        if scalars:
            if level > 0:
                pdf.set_font("Arial", 'B', 12)
                # No specific title for scalars if we're in a nested dict, they just go under the parent
            
            self._draw_pdf_table(pdf, ["Field", "Value"], scalars)
            pdf.ln(5)

        # Draw nested lists (tables with multiple columns)
        for k, v in nested_lists:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, k.replace('_', ' ').title(), ln=True)
            
            if v and isinstance(v[0], dict):
                headers = [hk.replace('_', ' ').title() for hk in v[0].keys()]
                rows = [[str(rv) for rv in row.values()] for row in v]
                self._draw_pdf_table(pdf, headers, rows)
            elif v:
                self._draw_pdf_table(pdf, ["Item"], [[str(i)] for i in v])
            pdf.ln(5)

        # Draw nested dicts recursively
        for k, v in nested_dicts:
            pdf.set_font("Arial", 'B', 14 if level == 0 else 12)
            pdf.set_text_color(0, 51, 102) # Dark blue for section headers
            pdf.cell(0, 12, k.replace('_', ' ').title(), ln=True)
            pdf.set_text_color(0, 0, 0)
            self._process_data_to_pdf_sections(pdf, v, level + 1)

    def _draw_pdf_table(self, pdf: FPDF, headers: List[str], rows: List[List[str]]):
        if not headers: return
        
        pdf.set_font("Arial", 'B', 10)
        # Dynamic column width based on total width
        page_width = pdf.w - 2 * pdf.l_margin
        col_width = page_width / len(headers)
        
        # Draw Headers
        pdf.set_fill_color(230, 230, 250) # Light lavender
        for header in headers:
            pdf.cell(col_width, 10, header, border=1, fill=True, align='C')
        pdf.ln()
        
        # Draw Rows
        pdf.set_font("Arial", size=9)
        for row in rows:
            # Calculate height needed for this row (supporting multi-line if needed, but for now simple)
            # Find max height for any cell in the row
            row_height = 8
            for col in row:
                pdf.cell(col_width, row_height, str(col), border=1, align='L')
            pdf.ln()

    def _generate_excel(self, title: str, data: dict) -> io.BytesIO:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            self._process_data_to_excel_sheets(writer, data, "Summary")

        buffer.seek(0)
        return buffer

    def _process_data_to_excel_sheets(self, writer: pd.ExcelWriter, data: dict, sheet_name: str):
        scalars = {k.replace('_', ' ').title(): [v] for k, v in data.items() if not isinstance(v, (dict, list))}
        
        if scalars:
            df_summary = pd.DataFrame(scalars)
            # If sheet exists, we append? No, ExcelWriter sheets are per-call
            # We'll just create sheets dynamically
            df_summary.to_excel(writer, index=False, sheet_name=sheet_name[:31])

        for k, v in data.items():
            if isinstance(v, list) and v:
                sub_name = k.replace('_', ' ').title()[:31]
                if isinstance(v[0], dict):
                    pd.DataFrame(v).to_excel(writer, index=False, sheet_name=sub_name)
                else:
                    pd.DataFrame({k: v}).to_excel(writer, index=False, sheet_name=sub_name)
            elif isinstance(v, dict):
                # Recurse for nested dicts but as new sheets or appended? 
                # Better as new sheets for clarity
                self._process_data_to_excel_sheets(writer, v, k.replace('_', ' ').title())

    def get_tenant_operational_summary(self) -> TenantOperationalSummary:
        return TenantOperationalSummary(
            total_patients=self.db.query(Patient).count(),
            total_active_visits=self.db.query(Visit).filter(Visit.is_active.is_(True)).count(),
            total_admissions=self.db.query(Admission).count(),
            total_staff=self.db.query(StaffProfile).count()
        )

    def get_platform_admin_stats(self) -> PlatformDashboardSchema:
        with get_master_db_context() as master_db:
            total_tenants = master_db.query(Tenant).count()
            active_tenants = master_db.query(Tenant).filter(Tenant.status == "ACTIVE").count()
            usage_stats = master_db.query(
                func.sum(TenantUsage.api_call_count).label("total_api_calls"),
                func.sum(TenantUsage.transaction_count).label("total_transactions")
            ).first()
            return PlatformDashboardSchema(
                total_tenants=total_tenants,
                active_tenants=active_tenants,
                total_revenue_platform=0.0,
                total_api_calls=usage_stats.total_api_calls or 0,
                system_health_status="HEALTHY"
            )
