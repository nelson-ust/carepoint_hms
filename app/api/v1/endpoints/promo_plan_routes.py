"""
SaaS endpoints for promotional plan-move campaigns (DSTV "open window" strategy).

A SaaS admin temporarily moves tenants onto a higher plan for a fixed window,
free of charge, with an announcement email to each tenant. Campaigns revert
automatically when the window closes, or manually here.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSAdmin
from app.services.promo_plan_service import PromoPlanService

router = APIRouter(prefix="/plan-campaigns", tags=["SaaS - Plan Campaigns"])


def _service(db: Session = Depends(get_master_db)) -> PromoPlanService:
    return PromoPlanService(db)


class PromoCampaignCreateSchema(BaseModel):
    name: str = Field(..., examples=["Festive season upgrade"])
    target_plan_code: str = Field(..., examples=["PRO"])
    days: int = Field(0, ge=0)
    months: int = Field(0, ge=0)
    message: Optional[str] = None
    tenant_ids: Optional[list[int]] = None
    from_plan_code: Optional[str] = None


@router.post("", summary="Launch a promotional plan-move campaign")
def create_campaign(
    payload: PromoCampaignCreateSchema,
    actor: CurrentSaaSAdmin,
    service: Annotated[PromoPlanService, Depends(_service)],
):
    campaign = service.create_campaign(
        name=payload.name,
        target_plan_code=payload.target_plan_code,
        days=payload.days,
        months=payload.months,
        message=payload.message,
        tenant_ids=payload.tenant_ids,
        from_plan_code=payload.from_plan_code,
        actor=actor,
    )
    return {
        "success": True,
        "message": f"{campaign.tenant_count} tenant(s) upgraded to the target plan.",
        "campaign": service.get_campaign(campaign.id),
    }


@router.get("", summary="List promotional plan-move campaigns")
def list_campaigns(
    _: CurrentSaaSAdmin,
    service: Annotated[PromoPlanService, Depends(_service)],
):
    return {"success": True, "items": service.list_campaigns()}


@router.get("/{campaign_id}", summary="Campaign detail")
def get_campaign(
    campaign_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[PromoPlanService, Depends(_service)],
):
    return {"success": True, "campaign": service.get_campaign(campaign_id)}


@router.post("/{campaign_id}/revert", summary="Revert a campaign early")
def revert_campaign(
    campaign_id: int,
    actor: CurrentSaaSAdmin,
    service: Annotated[PromoPlanService, Depends(_service)],
):
    campaign = service.revert_campaign(campaign_id, actor=actor)
    return {
        "success": True,
        "message": "Campaign reverted — tenants restored to their original plans.",
        "campaign": service.get_campaign(campaign.id),
    }
