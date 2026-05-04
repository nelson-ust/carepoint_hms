# utils/pagination.py
from __future__ import annotations

"""
Pagination helpers for list endpoints and repository queries.

Purpose
-------
This module centralizes pagination logic for API endpoints, repositories,
and service-layer query responses.

Supported styles
----------------
1. Offset-based pagination
   - Uses `skip` and `limit`
   - Good for SQLAlchemy `.offset(skip).limit(limit)`

2. Page-based pagination
   - Uses `page` and `page_size`
   - Good for frontend-friendly pagination

Design goals
------------
- normalize invalid pagination inputs safely
- provide consistent pagination metadata
- support repository and route usage
- keep helpers framework-agnostic
"""

from math import ceil
from typing import Any, Iterable, Optional


DEFAULT_SKIP = 0
DEFAULT_LIMIT = 20
DEFAULT_PAGE = 1
DEFAULT_MAX_LIMIT = 100
DEFAULT_SORT_DIRECTION = "asc"


def get_offset(skip: int = DEFAULT_SKIP) -> int:
    """
    Return a normalized offset value.

    Args:
        skip: Raw offset value.

    Returns:
        int: Non-negative offset.
    """
    if skip is None:
        return DEFAULT_SKIP
    return max(int(skip), 0)


def get_limit(limit: int = DEFAULT_LIMIT, max_limit: int = DEFAULT_MAX_LIMIT) -> int:
    """
    Return a normalized limit constrained by max_limit.

    Args:
        limit: Requested page size.
        max_limit: Maximum allowed page size.

    Returns:
        int: Safe limit value.
    """
    if limit is None or int(limit) <= 0:
        return DEFAULT_LIMIT

    safe_limit = int(limit)
    safe_max_limit = max(int(max_limit), 1)
    return min(safe_limit, safe_max_limit)


def get_page(page: int = DEFAULT_PAGE) -> int:
    """
    Return a normalized page number.

    Args:
        page: Requested page number.

    Returns:
        int: Page number, minimum 1.
    """
    if page is None:
        return DEFAULT_PAGE
    return max(int(page), 1)


def get_skip_from_page(page: int = DEFAULT_PAGE, page_size: int = DEFAULT_LIMIT) -> int:
    """
    Convert page/page_size values into a skip/offset value.

    Args:
        page: Page number.
        page_size: Number of records per page.

    Returns:
        int: Offset value.
    """
    normalized_page = get_page(page)
    normalized_limit = get_limit(page_size)
    return (normalized_page - 1) * normalized_limit


def get_page_from_skip(skip: int = DEFAULT_SKIP, limit: int = DEFAULT_LIMIT) -> int:
    """
    Convert skip/limit values into a current page number.

    Args:
        skip: Offset value.
        limit: Page size.

    Returns:
        int: Derived current page number.
    """
    normalized_skip = get_offset(skip)
    normalized_limit = get_limit(limit)
    return (normalized_skip // normalized_limit) + 1


def normalize_pagination_params(
    *,
    skip: Optional[int] = None,
    limit: Optional[int] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    max_limit: int = DEFAULT_MAX_LIMIT,
) -> dict[str, int]:
    """
    Normalize pagination parameters from either offset-based or page-based input.

    Rules
    -----
    - If `page` or `page_size` is provided, page-based pagination takes priority.
    - Otherwise, offset-based pagination is used.

    Returns:
        dict[str, int]:
            {
                "skip": ...,
                "limit": ...,
                "page": ...,
                "page_size": ...
            }
    """
    if page is not None or page_size is not None:
        normalized_page = get_page(page or DEFAULT_PAGE)
        normalized_page_size = get_limit(page_size or DEFAULT_LIMIT, max_limit=max_limit)
        normalized_skip = get_skip_from_page(normalized_page, normalized_page_size)
        return {
            "skip": normalized_skip,
            "limit": normalized_page_size,
            "page": normalized_page,
            "page_size": normalized_page_size,
        }

    normalized_skip = get_offset(skip or DEFAULT_SKIP)
    normalized_limit = get_limit(limit or DEFAULT_LIMIT, max_limit=max_limit)
    derived_page = get_page_from_skip(normalized_skip, normalized_limit)

    return {
        "skip": normalized_skip,
        "limit": normalized_limit,
        "page": derived_page,
        "page_size": normalized_limit,
    }


def build_pagination_meta(
    *,
    total: int,
    skip: int,
    limit: int,
) -> dict[str, Any]:
    """
    Build common pagination metadata.

    Args:
        total: Total number of available records.
        skip: Offset used for the current result set.
        limit: Page size used for the current result set.

    Returns:
        dict[str, Any]: Pagination metadata.
    """
    normalized_total = max(int(total), 0)
    normalized_skip = get_offset(skip)
    normalized_limit = get_limit(limit)

    current_page = get_page_from_skip(normalized_skip, normalized_limit)
    total_pages = ceil(normalized_total / normalized_limit) if normalized_limit else 1

    return {
        "total": normalized_total,
        "skip": normalized_skip,
        "limit": normalized_limit,
        "current_page": current_page,
        "page_size": normalized_limit,
        "total_pages": total_pages,
        "has_next": normalized_skip + normalized_limit < normalized_total,
        "has_previous": normalized_skip > 0,
        "next_skip": normalized_skip + normalized_limit if normalized_skip + normalized_limit < normalized_total else None,
        "previous_skip": max(normalized_skip - normalized_limit, 0) if normalized_skip > 0 else None,
    }


def paginate_response(
    *,
    items: list[Any],
    total: int,
    skip: int,
    limit: int,
    message: Optional[str] = None,
) -> dict[str, Any]:
    """
    Return a paginated response payload.

    Args:
        items: Current page items.
        total: Total number of available items.
        skip: Offset used.
        limit: Page size used.
        message: Optional response message.

    Returns:
        dict[str, Any]: Response payload with items and meta.
    """
    return {
        "success": True,
        "message": message or "Records fetched successfully.",
        "items": items,
        "count": len(items),
        "meta": build_pagination_meta(total=total, skip=skip, limit=limit),
    }


def paginate_iterable(
    items: Iterable[Any],
    *,
    skip: int = DEFAULT_SKIP,
    limit: int = DEFAULT_LIMIT,
) -> list[Any]:
    """
    Paginate an in-memory iterable.

    Useful for:
    - small in-memory lists
    - mock data
    - post-processed results

    Args:
        items: Source iterable.
        skip: Offset.
        limit: Maximum number of items to return.

    Returns:
        list[Any]: Sliced result list.
    """
    materialized = list(items)
    normalized_skip = get_offset(skip)
    normalized_limit = get_limit(limit)
    return materialized[normalized_skip: normalized_skip + normalized_limit]


def build_sort_meta(
    *,
    sort_by: Optional[str] = None,
    sort_direction: str = DEFAULT_SORT_DIRECTION,
) -> dict[str, Optional[str]]:
    """
    Build sorting metadata.

    Args:
        sort_by: Field used for sorting.
        sort_direction: Sort direction, usually 'asc' or 'desc'.

    Returns:
        dict[str, Optional[str]]: Sorting metadata.
    """
    direction = (sort_direction or DEFAULT_SORT_DIRECTION).strip().lower()
    if direction not in {"asc", "desc"}:
        direction = DEFAULT_SORT_DIRECTION

    return {
        "sort_by": sort_by,
        "sort_direction": direction,
    }


def build_paginated_response_with_sort(
    *,
    items: list[Any],
    total: int,
    skip: int,
    limit: int,
    sort_by: Optional[str] = None,
    sort_direction: str = DEFAULT_SORT_DIRECTION,
    message: Optional[str] = None,
) -> dict[str, Any]:
    """
    Return a paginated response that also includes sorting metadata.
    """
    response = paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message=message,
    )
    response["meta"]["sort"] = build_sort_meta(
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
    return response