# app/api/v1/endpoints/membership_card_routes.py
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, Query, status

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.membership_card_schemas import (
    MembershipCardCreate,
    MembershipCardRead,
    MembershipCardUpdate,
    MembershipCardFund,
    MembershipCardDebit,
    MembershipCardTransactionRead,
    MembershipCardWithTransactions,
)
from app.services.membership_card_service import MembershipCardService

router = APIRouter(strict_slashes=False)


@router.post(
    "",
    response_model=MembershipCardRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("PATIENT_CARD_CREATE"))],
)
def create_membership_card(
    payload: MembershipCardCreate,
    db=Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Issue a new membership card to a patient."""
    service = MembershipCardService(db)
    return service.create_card(payload, issued_by_id=current_user.id)


@router.get(
    "",
    response_model=List[MembershipCardRead],
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def list_membership_cards(
    db=Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """List all membership cards issued in the system."""
    service = MembershipCardService(db)
    return service.list_cards(skip=skip, limit=limit)


@router.get(
    "/{card_id}",
    response_model=MembershipCardWithTransactions,
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def get_membership_card(card_id: int, db=Depends(get_db)):
    """Retrieve membership card details and transaction history."""
    service = MembershipCardService(db)
    card = service.get_card(card_id, include_transactions=True)
    # The transactions are loaded via relationship in the schema if configured, 
    # but we can also manually load them if needed.
    return card


@router.get(
    "/by-number/{card_number}",
    response_model=MembershipCardRead,
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def get_membership_card_by_number(card_number: str, db=Depends(get_db)):
    """Lookup a membership card by its unique number."""
    service = MembershipCardService(db)
    return service.get_card_by_number(card_number)


@router.get(
    "/patient/{patient_id}",
    response_model=List[MembershipCardRead],
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def list_patient_membership_cards(patient_id: int, db=Depends(get_db)):
    """List all membership cards issued to a specific patient."""
    service = MembershipCardService(db)
    return service.list_patient_cards(patient_id)


@router.patch(
    "/{card_id}",
    response_model=MembershipCardRead,
    dependencies=[Depends(require_permission("PATIENT_CARD_UPDATE"))],
)
def update_membership_card(
    card_id: int,
    payload: MembershipCardUpdate,
    db=Depends(get_db),
):
    """Update membership card status or expiry date."""
    service = MembershipCardService(db)
    return service.update_card(card_id, payload)


@router.post(
    "/{card_id}/fund",
    response_model=MembershipCardTransactionRead,
    dependencies=[Depends(require_permission("PATIENT_CARD_FUND"))],
)
def fund_membership_card(
    card_id: int,
    payload: MembershipCardFund,
    db=Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    facility_id: int = Query(..., description="The facility where funding is processed"),
):
    """Credit a membership card wallet."""
    service = MembershipCardService(db)
    return service.fund_card(
        card_id=card_id,
        payload=payload,
        processed_by_id=current_user.id,
        facility_id=facility_id,
    )


@router.post(
    "/{card_id}/debit",
    response_model=MembershipCardTransactionRead,
    dependencies=[Depends(require_permission("PATIENT_CARD_DEBIT"))],
)
def debit_membership_card(
    card_id: int,
    payload: MembershipCardDebit,
    db=Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    facility_id: int = Query(..., description="The facility where payment is processed"),
):
    """Debit a membership card wallet for services."""
    service = MembershipCardService(db)
    return service.debit_card(
        card_id=card_id,
        payload=payload,
        processed_by_id=current_user.id,
        facility_id=facility_id,
    )


@router.get(
    "/{card_id}/transactions",
    response_model=List[MembershipCardTransactionRead],
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def list_membership_card_transactions(card_id: int, db=Depends(get_db)):
    """Retrieve the full transaction history for a specific membership card."""
    service = MembershipCardService(db)
    return service.get_card_transactions(card_id)
