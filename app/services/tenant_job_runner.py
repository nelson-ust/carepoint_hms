"""
Tenant-aware background job runner.

Discovers all active tenants in the master database, then for each tenant
opens a tenant-scoped session, sets the request-scoped tenant context, and
runs every :class:`TenantScheduledJob` whose ``next_run_at`` is due.

The runner is invoked periodically by ``app/scheduler.py`` (every minute).
Handlers are registered through :func:`register_handler`; the platform
ships with sensible defaults for reminders, invoice generation, backups,
and report generation but tenants and operators may extend the registry.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.orm import Session

from app.core.cryptography import decrypt_string
from app.core.database import MASTER_DATABASE_URL, get_engine_for_url
from app.core.multitenancy import clear_current_tenant, set_current_tenant
from app.models.all_models import Tenant, TenantScheduledJob


logger = logging.getLogger(__name__)


# Per-engine cache: maps an engine's URL → bool indicating whether the
# tenant_scheduled_job table is present. We cache so the dispatcher
# doesn't run a fresh ``information_schema`` query against every tenant
# on every tick. The cache is invalidated when the runner sees a fresh
# UndefinedTable error (e.g. after a migration runs the table appears).
_TABLE_PRESENCE_CACHE: dict[str, bool] = {}


def _scheduled_jobs_table_present(engine) -> bool:
    """
    Return True iff the ``tenant_scheduled_job`` table exists in the
    database behind ``engine``. Result is cached for the lifetime of the
    process; an UndefinedTable exception elsewhere clears the cache so a
    table that's been migrated in becomes visible on the next tick.

    Also caches "False" when the underlying database has gone missing
    (PostgreSQL ``3D000`` / "database does not exist") so we don't keep
    re-checking every minute and spamming the log with stack traces.
    """
    key = str(engine.url)
    cached = _TABLE_PRESENCE_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        present = inspect(engine).has_table("tenant_scheduled_job")
    except Exception as exc:
        # Detect "missing tenant database" and downgrade to a single
        # WARNING line rather than the full stack trace.
        try:
            from app.db_sync import _is_missing_db_error
        except Exception:
            _is_missing_db_error = lambda _e: False  # type: ignore[assignment]

        if _is_missing_db_error(exc):
            logger.warning(
                "Tenant-job runner: skipping %s — physical database missing. "
                "Run `python -m app.init_db --heal-missing-tenant-dbs` to clean "
                "up master records.",
                key,
            )
            # Cache the False so we stop checking on every tick.
            _TABLE_PRESENCE_CACHE[key] = False
            return False
        logger.warning("Tenant-job runner: inspector failed for %s: %s", key, exc)
        return False
    _TABLE_PRESENCE_CACHE[key] = present
    return present


def reset_table_presence_cache() -> None:
    """Drop the cached ``has_table`` results — call after running a migration."""
    _TABLE_PRESENCE_CACHE.clear()


HandlerFn = Callable[[Session, "TenantScheduledJob"], Dict[str, Any]]


_HANDLER_REGISTRY: Dict[str, HandlerFn] = {}


def register_handler(name: str) -> Callable[[HandlerFn], HandlerFn]:
    """
    Decorator: register a callable as a job handler.

    Handlers receive the active tenant's :class:`Session` and the
    :class:`TenantScheduledJob` row, and return a dict that is stored in
    ``last_error`` on failure or logged on success.
    """

    def _wrap(fn: HandlerFn) -> HandlerFn:
        _HANDLER_REGISTRY[name] = fn
        return fn

    return _wrap


def get_handler(name: str) -> Optional[HandlerFn]:
    return _HANDLER_REGISTRY.get(name)


# ---------------------------------------------------------------------------
# Tenant iteration
# ---------------------------------------------------------------------------


def _iter_active_tenants() -> list[Tenant]:
    if not MASTER_DATABASE_URL:
        logger.warning("MASTER_DATABASE_URL is not set; tenant job runner skipped.")
        return []

    try:
        master_engine = create_engine(MASTER_DATABASE_URL, future=True)
        try:
            with Session(master_engine) as master_db:
                return (
                    master_db.query(Tenant)
                    .filter(
                        Tenant.is_active.is_(True),
                        Tenant.is_provisioned.is_(True),
                        Tenant.is_deleted.is_(False),
                    )
                    .all()
                )
        finally:
            master_engine.dispose()
    except Exception as exc:
        logger.error("Tenant job runner: failed to connect to master database: %s", exc)
        return []


def _resolve_tenant_db_url(tenant: Tenant) -> Optional[str]:
    if not tenant.db_connection_string:
        return None
    try:
        return decrypt_string(tenant.db_connection_string)
    except Exception:
        # Fall back to treating the field as plaintext (legacy data).
        return tenant.db_connection_string


# ---------------------------------------------------------------------------
# Schedule arithmetic
# ---------------------------------------------------------------------------


def _compute_next_run(job: TenantScheduledJob, *, base: datetime) -> datetime:
    """
    Determine the next scheduled run for ``job``.

    Cron expressions are honored when possible (via croniter, which ships
    with APScheduler); otherwise we fall back to a plain interval window.
    """
    if job.schedule_cron:
        try:
            from croniter import croniter  # type: ignore

            it = croniter(job.schedule_cron, base)
            return it.get_next(datetime).astimezone(timezone.utc)
        except Exception as exc:
            logger.warning("croniter unavailable or cron invalid (%s); using interval fallback", exc)

    minutes = int(job.schedule_interval_minutes or 60)
    return base + timedelta(minutes=max(minutes, 1))


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_tenant_jobs() -> dict[str, Any]:
    """
    Tick: scan every active tenant, run any due jobs, update bookkeeping.

    Returns a summary with counts so the caller (the global scheduler) can
    log a single line per tick.
    """
    summary = {"tenants": 0, "skipped_unmigrated": 0, "jobs_run": 0, "jobs_failed": 0}

    for tenant in _iter_active_tenants():
        summary["tenants"] += 1
        db_url = _resolve_tenant_db_url(tenant)
        if not db_url:
            continue

        engine = get_engine_for_url(db_url)

        # Short-circuit before opening a session if the tenant DB hasn't
        # been migrated yet. This avoids the per-minute UndefinedTable
        # spam when new tenant tables (e.g. ``tenant_scheduled_job``) are
        # added to the model but a tenant DB hasn't been forward-migrated.
        if not _scheduled_jobs_table_present(engine):
            summary["skipped_unmigrated"] += 1
            logger.debug(
                "Tenant-job runner: skipping tenant=%s (tenant_scheduled_job missing — run "
                "`python -m app.init_db --sync-tenants`)",
                tenant.code,
            )
            continue

        with Session(engine) as tenant_db:
            try:
                set_current_tenant(tenant)
                _run_due_jobs(tenant_db, summary)
            except (ProgrammingError, OperationalError) as exc:
                # Most likely a UndefinedTable / UndefinedColumn during a
                # rolling deploy. Drop the cache entry so the next tick
                # re-checks (the table may appear after a migration), and
                # continue on to the next tenant.
                _TABLE_PRESENCE_CACHE.pop(str(engine.url), None)
                summary["skipped_unmigrated"] += 1
                logger.warning(
                    "Tenant-job runner: schema drift on tenant=%s: %s. "
                    "Run `python -m app.init_db --sync-tenants` to migrate.",
                    tenant.code,
                    str(exc).splitlines()[0],
                )
            finally:
                clear_current_tenant()

    return summary


def _run_due_jobs(tenant_db: Session, summary: dict) -> None:
    now = datetime.now(timezone.utc)

    due_jobs = (
        tenant_db.query(TenantScheduledJob)
        .filter(
            TenantScheduledJob.is_enabled.is_(True),
            TenantScheduledJob.is_deleted.is_(False),
        )
        .all()
    )

    for job in due_jobs:
        next_run = job.next_run_at
        if next_run is not None and next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)

        if next_run is not None and next_run > now:
            continue

        handler = get_handler(job.handler)
        if handler is None:
            job.last_status = "FAILED"
            job.last_error = f"unknown handler: {job.handler}"
            job.last_run_at = now
            job.next_run_at = _compute_next_run(job, base=now)
            tenant_db.commit()
            summary["jobs_failed"] += 1
            continue

        started = datetime.now(timezone.utc)
        try:
            result = handler(tenant_db, job) or {}
            job.last_status = "OK"
            job.last_error = None
            summary["jobs_run"] += 1
            logger.info(
                "tenant_job: ran %s for job=%s result=%s",
                job.handler,
                job.job_code,
                {k: v for k, v in result.items() if k != "details"},
            )
        except Exception as exc:
            job.last_status = "FAILED"
            job.last_error = str(exc)[:1000]
            summary["jobs_failed"] += 1
            logger.exception("tenant_job: handler %s failed: %s", job.handler, exc)

        finished = datetime.now(timezone.utc)
        job.last_run_at = finished
        job.next_run_at = _compute_next_run(job, base=finished)
        job.run_count = (job.run_count or 0) + 1
        job.last_duration_ms = int((finished - started).total_seconds() * 1000)
        tenant_db.commit()


# ---------------------------------------------------------------------------
# Built-in handlers (best-effort; degrade if optional services are absent).
# ---------------------------------------------------------------------------


@register_handler("appointment_reminders")
def _handler_appointment_reminders(db: Session, job: TenantScheduledJob) -> dict:
    """Send reminder notifications for upcoming appointments."""
    from app.core.enums import NotificationEvent
    from app.models.all_models import Appointment, User
    from app.services.notification_dispatcher import NotificationDispatcher

    horizon_hours = int((job.params or {}).get("horizon_hours", 24))
    cutoff = datetime.now(timezone.utc) + timedelta(hours=horizon_hours)

    try:
        upcoming = (
            db.query(Appointment)
            .filter(
                Appointment.scheduled_at <= cutoff,
                Appointment.scheduled_at >= datetime.now(timezone.utc),
                Appointment.is_deleted.is_(False),
            )
            .limit(500)
            .all()
        )
    except Exception:
        return {"sent": 0, "skipped": "appointments table unavailable"}

    dispatcher = NotificationDispatcher(db)
    sent = 0
    for appt in upcoming:
        user_id = getattr(appt, "patient_user_id", None) or getattr(appt, "user_id", None)
        if not user_id:
            continue
        user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
        if not user:
            continue
        dispatcher.dispatch(
            event=NotificationEvent.APPOINTMENT_REMINDER,
            recipients=[user],
            subject="Upcoming appointment reminder",
            body=f"You have an appointment scheduled at {appt.scheduled_at:%Y-%m-%d %H:%M}.",
            context={"appointment_id": appt.id},
        )
        sent += 1

    return {"sent": sent}


@register_handler("daily_backup")
def _handler_daily_backup(db: Session, job: TenantScheduledJob) -> dict:
    """Trigger the encrypted backup pipeline for the active tenant."""
    from app.core.multitenancy import get_current_tenant

    tenant = get_current_tenant()
    if tenant is None:
        return {"status": "skipped", "reason": "no tenant context"}

    try:
        from app.services.tenant_backup_service import TenantBackupService
    except Exception as exc:
        return {"status": "skipped", "reason": f"backup service unavailable: {exc}"}

    # create_backup() returns a summary dict, not an ORM record.
    backup = TenantBackupService(db, tenant_code=tenant.code).create_backup(triggered_by="SCHEDULED")
    return {"status": "ok", "backup_id": backup.get("backup_id"), "filename": backup.get("filename")}


@register_handler("invoice_generation")
def _handler_invoice_generation(db: Session, job: TenantScheduledJob) -> dict:
    """
    Hook for tenant-driven recurring invoice generation. The platform
    intentionally ships an empty default; tenants override by registering
    their own handler under ``invoice_generation`` or by storing the
    business logic in ``params``.
    """
    return {"status": "noop"}


@register_handler("report_generation")
def _handler_report_generation(db: Session, job: TenantScheduledJob) -> dict:
    """
    Hook for periodic report generation. 
    Params:
        report_code: str (financial, clinical, etc.)
        file_type: str (pdf, excel)
    """
    params = job.params or {}
    code = params.get("report_code")
    file_type = params.get("file_type", "pdf")
    
    if not code:
        return {"status": "noop", "reason": "Missing report_code in params"}
    
    try:
        from app.services.report_service import ReportService  # type: ignore
        service = ReportService(db)
        
        # If a specific method exists (e.g. generate_custom_thing), use it
        method = getattr(service, f"generate_{code}", None)
        if callable(method):
            method()
            return {"status": "ok", "method": f"generate_{code}"}
            
        # Otherwise use the generic background generation
        file_url = service.generate_and_upload_report(code, file_type)
        return {"status": "ok", "report_type": code, "file_url": file_url}
        
    except Exception as exc:
        logger.error(f"Report generation failed for job {job.id}: {exc}")
        return {"status": "failed", "reason": str(exc)}


@register_handler("payroll")
def _handler_payroll(db: Session, job: TenantScheduledJob) -> dict:
    """Hook for tenant-driven payroll runs. Default is a no-op."""
    return {"status": "noop"}
