# app/services/insurance_claim_service.py
from __future__ import annotations

"""
Service layer for the Insurance Claims module.

Composes repositories, audit, and totals roll-up into the orchestration
needed for the full revenue-cycle insurance loop.

Service classes:
- :class:`ClaimBatchService`         — batch CRUD + submit / acknowledge
- :class:`InsuranceClaimService`     — create / submit / withdraw a claim
- :class:`ClaimAuthorizationService` — request + decision
- :class:`ClaimAdjudicationService`  — record insurer's adjudication
- :class:`ClaimPaymentService`       — record receipts (idempotent on reference)
- :class:`ClaimAppealService`        — submit + decide appeals

Business rules:
- ``ClaimBatch`` totals are recomputed from constituent claims on every change.
- ``InsuranceClaim`` ``billed_amount`` is recomputed from line items.
- Adjudication outcomes drive ``InsuranceClaim.status`` transitions.
- ``ClaimPayment`` totals are tracked against ``approved_amount``; once
  ``paid_amount >= approved_amount`` the claim status flips to ``PAID``.
- ``ClaimAppeal`` decisions can adjust ``approved_amount`` upward and flip
  the parent claim back to ``APPROVED`` / ``PARTIALLY_APPROVED``.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    AuthorizationStatus,
    ClaimAppealStatus,
    ClaimBatchStatus,
    InsuranceClaimStatus,
)
from app.core.exceptions import BadRequestError
from app.models.all_models import (
    ClaimAdjudication,
    ClaimAppeal,
    ClaimAuthorization,
    ClaimBatch,
    ClaimPayment,
    InsuranceClaim,
)
from app.repositories.insurance_claim_repository import (
    ClaimAdjudicationRepository,
    ClaimAppealRepository,
    ClaimAuthorizationRepository,
    ClaimBatchRepository,
    ClaimPaymentRepository,
    InsuranceClaimRepository,
)
from app.schemas.insurance_claim_schemas import (
    ClaimAdjudicationCreateSchema,
    ClaimAppealCreateSchema,
    ClaimAppealDecisionSchema,
    ClaimAuthorizationCreateSchema,
    ClaimAuthorizationDecisionSchema,
    ClaimBatchAcknowledgeSchema,
    ClaimBatchCreateSchema,
    ClaimBatchSubmitSchema,
    ClaimPaymentCreateSchema,
    InsuranceClaimCreateSchema,
    InsuranceClaimSubmitSchema,
)
from app.utils.security_event_util import record_security_event


# ============================================================
# CLAIM BATCH
# ============================================================


class ClaimBatchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ClaimBatchRepository(db)
        self.claim_repository = InsuranceClaimRepository(db)

    def get(self, batch_id: int) -> ClaimBatch:
        return self.repository.get_required_by_id(batch_id)

    def list_batches(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        statuses: Optional[list[str]] = None,
        insurance_provider_id: Optional[int] = None,
        facility_id: Optional[int] = None,
    ):
        normalized = (
            [ClaimBatchStatus(s.strip().upper()) for s in statuses] if statuses else None
        )
        return self.repository.list_batches(
            skip=skip,
            limit=limit,
            statuses=normalized,
            insurance_provider_id=insurance_provider_id,
            facility_id=facility_id,
        )

    def create(
        self,
        payload: ClaimBatchCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ClaimBatch:
        b = self.repository.create(**payload.model_dump(exclude_unset=True))
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="CLAIM_BATCH_CREATED",
            severity="INFO",
            event_detail=f"Claim batch {b.batch_no} created.",
            event_metadata={"batch_id": b.id},
        )
        self.db.commit()
        return self.repository.get_required_by_id(b.id)

    def submit(
        self,
        batch_id: int,
        payload: ClaimBatchSubmitSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ClaimBatch:
        b = self.repository.get_required_by_id(batch_id)
        if b.status != ClaimBatchStatus.DRAFT:
            raise BadRequestError(
                message="Only DRAFT batches can be submitted.",
                detail={"status": str(b.status)},
            )
        # Recompute totals before submission
        self.repository.recompute_totals(b)
        if (b.total_claims or 0) <= 0:
            raise BadRequestError(
                message="Cannot submit an empty batch.",
                detail={"batch_id": b.id},
            )
        b.status = ClaimBatchStatus.SUBMITTED
        b.submitted_at = datetime.now(timezone.utc)
        if payload.submitted_by_staff_id is not None:
            b.submitted_by_staff_id = payload.submitted_by_staff_id
        if payload.notes:
            b.notes = (b.notes or "") + f"\n[SUBMIT] {payload.notes}"
        self.repository.save(b)

        # Cascade — flip every still-DRAFT claim in the batch to SUBMITTED.
        for c in b.claims or []:
            if c.is_deleted:
                continue
            if c.status == InsuranceClaimStatus.DRAFT:
                c.status = InsuranceClaimStatus.SUBMITTED
                c.submitted_at = b.submitted_at
                self.claim_repository.save(c)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="CLAIM_BATCH_SUBMITTED",
            severity="INFO",
            event_detail=f"Claim batch {b.batch_no} submitted with {b.total_claims} claims.",
            event_metadata={
                "batch_id": b.id,
                "total_claims": b.total_claims,
                "total_billed_amount": str(b.total_billed_amount),
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(b.id)

    def acknowledge(
        self,
        batch_id: int,
        payload: ClaimBatchAcknowledgeSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ClaimBatch:
        b = self.repository.get_required_by_id(batch_id)
        if b.status != ClaimBatchStatus.SUBMITTED:
            raise BadRequestError(
                message="Only SUBMITTED batches can be acknowledged.",
                detail={"status": str(b.status)},
            )
        b.status = ClaimBatchStatus.ACKNOWLEDGED
        b.acknowledged_at = payload.acknowledged_at or datetime.now(timezone.utc)
        if payload.notes:
            b.notes = (b.notes or "") + f"\n[ACK] {payload.notes}"
        self.repository.save(b)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="CLAIM_BATCH_ACKNOWLEDGED",
            severity="INFO",
            event_detail=f"Claim batch {b.batch_no} acknowledged by insurer.",
            event_metadata={"batch_id": b.id},
        )
        self.db.commit()
        return self.repository.get_required_by_id(b.id)


# ============================================================
# INSURANCE CLAIM
# ============================================================


class InsuranceClaimService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InsuranceClaimRepository(db)
        self.batch_repository = ClaimBatchRepository(db)
        self.payment_repository = ClaimPaymentRepository(db)

    def get(self, claim_id: int) -> InsuranceClaim:
        return self.repository.get_required_by_id(claim_id)

    def list_claims(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        statuses: Optional[list[str]] = None,
        insurance_provider_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        visit_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        batch_id: Optional[int] = None,
    ):
        normalized = (
            [InsuranceClaimStatus(s.strip().upper()) for s in statuses]
            if statuses
            else None
        )
        return self.repository.list_claims(
            skip=skip,
            limit=limit,
            statuses=normalized,
            insurance_provider_id=insurance_provider_id,
            patient_id=patient_id,
            visit_id=visit_id,
            invoice_id=invoice_id,
            batch_id=batch_id,
        )

    def create_claim(
        self,
        payload: InsuranceClaimCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> InsuranceClaim:
        # Validate batch (if provided) — must be DRAFT
        if payload.batch_id is not None:
            batch = self.batch_repository.get_required_by_id(payload.batch_id)
            if batch.status != ClaimBatchStatus.DRAFT:
                raise BadRequestError(
                    message="Cannot add a claim to a non-DRAFT batch.",
                    detail={"batch_id": batch.id, "batch_status": str(batch.status)},
                )

        claim = self.repository.create(
            patient_id=payload.patient_id,
            patient_insurance_id=payload.patient_insurance_id,
            insurance_provider_id=payload.insurance_provider_id,
            visit_id=payload.visit_id,
            invoice_id=payload.invoice_id,
            facility_id=payload.facility_id,
            batch_id=payload.batch_id,
            service_date=payload.service_date,
            diagnosis_codes=payload.diagnosis_codes,
            primary_diagnosis_text=payload.primary_diagnosis_text,
            notes=payload.notes,
        )

        for entry in payload.items:
            self.repository.add_item(
                claim_id=claim.id,
                invoice_item_id=entry.invoice_item_id,
                billable_service_id=entry.billable_service_id,
                service_date=entry.service_date,
                procedure_code=entry.procedure_code,
                diagnosis_code=entry.diagnosis_code,
                description=entry.description,
                quantity=entry.quantity,
                unit_price=entry.unit_price,
            )

        self.repository.recompute_billed(claim)
        if payload.batch_id is not None:
            self.batch_repository.recompute_totals(
                self.batch_repository.get_required_by_id(payload.batch_id)
            )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INSURANCE_CLAIM_CREATED",
            severity="INFO",
            event_detail=f"Insurance claim {claim.claim_no} created.",
            event_metadata={
                "claim_id": claim.id,
                "patient_id": claim.patient_id,
                "billed_amount": str(claim.billed_amount),
            },
        )
        self.db.commit()
        return self.repository.get_required_by_id(claim.id)

    def submit(
        self,
        claim_id: int,
        payload: InsuranceClaimSubmitSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> InsuranceClaim:
        claim = self.repository.get_required_by_id(claim_id)
        if claim.status not in {
            InsuranceClaimStatus.DRAFT,
            InsuranceClaimStatus.AUTHORIZED,
        }:
            raise BadRequestError(
                message="Only DRAFT or AUTHORIZED claims can be submitted.",
                detail={"status": str(claim.status)},
            )
        claim.status = InsuranceClaimStatus.SUBMITTED
        claim.submitted_at = datetime.now(timezone.utc)
        if payload.notes:
            claim.notes = (claim.notes or "") + f"\n[SUBMIT] {payload.notes}"
        self.repository.save(claim)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INSURANCE_CLAIM_SUBMITTED",
            severity="INFO",
            event_detail=f"Claim {claim.claim_no} submitted.",
            event_metadata={"claim_id": claim.id},
        )
        self.db.commit()
        return self.repository.get_required_by_id(claim.id)

    def withdraw(
        self,
        claim_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> InsuranceClaim:
        claim = self.repository.get_required_by_id(claim_id)
        if claim.status in {
            InsuranceClaimStatus.PAID,
            InsuranceClaimStatus.CLOSED,
        }:
            raise BadRequestError(
                message="Cannot withdraw a paid or closed claim.",
                detail={"status": str(claim.status)},
            )
        claim.status = InsuranceClaimStatus.CLOSED
        claim.notes = (claim.notes or "") + f"\n[WITHDRAW] {reason or 'No reason given.'}"
        self.repository.save(claim)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INSURANCE_CLAIM_WITHDRAWN",
            severity="WARNING",
            event_detail=f"Claim {claim.claim_no} withdrawn.",
            event_metadata={"claim_id": claim.id, "reason": reason},
        )
        self.db.commit()
        return self.repository.get_required_by_id(claim.id)


# ============================================================
# AUTHORIZATION
# ============================================================


class ClaimAuthorizationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ClaimAuthorizationRepository(db)
        self.claim_repository = InsuranceClaimRepository(db)

    def list_for_claim(self, claim_id: int) -> list[ClaimAuthorization]:
        self.claim_repository.get_required_by_id(claim_id)
        return self.repository.list_for_claim(claim_id)

    def request(
        self,
        payload: ClaimAuthorizationCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ClaimAuthorization:
        # If a claim is supplied, mark it PENDING_AUTH for downstream visibility.
        if payload.claim_id is not None:
            claim = self.claim_repository.get_required_by_id(payload.claim_id)
            if claim.status == InsuranceClaimStatus.DRAFT:
                claim.status = InsuranceClaimStatus.PENDING_AUTH
                self.claim_repository.save(claim)
        a = self.repository.create(
            claim_id=payload.claim_id,
            patient_insurance_id=payload.patient_insurance_id,
            requested_service=payload.requested_service,
            requested_amount=payload.requested_amount,
            requested_at=payload.requested_at or datetime.now(timezone.utc),
            decision_reason=payload.decision_reason,
        )
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="CLAIM_AUTHORIZATION_REQUESTED",
            severity="INFO",
            event_detail=(
                f"Authorization requested for service '{payload.requested_service}'."
            ),
            event_metadata={"authorization_id": a.id, "claim_id": a.claim_id},
        )
        self.db.commit()
        return a

    def decide(
        self,
        auth_id: int,
        payload: ClaimAuthorizationDecisionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ClaimAuthorization:
        a = self.repository.get_required_by_id(auth_id)
        if a.status not in {
            AuthorizationStatus.REQUESTED,
            AuthorizationStatus.PENDING,
        }:
            raise BadRequestError(
                message="This authorization is no longer awaiting a decision.",
                detail={"status": str(a.status)},
            )
        a.status = AuthorizationStatus(payload.decision)
        a.authorization_no = payload.authorization_no or a.authorization_no
        a.approved_amount = (
            payload.approved_amount if payload.approved_amount is not None
            else a.approved_amount
        )
        a.valid_from = payload.valid_from or a.valid_from
        a.valid_until = payload.valid_until or a.valid_until
        a.decision_reason = payload.decision_reason or a.decision_reason
        a.decided_at = datetime.now(timezone.utc)
        self.repository.save(a)

        # Reflect the decision on the parent claim where possible.
        if a.claim_id is not None:
            claim = self.claim_repository.get_required_by_id(a.claim_id)
            if a.status in {
                AuthorizationStatus.APPROVED,
                AuthorizationStatus.PARTIALLY_APPROVED,
            }:
                if claim.status in {
                    InsuranceClaimStatus.DRAFT,
                    InsuranceClaimStatus.PENDING_AUTH,
                }:
                    claim.status = InsuranceClaimStatus.AUTHORIZED
                    self.claim_repository.save(claim)
            elif a.status == AuthorizationStatus.DECLINED:
                if claim.status == InsuranceClaimStatus.PENDING_AUTH:
                    claim.status = InsuranceClaimStatus.REJECTED
                    self.claim_repository.save(claim)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="CLAIM_AUTHORIZATION_DECIDED",
            severity="INFO",
            event_detail=(
                f"Authorization {a.id} decided as {a.status.value}."
            ),
            event_metadata={"authorization_id": a.id, "decision": a.status.value},
        )
        self.db.commit()
        return a


# ============================================================
# ADJUDICATION
# ============================================================


class ClaimAdjudicationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ClaimAdjudicationRepository(db)
        self.claim_repository = InsuranceClaimRepository(db)
        self.batch_repository = ClaimBatchRepository(db)

    def list_for_claim(self, claim_id: int) -> list[ClaimAdjudication]:
        self.claim_repository.get_required_by_id(claim_id)
        return self.repository.list_for_claim(claim_id)

    def record(
        self,
        payload: ClaimAdjudicationCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ClaimAdjudication:
        from app.core.enums import AdjudicationOutcome

        claim = self.claim_repository.get_required_by_id(payload.claim_id)
        if claim.status not in {
            InsuranceClaimStatus.SUBMITTED,
            InsuranceClaimStatus.UNDER_REVIEW,
            InsuranceClaimStatus.AUTHORIZED,
            InsuranceClaimStatus.APPEALED,
        }:
            raise BadRequestError(
                message="Cannot adjudicate a claim that is not in a reviewable state.",
                detail={"status": str(claim.status)},
            )
        a = self.repository.create(
            claim_id=claim.id,
            outcome=AdjudicationOutcome(payload.outcome),
            approved_amount=payload.approved_amount,
            rejected_amount=payload.rejected_amount,
            adjudication_no=payload.adjudication_no,
            rejection_codes=payload.rejection_codes,
            explanation_of_benefit=payload.explanation_of_benefit,
            adjudicated_at=payload.adjudicated_at or datetime.now(timezone.utc),
        )

        # Reflect totals + status on the claim.
        claim.approved_amount = Decimal(payload.approved_amount or 0)
        claim.rejected_amount = Decimal(payload.rejected_amount or 0)
        claim.patient_responsibility_amount = (
            Decimal(claim.billed_amount or 0) - claim.approved_amount
        )
        if claim.patient_responsibility_amount < 0:
            claim.patient_responsibility_amount = Decimal("0")

        outcome = AdjudicationOutcome(payload.outcome)
        if outcome == AdjudicationOutcome.APPROVED:
            claim.status = InsuranceClaimStatus.APPROVED
        elif outcome == AdjudicationOutcome.PARTIALLY_APPROVED:
            claim.status = InsuranceClaimStatus.PARTIALLY_APPROVED
        elif outcome == AdjudicationOutcome.DENIED:
            claim.status = InsuranceClaimStatus.REJECTED
        else:  # PENDING
            claim.status = InsuranceClaimStatus.UNDER_REVIEW
        self.claim_repository.save(claim)

        # Roll-up onto the batch.
        if claim.batch_id is not None:
            batch = self.batch_repository.get_required_by_id(claim.batch_id)
            self.batch_repository.recompute_totals(batch)
            if outcome == AdjudicationOutcome.PENDING:
                pass
            else:
                if batch.status == ClaimBatchStatus.SUBMITTED:
                    batch.status = ClaimBatchStatus.ACKNOWLEDGED
                if batch.status == ClaimBatchStatus.ACKNOWLEDGED:
                    batch.status = ClaimBatchStatus.PARTIALLY_ADJUDICATED
                self.batch_repository.save(batch)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="CLAIM_ADJUDICATED",
            severity="INFO",
            event_detail=(
                f"Claim {claim.claim_no} adjudicated as {outcome.value}: "
                f"approved={claim.approved_amount} rejected={claim.rejected_amount}."
            ),
            event_metadata={
                "claim_id": claim.id,
                "outcome": outcome.value,
                "approved_amount": str(claim.approved_amount),
                "rejected_amount": str(claim.rejected_amount),
            },
        )
        self.db.commit()
        return a


# ============================================================
# PAYMENT
# ============================================================


class ClaimPaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ClaimPaymentRepository(db)
        self.claim_repository = InsuranceClaimRepository(db)
        self.batch_repository = ClaimBatchRepository(db)

    def list_for_claim(self, claim_id: int) -> list[ClaimPayment]:
        self.claim_repository.get_required_by_id(claim_id)
        return self.repository.list_for_claim(claim_id)

    def record(
        self,
        payload: ClaimPaymentCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ClaimPayment:
        claim = self.claim_repository.get_required_by_id(payload.claim_id)
        if claim.status not in {
            InsuranceClaimStatus.APPROVED,
            InsuranceClaimStatus.PARTIALLY_APPROVED,
            InsuranceClaimStatus.PAID,
        }:
            raise BadRequestError(
                message="Cannot record a payment on an unapproved claim.",
                detail={"claim_id": claim.id, "status": str(claim.status)},
            )

        p = self.repository.create(
            claim_id=claim.id,
            payment_reference=payload.payment_reference,
            amount=payload.amount,
            currency=payload.currency,
            paid_at=payload.paid_at or datetime.now(timezone.utc),
            payment_method=payload.payment_method,
            notes=payload.notes,
        )

        # Roll-up paid amount + close out claim if fully paid.
        claim.paid_amount = self.repository.total_paid(claim.id)
        if claim.paid_amount >= (claim.approved_amount or Decimal("0")):
            claim.status = InsuranceClaimStatus.PAID
        self.claim_repository.save(claim)

        # Reflect on batch — once every claim in batch is PAID, batch is PAID.
        if claim.batch_id is not None:
            batch = self.batch_repository.get_required_by_id(claim.batch_id)
            self.batch_repository.recompute_totals(batch)
            siblings = batch.claims or []
            if siblings and all(
                c.status == InsuranceClaimStatus.PAID
                for c in siblings
                if not c.is_deleted
            ):
                batch.status = ClaimBatchStatus.PAID
                self.batch_repository.save(batch)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="CLAIM_PAYMENT_RECORDED",
            severity="INFO",
            event_detail=(
                f"Payment {p.payment_reference} of {p.amount} recorded "
                f"on claim {claim.claim_no}."
            ),
            event_metadata={
                "claim_id": claim.id,
                "payment_id": p.id,
                "amount": str(p.amount),
            },
        )
        self.db.commit()
        return p


# ============================================================
# APPEAL
# ============================================================


class ClaimAppealService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ClaimAppealRepository(db)
        self.claim_repository = InsuranceClaimRepository(db)

    def list_for_claim(self, claim_id: int) -> list[ClaimAppeal]:
        self.claim_repository.get_required_by_id(claim_id)
        return self.repository.list_for_claim(claim_id)

    def submit(
        self,
        payload: ClaimAppealCreateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ClaimAppeal:
        claim = self.claim_repository.get_required_by_id(payload.claim_id)
        if claim.status not in {
            InsuranceClaimStatus.REJECTED,
            InsuranceClaimStatus.PARTIALLY_APPROVED,
        }:
            raise BadRequestError(
                message="Only rejected or partially-approved claims can be appealed.",
                detail={"status": str(claim.status)},
            )
        a = self.repository.create(
            claim_id=claim.id,
            appeal_text=payload.appeal_text,
            submitted_by_staff_id=payload.submitted_by_staff_id,
            additional_evidence_url=payload.additional_evidence_url,
            additional_amount_requested=payload.additional_amount_requested,
            status=ClaimAppealStatus.SUBMITTED,
            submitted_at=datetime.now(timezone.utc),
        )
        claim.status = InsuranceClaimStatus.APPEALED
        self.claim_repository.save(claim)
        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="CLAIM_APPEAL_SUBMITTED",
            severity="INFO",
            event_detail=f"Appeal {a.appeal_no} submitted on claim {claim.claim_no}.",
            event_metadata={"appeal_id": a.id, "claim_id": claim.id},
        )
        self.db.commit()
        return a

    def decide(
        self,
        appeal_id: int,
        payload: ClaimAppealDecisionSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> ClaimAppeal:
        a = self.repository.get_required_by_id(appeal_id)
        if a.status not in {ClaimAppealStatus.SUBMITTED, ClaimAppealStatus.UNDER_REVIEW}:
            raise BadRequestError(
                message="Only submitted or under-review appeals can be decided.",
                detail={"status": str(a.status)},
            )
        a.status = ClaimAppealStatus(payload.decision)
        a.decision_text = payload.decision_text
        a.additional_amount_approved = payload.additional_amount_approved
        a.decided_at = datetime.now(timezone.utc)
        self.repository.save(a)

        # Adjust the parent claim's approved_amount if the appeal was overturned.
        claim = self.claim_repository.get_required_by_id(a.claim_id)
        if a.status in {
            ClaimAppealStatus.OVERTURNED,
            ClaimAppealStatus.PARTIALLY_OVERTURNED,
        }:
            uplift = Decimal(payload.additional_amount_approved or 0)
            if uplift > 0:
                claim.approved_amount = (claim.approved_amount or Decimal("0")) + uplift
                if claim.rejected_amount is not None:
                    claim.rejected_amount = max(
                        Decimal("0"), claim.rejected_amount - uplift
                    )
                claim.patient_responsibility_amount = max(
                    Decimal("0"),
                    Decimal(claim.billed_amount or 0) - claim.approved_amount,
                )
            # Roll claim status forward
            if a.status == ClaimAppealStatus.OVERTURNED:
                claim.status = InsuranceClaimStatus.APPROVED
            else:
                claim.status = InsuranceClaimStatus.PARTIALLY_APPROVED
        elif a.status == ClaimAppealStatus.UPHELD:
            # No change to approved_amount; original rejection stands.
            claim.status = InsuranceClaimStatus.REJECTED
        elif a.status == ClaimAppealStatus.WITHDRAWN:
            # Restore previous status (best-effort: keep current rejection).
            claim.status = InsuranceClaimStatus.REJECTED
        self.claim_repository.save(claim)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="CLAIM_APPEAL_DECIDED",
            severity="INFO",
            event_detail=f"Appeal {a.appeal_no} decided as {a.status.value}.",
            event_metadata={
                "appeal_id": a.id,
                "claim_id": claim.id,
                "decision": a.status.value,
            },
        )
        self.db.commit()
        return a
