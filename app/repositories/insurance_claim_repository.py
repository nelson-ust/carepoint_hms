# app/repositories/insurance_claim_repository.py
from __future__ import annotations

"""
Repository layer for the Insurance Claims module.

Repositories:
- ``ClaimBatchRepository``         — batch CRUD + totals roll-up helpers
- ``InsuranceClaimRepository``     — claim header + items
- ``ClaimAuthorizationRepository`` — pre-auth records
- ``ClaimAdjudicationRepository``  — adjudication decisions
- ``ClaimPaymentRepository``       — receipts against approved amount
- ``ClaimAppealRepository``        — appeal records
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.enums import (
    ClaimAppealStatus,
    ClaimBatchStatus,
    InsuranceClaimStatus,
)
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import (
    ClaimAdjudication,
    ClaimAppeal,
    ClaimAuthorization,
    ClaimBatch,
    ClaimPayment,
    InsuranceClaim,
    InsuranceClaimItem,
)
from app.utils.helpers import generate_uuid_str


# ============================================================
# CLAIM BATCH
# ============================================================


class ClaimBatchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, batch_id: int) -> Optional[ClaimBatch]:
        return (
            self.db.query(ClaimBatch)
            .options(selectinload(ClaimBatch.claims))
            .filter(ClaimBatch.id == batch_id, ClaimBatch.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, batch_id: int) -> ClaimBatch:
        b = self.get_by_id(batch_id)
        if not b:
            raise NotFoundError(
                message="Claim batch not found.", detail={"batch_id": batch_id}
            )
        return b

    def get_by_batch_no(self, batch_no: str) -> Optional[ClaimBatch]:
        return (
            self.db.query(ClaimBatch)
            .filter(
                ClaimBatch.batch_no == batch_no.strip(),
                ClaimBatch.is_deleted.is_(False),
            )
            .first()
        )

    def list_batches(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        statuses: Optional[list[ClaimBatchStatus]] = None,
        insurance_provider_id: Optional[int] = None,
        facility_id: Optional[int] = None,
    ) -> tuple[list[ClaimBatch], int]:
        query = self.db.query(ClaimBatch).filter(ClaimBatch.is_deleted.is_(False))
        if statuses:
            query = query.filter(ClaimBatch.status.in_(statuses))
        if insurance_provider_id is not None:
            query = query.filter(
                ClaimBatch.insurance_provider_id == insurance_provider_id
            )
        if facility_id is not None:
            query = query.filter(ClaimBatch.facility_id == facility_id)
        total = query.with_entities(func.count(ClaimBatch.id)).scalar() or 0
        items = query.order_by(ClaimBatch.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def generate_batch_no(self) -> str:
        return f"CLB-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create(self, **kwargs) -> ClaimBatch:
        kwargs.setdefault("batch_no", self.generate_batch_no())
        kwargs.setdefault("status", ClaimBatchStatus.DRAFT)
        b = ClaimBatch(**kwargs)
        self.db.add(b)
        self.db.flush()
        self.db.refresh(b)
        return b

    def save(self, b: ClaimBatch) -> ClaimBatch:
        self.db.add(b)
        self.db.flush()
        self.db.refresh(b)
        return b

    def recompute_totals(self, batch: ClaimBatch) -> ClaimBatch:
        """Sum up totals from all non-deleted claims in the batch."""
        rows = (
            self.db.query(
                func.count(InsuranceClaim.id),
                func.coalesce(func.sum(InsuranceClaim.billed_amount), 0),
                func.coalesce(func.sum(InsuranceClaim.approved_amount), 0),
            )
            .filter(
                InsuranceClaim.batch_id == batch.id,
                InsuranceClaim.is_deleted.is_(False),
            )
            .first()
        )
        if rows:
            count, billed, approved = rows
            batch.total_claims = int(count or 0)
            batch.total_billed_amount = Decimal(billed or 0)
            batch.total_approved_amount = Decimal(approved or 0)
            self.db.add(batch)
            self.db.flush()
            self.db.refresh(batch)
        return batch


# ============================================================
# INSURANCE CLAIM
# ============================================================


class InsuranceClaimRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, claim_id: int) -> Optional[InsuranceClaim]:
        return (
            self.db.query(InsuranceClaim)
            .options(
                selectinload(InsuranceClaim.items),
                selectinload(InsuranceClaim.authorizations),
                selectinload(InsuranceClaim.adjudications),
                selectinload(InsuranceClaim.claim_payments),
                selectinload(InsuranceClaim.appeals),
            )
            .filter(
                InsuranceClaim.id == claim_id,
                InsuranceClaim.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, claim_id: int) -> InsuranceClaim:
        c = self.get_by_id(claim_id)
        if not c:
            raise NotFoundError(
                message="Insurance claim not found.", detail={"claim_id": claim_id}
            )
        return c

    def get_by_claim_no(self, claim_no: str) -> Optional[InsuranceClaim]:
        return (
            self.db.query(InsuranceClaim)
            .filter(
                InsuranceClaim.claim_no == claim_no.strip(),
                InsuranceClaim.is_deleted.is_(False),
            )
            .first()
        )

    def list_claims(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        statuses: Optional[list[InsuranceClaimStatus]] = None,
        insurance_provider_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        visit_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        batch_id: Optional[int] = None,
    ) -> tuple[list[InsuranceClaim], int]:
        query = (
            self.db.query(InsuranceClaim)
            .options(selectinload(InsuranceClaim.items))
            .filter(InsuranceClaim.is_deleted.is_(False))
        )
        if statuses:
            query = query.filter(InsuranceClaim.status.in_(statuses))
        if insurance_provider_id is not None:
            query = query.filter(
                InsuranceClaim.insurance_provider_id == insurance_provider_id
            )
        if patient_id is not None:
            query = query.filter(InsuranceClaim.patient_id == patient_id)
        if visit_id is not None:
            query = query.filter(InsuranceClaim.visit_id == visit_id)
        if invoice_id is not None:
            query = query.filter(InsuranceClaim.invoice_id == invoice_id)
        if batch_id is not None:
            query = query.filter(InsuranceClaim.batch_id == batch_id)
        total = query.with_entities(func.count(InsuranceClaim.id)).scalar() or 0
        items = (
            query.order_by(InsuranceClaim.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def generate_claim_no(self) -> str:
        return f"CLM-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create(self, **kwargs) -> InsuranceClaim:
        kwargs.setdefault("claim_no", self.generate_claim_no())
        kwargs.setdefault("status", InsuranceClaimStatus.DRAFT)
        if "billed_amount" not in kwargs:
            kwargs["billed_amount"] = Decimal("0")
        c = InsuranceClaim(**kwargs)
        self.db.add(c)
        self.db.flush()
        self.db.refresh(c)
        return c

    def save(self, c: InsuranceClaim) -> InsuranceClaim:
        self.db.add(c)
        self.db.flush()
        self.db.refresh(c)
        return c

    def add_item(self, **kwargs) -> InsuranceClaimItem:
        quantity = Decimal(kwargs.get("quantity", 1) or 1)
        unit_price = Decimal(kwargs.get("unit_price", 0) or 0)
        kwargs.setdefault("billed_amount", quantity * unit_price)
        item = InsuranceClaimItem(**kwargs)
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def items_for_claim(self, claim_id: int) -> list[InsuranceClaimItem]:
        return (
            self.db.query(InsuranceClaimItem)
            .filter(
                InsuranceClaimItem.claim_id == claim_id,
                InsuranceClaimItem.is_deleted.is_(False),
            )
            .all()
        )

    def recompute_billed(self, claim: InsuranceClaim) -> InsuranceClaim:
        rows = (
            self.db.query(
                func.coalesce(func.sum(InsuranceClaimItem.billed_amount), 0),
                func.coalesce(func.sum(InsuranceClaimItem.approved_amount), 0),
                func.coalesce(func.sum(InsuranceClaimItem.rejected_amount), 0),
            )
            .filter(
                InsuranceClaimItem.claim_id == claim.id,
                InsuranceClaimItem.is_deleted.is_(False),
            )
            .first()
        )
        if rows:
            billed, approved, rejected = rows
            claim.billed_amount = Decimal(billed or 0)
            claim.approved_amount = Decimal(approved or 0)
            claim.rejected_amount = Decimal(rejected or 0)
            self.db.add(claim)
            self.db.flush()
            self.db.refresh(claim)
        return claim


# ============================================================
# AUTHORIZATION
# ============================================================


class ClaimAuthorizationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_by_id(self, auth_id: int) -> ClaimAuthorization:
        a = (
            self.db.query(ClaimAuthorization)
            .filter(
                ClaimAuthorization.id == auth_id,
                ClaimAuthorization.is_deleted.is_(False),
            )
            .first()
        )
        if not a:
            raise NotFoundError(
                message="Authorization not found.", detail={"auth_id": auth_id}
            )
        return a

    def list_for_claim(self, claim_id: int) -> list[ClaimAuthorization]:
        return (
            self.db.query(ClaimAuthorization)
            .filter(
                ClaimAuthorization.claim_id == claim_id,
                ClaimAuthorization.is_deleted.is_(False),
            )
            .order_by(ClaimAuthorization.id.asc())
            .all()
        )

    def create(self, **kwargs) -> ClaimAuthorization:
        kwargs.setdefault("requested_at", datetime.now(timezone.utc))
        a = ClaimAuthorization(**kwargs)
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a

    def save(self, a: ClaimAuthorization) -> ClaimAuthorization:
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a


# ============================================================
# ADJUDICATION
# ============================================================


class ClaimAdjudicationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_by_id(self, adj_id: int) -> ClaimAdjudication:
        a = (
            self.db.query(ClaimAdjudication)
            .filter(
                ClaimAdjudication.id == adj_id,
                ClaimAdjudication.is_deleted.is_(False),
            )
            .first()
        )
        if not a:
            raise NotFoundError(
                message="Adjudication not found.", detail={"adjudication_id": adj_id}
            )
        return a

    def list_for_claim(self, claim_id: int) -> list[ClaimAdjudication]:
        return (
            self.db.query(ClaimAdjudication)
            .filter(
                ClaimAdjudication.claim_id == claim_id,
                ClaimAdjudication.is_deleted.is_(False),
            )
            .order_by(ClaimAdjudication.adjudicated_at.desc())
            .all()
        )

    def create(self, **kwargs) -> ClaimAdjudication:
        kwargs.setdefault("adjudicated_at", datetime.now(timezone.utc))
        a = ClaimAdjudication(**kwargs)
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a


# ============================================================
# PAYMENT
# ============================================================


class ClaimPaymentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_by_id(self, payment_id: int) -> ClaimPayment:
        p = (
            self.db.query(ClaimPayment)
            .filter(
                ClaimPayment.id == payment_id,
                ClaimPayment.is_deleted.is_(False),
            )
            .first()
        )
        if not p:
            raise NotFoundError(
                message="Claim payment not found.", detail={"payment_id": payment_id}
            )
        return p

    def get_by_reference(
        self, claim_id: int, payment_reference: str
    ) -> Optional[ClaimPayment]:
        return (
            self.db.query(ClaimPayment)
            .filter(
                ClaimPayment.claim_id == claim_id,
                ClaimPayment.payment_reference == payment_reference.strip(),
                ClaimPayment.is_deleted.is_(False),
            )
            .first()
        )

    def list_for_claim(self, claim_id: int) -> list[ClaimPayment]:
        return (
            self.db.query(ClaimPayment)
            .filter(
                ClaimPayment.claim_id == claim_id,
                ClaimPayment.is_deleted.is_(False),
            )
            .order_by(ClaimPayment.paid_at.desc())
            .all()
        )

    def create(self, **kwargs) -> ClaimPayment:
        kwargs.setdefault("paid_at", datetime.now(timezone.utc))
        # idempotency by (claim_id, payment_reference)
        existing = self.get_by_reference(
            kwargs["claim_id"], kwargs["payment_reference"]
        )
        if existing is not None:
            raise AlreadyExistsError(
                message="A payment with this reference already exists for this claim.",
                detail={
                    "claim_id": kwargs["claim_id"],
                    "payment_reference": kwargs["payment_reference"],
                },
            )
        p = ClaimPayment(**kwargs)
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p

    def total_paid(self, claim_id: int) -> Decimal:
        total = (
            self.db.query(func.coalesce(func.sum(ClaimPayment.amount), 0))
            .filter(
                ClaimPayment.claim_id == claim_id,
                ClaimPayment.is_deleted.is_(False),
            )
            .scalar()
        )
        return Decimal(total or 0)


# ============================================================
# APPEAL
# ============================================================


class ClaimAppealRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_by_id(self, appeal_id: int) -> ClaimAppeal:
        a = (
            self.db.query(ClaimAppeal)
            .filter(
                ClaimAppeal.id == appeal_id,
                ClaimAppeal.is_deleted.is_(False),
            )
            .first()
        )
        if not a:
            raise NotFoundError(
                message="Appeal not found.", detail={"appeal_id": appeal_id}
            )
        return a

    def list_for_claim(self, claim_id: int) -> list[ClaimAppeal]:
        return (
            self.db.query(ClaimAppeal)
            .filter(
                ClaimAppeal.claim_id == claim_id,
                ClaimAppeal.is_deleted.is_(False),
            )
            .order_by(ClaimAppeal.id.desc())
            .all()
        )

    def generate_appeal_no(self) -> str:
        return f"APL-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create(self, **kwargs) -> ClaimAppeal:
        kwargs.setdefault("appeal_no", self.generate_appeal_no())
        kwargs.setdefault("status", ClaimAppealStatus.DRAFT)
        a = ClaimAppeal(**kwargs)
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a

    def save(self, a: ClaimAppeal) -> ClaimAppeal:
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a
