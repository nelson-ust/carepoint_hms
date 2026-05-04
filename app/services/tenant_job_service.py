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
        record.next_run_at = _compute_next_run(record, base=datetime.now(timezone.utc))
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete_job(self, job_id: int) -> None:
        record = self.get_job(job_id)
        record.soft_delete()
        self.db.commit()
