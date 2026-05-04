# utils/visit_code.py
from __future__ import annotations

"""
Visit code helpers for Carepoint HMS.

Purpose
-------
This module centralizes visit code generation and validation for patient visits.

Design goals
------------
- generate predictable visit codes
- keep visit code formatting consistent across the application
- support parsing and validation
- allow safe fallback generation when patient identifier is unavailable

Default format
--------------
    VIS-YYYYMMDD-HHMMSS-SUFFIX

Example
-------
    VIS-20260412-154530-12345
"""

import re
import secrets
import string
from datetime import datetime
from typing import Optional

from .date_time import local_now


DEFAULT_VISIT_PREFIX = "VIS"
DEFAULT_FALLBACK_SUFFIX = "GEN"
DEFAULT_RANDOM_SUFFIX_LENGTH = 6

VISIT_CODE_PATTERN = re.compile(
    r"^(?P<prefix>[A-Z0-9]+)-(?P<date>\d{8})-(?P<time>\d{6})-(?P<suffix>[A-Z0-9_-]+)$"
)


def normalize_visit_prefix(prefix: Optional[str] = None) -> str:
    """
    Normalize a visit code prefix.

    Args:
        prefix: Raw prefix value.

    Returns:
        str: Uppercase normalized prefix.

    Raises:
        ValueError: If the prefix becomes empty after normalization.
    """
    normalized = (prefix or DEFAULT_VISIT_PREFIX).strip().upper()
    normalized = "".join(char for char in normalized if char.isalnum())

    if not normalized:
        raise ValueError("Visit code prefix cannot be empty.")

    return normalized


def normalize_visit_suffix(
    patient_identifier: str | int | None = None,
    *,
    fallback_suffix: str = DEFAULT_FALLBACK_SUFFIX,
) -> str:
    """
    Normalize the suffix used in a visit code.

    Args:
        patient_identifier: Patient identifier or similar value.
        fallback_suffix: Value to use if identifier is missing.

    Returns:
        str: Safe normalized suffix.
    """
    if patient_identifier is None:
        suffix = fallback_suffix
    else:
        suffix = str(patient_identifier).strip()

    suffix = suffix.upper()
    suffix = "".join(char for char in suffix if char.isalnum() or char in {"_", "-"})

    if not suffix:
        suffix = fallback_suffix

    return suffix


def generate_random_visit_suffix(length: int = DEFAULT_RANDOM_SUFFIX_LENGTH) -> str:
    """
    Generate a random fallback suffix.

    Args:
        length: Number of characters in the suffix.

    Returns:
        str: Random uppercase alphanumeric suffix.
    """
    if length <= 0:
        raise ValueError("Random suffix length must be greater than zero.")

    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_visit_code(
    patient_identifier: str | int | None = None,
    when: datetime | None = None,
    *,
    prefix: str | None = None,
    use_random_suffix_when_missing: bool = False,
    random_suffix_length: int = DEFAULT_RANDOM_SUFFIX_LENGTH,
) -> str:
    """
    Generate a visit code.

    Args:
        patient_identifier: Optional patient identifier.
        when: Optional datetime override for deterministic testing.
        prefix: Optional visit code prefix.
        use_random_suffix_when_missing: Whether to generate a random suffix when
            patient_identifier is missing.
        random_suffix_length: Length of random suffix when enabled.

    Returns:
        str: Generated visit code.

    Example:
        VIS-20260412-154530-12345
    """
    current = when or local_now()
    normalized_prefix = normalize_visit_prefix(prefix)

    if patient_identifier is None and use_random_suffix_when_missing:
        suffix = generate_random_visit_suffix(random_suffix_length)
    else:
        suffix = normalize_visit_suffix(patient_identifier)

    return f"{normalized_prefix}-{current.strftime('%Y%m%d')}-{current.strftime('%H%M%S')}-{suffix}"


def parse_visit_code(visit_code: str) -> dict[str, str]:
    """
    Parse a visit code into its components.

    Args:
        visit_code: Visit code string.

    Returns:
        dict[str, str]:
            {
                "prefix": "VIS",
                "date": "20260412",
                "time": "154530",
                "suffix": "12345"
            }

    Raises:
        ValueError: If the format is invalid.
    """
    if not visit_code or not visit_code.strip():
        raise ValueError("Visit code cannot be empty.")

    match = VISIT_CODE_PATTERN.match(visit_code.strip().upper())
    if not match:
        raise ValueError("Invalid visit code format.")

    return {
        "prefix": match.group("prefix"),
        "date": match.group("date"),
        "time": match.group("time"),
        "suffix": match.group("suffix"),
    }


def is_valid_visit_code(visit_code: str) -> bool:
    """
    Check whether a visit code matches the expected format.

    Args:
        visit_code: Visit code string.

    Returns:
        bool: True if valid, otherwise False.
    """
    try:
        parse_visit_code(visit_code)
        return True
    except ValueError:
        return False


def extract_visit_suffix(visit_code: str) -> str:
    """
    Extract the suffix part of a visit code.

    Args:
        visit_code: Visit code string.

    Returns:
        str: Visit suffix.
    """
    return parse_visit_code(visit_code)["suffix"]


def extract_visit_prefix(visit_code: str) -> str:
    """
    Extract the prefix part of a visit code.

    Args:
        visit_code: Visit code string.

    Returns:
        str: Visit prefix.
    """
    return parse_visit_code(visit_code)["prefix"]


def extract_visit_datetime_parts(visit_code: str) -> dict[str, str]:
    """
    Extract date and time parts from a visit code.

    Args:
        visit_code: Visit code string.

    Returns:
        dict[str, str]:
            {
                "date": "20260412",
                "time": "154530"
            }
    """
    parsed = parse_visit_code(visit_code)
    return {
        "date": parsed["date"],
        "time": parsed["time"],
    }