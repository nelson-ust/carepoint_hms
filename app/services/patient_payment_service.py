"""
Unified patient-payment dispatcher.

Patients pay their bills against an :class:`Invoice`. The service exposed
here is the single entry point for that flow, regardless of how the
patient chose to pay:

* ``CASHIER``         — cash / POS / card-at-counter; the cashier records the
                        payment manually.
* ``MEMBERSHIP_CARD`` — debit the patient's prepaid membership-card balance.
* ``LOYALTY``         — redeem loyalty points (converted to currency via
                        the loyalty program's ``points_per_currency_unit``).
* ``GATEWAY``         — initiate an online payment using the tenant's
                        configured online payment provider
                        (Paystack / Flutterwave / Stripe / …).
* ``BANK_TRANSFER``   — record a manual offline transfer for reconciliation.

The dispatcher always:

1. Validates that the invoice has an outstanding balance,
2. Validates that the chosen channel is configured + active for the
   tenant (via :class:`TenantPaymentMethodConfig`),
3. Performs the channel-specific debit/credit/initiate action,
4. Persists a :class:`Payment` row in the tenant DB,
5. Updates ``Invoice.amount_paid`` and ``Invoice.balance_due``,
6. Marks the invoice ``PAID`` once the balance reaches zero.

Online (GATEWAY) payments return a redirect/authorization URL and a
provider reference; the actual money movement is finalised later by the
provider's webhook (or the tenant's verify endpoint).
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    LoyaltyTransactionType,
    MembershipCardStatus,
    MembershipCardTransactionType,
    PaymentChannel,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    SyncJournalOp,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    Invoice,
    LoyaltyTransaction,
    MembershipCard,
    MembershipCardTransaction,
    Patient,
    PatientLoyalty,
    Payment,
    TenantPaymentMethodConfig,
)
from app.services.tenant_payment_method_service import TenantPaymentMethodService


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _generate_reference(prefix: str) -> str:
    return f"{prefix}-{datetime.utcnow():%Y%m%d%H%M%S}-{secrets.token_hex(4).upper()}"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class PatientPaymentService:
    """
    Tenant-DB service that ties patient payment intent → invoice settlement.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.config_service = TenantPaymentMethodService(db)

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_available_methods(self) -> list[dict[str, Any]]:
        """
        Return a sanitized list of accepted payment methods for the
        current tenant. Credentials are NEVER included.
        """
        configs = self.config_service.list_configs(
            only_active=True, accepts_patient_payments=True
        )
        return [
            {
                "id": c.id,
                "channel": c.channel.value,
                "provider": c.provider.value,
                "display_name": c.display_name,
                "description": c.description,
                "currency": c.currency,
                "minimum_amount": float(c.minimum_amount) if c.minimum_amount is not None else None,
                "maximum_amount": float(c.maximum_amount) if c.maximum_amount is not None else None,
                "fee_percent": float(c.fee_percent or 0),
                "fee_flat": float(c.fee_flat or 0),
                "fee_borne_by_patient": c.fee_borne_by_patient,
                "is_default": c.is_default,
            }
            for c in configs
        ]

    # ------------------------------------------------------------------
    # MAIN ENTRY POINT
    # ------------------------------------------------------------------

    def pay_invoice(
        self,
        *,
        invoice_id: int,
        amount: Decimal | float,
        channel: PaymentChannel,
        patient_id: Optional[int] = None,
        provider: Optional[PaymentProvider] = None,
        config_id: Optional[int] = None,
        cashier_staff_id: Optional[int] = None,
        callback_url: Optional[str] = None,
        external_reference: Optional[str] = None,
        note: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Settle (or partially settle) ``invoice_id`` using ``channel``.

        Returns a dict with keys ``payment``, ``invoice``, ``status``,
        and — for GATEWAY — ``authorization_url`` and ``provider_reference``.
        """
        invoice = self._get_open_invoice(invoice_id)
        amount_dec = _decimal(amount)
        if amount_dec <= 0:
            raise BadRequestError(message="Payment amount must be greater than zero.")
        if amount_dec > invoice.balance_due:
            raise BadRequestError(
                message="Payment amount exceeds the invoice balance due.",
                detail={
                    "amount": float(amount_dec),
                    "balance_due": float(invoice.balance_due),
                },
            )

        config = self._resolve_config(channel=channel, provider=provider, config_id=config_id)
        self._enforce_amount_limits(config, amount_dec)

        # Channel-specific dispatch.
        if channel == PaymentChannel.CASHIER:
            return self._pay_via_cashier(
                invoice=invoice,
                amount=amount_dec,
                config=config,
                cashier_staff_id=cashier_staff_id,
                external_reference=external_reference,
                note=note,
                metadata=metadata,
            )
        if channel == PaymentChannel.MEMBERSHIP_CARD:
            return self._pay_via_membership_card(
                invoice=invoice,
                amount=amount_dec,
                config=config,
                patient_id=patient_id,
                cashier_staff_id=cashier_staff_id,
                note=note,
                metadata=metadata,
            )
        if channel == PaymentChannel.LOYALTY:
            return self._pay_via_loyalty(
                invoice=invoice,
                amount=amount_dec,
                config=config,
                patient_id=patient_id,
                note=note,
                metadata=metadata,
            )
        if channel == PaymentChannel.BANK_TRANSFER:
            return self._pay_via_bank_transfer(
                invoice=invoice,
                amount=amount_dec,
                config=config,
                external_reference=external_reference,
                cashier_staff_id=cashier_staff_id,
                note=note,
                metadata=metadata,
            )
        if channel == PaymentChannel.GATEWAY:
            return self._initiate_gateway_payment(
                invoice=invoice,
                amount=amount_dec,
                config=config,
                callback_url=callback_url,
                metadata=metadata,
            )

        raise BadRequestError(message=f"Unsupported payment channel: {channel}")

    # ------------------------------------------------------------------
    # Channel handlers
    # ------------------------------------------------------------------

    def _pay_via_cashier(
        self,
        *,
        invoice: Invoice,
        amount: Decimal,
        config: TenantPaymentMethodConfig,
        cashier_staff_id: Optional[int],
        external_reference: Optional[str],
        note: Optional[str],
        metadata: Optional[dict],
    ) -> dict[str, Any]:
        payment = self._record_payment(
            invoice=invoice,
            amount=amount,
            currency=config.currency,
            method=PaymentMethod.CASH,
            status=PaymentStatus.SUCCESSFUL,
            reference=external_reference or _generate_reference("CSH"),
            cashier_staff_id=cashier_staff_id,
            metadata=metadata,
            note=note or "Payment received at cashier point",
            paid_now=True,
        )
        self._apply_payment_to_invoice(invoice, amount)
        self._mark_config_used(config)
        self.db.commit()
        return {"status": "ok", "payment": payment, "invoice": invoice}

    def _pay_via_bank_transfer(
        self,
        *,
        invoice: Invoice,
        amount: Decimal,
        config: TenantPaymentMethodConfig,
        external_reference: Optional[str],
        cashier_staff_id: Optional[int],
        note: Optional[str],
        metadata: Optional[dict],
    ) -> dict[str, Any]:
        if not external_reference:
            raise BadRequestError(message="A bank-transfer reference is required.")
        payment = self._record_payment(
            invoice=invoice,
            amount=amount,
            currency=config.currency,
            method=PaymentMethod.BANK_TRANSFER,
            status=PaymentStatus.SUCCESSFUL,
            reference=external_reference,
            cashier_staff_id=cashier_staff_id,
            metadata=metadata,
            note=note or "Bank transfer reconciliation",
            paid_now=True,
        )
        self._apply_payment_to_invoice(invoice, amount)
        self._mark_config_used(config)
        self.db.commit()
        return {"status": "ok", "payment": payment, "invoice": invoice}

    def _pay_via_membership_card(
        self,
        *,
        invoice: Invoice,
        amount: Decimal,
        config: TenantPaymentMethodConfig,
        patient_id: Optional[int],
        cashier_staff_id: Optional[int],
        note: Optional[str],
        metadata: Optional[dict],
    ) -> dict[str, Any]:
        target_patient_id = patient_id or invoice.patient_id
        card = (
            self.db.query(MembershipCard)
            .filter(
                MembershipCard.patient_id == target_patient_id,
                MembershipCard.is_deleted.is_(False),
                MembershipCard.status == MembershipCardStatus.ACTIVE,
            )
            .order_by(MembershipCard.id.desc())
            .first()
        )
        if card is None:
            raise NotFoundError(message="Patient has no active membership card.")
        balance = _decimal(card.balance or 0)
        if balance < amount:
            raise BadRequestError(
                message="Insufficient membership-card balance.",
                detail={
                    "balance": float(balance),
                    "requested": float(amount),
                },
            )

        new_balance = balance - amount
        reference = _generate_reference("MBC")

        payment = self._record_payment(
            invoice=invoice,
            amount=amount,
            currency=config.currency,
            method=PaymentMethod.MEMBERSHIP_CARD,
            status=PaymentStatus.SUCCESSFUL,
            reference=reference,
            cashier_staff_id=cashier_staff_id,
            metadata={**(metadata or {}), "card_number": card.card_number},
            note=note or "Membership-card debit",
            paid_now=True,
        )

        # Persist the card transaction.
        tx = MembershipCardTransaction(
            membership_card_id=card.id,
            patient_id=target_patient_id,
            facility_id=invoice.facility_id,
            processed_by_id=cashier_staff_id,
            invoice_id=invoice.id,
            visit_id=invoice.visit_id,
            payment_id=payment.id,
            amount=amount,
            transaction_type=getattr(MembershipCardTransactionType, "DEBIT", MembershipCardTransactionType.PAYMENT)
            if hasattr(MembershipCardTransactionType, "DEBIT")
            else MembershipCardTransactionType.PAYMENT,
            payment_source="MEMBERSHIP_CARD",
            payment_reference=reference,
            balance_before=balance,
            balance_after=new_balance,
            narration=f"Settlement against invoice {invoice.invoice_no}",
            transaction_date=datetime.now(timezone.utc),
        )
        card.balance = new_balance
        self.db.add(tx)

        self._apply_payment_to_invoice(invoice, amount)
        self._mark_config_used(config)
        self.db.commit()
        return {"status": "ok", "payment": payment, "invoice": invoice, "card_balance_after": float(new_balance)}

    def _pay_via_loyalty(
        self,
        *,
        invoice: Invoice,
        amount: Decimal,
        config: TenantPaymentMethodConfig,
        patient_id: Optional[int],
        note: Optional[str],
        metadata: Optional[dict],
    ) -> dict[str, Any]:
        target_patient_id = patient_id or invoice.patient_id

        loyalty = (
            self.db.query(PatientLoyalty)
            .filter(
                PatientLoyalty.patient_id == target_patient_id,
                PatientLoyalty.is_deleted.is_(False),
            )
            .order_by(PatientLoyalty.id.desc())
            .first()
        )
        if loyalty is None:
            raise NotFoundError(message="Patient is not enrolled in any loyalty program.")

        program = loyalty.loyalty_program
        rate = _decimal(getattr(program, "points_per_currency_unit", None) or 1)
        if rate <= 0:
            raise BadRequestError(message="Loyalty program rate is not configured.")

        points_needed = (amount * rate).quantize(Decimal("0.01"))
        if (loyalty.points_balance or Decimal("0")) < points_needed:
            raise BadRequestError(
                message="Insufficient loyalty points.",
                detail={
                    "points_balance": float(loyalty.points_balance or 0),
                    "points_required": float(points_needed),
                    "rate_points_per_currency_unit": float(rate),
                },
            )
        min_redeem = _decimal(getattr(program, "minimum_redemption_points", None) or 0)
        if points_needed < min_redeem:
            raise BadRequestError(
                message=f"Minimum redemption is {float(min_redeem)} points.",
            )

        reference = _generate_reference("LOY")

        payment = self._record_payment(
            invoice=invoice,
            amount=amount,
            currency=config.currency,
            method=PaymentMethod.LOYALTY,
            status=PaymentStatus.SUCCESSFUL,
            reference=reference,
            cashier_staff_id=None,
            metadata={
                **(metadata or {}),
                "points_redeemed": float(points_needed),
                "rate": float(rate),
            },
            note=note or "Loyalty points redemption",
            paid_now=True,
        )

        loyalty.points_balance = (loyalty.points_balance or Decimal("0")) - points_needed
        self.db.add(
            LoyaltyTransaction(
                patient_loyalty_id=loyalty.id,
                invoice_id=invoice.id,
                transaction_type=LoyaltyTransactionType.REDEEM,
                points=points_needed,
                description=f"Redeemed against invoice {invoice.invoice_no}",
                transaction_date=datetime.now(timezone.utc),
            )
        )

        self._apply_payment_to_invoice(invoice, amount)
        self._mark_config_used(config)
        self.db.commit()
        return {
            "status": "ok",
            "payment": payment,
            "invoice": invoice,
            "points_redeemed": float(points_needed),
            "points_balance_after": float(loyalty.points_balance or 0),
        }

    def _initiate_gateway_payment(
        self,
        *,
        invoice: Invoice,
        amount: Decimal,
        config: TenantPaymentMethodConfig,
        callback_url: Optional[str],
        metadata: Optional[dict],
    ) -> dict[str, Any]:
        """
        Create a PENDING Payment and ask the configured provider to start
        the transaction. Webhook / verify endpoints will mark it
        SUCCESSFUL once the provider confirms the charge.
        """
        creds = self.config_service.get_decrypted_credentials(config)
        if not creds.get("secret_key"):
            raise BadRequestError(
                message="Gateway is not fully configured (missing secret_key).",
                detail={"provider": config.provider.value},
            )

        reference = _generate_reference("GW")
        payment = self._record_payment(
            invoice=invoice,
            amount=amount,
            currency=config.currency,
            method=self._method_for_provider(config.provider),
            status=PaymentStatus.PENDING,
            reference=reference,
            cashier_staff_id=None,
            metadata={
                **(metadata or {}),
                "provider": config.provider.value,
                "config_id": config.id,
            },
            note=f"Gateway-initiated payment via {config.provider.value}",
            paid_now=False,
        )

        # Best-effort gateway initiation. We delegate to a provider
        # adapter when available; otherwise we return enough information
        # for the caller to drive the provider directly.
        provider_response = self._call_provider_initiate(
            config=config,
            credentials=creds,
            invoice=invoice,
            amount=amount,
            reference=reference,
            callback_url=callback_url or config.callback_url,
        )

        if provider_response.get("authorization_url"):
            payment.transaction_metadata = {
                **(payment.transaction_metadata or {}),
                "authorization_url": provider_response["authorization_url"],
                "provider_reference": provider_response.get("provider_reference"),
            }
            self.db.commit()

        self._mark_config_used(config)

        return {
            "status": "pending",
            "payment": payment,
            "invoice": invoice,
            "authorization_url": provider_response.get("authorization_url"),
            "provider_reference": provider_response.get("provider_reference") or reference,
            "provider": config.provider.value,
        }

    # ------------------------------------------------------------------
    # Gateway adapter dispatch
    # ------------------------------------------------------------------

    def _method_for_provider(self, provider: PaymentProvider) -> PaymentMethod:
        if provider == PaymentProvider.PAYSTACK:
            return PaymentMethod.PAYSTACK
        if provider == PaymentProvider.FLUTTERWAVE:
            return PaymentMethod.FLUTTERWAVE
        if provider == PaymentProvider.STRIPE:
            return PaymentMethod.STRIPE
        return PaymentMethod.OTHER

    def _call_provider_initiate(
        self,
        *,
        config: TenantPaymentMethodConfig,
        credentials: dict[str, str],
        invoice: Invoice,
        amount: Decimal,
        reference: str,
        callback_url: Optional[str],
    ) -> dict[str, Any]:
        """
        Best-effort gateway-initiate dispatch.

        We try to use an existing provider adapter (e.g. the bundled
        Paystack adapter) when configured; otherwise we return the
        bare reference so the caller can drive the gateway with their own
        client. Failures degrade to PENDING-with-no-URL rather than
        crashing the patient flow.
        """
        try:
            if config.provider == PaymentProvider.PAYSTACK:
                from app.services.paystack_service import PaystackService  # type: ignore

                # The bundled adapter targets a global PAYSTACK_SECRET_KEY;
                # we override with the tenant secret when it differs from
                # the platform default.
                svc = PaystackService()
                if hasattr(svc, "secret_key"):
                    svc.secret_key = credentials.get("secret_key", svc.secret_key)
                # Most adapter implementations expose initialize_transaction(...)
                init = getattr(svc, "initialize_transaction", None)
                if callable(init):
                    raw = init(
                        amount=int(_decimal(amount) * 100),  # kobo
                        email=getattr(invoice.patient, "email", None) or "no-email@invoice.local",
                        reference=reference,
                        callback_url=callback_url,
                    )
                    return {
                        "authorization_url": (raw or {}).get("authorization_url"),
                        "provider_reference": (raw or {}).get("reference") or reference,
                    }
        except Exception as exc:
            logger.warning(
                "Gateway initiate failed for provider=%s: %s",
                getattr(config.provider, "value", config.provider),
                exc,
            )

        # Generic fallback: surface a synthetic reference and let the
        # caller render their own redirect.
        return {"authorization_url": None, "provider_reference": reference}

    # ------------------------------------------------------------------
    # Webhook / verify hook
    # ------------------------------------------------------------------

    def confirm_gateway_payment(
        self,
        *,
        payment_reference: str,
        succeeded: bool,
        provider_payload: Optional[dict] = None,
    ) -> Payment:
        """
        Called from a webhook or polling/verify endpoint.

        Marks the corresponding Payment row SUCCESSFUL or FAILED, and
        applies the payment to the invoice on success.
        """
        payment = (
            self.db.query(Payment)
            .filter(Payment.payment_reference == payment_reference)
            .first()
        )
        if payment is None:
            raise NotFoundError(message="Unknown payment reference.")

        if succeeded:
            if payment.payment_status == PaymentStatus.SUCCESSFUL:
                # Idempotent: already settled.
                return payment
            payment.payment_status = PaymentStatus.SUCCESSFUL
            payment.paid_at = datetime.now(timezone.utc)
            payment.transaction_metadata = {
                **(payment.transaction_metadata or {}),
                "provider_payload": provider_payload or {},
            }
            invoice = self._get_open_invoice(payment.invoice_id)
            self._apply_payment_to_invoice(invoice, _decimal(payment.amount))
        else:
            payment.payment_status = PaymentStatus.FAILED
            payment.transaction_metadata = {
                **(payment.transaction_metadata or {}),
                "provider_payload": provider_payload or {},
            }

        self.db.commit()
        self.db.refresh(payment)
        return payment

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_config(
        self,
        *,
        channel: PaymentChannel,
        provider: Optional[PaymentProvider],
        config_id: Optional[int],
    ) -> TenantPaymentMethodConfig:
        if config_id is not None:
            cfg = self.config_service.get(config_id)
            if cfg.channel != channel:
                raise BadRequestError(
                    message="Selected payment-method config does not match the requested channel.",
                )
            if not cfg.is_active or not cfg.accepts_patient_payments:
                raise BadRequestError(message="The selected payment method is not active for patient payments.")
            return cfg

        configs = self.config_service.list_configs(
            only_active=True,
            channel=channel,
            accepts_patient_payments=True,
        )
        if provider is not None:
            configs = [c for c in configs if c.provider == provider]
        if not configs:
            raise BadRequestError(
                message=(
                    f"No active payment method is configured for channel "
                    f"{channel.value}. Ask your administrator to enable one."
                ),
            )
        # Prefer the row marked is_default.
        configs.sort(key=lambda c: (not c.is_default, c.id))
        return configs[0]

    def _enforce_amount_limits(
        self, config: TenantPaymentMethodConfig, amount: Decimal
    ) -> None:
        if config.minimum_amount is not None and amount < _decimal(config.minimum_amount):
            raise BadRequestError(
                message=f"Amount is below the configured minimum ({float(config.minimum_amount)})."
            )
        if config.maximum_amount is not None and amount > _decimal(config.maximum_amount):
            raise BadRequestError(
                message=f"Amount exceeds the configured maximum ({float(config.maximum_amount)})."
            )

    def _get_open_invoice(self, invoice_id: int) -> Invoice:
        rec = (
            self.db.query(Invoice)
            .filter(Invoice.id == invoice_id, Invoice.is_deleted.is_(False))
            .first()
        )
        if rec is None:
            raise NotFoundError(message="Invoice not found.")
        if (rec.balance_due or Decimal("0")) <= Decimal("0"):
            raise BadRequestError(message="Invoice has no outstanding balance.")
        return rec

    def _record_payment(
        self,
        *,
        invoice: Invoice,
        amount: Decimal,
        currency: str,
        method: PaymentMethod,
        status: PaymentStatus,
        reference: str,
        cashier_staff_id: Optional[int],
        metadata: Optional[dict],
        note: Optional[str],
        paid_now: bool,
    ) -> Payment:
        payment = Payment(
            invoice_id=invoice.id,
            received_by_staff_id=cashier_staff_id,
            payment_reference=reference,
            payment_method=method.value,
            payment_status=status,
            amount=amount,
            currency=currency,
            paid_at=datetime.now(timezone.utc) if paid_now else None,
            transaction_metadata=metadata or {},
            note=note,
        )
        self.db.add(payment)
        self.db.flush()

        # Append to the cloud↔edge sync journal so this payment is
        # preserved across the next reconciliation, regardless of which
        # side authored it. EVENT op = append-only on both sides.
        try:
            from app.services.sync_journal_service import SyncJournalService

            SyncJournalService(self.db).record_change(
                entity_type="payment",
                op=SyncJournalOp.EVENT,
                entity_id=payment.id,
                client_uuid=reference,
                payload={
                    "invoice_id": invoice.id,
                    "amount": float(amount),
                    "currency": currency,
                    "method": method.value,
                    "status": str(getattr(status, "value", status)),
                    "reference": reference,
                    "metadata": metadata or {},
                },
            )
        except Exception:
            # Sync journaling is best-effort; never block a real payment.
            pass

        return payment

    def _apply_payment_to_invoice(self, invoice: Invoice, amount: Decimal) -> None:
        invoice.amount_paid = (invoice.amount_paid or Decimal("0")) + amount
        invoice.balance_due = max(
            Decimal("0"),
            (invoice.total_amount or Decimal("0")) - invoice.amount_paid,
        )
        if invoice.balance_due <= Decimal("0"):
            try:
                from app.core.enums import InvoiceStatus  # local import to avoid cycles

                invoice.status = InvoiceStatus.PAID
            except Exception:
                pass

    def _mark_config_used(self, config: TenantPaymentMethodConfig) -> None:
        config.last_used_at = datetime.now(timezone.utc)
