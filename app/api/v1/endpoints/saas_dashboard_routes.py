# app/api/v1/endpoints/saas_dashboard_routes.py
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSAdmin
from app.schemas.saas_dashboard_schemas import SaaSDashboardMetricsSchema
from app.services.dashboard_service import SaaSDashboardOverviewService
from app.services.saas_dashboard_service import SaaSDashboardService


router = APIRouter(prefix="/saas/dashboard", tags=["SaaS - Dashboard"])


def get_dashboard_service(
    db: Annotated[Session, Depends(get_master_db)],
) -> SaaSDashboardService:
    return SaaSDashboardService(db)


def get_overview_service(
    db: Annotated[Session, Depends(get_master_db)],
) -> SaaSDashboardOverviewService:
    return SaaSDashboardOverviewService(db)


# ---------------------------------------------------------------------------
# Legacy endpoint (kept for back-compat with existing dashboards)
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Aggregated dashboard metrics (legacy)",
)
def get_metrics(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardService, Depends(get_dashboard_service)],
):
    """
    Retrieve aggregated dashboard metrics for the SaaS portal.
    """
    metrics = service.get_ecosystem_metrics()
    return {
        "success": True,
        "message": "Dashboard metrics retrieved successfully.",
        "data": metrics,
    }


# ---------------------------------------------------------------------------
# Expanded SaaS dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/overview",
    summary="Combined SaaS overview (tenants + billing + edge + support)",
)
def overview(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
):
    return {"success": True, "data": service.overview()}


@router.get(
    "/tenants",
    summary="Tenant population summary (active / pending / suspended / new this month)",
)
def tenant_summary(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
):
    return {"success": True, "data": service.tenant_summary()}


@router.get(
    "/onboarding-pipeline",
    summary="Onboarding conversion: applied → approved → active",
)
def onboarding_pipeline(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
):
    return {"success": True, "data": service.onboarding_pipeline()}


@router.get(
    "/subscriptions",
    summary="Subscription breakdown (active by plan, trialing total)",
)
def subscription_summary(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
):
    return {"success": True, "data": service.subscription_summary()}


@router.get(
    "/billing",
    summary="Billing summary (MRR, outstanding, overdue, MTD/LMTD collection)",
)
def billing_summary(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
):
    return {"success": True, "data": service.billing_summary()}


@router.get(
    "/billing/ageing",
    summary="AR ageing buckets (<30, 30-60, 60-90, >90 days overdue)",
)
def billing_ageing(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
):
    return {"success": True, "data": service.billing_ageing()}


@router.get(
    "/edge-nodes",
    summary="Edge-node connectivity (active / offline / degraded / provisioned)",
)
def edge_node_summary(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
):
    return {"success": True, "data": service.edge_node_summary()}


@router.get(
    "/support-access",
    summary="Support-access grants summary (requested / approved / expired)",
)
def support_access_summary(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
):
    return {"success": True, "data": service.support_access_summary()}


@router.get(
    "/usage",
    summary="Platform-wide usage rollup (logins / SMS / email / storage)",
)
def usage_summary(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
):
    return {"success": True, "data": service.usage_summary()}


@router.get(
    "/top-tenants",
    summary="Most-active tenants by login count",
)
def top_tenants(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
    limit: int = 10,
):
    return {"success": True, "data": service.top_tenants_by_usage(limit=limit)}


@router.get(
    "/recent-activity",
    summary="Recent SaaS-relevant events (notifications / registrations / payments)",
)
def recent_activity(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSDashboardOverviewService, Depends(get_overview_service)],
    limit: int = 20,
):
    return {"success": True, "data": service.recent_activity(limit=limit)}
