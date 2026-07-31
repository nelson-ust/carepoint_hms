# app/api/v1/endpoints/referral_routes.py
from __future__ import annotations

"""
FastAPI routes for the patient referral module.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.multitenancy import get_current_tenant_id
from app.core.dependencies import CurrentActiveUser, require_plan_feature
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

router = APIRouter(
    prefix="/referrals", 
    tags=["Referrals"],
    dependencies=[Depends(require_plan_feature("clinical"))]
)


def get_referral_service(db: Annotated[Session, Depends(get_db)]) -> ReferralService:
    """FastAPI dependency that constructs a ReferralService per-request."""
    return ReferralService(db)


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
    limit: int = Query(50, ge=1, le=1000),
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
        items=items,
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
    return service.get(referral_id)


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
        source_facility_id=getattr(actor.staff_profile, "facility_id", None),
        actor_user_id=actor.id
    )
    return {
        "success": True,
        "message": "Referral created successfully.",
        "referral": referral,
    }


@router.get(
    "/facility/incoming",
    response_model=ReferralListResponseSchema,
    summary="Referrals sent to my facility (within this hospital)",
)
def list_facility_incoming(
    actor: CurrentActiveUser,
    service: Annotated[ReferralService, Depends(get_referral_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """Internal facility referrals addressed to the current user's facility."""
    facility_id = getattr(getattr(actor, "staff_profile", None), "facility_id", None)
    if not facility_id:
        return paginate_response(items=[], total=0, skip=skip, limit=limit,
                                 message="You are not assigned to a facility.")
    items, total = service.list_facility_referrals(
        facility_id=facility_id, direction="incoming", skip=skip, limit=limit, status=status_filter,
    )
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Incoming facility referrals fetched successfully.")


@router.get(
    "/facility/outgoing",
    response_model=ReferralListResponseSchema,
    summary="Referrals my facility has sent (within this hospital)",
)
def list_facility_outgoing(
    actor: CurrentActiveUser,
    service: Annotated[ReferralService, Depends(get_referral_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """Internal facility referrals sent from the current user's facility."""
    facility_id = getattr(getattr(actor, "staff_profile", None), "facility_id", None)
    if not facility_id:
        return paginate_response(items=[], total=0, skip=skip, limit=limit,
                                 message="You are not assigned to a facility.")
    items, total = service.list_facility_referrals(
        facility_id=facility_id, direction="outgoing", skip=skip, limit=limit, status=status_filter,
    )
    return paginate_response(items=items, total=total, skip=skip, limit=limit,
                             message="Outgoing facility referrals fetched successfully.")


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
        "referral": referral,
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
        "referral": referral,
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
        # Staff without a facility assignment can still refer: 0 is the
        # "unspecified facility" sentinel (the column is NOT NULL in master,
        # and the receiving side keys off the tenant, not the facility).
        source_facility_id=actor.staff_profile.facility_id or 0,
        actor_user_id=actor.id
    )
    return {
        "success": True,
        "message": "Inter-facility referral initiated.",
        "referral": referral,
    }


@router.get(
    "/inter-facility/{referral_id}/record",
    summary="Receiving hospital: open the referred patient's record (post-acceptance)",
)
def get_inter_facility_referral_record(
    referral_id: int,
    actor: CurrentActiveUser,
    service: Annotated[ReferralService, Depends(get_referral_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
):
    """Grant-gated live record pull from the referring hospital, including
    demographics/baseline diagnostics (blood group, genotype) and clinical
    history sections. Available only to the target tenant while the
    time-limited access is active."""
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(message="User must belong to a tenant.")
    record = service.get_referral_record(
        referral_id, requesting_tenant_id=tenant_id, actor_user_id=actor.id
    )
    return {"success": True, "message": "Record retrieved.", "record": record}


class ReferralImportRequestSchema(BaseModel):
    """Registrar-reviewed edits + duplicate override for a one-click import."""
    overrides: Optional[dict] = None
    force: bool = False


@router.get(
    "/inter-facility/{referral_id}/import-preview",
    summary="Receiving hospital: preview one-click patient import from an accepted referral",
)
def preview_referral_import(
    referral_id: int,
    actor: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permission("PATIENT_CREATE"))],
):
    """Non-mutating: returns the referral package, an import plan (what will be
    created, the next Hospital Number, the preserved Global Patient ID),
    duplicate matches and validation warnings for the registrar to review."""
    from app.core.multitenancy import get_current_tenant_id
    from app.core.exceptions import BadRequestError
    from app.services.referral_import_service import ReferralImportService
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise BadRequestError(message="User must belong to a tenant.")
    data = ReferralImportService(db).preview(
        referral_id, requesting_tenant_id=tenant_id, actor_user_id=actor.id)
    return {"success": True, "message": "Import preview ready.", "preview": data}


@router.post(
    "/inter-facility/{referral_id}/create-patient",
    summary="Receiving hospital: one-click create local patient from an accepted referral",
)
def create_patient_from_referral(
    referral_id: int,
    payload: ReferralImportRequestSchema,
    actor: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_permission("PATIENT_CREATE"))],
):
    """Atomically create the local patient record (new Hospital Number,
    preserved Global Patient ID), baseline medical profile, and provenance-
    tagged copies of the two most recent visits — all audited."""
    from app.core.multitenancy import get_current_tenant_id
    from app.core.exceptions import BadRequestError
    from app.services.referral_import_service import ReferralImportService
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise BadRequestError(message="User must belong to a tenant.")
    result = ReferralImportService(db).create_patient_from_referral(
        referral_id, requesting_tenant_id=tenant_id, actor_user_id=actor.id,
        overrides=payload.overrides or {}, force=bool(payload.force))
    return {"success": True, "message": "Patient created from referral.",
            "result": result}



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
    limit: int = Query(50, ge=1, le=1000),
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
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Incoming referrals fetched successfully.",
    )


@router.get(
    "/inter-facility/outgoing",
    response_model=InterFacilityReferralListResponseSchema,
    summary="List outgoing inter-facility referrals",
)
def list_outgoing_referrals(
    actor: CurrentActiveUser,
    service: Annotated[ReferralService, Depends(get_referral_service)],
    _: Annotated[User, Depends(require_permission("REFERRAL_READ"))],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List referrals this tenant has sent to other tenants."""
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(message="User must belong to a tenant.")

    items, total = service.list_outgoing_referrals(
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
        status=status_filter,
    )
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Outgoing referrals fetched successfully.",
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
        "referral": referral,
    }
