"""
Tenant-level settings service.

Surfaces three classes of policy:

* Branding & regional defaults (logo, colors, currency, timezone, etc.)
* Document numbering policy (invoice, receipt, appointment formats)
* Operational policy:
    - Approval workflows (per business action)
    - Notification preferences (per event, per channel)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone as _tz
from typing import Any, Iterable, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_master_db_context
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Tenant, TenantSetting
from app.schemas.tenant_setting_schemas import TenantSettingUpdateSchema
from app.services.aws_s3_service import S3Service


# ---------------------------------------------------------------------------
# Default routing
# ---------------------------------------------------------------------------

# Channel codes used in notification_channels and elsewhere.
SUPPORTED_CHANNELS: tuple[str, ...] = ("in_app", "email", "sms", "whatsapp", "push")

# Sensible defaults if a tenant hasn't customized their event routing.
DEFAULT_NOTIFICATION_CHANNELS: dict[str, list[str]] = {
    "user.invited": ["email"],
    "user.password_reset": ["email"],
    "appointment.created": ["in_app", "email"],
    "appointment.reminder": ["sms", "email"],
    "appointment.cancelled": ["in_app", "email"],
    "invoice.created": ["in_app", "email"],
    "payment.received": ["email", "sms"],
    "subscription.renewed": ["email"],
    "subscription.expiring": ["email"],
    "subscription.suspended": ["email"],
    "approval.requested": ["in_app", "email"],
    "approval.granted": ["in_app"],
    "approval.rejected": ["in_app"],
    "system.alert": ["in_app", "email"],
    "backup.completed": ["email"],
    "backup.failed": ["email"],
}


class TenantSettingService:
    """
    Service for reading and mutating per-tenant settings.

    Operates on the **tenant** database (TenantSetting is a TenantTable).
    """

    def __init__(self, db: Session, tenant_code: Optional[str] = None) -> None:
        self.db = db
        self.tenant_code = tenant_code

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_settings(self) -> TenantSetting:
        """Return the singleton TenantSetting for this tenant, creating defaults if absent."""
        setting = self.db.query(TenantSetting).first()
        if not setting:
            setting = TenantSetting(
                default_currency="NGN",
                timezone="Africa/Lagos",
                theme_config={},
            )
            self.db.add(setting)
            self.db.commit()
            self.db.refresh(setting)
        return setting

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def update_settings(self, payload: TenantSettingUpdateSchema) -> TenantSetting:
        """
        Update mutable fields on the TenantSetting row.

        Validates approval-workflow and notification-channel JSON shapes
        before persisting.
        """
        setting = self.get_settings()

        update_data = payload.model_dump(exclude_unset=True)

        if "approval_workflows" in update_data and update_data["approval_workflows"] is not None:
            self._validate_approval_workflows(update_data["approval_workflows"])

        if "notification_channels" in update_data and update_data["notification_channels"] is not None:
            self._validate_notification_channels(update_data["notification_channels"])

        for key, value in update_data.items():
            setattr(setting, key, value)

        self.db.commit()
        self.db.refresh(setting)
        return setting

    def upload_logo(self, file_obj: UploadFile) -> TenantSetting:
        if not self.tenant_code:
            raise BadRequestError(message="tenant_code is required to upload a logo.")

        with get_master_db_context() as master_db:
            tenant = master_db.query(Tenant).filter(Tenant.code == self.tenant_code).first()
            if not tenant or not tenant.aws_s3_bucket_name:
                raise BadRequestError(message="Tenant AWS S3 bucket not provisioned.")
            bucket_name = tenant.aws_s3_bucket_name

        s3_service = S3Service()
        file_ext = file_obj.filename.split(".")[-1] if "." in (file_obj.filename or "") else "png"
        s3_key = f"settings/logo_{uuid.uuid4().hex}.{file_ext}"

        logo_url = s3_service.upload_file(bucket_name, file_obj, s3_key)
        if not logo_url:
            raise BadRequestError(message="Failed to upload logo to AWS S3.")

        setting = self.get_settings()
        setting.logo_url = logo_url
        self.db.commit()
        self.db.refresh(setting)
        return setting

    # ------------------------------------------------------------------
    # APPROVAL WORKFLOWS
    # ------------------------------------------------------------------

    def get_approval_policy(self, action_code: str) -> dict[str, Any]:
        """
        Return the approval policy for a single action, or an empty dict if
        no policy is configured.
        """
        setting = self.get_settings()
        policies = setting.approval_workflows or {}
        return dict(policies.get(action_code, {}))

    def is_approval_required(self, action_code: str, *, amount: Optional[float] = None) -> bool:
        """
        Compute whether ``action_code`` requires an approval, optionally
        compared against a threshold.
        """
        policy = self.get_approval_policy(action_code)
        if not policy.get("required"):
            return False
        threshold = policy.get("min_amount")
        if threshold is not None and amount is not None:
            try:
                return float(amount) >= float(threshold)
            except (TypeError, ValueError):
                return True
        return True

    # ------------------------------------------------------------------
    # NOTIFICATION ROUTING
    # ------------------------------------------------------------------

    def get_channels_for_event(self, event_code: str) -> list[str]:
        """
        Return the list of channel codes that should be used for ``event_code``.

        Resolution order:
            1. tenant-specific override in ``notification_channels``
            2. platform default in :data:`DEFAULT_NOTIFICATION_CHANNELS`
            3. ``["in_app"]`` as a final fallback.

        Channels disabled at the tenant level (``notify_<channel>_enabled=False``)
        are stripped from the resolved list.
        """
        setting = self.get_settings()

        configured = (setting.notification_channels or {}).get(event_code)
        channels = configured if configured else DEFAULT_NOTIFICATION_CHANNELS.get(event_code, ["in_app"])

        normalized = [c for c in (channels or []) if c in SUPPORTED_CHANNELS]
        return [c for c in normalized if self._is_channel_enabled(setting, c)]

    def is_in_quiet_hours(self, *, now: Optional[datetime] = None) -> bool:
        """
        Return True if the current local time is within the tenant's
        configured quiet-hours window. Quiet hours apply to push/SMS only;
        callers decide which channels to suppress.
        """
        setting = self.get_settings()
        window = setting.quiet_hours or {}
        start = window.get("start")
        end = window.get("end")
        if not start or not end:
            return False

        moment = (now or datetime.now(_tz.utc)).strftime("%H:%M")
        if start <= end:
            return start <= moment < end
        return moment >= start or moment < end

    # ------------------------------------------------------------------
    # DOCUMENT NUMBERING
    # ------------------------------------------------------------------

    def next_invoice_number(self) -> str:
        return self._next_document_number(
            prefix_attr="invoice_prefix",
            counter_attr="invoice_next_number",
            format_attr="invoice_number_format",
        )

    def next_receipt_number(self) -> str:
        return self._next_document_number(
            prefix_attr="receipt_prefix",
            counter_attr="receipt_next_number",
            format_attr="receipt_number_format",
        )

    def next_appointment_number(self) -> str:
        return self._next_document_number(
            prefix_attr="appointment_prefix",
            counter_attr="appointment_next_number",
            format_attr=None,
        )

    # ------------------------------------------------------------------
    # INTERNAL
    # ------------------------------------------------------------------

    def _is_channel_enabled(self, setting: TenantSetting, channel: str) -> bool:
        flag = f"notify_{channel}_enabled"
        return bool(getattr(setting, flag, True))

    def _validate_approval_workflows(self, workflows: dict[str, Any]) -> None:
        if not isinstance(workflows, dict):
            raise BadRequestError(message="approval_workflows must be a JSON object.")
        for action, policy in workflows.items():
            if not isinstance(action, str) or not action:
                raise BadRequestError(message="Each approval workflow key must be a non-empty string.")
            if not isinstance(policy, dict):
                raise BadRequestError(
                    message=f"Approval workflow '{action}' must be a JSON object."
                )

    def _validate_notification_channels(self, channels: dict[str, Iterable[str]]) -> None:
        if not isinstance(channels, dict):
            raise BadRequestError(message="notification_channels must be a JSON object.")
        for event, value in channels.items():
            if not isinstance(value, (list, tuple)):
                raise BadRequestError(
                    message=f"Channels for event '{event}' must be a list."
                )
            for channel in value:
                if channel not in SUPPORTED_CHANNELS:
                    raise BadRequestError(
                        message=(
                            f"Unsupported channel '{channel}' for event '{event}'."
                            f" Supported: {sorted(SUPPORTED_CHANNELS)}."
                        )
                    )

    def _next_document_number(
        self,
        *,
        prefix_attr: str,
        counter_attr: str,
        format_attr: Optional[str],
    ) -> str:
        setting = self.get_settings()
        prefix = getattr(setting, prefix_attr) or ""
        seq = int(getattr(setting, counter_attr) or 1)
        fmt = getattr(setting, format_attr, None) if format_attr else None

        if fmt:
            try:
                rendered = fmt.format(prefix=prefix, seq=seq, year=datetime.utcnow().year)
            except Exception:
                rendered = f"{prefix}-{seq:06d}"
        else:
            rendered = f"{prefix}-{seq:06d}"

        setattr(setting, counter_attr, seq + 1)
        self.db.commit()
        return rendered
