# app/api/v1/endpoints/home_orders_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.home_orders_schemas import (
    HomeLabOrderActionResponse,
    HomeLabOrderCreateSchema,
    HomeLabOrderListResponse,
    HomeLabResultEntrySchema,
    HomeLabStatusChangeSchema,
    HomeMedDeliverySchema,
    HomeMedDispenseSchema,
    HomeMedStatusChangeSchema,
    HomeMedicationOrderActionResponse,
    HomeMedicationOrderCreateSchema,
    HomeMedicationOrderListResponse,
)
from app.services.home_orders_service import HomeLabService, HomeMedicationService
from app.utils.pagination import paginate_response

# ===========================================================================
# Home Lab Orders
# ===========================================================================
lab_router = APIRouter(
    prefix="/home-lab-orders",
    tags=["Home Health - Lab"],
    dependencies=[Depends(require_plan_feature("clinical"))],
)

_LAB_READ = require_permission("HOME_VISIT_READ", "CARE_PLAN_READ", "LAB_ORDER_CREATE", "LAB_RESULT_ENTER")
_LAB_ORDER = require_permission("LAB_ORDER_CREATE", "HOME_VISIT_DOCUMENT", "CARE_PLAN_MANAGE")
_LAB_RESULT = require_permission("LAB_RESULT_ENTER", "LAB_RESULT_VERIFY", "LAB_RESULT_RELEASE")


def get_lab(db: Annotated[Session, Depends(get_db)]) -> HomeLabService:
    return HomeLabService(db)


@lab_router.get("/", response_model=HomeLabOrderListResponse, summary="List home lab orders")
def list_lab(
    _: Annotated[User, Depends(_LAB_READ)],
    service: Annotated[HomeLabService, Depends(get_lab)],
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    patient_id: Optional[int] = Query(None), home_visit_id: Optional[int] = Query(None),
    care_plan_id: Optional[int] = Query(None), status_filter: Optional[str] = Query(None, alias="status"),
):
    items, total = service.list(patient_id=patient_id, home_visit_id=home_visit_id, care_plan_id=care_plan_id, status=status_filter, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Home lab orders fetched successfully.")


@lab_router.post("/", response_model=HomeLabOrderActionResponse, status_code=status.HTTP_201_CREATED, summary="Order home labs")
def create_lab(payload: HomeLabOrderCreateSchema, actor: CurrentActiveUser, _: Annotated[User, Depends(_LAB_ORDER)], service: Annotated[HomeLabService, Depends(get_lab)]):
    return {"success": True, "message": "Home lab order created.", "order": service.create(payload, actor_user_id=actor.id)}


@lab_router.get("/{order_id}", response_model=HomeLabOrderActionResponse, summary="Get a home lab order")
def get_lab_order(order_id: int, _: Annotated[User, Depends(_LAB_READ)], service: Annotated[HomeLabService, Depends(get_lab)]):
    return {"success": True, "message": "Home lab order fetched.", "order": service.get(order_id)}


@lab_router.post("/{order_id}/status", response_model=HomeLabOrderActionResponse, summary="Update home lab order status")
def lab_status(order_id: int, payload: HomeLabStatusChangeSchema, actor: CurrentActiveUser, _: Annotated[User, Depends(_LAB_RESULT)], service: Annotated[HomeLabService, Depends(get_lab)]):
    return {"success": True, "message": "Status updated.", "order": service.change_status(order_id, payload, actor_user_id=actor.id)}


@lab_router.post("/items/{item_id}/result", response_model=HomeLabOrderActionResponse, summary="Enter a home lab result")
def lab_result(item_id: int, payload: HomeLabResultEntrySchema, actor: CurrentActiveUser, _: Annotated[User, Depends(_LAB_RESULT)], service: Annotated[HomeLabService, Depends(get_lab)]):
    return {"success": True, "message": "Result recorded.", "order": service.enter_result(item_id, payload, actor_user_id=actor.id)}


# ===========================================================================
# Home Medication Orders (dispense + delivery)
# ===========================================================================
med_router = APIRouter(
    prefix="/home-medication-orders",
    tags=["Home Health - Pharmacy"],
    dependencies=[Depends(require_plan_feature("clinical"))],
)

_MED_READ = require_permission("HOME_VISIT_READ", "CARE_PLAN_READ", "PRESCRIPTION_WRITE", "PRESCRIPTION_DISPENSE")
_MED_ORDER = require_permission("PRESCRIPTION_WRITE", "CARE_PLAN_MANAGE")
_MED_DISPENSE = require_permission("PRESCRIPTION_DISPENSE")
_MED_DELIVER = require_permission("PRESCRIPTION_DISPENSE", "HOME_VISIT_DOCUMENT")


def get_med(db: Annotated[Session, Depends(get_db)]) -> HomeMedicationService:
    return HomeMedicationService(db)


@med_router.get("/", response_model=HomeMedicationOrderListResponse, summary="List home medication orders")
def list_med(
    _: Annotated[User, Depends(_MED_READ)],
    service: Annotated[HomeMedicationService, Depends(get_med)],
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
    patient_id: Optional[int] = Query(None), home_visit_id: Optional[int] = Query(None),
    care_plan_id: Optional[int] = Query(None), status_filter: Optional[str] = Query(None, alias="status"),
):
    items, total = service.list(patient_id=patient_id, home_visit_id=home_visit_id, care_plan_id=care_plan_id, status=status_filter, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Home medication orders fetched successfully.")


@med_router.post("/", response_model=HomeMedicationOrderActionResponse, status_code=status.HTTP_201_CREATED, summary="Prescribe home medication")
def create_med(payload: HomeMedicationOrderCreateSchema, actor: CurrentActiveUser, _: Annotated[User, Depends(_MED_ORDER)], service: Annotated[HomeMedicationService, Depends(get_med)]):
    return {"success": True, "message": "Home medication order created.", "order": service.create(payload, actor_user_id=actor.id)}


@med_router.get("/{order_id}", response_model=HomeMedicationOrderActionResponse, summary="Get a home medication order")
def get_med_order(order_id: int, _: Annotated[User, Depends(_MED_READ)], service: Annotated[HomeMedicationService, Depends(get_med)]):
    return {"success": True, "message": "Home medication order fetched.", "order": service.get(order_id)}


@med_router.post("/{order_id}/dispense", response_model=HomeMedicationOrderActionResponse, summary="Dispense a home medication order")
def dispense_med(order_id: int, payload: HomeMedDispenseSchema, actor: CurrentActiveUser, _: Annotated[User, Depends(_MED_DISPENSE)], service: Annotated[HomeMedicationService, Depends(get_med)]):
    return {"success": True, "message": "Order dispensed.", "order": service.dispense(order_id, payload, actor_user_id=actor.id)}


@med_router.post("/{order_id}/dispatch", response_model=HomeMedicationOrderActionResponse, summary="Send a dispensed order out for delivery")
def dispatch_med(order_id: int, payload: HomeMedDeliverySchema, actor: CurrentActiveUser, _: Annotated[User, Depends(_MED_DELIVER)], service: Annotated[HomeMedicationService, Depends(get_med)]):
    return {"success": True, "message": "Order out for delivery.", "order": service.deliver(order_id, payload, mark_delivered=False, actor_user_id=actor.id)}


@med_router.post("/{order_id}/deliver", response_model=HomeMedicationOrderActionResponse, summary="Confirm home delivery")
def deliver_med(order_id: int, payload: HomeMedDeliverySchema, actor: CurrentActiveUser, _: Annotated[User, Depends(_MED_DELIVER)], service: Annotated[HomeMedicationService, Depends(get_med)]):
    return {"success": True, "message": "Delivery confirmed.", "order": service.deliver(order_id, payload, mark_delivered=True, actor_user_id=actor.id)}


@med_router.post("/{order_id}/status", response_model=HomeMedicationOrderActionResponse, summary="Update home medication status")
def med_status(order_id: int, payload: HomeMedStatusChangeSchema, actor: CurrentActiveUser, _: Annotated[User, Depends(_MED_DISPENSE)], service: Annotated[HomeMedicationService, Depends(get_med)]):
    return {"success": True, "message": "Status updated.", "order": service.change_status(order_id, payload, actor_user_id=actor.id)}
