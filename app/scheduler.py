# app/scheduler.py
from __future__ import annotations

"""
app.scheduler

Background task scheduling for the Carepoint Hospital Management System.

Purpose
-------
This module manages recurring system tasks such as:
- Daily bed-day rollover/billing.
- Expiring OTP challenges.
- Sending leave schedule reminders.
- Database maintenance tasks.

Implementation
--------------
Currently uses a simple APScheduler-based implementation.
"""

from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import MASTER_DATABASE_URL, get_engine_for_url
from app.core.logger import get_logger
from app.models.all_models import Tenant, Admission, PatientPortalOtp, UserSession
from app.services.admission_service import _OPEN_STATES
from app.utils.charge_capture import capture_bed_day_charges_for_admission
# from app.services.staff_leave_service import StaffLeaveService
from app.models.all_models import PatientPortalOtp, UserSession
from app.services.database_backup_service import DatabaseBackupService

try:
    from app.services.tenant_job_runner import run_tenant_jobs
except Exception:  # pragma: no cover
    run_tenant_jobs = None  # type: ignore[assignment]

try:
    from app.services.subscription_billing_service import SubscriptionBillingService
except Exception:  # pragma: no cover
    SubscriptionBillingService = None  # type: ignore[assignment]

try:
    from app.services.edge_sync_service import sweep_offline_nodes
except Exception:  # pragma: no cover
    sweep_offline_nodes = None  # type: ignore[assignment]

logger = get_logger(__name__)

# Global scheduler instance
_scheduler = BackgroundScheduler()


def _get_active_tenant_engines():
    """
    Fetch all active tenants from the Master Database and yield (code, engine).

    Each tenant's connection string is decrypted before being handed to the
    engine factory so jobs run against the live tenant DB, not the
    encrypted blob stored in master.
    """
    if not MASTER_DATABASE_URL:
        logger.warning("MASTER_DATABASE_URL is not set. Cannot fetch tenants.")
        return []

    from app.core.cryptography import decrypt_string

    master_engine = create_engine(MASTER_DATABASE_URL, future=True)
    try:
        with Session(master_engine) as master_db:
            tenants = (
                master_db.query(Tenant)
                .filter(
                    Tenant.is_active.is_(True),
                    Tenant.is_provisioned.is_(True),
                    Tenant.is_deleted.is_(False),
                )
                .all()
            )

            engines = []
            for tenant in tenants:
                try:
                    if not tenant.db_connection_string:
                        continue
                    try:
                        url = decrypt_string(tenant.db_connection_string)
                    except Exception:
                        url = tenant.db_connection_string
                    engine = get_engine_for_url(url)
                    engines.append((tenant.code, engine))
                except Exception as e:
                    logger.error(f"Failed to get engine for tenant {tenant.code}: {e}")

            return engines
    finally:
        master_engine.dispose()


def _run_daily_bed_day_rollover():
    """Execute billing rollover for all active tenants."""
    logger.info("Starting daily bed-day rollover across all tenants.")
    for tenant_code, engine in _get_active_tenant_engines():
        try:
            with Session(engine) as tenant_db:
                active_admissions = tenant_db.query(Admission).filter(
                    Admission.admission_status.in_(_OPEN_STATES)
                ).all()
                today = datetime.now(timezone.utc).date()
                
                captured_count = 0
                for admission in active_admissions:
                    summary = capture_bed_day_charges_for_admission(
                        tenant_db, admission=admission, through_date=today
                    )
                    captured_count += summary.get("charges_captured", 0)
                
                tenant_db.commit()
                logger.info(f"Completed rollover for tenant {tenant_code}: {captured_count} total charges captured.")
        except Exception as e:
            logger.error(f"Error during rollover for tenant {tenant_code}: {e}")


def _run_leave_reminders():
    """Execute leave reminders for all active tenants."""
    logger.info("Starting leave reminders dispatch across all tenants.")
    for tenant_code, engine in _get_active_tenant_engines():
        try:
            with Session(engine) as tenant_db:
                # service = StaffLeaveService(tenant_db)
                # service.trigger_due_reminders()
                pass
                logger.info(f"Completed leave reminders for tenant: {tenant_code}")
        except Exception as e:
            logger.error(f"Error during leave reminders for tenant {tenant_code}: {e}")


def _run_otp_cleanup():
    """Clean up expired OTPs and expired sessions across all tenants."""
    logger.info("Starting OTP and session cleanup across all tenants.")
    now = datetime.now(timezone.utc)
    for tenant_code, engine in _get_active_tenant_engines():
        try:
            with Session(engine) as tenant_db:
                # Clean expired OTPs
                deleted_otps = tenant_db.query(PatientPortalOtp).filter(
                    PatientPortalOtp.expires_at < now
                ).delete()
                
                # Clean expired sessions
                deleted_sessions = tenant_db.query(UserSession).filter(
                    UserSession.expires_at < now
                ).delete()
                
                tenant_db.commit()
                if deleted_otps > 0 or deleted_sessions > 0:
                    logger.info(f"Cleanup for {tenant_code}: {deleted_otps} OTPs, {deleted_sessions} sessions removed.")
        except Exception as e:
            logger.error(f"Error during cleanup for tenant {tenant_code}: {e}")


def _run_daily_backups():
    """Execute automated database backups for all active tenants."""
    logger.info("Starting automated daily backups across all tenants.")
    for tenant_code, engine in _get_active_tenant_engines():
        try:
            with Session(engine) as tenant_db:
                service = DatabaseBackupService(tenant_db, tenant_code)
                logger.info(f"Triggering backup for tenant: {tenant_code}")
                service.trigger_backup()
        except Exception as e:
            logger.error(f"Failed to run automated backup for tenant {tenant_code}: {e}")


def start_scheduler() -> None:
    """
    Idempotent start for the background task scheduler.
    """
    if _scheduler.running:
        logger.warning("Scheduler is already running.")
        return

    logger.info("Starting background task scheduler...")
    
    # Schedule Daily Bed-Day Rollover at 00:05 AM
    _scheduler.add_job(
        _run_daily_bed_day_rollover,
        trigger="cron",
        hour=0,
        minute=5,
        id="daily_bed_day_rollover",
        replace_existing=True,
    )
    
    # Schedule Leave Reminders at 08:00 AM
    _scheduler.add_job(
        _run_leave_reminders,
        trigger="cron",
        hour=8,
        minute=0,
        id="daily_leave_reminders",
        replace_existing=True,
    )
    
    # Schedule OTP & Session Cleanup every hour
    _scheduler.add_job(
        _run_otp_cleanup,
        trigger="interval",
        hours=1,
        id="hourly_otp_cleanup",
        replace_existing=True,
    )
    
    # Schedule Daily Backups at 01:00 AM
    _scheduler.add_job(
        _run_daily_backups,
        trigger="cron",
        hour=1,
        minute=0,
        id="daily_database_backups",
        replace_existing=True,
    )

    # Schedule the tenant-aware job dispatcher every minute. Each tick walks
    # all active tenants and runs any due TenantScheduledJob rows for them.
    if run_tenant_jobs is not None:
        _scheduler.add_job(
            _safe_run_tenant_jobs,
            trigger="interval",
            minutes=1,
            id="tenant_job_dispatcher",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    # Edge-node liveness sweep. Every 60s we flip nodes that missed
    # their heartbeat window to OFFLINE so the SaaS dashboard reflects
    # live connectivity state.
    if sweep_offline_nodes is not None:
        _scheduler.add_job(
            _safe_sweep_offline_nodes,
            trigger="interval",
            seconds=60,
            id="edge_node_offline_sweep",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    # Subscription billing — runs once a day at 02:30 to issue invoices for
    # subscriptions whose period is closing and to flip overdue invoices.
    if SubscriptionBillingService is not None:
        _scheduler.add_job(
            _safe_run_subscription_billing,
            trigger="cron",
            hour=2,
            minute=30,
            id="daily_subscription_billing",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    _scheduler.start()


def _safe_run_subscription_billing() -> None:
    """Daily billing tick — issue due invoices then sweep overdue ones."""
    if SubscriptionBillingService is None:
        return
    if not MASTER_DATABASE_URL:
        logger.warning("Subscription billing tick skipped: MASTER_DATABASE_URL is unset.")
        return

    master_engine = create_engine(MASTER_DATABASE_URL, future=True)
    try:
        with Session(master_engine) as master_db:
            service = SubscriptionBillingService(master_db)
            try:
                issued = service.generate_due_invoices()
                logger.info(
                    "Subscription billing: candidates=%s issued=%s skipped=%s",
                    issued.get("candidates"),
                    issued.get("issued"),
                    issued.get("skipped"),
                )
            except Exception as exc:
                logger.exception("generate_due_invoices failed: %s", exc)

            try:
                overdue = service.sweep_overdue()
                if overdue.get("marked_overdue"):
                    logger.info(
                        "Subscription billing: marked_overdue=%s",
                        overdue.get("marked_overdue"),
                    )
            except Exception as exc:
                logger.exception("sweep_overdue failed: %s", exc)
    finally:
        master_engine.dispose()


def _safe_sweep_offline_nodes() -> None:
    """Wrapper that swallows exceptions so a bad row doesn't kill the sweep."""
    if sweep_offline_nodes is None:
        return
    try:
        flipped = sweep_offline_nodes()
        if flipped:
            logger.info("Edge-node sweep: flipped %s node(s) to OFFLINE", flipped)
    except Exception as exc:
        logger.exception("Edge-node sweep raised: %s", exc)


def _safe_run_tenant_jobs() -> None:
    """Wrapper that swallows exceptions so a single bad tenant doesn't kill the dispatcher."""
    if run_tenant_jobs is None:
        return
    try:
        summary = run_tenant_jobs()
        if summary.get("jobs_run") or summary.get("jobs_failed"):
            logger.info(
                "Tenant job dispatcher tick: tenants=%s ran=%s failed=%s",
                summary.get("tenants"),
                summary.get("jobs_run"),
                summary.get("jobs_failed"),
            )
    except Exception as exc:
        logger.exception("Tenant job dispatcher tick raised: %s", exc)


def shutdown_scheduler() -> None:
    """
    Gracefully stop the background task scheduler.
    """
    if _scheduler.running:
        logger.info("Shutting down background task scheduler...")
        _scheduler.shutdown(wait=True)



'''
lsof -i :8005 -t | xargs kill


{
  "tenant_name": "St. Nicholas Hospital",
  "tenant_code": "stnicholas",
  "domain_url": "stnicholas.carepointhms.com",
  "plan_code": "ENTERPRISE",
  "admin_email": "admin@stnicholas.com",
  "admin_username": "stadmin",
  "admin_password": "SecurePassword123!",
  "admin_first_name": "Nelson",
  "admin_last_name": "Attah"
}

'''