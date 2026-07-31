"""
Tax service.

Owns:

* CRUD for :class:`TaxType`, :class:`TaxRate`, :class:`TaxRule`,
  :class:`TaxExemption` — with an audit trail in :class:`TaxAuditLog`.
* Tax computation: given an Invoice + its items, decide which TaxTypes
  apply (consulting active rules and exemptions), look up the
  effective-dated rate, and emit immutable :class:`InvoiceTaxLine`
  snapshots that survive future rate changes.
* Withholding tax records: capture WHT deducted on payments to
  vendors / contractors / other applicable beneficiaries.

Tax rate immutability is enforced by snapshotting the rate value and
type code/name at the moment of issuance: historical invoice taxes are
never recomputed when an admin edits a TaxRate later.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.enums import (
    TaxApplicability,
    TaxExemptionScope,
    TaxKind,
    TaxPricingMode,
    TaxScope,
    WithholdingTaxStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    Invoice,
    InvoiceItem,
    InvoiceTaxLine,
    TaxAuditLog,
    TaxExemption,
    TaxRate,
    TaxRule,
    TaxType,
    WithholdingTaxRecord,
)


logger = logging.getLogger(__name__)


def _q(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places))


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TaxService:
    def __init__(self, db: Session, *, actor_user_id: Optional[int] = None) -> None:
        self.db = db
        self.actor_user_id = actor_user_id

    # ------------------------------------------------------------------
    # TAX TYPE CRUD
    # ------------------------------------------------------------------

    def list_tax_types(self, *, only_active: bool = False) -> list[TaxType]:
        q = self.db.query(TaxType).filter(TaxType.is_deleted.is_(False))
        if only_active:
            q = q.filter(TaxType.is_active.is_(True))
        return q.order_by(TaxType.code.asc()).all()

    def create_tax_type(
        self,
        *,
        code: str,
        name: str,
        kind: TaxKind = TaxKind.OTHER,
        description: Optional[str] = None,
        country_code: Optional[str] = None,
        is_withholding: bool = False,
        is_active: bool = True,
    ) -> TaxType:
        norm = code.strip().upper()
        if (
            self.db.query(TaxType)
            .filter(TaxType.code == norm, TaxType.is_deleted.is_(False))
            .first()
        ):
            raise BadRequestError(message=f"Tax type code '{norm}' already exists.")
        rec = TaxType(
            code=norm,
            name=name.strip(),
            kind=kind,
            description=description,
            country_code=country_code,
            is_withholding=bool(is_withholding) or kind == TaxKind.WHT,
            is_active=is_active,
        )
        self.db.add(rec)
        self.db.flush()
        self._audit("tax_type", rec.id, "CREATE", after=self._snap(rec))
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def update_tax_type(self, tax_type_id: int, **fields) -> TaxType:
        rec = self._get_tax_type(tax_type_id)
        before = self._snap(rec)
        for k, v in fields.items():
            if v is None:
                continue
            if k == "code":
                v = v.strip().upper()
            setattr(rec, k, v)
        self._audit("tax_type", rec.id, "UPDATE", before=before, after=self._snap(rec))
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def delete_tax_type(self, tax_type_id: int) -> None:
        rec = self._get_tax_type(tax_type_id)
        # Guard: a type still referenced by rules cannot be removed, otherwise
        # those rules would point at a missing type. Ask the caller to clean up
        # the dependent rules first.
        dependent_rules = (
            self.db.query(TaxRule)
            .filter(TaxRule.tax_type_id == tax_type_id, TaxRule.is_deleted.is_(False))
            .count()
        )
        if dependent_rules:
            raise BadRequestError(
                message=(
                    "This tax type still has tax rules attached. Delete or "
                    "reassign those rules before removing the type."
                )
            )
        before = self._snap(rec)
        rec.is_deleted = True
        rec.is_active = False
        self._audit("tax_type", rec.id, "DELETE", before=before, after=self._snap(rec))
        self.db.commit()

        # ------------------------------------------------------------------
    # TAX RATE CRUD
    # ------------------------------------------------------------------

    def add_rate(
        self,
        *,
        tax_type_id: int,
        rate_percent: Decimal | float,
        effective_from: date,
        effective_to: Optional[date] = None,
        note: Optional[str] = None,
    ) -> TaxRate:
        self._get_tax_type(tax_type_id)
        rec = TaxRate(
            tax_type_id=tax_type_id,
            rate_percent=Decimal(str(rate_percent)),
            effective_from=effective_from,
            effective_to=effective_to,
            note=note,
        )
        self.db.add(rec)
        self.db.flush()
        self._audit("tax_rate", rec.id, "CREATE", after=self._snap(rec))
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def get_active_rate(self, tax_type_id: int, *, on_date: date) -> Optional[TaxRate]:
        return (
            self.db.query(TaxRate)
            .filter(
                TaxRate.tax_type_id == tax_type_id,
                TaxRate.effective_from <= on_date,
                (TaxRate.effective_to.is_(None)) | (TaxRate.effective_to >= on_date),
                TaxRate.is_deleted.is_(False),
            )
            .order_by(TaxRate.effective_from.desc())
            .first()
        )

    # ------------------------------------------------------------------
    # TAX RULE / EXEMPTION CRUD
    # ------------------------------------------------------------------

    def add_rule(
        self,
        *,
        tax_type_id: int,
        name: str,
        scope: TaxScope = TaxScope.TENANT,
        applicability: TaxApplicability = TaxApplicability.ALL,
        match_values: Optional[list[str]] = None,
        pricing_mode: TaxPricingMode = TaxPricingMode.EXCLUSIVE,
        priority: int = 100,
        facility_id: Optional[int] = None,
        is_active: bool = True,
    ) -> TaxRule:
        self._get_tax_type(tax_type_id)
        rec = TaxRule(
            tax_type_id=tax_type_id,
            name=name,
            scope=scope,
            facility_id=facility_id,
            applicability=applicability,
            match_values=match_values,
            pricing_mode=pricing_mode,
            priority=priority,
            is_active=is_active,
        )
        self.db.add(rec)
        self.db.flush()
        self._audit("tax_rule", rec.id, "CREATE", after=self._snap(rec))
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def update_rule(self, rule_id: int, **fields) -> TaxRule:
        rec = (
            self.db.query(TaxRule)
            .filter(TaxRule.id == rule_id, TaxRule.is_deleted.is_(False))
            .first()
        )
        if rec is None:
            raise BadRequestError(message="Tax rule not found.")
        before = self._snap(rec)
        # Validate a re-pointed tax type before applying anything.
        if fields.get("tax_type_id") is not None:
            self._get_tax_type(fields["tax_type_id"])
        allowed = {
            "tax_type_id", "name", "scope", "applicability", "match_values",
            "pricing_mode", "priority", "facility_id", "is_active",
        }
        for k, v in fields.items():
            if k not in allowed:
                continue
            setattr(rec, k, v)
        self._audit("tax_rule", rec.id, "UPDATE", before=before, after=self._snap(rec))
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def delete_rule(self, rule_id: int) -> None:
        rec = (
            self.db.query(TaxRule)
            .filter(TaxRule.id == rule_id, TaxRule.is_deleted.is_(False))
            .first()
        )
        if rec is None:
            raise BadRequestError(message="Tax rule not found.")
        before = self._snap(rec)
        rec.is_deleted = True
        rec.is_active = False
        self._audit("tax_rule", rec.id, "DELETE", before=before, after=self._snap(rec))
        self.db.commit()

    def add_exemption(
        self,
        *,
        tax_type_id: int,
        scope: TaxExemptionScope,
        target_id: int,
        reason: Optional[str] = None,
        starts_on: Optional[date] = None,
        ends_on: Optional[date] = None,
        supporting_document_url: Optional[str] = None,
    ) -> TaxExemption:
        self._get_tax_type(tax_type_id)
        rec = TaxExemption(
            tax_type_id=tax_type_id,
            scope=scope,
            target_id=target_id,
            reason=reason,
            starts_on=starts_on,
            ends_on=ends_on,
            supporting_document_url=supporting_document_url,
            is_active=True,
        )
        self.db.add(rec)
        self.db.flush()
        self._audit("tax_exemption", rec.id, "CREATE", after=self._snap(rec))
        self.db.commit()
        self.db.refresh(rec)
        return rec

    # ------------------------------------------------------------------
    # COMPUTATION
    # ------------------------------------------------------------------

    def compute_invoice_tax(
        self,
        invoice: Invoice,
        *,
        items: Optional[Iterable[InvoiceItem]] = None,
        commit: bool = True,
    ) -> list[InvoiceTaxLine]:
        """
        Compute and persist :class:`InvoiceTaxLine` rows for an Invoice.

        Idempotent: re-running on an invoice that already has tax lines
        is a no-op (the snapshots survive rate changes; revising the
        invoice should be done by issuing a credit note).
        """
        existing = (
            self.db.query(InvoiceTaxLine)
            .filter(InvoiceTaxLine.invoice_id == invoice.id, InvoiceTaxLine.is_deleted.is_(False))
            .all()
        )
        if existing:
            return existing

        items = list(items or invoice.items or [])
        if not items:
            return []

        on_date = (invoice.invoice_date or datetime.now(timezone.utc)).date()

        # Pull active types/rules once.
        types = self.list_tax_types(only_active=True)
        rules = (
            self.db.query(TaxRule)
            .filter(TaxRule.is_active.is_(True), TaxRule.is_deleted.is_(False))
            .order_by(TaxRule.priority.asc())
            .all()
        )
        exemptions = (
            self.db.query(TaxExemption)
            .filter(TaxExemption.is_active.is_(True), TaxExemption.is_deleted.is_(False))
            .all()
        )

        out: list[InvoiceTaxLine] = []
        for item in items:
            base = self._line_base(item)
            for tt in types:
                if tt.is_withholding:
                    # WHT is captured separately on payments, not invoice issuance.
                    continue
                rate = self.get_active_rate(tt.id, on_date=on_date)
                if rate is None:
                    continue

                rule = self._find_matching_rule(tt, rules, item, invoice)
                if rule is None:
                    continue

                # Exemptions trump rules.
                exempt = self._is_line_exempt(tt, item, invoice, exemptions, on_date=on_date)

                pricing_mode = rule.pricing_mode
                rate_percent = Decimal(rate.rate_percent)
                if exempt:
                    line = InvoiceTaxLine(
                        invoice_id=invoice.id,
                        invoice_item_id=item.id,
                        tax_type_id=tt.id,
                        tax_type_code_snapshot=tt.code,
                        tax_type_name_snapshot=tt.name,
                        rate_percent_snapshot=rate_percent,
                        taxable_base=_q(base),
                        tax_amount=Decimal("0.00"),
                        pricing_mode=pricing_mode,
                        is_exempt=True,
                        exemption_reason="Exempt",
                    )
                    self.db.add(line)
                    out.append(line)
                    continue

                if pricing_mode == TaxPricingMode.INCLUSIVE:
                    # Tax already inside base: tax = base - base / (1 + rate)
                    divisor = Decimal("1") + (rate_percent / Decimal("100"))
                    tax = base - (base / divisor) if divisor != 0 else Decimal("0")
                    taxable_base = base - tax
                else:
                    taxable_base = base
                    tax = (base * rate_percent / Decimal("100"))

                line = InvoiceTaxLine(
                    invoice_id=invoice.id,
                    invoice_item_id=item.id,
                    tax_type_id=tt.id,
                    tax_type_code_snapshot=tt.code,
                    tax_type_name_snapshot=tt.name,
                    rate_percent_snapshot=rate_percent,
                    taxable_base=_q(taxable_base),
                    tax_amount=_q(tax),
                    pricing_mode=pricing_mode,
                    is_exempt=False,
                )
                self.db.add(line)
                out.append(line)

        # Roll the totals back onto the Invoice.
        total_tax = sum((Decimal(l.tax_amount) for l in out), Decimal("0"))
        invoice.tax_amount = _q(total_tax)
        invoice.total_amount = _q(
            (invoice.subtotal_amount or Decimal("0"))
            - (invoice.discount_amount or Decimal("0"))
            + invoice.tax_amount
        )
        invoice.balance_due = _q(
            invoice.total_amount - (invoice.amount_paid or Decimal("0"))
        )

        if commit:
            self.db.commit()
        return out

    # ------------------------------------------------------------------
    # WITHHOLDING TAX
    # ------------------------------------------------------------------

    def record_withholding(
        self,
        *,
        tax_type_id: int,
        payee_name: str,
        gross_amount: Decimal | float,
        rate_percent: Optional[Decimal | float] = None,
        related_invoice_id: Optional[int] = None,
        related_payment_id: Optional[int] = None,
        payee_tax_id: Optional[str] = None,
        payee_kind: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> WithholdingTaxRecord:
        tt = self._get_tax_type(tax_type_id)
        if not tt.is_withholding:
            raise BadRequestError(message="Selected tax type is not a withholding tax.")

        if rate_percent is None:
            rate = self.get_active_rate(tt.id, on_date=date.today())
            if rate is None:
                raise BadRequestError(message="No active rate found for tax type.")
            rate_percent = rate.rate_percent

        gross = Decimal(str(gross_amount))
        rate_dec = Decimal(str(rate_percent))
        wht = _q(gross * rate_dec / Decimal("100"))

        rec = WithholdingTaxRecord(
            tax_type_id=tt.id,
            payee_name=payee_name,
            payee_tax_id=payee_tax_id,
            payee_kind=payee_kind,
            related_invoice_id=related_invoice_id,
            related_payment_id=related_payment_id,
            gross_amount=_q(gross),
            rate_percent_snapshot=rate_dec,
            wht_amount=wht,
            status=WithholdingTaxStatus.DEDUCTED,
            deducted_at=datetime.now(timezone.utc),
            notes=notes,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def mark_wht_remitted(
        self,
        record_id: int,
        *,
        certificate_no: Optional[str] = None,
        certificate_url: Optional[str] = None,
    ) -> WithholdingTaxRecord:
        rec = self.db.query(WithholdingTaxRecord).filter(WithholdingTaxRecord.id == record_id).first()
        if rec is None:
            raise NotFoundError(message="WHT record not found.")
        rec.status = WithholdingTaxStatus.REMITTED
        rec.remitted_at = datetime.now(timezone.utc)
        if certificate_no:
            rec.certificate_no = certificate_no
            rec.status = WithholdingTaxStatus.CERTIFICATE_ISSUED
        if certificate_url:
            rec.certificate_url = certificate_url
        self.db.commit()
        self.db.refresh(rec)
        return rec

    # ------------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------------

    def _get_tax_type(self, tax_type_id: int) -> TaxType:
        rec = (
            self.db.query(TaxType)
            .filter(TaxType.id == tax_type_id, TaxType.is_deleted.is_(False))
            .first()
        )
        if rec is None:
            raise NotFoundError(message="Tax type not found.")
        return rec

    @staticmethod
    def _line_base(item: InvoiceItem) -> Decimal:
        # Prefer line subtotal if we have it; otherwise compute from qty * unit.
        for attr in ("net_amount", "subtotal_amount", "amount", "total_amount"):
            v = getattr(item, attr, None)
            if v is not None:
                return Decimal(v)
        qty = Decimal(getattr(item, "quantity", 1) or 1)
        unit = Decimal(getattr(item, "unit_price", 0) or 0)
        return qty * unit

    def _find_matching_rule(
        self,
        tt: TaxType,
        rules: list[TaxRule],
        item: InvoiceItem,
        invoice: Invoice,
    ) -> Optional[TaxRule]:
        candidate: Optional[TaxRule] = None
        for r in rules:
            if r.tax_type_id != tt.id:
                continue
            if r.scope == TaxScope.FACILITY and r.facility_id and r.facility_id != invoice.facility_id:
                continue
            if r.applicability == TaxApplicability.ALL:
                if candidate is None or r.priority < candidate.priority:
                    candidate = r
                continue
            if r.applicability == TaxApplicability.SERVICE_TYPE and r.match_values:
                if getattr(item, "service_type", None) in r.match_values:
                    if candidate is None or r.priority < candidate.priority:
                        candidate = r
                    continue
            if r.applicability == TaxApplicability.ITEM_CATEGORY and r.match_values:
                if getattr(item, "item_category", None) in r.match_values:
                    if candidate is None or r.priority < candidate.priority:
                        candidate = r
                    continue
            if r.applicability == TaxApplicability.PAYER_TYPE and r.match_values:
                payer_type = getattr(getattr(invoice, "payer", None), "payer_type", None)
                if payer_type in r.match_values:
                    if candidate is None or r.priority < candidate.priority:
                        candidate = r
                    continue
            if r.applicability == TaxApplicability.PATIENT_TYPE and r.match_values:
                pt = getattr(getattr(invoice, "patient", None), "patient_type", None)
                if pt in r.match_values:
                    if candidate is None or r.priority < candidate.priority:
                        candidate = r
                    continue
        return candidate

    def _is_line_exempt(
        self,
        tt: TaxType,
        item: InvoiceItem,
        invoice: Invoice,
        exemptions: list[TaxExemption],
        *,
        on_date: date,
    ) -> bool:
        for ex in exemptions:
            if ex.tax_type_id != tt.id:
                continue
            if ex.starts_on and ex.starts_on > on_date:
                continue
            if ex.ends_on and ex.ends_on < on_date:
                continue
            target = ex.target_id
            if ex.scope == TaxExemptionScope.PATIENT and target == invoice.patient_id:
                return True
            if ex.scope == TaxExemptionScope.PAYER and target == invoice.payer_id:
                return True
            if ex.scope == TaxExemptionScope.SERVICE and target == getattr(item, "service_id", None):
                return True
            if ex.scope == TaxExemptionScope.PRODUCT and target == getattr(item, "product_id", None):
                return True
            if ex.scope == TaxExemptionScope.ORGANIZATION and target == invoice.facility_id:
                return True
        return False

    def _audit(
        self,
        entity: str,
        entity_id: Optional[int],
        action: str,
        *,
        before: Optional[dict] = None,
        after: Optional[dict] = None,
    ) -> None:
        self.db.add(
            TaxAuditLog(
                actor_user_id=self.actor_user_id,
                entity=entity,
                entity_id=entity_id,
                action=action,
                before_data=before,
                after_data=after,
            )
        )

    @staticmethod
    def _snap(rec: Any) -> dict:
        out: dict[str, Any] = {}
        for col in rec.__table__.columns:
            val = getattr(rec, col.name, None)
            if isinstance(val, (date, datetime)):
                val = val.isoformat()
            elif isinstance(val, Decimal):
                val = str(val)
            out[col.name] = val
        return out
