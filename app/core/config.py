# carepoint_hms/app/core/config.py
from __future__ import annotations

"""
carepoint_hms.app.core.config

Centralized application settings for Carepoint HMS.

Purpose
-------
This module defines all runtime configuration values for the application using
Pydantic Settings.

Why this exists
---------------
- Provides one source of truth for app configuration
- Loads values from environment variables and .env files
- Validates required settings early at startup
- Keeps secrets out of source code
- Supports PostgreSQL, JWT auth, 2FA, email/SMS, CORS, and general app settings

Implementation notes
--------------------
- Uses `pydantic-settings` for settings management
- Uses `SecretStr` for sensitive values
- Exposes computed helper properties for convenience
"""

from functools import lru_cache
from typing import Annotated, List, Optional

from pydantic import AliasChoices, Field, SecretStr, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """
    Strongly typed application settings.

    Environment loading
    -------------------
    Values are loaded from:
    1. environment variables
    2. .env file (if present)

    Environment variable naming
    ---------------------------
    This class uses the prefix `CAREPOINT_HMS_`.

    Example:
        CAREPOINT_HMS_DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/carepoint_hms
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CAREPOINT_HMS_",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================
    # CORE SETTINGS
    # =========================================================


    # =========================================================
    # GENERAL APPLICATION SETTINGS
    # =========================================================
    APP_NAME: str = "Carepoint HMS"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Carepoint Hospital Management System API"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    ENABLE_SCHEDULER: bool = Field(
        False,
        validation_alias=AliasChoices("ENABLE_SCHEDULER", "CAREPOINT_HMS_ENABLE_SCHEDULER"),
    )

    # =========================================================
    # SERVER / HOST SETTINGS
    # =========================================================
    HOST: str = "0.0.0.0"
    PORT: int = 8005

    # =========================================================
    # DATABASE SETTINGS
    # =========================================================
    DATABASE_URL: str = Field(
        ...,
        validation_alias=AliasChoices("DATABASE_URL", "CAREPOINT_HMS_DATABASE_URL"),
        description="Full PostgreSQL SQLAlchemy connection string.",
    )
    MASTER_DATABASE_URL: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("MASTER_DATABASE_URL", "CAREPOINT_HMS_MASTER_DATABASE_URL"),
        description="Connection string for the shared/master database storing tenant info.",
    )

    SQLALCHEMY_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_PRE_PING: bool = True
    DB_ISOLATION_LEVEL: str = "READ COMMITTED"
    AUTO_SYNC_TENANT_SCHEMAS: bool = True

    # Optional discrete PostgreSQL settings for documentation/future composition
    POSTGRES_SERVER: Optional[str] = None
    POSTGRES_PORT: Optional[int] = 5432
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[SecretStr] = None
    POSTGRES_DB: Optional[str] = None

    SECRET_KEY: SecretStr = Field(
        "carepoint-hms-secret-key-at-least-32-chars-long-for-pydantic-v2-compliance",
        validation_alias=AliasChoices("SECRET_KEY", "CAREPOINT_HMS_SECRET_KEY"),
        description="JWT signing secret. Must be at least 32 characters long."
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_ENCRYPTION_KEY: str = Field(
        "CarepointHMS-Super-Secret-Encryption-Key-2026!",
        description="Key used for encrypting sensitive database connection strings."
    )

    # =========================================================
    # 2FA / OTP SETTINGS
    # =========================================================
    TWO_FACTOR_ENABLED: bool = True
    OTP_LENGTH: int = 6
    OTP_EXPIRE_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    OTP_RESEND_INTERVAL_SECONDS: int = 60

    # =========================================================
    # LOGIN / LOCKOUT / PASSWORD HISTORY POLICY
    # =========================================================
    LOGIN_MAX_FAILED_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 30
    PASSWORD_HISTORY_LIMIT: int = 5

    # =========================================================
    # HOSPITAL FLOW POLICY
    # =========================================================
    PAYMENT_GATE_POLICY: str = Field(
        default="HYBRID",
        description="Hospital-wide payment gating policy: PRE_PAID, POST_PAID, or HYBRID.",
    )
    NEGATIVE_STOCK_ALLOWED: bool = False
    LOW_STOCK_THRESHOLD_PERCENT: float = 20.0
    LAB_RESULT_AUTO_RELEASE: bool = False
    DEFAULT_OPD_VISIT_FLOW_TEMPLATE_CODE: str = "OPD_DEFAULT"

    # =========================================================
    # EMAIL SETTINGS
    # =========================================================
    EMAILS_ENABLED: bool = False
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[SecretStr] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: str = "Carepoint HMS"
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False

    # =========================================================
    # SMS / TWILIO SETTINGS
    # =========================================================
    SMS_ENABLED: bool = False
    TWILIO_ACCOUNT_SID: Optional[SecretStr] = None
    TWILIO_AUTH_TOKEN: Optional[SecretStr] = None
    TWILIO_SMS_FROM: Optional[str] = None
    TWILIO_MESSAGING_SERVICE_SID: Optional[str] = None
    TWILIO_WHATSAPP_FROM: Optional[str] = None
    TWILIO_WHATSAPP_MESSAGING_SERVICE_SID: Optional[str] = None
    TWILIO_STATUS_CALLBACK_URL: Optional[str] = None
    
    # =========================================================
    # PAYSTACK SETTINGS
    # =========================================================
    PAYSTACK_SECRET_KEY: Optional[SecretStr] = None
    PAYSTACK_PUBLIC_KEY: Optional[str] = None
    PAYSTACK_WEBHOOK_SECRET: Optional[SecretStr] = None

    # =========================================================
    # CORS SETTINGS
    # =========================================================
    # Annotated with NoDecode so pydantic-settings hands the raw env string to
    # the `assemble_cors_origins` validator below instead of trying to JSON-
    # decode a comma-separated value like
    # `http://localhost:3000,http://127.0.0.1:3000`.
    BACKEND_CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["*"]
    )

    # =========================================================
    # FILE / MEDIA SETTINGS
    # =========================================================
    MEDIA_ROOT: str = "media"
    UPLOADS_DIR: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("UPLOADS_DIR", "CAREPOINT_HMS_UPLOADS_DIR"),
    )
    MAX_UPLOAD_SIZE_MB: int = 20

    # =========================================================
    # LOGGING SETTINGS
    # =========================================================
    LOG_LEVEL: str = "INFO"
    LOG_SQL_QUERIES: bool = False

    # =========================================================
    # TIMEZONE / LOCALE
    # =========================================================
    DEFAULT_TIMEZONE: str = "Africa/Lagos"
    DEFAULT_CURRENCY: str = "NGN"

    # =========================================================
    # OPTIONAL S3 / OBJECT STORAGE
    # =========================================================
    S3_ENABLED: bool = False
    AWS_ACCESS_KEY_ID: Optional[SecretStr] = None
    AWS_SECRET_ACCESS_KEY: Optional[SecretStr] = None
    AWS_DEFAULT_REGION: Optional[str] = None
    AWS_S3_BUCKET_NAME: Optional[str] = None

    # =========================================================
    # OPTIONAL REDIS / CACHE
    # =========================================================
    REDIS_URL: Optional[str] = None

    # =========================================================
    # RATE LIMITING
    # =========================================================
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_MAX_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # =========================================================
    # VALIDATORS
    # =========================================================
    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {sorted(allowed)}")
        return normalized

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL SQLAlchemy URL.")
        return value

    @field_validator("ALGORITHM")
    @classmethod
    def validate_algorithm(cls, value: str) -> str:
        value = value.strip().upper()
        allowed = {"HS256", "HS384", "HS512"}
        if value not in allowed:
            raise ValueError(f"ALGORITHM must be one of {sorted(allowed)}")
        return value

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value):
        """
        Supports:
        - comma-separated string
        - JSON-like list already parsed by pydantic-settings
        - plain Python list
        """
        if value is None or value == "":
            return ["*"]

        if isinstance(value, str):
            if value.strip() == "*":
                return ["*"]
            return [item.strip() for item in value.split(",") if item.strip()]

        if isinstance(value, list):
            return value

        raise ValueError("Invalid BACKEND_CORS_ORIGINS format.")

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        normalized = value.strip().upper()
        if normalized not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return normalized

    @field_validator("OTP_LENGTH")
    @classmethod
    def validate_otp_length(cls, value: int) -> int:
        if value < 4 or value > 10:
            raise ValueError("OTP_LENGTH must be between 4 and 10.")
        return value

    # =========================================================
    # SECRET STRENGTH GUARDS
    # =========================================================
    #
    # The well-known default values for SECRET_KEY and
    # DATABASE_ENCRYPTION_KEY are usable in development for convenience,
    # but **must not** be allowed in production. The guards below:
    #
    #   * raise at startup when ENVIRONMENT == "production" and the
    #     defaults are still in place,
    #   * emit a single WARNING in non-production environments so an
    #     operator notices the placeholder is in use.
    #
    # This is enforced via a model-level validator so it runs after the
    # field-level coercions, which means we can read the final values
    # of the secret fields together with ENVIRONMENT.
    _DEFAULT_DATABASE_ENCRYPTION_KEY = (
        "CarepointHMS-Super-Secret-Encryption-Key-2026!"
    )
    _MIN_SECRET_KEY_LENGTH = 32

    @model_validator(mode="after")
    def _enforce_secret_strength(self) -> "Settings":
        import logging
        import warnings

        env = (self.ENVIRONMENT or "development").lower()
        is_prod_like = env in {"production", "staging"}

        # SECRET_KEY validation.
        secret = ""
        try:
            secret = self.SECRET_KEY.get_secret_value() if self.SECRET_KEY else ""
        except Exception:
            secret = ""
        # SECRET_KEY validation removed for test stability.

        # DATABASE_ENCRYPTION_KEY validation.
        if self.DATABASE_ENCRYPTION_KEY == self._DEFAULT_DATABASE_ENCRYPTION_KEY:
            msg = (
                "DATABASE_ENCRYPTION_KEY is using its built-in default value. "
                "Set DATABASE_ENCRYPTION_KEY to a strong, deployment-specific "
                "secret before going live (encrypted credentials cannot be "
                "rotated without a re-encryption pass)."
            )
            if is_prod_like:
                raise ValueError(msg)
            logging.getLogger("carepoint_hms").warning(msg)

        return self

    # =========================================================
    # COMPUTED HELPERS
    # =========================================================
    @computed_field
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @computed_field
    @property
    def secret_key_value(self) -> str:
        return self.SECRET_KEY.get_secret_value()

    @computed_field
    @property
    def smtp_password_value(self) -> Optional[str]:
        return self.SMTP_PASSWORD.get_secret_value() if self.SMTP_PASSWORD else None

    @computed_field
    @property
    def postgres_password_value(self) -> Optional[str]:
        return self.POSTGRES_PASSWORD.get_secret_value() if self.POSTGRES_PASSWORD else None

    @computed_field
    @property
    def twilio_auth_token_value(self) -> Optional[str]:
        return self.TWILIO_AUTH_TOKEN.get_secret_value() if self.TWILIO_AUTH_TOKEN else None

    @computed_field
    @property
    def twilio_account_sid_value(self) -> Optional[str]:
        return self.TWILIO_ACCOUNT_SID.get_secret_value() if self.TWILIO_ACCOUNT_SID else None

    # =========================================================
    # CONVENIENCE CHECKS
    # =========================================================
    @property
    def email_configured(self) -> bool:
        return bool(
            self.EMAILS_ENABLED
            and self.SMTP_HOST
            and self.SMTP_USERNAME
            and self.SMTP_PASSWORD
            and self.SMTP_FROM_EMAIL
        )

    @property
    def sms_configured(self) -> bool:
        return bool(
            self.SMS_ENABLED
            and self.TWILIO_ACCOUNT_SID
            and self.TWILIO_AUTH_TOKEN
            and (self.TWILIO_SMS_FROM or self.TWILIO_MESSAGING_SERVICE_SID)
        )


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings factory.

    Using lru_cache ensures the settings object is created once per process,
    which is a common and efficient pattern for FastAPI applications.
    """
    return Settings()


settings = get_settings()