# app/utils/storage.py
"""
Local filesystem storage helpers for user-uploaded assets.

The API serves these files as static content from the ``/uploads`` mount (see
``app/main.py``). Both the mount and the writers below resolve the *same* base
directory so a file written here is reachable at ``/uploads/<relative-path>``.

Resolution order for the base directory:
    1. ``settings.UPLOADS_DIR`` (env ``UPLOADS_DIR`` / ``CAREPOINT_HMS_UPLOADS_DIR``)
    2. ``<cwd>/uploads`` as a sensible default so uploads work out of the box.
"""
from __future__ import annotations

import os

from app.core.config import settings


def uploads_base_dir() -> str:
    """Return (creating if needed) the base directory for uploaded assets."""
    base = getattr(settings, "UPLOADS_DIR", None) or os.path.join(os.getcwd(), "uploads")
    os.makedirs(base, exist_ok=True)
    return base


def tenant_logos_dir() -> str:
    """Return (creating if needed) the directory for tenant branding logos."""
    path = os.path.join(uploads_base_dir(), "tenant_logos")
    os.makedirs(path, exist_ok=True)
    return path
