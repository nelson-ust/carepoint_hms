"""
Report Worker for Carepoint HMS.

This worker polls for SCHEDULED warehouse export jobs and other background 
reporting tasks across all tenants. It utilizes the ReportService to execute 
the queries and generate the final output (PDF/Excel/JSON), which is then 
stored in S3.

Execution:
    python -m app.workers.report_worker
"""
import time
import signal
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import List, Tuple

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import MASTER_DATABASE_URL, get_engine_for_url
from app.core.cryptography import decrypt_string
from app.models.all_models import Tenant, WarehouseExportRun, WarehouseJobStatus
from app.services.report_service import ReportService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("report_worker")

# Global flag for graceful shutdown
keep_running = True

def signal_handler(sig, frame):
    global keep_running
    logger.info("Shutdown signal received. Finishing current report task...")
    keep_running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_active_tenants() -> List[Tuple[str, str]]:
    """Fetch active and provisioned tenants from master DB."""
    if not MASTER_DATABASE_URL:
        logger.error("MASTER_DATABASE_URL not set")
        return []
        
    master_engine = create_engine(MASTER_DATABASE_URL)
    tenants_data = []
    try:
        with Session(master_engine) as session:
            tenants = (
                session.query(Tenant)
                .filter(
                    Tenant.is_active.is_(True),
                    Tenant.is_provisioned.is_(True),
                    Tenant.is_deleted.is_(False)
                )
                .all()
            )
            for t in tenants:
                try:
                    url = decrypt_string(t.db_connection_string) if t.db_connection_string else None
                    if url:
                        tenants_data.append((t.code, url))
                except Exception as e:
                    logger.error(f"Failed to decrypt connection string for tenant {t.code}: {e}")
    except Exception as e:
        logger.error(f"Error fetching tenants from master: {e}")
    finally:
        master_engine.dispose()
    return tenants_data

def process_tenant_reports(tenant_code: str, db_url: str):
    """
    Process pending reports for a specific tenant.
    Specifically looks for WarehouseExportRun records in SCHEDULED status.
    """
    try:
        engine = get_engine_for_url(db_url)
        with Session(engine) as tenant_db:
            # 1. Find scheduled warehouse export runs
            scheduled_runs = (
                tenant_db.query(WarehouseExportRun)
                .filter(WarehouseExportRun.status == WarehouseJobStatus.SCHEDULED)
                .order_by(WarehouseExportRun.date_created.asc())
                .all()
            )
            
            if not scheduled_runs:
                return
                
            logger.info(f"Tenant {tenant_code}: Found {len(scheduled_runs)} scheduled warehouse runs")
            
            service = ReportService(tenant_db)
            for run in scheduled_runs:
                if not keep_running:
                    break
                    
                logger.info(f"Tenant {tenant_code}: Starting warehouse run {run.id} (Job: {run.job_id})")
                
                # Mark as running
                run.status = WarehouseJobStatus.RUNNING
                run.started_at = datetime.now(timezone.utc)
                tenant_db.commit()
                
                try:
                    # In a real implementation, ReportService would have a method to process this.
                    # For now, we simulate or call a future service method.
                    # We'll use a generic handler if it exists.
                    if hasattr(service, "process_warehouse_export"):
                        service.process_warehouse_export(run.id)
                    else:
                        # Placeholder for manual processing if service isn't updated yet
                        logger.warning(f"ReportService.process_warehouse_export not implemented for tenant {tenant_code}")
                        run.status = WarehouseJobStatus.FAILED
                        run.error_message = "ReportService.process_warehouse_export not implemented"
                        run.finished_at = datetime.now(timezone.utc)
                except Exception as e:
                    logger.error(f"Failed to process run {run.id} for tenant {tenant_code}: {e}")
                    run.status = WarehouseJobStatus.FAILED
                    run.error_message = str(e)
                    run.finished_at = datetime.now(timezone.utc)
                    run.run_metadata = {"traceback": traceback.format_exc()}
                
                tenant_db.commit()
                
    except Exception as e:
        logger.error(f"Error connecting to tenant {tenant_code} database: {e}")

def run_worker_loop():
    """Main worker loop."""
    logger.info("Report worker started.")
    # Default poll interval for reports is longer than notifications as they are heavy
    poll_interval = getattr(settings, "REPORT_WORKER_POLL_INTERVAL", 30)
    
    while keep_running:
        start_time = time.time()
        
        tenants = get_active_tenants()
        for tenant_code, db_url in tenants:
            if not keep_running:
                break
            
            process_tenant_reports(tenant_code, db_url)
        
        # Calculate sleep time
        elapsed = time.time() - start_time
        sleep_time = max(1.0, poll_interval - elapsed)
        
        if keep_running:
            logger.debug(f"Sleeping for {sleep_time:.2f}s...")
            time.sleep(sleep_time)

    logger.info("Report worker shut down gracefully.")

if __name__ == "__main__":
    run_worker_loop()
