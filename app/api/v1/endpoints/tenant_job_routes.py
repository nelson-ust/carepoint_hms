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


class JobUpdateSchema(BaseModel):
    schedule_cron: Optional[str] = None
    schedule_interval_minutes: Optional[int] = None
    params: Optional[dict[str, Any]] = None
    is_enabled: Optional[bool] = None


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

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _service(db: Annotated[Session, Depends(get_db)]) -> TenantJobService:
    return TenantJobService(db)


@router.get("/handlers", summary="List registered job handlers")
def list_handlers(_: AdminUser):
    return {"handlers": sorted(_HANDLER_REGISTRY.keys())}


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
    )


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
