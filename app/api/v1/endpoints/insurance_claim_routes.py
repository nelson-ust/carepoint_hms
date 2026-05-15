# app/api/v1/endpoints/insurance_claim_routes.py
from __future__ import annotations

"""
FastAPI routes for the Insurance Claims module.

Routers:
- ``/insurance/batches``         — claim-batch CRUD + submit / acknowledge
- ``/insurance/claims``          — header + items, submit / withdraw, list
- ``/insurance/authorizations``  — request + decide pre-auth
- ``/insurance/adjudications``   — record insurer's adjudication
- ``/insurance/payments``        — receipts (idempotent on payment_reference)
- ``/insurance/appeals``         — submit + decide appeals

Permissions:
- ``CLAIM_MANAGE``  — create / submit / withdraw / appeal
- ``CLAIM_REVIEW``  — record adjudication / authorization decisions
- ``CLAIM_READ``    — read-only access
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.insurance_claim_schemas import (
    ClaimAdjudicationActionResponseSchema,
    ClaimAdjudicationCreateSchema,
    ClaimAppealActionResponseSchema,
    ClaimAppealCreateSchema,
    ClaimAppealDecisionSchema,
    ClaimAuthorizationActionResponseSchema,
    ClaimAuthorizationCreateSchema,
    ClaimAuthorizationDecisionSchema,
    ClaimBatchAcknowledgeSchema,
    ClaimBatchActionResponseSchema,
    ClaimBatchCreateSchema,
    ClaimBatchListResponseSchema,
    ClaimBatchSubmitSchema,
    ClaimPaymentActionResponseSchema,
    ClaimPaymentCreateSchema,
    InsuranceClaimActionResponseSchema,
    InsuranceClaimCreateSchema,
    InsuranceClaimListResponseSchema,
    InsuranceClaimSubmitSchema,
)
from app.services.insurance_claim_service import (
    ClaimAdjudicationService,
    ClaimAppealService,
    ClaimAuthorizationService,
    ClaimBatchService,
    ClaimPaymentService,
    InsuranceClaimService,
)
from app.utils.pagination import paginate_response

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

batch_router = APIRouter(prefix="/insurance/batches", tags=["Insurance - Batches"], dependencies=[Depends(require_plan_feature("insurance"))])
claim_router = APIRouter(prefix="/insurance/claims", tags=["Insurance - Claims"], dependencies=[Depends(require_plan_feature("insurance"))])
auth_router = APIRouter(
    prefix="/insurance/authorizations", tags=["Insurance - Authorizations"], dependencies=[Depends(require_plan_feature("insurance"))]
)
adjudication_router = APIRouter(
    prefix="/insurance/adjudications", tags=["Insurance - Adjudications"], dependencies=[Depends(require_plan_feature("insurance"))]
)
payment_router = APIRouter(prefix="/insurance/payments", tags=["Insurance - Payments"], dependencies=[Depends(require_plan_feature("insurance"))])
appeal_router = APIRouter(prefix="/insurance/appeals", tags=["Insurance - Appeals"], dependencies=[Depends(require_plan_feature("insurance"))])



# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_batch_service(db: Annotated[Session, Depends(get_db)]) -> ClaimBatchService:
    return ClaimBatchService(db)


def get_claim_service(db: Annotated[Session, Depends(get_db)]) -> InsuranceClaimService:
    return InsuranceClaimService(db)


def get_auth_service(db: Annotated[Session, Depends(get_db)]) -> ClaimAuthorizationService:
    return ClaimAuthorizationService(db)


def get_adjudication_service(
    db: Annotated[Session, Depends(get_db)],
) -> ClaimAdjudicationService:
    return ClaimAdjudicationService(db)


def get_payment_service(db: Annotated[Session, Depends(get_db)]) -> ClaimPaymentService:
    return ClaimPaymentService(db)


def get_appeal_service(db: Annotated[Session, Depends(get_db)]) -> ClaimAppealService:
    return ClaimAppealService(db)


# ---------------------------------------------------------------------------
# ORM -> dict helpers
# ---------------------------------------------------------------------------


def _batch_dict(b) -> dict:
    return {
        "id": b.id,
        "batch_no": b.batch_no,
        "insurance_provider_id": b.insurance_provider_id,
        "facility_id": b.facility_id,
        "submitted_by_staff_id": b.submitted_by_staff_id,
        "status": str(b.status),
        "period_start": b.period_start,
        "period_end": b.period_end,
        "submitted_at": b.submitted_at,
        "acknowledged_at": b.acknowledged_at,
        "total_claims": b.total_claims,
        "total_billed_amount": b.total_billed_amount,
        "total_approved_amount": b.total_approved_amount,
        "notes": b.notes,
        "created_at": getattr(b, "created_at", None),
    }


def _claim_item_dict(i) -> dict:
    return {
        "id": i.id,
        "claim_id": i.claim_id,
        "invoice_item_id": i.invoice_item_id,
        "billable_service_id": i.billable_service_id,
        "service_date": i.service_date,
        "procedure_code": i.procedure_code,
        "diagnosis_code": i.diagnosis_code,
        "description": i.description,
        "quantity": i.quantity,
        "unit_price": i.unit_price,
        "billed_amount": i.billed_amount,
        "approved_amount": i.approved_amount,
        "rejected_amount": i.rejected_amount,
    }


def _claim_dict(c) -> dict:
    return {
        "id": c.id,
        "claim_no": c.claim_no,
        "batch_id": c.batch_id,
        "patient_id": c.patient_id,
        "patient_insurance_id": c.patient_insurance_id,
        "insurance_provider_id": c.insurance_provider_id,
        "visit_id": c.visit_id,
        "invoice_id": c.invoice_id,
        "facility_id": c.facility_id,
        "status": str(c.status),
        "service_date": c.service_date,
        "diagnosis_codes": c.diagnosis_codes,
        "primary_diagnosis_text": c.primary_diagnosis_text,
        "billed_amount": c.billed_amount,
        "approved_amount": c.approved_amount,
        "rejected_amount": c.rejected_amount,
        "patient_responsibility_amount": c.patient_responsibility_amount,
        "paid_amount": c.paid_amount,
        "submitted_at": c.submitted_at,
        "notes": c.notes,
        "items": [
            _claim_item_dict(i)
            for i in (c.items or [])
            if not getattr(i, "is_deleted", False)
        ],
        "created_at": getattr(c, "created_at", None),
    }


def _auth_dict(a) -> dict:
    return {
        "id": a.id,
        "claim_id": a.claim_id,
        "patient_insurance_id": a.patient_insurance_id,
        "authorization_no": a.authorization_no,
        "requested_service": a.requested_service,
        "requested_amount": a.requested_amount,
        "approved_amount": a.approved_amount,
        "status": str(a.status),
        "requested_at": a.requested_at,
        "decided_at": a.decided_at,
        "valid_from": a.valid_from,
        "valid_until": a.valid_until,
        "decision_reason": a.decision_reason,
    }


def _adjudication_dict(a) -> dict:
    return {
        "id": a.id,
        "claim_id": a.claim_id,
        "adjudication_no": a.adjudication_no,
        "outcome": str(a.outcome),
        "approved_amount": a.approved_amount,
        "rejected_amount": a.rejected_amount,
        "rejection_codes": a.rejection_codes,
        "explanation_of_benefit": a.explanation_of_benefit,
        "adjudicated_at": a.adjudicated_at,
    }


def _payment_dict(p) -> dict:
    return {
        "id": p.id,
        "claim_id": p.claim_id,
        "payment_reference": p.payment_reference,
        "amount": p.amount,
        "currency": p.currency,
        "paid_at": p.paid_at,
        "payment_method": p.payment_method,
        "notes": p.notes,
    }


def _appeal_dict(a) -> dict:
    return {
        "id": a.id,
        "claim_id": a.claim_id,
        "appeal_no": a.appeal_no,
        "status": str(a.status),
        "submitted_by_staff_id": a.submitted_by_staff_id,
        "submitted_at": a.submitted_at,
        "decided_at": a.decided_at,
        "decision_text": a.decision_text,
        "appeal_text": a.appeal_text,
        "additional_evidence_url": a.additional_evidence_url,
        "additional_amount_requested": a.additional_amount_requested,
        "additional_amount_approved": a.additional_amount_approved,
    }


# ============================================================
# BATCH
# ============================================================


@batch_router.get(
    "/",
    response_model=ClaimBatchListResponseSchema,
    summary="List claim batches",
)
def list_batches(
    _: Annotated[User, Depends(require_permission("CLAIM_READ", "CLAIM_MANAGE"))],
    service: Annotated[ClaimBatchService, Depends(get_batch_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    statuses: Optional[list[str]] = Query(None),
    insurance_provider_id: Optional[int] = Query(None),
    facility_id: Optional[int] = Query(None),
):
    items, total = service.list_batches(
        skip=skip,
        limit=limit,
        statuses=statuses,
        insurance_provider_id=insurance_provider_id,
        facility_id=facility_id,
    )
    return paginate_response(
        items=[_batch_dict(b) for b in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Claim batches fetched successfully.",
    )


@batch_router.post(
    "/",
    response_model=ClaimBatchActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a claim batch",
)
def create_batch(
    payload: ClaimBatchCreateSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_MANAGE"))],
    service: Annotated[ClaimBatchService, Depends(get_batch_service)],
):
    b = service.create(payload, actor_user_id=user.id)
    return {"success": True, "message": "Claim batch created.", "batch": _batch_dict(b)}


@batch_router.get(
    "/{batch_id}",
    summary="Get a claim batch",
)
def get_batch(
    batch_id: int,
    _: Annotated[User, Depends(require_permission("CLAIM_READ", "CLAIM_MANAGE"))],
    service: Annotated[ClaimBatchService, Depends(get_batch_service)],
):
    return _batch_dict(service.get(batch_id))


@batch_router.post(
    "/{batch_id}/submit",
    response_model=ClaimBatchActionResponseSchema,
    summary="Submit a claim batch to the insurer",
)
def submit_batch(
    batch_id: int,
    payload: ClaimBatchSubmitSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_MANAGE"))],
    service: Annotated[ClaimBatchService, Depends(get_batch_service)],
):
    b = service.submit(batch_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Batch submitted.", "batch": _batch_dict(b)}


@batch_router.post(
    "/{batch_id}/acknowledge",
    response_model=ClaimBatchActionResponseSchema,
    summary="Mark batch as acknowledged by the insurer",
)
def acknowledge_batch(
    batch_id: int,
    payload: ClaimBatchAcknowledgeSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_REVIEW", "CLAIM_MANAGE"))],
    service: Annotated[ClaimBatchService, Depends(get_batch_service)],
):
    b = service.acknowledge(batch_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Batch acknowledged.", "batch": _batch_dict(b)}


# ============================================================
# CLAIM
# ============================================================


@claim_router.get(
    "/",
    response_model=InsuranceClaimListResponseSchema,
    summary="List insurance claims",
)
def list_claims(
    _: Annotated[User, Depends(require_permission("CLAIM_READ", "CLAIM_MANAGE"))],
    service: Annotated[InsuranceClaimService, Depends(get_claim_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    statuses: Optional[list[str]] = Query(None),
    insurance_provider_id: Optional[int] = Query(None),
    patient_id: Optional[int] = Query(None),
    visit_id: Optional[int] = Query(None),
    invoice_id: Optional[int] = Query(None),
    batch_id: Optional[int] = Query(None),
):
    items, total = service.list_claims(
        skip=skip,
        limit=limit,
        statuses=statuses,
        insurance_provider_id=insurance_provider_id,
        patient_id=patient_id,
        visit_id=visit_id,
        invoice_id=invoice_id,
        batch_id=batch_id,
    )
    return paginate_response(
        items=[_claim_dict(c) for c in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Insurance claims fetched successfully.",
    )


@claim_router.post(
    "/",
    response_model=InsuranceClaimActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new insurance claim",
)
def create_claim(
    payload: InsuranceClaimCreateSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_MANAGE"))],
    service: Annotated[InsuranceClaimService, Depends(get_claim_service)],
):
    c = service.create_claim(payload, actor_user_id=user.id)
    return {"success": True, "message": "Insurance claim created.", "claim": _claim_dict(c)}


@claim_router.get(
    "/{claim_id}",
    summary="Get a single insurance claim",
)
def get_claim(
    claim_id: int,
    _: Annotated[User, Depends(require_permission("CLAIM_READ", "CLAIM_MANAGE"))],
    service: Annotated[InsuranceClaimService, Depends(get_claim_service)],
):
    return _claim_dict(service.get(claim_id))


@claim_router.post(
    "/{claim_id}/submit",
    response_model=InsuranceClaimActionResponseSchema,
    summary="Submit a claim",
)
def submit_claim(
    claim_id: int,
    payload: InsuranceClaimSubmitSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_MANAGE"))],
    service: Annotated[InsuranceClaimService, Depends(get_claim_service)],
):
    c = service.submit(claim_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Claim submitted.", "claim": _claim_dict(c)}


@claim_router.post(
    "/{claim_id}/withdraw",
    response_model=InsuranceClaimActionResponseSchema,
    summary="Withdraw a claim",
)
def withdraw_claim(
    claim_id: int,
    user: Annotated[User, Depends(require_permission("CLAIM_MANAGE"))],
    service: Annotated[InsuranceClaimService, Depends(get_claim_service)],
    reason: Optional[str] = Query(None, description="Reason for withdrawal"),
):
    c = service.withdraw(claim_id, reason=reason, actor_user_id=user.id)
    return {"success": True, "message": "Claim withdrawn.", "claim": _claim_dict(c)}


# ============================================================
# AUTHORIZATION
# ============================================================


@auth_router.get(
    "/claims/{claim_id}",
    summary="List authorizations for a claim",
)
def list_authorizations(
    claim_id: int,
    _: Annotated[User, Depends(require_permission("CLAIM_READ", "CLAIM_MANAGE"))],
    service: Annotated[ClaimAuthorizationService, Depends(get_auth_service)],
):
    auths = service.list_for_claim(claim_id)
    return {
        "success": True,
        "message": "Authorizations fetched successfully.",
        "items": [_auth_dict(a) for a in auths],
        "count": len(auths),
    }


@auth_router.post(
    "/",
    response_model=ClaimAuthorizationActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Request a pre-authorization",
)
def request_authorization(
    payload: ClaimAuthorizationCreateSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_MANAGE"))],
    service: Annotated[ClaimAuthorizationService, Depends(get_auth_service)],
):
    a = service.request(payload, actor_user_id=user.id)
    return {
        "success": True,
        "message": "Authorization requested.",
        "authorization": _auth_dict(a),
    }


@auth_router.post(
    "/{auth_id}/decide",
    response_model=ClaimAuthorizationActionResponseSchema,
    summary="Decide an outstanding authorization",
)
def decide_authorization(
    auth_id: int,
    payload: ClaimAuthorizationDecisionSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_REVIEW"))],
    service: Annotated[ClaimAuthorizationService, Depends(get_auth_service)],
):
    a = service.decide(auth_id, payload, actor_user_id=user.id)
    return {
        "success": True,
        "message": "Authorization decided.",
        "authorization": _auth_dict(a),
    }


# ============================================================
# ADJUDICATION
# ============================================================


@adjudication_router.get(
    "/claims/{claim_id}",
    summary="List adjudications for a claim",
)
def list_adjudications(
    claim_id: int,
    _: Annotated[User, Depends(require_permission("CLAIM_READ", "CLAIM_MANAGE"))],
    service: Annotated[ClaimAdjudicationService, Depends(get_adjudication_service)],
):
    items = service.list_for_claim(claim_id)
    return {
        "success": True,
        "message": "Adjudications fetched successfully.",
        "items": [_adjudication_dict(a) for a in items],
        "count": len(items),
    }


@adjudication_router.post(
    "/",
    response_model=ClaimAdjudicationActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record an insurer's adjudication on a claim",
)
def record_adjudication(
    payload: ClaimAdjudicationCreateSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_REVIEW"))],
    service: Annotated[ClaimAdjudicationService, Depends(get_adjudication_service)],
):
    a = service.record(payload, actor_user_id=user.id)
    return {
        "success": True,
        "message": "Adjudication recorded.",
        "adjudication": _adjudication_dict(a),
    }


# ============================================================
# PAYMENT
# ============================================================


@payment_router.get(
    "/claims/{claim_id}",
    summary="List payments against a claim",
)
def list_payments(
    claim_id: int,
    _: Annotated[User, Depends(require_permission("CLAIM_READ", "CLAIM_MANAGE"))],
    service: Annotated[ClaimPaymentService, Depends(get_payment_service)],
):
    payments = service.list_for_claim(claim_id)
    return {
        "success": True,
        "message": "Claim payments fetched successfully.",
        "items": [_payment_dict(p) for p in payments],
        "count": len(payments),
    }


@payment_router.post(
    "/",
    response_model=ClaimPaymentActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment received from the insurer",
)
def record_payment(
    payload: ClaimPaymentCreateSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_MANAGE", "CLAIM_REVIEW"))],
    service: Annotated[ClaimPaymentService, Depends(get_payment_service)],
):
    p = service.record(payload, actor_user_id=user.id)
    return {"success": True, "message": "Payment recorded.", "payment": _payment_dict(p)}


# ============================================================
# APPEAL
# ============================================================


@appeal_router.get(
    "/claims/{claim_id}",
    summary="List appeals on a claim",
)
def list_appeals(
    claim_id: int,
    _: Annotated[User, Depends(require_permission("CLAIM_READ", "CLAIM_MANAGE"))],
    service: Annotated[ClaimAppealService, Depends(get_appeal_service)],
):
    appeals = service.list_for_claim(claim_id)
    return {
        "success": True,
        "message": "Appeals fetched successfully.",
        "items": [_appeal_dict(a) for a in appeals],
        "count": len(appeals),
    }


@appeal_router.post(
    "/",
    response_model=ClaimAppealActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Submit an appeal on a (partially) rejected claim",
)
def submit_appeal(
    payload: ClaimAppealCreateSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_MANAGE"))],
    service: Annotated[ClaimAppealService, Depends(get_appeal_service)],
):
    a = service.submit(payload, actor_user_id=user.id)
    return {"success": True, "message": "Appeal submitted.", "appeal": _appeal_dict(a)}


@appeal_router.post(
    "/{appeal_id}/decide",
    response_model=ClaimAppealActionResponseSchema,
    summary="Decide an appeal",
)
def decide_appeal(
    appeal_id: int,
    payload: ClaimAppealDecisionSchema,
    user: Annotated[User, Depends(require_permission("CLAIM_REVIEW"))],
    service: Annotated[ClaimAppealService, Depends(get_appeal_service)],
):
    a = service.decide(appeal_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Appeal decided.", "appeal": _appeal_dict(a)}
