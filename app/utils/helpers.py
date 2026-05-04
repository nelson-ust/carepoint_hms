from __future__ import annotations
"""General helper functions used across the application."""
import re
import uuid
from decimal import Decimal
from typing import Any, Iterable, Optional
def generate_uuid_str() -> str:
    """Return a UUID4 string."""
    return str(uuid.uuid4())
def compact_whitespace(value: Optional[str]) -> Optional[str]:
    """Normalize whitespace in a string."""
    if value is None:
        return None
    return re.sub(r"\s+", " ", value).strip()
def slugify(value: str) -> str:
    """Convert text into a simple slug."""
    cleaned = compact_whitespace(value or "") or ""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", cleaned.lower())
    return cleaned.strip("-")
def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Safely convert to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
def safe_decimal(value: Any, default: Optional[Decimal] = None) -> Optional[Decimal]:
    """Safely convert to Decimal."""
    try:
        return Decimal(str(value))
    except Exception:
        return default
def chunk_list(items: list[Any], chunk_size: int) -> list[list[Any]]:
    """Split a list into chunks."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
def first_or_none(values: Iterable[Any]) -> Any | None:
    """Return the first item or None."""
    for value in values:
        return value
    return None
def remove_none_values(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove keys whose values are None."""
    return {k: v for k, v in payload.items() if v is not None}
def get_full_name(first_name: str, last_name: str, middle_name: Optional[str] = None) -> str:
    """Build a full name from parts."""
    return " ".join(part.strip() for part in [first_name, middle_name, last_name] if part and part.strip())
