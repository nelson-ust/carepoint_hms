# carepoint_hms/app/core/logger.py
from __future__ import annotations

"""
carepoint_hms.app.core.logger

Centralized logging configuration for Carepoint HMS.

Purpose
-------
This module provides a shared logging setup for the application so that all
modules use a consistent log format, log level, and handler configuration.

Features
--------
- application-wide logger configuration
- console logging by default
- optional file logging
- request ID support through LoggerAdapter
- protection against duplicate handlers
- helper functions for retrieving named loggers

Typical usage
-------------
Example:

    from app.core.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Application started")

For request-scoped logging:

    from app.core.logger import get_request_logger

    logger = get_request_logger(__name__, request_id="abc-123")
    logger.info("Processing request")
"""

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional

try:
    from app.core.config import settings
except Exception:  # pragma: no cover
    settings = None


# ---------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------

DEFAULT_LOGGER_NAME = "carepoint_hms"
DEFAULT_LOG_LEVEL = getattr(settings, "LOG_LEVEL", "INFO") if settings else "INFO"
DEFAULT_LOG_DIR = Path("logs")
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "carepoint_hms.log"

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | "
    "%(request_id)s%(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class RequestIdFilter(logging.Filter):
    """
    Logging filter that ensures every log record has a request_id field.

    This prevents formatter failures when a log record is emitted without
    request-specific context.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # If request_id is missing, provide an empty formatted value.
        if not hasattr(record, "request_id"):
            record.request_id = ""
        elif record.request_id:
            record.request_id = f"[request_id={record.request_id}] "
        else:
            record.request_id = ""
        return True


class RequestLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that injects a request ID into log records.
    """

    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        extra["request_id"] = self.extra.get("request_id")
        return msg, kwargs


def _normalize_log_level(level: str | int) -> int:
    """
    Convert a log level name or integer into a logging level integer.
    """
    if isinstance(level, int):
        return level

    normalized = str(level).strip().upper()
    return getattr(logging, normalized, logging.INFO)


def _build_formatter() -> logging.Formatter:
    """
    Create the application log formatter.
    """
    return logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)


def _build_stream_handler(level: int) -> logging.Handler:
    """
    Create a console log handler.
    """
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(_build_formatter())
    handler.addFilter(RequestIdFilter())
    return handler


def _build_file_handler(
    log_file: str | Path,
    level: int,
    *,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Handler:
    """
    Create a rotating file handler.

    Args:
        log_file: Target log file path.
        level: Logging level.
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of rotated log files to keep.
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(_build_formatter())
    handler.addFilter(RequestIdFilter())
    return handler


def configure_logging(
    *,
    logger_name: str = DEFAULT_LOGGER_NAME,
    level: str | int = DEFAULT_LOG_LEVEL,
    enable_console: bool = True,
    enable_file: bool = False,
    log_file: str | Path = DEFAULT_LOG_FILE,
) -> logging.Logger:
    """
    Configure and return the application logger.

    This function is safe to call multiple times. It avoids adding duplicate
    handlers to the same logger.

    Args:
        logger_name: Root application logger name.
        level: Logging level name or integer.
        enable_console: Whether to enable console logging.
        enable_file: Whether to enable file logging.
        log_file: File path to use when file logging is enabled.

    Returns:
        logging.Logger: Configured logger instance.
    """
    resolved_level = _normalize_log_level(level)
    logger = logging.getLogger(logger_name)
    logger.setLevel(resolved_level)
    logger.propagate = False

    # Prevent duplicate handlers when called repeatedly.
    if logger.handlers:
        return logger

    if enable_console:
        logger.addHandler(_build_stream_handler(resolved_level))

    if enable_file:
        logger.addHandler(_build_file_handler(log_file, resolved_level))

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Return a logger instance.

    If the root application logger has not yet been configured, this function
    configures it using settings/defaults first.

    Args:
        name: Optional logger name. If omitted, the default application logger
              is returned.
    """
    enable_file = False
    log_file = DEFAULT_LOG_FILE

    if settings:
        # Optional flags from settings if present.
        enable_file = bool(getattr(settings, "LOG_TO_FILE", False))
        log_file = Path(getattr(settings, "LOG_FILE_PATH", str(DEFAULT_LOG_FILE)))

    configure_logging(
        logger_name=DEFAULT_LOGGER_NAME,
        level=DEFAULT_LOG_LEVEL,
        enable_console=True,
        enable_file=enable_file,
        log_file=log_file,
    )

    return logging.getLogger(name or DEFAULT_LOGGER_NAME)


def get_request_logger(name: Optional[str] = None, request_id: Optional[str] = None) -> RequestLoggerAdapter:
    """
    Return a request-aware logger adapter.

    Args:
        name: Optional logger name.
        request_id: Optional request identifier.
    """
    logger = get_logger(name)
    return RequestLoggerAdapter(logger, {"request_id": request_id})


def set_log_level(level: str | int, logger_name: str = DEFAULT_LOGGER_NAME) -> None:
    """
    Update the log level for the target logger and all attached handlers.
    """
    resolved_level = _normalize_log_level(level)
    logger = logging.getLogger(logger_name)
    logger.setLevel(resolved_level)

    for handler in logger.handlers:
        handler.setLevel(resolved_level)


def get_uvicorn_log_config() -> dict:
    """
    Return a basic logging config dictionary suitable for uvicorn.

    This is useful if you want uvicorn to use the same formatter style as the
    rest of the application.
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id_filter": {
                "()": "app.core.logger.RequestIdFilter",
            }
        },
        "formatters": {
            "default": {
                "format": LOG_FORMAT,
                "datefmt": DATE_FORMAT,
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "filters": ["request_id_filter"],
            }
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": DEFAULT_LOG_LEVEL, "propagate": False},
            "uvicorn.error": {"handlers": ["default"], "level": DEFAULT_LOG_LEVEL, "propagate": False},
            "uvicorn.access": {"handlers": ["default"], "level": DEFAULT_LOG_LEVEL, "propagate": False},
            DEFAULT_LOGGER_NAME: {"handlers": ["default"], "level": DEFAULT_LOG_LEVEL, "propagate": False},
        },
    }


# Configure the base application logger on import so it is ready early.
configure_logging(
    logger_name=DEFAULT_LOGGER_NAME,
    level=DEFAULT_LOG_LEVEL,
    enable_console=True,
    enable_file=bool(getattr(settings, "LOG_TO_FILE", False)) if settings else False,
    log_file=Path(getattr(settings, "LOG_FILE_PATH", str(DEFAULT_LOG_FILE))) if settings else DEFAULT_LOG_FILE,
)