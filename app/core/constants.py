# carepoint_hms/app/core/constants.py
from __future__ import annotations

"""
carepoint_hms.app.core.constants

Centralized application constants for Carepoint HMS.

Purpose
-------
This module defines shared constants used across the application to avoid
hard-coded strings and magic numbers in routes, services, repositories,
middlewares, and utilities.

Why this exists
---------------
- improves consistency across the codebase
- makes future changes easier
- reduces typo-related bugs
- keeps commonly reused values in one place
"""

# ============================================================
# APPLICATION
# ============================================================

APP_CODE: str = "CAREPOINT_HMS"
APP_DISPLAY_NAME: str = "Carepoint HMS"
APP_TIMEZONE_FALLBACK: str = "Africa/Lagos"
DEFAULT_CURRENCY: str = "NGN"
DEFAULT_LANGUAGE: str = "en"


# ============================================================
# API
# ============================================================

API_VERSION_V1: str = "/api/v1"
DEFAULT_API_TAG: str = "Carepoint HMS"


# ============================================================
# HTTP / REQUEST HEADERS
# ============================================================

HEADER_AUTHORIZATION: str = "Authorization"
HEADER_CONTENT_TYPE: str = "Content-Type"
HEADER_ACCEPT: str = "Accept"
HEADER_REQUEST_ID: str = "X-Request-ID"
HEADER_FORWARDED_FOR: str = "X-Forwarded-For"
HEADER_REAL_IP: str = "X-Real-IP"


# ============================================================
# AUTH / TOKENS / SECURITY
# ============================================================

TOKEN_TYPE_ACCESS: str = "access"
TOKEN_TYPE_REFRESH: str = "refresh"
TOKEN_TYPE_PASSWORD_RESET: str = "password_reset"
TOKEN_TYPE_EMAIL_VERIFICATION: str = "email_verification"
TOKEN_TYPE_PHONE_VERIFICATION: str = "phone_verification"

AUTH_SCHEME_BEARER: str = "Bearer"

DEFAULT_OTP_LENGTH: int = 6
DEFAULT_OTP_EXPIRY_MINUTES: int = 10
DEFAULT_OTP_MAX_ATTEMPTS: int = 5
DEFAULT_OTP_RESEND_INTERVAL_SECONDS: int = 60

PASSWORD_MIN_LENGTH: int = 8


# ============================================================
# PAGINATION
# ============================================================

DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100
DEFAULT_SKIP: int = 0


# ============================================================
# FILE / UPLOADS
# ============================================================

DEFAULT_MEDIA_ROOT: str = "media"
DEFAULT_REPORTS_DIR: str = "reports"
DEFAULT_UPLOAD_MAX_SIZE_MB: int = 20

ALLOWED_IMAGE_EXTENSIONS: tuple[str, ...] = (
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
)

ALLOWED_DOCUMENT_EXTENSIONS: tuple[str, ...] = (
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
)

ALLOWED_SPREADSHEET_EXTENSIONS: tuple[str, ...] = (
    ".xls",
    ".xlsx",
    ".csv",
)

ALLOWED_GENERIC_UPLOAD_EXTENSIONS: tuple[str, ...] = (
    *ALLOWED_IMAGE_EXTENSIONS,
    *ALLOWED_DOCUMENT_EXTENSIONS,
    *ALLOWED_SPREADSHEET_EXTENSIONS,
)


# ============================================================
# CODE / NUMBER PREFIXES
# ============================================================

PATIENT_HOSPITAL_NO_PREFIX: str = "HMS"
VISIT_CODE_PREFIX: str = "VIS"
APPOINTMENT_CODE_PREFIX: str = "APT"
QUEUE_NUMBER_DEFAULT_PREFIX: str = "Q"
LAB_ORDER_NO_PREFIX: str = "LAB"
PRESCRIPTION_NO_PREFIX: str = "RX"
DISPENSE_NO_PREFIX: str = "DSP"
BILLING_NO_PREFIX: str = "BIL"
INVOICE_NO_PREFIX: str = "INV"
PAYMENT_REFERENCE_PREFIX: str = "PAY"
ADMISSION_NO_PREFIX: str = "ADM"
AMBULANCE_DISPATCH_NO_PREFIX: str = "AMB"
INCIDENT_NO_PREFIX: str = "INC"
LOYALTY_MEMBERSHIP_NO_PREFIX: str = "LOY"


# ============================================================
# MODULE NAMES
# ============================================================

MODULE_AUTH: str = "AUTH"
MODULE_USERS: str = "USERS"
MODULE_PATIENTS: str = "PATIENTS"
MODULE_REGISTRATION: str = "REGISTRATION"
MODULE_APPOINTMENTS: str = "APPOINTMENTS"
MODULE_VISITS: str = "VISITS"
MODULE_QUEUE: str = "QUEUE"
MODULE_TRIAGE: str = "TRIAGE"
MODULE_CLINICAL: str = "CLINICAL"
MODULE_LAB: str = "LAB"
MODULE_PHARMACY: str = "PHARMACY"
MODULE_BILLING: str = "BILLING"
MODULE_INSURANCE: str = "INSURANCE"
MODULE_LOYALTY: str = "LOYALTY"
MODULE_ADMISSION: str = "ADMISSION"
MODULE_WARD: str = "WARD"
MODULE_INVENTORY: str = "INVENTORY"
MODULE_AMBULANCE: str = "AMBULANCE"
MODULE_HR: str = "HR"
MODULE_NOTIFICATIONS: str = "NOTIFICATIONS"
MODULE_COMPLIANCE: str = "COMPLIANCE"
MODULE_QUALITY: str = "QUALITY"
MODULE_REPORTS: str = "REPORTS"
MODULE_AUDIT: str = "AUDIT"


# ============================================================
# COMMON ACTION LABELS
# ============================================================

ACTION_CREATE: str = "CREATE"
ACTION_UPDATE: str = "UPDATE"
ACTION_DELETE: str = "DELETE"
ACTION_RESTORE: str = "RESTORE"
ACTION_VIEW: str = "VIEW"
ACTION_LIST: str = "LIST"
ACTION_LOGIN: str = "LOGIN"
ACTION_LOGOUT: str = "LOGOUT"
ACTION_VERIFY: str = "VERIFY"
ACTION_APPROVE: str = "APPROVE"
ACTION_REJECT: str = "REJECT"
ACTION_SUBMIT: str = "SUBMIT"
ACTION_CANCEL: str = "CANCEL"
ACTION_ASSIGN: str = "ASSIGN"
ACTION_TRANSFER: str = "TRANSFER"
ACTION_DISPATCH: str = "DISPATCH"
ACTION_COMPLETE: str = "COMPLETE"


# ============================================================
# COMMON STATUS TEXT
# ============================================================

STATUS_SUCCESS: str = "success"
STATUS_FAILED: str = "failed"
STATUS_PENDING: str = "pending"
STATUS_ACTIVE: str = "active"
STATUS_INACTIVE: str = "inactive"


# ============================================================
# COMMON RESPONSE / ERROR MESSAGES
# ============================================================

MSG_CREATED_SUCCESSFULLY: str = "Record created successfully."
MSG_UPDATED_SUCCESSFULLY: str = "Record updated successfully."
MSG_DELETED_SUCCESSFULLY: str = "Record deleted successfully."
MSG_RESTORED_SUCCESSFULLY: str = "Record restored successfully."
MSG_FETCHED_SUCCESSFULLY: str = "Record fetched successfully."
MSG_LIST_FETCHED_SUCCESSFULLY: str = "Records fetched successfully."

MSG_INVALID_CREDENTIALS: str = "Invalid credentials."
MSG_ACCESS_DENIED: str = "Access denied."
MSG_RECORD_NOT_FOUND: str = "Record not found."
MSG_DUPLICATE_RECORD: str = "Duplicate record found."
MSG_VALIDATION_ERROR: str = "Validation error."
MSG_INTERNAL_SERVER_ERROR: str = "An internal server error occurred."
MSG_DATABASE_ERROR: str = "A database error occurred."
MSG_INVALID_TOKEN: str = "Invalid token."
MSG_EXPIRED_TOKEN: str = "Token has expired."
MSG_INVALID_OTP: str = "Invalid OTP."
MSG_EXPIRED_OTP: str = "OTP has expired."
MSG_OTP_VERIFIED: str = "OTP verified successfully."
MSG_OPERATION_NOT_ALLOWED: str = "Operation not allowed."


# ============================================================
# AUDIT / LOGGING
# ============================================================

AUDIT_ENTITY_UNKNOWN: str = "UNKNOWN_ENTITY"
AUDIT_ACTION_UNKNOWN: str = "UNKNOWN_ACTION"
LOG_REQUEST_START: str = "REQUEST_START"
LOG_REQUEST_END: str = "REQUEST_END"
LOG_DB_CONNECTION_CHECK: str = "DB_CONNECTION_CHECK"


# ============================================================
# REPORT TYPES
# ============================================================

REPORT_TYPE_PATIENT_LIST: str = "PATIENT_LIST"
REPORT_TYPE_VISIT_SUMMARY: str = "VISIT_SUMMARY"
REPORT_TYPE_LAB_SUMMARY: str = "LAB_SUMMARY"
REPORT_TYPE_PHARMACY_SUMMARY: str = "PHARMACY_SUMMARY"
REPORT_TYPE_BILLING_SUMMARY: str = "BILLING_SUMMARY"
REPORT_TYPE_INVENTORY_SUMMARY: str = "INVENTORY_SUMMARY"
REPORT_TYPE_AMBULANCE_SUMMARY: str = "AMBULANCE_SUMMARY"
REPORT_TYPE_HR_SUMMARY: str = "HR_SUMMARY"
REPORT_TYPE_COMPLIANCE_SUMMARY: str = "COMPLIANCE_SUMMARY"


# ============================================================
# DATE / FORMAT STRINGS
# ============================================================

DATE_FORMAT_STANDARD: str = "%Y-%m-%d"
DATETIME_FORMAT_STANDARD: str = "%Y-%m-%d %H:%M:%S"
DATEKEY_FORMAT: str = "%Y%m%d"
TIMESTAMP_KEY_FORMAT: str = "%Y%m%d%H%M%S"


# ============================================================
# CACHE / REDIS KEYS
# ============================================================

CACHE_KEY_USER_SESSION_PREFIX: str = "user_session"
CACHE_KEY_OTP_PREFIX: str = "otp"
CACHE_KEY_RATE_LIMIT_PREFIX: str = "rate_limit"
CACHE_KEY_SETTINGS_PREFIX: str = "settings"


# ============================================================
# NOTIFICATION CHANNEL LABELS
# ============================================================

CHANNEL_EMAIL: str = "EMAIL"
CHANNEL_SMS: str = "SMS"
CHANNEL_WHATSAPP: str = "WHATSAPP"
CHANNEL_IN_APP: str = "IN_APP"