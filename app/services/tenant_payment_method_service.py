"""
Per-tenant payment-method configuration.

Each tenant configures which channels they accept (cashier, membership
card, loyalty, online gateway, bank transfer, insurance) and how each
gateway-style channel is wired up (provider, encrypted credentials,
fees, currency caps).

Credentials never travel through the database in plaintext. The service
encrypts them on the way in via :func:`app.core.cryptography.encrypt_string`
and decrypts them on demand for callers that need to issue a request to
the provider (e.g. the gateway adapter).

Operates on the **tenant** database — configurations are scoped to the
tenant whose context the request is running in.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.cryptography import decrypt_string, encrypt_string
from app.core.enums import PaymentChannel, PaymentProvider
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import TenantPaymentMethodConfig


logger = logging.getLogger(__name__)


# Required credential keys per provider. Used at "test" time to surface
# misconfiguration before a patient tries to pay.
PROVIDER_REQUIRED_CREDENTIALS: dict[PaymentProvider, tuple[str, ...]] = {
    PaymentProvider.PAYSTACK: ("secret_key",),
    PaymentProvider.FLUTTERWAVE: ("secret_key",),
    PaymentProvider.STRIPE: ("secret_key",),
    PaymentProvider.MONNIFY: ("secret_key", "api_token"),
    PaymentProvider.REMITA: ("secret_key", "merchant_id"),
    PaymentProvider.MANUAL: tuple(),
}


# Map credential field names → encrypted column names on the model.
_CRED_FIELDS = {
    "secret_key": "secret_key_encrypted",
    "public_key": "public_key_encrypted",
    "webhook_secret": "webhook_secret_encrypted",
    "api_token": "api_token_encrypted",
    "merchant_id": "merchant_id_encrypted",
}


class TenantPaymentMethodService:
    """
    CRUD service for :class:`TenantPaymentMethodConfig`.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def list_configs(
        self,
        *,
        only_active: bool = False,
        channel: Optional[PaymentChannel] = None,
        accepts_patient_payments: Optional[bool] = None,
    ) -> list[TenantPaymentMethodConfig]:
        q = self.db.query(TenantPaymentMethodConfig).filter(
            TenantPaymentMethodConfig.is_deleted.is_(False)
        )
        if only_active:
            q = q.filter(TenantPaymentMethodConfig.is_active.is_(True))
        if channel is not None:
            q = q.filter(TenantPaymentMethodConfig.channel == channel)
        if accepts_patient_payments is not None:
            q = q.filter(
                TenantPaymentMethodConfig.accepts_patient_payments.is_(accepts_patient_payments)
            )
        return q.order_by(
            TenantPaymentMethodConfig.is_default.desc(),
            TenantPaymentMethodConfig.id.asc(),
        ).all()

    def get(self, config_id: int) -> TenantPaymentMethodConfig:
        rec = (
            self.db.query(TenantPaymentMethodConfig)
            .filter(
                TenantPaymentMethodConfig.id == config_id,
                TenantPaymentMethodConfig.is_deleted.is_(False),
            )
            .first()
        )
        if rec is None:
            raise NotFoundError(message="Payment-method configuration not found.")
        return rec

    def get_default_for_channel(
        self, channel: PaymentChannel
    ) -> Optional[TenantPaymentMethodConfig]:
        """
        Resolve the active config the dispatcher should use for ``channel``.

        Preference order:
          1. is_default = True
          2. first active row by id
        """
        rows = (
            self.db.query(TenantPaymentMethodConfig)
            .filter(
                TenantPaymentMethodConfig.channel == channel,
                TenantPaymentMethodConfig.is_active.is_(True),
                TenantPaymentMethodConfig.is_deleted.is_(False),
            )
            .order_by(
                TenantPaymentMethodConfig.is_default.desc(),
                TenantPaymentMethodConfig.id.asc(),
            )
            .all()
        )
        return rows[0] if rows else None

    def get_decrypted_credentials(self, config: TenantPaymentMethodConfig) -> dict[str, str]:
        """
        Return a plaintext dict of credentials for the gateway adapter.

        Callers MUST treat the returned dict as in-memory only and never
        log it. For convenience, missing or empty fields are omitted from
        the result.
        """
        out: dict[str, str] = {}
        for plain, encrypted_attr in _CRED_FIELDS.items():
            cipher = getattr(config, encrypted_attr, None)
            if not cipher:
                continue
            try:
                out[plain] = decrypt_string(cipher)
            except Exception as exc:
                logger.exception("Could not decrypt %s for config %s: %s", plain, config.id, exc)
        return out

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        channel: PaymentChannel,
        provider: PaymentProvider = PaymentProvider.MANUAL,
        display_name: str,
        description: Optional[str] = None,
        currency: str = "NGN",
        is_active: bool = True,
        is_default: bool = False,
        accepts_patient_payments: bool = True,
        accepts_subscription_payments: bool = False,
        minimum_amount: Optional[float] = None,
        maximum_amount: Optional[float] = None,
        fee_percent: float = 0.0,
        fee_flat: float = 0.0,
        fee_borne_by_patient: bool = False,
        api_base_url: Optional[str] = None,
        callback_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        metadata_json: Optional[dict[str, Any]] = None,
        sandbox_mode: bool = False,
        credentials: Optional[dict[str, str]] = None,
    ) -> TenantPaymentMethodConfig:
        """
        Create a new payment-method configuration.

        ``credentials`` is a plaintext mapping such as
        ``{"secret_key": "sk_test_..."}``; the service encrypts them
        before persisting.
        """
        self._validate_provider_for_channel(channel, provider)
        self._validate_credentials(provider, credentials)

        rec = TenantPaymentMethodConfig(
            channel=channel,
            provider=provider,
            display_name=display_name.strip(),
            description=description,
            currency=str(currency or "NGN").upper(),
            is_active=bool(is_active),
            is_default=bool(is_default),
            accepts_patient_payments=bool(accepts_patient_payments),
            accepts_subscription_payments=bool(accepts_subscription_payments),
            minimum_amount=Decimal(str(minimum_amount)) if minimum_amount is not None else None,
            maximum_amount=Decimal(str(maximum_amount)) if maximum_amount is not None else None,
            fee_percent=Decimal(str(fee_percent or 0)),
            fee_flat=Decimal(str(fee_flat or 0)),
            fee_borne_by_patient=bool(fee_borne_by_patient),
            api_base_url=api_base_url,
            callback_url=callback_url,
            webhook_url=webhook_url,
            metadata_json=metadata_json,
            sandbox_mode=bool(sandbox_mode),
        )
        self._apply_credentials(rec, credentials)
        self.db.add(rec)
        self.db.flush()

        if rec.is_default:
            self._enforce_single_default(rec)

        self.db.commit()
        self.db.refresh(rec)
        return rec

    def update(
        self,
        config_id: int,
        *,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        currency: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_default: Optional[bool] = None,
        accepts_patient_payments: Optional[bool] = None,
        accepts_subscription_payments: Optional[bool] = None,
        minimum_amount: Optional[float] = None,
        maximum_amount: Optional[float] = None,
        fee_percent: Optional[float] = None,
        fee_flat: Optional[float] = None,
        fee_borne_by_patient: Optional[bool] = None,
        api_base_url: Optional[str] = None,
        callback_url: Optional[str] = None,
        webhook_url: Optional[str] = None,
        metadata_json: Optional[dict[str, Any]] = None,
        sandbox_mode: Optional[bool] = None,
        credentials: Optional[dict[str, str]] = None,
    ) -> TenantPaymentMethodConfig:
        rec = self.get(config_id)

        for field, value in (
            ("display_name", display_name.strip() if display_name is not None else None),
            ("description", description),
            ("currency", str(currency).upper() if currency else None),
            ("is_active", is_active),
            ("accepts_patient_payments", accepts_patient_payments),
            ("accepts_subscription_payments", accepts_subscription_payments),
            ("fee_borne_by_patient", fee_borne_by_patient),
            ("api_base_url", api_base_url),
            ("callback_url", callback_url),
            ("webhook_url", webhook_url),
            ("metadata_json", metadata_json),
            ("sandbox_mode", sandbox_mode),
        ):
            if value is not None:
                setattr(rec, field, value)

        for field, value in (
            ("minimum_amount", minimum_amount),
            ("maximum_amount", maximum_amount),
            ("fee_percent", fee_percent),
            ("fee_flat", fee_flat),
        ):
            if value is not None:
                setattr(rec, field, Decimal(str(value)))

        if credentials:
            self._apply_credentials(rec, credentials)

        if is_default is True:
            rec.is_default = True
            self._enforce_single_default(rec)
        elif is_default is False:
            rec.is_default = False

        self.db.commit()
        self.db.refresh(rec)
        return rec

    def delete(self, config_id: int) -> None:
        rec = self.get(config_id)
        rec.soft_delete()
        rec.is_active = False
        self.db.commit()

    def test_config(self, config_id: int) -> dict[str, Any]:
        """
        Lightweight self-check.

        For online providers we ensure required credentials are populated
        and decryptable. We do **not** make a network call here so the
        check is safe to run on every dashboard load. A real provider
        ping is delegated to the gateway adapter.
        """
        rec = self.get(config_id)
        required = PROVIDER_REQUIRED_CREDENTIALS.get(rec.provider, ())
        creds = self.get_decrypted_credentials(rec)
        missing = [k for k in required if not creds.get(k)]

        rec.last_test_at = datetime.now(timezone.utc)
        if missing:
            rec.last_test_status = "FAILED"
            rec.last_test_error = f"Missing credentials: {', '.join(missing)}"
            self.db.commit()
            return {"ok": False, "missing": missing}

        rec.last_test_status = "OK"
        rec.last_test_error = None
        self.db.commit()
        return {"ok": True, "missing": []}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate_provider_for_channel(
        self, channel: PaymentChannel, provider: PaymentProvider
    ) -> None:
        if channel == PaymentChannel.GATEWAY and provider == PaymentProvider.MANUAL:
            raise BadRequestError(
                message="GATEWAY channel requires a real provider (PAYSTACK / FLUTTERWAVE / STRIPE / MONNIFY / REMITA).",
            )
        manual_only = {
            PaymentChannel.CASHIER,
            PaymentChannel.MEMBERSHIP_CARD,
            PaymentChannel.LOYALTY,
            PaymentChannel.BANK_TRANSFER,
            PaymentChannel.INSURANCE,
        }
        if channel in manual_only and provider != PaymentProvider.MANUAL:
            raise BadRequestError(
                message=f"Channel {channel} must use provider MANUAL.",
            )

    def _validate_credentials(
        self,
        provider: PaymentProvider,
        credentials: Optional[dict[str, str]],
    ) -> None:
        # Reject unknown credential keys to catch typos early.
        if credentials:
            unknown = sorted(set(credentials.keys()) - _CRED_FIELDS.keys())
            if unknown:
                raise BadRequestError(
                    message=f"Unsupported credential field(s): {unknown}",
                    detail={"allowed": sorted(_CRED_FIELDS.keys())},
                )
        # Don't enforce required creds at create-time — operators may want
        # to register a provider record first and add the secret later.
        # ``test_config`` surfaces missing-cred errors at use time.

    def _apply_credentials(
        self,
        rec: TenantPaymentMethodConfig,
        credentials: Optional[dict[str, str]],
    ) -> None:
        if not credentials:
            return
        for plain_field, encrypted_attr in _CRED_FIELDS.items():
            if plain_field not in credentials:
                continue
            value = credentials[plain_field]
            if value is None or value == "":
                # Clearing a credential.
                setattr(rec, encrypted_attr, None)
            else:
                setattr(rec, encrypted_attr, encrypt_string(str(value)))

    def _enforce_single_default(self, default_rec: TenantPaymentMethodConfig) -> None:
        """Ensure no other active row of the same channel claims is_default."""
        (
            self.db.query(TenantPaymentMethodConfig)
            .filter(
                TenantPaymentMethodConfig.id != default_rec.id,
                TenantPaymentMethodConfig.channel == default_rec.channel,
                TenantPaymentMethodConfig.is_deleted.is_(False),
            )
            .update({TenantPaymentMethodConfig.is_default: False})
        )
