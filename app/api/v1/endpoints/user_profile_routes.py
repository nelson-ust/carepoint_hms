"""
Self-service profile endpoints for the authenticated tenant user.

Separation of concerns
----------------------
* ``app/api/v1/endpoints/user_routes.py`` is the **admin** surface — admins
  manage other users, assign roles, lock/unlock accounts, etc.
* This file is the **self-service** surface — the currently signed-in user
  reads and updates fields they're allowed to change for themselves.

Admins should never use these endpoints to manage other users; they should
use the admin surface, which validates RBAC and audits more strictly.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel, EmailStr, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BadRequestError
from app.core.multitenancy import get_current_tenant
from app.dependencies.auth import get_current_active_user
from app.models.all_models import Tenant, User
from app.services.aws_s3_service import S3Service


router = APIRouter(prefix="/users/me", tags=["Tenant - My Profile"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MyProfileReadSchema(BaseModel):
    id: int
    username: str
    email: EmailStr
    phone_number: Optional[str] = None
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    profile_photo_url: Optional[str] = None
    job_title: Optional[str] = None
    department_id: Optional[int] = None
    facility_id: Optional[int] = None
    employment_status: Optional[str] = None
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    is_email_verified: bool = False
    is_phone_verified: bool = False
    is_two_factor_enabled: bool = False
    profile_completion: int = 0
    last_login_at: Optional[datetime] = None
    roles: list[dict] = []

    model_config = ConfigDict(from_attributes=True)


class MyProfileUpdateSchema(BaseModel):
    """
    Fields a user is permitted to update on themselves.

    Note that ``email``, ``role``, ``department``, ``facility``, and
    ``employment_status`` are **not** in this list — those are managed by
    administrators via ``/users/{id}`` admin endpoints.
    """

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    job_title: Optional[str] = None


def _serialize(user: User) -> dict:
    roles = []
    for assoc in user.user_roles or []:
        if getattr(assoc, "is_deleted", False):
            continue
        role = getattr(assoc, "role", None)
        if role is None:
            continue
        roles.append({"id": role.id, "name": role.name, "code": role.code})

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone_number": user.phone_number,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "middle_name": user.middle_name,
        "profile_photo_url": user.profile_photo_url,
        "job_title": user.job_title,
        "department_id": user.department_id,
        "facility_id": user.facility_id,
        "employment_status": user.employment_status,
        "bio": user.bio,
        "date_of_birth": user.date_of_birth,
        "gender": user.gender,
        "is_email_verified": user.is_email_verified,
        "is_phone_verified": user.is_phone_verified,
        "is_two_factor_enabled": user.is_two_factor_enabled,
        "profile_completion": user.profile_completion,
        "last_login_at": user.last_login_at,
        "roles": roles,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=MyProfileReadSchema,
    summary="Get my profile",
)
def read_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return _serialize(current_user)


@router.put(
    "",
    response_model=MyProfileReadSchema,
    summary="Update my profile (self-service)",
)
def update_me(
    payload: MyProfileUpdateSchema,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return _serialize(current_user)


@router.post(
    "/photo",
    response_model=MyProfileReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Upload my profile photo",
)
def upload_photo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    tenant = get_current_tenant()
    if tenant is None:
        raise BadRequestError(message="Tenant context is required to upload a photo.")

    # Resolve the bucket from the master DB.
    from app.core.database import get_master_db_context

    with get_master_db_context() as master_db:
        master_tenant = (
            master_db.query(Tenant).filter(Tenant.code == tenant.code).first()
        )
        bucket = master_tenant.aws_s3_bucket_name if master_tenant else None

    s3_service = S3Service()
    if not getattr(s3_service, "is_enabled", False) or not bucket:
        # Storage disabled or not provisioned — accept the upload and
        # return a placeholder URL pointing at the in-process upload.
        # Production deployments should wire S3 properly.
        raise BadRequestError(
            message="File storage is not configured for this tenant. Contact your administrator.",
        )

    file_ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "png"
    if file_ext not in {"png", "jpg", "jpeg", "webp", "gif"}:
        raise BadRequestError(message="Only image files are supported (png/jpg/jpeg/webp/gif).")

    s3_key = f"profile-photos/user-{current_user.id}-{uuid.uuid4().hex}.{file_ext}"
    photo_url = s3_service.upload_file(bucket, file, s3_key)
    if not photo_url:
        raise BadRequestError(message="Failed to upload profile photo.")

    current_user.profile_photo_url = photo_url
    db.commit()
    db.refresh(current_user)
    return _serialize(current_user)


@router.delete(
    "/photo",
    response_model=MyProfileReadSchema,
    summary="Remove my profile photo",
)
def remove_photo(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    current_user.profile_photo_url = None
    db.commit()
    db.refresh(current_user)
    return _serialize(current_user)
