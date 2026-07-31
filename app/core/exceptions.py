# carepoint_hms/app/core/exceptions.py
from __future__ import annotations

"""
carepoint_hms.app.core.exceptions

Custom exception classes and FastAPI exception handlers for Carepoint HMS.

Purpose
-------
This module centralizes application-specific exceptions so the codebase can:

- raise meaningful domain errors
- return consistent API error responses
- separate business errors from framework/internal errors
- simplify global exception handling

Design goals
------------
- keep exception classes simple and reusable
- support FastAPI exception handlers
- standardize error payloads
- make services and repositories easier to read

Typical usage
-------------
Example in a service or repository:

    from app.core.exceptions import NotFoundError, ConflictError

    if patient is None:
        raise NotFoundError(
            message="Patient not found.",
            detail={"patient_id": patient_id},
        )

    if existing_user:
        raise ConflictError(
            message="A user with this email already exists.",
            detail={"email": email},
        )

Example in app startup:

    from fastapi import FastAPI
    from app.core.exceptions import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)
"""

from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError

import logging

_exc_logger = logging.getLogger(__name__)


class AppException(Exception):
    """
    Base application exception.

    Attributes
    ----------
    message:
        Human-readable error message.

    status_code:
        HTTP status code that should be returned to the client.

    error_code:
        Optional machine-readable error code.

    detail:
        Optional structured detail payload for debugging or UI use.
    """

    def __init__(
        self,
        message: str = "Application error.",
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: Optional[str] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__.upper()
        self.detail = detail or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the exception into a standardized response payload.
        """
        return {
            "success": False,
            "message": self.message,
            "error_code": self.error_code,
            "detail": self.detail,
        }


class ValidationError(AppException):
    """Raised when business validation fails."""

    def __init__(
        self,
        message: str = "Validation error.",
        *,
        error_code: str = "VALIDATION_ERROR",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code=error_code,
            detail=detail,
        )


class BadRequestError(AppException):
    """Raised for invalid requests."""

    def __init__(
        self,
        message: str = "Bad request.",
        *,
        error_code: str = "BAD_REQUEST",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            detail=detail,
        )


class UnauthorizedError(AppException):
    """Raised when authentication fails."""

    def __init__(
        self,
        message: str = "Unauthorized.",
        *,
        error_code: str = "UNAUTHORIZED",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            detail=detail,
        )


class ForbiddenError(AppException):
    """Raised when the user lacks permission to perform an action."""

    def __init__(
        self,
        message: str = "Forbidden.",
        *,
        error_code: str = "FORBIDDEN",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
            detail=detail,
        )


class NotFoundError(AppException):
    """Raised when a requested resource cannot be found."""

    def __init__(
        self,
        message: str = "Record not found.",
        *,
        error_code: str = "NOT_FOUND",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=error_code,
            detail=detail,
        )


class ConflictError(AppException):
    """Raised when a uniqueness or state conflict occurs."""

    def __init__(
        self,
        message: str = "Conflict detected.",
        *,
        error_code: str = "CONFLICT",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_409_CONFLICT,
            error_code=error_code,
            detail=detail,
        )


class AlreadyExistsError(ConflictError):
    """Raised when a record already exists."""

    def __init__(
        self,
        message: str = "Record already exists.",
        *,
        error_code: str = "ALREADY_EXISTS",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            detail=detail,
        )


class DatabaseError(AppException):
    """Raised when a database operation fails in a business-relevant way."""

    def __init__(
        self,
        message: str = "Database error.",
        *,
        error_code: str = "DATABASE_ERROR",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            detail=detail,
        )


class ServiceError(AppException):
    """Raised when service-layer processing fails."""

    def __init__(
        self,
        message: str = "Service error.",
        *,
        error_code: str = "SERVICE_ERROR",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            detail=detail,
        )


class ConfigurationError(AppException):
    """Raised when application configuration is missing or invalid."""

    def __init__(
        self,
        message: str = "Configuration error.",
        *,
        error_code: str = "CONFIGURATION_ERROR",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            detail=detail,
        )


class TokenError(AppException):
    """Raised when token processing fails."""

    def __init__(
        self,
        message: str = "Token error.",
        *,
        error_code: str = "TOKEN_ERROR",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            detail=detail,
        )


class OTPError(AppException):
    """Raised when OTP validation or processing fails."""

    def __init__(
        self,
        message: str = "OTP error.",
        *,
        error_code: str = "OTP_ERROR",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            detail=detail,
        )


class FileProcessingError(AppException):
    """Raised when file validation, upload, parsing, or deletion fails."""

    def __init__(
        self,
        message: str = "File processing error.",
        *,
        error_code: str = "FILE_PROCESSING_ERROR",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            detail=detail,
        )


class BusinessRuleError(AppException):
    """Raised when a domain/business rule is violated."""

    def __init__(
        self,
        message: str = "Business rule violation.",
        *,
        error_code: str = "BUSINESS_RULE_ERROR",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code=error_code,
            detail=detail,
        )


class ExternalServiceError(AppException):
    """Raised when an external integration fails."""

    def __init__(
        self,
        message: str = "External service error.",
        *,
        error_code: str = "EXTERNAL_SERVICE_ERROR",
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code=error_code,
            detail=detail,
        )


def build_error_response(exc: AppException) -> JSONResponse:
    """
    Build a JSONResponse from an AppException instance.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handle any custom application exception.

    CORS headers are attached explicitly so business-error responses are
    never blocked by the browser (which would surface to the SPA as an
    opaque "Network Error" instead of the real message).
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
        headers=_cors_headers_for(request),
    )


async def database_operational_error_handler(_: Request, exc: SQLAlchemyOperationalError) -> JSONResponse:
    """
    Handle SQLAlchemy OperationalError (connection exhaustion, SSL drops, etc.)
    with a friendly 503 response instead of a raw traceback.
    """
    err_msg = str(exc.orig) if hasattr(exc, "orig") and exc.orig else str(exc)
    _exc_logger.error("Database OperationalError caught by global handler: %s", err_msg)

    if "too many clients" in err_msg.lower():
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "The server is currently experiencing high demand. Please try again in a few moments.",
                "error_code": "DATABASE_CONNECTION_LIMIT",
                "detail": {
                    "reason": "The database connection pool has been exhausted.",
                    "action": "Please retry your request shortly. If this persists, contact your system administrator.",
                },
            },
        )

    if "connection refused" in err_msg.lower():
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "Unable to reach the database server. Please try again shortly.",
                "error_code": "DATABASE_UNREACHABLE",
                "detail": {
                    "action": "If this persists, contact your system administrator.",
                },
            },
        )

    if "ssl" in err_msg.lower():
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "A secure connection to the database was interrupted. Please retry your request.",
                "error_code": "DATABASE_SSL_ERROR",
                "detail": {
                    "action": "This is usually temporary. If it persists, contact your system administrator.",
                },
            },
        )

    # Generic fallback for other OperationalErrors
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "message": "The service is temporarily unavailable. Please try again shortly.",
            "error_code": "DATABASE_UNAVAILABLE",
            "detail": {
                "action": "If this persists, contact your system administrator.",
            },
        },
    )


def _cors_headers_for(request: Request) -> dict:
    """
    Compute CORS headers for error responses.

    Starlette installs the ``Exception`` handler on the OUTERMOST
    ServerErrorMiddleware — outside CORSMiddleware — so unhandled-500
    responses would otherwise ship without CORS headers. Browsers then block
    the response entirely and frontends see a bare "Network Error" instead of
    the actual failure. We echo the request Origin when it is allowed.
    """
    origin = request.headers.get("origin")
    if not origin:
        return {}

    allowed = False
    try:
        # Mirror the EFFECTIVE policy the CORSMiddleware runs with — main.py
        # computes exact origins + a regex (wildcard entries and, in dev, the
        # private-LAN pattern). Checking only the raw settings list here made
        # error responses invisible to browsers on any regex-allowed origin.
        from app import main as _main

        exact = getattr(_main, "ALLOW_ORIGINS", []) or []
        pattern = getattr(_main, "ALLOW_ORIGIN_REGEX", None)
        if "*" in exact or origin in exact:
            allowed = True
        elif pattern:
            import re as _re

            if _re.fullmatch(pattern, origin):
                allowed = True
    except Exception:
        try:
            from app.core.config import settings

            raw = getattr(settings, "normalized_cors_origins", None) or getattr(
                settings, "BACKEND_CORS_ORIGINS", []
            )
            allowed = "*" in raw or origin in raw
        except Exception:
            allowed = False

    if allowed:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return {}


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Fallback handler for unexpected exceptions.

    This keeps API error responses consistent while avoiding exposure of
    internal implementation details. CORS headers are attached manually —
    this handler runs outside CORSMiddleware (see ``_cors_headers_for``).
    """
    _exc_logger.exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "An unexpected internal server error occurred.",
            "error_code": "INTERNAL_SERVER_ERROR",
            "detail": {
                "exception_type": exc.__class__.__name__,
            },
        },
        headers=_cors_headers_for(request),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register exception handlers on the FastAPI application.

    Args
    ----
    app:
        The FastAPI application instance.
    """
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(SQLAlchemyOperationalError, database_operational_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)