# app/api/v1/endpoints/membership_card_routes.py
from __future__ import annotations

import os
from typing import List
from fastapi import APIRouter, Depends, Query, status, HTTPException
from fastapi.responses import FileResponse

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.role import require_permission
from app.models.all_models import User
from typing import Optional

from app.schemas.membership_card_schemas import (
    MembershipCardCreate,
    MembershipCardRead,
    MembershipCardStatsSchema,
    MembershipCardUpdate,
    MembershipCardFund,
    MembershipCardDebit,
    MembershipCardTransactionRead,
    MembershipCardWithTransactions,
    CardFundingRequestRead,
    CardFundingRequestReview,
)
from app.services.membership_card_service import MembershipCardService

router = APIRouter()


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
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Match card number or patient name"),
    status: Optional[str] = Query(None, description="Filter by card status"),
):
    """List membership cards, optionally filtered by search term or status."""
    service = MembershipCardService(db)
    return service.list_cards(skip=skip, limit=limit, search=search, status=status)


@router.get(
    "/stats",
    response_model=MembershipCardStatsSchema,
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def get_membership_card_stats(db=Depends(get_db)):
    """Aggregate counts by status and total wallet balance."""
    service = MembershipCardService(db)
    return service.get_stats()


# ---------------------------------------------------------------------------
# Manual funding requests (patient-submitted → staff review queue)
# NOTE: declared before "/{card_id}" so the literal path wins over the
# integer path parameter.
# ---------------------------------------------------------------------------


@router.get(
    "/funding-requests",
    response_model=List[CardFundingRequestRead],
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def list_card_funding_requests(
    db=Depends(get_db),
    status: Optional[str] = Query(
        None, description="Filter by PENDING / APPROVED / REJECTED"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """List manual card-funding requests for the staff review queue."""
    service = MembershipCardService(db)
    return service.list_funding_requests(status=status, skip=skip, limit=limit)


@router.get(
    "/funding-requests/{request_id}/evidence",
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def get_card_funding_evidence(request_id: int, db=Depends(get_db)):
    """Stream the uploaded evidence file for a funding request (staff review)."""
    service = MembershipCardService(db)
    req = service.get_funding_request(request_id)
    path = req.evidence_file_path
    if not path or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Evidence file is not available.")
    return FileResponse(
        path,
        media_type=req.evidence_content_type or "application/octet-stream",
        filename=req.evidence_file_name or os.path.basename(path),
    )


@router.post(
    "/funding-requests/{request_id}/approve",
    response_model=CardFundingRequestRead,
    dependencies=[Depends(require_permission("PATIENT_CARD_FUND"))],
)
def approve_card_funding_request(
    request_id: int,
    payload: CardFundingRequestReview | None = None,
    db=Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Approve a manual funding request and credit the patient's wallet."""
    service = MembershipCardService(db)
    return service.approve_funding_request(
        request_id,
        reviewed_by_id=current_user.id,
        note=(payload.note if payload else None),
    )


@router.post(
    "/funding-requests/{request_id}/reject",
    response_model=CardFundingRequestRead,
    dependencies=[Depends(require_permission("PATIENT_CARD_FUND"))],
)
def reject_card_funding_request(
    request_id: int,
    payload: CardFundingRequestReview | None = None,
    db=Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Reject a manual funding request with an optional reason."""
    service = MembershipCardService(db)
    return service.reject_funding_request(
        request_id,
        reviewed_by_id=current_user.id,
        note=(payload.note if payload else None),
    )


@router.get(
    "/verify",
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def verify_membership_card(
    db=Depends(get_db),
    code: str = Query(..., description="A scanned QR payload or a raw card number."),
):
    """Verify a membership card from a scanned QR code (or typed card number)."""
    service = MembershipCardService(db)
    return service.verify_card(code)


@router.get(
    "/{card_id}/card-pdf",
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def print_membership_card(card_id: int, db=Depends(get_db)):
    """Generate a printable PDF of the membership card (hospital, patient, number, QR)."""
    from fastapi import Response

    service = MembershipCardService(db)
    pdf_bytes, filename = service.generate_card_pdf(card_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get(
    "/{card_id}/qr",
    dependencies=[Depends(require_permission("PATIENT_CARD_VIEW"))],
)
def membership_card_qr(
    card_id: int,
    base: Optional[str] = Query(None, description="Frontend origin for the verification link (defaults to FRONTEND_URL)."),
    db=Depends(get_db),
):
    """Return a scannable QR PNG that links to this card's verification page."""
    from fastapi import Response

    service = MembershipCardService(db)
    png_bytes, filename = service.build_card_qr_png(card_id, base=base)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


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
