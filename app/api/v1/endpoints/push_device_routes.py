"""
Push-notification device registration endpoints.

Each authenticated user can register one or more device tokens (web push,
iOS APNs, Android FCM). Tokens are stored per-tenant and pruned when delivery
fails permanently.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.all_models import PushDeviceToken, User


router = APIRouter(prefix="/push-devices", tags=["Notifications - Push Devices"])


class PushDeviceRegisterSchema(BaseModel):
    device_token: str = Field(..., min_length=8, max_length=512)
    platform: str = Field("WEB", pattern=r"^(WEB|IOS|ANDROID)$")
    label: Optional[str] = None


class PushDeviceReadSchema(BaseModel):
    id: int
    device_token: str
    platform: str
    label: Optional[str] = None
    is_active: bool
    last_used_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


@router.post(
    "",
    response_model=PushDeviceReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register or refresh a push device token",
)
def register_device(
    payload: PushDeviceRegisterSchema,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    existing = (
        db.query(PushDeviceToken)
        .filter(
            PushDeviceToken.user_id == current_user.id,
            PushDeviceToken.device_token == payload.device_token,
        )
        .first()
    )
    if existing:
        existing.platform = payload.platform
        existing.label = payload.label
        existing.is_active = True
        existing.is_deleted = False
        existing.last_used_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    record = PushDeviceToken(
        user_id=current_user.id,
        device_token=payload.device_token,
        platform=payload.platform,
        label=payload.label,
        is_active=True,
        last_used_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get(
    "",
    response_model=list[PushDeviceReadSchema],
    summary="List the current user's push devices",
)
def list_devices(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return (
        db.query(PushDeviceToken)
        .filter(
            PushDeviceToken.user_id == current_user.id,
            PushDeviceToken.is_deleted.is_(False),
        )
        .all()
    )


@router.delete(
    "/{device_id}",
    status_code=status.HTTP_200_OK,
    summary="Unregister a push device",
)
def remove_device(
    device_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    record = (
        db.query(PushDeviceToken)
        .filter(
            PushDeviceToken.id == device_id,
            PushDeviceToken.user_id == current_user.id,
        )
        .first()
    )
    if record is None:
        return {"success": True}
    record.soft_delete()
    record.is_active = False
    db.commit()
    return {"success": True}
