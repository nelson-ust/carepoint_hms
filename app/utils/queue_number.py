# utils/queue_number.py
from __future__ import annotations

"""
Queue number helpers for Carepoint HMS.

Purpose
-------
This module centralizes queue number generation and validation for service
delivery points such as:

- registration
- triage
- clinician consultation
- laboratory
- pharmacy
- billing/cashier

Design goals
------------
- generate predictable queue numbers
- keep format consistent across the application
- support parsing and validation
- allow future reuse in repositories and services

Default format
--------------
    PREFIX-YYYYMMDD-0001

Example
-------
    CLI-20260411-0001
"""

import re
from datetime import datetime
from typing import Optional

from .date_time import local_now


DEFAULT_QUEUE_PREFIX = "Q"
DEFAULT_SEQUENCE_PADDING = 4
DEFAULT_DATE_FORMAT = "%Y%m%d"

# Regex used to validate and parse queue numbers.
QUEUE_NUMBER_PATTERN = re.compile(
    r"^(?P<prefix>[A-Z0-9]+)-(?P<date>\d{8})-(?P<sequence>\d+)$"
)


def normalize_queue_prefix(prefix: Optional[str] = None) -> str:
    """
    Normalize a queue prefix.

    Args:
        prefix: Raw prefix value.

    Returns:
        str: Normalized uppercase prefix.

    Raises:
        ValueError: If the resulting prefix is invalid.
    """
    normalized = (prefix or DEFAULT_QUEUE_PREFIX).strip().upper()

    if not normalized:
        raise ValueError("Queue prefix cannot be empty.")

    # Keep only alphanumeric characters for predictable formatting.
    normalized = "".join(char for char in normalized if char.isalnum())

    if not normalized:
        raise ValueError("Queue prefix must contain at least one alphanumeric character.")

    return normalized


def validate_sequence(sequence: int) -> int:
    """
    Validate a queue sequence number.

    Args:
        sequence: Queue position/sequence value.

    Returns:
        int: Validated sequence.

    Raises:
        ValueError: If sequence is invalid.
    """
    if sequence <= 0:
        raise ValueError("Sequence must be greater than zero.")
    return sequence


def generate_queue_number(
    prefix: str | None = None,
    sequence: int = 1,
    when: datetime | None = None,
    *,
    padding: int = DEFAULT_SEQUENCE_PADDING,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> str:
    """
    Generate a queue number.

    Args:
        prefix: Optional service delivery point prefix.
        sequence: Running queue sequence number.
        when: Optional datetime for deterministic generation in tests.
        padding: Number of digits used to left-pad the sequence.
        date_format: Datetime format used for the date section.

    Returns:
        str: Generated queue number.

    Example:
        CLI-20260411-0001
    """
    sequence = validate_sequence(sequence)

    if padding <= 0:
        raise ValueError("Padding must be greater than zero.")

    current = when or local_now()
    normalized_prefix = normalize_queue_prefix(prefix)

    return f"{normalized_prefix}-{current.strftime(date_format)}-{sequence:0{padding}d}"


def generate_daily_queue_token(
    *,
    service_point_code: str | None = None,
    current_count: int = 0,
    when: datetime | None = None,
    padding: int = DEFAULT_SEQUENCE_PADDING,
) -> str:
    """
    Generate the next queue token for a service point.

    Args:
        service_point_code: Queue prefix/service point code.
        current_count: Current number of issued tokens for the day.
        when: Optional datetime override.
        padding: Sequence padding length.

    Returns:
        str: Next queue number.
    """
    next_sequence = current_count + 1
    return generate_queue_number(
        prefix=service_point_code,
        sequence=next_sequence,
        when=when,
        padding=padding,
    )


def parse_queue_number(queue_number: str) -> dict[str, str | int]:
    """
    Parse a queue number into its components.

    Args:
        queue_number: Queue number string.

    Returns:
        dict[str, str | int]:
            {
                "prefix": "CLI",
                "date": "20260411",
                "sequence": 1
            }

    Raises:
        ValueError: If the queue number format is invalid.
    """
    if not queue_number or not queue_number.strip():
        raise ValueError("Queue number cannot be empty.")

    match = QUEUE_NUMBER_PATTERN.match(queue_number.strip().upper())
    if not match:
        raise ValueError("Invalid queue number format.")

    return {
        "prefix": match.group("prefix"),
        "date": match.group("date"),
        "sequence": int(match.group("sequence")),
    }


def is_valid_queue_number(queue_number: str) -> bool:
    """
    Check whether a queue number matches the expected format.

    Args:
        queue_number: Queue number string.

    Returns:
        bool: True if valid, otherwise False.
    """
    try:
        parse_queue_number(queue_number)
        return True
    except ValueError:
        return False


def extract_queue_sequence(queue_number: str) -> int:
    """
    Extract the numeric sequence part of a queue number.

    Args:
        queue_number: Queue number string.

    Returns:
        int: Sequence number.
    """
    parsed = parse_queue_number(queue_number)
    return int(parsed["sequence"])


def extract_queue_prefix(queue_number: str) -> str:
    """
    Extract the prefix part of a queue number.

    Args:
        queue_number: Queue number string.

    Returns:
        str: Queue prefix.
    """
    parsed = parse_queue_number(queue_number)
    return str(parsed["prefix"])


def extract_queue_date(queue_number: str) -> str:
    """
    Extract the date part of a queue number.

    Args:
        queue_number: Queue number string.

    Returns:
        str: Date portion in YYYYMMDD format.
    """
    parsed = parse_queue_number(queue_number)
    return str(parsed["date"])




# get_unprocessed_finance_request