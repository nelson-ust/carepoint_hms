# app/api/v1/endpoints/deployment_routes.py
from __future__ import annotations

"""
Per-tenant deployment mode: each hospital opts into cloud (online-only),
onprem (offline/on-premise) or hybrid. The mode governs file storage, offline
2FA and subscription validation (see app/core/tenant_mode.py).
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import tenant_mode
from app.core.database import get_master_db
from app.core.dependencies import AdminUser, CurrentActiveUser
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.multitenancy import get_current_tenant_id
from app.models.all_models import Tenant
from pydantic import BaseModel, Field

router = APIRouter(prefix="/deployment", tags=["Deployment"])


class ModeSchema(BaseModel):
    mode: str = Field(..., description="cloud | onprem | hybrid (synonyms: online/offline accepted).")


def _effective(mode: str) -> dict:
    return {
        "mode": mode,
        "file_storage": tenant_mode.storage_backend_for(mode, online=True) + " online / "
        + tenant_mode.storage_backend_for(mode, online=False) + " offline",
        "two_factor_skipped_offline": tenant_mode.skip_2fa_when_offline(mode),
        "offline_licence_lease": tenant_mode.enforce_lease(mode),
        "offline_capable": tenant_mode.offline_capable(mode),
    }


@router.get("/mode", summary="This hospital's deployment mode + effective behaviour")
def get_mode(_: CurrentActiveUser):
    return _effective(tenant_mode.current_mode())


@router.put("/mode", summary="Set this hospital's deployment mode (admin)")
def set_mode(
    payload: ModeSchema,
    _: AdminUser,
    db: Annotated[Session, Depends(get_master_db)],
    tenant_id: Annotated[Optional[int], Depends(get_current_tenant_id)] = None,
):
    mode = tenant_mode.normalize(payload.mode)
    if mode not in tenant_mode.VALID:
        raise BadRequestError(message="mode must be one of: cloud, onprem, hybrid.")
    if not tenant_id:
        raise BadRequestError(message="No tenant context.")
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise NotFoundError(message="Tenant not found.")
    tenant.deployment_mode = mode
    db.commit()
    tenant_mode.set_current_mode(mode)
    # Best-effort: clear the short-TTL tenant cache so the change is seen at once.
    try:
        from app.core import tenant_cache
        tenant_cache.invalidate(tenant)  # type: ignore[attr-defined]
    except Exception:
        pass
    return _effective(mode)
