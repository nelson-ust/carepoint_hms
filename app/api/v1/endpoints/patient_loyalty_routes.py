# app/api/v1/endpoints/patient_loyalty_routes.py
"""
Patient loyalty endpoints powering the Patient Loyalty page:

    GET  /patient-loyalty/points/{patient_id}   -> current balance + tier inputs
    GET  /patient-loyalty/history/{patient_id}  -> transaction ledger
    POST /patient-loyalty/earn                  -> award points
    POST /patient-loyalty/redeem                -> redeem points
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser
from app.schemas.patient_loyalty_schemas import (
    LoyaltyHistoryResponse,
    PatientPointsRead,
    PointsMutationRequest,
    PointsMutationResponse,
)
from app.services.patient_loyalty_service import PatientLoyaltyService

router = APIRouter(prefix="/patient-loyalty", tags=["Patient Loyalty"])


def _service(db: Annotated[Session, Depends(get_db)]) -> PatientLoyaltyService:
    return PatientLoyaltyService(db)


@router.get("/points/{patient_id}", response_model=PatientPointsRead)
def get_points(
    patient_id: int,
    _: CurrentActiveUser,
    service: Annotated[PatientLoyaltyService, Depends(_service)],
):
    """Current loyalty balance for a patient (0 when not yet enrolled)."""
    return service.get_points(patient_id)


@router.get("/history/{patient_id}", response_model=LoyaltyHistoryResponse)
def get_history(
    patient_id: int,
    _: CurrentActiveUser,
    service: Annotated[PatientLoyaltyService, Depends(_service)],
):
    """Full points transaction history for a patient, newest first."""
    items = service.get_history(patient_id)
    return LoyaltyHistoryResponse(
        items=items,
        count=len(items),
        meta={"total": len(items)},
    )


@router.post("/earn", response_model=PointsMutationResponse)
def earn_points(
    payload: PointsMutationRequest,
    _: CurrentActiveUser,
    service: Annotated[PatientLoyaltyService, Depends(_service)],
):
    """Award loyalty points to a patient (auto-enrolls if needed)."""
    balance = service.earn(payload.patient_id, payload.points, payload.reason)
    return PointsMutationResponse(
        success=True, balance=balance, message="Points awarded successfully."
    )


@router.post("/redeem", response_model=PointsMutationResponse)
def redeem_points(
    payload: PointsMutationRequest,
    _: CurrentActiveUser,
    service: Annotated[PatientLoyaltyService, Depends(_service)],
):
    """Redeem loyalty points from a patient's balance."""
    balance = service.redeem(payload.patient_id, payload.points, payload.reason)
    return PointsMutationResponse(
        success=True, balance=balance, message="Points redeemed successfully."
    )
