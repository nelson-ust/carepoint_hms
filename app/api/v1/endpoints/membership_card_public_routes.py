# app/api/v1/endpoints/membership_card_public_routes.py
from __future__ import annotations

"""
Public membership-card verification — the target of the QR code printed on the
card. Token-free and read-only: given a card code and the issuing hospital's
public code, it confirms the card's validity and cardholder without exposing
wallet balance or internal identifiers.
"""

from typing import Optional

from fastapi import APIRouter, Query

from app.core.database import get_master_db_context, get_tenant_db_context
from app.core.exceptions import BadRequestError, NotFoundError
from app.services.membership_card_service import MembershipCardService

router = APIRouter(prefix="/membership-cards/public", tags=["Membership Card (public)"])


@router.get("/verify", summary="Verify a membership card from its QR link")
def public_verify(
    code: str = Query(..., description="Card number or scanned QR payload/URL."),
    hospital: Optional[str] = Query(None, alias="h", description="Issuing hospital's public code."),
):
    if not (hospital or "").strip():
        raise BadRequestError(message="A hospital reference (h) is required to verify this card.")

    from app.models.all_models import Tenant
    with get_master_db_context() as mdb:
        tenant = mdb.query(Tenant).filter(
            Tenant.code == hospital.strip(),
            Tenant.is_deleted.is_(False),
        ).first()
        if tenant is None:
            raise NotFoundError(message="Unknown hospital reference.")
        tenant_id, tenant_name = tenant.id, tenant.name

    with get_tenant_db_context(tenant_id) as tdb:
        result = MembershipCardService(tdb).verify_card_public(code)

    result.setdefault("hospital_name", tenant_name)
    return {"success": True, **result}
