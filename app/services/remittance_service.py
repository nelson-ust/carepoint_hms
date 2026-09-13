# app/services/remittance_service.py
from __future__ import annotations

"""
HMO receivables side of the insurance module:

* Payer ledger / statement — "how much does this HMO owe us right now",
  built from approved claims (debits), confirmed capitation (debits),
  claim/capitation receipts (credits) and disallowance write-offs (credits).
* Remittance advices — one bulk payment from an HMO allocated across many
  claims and/or capitation schedule lines, with fuzzy auto-matching.
* Disallowance write-offs — the approved-vs-billed gap (or later clawbacks)
  is written off explicitly, never silently.
* Patient-responsibility push — amounts an adjudication returns to the
  patient become collectible patient invoices.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import (
    CapitationScheduleStatus,
    InsuranceClaimStatus,
    InvoiceStatus,
    RemittanceAdviceStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    ClaimPayment,
    InsuranceClaim,
    InsuranceProvider,
    Invoice,
    InvoiceItem,
)
from app.models.finance_models import (
    CapitationScheduleLine,
    CapitationContract,
    ClaimWriteOff,
    RemittanceAdvice,
    RemittanceLine,
)
from app.services.system_accounts_service import audit, next_document_no


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


APPROVED_STATUSES = {InsuranceClaimStatus.APPROVED,
                     InsuranceClaimStatus.PARTIALLY_APPROVED,
                     InsuranceClaimStatus.PAID}


class RemittanceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Payer ledger / statement
    # ------------------------------------------------------------------

    def payer_statement(self, provider_id: int, *,
                        date_from: Optional[date] = None,
                        date_to: Optional[date] = None) -> dict:
        provider = (self.db.query(InsuranceProvider)
                    .filter(InsuranceProvider.id == provider_id).first())
        if provider is None:
            raise NotFoundError("Insurance provider not found.")

        rows: list[dict] = []

        claims = (self.db.query(InsuranceClaim)
                  .filter(InsuranceClaim.insurance_provider_id == provider_id,
                          InsuranceClaim.is_deleted.is_(False),
                          InsuranceClaim.status.in_(APPROVED_STATUSES)).all())
        for c in claims:
            when = (c.submitted_at.date() if c.submitted_at else
                    (c.service_date or c.date_created.date()))
            rows.append({"date": when, "type": "CLAIM_APPROVED",
                         "ref": c.claim_no, "debit": _d(c.approved_amount),
                         "credit": Decimal("0"),
                         "detail": f"Claim {c.claim_no} approved"})
            for p in (c.claim_payments or []):
                if p.is_deleted:
                    continue
                rows.append({"date": p.paid_at.date() if p.paid_at else when,
                             "type": "CLAIM_PAYMENT", "ref": p.payment_reference,
                             "debit": Decimal("0"), "credit": _d(p.amount),
                             "detail": f"Payment on claim {c.claim_no}"})
            for w in (self.db.query(ClaimWriteOff)
                      .filter(ClaimWriteOff.claim_id == c.id,
                              ClaimWriteOff.is_deleted.is_(False)).all()):
                rows.append({"date": w.written_off_at.date(), "type": "WRITE_OFF",
                             "ref": f"WO-{w.id}", "debit": Decimal("0"),
                             "credit": _d(w.amount),
                             "detail": f"Disallowance write-off on {c.claim_no}"})

        cap_lines = (self.db.query(CapitationScheduleLine)
                     .join(CapitationContract,
                           CapitationContract.id == CapitationScheduleLine.contract_id)
                     .filter(CapitationContract.insurance_provider_id == provider_id,
                             CapitationScheduleLine.is_deleted.is_(False),
                             CapitationScheduleLine.status.in_([
                                 CapitationScheduleStatus.CONFIRMED,
                                 CapitationScheduleStatus.PARTIALLY_PAID,
                                 CapitationScheduleStatus.PAID])).all())
        for l in cap_lines:
            when = (l.confirmed_at.date() if l.confirmed_at else l.date_created.date())
            rows.append({"date": when, "type": "CAPITATION_DUE",
                         "ref": f"CAP {l.period_code}",
                         "debit": _d(l.expected_amount), "credit": Decimal("0"),
                         "detail": f"Capitation {l.period_code} ({l.enrollee_count} enrollees)"})
            for p in (l.payments or []):
                if p.is_deleted:
                    continue
                rows.append({"date": p.paid_at, "type": "CAPITATION_PAYMENT",
                             "ref": p.reference or f"CAPPAY-{p.id}",
                             "debit": Decimal("0"), "credit": _d(p.amount),
                             "detail": f"Capitation receipt {l.period_code}"})

        rows.sort(key=lambda r: (r["date"], r["type"]))

        opening = Decimal("0")
        if date_from:
            opening = sum((r["debit"] - r["credit"] for r in rows if r["date"] < date_from),
                          Decimal("0"))
            rows = [r for r in rows if r["date"] >= date_from]
        if date_to:
            rows = [r for r in rows if r["date"] <= date_to]

        running = opening
        out_rows = []
        for r in rows:
            running += r["debit"] - r["credit"]
            out_rows.append({**r, "date": r["date"].isoformat(),
                             "debit": str(r["debit"]), "credit": str(r["credit"]),
                             "balance": str(running)})
        return {
            "provider_id": provider_id, "provider_name": provider.name,
            "opening_balance": str(opening),
            "closing_balance": str(running),
            "rows": out_rows,
        }

    def payer_balances(self) -> list[dict]:
        """One-line outstanding balance per payer (dashboard KPI)."""
        out = []
        providers = (self.db.query(InsuranceProvider)
                     .filter(InsuranceProvider.is_deleted.is_(False)).all())
        for p in providers:
            claim_out = _d(self.db.query(
                func.coalesce(func.sum(InsuranceClaim.approved_amount - InsuranceClaim.paid_amount), 0))
                .filter(InsuranceClaim.insurance_provider_id == p.id,
                        InsuranceClaim.is_deleted.is_(False),
                        InsuranceClaim.status.in_([InsuranceClaimStatus.APPROVED,
                                                   InsuranceClaimStatus.PARTIALLY_APPROVED]))
                .scalar() or 0)
            wo = _d(self.db.query(func.coalesce(func.sum(ClaimWriteOff.amount), 0))
                    .join(InsuranceClaim, InsuranceClaim.id == ClaimWriteOff.claim_id)
                    .filter(InsuranceClaim.insurance_provider_id == p.id,
                            InsuranceClaim.status.in_([InsuranceClaimStatus.APPROVED,
                                                       InsuranceClaimStatus.PARTIALLY_APPROVED]),
                            ClaimWriteOff.is_deleted.is_(False)).scalar() or 0)
            cap_out = Decimal("0")
            for l in (self.db.query(CapitationScheduleLine)
                      .join(CapitationContract,
                            CapitationContract.id == CapitationScheduleLine.contract_id)
                      .filter(CapitationContract.insurance_provider_id == p.id,
                              CapitationScheduleLine.is_deleted.is_(False),
                              CapitationScheduleLine.status.in_([
                                  CapitationScheduleStatus.CONFIRMED,
                                  CapitationScheduleStatus.PARTIALLY_PAID])).all()):
                cap_out += _d(l.expected_amount) - _d(l.received_amount)
            total = claim_out - wo + cap_out
            if total != 0 or claim_out != 0 or cap_out != 0:
                out.append({"provider_id": p.id, "provider_name": p.name,
                            "claims_outstanding": str(max(claim_out - wo, Decimal('0'))),
                            "capitation_outstanding": str(cap_out),
                            "total_outstanding": str(max(total, Decimal('0')))})
        out.sort(key=lambda r: Decimal(r["total_outstanding"]), reverse=True)
        return out

    # ------------------------------------------------------------------
    # Remittance advices
    # ------------------------------------------------------------------

    def _get_advice(self, advice_id: int) -> RemittanceAdvice:
        a = (self.db.query(RemittanceAdvice)
             .filter(RemittanceAdvice.id == advice_id,
                     RemittanceAdvice.is_deleted.is_(False)).first())
        if a is None:
            raise NotFoundError("Remittance advice not found.")
        return a

    def _advice_read(self, a: RemittanceAdvice) -> dict:
        return {
            "id": a.id, "insurance_provider_id": a.insurance_provider_id,
            "provider_name": a.insurance_provider.name if a.insurance_provider else None,
            "reference": a.reference, "received_at": a.received_at.isoformat(),
            "total_amount": str(_d(a.total_amount)),
            "allocated_amount": str(_d(a.allocated_amount)),
            "unallocated_amount": str(_d(a.total_amount) - _d(a.allocated_amount)),
            "bank_account_id": a.bank_account_id,
            "document_url": a.document_url,
            "status": a.status.value if hasattr(a.status, "value") else a.status,
            "notes": a.notes,
            "lines": [{
                "id": l.id, "claim_id": l.claim_id,
                "capitation_schedule_line_id": l.capitation_schedule_line_id,
                "amount": str(_d(l.amount)), "notes": l.notes,
            } for l in (a.lines or []) if not l.is_deleted],
        }

    def list_advices(self, *, provider_id: Optional[int] = None) -> list[dict]:
        q = (self.db.query(RemittanceAdvice)
             .filter(RemittanceAdvice.is_deleted.is_(False)))
        if provider_id:
            q = q.filter(RemittanceAdvice.insurance_provider_id == provider_id)
        return [self._advice_read(a) for a in q.order_by(RemittanceAdvice.id.desc()).all()]

    def create_advice(self, *, insurance_provider_id: int, total_amount,
                      received_at: date, reference: Optional[str] = None,
                      bank_account_id: Optional[int] = None,
                      document_url: Optional[str] = None,
                      notes: Optional[str] = None,
                      user_id: Optional[int] = None) -> dict:
        total = _d(total_amount)
        if total <= 0:
            raise BadRequestError("total_amount must be positive.")
        a = RemittanceAdvice(
            insurance_provider_id=insurance_provider_id,
            reference=reference or next_document_no(self.db, "REMITTANCE"),
            received_at=received_at, total_amount=total,
            bank_account_id=bank_account_id, document_url=document_url, notes=notes)
        self.db.add(a)
        self.db.flush()
        audit(self.db, action="REMITTANCE_CREATED", entity_type="remittance_advice",
              entity_id=a.id, user_id=user_id,
              summary=f"Remittance {a.reference} of {total} recorded")
        self.db.commit()
        return self._advice_read(a)

    def suggest_matches(self, advice_id: int) -> dict:
        """Fuzzy-match open approved claims and unpaid capitation lines for
        the remittance's provider, best-first, to seed the allocation UI."""
        a = self._get_advice(advice_id)
        unallocated = _d(a.total_amount) - _d(a.allocated_amount)
        claims = (self.db.query(InsuranceClaim)
                  .filter(InsuranceClaim.insurance_provider_id == a.insurance_provider_id,
                          InsuranceClaim.is_deleted.is_(False),
                          InsuranceClaim.status.in_([InsuranceClaimStatus.APPROVED,
                                                     InsuranceClaimStatus.PARTIALLY_APPROVED]))
                  .order_by(InsuranceClaim.submitted_at.asc().nullslast()).all())
        claim_rows = []
        for c in claims:
            outstanding = _d(c.approved_amount) - _d(c.paid_amount)
            if outstanding <= 0:
                continue
            claim_rows.append({
                "claim_id": c.id, "claim_no": c.claim_no,
                "patient_id": c.patient_id,
                "approved_amount": str(_d(c.approved_amount)),
                "outstanding": str(outstanding),
                "exact_amount_match": outstanding == unallocated,
            })
        cap_rows = []
        for l in (self.db.query(CapitationScheduleLine)
                  .join(CapitationContract,
                        CapitationContract.id == CapitationScheduleLine.contract_id)
                  .filter(CapitationContract.insurance_provider_id == a.insurance_provider_id,
                          CapitationScheduleLine.is_deleted.is_(False),
                          CapitationScheduleLine.status.in_([
                              CapitationScheduleStatus.CONFIRMED,
                              CapitationScheduleStatus.PARTIALLY_PAID])).all()):
            outstanding = _d(l.expected_amount) - _d(l.received_amount)
            if outstanding <= 0:
                continue
            cap_rows.append({"capitation_schedule_line_id": l.id,
                             "period_code": l.period_code,
                             "outstanding": str(outstanding),
                             "exact_amount_match": outstanding == unallocated})
        return {"advice": self._advice_read(a),
                "open_claims": claim_rows, "open_capitation": cap_rows}

    def allocate(self, advice_id: int, *, allocations: list[dict],
                 user_id: Optional[int] = None) -> dict:
        """Allocate parts of the remittance to claims and/or capitation lines.
        Each allocation: {claim_id | capitation_schedule_line_id, amount}."""
        from app.services.capitation_service import CapitationService
        a = self._get_advice(advice_id)
        if a.status == RemittanceAdviceStatus.CANCELLED:
            raise BadRequestError("Remittance advice is cancelled.")
        remaining = _d(a.total_amount) - _d(a.allocated_amount)
        applied = []
        for alloc in allocations:
            amount = _d(alloc.get("amount"))
            if amount <= 0:
                raise BadRequestError("Each allocation amount must be positive.")
            if amount > remaining:
                raise BadRequestError(
                    f"Allocation {amount} exceeds unallocated remainder {remaining}.")
            claim_id = alloc.get("claim_id")
            cap_line_id = alloc.get("capitation_schedule_line_id")
            if bool(claim_id) == bool(cap_line_id):
                raise BadRequestError(
                    "Each allocation needs exactly one of claim_id / capitation_schedule_line_id.")
            if claim_id:
                claim = (self.db.query(InsuranceClaim)
                         .filter(InsuranceClaim.id == claim_id,
                                 InsuranceClaim.is_deleted.is_(False)).first())
                if claim is None:
                    raise NotFoundError(f"Claim {claim_id} not found.")
                if claim.insurance_provider_id != a.insurance_provider_id:
                    raise BadRequestError(f"Claim {claim.claim_no} belongs to another payer.")
                if claim.status not in APPROVED_STATUSES:
                    raise BadRequestError(f"Claim {claim.claim_no} is not approved.")
                outstanding = _d(claim.approved_amount) - _d(claim.paid_amount)
                if amount > outstanding:
                    raise BadRequestError(
                        f"Allocation {amount} exceeds outstanding {outstanding} on {claim.claim_no}.")
                cp = ClaimPayment(
                    claim_id=claim.id,
                    payment_reference=f"{a.reference}/{claim.claim_no}",
                    amount=amount, currency="NGN",
                    paid_at=datetime.now(timezone.utc),
                    payment_method="BANK_TRANSFER",
                    notes=f"Remittance advice {a.reference}")
                self.db.add(cp)
                claim.paid_amount = _d(claim.paid_amount) + amount
                if claim.paid_amount >= _d(claim.approved_amount):
                    claim.status = InsuranceClaimStatus.PAID
                self.db.add(RemittanceLine(remittance_advice_id=a.id,
                                           claim_id=claim.id, amount=amount))
                applied.append({"claim_id": claim.id, "amount": str(amount)})
            else:
                CapitationService(self.db).record_payment(
                    line_id=cap_line_id, amount=amount,
                    paid_at=a.received_at, reference=a.reference,
                    bank_account_id=a.bank_account_id,
                    remittance_advice_id=a.id)
                self.db.add(RemittanceLine(remittance_advice_id=a.id,
                                           capitation_schedule_line_id=cap_line_id,
                                           amount=amount))
                applied.append({"capitation_schedule_line_id": cap_line_id,
                                "amount": str(amount)})
            remaining -= amount
            a.allocated_amount = _d(a.allocated_amount) + amount

        a.status = (RemittanceAdviceStatus.ALLOCATED
                    if _d(a.allocated_amount) >= _d(a.total_amount)
                    else RemittanceAdviceStatus.PARTIALLY_ALLOCATED)
        audit(self.db, action="REMITTANCE_ALLOCATED", entity_type="remittance_advice",
              entity_id=a.id, user_id=user_id,
              summary=f"Allocated {len(applied)} lines on {a.reference}",
              detail={"applied": applied})
        self.db.commit()
        return self._advice_read(a)

    # ------------------------------------------------------------------
    # Disallowance write-offs
    # ------------------------------------------------------------------

    def write_off_claim(self, *, claim_id: int, amount=None,
                        reason_code: Optional[str] = None,
                        reason_text: Optional[str] = None,
                        user_id: Optional[int] = None) -> dict:
        claim = (self.db.query(InsuranceClaim)
                 .filter(InsuranceClaim.id == claim_id,
                         InsuranceClaim.is_deleted.is_(False)).first())
        if claim is None:
            raise NotFoundError("Claim not found.")
        # The receivable only ever carries the APPROVED amount (revenue is
        # recognised at approved value; the billed-vs-approved gap is tracked
        # as rejected_amount and never enters the ledger). A write-off
        # therefore covers the UNCOLLECTIBLE part of the approved amount.
        already = _d(self.db.query(func.coalesce(func.sum(ClaimWriteOff.amount), 0))
                     .filter(ClaimWriteOff.claim_id == claim.id,
                             ClaimWriteOff.is_deleted.is_(False)).scalar() or 0)
        writable = _d(claim.approved_amount) - _d(claim.paid_amount) - already
        amount = _d(amount) if amount is not None else writable
        if amount <= 0:
            raise BadRequestError("Nothing to write off (amount must be positive).")
        if amount > writable:
            raise BadRequestError(
                f"Write-off {amount} exceeds the uncollected approved balance ({writable}).")
        w = ClaimWriteOff(claim_id=claim.id, amount=amount,
                          reason_code=reason_code, reason_text=reason_text,
                          approved_by_user_id=user_id,
                          written_off_at=datetime.now(timezone.utc))
        self.db.add(w)
        # Track the billed-vs-approved gap once, for rejection analytics.
        gap = _d(claim.billed_amount) - _d(claim.approved_amount)
        if gap > 0:
            claim.rejected_amount = max(_d(claim.rejected_amount), gap)
        if amount >= writable:
            claim.status = InsuranceClaimStatus.CLOSED
        self.db.flush()
        audit(self.db, action="CLAIM_WRITE_OFF", entity_type="insurance_claim",
              entity_id=claim.id, user_id=user_id,
              summary=f"Wrote off {amount} on claim {claim.claim_no}",
              detail={"reason_code": reason_code})
        self.db.commit()
        return {"id": w.id, "claim_id": claim.id, "amount": str(amount),
                "reason_code": reason_code}

    # ------------------------------------------------------------------
    # Patient responsibility -> collectible patient invoice
    # ------------------------------------------------------------------

    def push_patient_responsibility(self, *, claim_id: int,
                                    user_id: Optional[int] = None) -> dict:
        """Create (once) a patient invoice for the amount the adjudication
        shifted to the patient, so the front desk can collect it."""
        claim = (self.db.query(InsuranceClaim)
                 .filter(InsuranceClaim.id == claim_id,
                         InsuranceClaim.is_deleted.is_(False)).first())
        if claim is None:
            raise NotFoundError("Claim not found.")
        amount = _d(claim.patient_responsibility_amount)
        if amount <= 0:
            raise BadRequestError("Claim has no patient-responsibility amount.")
        marker = f"CLAIM_PR:{claim.id}"
        existing = (self.db.query(InvoiceItem)
                    .filter(InvoiceItem.source_reference == marker,
                            InvoiceItem.is_deleted.is_(False)).first())
        if existing is not None:
            return {"invoice_id": existing.invoice_id, "already_existed": True}
        now = datetime.now(timezone.utc)
        inv = Invoice(
            patient_id=claim.patient_id, visit_id=claim.visit_id,
            invoice_no=f"INV-PR-{claim.claim_no}",
            status=InvoiceStatus.ISSUED, invoice_date=now,
            subtotal_amount=amount, discount_amount=Decimal("0"),
            tax_amount=Decimal("0"), total_amount=amount,
            amount_paid=Decimal("0"), balance_due=amount,
            note=f"Patient responsibility per adjudication of claim {claim.claim_no}")
        self.db.add(inv)
        self.db.flush()
        self.db.add(InvoiceItem(
            invoice_id=inv.id, service_name="Insurance patient responsibility",
            quantity=Decimal("1"), unit_price=amount,
            discount_amount=Decimal("0"), line_total=amount,
            source_reference=marker))
        audit(self.db, action="PATIENT_RESPONSIBILITY_INVOICED",
              entity_type="insurance_claim", entity_id=claim.id, user_id=user_id,
              summary=f"Invoice {inv.invoice_no} for {amount}")
        self.db.commit()
        return {"invoice_id": inv.id, "invoice_no": inv.invoice_no,
                "amount": str(amount), "already_existed": False}
