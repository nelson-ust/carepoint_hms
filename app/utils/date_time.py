from __future__ import annotations
"""Timezone-aware date and time helpers used across the application."""
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo
try:
    from app.core.config import settings
except Exception:
    settings = None
DEFAULT_TIMEZONE = getattr(settings, "DEFAULT_TIMEZONE", "Africa/Lagos") if settings else "Africa/Lagos"
def get_timezone(tz_name: Optional[str] = None) -> ZoneInfo:
    """Return the configured timezone."""
    return ZoneInfo(tz_name or DEFAULT_TIMEZONE)
def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)
def local_now(tz_name: Optional[str] = None) -> datetime:
    """Return the current local datetime."""
    return datetime.now(get_timezone(tz_name))
def to_local(dt: Optional[datetime], tz_name: Optional[str] = None) -> Optional[datetime]:
    """Convert a datetime to the requested timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(get_timezone(tz_name))
def to_utc(dt: Optional[datetime], tz_name: Optional[str] = None) -> Optional[datetime]:
    """Convert a datetime to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_timezone(tz_name))
    return dt.astimezone(timezone.utc)
def isoformat_or_none(dt: Optional[datetime], tz_name: Optional[str] = None) -> Optional[str]:
    """Return an ISO string or None."""
    return None if dt is None else to_local(dt, tz_name).isoformat()
def parse_iso_datetime(value: str, assume_tz: Optional[str] = None) -> datetime:
    """Parse an ISO string into a timezone-aware datetime."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=get_timezone(assume_tz))
    return parsed
def start_of_day(value: date | datetime, tz_name: Optional[str] = None) -> datetime:
    """Return the start of the supplied day."""
    tz = get_timezone(tz_name)
    if isinstance(value, datetime):
        value = to_local(value, tz_name).date()
    return datetime(value.year, value.month, value.day, 0, 0, 0, tzinfo=tz)
def end_of_day(value: date | datetime, tz_name: Optional[str] = None) -> datetime:
    """Return the end of the supplied day."""
    tz = get_timezone(tz_name)
    if isinstance(value, datetime):
        value = to_local(value, tz_name).date()
    return datetime(value.year, value.month, value.day, 23, 59, 59, 999999, tzinfo=tz)
