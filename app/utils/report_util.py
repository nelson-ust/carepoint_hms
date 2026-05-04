# utils/report_util.py
from __future__ import annotations

"""
Reporting and export utilities for Carepoint HMS.

Purpose
-------
This module centralizes helpers used for:

- CSV export generation
- JSON export generation
- lightweight report summarization
- report filename creation
- optional upload of generated reports to AWS S3

Typical use cases
-----------------
- patient list export
- billing summary export
- inventory report export
- ambulance dispatch report export
- HR and compliance report export
"""

import csv
import json
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

try:
    from app.utils.s3_utils import (
        build_s3_object_key,
        generate_presigned_url_file,
        upload_bytes_to_s3,
    )
except Exception:  # pragma: no cover
    build_s3_object_key = None
    generate_presigned_url_file = None
    upload_bytes_to_s3 = None


def _utc_now() -> datetime:
    """
    Return the current UTC datetime.
    """
    return datetime.now(timezone.utc)


def normalize_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Materialize an iterable of dictionaries into a list.

    Args:
        rows: Source iterable.

    Returns:
        list[dict[str, Any]]: Materialized rows.
    """
    return list(rows)


def get_fieldnames(
    rows: Sequence[dict[str, Any]],
    preferred_order: Optional[Sequence[str]] = None,
) -> list[str]:
    """
    Determine CSV/report fieldnames.

    Args:
        rows: Source rows.
        preferred_order: Optional explicit field ordering.

    Returns:
        list[str]: Final ordered fieldnames.
    """
    if not rows:
        return list(preferred_order or [])

    discovered: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in discovered:
                discovered.append(key)

    if not preferred_order:
        return discovered

    ordered: list[str] = []
    for field in preferred_order:
        if field in discovered and field not in ordered:
            ordered.append(field)

    for field in discovered:
        if field not in ordered:
            ordered.append(field)

    return ordered


def project_rows(
    rows: Iterable[dict[str, Any]],
    fields: Optional[Sequence[str]] = None,
) -> list[dict[str, Any]]:
    """
    Reduce rows to only the requested fields.

    Args:
        rows: Source rows.
        fields: Fields to keep.

    Returns:
        list[dict[str, Any]]: Projected rows.
    """
    materialized = normalize_rows(rows)

    if not fields:
        return materialized

    return [{field: row.get(field) for field in fields} for row in materialized]


def dicts_to_csv_string(
    rows: Iterable[dict[str, Any]],
    *,
    fieldnames: Optional[Sequence[str]] = None,
    include_header: bool = True,
) -> str:
    """
    Convert an iterable of dictionaries to a CSV string.

    Args:
        rows: Source rows.
        fieldnames: Optional explicit column order.
        include_header: Whether to include the CSV header row.

    Returns:
        str: CSV text.
    """
    materialized = normalize_rows(rows)
    resolved_fieldnames = get_fieldnames(materialized, fieldnames)

    if not resolved_fieldnames:
        return ""

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=resolved_fieldnames, extrasaction="ignore")

    if include_header:
        writer.writeheader()

    for row in materialized:
        writer.writerow({field: row.get(field) for field in resolved_fieldnames})

    return output.getvalue()


def dicts_to_csv_bytes(
    rows: Iterable[dict[str, Any]],
    *,
    fieldnames: Optional[Sequence[str]] = None,
    include_header: bool = True,
    encoding: str = "utf-8",
) -> bytes:
    """
    Convert rows to CSV bytes.

    Args:
        rows: Source rows.
        fieldnames: Optional explicit column order.
        include_header: Whether to include the header row.
        encoding: Output text encoding.

    Returns:
        bytes: Encoded CSV content.
    """
    csv_string = dicts_to_csv_string(
        rows,
        fieldnames=fieldnames,
        include_header=include_header,
    )
    return csv_string.encode(encoding)


def dicts_to_json_string(
    rows: Iterable[dict[str, Any]],
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
) -> str:
    """
    Convert rows to a JSON string.

    Args:
        rows: Source rows.
        indent: JSON indentation.
        ensure_ascii: Whether to escape non-ASCII characters.

    Returns:
        str: JSON text.
    """
    materialized = normalize_rows(rows)
    return json.dumps(materialized, indent=indent, ensure_ascii=ensure_ascii, default=str)


def dicts_to_json_bytes(
    rows: Iterable[dict[str, Any]],
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
    encoding: str = "utf-8",
) -> bytes:
    """
    Convert rows to JSON bytes.
    """
    return dicts_to_json_string(
        rows,
        indent=indent,
        ensure_ascii=ensure_ascii,
    ).encode(encoding)


def summarize_numeric_field(rows: Iterable[dict[str, Any]], field_name: str) -> float:
    """
    Sum a numeric field across rows.

    Args:
        rows: Source rows.
        field_name: Numeric field to sum.

    Returns:
        float: Total sum.
    """
    total = 0.0
    for row in rows:
        try:
            total += float(row.get(field_name, 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def average_numeric_field(rows: Iterable[dict[str, Any]], field_name: str) -> float:
    """
    Calculate the average value of a numeric field across rows.

    Returns:
        float: Average value, or 0.0 if no valid values exist.
    """
    values: list[float] = []

    for row in rows:
        try:
            values.append(float(row.get(field_name, 0) or 0))
        except (TypeError, ValueError):
            continue

    if not values:
        return 0.0

    return sum(values) / len(values)


def count_non_empty_field(rows: Iterable[dict[str, Any]], field_name: str) -> int:
    """
    Count rows where a field is present and non-empty.
    """
    count = 0
    for row in rows:
        value = row.get(field_name)
        if value not in (None, "", [], {}, ()):
            count += 1
    return count


def build_report_summary(
    rows: Iterable[dict[str, Any]],
    *,
    numeric_fields: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """
    Build a lightweight summary for a dataset.

    Args:
        rows: Source rows.
        numeric_fields: Optional numeric fields to summarize.

    Returns:
        dict[str, Any]: Summary payload.
    """
    materialized = normalize_rows(rows)
    summary: dict[str, Any] = {
        "row_count": len(materialized),
    }

    for field in numeric_fields or []:
        summary[field] = {
            "sum": summarize_numeric_field(materialized, field),
            "average": average_numeric_field(materialized, field),
        }

    return summary


def generate_report_filename(
    *,
    report_name: str,
    extension: str,
    prefix: Optional[str] = None,
    include_timestamp: bool = True,
) -> str:
    """
    Generate a safe report filename.

    Args:
        report_name: Report display name.
        extension: File extension such as 'csv', 'json', or '.csv'.
        prefix: Optional prefix.
        include_timestamp: Whether to append a UTC timestamp.

    Returns:
        str: Generated file name.
    """
    safe_report_name = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in report_name.strip().lower().replace(" ", "_")
    ).strip("_")

    safe_extension = extension if extension.startswith(".") else f".{extension}"
    parts: list[str] = []

    if prefix:
        parts.append(prefix.strip())

    parts.append(safe_report_name)

    if include_timestamp:
        parts.append(_utc_now().strftime("%Y%m%d%H%M%S"))

    return "_".join(part for part in parts if part) + safe_extension


def export_csv_report(
    rows: Iterable[dict[str, Any]],
    *,
    report_name: str,
    fieldnames: Optional[Sequence[str]] = None,
    prefix: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build a CSV report payload without uploading it.

    Returns:
        dict[str, Any]: Export payload with file name and bytes.
    """
    materialized = normalize_rows(rows)
    file_name = generate_report_filename(
        report_name=report_name,
        extension="csv",
        prefix=prefix,
    )
    content = dicts_to_csv_bytes(materialized, fieldnames=fieldnames)

    return {
        "file_name": file_name,
        "content_type": "text/csv",
        "content_bytes": content,
        "row_count": len(materialized),
    }


def export_json_report(
    rows: Iterable[dict[str, Any]],
    *,
    report_name: str,
    prefix: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build a JSON report payload without uploading it.
    """
    materialized = normalize_rows(rows)
    file_name = generate_report_filename(
        report_name=report_name,
        extension="json",
        prefix=prefix,
    )
    content = dicts_to_json_bytes(materialized)

    return {
        "file_name": file_name,
        "content_type": "application/json",
        "content_bytes": content,
        "row_count": len(materialized),
    }


def upload_report_to_s3(
    *,
    content_bytes: bytes,
    file_name: str,
    destination_dir: str,
    content_type: str,
    prefix: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
    generate_presigned_url_after_upload: bool = True,
    presigned_url_expiration: int = 3600,
) -> dict[str, Any]:
    """
    Upload generated report content to S3.

    Args:
        content_bytes: Report bytes.
        file_name: Final file name.
        destination_dir: S3 folder path.
        content_type: MIME type.
        prefix: Optional S3 key prefix.
        metadata: Optional S3 metadata.
        generate_presigned_url_after_upload: Whether to generate a presigned URL.
        presigned_url_expiration: Presigned URL expiration time in seconds.

    Returns:
        dict[str, Any]: Structured upload metadata.

    Raises:
        RuntimeError: If S3 utilities are unavailable.
    """
    if not all([build_s3_object_key, upload_bytes_to_s3]):
        raise RuntimeError("S3 utilities are not available.")

    object_key = build_s3_object_key(
        folder=destination_dir,
        filename=file_name,
        prefix=prefix,
        include_timestamp=True,
    )

    upload_result = upload_bytes_to_s3(
        data=content_bytes,
        object_name=object_key,
        file_name=file_name,
        content_type=content_type,
        metadata=metadata,
    )

    presigned_url = None
    if generate_presigned_url_after_upload:
        if not generate_presigned_url_file:
            raise RuntimeError("Presigned URL helper is unavailable.")
        presigned_url = generate_presigned_url_file(
            object_name=object_key,
            expiration=presigned_url_expiration,
        )

    return {
        **upload_result,
        "presigned_url": presigned_url,
    }


def export_and_upload_csv_report(
    rows: Iterable[dict[str, Any]],
    *,
    report_name: str,
    destination_dir: str,
    fieldnames: Optional[Sequence[str]] = None,
    file_prefix: Optional[str] = None,
    s3_prefix: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """
    Build a CSV report and upload it to S3.

    Returns:
        dict[str, Any]: Export and upload result.
    """
    report_payload = export_csv_report(
        rows,
        report_name=report_name,
        fieldnames=fieldnames,
        prefix=file_prefix,
    )

    upload_result = upload_report_to_s3(
        content_bytes=report_payload["content_bytes"],
        file_name=report_payload["file_name"],
        destination_dir=destination_dir,
        content_type=report_payload["content_type"],
        prefix=s3_prefix,
        metadata=metadata,
    )

    return {
        "report_name": report_name,
        "file_name": report_payload["file_name"],
        "content_type": report_payload["content_type"],
        "row_count": report_payload["row_count"],
        "upload": upload_result,
    }


def export_and_upload_json_report(
    rows: Iterable[dict[str, Any]],
    *,
    report_name: str,
    destination_dir: str,
    file_prefix: Optional[str] = None,
    s3_prefix: Optional[str] = None,
    metadata: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """
    Build a JSON report and upload it to S3.
    """
    report_payload = export_json_report(
        rows,
        report_name=report_name,
        prefix=file_prefix,
    )

    upload_result = upload_report_to_s3(
        content_bytes=report_payload["content_bytes"],
        file_name=report_payload["file_name"],
        destination_dir=destination_dir,
        content_type=report_payload["content_type"],
        prefix=s3_prefix,
        metadata=metadata,
    )

    return {
        "report_name": report_name,
        "file_name": report_payload["file_name"],
        "content_type": report_payload["content_type"],
        "row_count": report_payload["row_count"],
        "upload": upload_result,
    }