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

from sqlalchemy import inspect, or_
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.orm import Session

from app.core.cryptography import decrypt_string
from app.core.database import MASTER_DATABASE_URL, get_engine_for_url, get_master_engine
from app.core.multitenancy import clear_current_tenant, set_current_tenant
from app.models.all_models import Tenant, TenantScheduledJob


logger = logging.getLogger(__name__)

try:
    from app.core.config import settings as _settings
except Exception:  # pragma: no cover - config should always import
    _settings = None

def _stale_lease_minutes() -> int:
    """Minutes before a RUNNING job's lease is considered stale and reclaimed."""
    try:
        return max(int(getattr(_settings, "JOB_STALE_LEASE_MINUTES", 30) or 30), 1)
    except Exception:
        return 30


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
        # Reuse the process-wide cached master engine instead of building and
        # disposing a fresh engine (and its connection pool) on every tick.
        master_engine = get_master_engine()
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


def _job_timezone(job: TenantScheduledJob) -> Any:
    """
    Resolve the tzinfo used to interpret a job's cron expression.

    Precedence: the job's ``timezone`` column, then a ``timezone`` key inside
    ``params``, then UTC. An unknown name falls back to UTC rather than
    raising, so a bad value can never wedge the dispatcher.
    """
    name = (
        getattr(job, "timezone", None) or (job.params or {}).get("timezone") or ""
    ).strip()
    if not name or name.upper() == "UTC":
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        logger.warning(
            "Job %s: unknown timezone %r; falling back to UTC.",
            getattr(job, "job_code", "?"),
            name,
        )
        return timezone.utc


def _compute_next_run(
    job: TenantScheduledJob,
    *,
    base: datetime,
    prev: Optional[datetime] = None,
) -> datetime:
    """
    Determine the next scheduled run for ``job`` as a timezone-aware UTC time.

    Cron expressions are honoured via croniter and evaluated in the job's
    timezone (see :func:`_job_timezone`); otherwise a plain interval window is
    used. ``prev`` is the slot that just fired — basing the computation on it
    rather than on wall-clock ``base`` keeps a fixed cadence instead of
    drifting by each run's duration. A single catch-up cap avoids a backlog
    storm after downtime: if the computed time is already in the past we
    recompute once from ``base`` (now).
    """
    base = base if base.tzinfo else base.replace(tzinfo=timezone.utc)
    anchor = prev if prev is not None else base
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)

    if job.schedule_cron:
        try:
            from croniter import croniter  # type: ignore

            tz = _job_timezone(job)
            nxt = (
                croniter(job.schedule_cron, anchor.astimezone(tz))
                .get_next(datetime)
                .astimezone(timezone.utc)
            )
            if nxt <= base:
                # Missed one or more slots (downtime) — jump to the next slot
                # from now so we fire once, not once per missed slot.
                nxt = (
                    croniter(job.schedule_cron, base.astimezone(tz))
                    .get_next(datetime)
                    .astimezone(timezone.utc)
                )
            return nxt
        except Exception as exc:
            logger.warning(
                "croniter unavailable or cron invalid (%s); using interval fallback",
                exc,
            )

    minutes = max(int(job.schedule_interval_minutes or 60), 1)
    nxt = anchor + timedelta(minutes=minutes)
    if nxt <= base:
        nxt = base + timedelta(minutes=minutes)
    return nxt


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_tenant_jobs() -> dict[str, Any]:
    """
    Tick: scan every active tenant, run any due jobs, update bookkeeping.

    Concurrency model
    -----------------
    The global scheduler already wraps this tick in a master-DB advisory lock
    (see ``app/scheduler.py``) so only one worker dispatches at a time. As a
    second line of defence, due jobs are claimed with ``FOR UPDATE SKIP
    LOCKED`` and their ``next_run_at`` is advanced *before* the handler runs,
    so a job can never be executed twice for the same slot even if two ticks
    overlap.

    Returns a summary with counts so the caller can log a single line per tick.
    """
    summary = {"tenants": 0, "skipped_unmigrated": 0, "jobs_run": 0, "jobs_failed": 0, "stale_reaped": 0}

    for tenant in _iter_active_tenants():
        summary["tenants"] += 1
        db_url = _resolve_tenant_db_url(tenant)
        if not db_url:
            continue

        engine = get_engine_for_url(db_url)

        # Short-circuit before opening a session if the tenant DB hasn't been
        # migrated yet (avoids per-minute UndefinedTable spam).
        if not _scheduled_jobs_table_present(engine):
            summary["skipped_unmigrated"] += 1
            logger.debug(
                "Tenant-job runner: skipping tenant=%s (tenant_scheduled_job missing — "
                "run `python -m app.init_db --sync-tenants`)",
                tenant.code,
            )
            continue

        try:
            set_current_tenant(tenant)
            with Session(engine) as tenant_db:
                # Reclaim leases from runs whose worker died mid-execution so
                # the job stops showing as permanently RUNNING and recovers.
                summary["stale_reaped"] += _reap_stale_leases(tenant_db)
                claimed_ids = _claim_due_jobs(tenant_db)
                for job_id in claimed_ids:
                    _execute_claimed_job(tenant_db, job_id, summary)
        except (ProgrammingError, OperationalError) as exc:
            # Schema drift during a rolling deploy. Drop the cache entry so the
            # next tick re-checks, and continue to the next tenant.
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


def _reap_stale_leases(tenant_db: Session) -> int:
    """
    Reclaim leases for jobs stuck in RUNNING past the stale threshold.

    A job is marked RUNNING at claim time and cleared when it finishes. If
    the worker crashes or is restarted mid-run, the row stays RUNNING with a
    ``locked_at`` in the past. This bulk UPDATE flips such rows to STALE and
    clears the lease so they stop displaying as permanently running; their
    ``next_run_at`` was already advanced at claim time, so they simply resume
    on their normal schedule. The threshold must exceed the longest expected
    job (see ``JOB_STALE_LEASE_MINUTES``) so a legitimately long run is not
    reaped out from under itself.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_stale_lease_minutes())
    updated = (
        tenant_db.query(TenantScheduledJob)
        .filter(
            TenantScheduledJob.last_status == "RUNNING",
            TenantScheduledJob.locked_at.isnot(None),
            TenantScheduledJob.locked_at < cutoff,
        )
        .update(
            {
                TenantScheduledJob.last_status: "STALE",
                TenantScheduledJob.last_error: (
                    "Run did not complete (worker restarted or crashed); "
                    "lease reclaimed by the dispatcher."
                ),
                TenantScheduledJob.locked_at: None,
            },
            synchronize_session=False,
        )
    )
    if updated:
        tenant_db.commit()
        logger.warning("tenant_job: reclaimed %s stale RUNNING lease(s).", updated)
    return updated


def _claim_due_jobs(tenant_db: Session) -> list[int]:
    """
    Atomically claim all due jobs for the current tenant.

    Due rows are selected ``FOR UPDATE SKIP LOCKED`` (so a concurrent runner
    skips anything already claimed), their schedule is advanced to the next
    slot, their status is set to RUNNING, and the claim is committed. The
    advanced ``next_run_at`` is what prevents a second execution of the same
    slot. Returns the ids of the jobs this runner claimed.
    """
    now = datetime.now(timezone.utc)

    query = (
        tenant_db.query(TenantScheduledJob)
        .filter(
            TenantScheduledJob.is_enabled.is_(True),
            TenantScheduledJob.is_deleted.is_(False),
            or_(
                TenantScheduledJob.next_run_at.is_(None),
                TenantScheduledJob.next_run_at <= now,
            ),
        )
        .order_by(TenantScheduledJob.next_run_at.asc())
    )
    due_jobs = query.with_for_update(skip_locked=True).all()

    claimed: list[int] = []
    for job in due_jobs:
        prev_slot = job.next_run_at
        if prev_slot is not None and prev_slot.tzinfo is None:
            prev_slot = prev_slot.replace(tzinfo=timezone.utc)
        job.last_status = "RUNNING"
        job.locked_at = now
        job.next_run_at = _compute_next_run(job, base=now, prev=prev_slot)
        claimed.append(job.id)

    tenant_db.commit()
    return claimed


def _execute_claimed_job(tenant_db: Session, job_id: int, summary: dict) -> None:
    """
    Run one already-claimed job and record the outcome in its own transaction.

    The handler runs independently of the claim: on failure we roll back any
    partial handler work (so a poisoned transaction can't swallow the
    bookkeeping write) and then persist FAILED status + error in a fresh
    commit. ``next_run_at`` was already advanced at claim time, so the outcome
    here never changes *when* the job next runs.
    """
    job = tenant_db.get(TenantScheduledJob, job_id)
    if job is None:
        return

    handler = get_handler(job.handler)
    started = datetime.now(timezone.utc)

    if handler is None:
        tenant_db.rollback()
        job = tenant_db.get(TenantScheduledJob, job_id)
        if job is None:
            return
        job.last_status = "FAILED"
        job.last_error = f"unknown handler: {job.handler}"
        job.consecutive_failures = (job.consecutive_failures or 0) + 1
        _finalize_run(tenant_db, job, started, ok=False, summary=summary)
        return

    try:
        result = handler(tenant_db, job) or {}
        job.last_status = "OK"
        job.last_error = None
        job.consecutive_failures = 0
        _finalize_run(tenant_db, job, started, ok=True, summary=summary)
        logger.info(
            "tenant_job: ran %s for job=%s result=%s",
            job.handler,
            job.job_code,
            {k: v for k, v in result.items() if k != "details"},
        )
    except Exception as exc:
        # Clear any partially-applied / poisoned transaction before writing the
        # failure record, then reload the row in the fresh transaction.
        tenant_db.rollback()
        job = tenant_db.get(TenantScheduledJob, job_id)
        if job is None:
            summary["jobs_failed"] += 1
            return
        job.last_status = "FAILED"
        job.last_error = str(exc)[:1000]
        job.consecutive_failures = (job.consecutive_failures or 0) + 1
        if job.max_failures and job.consecutive_failures >= job.max_failures:
            job.is_enabled = False
            logger.error(
                "tenant_job: auto-paused job=%s after %s consecutive failures",
                job.job_code,
                job.consecutive_failures,
            )
        _finalize_run(tenant_db, job, started, ok=False, summary=summary)
        logger.exception("tenant_job: handler %s failed: %s", job.handler, exc)


def _finalize_run(
    tenant_db: Session,
    job: TenantScheduledJob,
    started: datetime,
    *,
    ok: bool,
    summary: dict,
) -> None:
    finished = datetime.now(timezone.utc)
    job.last_run_at = finished
    job.run_count = (job.run_count or 0) + 1
    job.last_duration_ms = int((finished - started).total_seconds() * 1000)
    job.locked_at = None
    tenant_db.commit()
    summary["jobs_run" if ok else "jobs_failed"] += 1


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
