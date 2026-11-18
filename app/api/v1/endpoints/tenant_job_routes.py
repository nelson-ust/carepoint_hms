"""
Endpoints for managing per-tenant scheduled jobs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser
from app.services.tenant_job_runner import _HANDLER_REGISTRY
from app.services.tenant_job_service import TenantJobService


router = APIRouter(prefix="/tenant-jobs", tags=["Tenant - Background Jobs"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class JobCreateSchema(BaseModel):
    job_code: str = Field(..., examples=["nightly_invoice_run"])
    handler: str = Field(..., examples=["invoice_generation"])
    schedule_cron: Optional[str] = Field(None, examples=["0 1 * * *"])
    schedule_interval_minutes: Optional[int] = None
    params: Optional[dict[str, Any]] = None
    is_enabled: bool = True
    timezone: Optional[str] = Field(None, examples=["Africa/Lagos"])
    max_failures: Optional[int] = Field(
        None,
        ge=1,
        description="Auto-pause the job after this many consecutive failures.",
    )


class JobUpdateSchema(BaseModel):
    schedule_cron: Optional[str] = None
    schedule_interval_minutes: Optional[int] = None
    params: Optional[dict[str, Any]] = None
    is_enabled: Optional[bool] = None
    timezone: Optional[str] = None
    max_failures: Optional[int] = Field(None, ge=1)


class JobReadSchema(BaseModel):
    id: int
    job_code: str
    handler: str
    schedule_cron: Optional[str] = None
    schedule_interval_minutes: Optional[int] = None
    params: Optional[dict[str, Any]] = None
    is_enabled: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    last_duration_ms: Optional[int] = None
    run_count: int
    timezone: Optional[str] = None
    consecutive_failures: Optional[int] = None
    max_failures: Optional[int] = None
    locked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _service(db: Annotated[Session, Depends(get_db)]) -> TenantJobService:
    return TenantJobService(db)


class JobHandlerSchema(BaseModel):
    name: str
    description: str = ""


@router.get(
    "/handlers",
    response_model=list[JobHandlerSchema],
    summary="List registered job handlers",
)
def list_handlers(_: AdminUser):
    """
    Return the registered job handlers as a flat array of ``{name,
    description}``. The description is taken from each handler's docstring
    first line. (Previously this returned ``{"handlers": [...]}`` — an object
    of bare strings — which the UI tried to ``.map`` over, crashing the page.)
    """
    def _describe(fn) -> str:
        doc = (getattr(fn, "__doc__", "") or "").strip()
        return doc.split("\n", 1)[0].strip() if doc else ""

    return [
        {"name": name, "description": _describe(_HANDLER_REGISTRY[name])}
        for name in sorted(_HANDLER_REGISTRY.keys())
    ]


@router.get("", response_model=list[JobReadSchema], summary="List scheduled jobs")
def list_jobs(
    _: AdminUser,
    service: Annotated[TenantJobService, Depends(_service)],
):
    return service.list_jobs()


@router.post(
    "",
    response_model=JobReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new scheduled job",
)
def create_job(
    payload: JobCreateSchema,
    _: AdminUser,
    service: Annotated[TenantJobService, Depends(_service)],
):
    return service.create_job(
        job_code=payload.job_code,
        handler=payload.handler,
        schedule_cron=payload.schedule_cron,
        schedule_interval_minutes=payload.schedule_interval_minutes,
        params=payload.params,
        is_enabled=payload.is_enabled,
        timezone_name=payload.timezone,
        max_failures=payload.max_failures,
    )


@router.put(
    "/{job_id}",
    response_model=JobReadSchema,
    summary="Update a scheduled job",
)
def update_job(
    job_id: int,
    payload: JobUpdateSchema,
    _: AdminUser,
    service: Annotated[TenantJobService, Depends(_service)],
):
    return service.update_job(
        job_id,
        schedule_cron=payload.schedule_cron,
        schedule_interval_minutes=payload.schedule_interval_minutes,
        params=payload.params,
        is_enabled=payload.is_enabled,
        timezone_name=payload.timezone,
        max_failures=payload.max_failures,
    )


@router.post(
    "/{job_id}/run",
    response_model=JobReadSchema,
    summary="Run a scheduled job now",
)
def run_job_now(
    job_id: int,
    _: AdminUser,
    service: Annotated[TenantJobService, Depends(_service)],
):
    """
    Make the job due immediately. The background dispatcher picks it up on its
    next tick (within ~1 minute) and runs it under the same concurrency guards
    as a normal scheduled run — this endpoint never executes the handler
    inline.
    """
    return service.run_now(job_id)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft-delete a scheduled job",
)
def delete_job(
    job_id: int,
    _: AdminUser,
    service: Annotated[TenantJobService, Depends(_service)],
):
    service.delete_job(job_id)
    return {"success": True}
