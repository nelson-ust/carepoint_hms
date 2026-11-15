# app/api/v1/endpoints/ambulance_ext_routes.py
from __future__ import annotations

"""Routes for extended ambulance EMS processes: crew, PCR, fuel, trip billing, analytics."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.ambulance_ext_schemas import (
    AmbExtActionResponseSchema,
    AmbExtListResponseSchema,
    ChargeStatusSchema,
    CrewCreateSchema,
    FuelCreateSchema,
    PCRUpsertSchema,
    TripChargeCreateSchema,
)
from app.services.ambulance_ext_service import AmbulanceExtService
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/ambulance-ext", tags=["Ambulance EMS"], dependencies=[Depends(require_plan_feature("ambulance"))])

DREAD = require_permission("DISPATCH_READ")
DMANAGE = require_permission("DISPATCH_MANAGE")
AREAD = require_permission("AMBULANCE_READ")
AMANAGE = require_permission("AMBULANCE_MANAGE")


def svc(db: Annotated[Session, Depends(get_db)]) -> AmbulanceExtService:
    return AmbulanceExtService(db)


def _list(items, builder, msg):
    return paginate_response(items=[builder(i) for i in items], total=len(items), skip=0, limit=len(items) or 1, message=msg)


# ---- analytics ----
@router.get("/analytics", response_model=AmbExtActionResponseSchema, summary="Ambulance / EMS analytics")
def analytics(_: Annotated[User, Depends(DREAD)], s: Annotated[AmbulanceExtService, Depends(svc)], months: int = Query(6, ge=1, le=24)):
    return {"success": True, "message": "Analytics computed.", "data": s.analytics(months=months)}


# ---- crew ----
@router.get("/dispatches/{dispatch_id}/crew", response_model=AmbExtListResponseSchema, summary="List crew on a dispatch")
def list_crew(dispatch_id: int, _: Annotated[User, Depends(DREAD)], s: Annotated[AmbulanceExtService, Depends(svc)]):
    return _list(s.list_crew(dispatch_id), s.crew_dict, "Crew fetched.")


@router.post("/dispatches/{dispatch_id}/crew", response_model=AmbExtActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Assign a crew member")
def add_crew(dispatch_id: int, payload: CrewCreateSchema, _: Annotated[User, Depends(DMANAGE)], s: Annotated[AmbulanceExtService, Depends(svc)]):
    return {"success": True, "message": "Crew assigned.", "data": s.crew_dict(s.add_crew(dispatch_id, payload))}


@router.delete("/crew/{crew_id}", summary="Remove a crew member")
def remove_crew(crew_id: int, _: Annotated[User, Depends(DMANAGE)], s: Annotated[AmbulanceExtService, Depends(svc)]):
    return {"success": True, "message": "Crew removed.", "id": s.remove_crew(crew_id).id}


# ---- PCR ----
@router.get("/dispatches/{dispatch_id}/pcr", response_model=AmbExtActionResponseSchema, summary="Get the patient care report")
def get_pcr(dispatch_id: int, _: Annotated[User, Depends(DREAD)], s: Annotated[AmbulanceExtService, Depends(svc)]):
    return {"success": True, "message": "PCR fetched.", "data": s.pcr_dict(s.get_pcr(dispatch_id))}


@router.put("/dispatches/{dispatch_id}/pcr", response_model=AmbExtActionResponseSchema, summary="Create / update the patient care report")
def upsert_pcr(dispatch_id: int, payload: PCRUpsertSchema, _: Annotated[User, Depends(DMANAGE)], s: Annotated[AmbulanceExtService, Depends(svc)]):
    return {"success": True, "message": "PCR saved.", "data": s.pcr_dict(s.upsert_pcr(dispatch_id, payload))}


# ---- trip charges ----
@router.get("/dispatches/{dispatch_id}/charges", response_model=AmbExtListResponseSchema, summary="List trip charges")
def list_charges(dispatch_id: int, _: Annotated[User, Depends(DREAD)], s: Annotated[AmbulanceExtService, Depends(svc)]):
    return _list(s.list_charges(dispatch_id), s.charge_dict, "Charges fetched.")


@router.post("/dispatches/{dispatch_id}/charges", response_model=AmbExtActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Add a trip charge")
def add_charge(dispatch_id: int, payload: TripChargeCreateSchema, _: Annotated[User, Depends(DMANAGE)], s: Annotated[AmbulanceExtService, Depends(svc)]):
    return {"success": True, "message": "Charge added.", "data": s.charge_dict(s.add_charge(dispatch_id, payload))}


@router.post("/trip-charges/{charge_id}/status", response_model=AmbExtActionResponseSchema, summary="Mark a trip charge paid / waived")
def set_charge_status(charge_id: int, payload: ChargeStatusSchema, _: Annotated[User, Depends(DMANAGE)], s: Annotated[AmbulanceExtService, Depends(svc)]):
    return {"success": True, "message": f"Charge marked {payload.status}.", "data": s.charge_dict(s.set_charge_status(charge_id, payload.status))}


# ---- fuel ----
@router.get("/ambulances/{ambulance_id}/fuel", response_model=AmbExtListResponseSchema, summary="List fuel logs")
def list_fuel(ambulance_id: int, _: Annotated[User, Depends(AREAD)], s: Annotated[AmbulanceExtService, Depends(svc)]):
    return _list(s.list_fuel(ambulance_id), s.fuel_dict, "Fuel logs fetched.")


@router.post("/ambulances/{ambulance_id}/fuel", response_model=AmbExtActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Add a fuel log")
def add_fuel(ambulance_id: int, payload: FuelCreateSchema, _: Annotated[User, Depends(AMANAGE)], s: Annotated[AmbulanceExtService, Depends(svc)]):
    return {"success": True, "message": "Fuel logged.", "data": s.fuel_dict(s.add_fuel(ambulance_id, payload))}
