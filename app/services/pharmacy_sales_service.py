# app/services/pharmacy_sales_service.py
from __future__ import annotations

"""
Retail / OTC point-of-sale for a standalone pharmaceutical store.

A sale moves stock OUT of a store without a prescription or a visit. Every
completed sale is one atomic transaction that:

  * creates a :class:`PharmacySale` + one :class:`PharmacySaleItem` per line,
  * decrements ``InventoryStockItem.quantity_on_hand`` for each line, and
  * writes a ``StockMovement`` (DISPENSE) audit row referencing the sale.

Voiding reverses the stock (RETURN_IN) and flips the sale status.
"""

from datetime import datetime, timezone, date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.enums import StockMovementType
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    InventoryStockItem,
    JournalEntry,
    PharmacySale,
    PharmacySaleItem,
    StockMovement,
)

logger = logging.getLogger(__name__)

TWOPLACES = Decimal("0.01")


def _money(value: Any, field: str = "amount") -> Decimal:
    try:
        return Decimal(str(value if value is not None else 0)).quantize(TWOPLACES)
    except (InvalidOperation, ValueError, TypeError):
        raise BadRequestError(message=f"Invalid {field}: {value!r}.")


class PharmacySalesService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def _next_sale_no(self) -> str:
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        count = (
            self.db.query(func.count(PharmacySale.id))
            .filter(PharmacySale.created_at >= start)
            .scalar()
            or 0
        )
        return f"SALE-{today.strftime('%Y%m%d')}-{count + 1:04d}"

    def create_sale(self, payload: dict) -> PharmacySale:
        store_id = payload.get("store_id")
        if not store_id:
            raise BadRequestError(message="A store is required for a sale.")
        lines = payload.get("items") or []
        if not lines:
            raise BadRequestError(message="A sale needs at least one item.")

        now = datetime.now(timezone.utc)
        sale = PharmacySale(
            sale_no=self._next_sale_no(),
            store_id=int(store_id),
            patient_id=payload.get("patient_id"),
            customer_name=(payload.get("customer_name") or None),
            customer_phone=(payload.get("customer_phone") or None),
            sold_by_staff_id=payload.get("sold_by_staff_id"),
            status="COMPLETED",
            payment_method=(payload.get("payment_method") or "CASH"),
            note=(payload.get("note") or None),
            sold_at=now,
        )

        subtotal = Decimal("0.00")
        sale_items: list[PharmacySaleItem] = []
        for raw in lines:
            item_id = raw.get("stock_item_id")
            item = (
                self.db.query(InventoryStockItem)
                .filter(
                    InventoryStockItem.id == item_id,
                    InventoryStockItem.is_deleted.is_(False),
                )
                .first()
            )
            if not item:
                raise NotFoundError(message=f"Stock item #{item_id} not found.")
            if item.store_id != int(store_id):
                raise BadRequestError(
                    message=f"'{item.item_name}' is not stocked in the selected store.",
                )
            qty = _money(raw.get("quantity"), "quantity")
            if qty <= 0:
                raise BadRequestError(message=f"Quantity for '{item.item_name}' must be greater than zero.")
            on_hand = Decimal(str(item.quantity_on_hand or 0))
            if qty > on_hand:
                raise BadRequestError(
                    message=f"Not enough stock for '{item.item_name}': {on_hand} on hand, {qty} requested.",
                )
            # Unit price defaults to the item's recorded cost when not supplied.
            unit_price = raw.get("unit_price")
            unit_price = _money(unit_price if unit_price not in (None, "") else (item.unit_cost or 0), "unit price")
            line_total = (qty * unit_price).quantize(TWOPLACES)
            subtotal += line_total
            sale_items.append(
                PharmacySaleItem(
                    stock_item_id=item.id,
                    item_name=item.item_name,
                    quantity=qty,
                    unit_price=unit_price,
                    line_total=line_total,
                    unit_cost=_money(item.unit_cost if item.unit_cost is not None else 0, "unit cost"),
                )
            )

        discount = _money(payload.get("discount_amount"), "discount")
        tax = _money(payload.get("tax_amount"), "tax")
        total = (subtotal - discount + tax).quantize(TWOPLACES)
        if total < 0:
            raise BadRequestError(message="Discount cannot exceed the sale total.")
        on_account = bool(payload.get("on_account"))
        amount_paid = payload.get("amount_paid")
        if amount_paid in (None, ""):
            amount_paid = Decimal("0.00") if on_account else total
        amount_paid = _money(amount_paid, "amount paid")
        if not on_account and amount_paid < total:
            raise BadRequestError(
                message=f"Amount paid ({amount_paid}) is less than the total due ({total}).",
            )
        # A credit (on-account) sale cannot be "overpaid"; the balance is owed.
        if on_account and amount_paid > total:
            amount_paid = total

        if on_account:
            sale.payment_method = "ACCOUNT"
            if not (sale.customer_name or sale.patient_id):
                raise BadRequestError(message="A credit sale needs a customer (name or linked patient).")

        sale.subtotal = subtotal.quantize(TWOPLACES)
        sale.discount_amount = discount
        sale.tax_amount = tax
        sale.total_amount = total
        sale.amount_paid = amount_paid
        sale.change_due = max(Decimal("0.00"), (amount_paid - total)).quantize(TWOPLACES)
        sale.items = sale_items

        self.db.add(sale)
        self.db.flush()  # assign sale.id + item ids before writing movements

        # Decrement stock and write a DISPENSE audit row per line (atomic).
        for line in sale_items:
            item = self.db.query(InventoryStockItem).filter(InventoryStockItem.id == line.stock_item_id).first()
            item.quantity_on_hand = Decimal(str(item.quantity_on_hand or 0)) - line.quantity
            self.db.add(
                StockMovement(
                    store_id=sale.store_id,
                    stock_item_id=item.id,
                    performed_by_staff_id=sale.sold_by_staff_id,
                    movement_type=StockMovementType.DISPENSE,
                    reference_no=sale.sale_no,
                    quantity=line.quantity,
                    balance_after=item.quantity_on_hand,
                    movement_date=now,
                    note=f"Retail sale {sale.sale_no}",
                )
            )

        self._commit("Could not complete the sale.")

        # Integrate with Accounting: recognise revenue + cash and the cost of
        # goods sold on the ledger. Best-effort and idempotent — a posting
        # problem must never fail or roll back a completed sale.
        self._post_sale_accounting(sale)

        return self.get_sale(sale.id)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get_sale(self, sale_id: int) -> PharmacySale:
        sale = (
            self.db.query(PharmacySale)
            .options(selectinload(PharmacySale.items))
            .filter(PharmacySale.id == sale_id, PharmacySale.is_deleted.is_(False))
            .first()
        )
        if not sale:
            raise NotFoundError(message="Sale not found.")
        return sale

    def list_sales(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        store_id: Optional[int] = None,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> tuple[list[PharmacySale], int]:
        q = self.db.query(PharmacySale).filter(PharmacySale.is_deleted.is_(False))
        if store_id:
            q = q.filter(PharmacySale.store_id == store_id)
        if status:
            q = q.filter(PharmacySale.status == status.upper())
        if date_from:
            q = q.filter(PharmacySale.sold_at >= datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc))
        if date_to:
            q = q.filter(PharmacySale.sold_at <= datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc))
        total = q.count()
        rows = (
            q.options(selectinload(PharmacySale.items))
            .order_by(PharmacySale.sold_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return rows, total

    def summary(self, *, store_id: Optional[int] = None) -> dict:
        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        q = self.db.query(PharmacySale).filter(
            PharmacySale.is_deleted.is_(False),
            PharmacySale.status == "COMPLETED",
            PharmacySale.sold_at >= start,
        )
        if store_id:
            q = q.filter(PharmacySale.store_id == store_id)
        rows = q.all()
        revenue = sum((Decimal(str(s.total_amount or 0)) for s in rows), Decimal("0.00"))
        by_method: dict[str, float] = {}
        for s in rows:
            by_method[s.payment_method] = round(float(by_method.get(s.payment_method, 0)) + float(s.total_amount or 0), 2)
        return {
            "sales_today": len(rows),
            "revenue_today": float(revenue),
            "items_sold_today": int(
                self.db.query(func.coalesce(func.sum(PharmacySaleItem.quantity), 0))
                .join(PharmacySale, PharmacySaleItem.sale_id == PharmacySale.id)
                .filter(PharmacySale.sold_at >= start, PharmacySale.status == "COMPLETED")
                .scalar()
                or 0
            ),
            "by_method": by_method,
        }

    def store_dashboard(self, *, store_id: Optional[int] = None) -> dict:
        """
        Consolidated retail-pharmacy dashboard: today's and this week's sales,
        gross margin, payment mix, top sellers, and stock health (low-stock,
        expiring-soon, inventory valuation). Everything a store operator needs
        at a glance.
        """
        now = datetime.now(timezone.utc)
        today = now.date()
        day_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        week_start = day_start - timedelta(days=6)

        def _sales_since(since: datetime) -> list[PharmacySale]:
            q = self.db.query(PharmacySale).filter(
                PharmacySale.is_deleted.is_(False),
                PharmacySale.status == "COMPLETED",
                PharmacySale.sold_at >= since,
            )
            if store_id:
                q = q.filter(PharmacySale.store_id == int(store_id))
            return q.options(selectinload(PharmacySale.items)).all()

        def _agg(rows: list[PharmacySale]) -> tuple[Decimal, Decimal, Decimal]:
            revenue = sum((_money(r.total_amount) for r in rows), Decimal("0.00"))
            cogs = Decimal("0.00")
            for r in rows:
                for it in (r.items or []):
                    cogs += (_money(it.quantity) * _money(it.unit_cost if it.unit_cost is not None else 0)).quantize(TWOPLACES)
            return revenue, cogs, (revenue - cogs)

        today_rows = _sales_since(day_start)
        week_rows = _sales_since(week_start)
        t_rev, t_cogs, t_margin = _agg(today_rows)
        w_rev, w_cogs, w_margin = _agg(week_rows)

        by_method: dict[str, float] = {}
        for r in today_rows:
            key = r.payment_method or "CASH"
            by_method[key] = round(by_method.get(key, 0.0) + float(r.total_amount or 0), 2)

        # Top sellers this week by quantity.
        top: dict[str, dict] = {}
        for r in week_rows:
            for it in (r.items or []):
                e = top.setdefault(it.item_name, {"item_name": it.item_name, "quantity": 0.0, "revenue": 0.0})
                e["quantity"] += float(it.quantity or 0)
                e["revenue"] += float(it.line_total or 0)
        top_sellers = sorted(top.values(), key=lambda x: x["quantity"], reverse=True)[:5]

        # Stock health.
        stock_q = self.db.query(InventoryStockItem).filter(InventoryStockItem.is_deleted.is_(False))
        if store_id:
            stock_q = stock_q.filter(InventoryStockItem.store_id == int(store_id))
        items = stock_q.all()
        soon = today + timedelta(days=60)
        inv_value = Decimal("0.00")
        low_stock: list[dict] = []
        expiring: list[dict] = []
        for it in items:
            qoh = _money(it.quantity_on_hand or 0)
            inv_value += (qoh * _money(it.unit_cost if it.unit_cost is not None else 0)).quantize(TWOPLACES)
            if it.reorder_level is not None and qoh <= _money(it.reorder_level):
                low_stock.append({
                    "item_name": it.item_name,
                    "quantity_on_hand": float(qoh),
                    "reorder_level": float(it.reorder_level),
                })
            if it.expiry_date is not None and it.expiry_date <= soon:
                expiring.append({
                    "item_name": it.item_name,
                    "expiry_date": it.expiry_date.isoformat(),
                    "quantity_on_hand": float(qoh),
                })
        low_stock_sorted = sorted(low_stock, key=lambda x: x["quantity_on_hand"])
        expiring_sorted = sorted(expiring, key=lambda x: x["expiry_date"])

        return {
            "today": {"sales": len(today_rows), "revenue": float(t_rev), "cogs": float(t_cogs), "margin": float(t_margin)},
            "week": {"sales": len(week_rows), "revenue": float(w_rev), "cogs": float(w_cogs), "margin": float(w_margin)},
            "payment_mix": by_method,
            "top_sellers": top_sellers,
            "low_stock": low_stock_sorted[:10],
            "low_stock_count": len(low_stock_sorted),
            "expiring_soon": expiring_sorted[:10],
            "expiring_count": len(expiring_sorted),
            "inventory_value": float(inv_value),
            "stock_item_count": len(items),
        }

    # ------------------------------------------------------------------
    # Void (reverses stock)
    # ------------------------------------------------------------------
    def void_sale(self, sale_id: int, *, reason: Optional[str] = None, staff_id: Optional[int] = None) -> PharmacySale:
        sale = self.get_sale(sale_id)
        if sale.status == "VOIDED":
            raise BadRequestError(message="This sale is already voided.")
        now = datetime.now(timezone.utc)
        for line in sale.items:
            item = self.db.query(InventoryStockItem).filter(InventoryStockItem.id == line.stock_item_id).first()
            if item is None:
                continue
            item.quantity_on_hand = Decimal(str(item.quantity_on_hand or 0)) + Decimal(str(line.quantity))
            self.db.add(
                StockMovement(
                    store_id=sale.store_id,
                    stock_item_id=item.id,
                    performed_by_staff_id=staff_id or sale.sold_by_staff_id,
                    movement_type=StockMovementType.RETURN_IN,
                    reference_no=sale.sale_no,
                    quantity=Decimal(str(line.quantity)),
                    balance_after=item.quantity_on_hand,
                    movement_date=now,
                    note=f"Void of sale {sale.sale_no}",
                )
            )
        sale.status = "VOIDED"
        sale.voided_at = now
        sale.void_reason = reason or None
        self._commit("Could not void the sale.")

        # Reverse the sale's ledger postings (revenue, cash and COGS).
        self._reverse_sale_accounting(sale, staff_id=staff_id)

        return self.get_sale(sale.id)

    # ------------------------------------------------------------------
    # Accounting integration (revenue / cash / COGS)
    # ------------------------------------------------------------------
    @staticmethod
    def _cash_account_key(payment_method: Optional[str]) -> str:
        """Map a sale's payment method to the debit (asset) account key."""
        pm = (payment_method or "CASH").strip().upper()
        if pm in {"CASH", "PETTY_CASH"}:
            return "CASH_ON_HAND"
        # Transfer, card, POS terminal, gateway, bank → bank account.
        return "BANK_DEFAULT"

    def _posted(self, ref: str) -> bool:
        return (
            self.db.query(JournalEntry.id)
            .filter(JournalEntry.source_ref == ref, JournalEntry.is_deleted.is_(False))
            .first()
            is not None
        )

    def _post_sale_accounting(self, sale: PharmacySale, *, reverse: bool = False) -> None:
        """
        Post (or reverse) the double-entry for a retail sale:

          Revenue + cash     Dr Cash/Bank              = total
                             Cr Pharmacy Sales Revenue = subtotal - discount
                             Cr VAT Payable            = tax
          Cost of goods sold Dr Pharmacy COGS          = Σ qty·unit_cost
                             Cr Inventory              = Σ qty·unit_cost

        A reversal posts the same amounts with debit/credit sides swapped (no
        negative amounts — the ledger forbids them). Idempotent via
        ``source_ref`` and fully best-effort: any failure is logged and
        swallowed so the sale/void itself is never affected. On a fresh tenant
        ``resolve_system_account`` creates the accounts on demand.
        """
        try:
            from app.services.accounting_service import AccountingService
            from app.services.system_accounts_service import resolve_system_account
            from app.core.enums import JournalSourceType

            def line(account_id, amount, *, debit):
                # Swap sides on a reversal so amounts stay positive.
                is_debit = debit if not reverse else (not debit)
                return {
                    "account_id": account_id,
                    "debit": amount if is_debit else Decimal("0.00"),
                    "credit": Decimal("0.00") if is_debit else amount,
                    "description": f"{'Void ' if reverse else ''}Pharmacy sale {sale.sale_no}",
                }

            suffix = "void" if reverse else "sale"
            rev_ref = f"pharmacy_sale_{suffix}:{sale.id}"
            cogs_ref = f"pharmacy_sale_{suffix}_cogs:{sale.id}"

            accounting = AccountingService(self.db)
            when = (sale.sold_at or datetime.now(timezone.utc)).date()

            total = _money(sale.total_amount)
            tax = _money(sale.tax_amount)
            discount = _money(sale.discount_amount)
            subtotal = _money(sale.subtotal)
            net_revenue = (subtotal - discount).quantize(TWOPLACES)

            # ---- Entry 1: revenue + cash / receivable ----
            if total > 0 and net_revenue > 0 and not self._posted(rev_ref):
                revenue = resolve_system_account(self.db, "PHARMACY_SALES_REVENUE")
                # Split the debit between cash actually taken and the amount left
                # on the customer's account (credit sale).
                paid = min(_money(sale.amount_paid), total)
                receivable = (total - paid).quantize(TWOPLACES)
                lines = []
                if paid > 0:
                    cash = resolve_system_account(self.db, self._cash_account_key(sale.payment_method))
                    lines.append(line(cash.id, paid, debit=True))
                if receivable > 0:
                    ar = resolve_system_account(self.db, "CUSTOMER_AR")
                    lines.append(line(ar.id, receivable, debit=True))
                lines.append(line(revenue.id, net_revenue, debit=False))
                if tax > 0:
                    vat = resolve_system_account(self.db, "VAT_PAYABLE")
                    lines.append(line(vat.id, tax, debit=False))
                accounting.create_entry(
                    entry_date=when,
                    memo=f"{'Void of ' if reverse else ''}Pharmacy sale {sale.sale_no}",
                    lines=lines,
                    source_type=JournalSourceType.BILLING_PAYMENT,
                    source_ref=rev_ref,
                    auto_post=True,
                )

            # ---- Entry 2: cost of goods sold ----
            cost_total = Decimal("0.00")
            for item_line in (sale.items or []):
                unit_cost = _money(item_line.unit_cost if item_line.unit_cost is not None else 0)
                cost_total += (_money(item_line.quantity) * unit_cost).quantize(TWOPLACES)
            if cost_total > 0 and not self._posted(cogs_ref):
                cogs = resolve_system_account(self.db, "PHARMACY_COGS")
                inventory = resolve_system_account(self.db, "INVENTORY_ASSET")
                accounting.create_entry(
                    entry_date=when,
                    memo=f"{'Void of ' if reverse else ''}Pharmacy COGS {sale.sale_no}",
                    lines=[
                        line(cogs.id, cost_total, debit=True),
                        line(inventory.id, cost_total, debit=False),
                    ],
                    source_type=JournalSourceType.INVENTORY,
                    source_ref=cogs_ref,
                    auto_post=True,
                )

            self.db.commit()
        except Exception as exc:  # pragma: no cover - accounting must not break sales
            logger.warning("Pharmacy sale %s accounting posting failed: %s", getattr(sale, "sale_no", "?"), exc)
            try:
                self.db.rollback()
            except Exception:
                pass

    def _reverse_sale_accounting(self, sale: PharmacySale, *, staff_id: Optional[int] = None) -> None:
        self._post_sale_accounting(sale, reverse=True)

    # ------------------------------------------------------------------
    # Credit sales (customer accounts)
    # ------------------------------------------------------------------
    def settle_sale(self, sale_id: int, *, amount, payment_method: str = "CASH",
                    staff_id: Optional[int] = None) -> PharmacySale:
        """Record a customer payment against a credit sale's outstanding balance."""
        sale = self.get_sale(sale_id)
        if sale.status != "COMPLETED":
            raise BadRequestError(message="Only completed sales can be settled.")
        total = _money(sale.total_amount)
        paid = _money(sale.amount_paid)
        outstanding = (total - paid).quantize(TWOPLACES)
        if outstanding <= 0:
            raise BadRequestError(message="This sale has no outstanding balance.")
        amt = _money(amount, "amount")
        if amt <= 0:
            raise BadRequestError(message="Settlement amount must be greater than zero.")
        if amt > outstanding:
            amt = outstanding
        sale.amount_paid = (paid + amt).quantize(TWOPLACES)
        self._commit("Could not record the payment.")
        self._post_settlement_accounting(sale, amt, payment_method)
        return self.get_sale(sale.id)

    def _post_settlement_accounting(self, sale: PharmacySale, amount: Decimal, payment_method: str) -> None:
        """Post a customer payment: Dr Cash/Bank, Cr Customer AR. Best-effort."""
        try:
            from app.services.accounting_service import AccountingService
            from app.services.system_accounts_service import resolve_system_account
            from app.core.enums import JournalSourceType

            accounting = AccountingService(self.db)
            cash = resolve_system_account(self.db, self._cash_account_key(payment_method))
            ar = resolve_system_account(self.db, "CUSTOMER_AR")
            now = datetime.now(timezone.utc)
            ref = f"pharmacy_sale_settle:{sale.id}:{int(now.timestamp())}"
            accounting.create_entry(
                entry_date=now.date(),
                memo=f"Customer payment for sale {sale.sale_no}",
                lines=[
                    {"account_id": cash.id, "debit": amount, "credit": Decimal("0.00"),
                     "description": f"Payment on sale {sale.sale_no}"},
                    {"account_id": ar.id, "debit": Decimal("0.00"), "credit": amount,
                     "description": f"Settle receivable {sale.sale_no}"},
                ],
                source_type=JournalSourceType.BILLING_PAYMENT,
                source_ref=ref,
                auto_post=True,
            )
            self.db.commit()
        except Exception as exc:  # pragma: no cover
            logger.warning("Pharmacy settlement posting failed for %s: %s", sale.sale_no, exc)
            try:
                self.db.rollback()
            except Exception:
                pass

    def list_outstanding(self, *, store_id: Optional[int] = None) -> list[dict]:
        """List credit sales that still carry an outstanding balance."""
        q = self.db.query(PharmacySale).filter(
            PharmacySale.is_deleted.is_(False),
            PharmacySale.status == "COMPLETED",
            PharmacySale.total_amount > PharmacySale.amount_paid,
        )
        if store_id:
            q = q.filter(PharmacySale.store_id == int(store_id))
        rows = q.order_by(PharmacySale.sold_at.desc()).all()
        out = []
        for s in rows:
            total = _money(s.total_amount)
            paid = _money(s.amount_paid)
            out.append({
                "id": s.id,
                "sale_no": s.sale_no,
                "customer_name": s.customer_name,
                "customer_phone": s.customer_phone,
                "patient_id": s.patient_id,
                "total_amount": float(total),
                "amount_paid": float(paid),
                "outstanding": float((total - paid).quantize(TWOPLACES)),
                "sold_at": s.sold_at.isoformat() if s.sold_at else None,
            })
        return out

    # ------------------------------------------------------------------
    def _commit(self, message: str) -> None:
        try:
            self.db.commit()
        except Exception as exc:  # pragma: no cover - surfaced to the caller
            self.db.rollback()
            raise BadRequestError(message=message, detail={"error": str(exc)})
