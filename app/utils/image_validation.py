# app/utils/image_validation.py
from __future__ import annotations

"""
Content-based (magic-byte) image validation.

Extension and ``Content-Type`` are client-supplied and trivially spoofable, so
a file named ``avatar.png`` can actually be HTML/SVG/script. When such a file
is later served from the public ``/uploads`` mount it becomes a stored-XSS or
content-confusion vector. These helpers inspect the real bytes and only accept
genuine raster image formats (SVG is intentionally excluded — it is XML/script).
"""

from typing import Optional

# Allowed raster image formats, keyed by the canonical extension we store.
_ALLOWED = {"png", "jpeg", "gif", "webp"}


def sniff_image_type(raw: bytes) -> Optional[str]:
    """
    Return the detected image type ("png" | "jpeg" | "gif" | "webp") from the
    file's magic bytes, or ``None`` if the content is not a supported image.
    """
    if not raw or len(raw) < 12:
        return None

    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if raw[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return None


def assert_valid_image(raw: bytes) -> str:
    """
    Validate ``raw`` is a genuine supported image and return its canonical
    extension. Raises ``BadRequestError`` otherwise.
    """
    from app.core.exceptions import BadRequestError

    detected = sniff_image_type(raw)
    if detected is None or detected not in _ALLOWED:
        raise BadRequestError(
            message="The uploaded file is not a valid image (png, jpg, gif or webp)."
        )
    return "jpg" if detected == "jpeg" else detected
