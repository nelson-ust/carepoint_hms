# app/services/billing_service.py
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import BillingStatus, MembershipCardStatus, PaymentStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    BillableService,
    Billing,
    BillingItem,
    BillingPayment,
    MembershipCard,
)
from app.repositories.billing_repository import (
    BillableServiceRepository,
    BillingRepository,
)
from app.schemas.billing_schemas import (
    BillableServiceCreateSchema,
    BillableServiceUpdateSchema,
    BillingCreateSchema,
    BillingItemCreateSchema,
)
from app.schemas.membership_card_schemas import MembershipCardDebit
from app.utils.charge_capture import resolve_cash_account, summarize_purpose
from app.utils.security_event_util import record_security_event


class BillableServiceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = BillableServiceRepository(db)

    def list(self, *, skip=0, limit=50, search=None, category=None):
        return self.repository.list_services(
            skip=skip, limit=limit, search=search, category=category
        )

    def get(self, sid: int) -> BillableService:
        return self.repository.get_required_by_id(sid)

    def _validate_account(self, account_id) -> None:
        from app.models.all_models import Account
        acct = (
            self.db.query(Account)
            .filter(Account.id == account_id, Account.is_deleted.is_(False))
            .first()
        )
        if acct is None:
            raise NotFoundError(
                message="The selected account does not exist.",
                detail={"account_id": account_id},
            )

    def create(self, payload: BillableServiceCreateSchema) -> BillableService:
        self._validate_account(payload.account_id)
        s = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(s.id)

    def update(self, sid: int, payload: BillableServiceUpdateSchema) -> BillableService:
        if payload.account_id is not None:
            self._validate_account(payload.account_id)
        s = self.repository.get_required_by_id(sid)
        updated = self.repository.update(s, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        fresh = self.repository.get_required_by_id(updated.id)
        # When the ledger account changes, back-stamp it onto this service's
        # existing charge lines that were captured before a mapping existed, so
        # previously-unaccounted charges reconcile to the GL.
        if payload.account_id is not None:
            self._backfill_line_item_accounts(fresh)
        return fresh

    def _backfill_line_item_accounts(self, service: BillableService) -> int:
        """Stamp ``service``'s account code/name onto its billing lines that
        currently have no account. Only fills gaps — never overwrites a line
        that already carries an account. Returns the number of lines updated."""
        acct = getattr(service, "account", None)
        if acct is None:
            return 0
        from app.models.all_models import BillingItem

        items = (
            self.db.query(BillingItem)
            .filter(
                BillingItem.billable_service_id == service.id,
                BillingItem.is_deleted.is_(False),
                BillingItem.account_code.is_(None),
            )
            .all()
        )
        for it in items:
            it.account_code = acct.code
            it.account_name = acct.name
            self.db.add(it)
        if items:
            self.db.commit()
        return len(items)

    def soft_delete(self, sid: int) -> BillableService:
        s = self.repository.get_required_by_id(sid)
        deleted = self.repository.soft_delete(s)
        self.db.commit()
        return deleted

    def mapping_health(self) -> dict:
        """Catalog reconciliation check: which active billable services still
        have no ledger account, so their captured charges cannot post to the
        GL. Drives the "needs a GL account" surface in the catalog UI."""
        q = self.db.query(BillableService).filter(BillableService.is_deleted.is_(False))
        total = q.count()
        missing = (
            q.filter(BillableService.account_id.is_(None))
            .order_by(BillableService.category.asc(), BillableService.code.asc())
            .all()
        )
        return {
            "success": True,
            "total_services": total,
            "missing_account": len(missing),
            "items": [
                {"id": s.id, "code": s.code, "name": s.name, "category": s.category}
                for s in missing
            ],
        }

    # ------------------------------------------------------------------
    # Bulk import
    # ------------------------------------------------------------------

    def build_import_template(self) -> bytes:
        from app.models.all_models import Account
        from app.utils.account_import import build_billable_service_template

        accounts = (
            self.db.query(Account)
            .filter(Account.is_deleted.is_(False))
            .order_by(Account.code.asc())
            .all()
        )
        return build_billable_service_template([(a.code, a.name) for a in accounts])

    def bulk_create(self, rows: list) -> dict:
        from decimal import Decimal, InvalidOperation

        from app.core.exceptions import AlreadyExistsError
        from app.models.all_models import Account

        account_by_code = {}
        for a in self.db.query(Account).filter(Account.is_deleted.is_(False)).all():
            account_by_code[a.code.strip().upper()] = a.id

        errors: list = []
        created = 0
        seen_codes: set = set()
        for entry in rows:
            row_no = entry.get("row")
            data = entry.get("data", {}) or {}
            try:
                code = str(data.get("code") or "").strip()
                name = str(data.get("name") or "").strip()
                if not code:
                    raise ValueError("Service Code is required.")
                if not name:
                    raise ValueError("Service Name is required.")
                norm_code = code.upper().replace(" ", "_")
                if norm_code in seen_codes:
                    raise ValueError(f"Duplicate code '{code}' in this file.")
                raw_price = data.get("default_price")
                try:
                    price = Decimal(str(raw_price)) if raw_price is not None else Decimal("0")
                except (InvalidOperation, ValueError):
                    raise ValueError(f"Rate '{raw_price}' is not a valid number.")
                if price <= 0:
                    raise ValueError("Rate must be greater than 0.")
                acc_code = str(data.get("account_code") or "").strip().upper()
                if not acc_code:
                    raise ValueError("Account Code is required.")
                account_id = account_by_code.get(acc_code)
                if account_id is None:
                    raise ValueError(f"Account code '{acc_code}' does not exist. Create it first.")
                with self.db.begin_nested():
                    self.repository.create(
                        code=norm_code,
                        name=name,
                        category=data.get("category"),
                        default_price=price,
                        account_id=account_id,
                        description=data.get("description"),
                    )
                seen_codes.add(norm_code)
                created += 1
            except AlreadyExistsError as exc:
                errors.append({"row": row_no, "message": getattr(exc, "message", None) or "A service with this code already exists."})
            except ValueError as exc:
                errors.append({"row": row_no, "message": str(exc)})
            except Exception as exc:  # pragma: no cover
                errors.append({"row": row_no, "message": f"Could not save this row: {exc}"})

        if created:
            self.db.commit()
        total = len(rows)
        failed = len(errors)
        if created and not failed:
            message = f"All {created} service(s) imported successfully."
        elif created and failed:
            message = f"Imported {created} service(s); {failed} row(s) had problems."
        elif failed:
            message = f"No services imported \u2014 all {failed} row(s) had problems."
        else:
            message = "The file had no data rows to import."
        return {
            "success": failed == 0 and created > 0,
            "message": message,
            "total_rows": total,
            "created": created,
            "failed": failed,
            "errors": errors,
        }


class BillingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = BillingRepository(db)

    def list_for_visit(self, visit_id: int) -> list[Billing]:
        return self.repository.list_for_visit(visit_id)

    def list_billings(self, **kwargs):
        return self.repository.list_billings(**kwargs)

    def get(self, billing_id: int) -> Billing:
        return self.repository.get_required_by_id(billing_id)

    def create_billing(self, payload: BillingCreateSchema) -> Billing:
        b = self.repository.create_billing(
            patient_id=payload.patient_id,
            visit_id=payload.visit_id,
            patient_insurance_id=payload.patient_insurance_id,
            notes=payload.notes,
        )
        for line in payload.items:
            self.repository.add_item(
                billing=b,
                service_name=line.service_name,
                service_code=line.service_code,
                quantity=Decimal(line.quantity),
                unit_price=Decimal(line.unit_price),
                discount_amount=Decimal(line.discount_amount),
                billable_service_id=line.billable_service_id,
                source_reference=line.source_reference,
            )
        self.db.commit()
        return self.repository.get_required_by_id(b.id)

    def add_item(self, billing_id: int, line: BillingItemCreateSchema) -> Billing:
        billing = self.repository.get_required_by_id(billing_id)
        if billing.status not in {str(BillingStatus.OPEN), str(BillingStatus.DRAFT)}:
            raise BadRequestError(
                message="Cannot add items to a billing that is not OPEN/DRAFT.",
                detail={"status": billing.status},
            )
        self.repository.add_item(
            billing=billing,
            service_name=line.service_name,
            service_code=line.service_code,
            quantity=Decimal(line.quantity),
            unit_price=Decimal(line.unit_price),
            discount_amount=Decimal(line.discount_amount),
            billable_service_id=line.billable_service_id,
            source_reference=line.source_reference,
        )
        self.db.commit()
        return self.repository.get_required_by_id(billing.id)

    # ============================================================
    # VISIT CHARGE SHEET (running billing) + PARTIAL PAYMENTS
    # ============================================================

    def _active_visit_billing(self, visit_id: int) -> Optional[Billing]:
        """
        Resolve the visit's charge sheet: prefer an OPEN/DRAFT billing, else the
        most recent non-cancelled one (e.g. already INVOICED/SETTLED).
        """
        billings = [
            b
            for b in self.repository.list_for_visit(visit_id)
            if not b.is_deleted and b.status != str(BillingStatus.CANCELLED)
        ]
        if not billings:
            return None
        for b in billings:
            if b.status in {str(BillingStatus.OPEN), str(BillingStatus.DRAFT)}:
                return b
        return sorted(billings, key=lambda b: b.id, reverse=True)[0]

    @staticmethod
    def _billing_paid_amount(billing: Billing) -> Decimal:
        total = Decimal("0")
        for p in billing.billing_payments or []:
            if not p.is_deleted and p.payment_status == PaymentStatus.SUCCESSFUL:
                total += Decimal(str(p.amount or 0))
        return total

    def get_visit_billing_summary(self, visit_id: int) -> dict:
        """
        A single view of everything billed for a visit: itemised charges, the
        running total, how much has already been paid (incremental payments),
        and the outstanding balance still to settle.
        """
        billing = self._active_visit_billing(visit_id)
        if billing is None:
            return {
                "visit_id": visit_id,
                "billing_id": None,
                "billing_no": None,
                "patient_id": None,
                "status": None,
                "currency": "NGN",
                "total_charges": Decimal("0.00"),
                "gross_amount": Decimal("0.00"),
                "discount_amount": Decimal("0.00"),
                "amount_paid": Decimal("0.00"),
                "outstanding": Decimal("0.00"),
                "unmapped_count": 0,
                "unaccounted_amount": Decimal("0.00"),
                "items": [],
                "payments": [],
                "invoice": None,
            }

        items = [i for i in (billing.items or []) if not i.is_deleted]
        # Enrich each charge line with the service category (from the billable
        # service catalog) so invoice/charge-line UIs can display it.
        for _it in items:
            try:
                _it.category = _it.billable_service.category if _it.billable_service else None
            except Exception:
                _it.category = None
        payments = [
            p
            for p in (billing.billing_payments or [])
            if not p.is_deleted and p.payment_status == PaymentStatus.SUCCESSFUL
        ]
        total = Decimal(str(billing.net_amount or 0))
        paid = self._billing_paid_amount(billing)
        outstanding = total - paid
        if outstanding < 0:
            outstanding = Decimal("0")

        # Reconciliation: charge lines with no ledger account are not postable
        # to finance. Surface them so cashiers/finance can resolve the mapping.
        unmapped = [i for i in items if not getattr(i, "account_code", None)]
        unmapped_count = len(unmapped)
        unaccounted_amount = sum(
            (Decimal(str(i.line_total or 0)) for i in unmapped), Decimal("0")
        )

        invoice = None
        for inv in (billing.invoices or []):
            if not inv.is_deleted:
                invoice = {
                    "id": inv.id,
                    "invoice_no": inv.invoice_no,
                    "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
                    "total_amount": Decimal(str(inv.total_amount or 0)),
                    "amount_paid": Decimal(str(inv.amount_paid or 0)),
                    "balance_due": Decimal(str(inv.balance_due or 0)),
                }
                break

        return {
            "visit_id": visit_id,
            "billing_id": billing.id,
            "billing_no": billing.billing_no,
            "patient_id": billing.patient_id,
            "status": billing.status,
            "currency": "NGN",
            "total_charges": total,
            "gross_amount": Decimal(str(billing.gross_amount or 0)),
            "discount_amount": Decimal(str(billing.discount_amount or 0)),
            "amount_paid": paid,
            "outstanding": outstanding,
            "unmapped_count": unmapped_count,
            "unaccounted_amount": unaccounted_amount,
            "items": items,
            "payments": payments,
            "invoice": invoice,
        }

    def _resolve_visit_card(self, billing: Billing, membership_card_id: int) -> MembershipCard:
        """
        Resolve and validate the membership card for a visit payment: it must
        exist and belong to the visit's patient.
        """
        card = (
            self.db.query(MembershipCard)
            .filter(
                MembershipCard.id == membership_card_id,
                MembershipCard.is_deleted.is_(False),
            )
            .first()
        )
        if card is None:
            raise NotFoundError(message="Membership card not found.")
        if card.patient_id != billing.patient_id:
            raise BadRequestError(message="This membership card does not belong to the patient.")
        return card

    def receive_visit_payment(
        self,
        visit_id: int,
        *,
        amount: Decimal,
        payment_method: Optional[str] = None,
        payment_reference: Optional[str] = None,
        received_by_staff_id: Optional[int] = None,
        membership_card_id: Optional[int] = None,
        note: Optional[str] = None,
        transaction_metadata: Optional[dict] = None,
        actor_user_id: Optional[int] = None,
    ) -> BillingPayment:
        """
        Record an incremental (partial) payment against the visit's charge sheet
        as services are rendered. Validates the amount against the outstanding
        balance so a visit can never be over-paid.

        When ``payment_method`` is ``MEMBERSHIP_CARD``, the patient's card is
        debited (after status + balance authorization) and the resulting card
        transaction is linked to this payment. The card debit itself sends the
        patient an emailed receipt + in-app notification and writes an audit
        event.
        """
        billing = self._active_visit_billing(visit_id)
        if billing is None or not [i for i in (billing.items or []) if not i.is_deleted]:
            raise BadRequestError(
                message="This visit has no charges to pay yet.",
                detail={"visit_id": visit_id},
            )

        amount = Decimal(str(amount))
        if amount <= 0:
            raise BadRequestError(message="Payment amount must be greater than zero.")

        outstanding = Decimal(str(billing.net_amount or 0)) - self._billing_paid_amount(billing)
        if amount > outstanding:
            raise BadRequestError(
                message="Payment exceeds the outstanding balance for this visit.",
                detail={"outstanding": str(outstanding), "amount": str(amount)},
            )

        method = (payment_method or "").strip().upper() or None
        metadata = dict(transaction_metadata or {})
        reference = payment_reference

        # ---- Membership-card settlement (deduct from card balance) ----
        if method == "MEMBERSHIP_CARD":
            if not membership_card_id:
                raise BadRequestError(
                    message="Select a membership card to pay from.",
                    detail={"field": "membership_card_id"},
                )
            card = self._resolve_visit_card(billing, membership_card_id)
            if card.status != MembershipCardStatus.ACTIVE:
                raise BadRequestError(
                    message=f"Membership card is {card.status.value if hasattr(card.status, 'value') else card.status} and cannot be used.",
                )

            purpose = summarize_purpose(
                [i.service_name for i in (billing.items or []) if not i.is_deleted]
            )
            facility_id = getattr(billing, "facility_id", None) or getattr(
                card, "issuing_facility_id", None
            ) or 1

            # Import here to avoid a circular import at module load.
            from app.services.membership_card_service import MembershipCardService

            card_service = MembershipCardService(self.db)
            card_tx = card_service.debit_card(
                card_id=card.id,
                payload=MembershipCardDebit(
                    amount=amount,
                    visit_id=visit_id,
                    narration=f"Visit {visit_id} charges — {purpose}",
                ),
                processed_by_id=(received_by_staff_id or actor_user_id or card.issued_by_id or 1),
                facility_id=facility_id,
                purpose=purpose,
                actor_user_id=actor_user_id,
            )
            reference = reference or card_tx.payment_reference or f"MCT-{card_tx.id}"
            metadata.update(
                {
                    "membership_card_id": card.id,
                    "membership_card_number": card.card_number,
                    "card_transaction_id": card_tx.id,
                    "card_balance_after": str(card_tx.balance_after),
                }
            )

        # Post the receipt to the matching cash/bank ledger account so every
        # monetary movement — not just charges — carries an account code.
        cash_acct = resolve_cash_account(self.db, payment_method=method)
        payment = BillingPayment(
            billing_id=billing.id,
            amount=amount,
            currency="NGN",
            payment_method=method,
            payment_status=PaymentStatus.SUCCESSFUL,
            payment_reference=(reference or f"VP-{_uuid.uuid4().hex[:12].upper()}"),
            paid_at=datetime.now(timezone.utc),
            received_by_staff_id=received_by_staff_id,
            note=note,
            transaction_metadata=metadata or None,
            account_code=cash_acct.code if cash_acct is not None else None,
            account_name=cash_acct.name if cash_acct is not None else None,
        )
        self.db.add(payment)
        self.db.flush()
        self.db.refresh(payment)

        # Audit the visit payment itself.
        try:
            record_security_event(
                self.db,
                user_id=actor_user_id,
                event_type="VISIT_PAYMENT_RECEIVED",
                severity="INFO",
                event_detail=(
                    f"Payment {payment.payment_reference} of {amount:,.2f} received "
                    f"against visit {visit_id} via {method or 'UNSPECIFIED'}."
                ),
                event_metadata={
                    "visit_id": visit_id,
                    "billing_id": billing.id,
                    "billing_payment_id": payment.id,
                    "amount": str(amount),
                    "method": method,
                    "membership_card_id": metadata.get("membership_card_id"),
                },
            )
        except Exception:
            pass

        self.db.commit()
        self.db.refresh(payment)

        # Payment confirmation receipt (email + in-app) for cash/POS/transfer/
        # etc. Membership-card debits already sent a richer receipt (with the
        # remaining card balance) via debit_card, so they're skipped here.
        if method != "MEMBERSHIP_CARD":
            try:
                from app.utils.payment_receipt import send_payment_receipt

                receipt_purpose = summarize_purpose(
                    [i.service_name for i in (billing.items or []) if not i.is_deleted]
                )
                send_payment_receipt(
                    self.db,
                    patient_id=billing.patient_id,
                    amount=amount,
                    purpose=receipt_purpose,
                    method=method,
                    reference=payment.payment_reference,
                    paid_at=payment.paid_at,
                    actor_user_id=actor_user_id,
                )
            except Exception:
                pass

        return payment

    def cancel_billing(self, billing_id: int, *, reason: Optional[str] = None) -> Billing:
        billing = self.repository.get_required_by_id(billing_id)
        if billing.status in {str(BillingStatus.SETTLED), str(BillingStatus.INVOICED)}:
            raise BadRequestError(
                message="Cannot cancel an invoiced/settled billing.",
                detail={"status": billing.status},
            )
        billing.status = str(BillingStatus.CANCELLED)
        if reason:
            existing = billing.notes or ""
            billing.notes = (existing + ("\n\n" if existing else "") + f"[CANCELLED] {reason}").strip()
        self.repository.save(billing)
        self.db.commit()
        return self.repository.get_required_by_id(billing.id)

    # ============================================================
    # RECORD SERVICES RENDERED (Patient Queue / SDP capture)
    # ============================================================

    def record_visit_services(
        self,
        visit_id: int,
        items: list,
        *,
        service_delivery_point_id: Optional[int] = None,
        rendered_by_user_id: Optional[int] = None,
    ) -> dict:
        """Record one or more services rendered for a visit — typically captured
        from the Patient Queue at the current service delivery point — onto the
        visit's running charge sheet (creating it if none exists). Each line is
        stamped with the SDP and the recording user for provenance. Returns the
        refreshed visit billing summary plus the number of lines added.

        ``items``: list of objects/dicts with ``billable_service_id`` (optional),
        ``service_name`` (optional when a billable service is given),
        ``service_code``, ``quantity`` (default 1), ``unit_price`` (defaults to
        the billable service's price), ``discount_amount`` (default 0)."""
        from app.models.all_models import BillableService, Visit

        if not items:
            raise BadRequestError(message="No services were provided to record.")

        visit = (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )
        if visit is None:
            raise NotFoundError(message="Visit not found.")

        billing = self._active_visit_billing(visit_id)
        if billing is None:
            billing = self.repository.create_billing(
                patient_id=visit.patient_id, visit_id=visit_id,
                patient_insurance_id=None, notes="Charge sheet opened from the patient queue.",
            )
        elif billing.status not in {str(BillingStatus.OPEN), str(BillingStatus.DRAFT)}:
            # The visit already has a finalised bill; open a fresh charge sheet
            # rather than mutating an invoiced/settled one.
            billing = self.repository.create_billing(
                patient_id=visit.patient_id, visit_id=visit_id,
                patient_insurance_id=None,
                notes="Additional charge sheet opened from the patient queue.",
            )

        added = []
        for raw in items:
            get = (raw.get if isinstance(raw, dict) else lambda k, d=None: getattr(raw, k, d))
            bs_id = get("billable_service_id")
            service_name = (get("service_name") or "").strip() if get("service_name") else None
            service_code = get("service_code")
            unit_price = get("unit_price")
            quantity = get("quantity") or 1
            discount = get("discount_amount") or 0

            svc = None
            if bs_id is not None:
                svc = (
                    self.db.query(BillableService)
                    .filter(BillableService.id == bs_id,
                            BillableService.is_deleted.is_(False))
                    .first()
                )
                if svc is None:
                    raise BadRequestError(
                        message="A selected service could not be found.",
                        detail={"billable_service_id": bs_id})
                if not service_name:
                    service_name = svc.name
                if service_code is None:
                    service_code = svc.code
                if unit_price is None:
                    unit_price = svc.default_price

            if not service_name:
                raise BadRequestError(
                    message="Each recorded service needs a name or a selected "
                            "billable service.")
            if unit_price is None:
                unit_price = 0

            item = self.repository.add_item(
                billing=billing,
                service_name=service_name,
                service_code=service_code,
                quantity=Decimal(str(quantity)),
                unit_price=Decimal(str(unit_price)),
                discount_amount=Decimal(str(discount)),
                billable_service_id=bs_id,
                source_reference=(f"QUEUE-SDP-{service_delivery_point_id}"
                                  if service_delivery_point_id else "QUEUE"),
                service_delivery_point_id=service_delivery_point_id,
                rendered_by_user_id=rendered_by_user_id,
            )
            added.append(item)

        self.db.commit()

        try:
            from app.utils.security_event_util import record_security_event
            record_security_event(
                self.db, user_id=rendered_by_user_id,
                event_type="VISIT_SERVICES_RECORDED", severity="INFO",
                event_detail=f"{len(added)} service(s) recorded for visit {visit_id} "
                             f"at SDP {service_delivery_point_id}.",
                event_metadata={"visit_id": visit_id,
                                "service_delivery_point_id": service_delivery_point_id,
                                "count": len(added)},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()

        summary = self.get_visit_billing_summary(visit_id)
        return {"recorded": len(added), "billing_summary": summary}
