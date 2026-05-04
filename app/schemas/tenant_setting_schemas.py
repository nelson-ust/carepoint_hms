"""
Pydantic schemas for tenant-specific settings.

Tenant settings cover three concerns:

* Branding (logo, theme colors, configurable theme JSON)
* Regional & document formatting (currency, timezone, date/time, doc numbering)
* Operational policy (approval workflows, notification preferences/channels)
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class TenantSettingUpdateSchema(BaseModel):
    # Branding
    logo_url: Optional[str] = None
    theme_config: Optional[dict[str, Any]] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None

    # Regional
    default_currency: Optional[str] = None
    timezone: Optional[str] = None
    date_format: Optional[str] = None
    time_format: Optional[str] = None

    # Document numbering
    invoice_prefix: Optional[str] = None
    invoice_next_number: Optional[int] = None
    invoice_number_format: Optional[str] = None
    receipt_prefix: Optional[str] = None
    receipt_next_number: Optional[int] = None
    receipt_number_format: Optional[str] = None
    appointment_prefix: Optional[str] = None
    appointment_next_number: Optional[int] = None

    # Approval workflows (free-form JSON, validated at the service layer).
    approval_workflows: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Per-action approval policy. Each key is a business action "
            "(e.g. 'invoice.discount') and the value declares the policy "
            "(required, threshold, approver_role)."
        ),
        examples=[
            {
                "invoice.discount": {
                    "required": True,
                    "min_amount": 5000,
                    "approver_role": "TENANT_ADMIN",
                }
            }
        ],
    )

    # Notification preferences
    notify_in_app_enabled: Optional[bool] = None
    notify_email_enabled: Optional[bool] = None
    notify_sms_enabled: Optional[bool] = None
    notify_whatsapp_enabled: Optional[bool] = None
    notify_push_enabled: Optional[bool] = None
    notification_channels: Optional[dict[str, list[str]]] = Field(
        default=None,
        description=(
            "Per-event channel routing. Keys are NotificationEvent codes; "
            "values are lists of channel codes such as 'email' or 'sms'."
        ),
        examples=[
            {
                "appointment.reminder": ["email", "sms"],
                "invoice.created": ["in_app", "email"],
            }
        ],
    )
    quiet_hours: Optional[dict[str, str]] = Field(
        default=None,
        description='Quiet-hours window such as {"start": "22:00", "end": "07:00"}.',
        examples=[{"start": "22:00", "end": "07:00", "tz": "Africa/Lagos"}],
    )
    notification_from_email: Optional[str] = None
    notification_from_name: Optional[str] = None
    notification_sms_sender_id: Optional[str] = None


class TenantSettingReadSchema(BaseModel):
    logo_url: Optional[str] = None
    theme_config: Optional[dict[str, Any]] = None
    primary_color: str
    secondary_color: str

    default_currency: str
    timezone: str
    date_format: str
    time_format: str

    invoice_prefix: str
    invoice_next_number: int
    invoice_number_format: Optional[str] = None
    receipt_prefix: str
    receipt_next_number: int
    receipt_number_format: Optional[str] = None
    appointment_prefix: str
    appointment_next_number: int

    approval_workflows: Optional[dict[str, Any]] = None

    notify_in_app_enabled: bool = True
    notify_email_enabled: bool = True
    notify_sms_enabled: bool = False
    notify_whatsapp_enabled: bool = False
    notify_push_enabled: bool = False
    notification_channels: Optional[dict[str, list[str]]] = None
    quiet_hours: Optional[dict[str, str]] = None
    notification_from_email: Optional[str] = None
    notification_from_name: Optional[str] = None
    notification_sms_sender_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
