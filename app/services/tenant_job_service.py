"""
CRUD service for per-tenant scheduled jobs.

Operates inside the tenant database. Use this service through the
``/api/v1/tenant-jobs`` routes to register, list, update, or pause jobs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import TenantScheduledJob
from app.services.tenant_job_runner import _compute_next_run, get_handler


def _validate_timezone(name: Optional[str]) -> Optional[str]:
    """Return a cleaned IANA tz name, or raise BadRequestError if invalid."""
    if name is None:
        return None
    cleaned = name.strip()
    if not cleaned or cleaned.upper() == "UTC":
        return cleaned or None
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(cleaned)
    except Exception:
        raise BadRequestError(message=f"Unknown timezone '{cleaned}'.")
    return cleaned


class TenantJobService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_jobs(self) -> list[TenantScheduledJob]:
        return (
            self.db.query(TenantScheduledJob)
            .filter(TenantScheduledJob.is_deleted.is_(False))
            .order_by(TenantScheduledJob.id.asc())
            .all()
        )

    def get_job(self, job_id: int) -> TenantScheduledJob:
        record = (
            self.db.query(TenantScheduledJob)
            .filter(
                TenantScheduledJob.id == job_id,
                TenantScheduledJob.is_deleted.is_(False),
            )
            .first()
        )
        if not record:
            raise NotFoundError(message="Scheduled job not found.")
        return record

    def create_job(
        self,
        *,
        job_code: str,
        handler: str,
        schedule_cron: Optional[str] = None,
        schedule_interval_minutes: Optional[int] = None,
        params: Optional[dict] = None,
        is_enabled: bool = True,
        timezone_name: Optional[str] = None,
        max_failures: Optional[int] = None,
    ) -> TenantScheduledJob:
        if not handler or get_handler(handler) is None:
            raise BadRequestError(
                message=f"Unknown job handler '{handler}'. Register one first.",
            )
        if not schedule_cron and not schedule_interval_minutes:
            raise BadRequestError(
                message="Either schedule_cron or schedule_interval_minutes must be provided.",
            )

        record = TenantScheduledJob(
            job_code=job_code.strip(),
            handler=handler.strip(),
            schedule_cron=schedule_cron,
            schedule_interval_minutes=schedule_interval_minutes,
            params=params,
            is_enabled=is_enabled,
            timezone=_validate_timezone(timezone_name),
            max_failures=max_failures,
        )
        record.next_run_at = _compute_next_run(record, base=datetime.now(timezone.utc))
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_job(
        self,
        job_id: int,
        *,
        schedule_cron: Optional[str] = None,
        schedule_interval_minutes: Optional[int] = None,
        params: Optional[dict] = None,
        is_enabled: Optional[bool] = None,
        timezone_name: Optional[str] = None,
        max_failures: Optional[int] = None,
    ) -> TenantScheduledJob:
        record = self.get_job(job_id)
        if schedule_cron is not None:
            record.schedule_cron = schedule_cron
        if schedule_interval_minutes is not None:
            record.schedule_interval_minutes = schedule_interval_minutes
        if params is not None:
            record.params = params
        if is_enabled is not None:
            record.is_enabled = is_enabled
            # Re-enabling a previously auto-paused job clears its failure streak.
            if is_enabled:
                record.consecutive_failures = 0
        if timezone_name is not None:
            record.timezone = _validate_timezone(timezone_name)
        if max_failures is not None:
            record.max_failures = max_failures
        record.next_run_at = _compute_next_run(record, base=datetime.now(timezone.utc))
        self.db.commit()
        self.db.refresh(record)
        return record

    def run_now(self, job_id: int) -> TenantScheduledJob:
        """Make a job due immediately so the next dispatcher tick runs it.

        Does not execute inline — the dispatcher owns execution (and its
        concurrency guards). Setting ``next_run_at`` to now is enough.
        """
        record = self.get_job(job_id)
        record.next_run_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete_job(self, job_id: int) -> None:
        record = self.get_job(job_id)
        record.soft_delete()
        self.db.commit()
