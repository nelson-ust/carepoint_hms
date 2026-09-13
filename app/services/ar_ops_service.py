# app/services/ar_ops_service.py
from __future__ import annotations

"""
Accounts-receivable completeness: credit notes, refunds, bad-debt write-offs,
vendor credit notes, AP payment runs and statements of account.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    CreditNoteStatus,
    InvoiceStatus,
    JournalSourceType,
    PaymentStatus,
    RefundStatus,
    VendorBillStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    Invoice,
    InvoiceItem,
    Patient,
    Payment,
    Vendor,
    VendorBill,
)
from app.models.finance_models import (
    BankAccount,
    CreditNote,
    CreditNoteItem,
    PettyCashFloat,
    Refund,
    VendorCreditNote,
)
from app.services.accounting_service import AccountingService, _d
from app.services.system_accounts_service import (
    audit,
    next_document_no,
    resolve_system_account,
)


class ArOpsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.accounting = AccountingService(db)

    # ------------------------------------------------------------------
    # Credit notes
    # ------------------------------------------------------------------

    def _cn_read(self, cn: CreditNote) -> dict:
        return {
            "id": cn.id, "credit_note_no": cn.credit_note_no,
            "invoice_id": cn.invoice_id,
            "invoice_no": cn.invoice.invoice_no if cn.invoice else None,
            "patient_id": cn.invoice.patient_id if cn.invoice else None,
            "reason": cn.reason,
            "total_amount": str(_d(cn.total_amount)),
            "applied_amount": str(_d(cn.applied_amount)),
            "status": cn.status.value if hasattr(cn.status, "value") else cn.status,
            "issued_at": cn.issued_at.isoformat() if cn.issued_at else None,
            "items": [{"id": i.id, "invoice_item_id": i.invoice_item_id,
                       "description": i.description, "amount": str(_d(i.amount))}
                      for i in (cn.items or []) if not i.is_deleted],
        }

    def list_credit_notes(self, *, invoice_id: Optional[int] = None,
                          status: Optional[str] = None) -> list[dict]:
        q = self.db.query(CreditNote).filter(CreditNote.is_deleted.is_(False))
        if invoice_id:
            q = q.filter(CreditNote.invoice_id == invoice_id)
        if status:
            q = q.filter(CreditNote.status == CreditNoteStatus(status))
        return [self._cn_read(cn) for cn in q.order_by(CreditNote.id.desc()).all()]

    def create_credit_note(self, *, invoice_id: int, reason: Optional[str],
                           items: list[dict], user_id: Optional[int] = None) -> dict:
        """items: [{invoice_item_id?, description?, amount}]"""
        inv = (self.db.query(Invoice)
               .filter(Invoice.id == invoice_id, Invoice.is_deleted.is_(False)).first())
        if inv is None:
            raise NotFoundError("Invoice not found.")
        if not items:
            raise BadRequestError("At least one credit line is required.")
        total = Decimal("0")
        cn = CreditNote(credit_note_no=next_document_no(self.db, "CREDIT_NOTE"),
                        invoice_id=inv.id, reason=reason, issued_by_user_id=user_id)
        self.db.add(cn)
        self.db.flush()
        for it in items:
            amount = _d(it.get("amount"))
            if amount <= 0:
                raise BadRequestError("Credit amounts must be positive.")
            desc = it.get("description")
            if it.get("invoice_item_id"):
                line = (self.db.query(InvoiceItem)
                        .filter(InvoiceItem.id == it["invoice_item_id"],
                                InvoiceItem.invoice_id == inv.id).first())
                if line is None:
                    raise BadRequestError(f"Invoice item {it['invoice_item_id']} not on this invoice.")
                desc = desc or line.service_name
                if amount > _d(line.line_total):
                    raise BadRequestError(
                        f"Credit {amount} exceeds line total {line.line_total} for {line.service_name}.")
            self.db.add(CreditNoteItem(credit_note_id=cn.id,
                                       invoice_item_id=it.get("invoice_item_id"),
                                       description=desc, amount=amount))
            total += amount
        if total > _d(inv.total_amount):
            raise BadRequestError("Credit note exceeds the invoice total.")
        cn.total_amount = total
        self.db.flush()
        self.db.commit()
        return self._cn_read(cn)

    def issue_credit_note(self, credit_note_id: int, *,
                          user_id: Optional[int] = None) -> dict:
        """Post Dr Revenue (contra) / Cr Patient AR and reduce the invoice
        balance."""
        cn = (self.db.query(CreditNote)
              .filter(CreditNote.id == credit_note_id,
                      CreditNote.is_deleted.is_(False)).first())
        if cn is None:
            raise NotFoundError("Credit note not found.")
        if cn.status != CreditNoteStatus.DRAFT:
            raise BadRequestError(f"Credit note is already {cn.status.value}.")
        inv = cn.invoice
        amount = _d(cn.total_amount)
        revenue = resolve_system_account(self.db, "PATIENT_REVENUE")
        ar = resolve_system_account(self.db, "PATIENT_AR")
        self.accounting.create_entry(
            entry_date=date.today(),
            memo=f"Credit note {cn.credit_note_no} on invoice {inv.invoice_no}",
            lines=[
                {"account_id": revenue.id, "debit": amount, "credit": 0,
                 "description": cn.reason or "Credit note"},
                {"account_id": ar.id, "debit": 0, "credit": amount,
                 "description": f"CN {cn.credit_note_no}"},
            ],
            source_type=JournalSourceType.CREDIT_NOTE,
            source_ref=f"credit_note:{cn.id}", user_id=user_id, auto_post=True)
        cn.status = CreditNoteStatus.ISSUED
        cn.issued_at = datetime.now(timezone.utc)
        # Apply to the invoice balance immediately.
        applied = min(amount, _d(inv.balance_due))
        inv.balance_due = _d(inv.balance_due) - applied
        cn.applied_amount = applied
        if inv.balance_due <= 0:
            inv.balance_due = Decimal("0")
            if _d(inv.amount_paid) > 0 or applied > 0:
                inv.status = InvoiceStatus.PAID
        if applied >= amount:
            cn.status = CreditNoteStatus.APPLIED
        audit(self.db, action="CREDIT_NOTE_ISSUED", entity_type="credit_note",
              entity_id=cn.id, user_id=user_id,
              summary=f"{cn.credit_note_no}: {amount} on {inv.invoice_no}")
        self.db.commit()
        return self._cn_read(cn)

    # ------------------------------------------------------------------
    # Refunds
    # ------------------------------------------------------------------

    def _refund_read(self, r: Refund) -> dict:
        return {"id": r.id, "refund_no": r.refund_no,
                "patient_id": r.patient_id,
                "insurance_provider_id": r.insurance_provider_id,
                "invoice_id": r.invoice_id, "credit_note_id": r.credit_note_id,
                "amount": str(_d(r.amount)),
                "bank_account_id": r.bank_account_id,
                "petty_cash_float_id": r.petty_cash_float_id,
                "reason": r.reason,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
                "paid_at": r.paid_at.isoformat() if r.paid_at else None}

    def list_refunds(self, *, status: Optional[str] = None) -> list[dict]:
        q = self.db.query(Refund).filter(Refund.is_deleted.is_(False))
        if status:
            q = q.filter(Refund.status == RefundStatus(status))
        return [self._refund_read(r) for r in q.order_by(Refund.id.desc()).all()]

    def create_refund(self, *, amount, patient_id: Optional[int] = None,
                      insurance_provider_id: Optional[int] = None,
                      invoice_id: Optional[int] = None,
                      credit_note_id: Optional[int] = None,
                      bank_account_id: Optional[int] = None,
                      petty_cash_float_id: Optional[int] = None,
                      reason: Optional[str] = None,
                      user_id: Optional[int] = None) -> dict:
        amount = _d(amount)
        if amount <= 0:
            raise BadRequestError("Amount must be positive.")
        if bool(bank_account_id) == bool(petty_cash_float_id):
            raise BadRequestError("Choose exactly one source: bank account or petty cash float.")
        r = Refund(refund_no=next_document_no(self.db, "REFUND"),
                   patient_id=patient_id,
                   insurance_provider_id=insurance_provider_id,
                   invoice_id=invoice_id, credit_note_id=credit_note_id,
                   amount=amount, bank_account_id=bank_account_id,
                   petty_cash_float_id=petty_cash_float_id,
                   reason=reason, approved_by_user_id=user_id)
        self.db.add(r)
        self.db.flush()
        self.db.commit()
        return self._refund_read(r)

    def pay_refund(self, refund_id: int, *, user_id: Optional[int] = None) -> dict:
        r = (self.db.query(Refund)
             .filter(Refund.id == refund_id, Refund.is_deleted.is_(False)).first())
        if r is None:
            raise NotFoundError("Refund not found.")
        if r.status != RefundStatus.PENDING:
            raise BadRequestError(f"Refund is already {r.status.value}.")
        amount = _d(r.amount)
        ar = resolve_system_account(
            self.db, "HMO_AR" if r.insurance_provider_id else "PATIENT_AR")
        if r.bank_account_id:
            src = (self.db.query(BankAccount)
                   .filter(BankAccount.id == r.bank_account_id).first())
            if src is None:
                raise NotFoundError("Bank account not found.")
            cash_account_id = src.account_id
        else:
            f = (self.db.query(PettyCashFloat)
                 .filter(PettyCashFloat.id == r.petty_cash_float_id).first())
            if f is None:
                raise NotFoundError("Petty cash float not found.")
            cash_account_id = f.account_id
        self.accounting.create_entry(
            entry_date=date.today(), memo=f"Refund {r.refund_no}",
            lines=[
                {"account_id": ar.id, "debit": amount, "credit": 0,
                 "description": r.reason or "Refund"},
                {"account_id": cash_account_id, "debit": 0, "credit": amount,
                 "description": f"Refund {r.refund_no} paid out"},
            ],
            source_type=JournalSourceType.REFUND,
            source_ref=f"refund:{r.id}", user_id=user_id, auto_post=True)
        r.status = RefundStatus.PAID
        r.paid_at = date.today()
        audit(self.db, action="REFUND_PAID", entity_type="refund",
              entity_id=r.id, user_id=user_id, summary=f"{r.refund_no}: {amount}")
        self.db.commit()
        return self._refund_read(r)

    # ------------------------------------------------------------------
    # Bad-debt write-off
    # ------------------------------------------------------------------

    def write_off_invoice(self, *, invoice_id: int, amount=None,
                          reason: Optional[str] = None,
                          user_id: Optional[int] = None) -> dict:
        inv = (self.db.query(Invoice)
               .filter(Invoice.id == invoice_id, Invoice.is_deleted.is_(False)).first())
        if inv is None:
            raise NotFoundError("Invoice not found.")
        balance = _d(inv.balance_due)
        amount = _d(amount) if amount is not None else balance
        if amount <= 0 or amount > balance:
            raise BadRequestError(f"Write-off must be positive and ≤ balance due ({balance}).")
        bad_debt = resolve_system_account(self.db, "BAD_DEBT_EXPENSE")
        ar = resolve_system_account(self.db, "PATIENT_AR")
        self.accounting.create_entry(
            entry_date=date.today(),
            memo=f"Bad-debt write-off — invoice {inv.invoice_no}",
            lines=[
                {"account_id": bad_debt.id, "debit": amount, "credit": 0,
                 "description": reason or "Bad debt"},
                {"account_id": ar.id, "debit": 0, "credit": amount,
                 "description": f"Write-off {inv.invoice_no}"},
            ],
            source_type=JournalSourceType.WRITE_OFF,
            source_ref=f"invoice_write_off:{inv.id}:{int(_d(inv.balance_due) - amount)}",
            user_id=user_id, auto_post=True)
        inv.balance_due = balance - amount
        if inv.balance_due <= 0:
            inv.balance_due = Decimal("0")
            inv.status = InvoiceStatus.WAIVED
        audit(self.db, action="INVOICE_WRITTEN_OFF", entity_type="invoice",
              entity_id=inv.id, user_id=user_id,
              summary=f"{inv.invoice_no}: {amount} ({reason or 'no reason'})")
        self.db.commit()
        return {"invoice_id": inv.id, "written_off": str(amount),
                "balance_due": str(_d(inv.balance_due)),
                "status": inv.status.value if hasattr(inv.status, "value") else inv.status}

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def patient_statement(self, patient_id: int, *,
                          date_from: Optional[date] = None,
                          date_to: Optional[date] = None) -> dict:
        patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
        if patient is None:
            raise NotFoundError("Patient not found.")
        rows: list[dict] = []
        invoices = (self.db.query(Invoice)
                    .filter(Invoice.patient_id == patient_id,
                            Invoice.is_deleted.is_(False),
                            Invoice.status.notin_([InvoiceStatus.DRAFT,
                                                   InvoiceStatus.VOIDED,
                                                   InvoiceStatus.CANCELLED])).all())
        for inv in invoices:
            d0 = inv.invoice_date.date() if inv.invoice_date else inv.date_created.date()
            rows.append({"date": d0, "type": "INVOICE", "ref": inv.invoice_no,
                         "debit": _d(inv.total_amount), "credit": Decimal("0")})
            for p in (inv.payments or []):
                if p.is_deleted or p.payment_status != PaymentStatus.SUCCESSFUL:
                    continue
                rows.append({"date": p.paid_at.date() if p.paid_at else d0,
                             "type": "PAYMENT", "ref": p.payment_reference,
                             "debit": Decimal("0"), "credit": _d(p.amount)})
            for cn in (self.db.query(CreditNote)
                       .filter(CreditNote.invoice_id == inv.id,
                               CreditNote.is_deleted.is_(False),
                               CreditNote.status.in_([CreditNoteStatus.ISSUED,
                                                      CreditNoteStatus.APPLIED])).all()):
                rows.append({"date": cn.issued_at.date() if cn.issued_at else d0,
                             "type": "CREDIT_NOTE", "ref": cn.credit_note_no,
                             "debit": Decimal("0"), "credit": _d(cn.total_amount)})
        rows.sort(key=lambda r: r["date"])
        opening = Decimal("0")
        if date_from:
            opening = sum((r["debit"] - r["credit"] for r in rows if r["date"] < date_from),
                          Decimal("0"))
            rows = [r for r in rows if r["date"] >= date_from]
        if date_to:
            rows = [r for r in rows if r["date"] <= date_to]
        running = opening
        out = []
        for r in rows:
            running += r["debit"] - r["credit"]
            out.append({**r, "date": r["date"].isoformat(),
                        "debit": str(r["debit"]), "credit": str(r["credit"]),
                        "balance": str(running)})
        return {"patient_id": patient_id,
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "opening_balance": str(opening), "closing_balance": str(running),
                "rows": out}

    # ------------------------------------------------------------------
    # Vendor credit notes + payment runs (AP completeness)
    # ------------------------------------------------------------------

    def create_vendor_credit_note(self, *, vendor_id: int, amount,
                                  vendor_bill_id: Optional[int] = None,
                                  reason: Optional[str] = None,
                                  user_id: Optional[int] = None) -> dict:
        vendor = (self.db.query(Vendor)
                  .filter(Vendor.id == vendor_id, Vendor.is_deleted.is_(False)).first())
        if vendor is None:
            raise NotFoundError("Vendor not found.")
        amount = _d(amount)
        if amount <= 0:
            raise BadRequestError("Amount must be positive.")
        bill = None
        expense_account_id = None
        if vendor_bill_id:
            bill = (self.db.query(VendorBill)
                    .filter(VendorBill.id == vendor_bill_id,
                            VendorBill.is_deleted.is_(False)).first())
            if bill is None or bill.vendor_id != vendor_id:
                raise BadRequestError("Bill not found for this vendor.")
            outstanding = _d(bill.total_amount) - _d(bill.amount_paid)
            if amount > outstanding:
                raise BadRequestError(f"Credit {amount} exceeds bill balance {outstanding}.")
            expense_account_id = bill.expense_account_id
        vcn = VendorCreditNote(
            credit_note_no=next_document_no(self.db, "VENDOR_CN"),
            vendor_id=vendor_id, vendor_bill_id=vendor_bill_id,
            amount=amount, reason=reason, issued_at=date.today())
        self.db.add(vcn)
        self.db.flush()
        ap = resolve_system_account(self.db, "AP")
        contra_id = expense_account_id or resolve_system_account(self.db, "BANK_CHARGES").id
        self.accounting.create_entry(
            entry_date=date.today(),
            memo=f"Vendor credit note {vcn.credit_note_no} — {vendor.name}",
            lines=[
                {"account_id": ap.id, "debit": amount, "credit": 0,
                 "description": reason or "Vendor credit"},
                {"account_id": contra_id, "debit": 0, "credit": amount,
                 "description": f"VCN {vcn.credit_note_no}"},
            ],
            source_type=JournalSourceType.CREDIT_NOTE,
            source_ref=f"vendor_credit_note:{vcn.id}", user_id=user_id, auto_post=True)
        if bill is not None:
            bill.amount_paid = _d(bill.amount_paid) + amount
            vcn.applied_amount = amount
            if bill.amount_paid >= _d(bill.total_amount):
                bill.status = VendorBillStatus.PAID
            else:
                bill.status = VendorBillStatus.PARTIALLY_PAID
        self.db.commit()
        return {"id": vcn.id, "credit_note_no": vcn.credit_note_no,
                "vendor_id": vendor_id, "amount": str(amount),
                "vendor_bill_id": vendor_bill_id}

    def vendor_statement(self, vendor_id: int) -> dict:
        vendor = (self.db.query(Vendor)
                  .filter(Vendor.id == vendor_id, Vendor.is_deleted.is_(False)).first())
        if vendor is None:
            raise NotFoundError("Vendor not found.")
        rows = []
        for b in (self.db.query(VendorBill)
                  .filter(VendorBill.vendor_id == vendor_id,
                          VendorBill.is_deleted.is_(False)).all()):
            rows.append({"date": b.bill_date, "type": "BILL", "ref": b.bill_no,
                         "debit": Decimal("0"), "credit": _d(b.total_amount)})
            for p in (b.payments or []):
                if p.is_deleted:
                    continue
                rows.append({"date": p.paid_at, "type": "PAYMENT",
                             "ref": p.reference or f"PMT-{p.id}",
                             "debit": _d(p.amount), "credit": Decimal("0")})
        for vcn in (self.db.query(VendorCreditNote)
                    .filter(VendorCreditNote.vendor_id == vendor_id,
                            VendorCreditNote.is_deleted.is_(False)).all()):
            rows.append({"date": vcn.issued_at or date.today(), "type": "CREDIT_NOTE",
                         "ref": vcn.credit_note_no, "debit": _d(vcn.amount),
                         "credit": Decimal("0")})
        rows.sort(key=lambda r: r["date"])
        running = Decimal("0")
        out = []
        for r in rows:
            running += r["credit"] - r["debit"]  # payable balance
            out.append({**r, "date": r["date"].isoformat(),
                        "debit": str(r["debit"]), "credit": str(r["credit"]),
                        "balance": str(running)})
        return {"vendor_id": vendor_id, "vendor_name": vendor.name,
                "closing_balance": str(running), "rows": out}

    def payment_run(self, *, bill_ids: list[int], bank_account_id: int,
                    paid_at: Optional[date] = None,
                    user_id: Optional[int] = None) -> dict:
        """Pay several due vendor bills from one bank account in one action."""
        from app.services.finance_ops_service import VendorService
        bank = (self.db.query(BankAccount)
                .filter(BankAccount.id == bank_account_id,
                        BankAccount.is_deleted.is_(False)).first())
        if bank is None:
            raise NotFoundError("Bank account not found.")
        paid_at = paid_at or date.today()
        vs = VendorService(self.db)
        results = []
        for bid in bill_ids:
            bill = (self.db.query(VendorBill)
                    .filter(VendorBill.id == bid, VendorBill.is_deleted.is_(False)).first())
            if bill is None:
                results.append({"bill_id": bid, "error": "not found"})
                continue
            outstanding = _d(bill.total_amount) - _d(bill.amount_paid)
            if outstanding <= 0:
                results.append({"bill_id": bid, "error": "already settled"})
                continue
            vs.pay_bill(bill_id=bid, amount=outstanding, paid_at=paid_at,
                        payment_method="BANK_TRANSFER",
                        reference=f"PAYRUN-{paid_at.isoformat()}",
                        cash_account_id=bank.account_id, user_id=user_id)
            results.append({"bill_id": bid, "paid": str(outstanding)})
        audit(self.db, action="AP_PAYMENT_RUN", entity_type="bank_account",
              entity_id=bank.id, user_id=user_id,
              summary=f"Payment run: {len(bill_ids)} bills")
        self.db.commit()
        return {"bank_account_id": bank_account_id, "results": results}
