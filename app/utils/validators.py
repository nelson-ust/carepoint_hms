# utils/validators.py
from __future__ import annotations

"""
Validation helpers for common domain values.

Purpose
-------
This module centralizes lightweight validation and normalization helpers used
across schemas, services, repositories, and utilities.

Design goals
------------
- keep common validation logic in one place
- make error messages consistent
- support both boolean checks and raise-on-failure workflows
- remain framework-agnostic and reusable
"""

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Optional
from uuid import UUID


# ---------------------------------------------------------------------
# Regular expressions
# ---------------------------------------------------------------------

# Basic email pattern suitable for common application validation.
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Simple E.164-like phone pattern:
# - optional leading +
# - first digit after optional + cannot be 0
# - total digits between 8 and 15
PHONE_REGEX = re.compile(r"^\+?[1-9]\d{7,14}$")

# Username/code-like value: letters, numbers, underscore, dash, dot.
SAFE_CODE_REGEX = re.compile(r"^[A-Za-z0-9_.-]+$")


# ---------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------

def normalize_string(value: Optional[str]) -> Optional[str]:
    """
    Normalize a string by stripping leading/trailing whitespace.

    Args:
        value: Input string.

    Returns:
        Optional[str]: Normalized string, or None if input is None.
    """
    if value is None:
        return None
    return value.strip()


def normalize_email(value: Optional[str]) -> Optional[str]:
    """
    Normalize an email address.

    Args:
        value: Input email.

    Returns:
        Optional[str]: Lowercased and stripped email, or None.
    """
    normalized = normalize_string(value)
    return normalized.lower() if normalized else normalized


def normalize_phone_number(value: Optional[str]) -> Optional[str]:
    """
    Normalize a phone number by stripping spaces.

    Args:
        value: Raw phone number.

    Returns:
        Optional[str]: Normalized phone number, or None.
    """
    normalized = normalize_string(value)
    if normalized is None:
        return None
    return normalized.replace(" ", "")


# ---------------------------------------------------------------------
# Boolean validators
# ---------------------------------------------------------------------

def is_valid_email(value: Optional[str]) -> bool:
    """
    Return True if the value resembles an email address.
    """
    normalized = normalize_email(value)
    return bool(normalized and EMAIL_REGEX.match(normalized))


def is_valid_phone_number(value: Optional[str]) -> bool:
    """
    Validate a phone number using a simple E.164-like pattern.
    """
    normalized = normalize_phone_number(value)
    return bool(normalized and PHONE_REGEX.match(normalized))


def is_valid_uuid(value: Optional[str]) -> bool:
    """
    Return True if the supplied value is a valid UUID string.
    """
    if not value:
        return False
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def is_non_empty_string(value: Any) -> bool:
    """
    Return True if the value is a non-empty string after trimming.
    """
    return isinstance(value, str) and bool(value.strip())


def is_valid_code(value: Optional[str]) -> bool:
    """
    Return True if the value contains only safe code characters.

    Useful for:
    - role codes
    - department codes
    - object prefixes
    - identifiers that should avoid whitespace/symbol noise
    """
    normalized = normalize_string(value)
    return bool(normalized and SAFE_CODE_REGEX.match(normalized))


def is_valid_date_range(start_date: date | datetime, end_date: date | datetime) -> bool:
    """
    Return True if start_date is less than or equal to end_date.
    """
    return start_date <= end_date


# ---------------------------------------------------------------------
# Raise-on-failure validators
# ---------------------------------------------------------------------

def ensure_required(value: object, field_name: str) -> None:
    """
    Raise ValueError when a required value is missing.

    Args:
        value: Value to validate.
        field_name: Name used in the error message.
    """
    if value is None:
        raise ValueError(f"{field_name} is required.")

    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{field_name} is required.")


def ensure_valid_email(value: Optional[str], field_name: str = "Email") -> str:
    """
    Validate and return a normalized email address.

    Raises:
        ValueError: If the email is invalid.
    """
    normalized = normalize_email(value)
    if not is_valid_email(normalized):
        raise ValueError(f"{field_name} is invalid.")
    return normalized  # type: ignore[return-value]


def ensure_valid_phone_number(value: Optional[str], field_name: str = "Phone number") -> str:
    """
    Validate and return a normalized phone number.

    Raises:
        ValueError: If the phone number is invalid.
    """
    normalized = normalize_phone_number(value)
    if not is_valid_phone_number(normalized):
        raise ValueError(f"{field_name} is invalid.")
    return normalized  # type: ignore[return-value]


def ensure_valid_uuid(value: Optional[str], field_name: str = "UUID") -> str:
    """
    Validate a UUID string and return it.

    Raises:
        ValueError: If invalid.
    """
    if not is_valid_uuid(value):
        raise ValueError(f"{field_name} is invalid.")
    return str(value)


def ensure_min_length(value: Optional[str], min_length: int, field_name: str) -> str:
    """
    Ensure a string meets a minimum length.

    Raises:
        ValueError: If too short.
    """
    normalized = normalize_string(value)
    ensure_required(normalized, field_name)

    if len(normalized) < min_length:  # type: ignore[arg-type]
        raise ValueError(f"{field_name} must be at least {min_length} characters long.")

    return normalized  # type: ignore[return-value]


def ensure_max_length(value: Optional[str], max_length: int, field_name: str) -> str:
    """
    Ensure a string does not exceed a maximum length.

    Raises:
        ValueError: If too long.
    """
    normalized = normalize_string(value)
    ensure_required(normalized, field_name)

    if len(normalized) > max_length:  # type: ignore[arg-type]
        raise ValueError(f"{field_name} must not exceed {max_length} characters.")

    return normalized  # type: ignore[return-value]


def ensure_valid_code(value: Optional[str], field_name: str = "Code") -> str:
    """
    Ensure a value is a valid safe code.

    Raises:
        ValueError: If invalid.
    """
    normalized = normalize_string(value)
    ensure_required(normalized, field_name)

    if not is_valid_code(normalized):
        raise ValueError(
            f"{field_name} may only contain letters, numbers, underscore, dash, or dot."
        )

    return normalized  # type: ignore[return-value]


def validate_positive_number(value: int | float, field_name: str) -> None:
    """
    Raise ValueError when a number is not positive.
    """
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")


def validate_non_negative_number(value: int | float, field_name: str) -> None:
    """
    Raise ValueError when a number is negative.
    """
    if value < 0:
        raise ValueError(f"{field_name} must not be negative.")


def validate_numeric_range(
    value: int | float,
    *,
    min_value: Optional[int | float] = None,
    max_value: Optional[int | float] = None,
    field_name: str = "Value",
) -> None:
    """
    Validate that a numeric value falls within an optional range.
    """
    if min_value is not None and value < min_value:
        raise ValueError(f"{field_name} must be at least {min_value}.")

    if max_value is not None and value > max_value:
        raise ValueError(f"{field_name} must not exceed {max_value}.")


def validate_date_range(
    *,
    start_date: date | datetime,
    end_date: date | datetime,
    start_field_name: str = "Start date",
    end_field_name: str = "End date",
) -> None:
    """
    Validate that start_date is not later than end_date.

    Raises:
        ValueError: If the range is invalid.
    """
    if start_date > end_date:
        raise ValueError(f"{start_field_name} cannot be later than {end_field_name}.")


# ---------------------------------------------------------------------
# File validators
# ---------------------------------------------------------------------

def normalize_extensions(allowed_extensions: Iterable[str]) -> set[str]:
    """
    Normalize allowed file extensions to lowercase dotted values.

    Example:
        ["pdf", ".jpg"] -> {".pdf", ".jpg"}
    """
    return {
        ext.lower() if str(ext).startswith(".") else f".{str(ext).lower()}"
        for ext in allowed_extensions
    }


def validate_file_extension(filename: str, allowed_extensions: Iterable[str]) -> bool:
    """
    Check whether a filename ends with an allowed extension.

    Args:
        filename: File name to validate.
        allowed_extensions: Iterable of allowed extensions.

    Returns:
        bool: True if allowed.
    """
    ext = Path(filename).suffix.lower()
    allowed = normalize_extensions(allowed_extensions)
    return ext in allowed


def ensure_valid_file_extension(
    filename: str,
    allowed_extensions: Iterable[str],
    field_name: str = "File",
) -> str:
    """
    Validate a file extension and return the filename.

    Raises:
        ValueError: If the extension is not allowed.
    """
    if not validate_file_extension(filename, allowed_extensions):
        allowed = ", ".join(sorted(normalize_extensions(allowed_extensions)))
        raise ValueError(f"{field_name} type is not allowed. Allowed types: {allowed}")
    return filename


def validate_mime_type(content_type: Optional[str], allowed_types: Iterable[str]) -> bool:
    """
    Check whether a MIME/content type is allowed.

    Args:
        content_type: MIME type such as 'application/pdf'.
        allowed_types: Allowed MIME types.

    Returns:
        bool: True if allowed.
    """
    if not content_type:
        return False

    normalized_content_type = content_type.strip().lower()
    normalized_allowed = {item.strip().lower() for item in allowed_types if item}
    return normalized_content_type in normalized_allowed


def ensure_valid_mime_type(
    content_type: Optional[str],
    allowed_types: Iterable[str],
    field_name: str = "File",
) -> str:
    """
    Validate a MIME type and return it.

    Raises:
        ValueError: If MIME type is not allowed.
    """
    if not validate_mime_type(content_type, allowed_types):
        allowed = ", ".join(sorted({item.strip().lower() for item in allowed_types if item}))
        raise ValueError(f"{field_name} MIME type is not allowed. Allowed types: {allowed}")
    return content_type.strip()  # type: ignore[union-attr]


# ---------------------------------------------------------------------
# Generic collection / choice validators
# ---------------------------------------------------------------------

def ensure_in_choices(value: Any, choices: Iterable[Any], field_name: str) -> Any:
    """
    Ensure a value is one of the allowed choices.

    Raises:
        ValueError: If the value is not in the choices.
    """
    allowed = list(choices)
    if value not in allowed:
        raise ValueError(f"{field_name} must be one of: {allowed}")
    return value


def ensure_not_empty_collection(value: Any, field_name: str) -> None:
    """
    Ensure a collection is not empty.

    Raises:
        ValueError: If the collection is empty or None.
    """
    if value is None:
        raise ValueError(f"{field_name} is required.")

    try:
        if len(value) == 0:
            raise ValueError(f"{field_name} must not be empty.")
    except TypeError as exc:
        raise ValueError(f"{field_name} must be a valid collection.") from exc