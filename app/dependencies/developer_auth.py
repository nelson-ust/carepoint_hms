# app/dependencies/developer_auth.py
from __future__ import annotations

"""
Authentication for the self-service developer platform.

Two distinct credentials, deliberately separated:

* Dashboard / management token (``cpm_...``) — long-lived, issued once at email
  verification. Authenticates a developer's portal calls (create / list / revoke
  apps, request data grants). Presented as ``X-Developer-Token`` or
  ``Authorization: Bearer``.
* App API key (``cpk_...``) — one per app. Authenticates *data* calls only, so a
  leaked data key cannot mint new keys.
"""

from typing import Optional

from fastapi import Header, HTTPException, Request, status

from app.services.developer_service import DeveloperService


def _bearer(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def require_developer_dashboard(
    request: Request,
    x_developer_token: Optional[str] = Header(None, alias="X-Developer-Token"),
) -> dict:
    token = x_developer_token or _bearer(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Developer dashboard token required.")
    account = DeveloperService().resolve_account_by_dashboard_token(token)
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or inactive developer dashboard token.")
    return account


def require_developer_app(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> dict:
    key = x_api_key or _bearer(request)
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required.")
    return DeveloperService().authenticate_app(key=key)
