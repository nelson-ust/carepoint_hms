# app/api/v1/endpoints/referral_routes.py
from __future__ import annotations

"""
FastAPI routes for the patient referral module.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.multitenancy import get_current_tenant_id
from app.core.dependencies import CurrentActiveUser
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.referral_schemas import (
    ReferralActionResponseSchema,
    ReferralCreateSchema,
    ReferralListResponseSchema,
    ReferralReadSchema,
    ReferralUpdateSchema,
    InterFacilityReferralCreateSchema,
    InterFacilityReferralReadSchema,
    InterFacilityReferralResponseSchema,
    InterFacilityReferralListResponseSchema,
    InterFacilityReferralActionResponseSchema,
)
from app.services.referral_service import ReferralService
from app.utils.pagination import paginate_response

router = APIRouter(prefix="/referrals", tags=["Referrals"])


def get_referral_service(db: Annotated[Session, Depends(get_db)]) -> ReferralService:
    """FastAPI dependency that constructs a ReferralService per-request."""
    return ReferralService(db)


def _serialize(r) -> dict:
    """ORM -> response dict translation."""
    return {
        "id": r.id,
        "referral_no": r.referral_no,
        "patient_id": r.patient_id,
        "visit_id": r.visit_id,
        "referring_staff_id": r.referring_staff_id,
        "destination_facility": r.destination_facility,
        "reason_for_referral": r.reason_for_referral,
        "clinical_summary": r.clinical_summary,
        "referral_date": r.referral_date,
        "status": str(r.status),
        "priority": str(r.priority),
        "date_created": getattr(r, "date_created", None),
        "date_updated": getattr(r, "date_updated", None),
    }


def _serialize_inter_facility(r) -> dict:
    return {
        "id": r.id,
        "referral_no": r.referral_no,
        "source_tenant_id": r.source_tenant_id,
        "source_facility_id": r.source_facility_id,
        "target_tenant_id": r.target_tenant_id,
        "target_facility_id": r.target_facility_id,
        "patient_global_id": r.patient_global_id,
        "reason_for_referral": r.reason_for_referral,
        "clinical_summary": r.clinical_summary,
        "status": str(r.status),
        "acceptance_note": r.acceptance_note,
        "declined_reason": r.declined_reason,
        "referral_date": r.referral_date,
        "responded_at": r.responded_at,
        "is_history_access_granted": r.is_history_access_granted,
        "access_expires_at": r.access_expires_at,
        "date_created": getattr(r, "date_created", None),
        "date_updated": getattr(r, "date_updated", None),
    }


# ============================================================
# LOCAL REFERRALS
# ============================================================


@router.get(
    "/",
    response_model=ReferralListResponseSchema,
    summary="List patient referrals",
)
def list_referrals(
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
    service: Annotated[ReferralService, Depends(get_referral_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    patient_id: Optional[int] = Query(None),
    visit_id: Optional[int] = Query(None),
    referring_staff_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status", description="PENDING, COMPLETED, CANCELLED."),
):
    """Paginated list of referrals with filters."""
    items, total = service.list_referrals(
        skip=skip,
        limit=limit,
        patient_id=patient_id,
        visit_id=visit_id,
        referring_staff_id=referring_staff_id,
        status=status_filter,
    )
    return paginate_response(
        items=[_serialize(r) for r in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Referrals fetched successfully.",
    )


@router.get(
    "/{referral_id}",
    response_model=ReferralReadSchema,
    summary="Get a referral record",
)
def get_referral(
    referral_id: int,
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
    service: Annotated[ReferralService, Depends(get_referral_service)],
):
    """Read a single referral by id."""
    return _serialize(service.get(referral_id))


@router.post(
    "/",
    response_model=ReferralActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new referral",
)
def create_referral(
    payload: ReferralCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[ReferralService, Depends(get_referral_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_CREATE"))],
):
    """Create a new referral record. Requires the actor to be a staff member."""
    if not actor.staff_profile:
         from app.core.exceptions import BadRequestError
         raise BadRequestError(message="Only staff members can create referrals.")
    
    referral = service.create_referral(
        payload, 
        referring_staff_id=actor.staff_profile.id,
        actor_user_id=actor.id
    )
    return {
        "success": True,
        "message": "Referral created successfully.",
        "referral": _serialize(referral),
    }


@router.patch(
    "/{referral_id}",
    response_model=ReferralActionResponseSchema,
    summary="Update a referral",
)
def update_referral(
    referral_id: int,
    payload: ReferralUpdateSchema,
    actor: CurrentActiveUser,
    service: Annotated[ReferralService, Depends(get_referral_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_UPDATE"))],
):
    """Update an existing referral record."""
    referral = service.update_referral(referral_id, payload, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Referral updated successfully.",
        "referral": _serialize(referral),
    }


@router.post(
    "/{referral_id}/cancel",
    response_model=ReferralActionResponseSchema,
    summary="Cancel a referral",
)
def cancel_referral(
    referral_id: int,
    actor: CurrentActiveUser,
    service: Annotated[ReferralService, Depends(get_referral_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_CANCEL"))],
    reason: Optional[str] = Query(None),
):
    """Cancel a referral record."""
    referral = service.cancel_referral(referral_id, reason=reason, actor_user_id=actor.id)
    return {
        "success": True,
        "message": "Referral cancelled.",
        "referral": _serialize(referral),
    }


# ============================================================
# INTER-FACILITY REFERRALS
# ============================================================

@router.post(
    "/inter-facility",
    response_model=InterFacilityReferralActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create an inter-facility referral",
)
def create_inter_facility_referral(
    payload: InterFacilityReferralCreateSchema,
    actor: CurrentActiveUser,
    service: Annotated[ReferralService, Depends(get_referral_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_CREATE"))],
):
    """Initiate a referral to another tenant in the platform."""
    tenant_id = get_current_tenant_id()
    if not tenant_id:
         from app.core.exceptions import BadRequestError
         raise BadRequestError(message="User must belong to a tenant to initiate inter-facility referrals.")
    
    if not actor.staff_profile:
         from app.core.exceptions import BadRequestError
         raise BadRequestError(message="Only staff members can initiate referrals.")

    referral = service.create_inter_facility_referral(
        payload,
        source_tenant_id=tenant_id,
        source_facility_id=actor.staff_profile.facility_id,
        actor_user_id=actor.id
    )
    return {
        "success": True,
        "message": "Inter-facility referral initiated.",
        "referral": _serialize_inter_facility(referral),
    }


@router.get(
    "/inter-facility/incoming",
    response_model=InterFacilityReferralListResponseSchema,
    summary="List incoming inter-facility referrals",
)
def list_incoming_referrals(
    actor: CurrentActiveUser,
    service: Annotated[ReferralService, Depends(get_referral_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List referrals sent to the current user's tenant from other tenants."""
    tenant_id = get_current_tenant_id()
    if not tenant_id:
         from app.core.exceptions import BadRequestError
         raise BadRequestError(message="User must belong to a tenant.")

    items, total = service.list_incoming_referrals(
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
        status=status_filter,
    )
    return paginate_response(
        items=[_serialize_inter_facility(r) for r in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Incoming referrals fetched successfully.",
    )


@router.post(
    "/inter-facility/{referral_id}/respond",
    response_model=InterFacilityReferralActionResponseSchema,
    summary="Respond to inter-facility referral",
)
def respond_to_inter_facility_referral(
    referral_id: int,
    payload: InterFacilityReferralResponseSchema,
    actor: CurrentActiveUser,
    service: Annotated[ReferralService, Depends(get_referral_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_UPDATE"))],
):
    """Accept or decline an incoming inter-facility referral."""
    referral = service.respond_to_inter_facility_referral(
        referral_id,
        payload,
        actor_user_id=actor.id
    )
    return {
        "success": True,
        "message": f"Referral {payload.status.lower()} successfully.",
        "referral": _serialize_inter_facility(referral),
    }
