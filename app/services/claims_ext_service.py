# app/services/claims_ext_service.py
from __future__ import annotations

"""
Extensions to the existing claims lifecycle (kept out of
``insurance_claim_service.py`` so the stable core stays untouched):

* Rejection-reason lookup management (structured denial analytics).
* Claim resubmission (rejected claim -> corrected child claim).
* Monthly batch generation for a provider + XLSX export of a batch.
* Claim aging report (0-30/31-60/61-90/90+ by approved-but-unpaid).
* Rejection analysis & days-to-settlement metrics for the dashboard.
"""

import io
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import ClaimBatchStatus, InsuranceClaimStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    ClaimBatch,
    InsuranceClaim,
    InsuranceClaimItem,
    InsuranceProvider,
    Patient,
)
from app.models.finance_models import ClaimRejectionReason
from app.services.system_accounts_service import audit, next_document_no


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


#: server-side legal transition map (state-machine hardening)
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PENDING_AUTH", "AUTHORIZED", "SUBMITTED", "CLOSED"},
    "PENDING_AUTH": {"AUTHORIZED", "DRAFT", "CLOSED"},
    "AUTHORIZED": {"SUBMITTED", "CLOSED"},
    "SUBMITTED": {"UNDER_REVIEW", "APPROVED", "PARTIALLY_APPROVED", "REJECTED", "DRAFT"},
    "UNDER_REVIEW": {"APPROVED", "PARTIALLY_APPROVED", "REJECTED"},
    "APPROVED": {"PAID", "APPEALED", "CLOSED"},
    "PARTIALLY_APPROVED": {"PAID", "APPEALED", "CLOSED"},
    "REJECTED": {"APPEALED", "CLOSED"},
    "PAID": {"CLOSED"},
    "APPEALED": {"APPROVED", "PARTIALLY_APPROVED", "REJECTED", "CLOSED"},
    "CLOSED": set(),
}


def assert_transition(current, target) -> None:
    cur = current.value if hasattr(current, "value") else str(current)
    tgt = target.value if hasattr(target, "value") else str(target)
    if tgt not in ALLOWED_TRANSITIONS.get(cur, set()):
        raise BadRequestError(
            f"Illegal claim status transition {cur} -> {tgt}.",
        )


class ClaimsExtService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------- rejection reasons ----------------

    def list_rejection_reasons(self) -> list[dict]:
        rows = (self.db.query(ClaimRejectionReason)
                .filter(ClaimRejectionReason.is_deleted.is_(False))
                .order_by(ClaimRejectionReason.code).all())
        return [{"id": r.id, "code": r.code, "description": r.description,
                 "is_active": r.is_active} for r in rows]

    def upsert_rejection_reason(self, *, reason_id: Optional[int] = None,
                                code: Optional[str] = None,
                                description: Optional[str] = None,
                                is_active: Optional[bool] = None) -> dict:
        if reason_id:
            r = (self.db.query(ClaimRejectionReason)
                 .filter(ClaimRejectionReason.id == reason_id,
                         ClaimRejectionReason.is_deleted.is_(False)).first())
            if r is None:
                raise NotFoundError("Rejection reason not found.")
        else:
            if not code or not description:
                raise BadRequestError("code and description are required.")
            r = ClaimRejectionReason(code=code.upper(), description=description)
            self.db.add(r)
        if code:
            r.code = code.upper()
        if description:
            r.description = description
        if is_active is not None:
            r.is_active = is_active
        self.db.flush()
        self.db.commit()
        return {"id": r.id, "code": r.code, "description": r.description,
                "is_active": r.is_active}

    # ---------------- resubmission ----------------

    def resubmit_claim(self, claim_id: int, *, user_id: Optional[int] = None) -> dict:
        """Spawn a corrected DRAFT child claim from a REJECTED claim."""
        parent = (self.db.query(InsuranceClaim)
                  .filter(InsuranceClaim.id == claim_id,
                          InsuranceClaim.is_deleted.is_(False)).first())
        if parent is None:
            raise NotFoundError("Claim not found.")
        if parent.status != InsuranceClaimStatus.REJECTED:
            raise BadRequestError("Only REJECTED claims can be resubmitted.")
        child = InsuranceClaim(
            claim_no=f"{parent.claim_no}-R{(parent.id % 1000)}",
            patient_id=parent.patient_id,
            patient_insurance_id=parent.patient_insurance_id,
            insurance_provider_id=parent.insurance_provider_id,
            visit_id=parent.visit_id, invoice_id=parent.invoice_id,
            facility_id=parent.facility_id,
            status=InsuranceClaimStatus.DRAFT,
            service_date=parent.service_date,
            diagnosis_codes=parent.diagnosis_codes,
            primary_diagnosis_text=parent.primary_diagnosis_text,
            billed_amount=parent.billed_amount,
            resubmission_of_id=parent.id,
            notes=f"Resubmission of {parent.claim_no}")
        self.db.add(child)
        self.db.flush()
        for it in (parent.items or []):
            if it.is_deleted:
                continue
            self.db.add(InsuranceClaimItem(
                claim_id=child.id, invoice_item_id=it.invoice_item_id,
                billable_service_id=it.billable_service_id,
                service_date=it.service_date, procedure_code=it.procedure_code,
                diagnosis_code=it.diagnosis_code, description=it.description,
                quantity=it.quantity, unit_price=it.unit_price,
                billed_amount=it.billed_amount))
        parent.status = InsuranceClaimStatus.CLOSED
        audit(self.db, action="CLAIM_RESUBMITTED", entity_type="insurance_claim",
              entity_id=parent.id, user_id=user_id,
              summary=f"{parent.claim_no} -> {child.claim_no}")
        self.db.commit()
        return {"parent_claim_id": parent.id, "new_claim_id": child.id,
                "new_claim_no": child.claim_no}

    # ---------------- monthly batch generation ----------------

    def generate_monthly_batch(self, *, provider_id: int, period_code: str,
                               user_id: Optional[int] = None) -> dict:
        """Sweep every un-batched DRAFT claim for the provider in YYYY-MM
        into a new DRAFT ClaimBatch ready for submission."""
        provider = (self.db.query(InsuranceProvider)
                    .filter(InsuranceProvider.id == provider_id).first())
        if provider is None:
            raise NotFoundError("Insurance provider not found.")
        try:
            year, month = (int(x) for x in period_code.split("-"))
            period_start = date(year, month, 1)
            period_end = (date(year + 1, 1, 1) if month == 12
                          else date(year, month + 1, 1))
        except (ValueError, AttributeError):
            raise BadRequestError("period_code must be YYYY-MM.")

        claims = (self.db.query(InsuranceClaim)
                  .filter(InsuranceClaim.insurance_provider_id == provider_id,
                          InsuranceClaim.is_deleted.is_(False),
                          InsuranceClaim.batch_id.is_(None),
                          InsuranceClaim.status == InsuranceClaimStatus.DRAFT)
                  .all())
        claims = [c for c in claims
                  if (c.service_date or c.date_created.date()) >= period_start
                  and (c.service_date or c.date_created.date()) < period_end]
        if not claims:
            raise BadRequestError(f"No un-batched draft claims for {period_code}.")

        batch = ClaimBatch(
            batch_no=f"{next_document_no(self.db, 'CLAIM_BATCH')}-{period_code}",
            insurance_provider_id=provider_id,
            period_start=period_start,
            period_end=period_end,
            status=ClaimBatchStatus.DRAFT,
            total_claims=len(claims),
            total_billed_amount=sum((_d(c.billed_amount) for c in claims), Decimal("0")))
        self.db.add(batch)
        self.db.flush()
        for c in claims:
            c.batch_id = batch.id
        audit(self.db, action="CLAIM_BATCH_GENERATED", entity_type="claim_batch",
              entity_id=batch.id, user_id=user_id,
              summary=f"{len(claims)} claims batched for {provider.name} {period_code}")
        self.db.commit()
        return {"batch_id": batch.id, "batch_no": batch.batch_no,
                "claims": len(claims),
                "total_billed_amount": str(_d(batch.total_billed_amount))}

    def export_batch_xlsx(self, batch_id: int) -> tuple[str, bytes]:
        """The submission workbook most Nigerian HMOs accept."""
        from openpyxl import Workbook
        batch = (self.db.query(ClaimBatch)
                 .filter(ClaimBatch.id == batch_id,
                         ClaimBatch.is_deleted.is_(False)).first())
        if batch is None:
            raise NotFoundError("Claim batch not found.")
        wb = Workbook()
        ws = wb.active
        ws.title = "Claims"
        ws.append(["Batch", batch.batch_no, "Provider",
                   batch.insurance_provider.name if batch.insurance_provider else ""])
        ws.append([])
        ws.append(["Claim No", "Patient", "Policy No", "Service Date",
                   "Diagnosis", "Item", "Code", "Qty", "Unit Price", "Amount"])
        for c in (batch.claims or []):
            if c.is_deleted:
                continue
            patient = self.db.query(Patient).filter(Patient.id == c.patient_id).first()
            pname = f"{patient.first_name} {patient.last_name}" if patient else str(c.patient_id)
            policy = c.patient_insurance.policy_number if c.patient_insurance else ""
            items = [i for i in (c.items or []) if not i.is_deleted]
            if not items:
                ws.append([c.claim_no, pname, policy,
                           c.service_date.isoformat() if c.service_date else "",
                           c.primary_diagnosis_text or "", "", "", "", "",
                           float(_d(c.billed_amount))])
            for i in items:
                ws.append([c.claim_no, pname, policy,
                           i.service_date.isoformat() if i.service_date else "",
                           i.diagnosis_code or (c.primary_diagnosis_text or ""),
                           i.description or "", i.procedure_code or "",
                           float(_d(i.quantity)), float(_d(i.unit_price)),
                           float(_d(i.billed_amount) or (_d(i.unit_price) * _d(i.quantity)))])
        ws.append([])
        ws.append(["", "", "", "", "", "", "", "", "TOTAL",
                   float(_d(batch.total_billed_amount))])
        buf = io.BytesIO()
        wb.save(buf)
        return f"claim_batch_{batch.batch_no}.xlsx", buf.getvalue()

    # ---------------- aging & analytics ----------------

    def claim_aging(self, *, provider_id: Optional[int] = None,
                    as_of: Optional[date] = None) -> dict:
        as_of = as_of or date.today()
        q = (self.db.query(InsuranceClaim)
             .filter(InsuranceClaim.is_deleted.is_(False),
                     InsuranceClaim.status.in_([InsuranceClaimStatus.APPROVED,
                                                InsuranceClaimStatus.PARTIALLY_APPROVED,
                                                InsuranceClaimStatus.SUBMITTED,
                                                InsuranceClaimStatus.UNDER_REVIEW])))
        if provider_id:
            q = q.filter(InsuranceClaim.insurance_provider_id == provider_id)
        buckets = {"0_30": Decimal("0"), "31_60": Decimal("0"),
                   "61_90": Decimal("0"), "over_90": Decimal("0")}
        per_provider: dict[int, dict] = {}
        for c in q.all():
            base = (c.submitted_at.date() if c.submitted_at
                    else (c.service_date or c.date_created.date()))
            days = (as_of - base).days
            outstanding = (_d(c.approved_amount) - _d(c.paid_amount)
                           if c.status in (InsuranceClaimStatus.APPROVED,
                                           InsuranceClaimStatus.PARTIALLY_APPROVED)
                           else _d(c.billed_amount))
            if outstanding <= 0:
                continue
            key = ("0_30" if days <= 30 else "31_60" if days <= 60
                   else "61_90" if days <= 90 else "over_90")
            buckets[key] += outstanding
            slot = per_provider.setdefault(c.insurance_provider_id, {
                "provider_id": c.insurance_provider_id,
                "provider_name": c.insurance_provider.name if c.insurance_provider else None,
                "0_30": Decimal("0"), "31_60": Decimal("0"),
                "61_90": Decimal("0"), "over_90": Decimal("0"),
                "total": Decimal("0")})
            slot[key] += outstanding
            slot["total"] += outstanding
        rows = sorted(per_provider.values(), key=lambda r: r["total"], reverse=True)
        return {"as_of": as_of.isoformat(),
                "buckets": {k: str(v) for k, v in buckets.items()},
                "total": str(sum(buckets.values(), Decimal("0"))),
                "providers": [{**r, **{k: str(r[k]) for k in
                                       ("0_30", "31_60", "61_90", "over_90", "total")}}
                              for r in rows]}

    def rejection_analysis(self, *, provider_id: Optional[int] = None,
                           date_from: Optional[date] = None,
                           date_to: Optional[date] = None) -> dict:
        from app.models.all_models import ClaimAdjudication
        q = (self.db.query(ClaimAdjudication)
             .join(InsuranceClaim, InsuranceClaim.id == ClaimAdjudication.claim_id)
             .filter(ClaimAdjudication.is_deleted.is_(False)))
        if provider_id:
            q = q.filter(InsuranceClaim.insurance_provider_id == provider_id)
        if date_from:
            q = q.filter(ClaimAdjudication.adjudicated_at >= datetime(
                date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
        if date_to:
            q = q.filter(ClaimAdjudication.adjudicated_at <= datetime(
                date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc))
        total = rejected_value = Decimal("0")
        reason_counter: dict[str, dict] = {}
        n = rejected_n = 0
        for adj in q.all():
            n += 1
            total += _d(adj.approved_amount) + _d(adj.rejected_amount)
            if _d(adj.rejected_amount) > 0:
                rejected_n += 1
                rejected_value += _d(adj.rejected_amount)
                for code in ((adj.rejection_codes or {}).get("codes")
                             or ([adj.rejection_codes] if isinstance(adj.rejection_codes, str) else [])
                             or ["UNSPECIFIED"]):
                    code = str(code)
                    slot = reason_counter.setdefault(code, {"code": code, "count": 0,
                                                            "value": Decimal("0")})
                    slot["count"] += 1
                    slot["value"] += _d(adj.rejected_amount)
        top = sorted(reason_counter.values(), key=lambda r: r["value"], reverse=True)[:10]
        return {
            "adjudications": n,
            "with_rejections": rejected_n,
            "rejection_rate_percent": str(Decimal(rejected_n * 100) / n) if n else "0",
            "rejected_value": str(rejected_value),
            "top_reasons": [{**r, "value": str(r["value"])} for r in top],
        }

    def settlement_metrics(self, *, provider_id: Optional[int] = None) -> dict:
        """Average days from submission to full payment for PAID claims."""
        q = (self.db.query(InsuranceClaim)
             .filter(InsuranceClaim.is_deleted.is_(False),
                     InsuranceClaim.status == InsuranceClaimStatus.PAID,
                     InsuranceClaim.submitted_at.isnot(None)))
        if provider_id:
            q = q.filter(InsuranceClaim.insurance_provider_id == provider_id)
        durations = []
        for c in q.all():
            last_pay = max((p.paid_at for p in (c.claim_payments or [])
                            if not p.is_deleted and p.paid_at), default=None)
            if last_pay is not None:
                durations.append((last_pay - c.submitted_at).days)
        return {"paid_claims": len(durations),
                "avg_days_to_settlement": (sum(durations) / len(durations)) if durations else None,
                "max_days": max(durations) if durations else None}
