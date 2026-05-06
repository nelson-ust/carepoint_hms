from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.loyalty_schemas import (
    LoyaltyProgramCreateSchema, LoyaltyProgramReadSchema,
    FacilityNetworkCreateSchema, FacilityNetworkReadSchema
)
from app.services.loyalty_service import LoyaltyService

router = APIRouter(prefix="/loyalty-network", tags=["Loyalty & Facility Network"])

def _get_service(db: Session = Depends(get_db)) -> LoyaltyService:
    return LoyaltyService(db)

@router.post("/programs", response_model=LoyaltyProgramReadSchema)
def create_program(
    payload: LoyaltyProgramCreateSchema,
    service: LoyaltyService = Depends(_get_service)
):
    return service.create_program(payload)

@router.get("/programs", response_model=List[LoyaltyProgramReadSchema])
def list_programs(
    service: LoyaltyService = Depends(_get_service)
):
    return service.repository.list_programs()

@router.post("/networks", response_model=FacilityNetworkReadSchema)
def create_network(
    payload: FacilityNetworkCreateSchema,
    service: LoyaltyService = Depends(_get_service)
):
    return service.create_network(payload)

@router.get("/networks", response_model=List[FacilityNetworkReadSchema])
def list_networks(
    service: LoyaltyService = Depends(_get_service)
):
    return service.repository.list_networks()
