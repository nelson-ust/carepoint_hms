# app/api/v1/endpoints/system_routes.py
from __future__ import annotations

"""
Small system-information endpoints shared by both deployment modes.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.core.deployment import license_status

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/deployment-info",
            summary="Deployment mode and (dedicated mode) licence posture")
def deployment_info():
    """Public, non-sensitive: lets the frontend adapt its navigation and show
    licence renewal notices on dedicated installs."""
    lic = license_status()
    return {
        "success": True,
        "mode": "dedicated" if settings.is_dedicated else "saas",
        "hospital_name": settings.DEDICATED_TENANT_NAME if settings.is_dedicated else None,
        "license": {
            "licensed_until": lic["licensed_until"],
            "days_left": lic["days_left"],
            "in_grace": lic["in_grace"],
            "blocked": lic["blocked"],
            "message": lic["message"],
        } if settings.is_dedicated else None,
    }
