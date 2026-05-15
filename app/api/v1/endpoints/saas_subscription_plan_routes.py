# app/api/v1/endpoints/saas_subscription_plan_routes.py
from typing import Annotated, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSAdmin, CurrentSaaSSuperuser
from app.schemas.subscription_schemas import (
    SubscriptionPlanReadSchema, 
    SubscriptionPlanCreateSchema, 
    SubscriptionPlanUpdateSchema
)
from app.services.subscription_plan_service import SubscriptionPlanService

router = APIRouter(prefix="/saas/plans", tags=["SaaS - Subscription Plans"])

def get_plan_service(db: Annotated[Session, Depends(get_master_db)]) -> SubscriptionPlanService:
    return SubscriptionPlanService(db)

@router.get(
    "",
    response_model=List[SubscriptionPlanReadSchema],
    status_code=status.HTTP_200_OK,
    summary="List subscription plans (Public)",
)
def list_plans(
    service: Annotated[SubscriptionPlanService, Depends(get_plan_service)],
    include_inactive: bool = False
):
    """
    List all subscription plans.
    """
    return service.list_plans(include_inactive=include_inactive)

@router.post(
    "",
    response_model=SubscriptionPlanReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new subscription plan",
)
def create_plan(
    payload: SubscriptionPlanCreateSchema,
    _: CurrentSaaSSuperuser,
    service: Annotated[SubscriptionPlanService, Depends(get_plan_service)],
):
    """
    Create a new subscription plan.
    Requires SaaS Superuser access.
    """
    return service.create_plan(payload)

@router.put(
    "/{plan_id}",
    response_model=SubscriptionPlanReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update a subscription plan",
)
def update_plan(
    plan_id: int,
    payload: SubscriptionPlanUpdateSchema,
    _: CurrentSaaSSuperuser,
    service: Annotated[SubscriptionPlanService, Depends(get_plan_service)],
):
    """
    Update a subscription plan's limits, pricing, or active status.
    Requires SaaS Superuser access.
    """
    return service.update_plan(plan_id, payload)
