"""
Tenant operational dashboard endpoints.

Audience: tenant administrators and clinical-operations leads viewing
their own tenant's data. All routes run inside the tenant-scoped
session resolved by ``TenantMiddleware``, so cross-tenant access is
impossible: a tenant only ever sees their own metrics.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.services.dashboard_service import TenantDashboardService


router = APIRouter(prefix="/dashboard", tags=["Tenant - Dashboard"])


def _service(db: Annotated[Session, Depends(get_db)]) -> TenantDashboardService:
    return TenantDashboardService(db)


# ---------------------------------------------------------------------------
# Top-level overview
# ---------------------------------------------------------------------------


@router.get(
    "/overview",
    summary="Combined tenant overview (every section in one call)",
)
def overview(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.overview()}


# ---------------------------------------------------------------------------
# Today's headline numbers
# ---------------------------------------------------------------------------


@router.get(
    "/today",
    summary="Today snapshot (new patients, visits, appointments, revenue)",
)
def today_snapshot(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.today_snapshot()}


# ---------------------------------------------------------------------------
# Sections — each useful as a standalone widget
# ---------------------------------------------------------------------------


@router.get(
    "/patients",
    summary="Patient population summary",
)
def patients(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.patient_summary()}


@router.get(
    "/visits",
    summary="Visit summary (today, in-progress, completed today)",
)
def visits(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.visit_summary()}


@router.get(
    "/appointments",
    summary="Today's appointments by status",
)
def appointments(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.appointment_summary()}


@router.get(
    "/inpatient",
    summary="Inpatient + bed-occupancy summary",
)
def inpatient(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.inpatient_summary()}


@router.get(
    "/billing",
    summary="Tenant-side billing (MTD billed / collected / outstanding)",
)
def billing(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.billing_summary()}


@router.get(
    "/lab-pharmacy-backlog",
    summary="Pending lab orders, prescriptions, and dispenses",
)
def lab_pharmacy_backlog(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.lab_pharmacy_backlog()}


@router.get(
    "/inventory-alerts",
    summary="Low-stock + expiring-soon inventory counts",
)
def inventory_alerts(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.inventory_alerts()}


@router.get(
    "/hr",
    summary="HR summary (staff counts, leave, license expiry, payroll)",
)
def hr(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.hr_summary()}


@router.get(
    "/medication-adherence",
    summary="Medication adherence overview (active schedules, alerts, refills)",
)
def medication_adherence(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
):
    return {"success": True, "data": service.medication_adherence_summary()}


@router.get(
    "/recent-activity",
    summary="Recent operational events (registrations, visits, payments)",
)
def recent_activity(
    _: CurrentActiveUser,
    service: Annotated[TenantDashboardService, Depends(_service)],
    limit: int = 20,
):
    return {"success": True, "data": service.recent_activity(limit=limit)}
