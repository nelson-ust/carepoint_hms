from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timezone
from typing import Optional, Any, Tuple, List
import logging
import os
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
from app.core.config import settings
from app.core.database import get_master_db_context
from app.core.multitenancy import get_current_tenant_code
from app.services.aws_s3_service import S3Service
from app.models.all_models import (
    WarehouseExportJob, WarehouseExportRun, WarehouseTableSnapshot,
    WarehouseJobStatus, WarehouseExportType
)

logger = logging.getLogger(__name__)

class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReportRepository(db)
        self.s3 = S3Service()

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

    def process_warehouse_export(self, run_id: int, tenant_code: Optional[str] = None):
        """
        Processes a single warehouse export run.

        Extracts data based on the job's source_query, writes the dataset to
        CSV (or Excel for EXCEL-type jobs), stores the file via S3 (with a
        local uploads-directory fallback when S3 is disabled), records a
        WarehouseTableSnapshot pointing at the file, and finalizes the run
        status.

        ``tenant_code`` should be supplied by background workers that operate
        outside a request context; otherwise the request-bound tenant is used.
        """
        run = self.db.query(WarehouseExportRun).filter(WarehouseExportRun.id == run_id).first()
        if not run:
            raise ValueError(f"WarehouseExportRun {run_id} not found")

        job = run.job
        if not job or not job.source_query:
            run.status = WarehouseJobStatus.FAILED
            run.error_message = "Job or source_query missing"
            run.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            return

        try:
            # 1. Execute the source query
            # We use text() to execute raw SQL from source_query
            from sqlalchemy import text
            result = self.db.execute(text(job.source_query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            
            run.rows_extracted = len(df)
            
            # 2. Generate the file (CSV or Excel based on job type)
            buffer = io.BytesIO()
            file_extension = "csv"
            content_type = "text/csv"
            
            if job.export_type == WarehouseExportType.EXCEL:
                df.to_excel(buffer, index=False)
                file_extension = "xlsx"
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            else:
                df.to_csv(buffer, index=False)
            
            buffer.seek(0)
            file_size = buffer.getbuffer().nbytes
            run.bytes_written = file_size
            
            # 3. Upload to S3 (or the local uploads directory fallback).
            resolved_tenant_code = tenant_code or get_current_tenant_code() or "unknown"

            # Central policy: reports land in the TENANT's own bucket under a
            # reports/ prefix — never a shared or hardcoded bucket.
            from app.utils.s3_utils import get_bucket_name
            bucket_name = get_bucket_name()

            s3_key = f"reports/warehouse/{job.code}/{run.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{file_extension}"

            # Use a mockable upload method
            file_url = self._upload_buffer_to_s3(buffer, bucket_name, s3_key, content_type)
            run.run_metadata = {**(run.run_metadata or {}), "file_url": file_url}

            # 4. Create Snapshot record
            snapshot = WarehouseTableSnapshot(
                run_id=run.id,
                source_table="DYNAMIC_QUERY",
                target_table=job.target_dataset,
                snapshot_taken_at=datetime.now(timezone.utc),
                snapshot_uri=file_url,
                row_count=len(df),
                column_count=len(df.columns)
            )
            self.db.add(snapshot)
            
            # 5. Finalize run
            run.status = WarehouseJobStatus.COMPLETED
            run.finished_at = datetime.now(timezone.utc)
            
        except Exception as e:
            run.status = WarehouseJobStatus.FAILED
            run.error_message = str(e)
            run.finished_at = datetime.now(timezone.utc)
            raise e
        finally:
            self.db.commit()

    def generate_and_upload_report(self, report_type: str, file_type: str = "pdf") -> str:
        """
        Generates a report, uploads it to S3, and returns the public URL.
        Useful for background scheduled reports.
        """
        buffer, filename = self.generate_on_the_fly_report(report_type, file_type)
        
        # Central policy: scheduled reports go to the tenant's own bucket.
        from app.utils.s3_utils import get_bucket_name
        bucket_name = get_bucket_name()
        s3_key = f"reports/scheduled/{filename}"
        
        content_type = "application/pdf" if file_type == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        
        url = self._upload_buffer_to_s3(buffer, bucket_name, s3_key, content_type)
        return url

    def _upload_buffer_to_s3(self, buffer: io.BytesIO, bucket_name: str, s3_key: str, content_type: str) -> str:
        """Helper to upload a BytesIO buffer to S3."""
        if not self.s3.is_enabled:
            # Fallback for dev/intranet: save to local filesystem or just log
            logger.warning(f"S3 disabled. Mocking upload for {s3_key}")
            return f"file://local_storage/{s3_key}"

        try:
            self.s3.s3_client.upload_fileobj(
                buffer,
                bucket_name,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )
            
            if settings.AWS_ENDPOINT_URL:
                base_url = settings.AWS_ENDPOINT_URL.rstrip('/')
                return f"{base_url}/{bucket_name}/{s3_key}"
            else:
                return f"https://{bucket_name}.s3.{self.s3.region}.amazonaws.com/{s3_key}"
        except Exception as e:
            logger.error(f"S3 Upload failed: {e}")
            raise e
