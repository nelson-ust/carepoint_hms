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

import os
import uuid
from datetime import date, datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator
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


class MyProfileRoleSchema(BaseModel):
    """Lightweight role representation embedded in the profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: Optional[str] = None


class MyProfileReadSchema(BaseModel):
    id: int
    username: str
    email: EmailStr
    phone_number: Optional[str] = None
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    profile_photo_url: Optional[str] = None
    #: Presigned, time-limited URL for DISPLAYING the photo (private bucket).
    profile_photo_display_url: Optional[str] = None
    signature_url: Optional[str] = None
    #: Presigned, time-limited URL for DISPLAYING the signature.
    signature_display_url: Optional[str] = None
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
    theme_preference: str = "light"
    profile_completion: int = 0
    last_login_at: Optional[datetime] = None
    # The ORM exposes Role objects here; accept them via from_attributes rather
    # than the old ``list[dict]`` which raised a ResponseValidationError 500.
    roles: list[MyProfileRoleSchema] = []

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


class ThemePreferenceSchema(BaseModel):
    """Body for updating the appearance (theme) preference."""

    theme: str = Field(..., description="Either 'light' or 'dark'")

    @field_validator("theme")
    @classmethod
    def _valid_theme(cls, v: str) -> str:
        normalized = (v or "").strip().lower()
        if normalized not in {"light", "dark"}:
            raise ValueError("theme must be 'light' or 'dark'.")
        return normalized


class ThemePreferenceResponse(BaseModel):
    success: bool = True
    theme: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


_SELF_EDITABLE_FIELDS = (
    "first_name", "last_name", "middle_name", "phone_number", "job_title",
    "date_of_birth", "gender", "bio", "national_identifier",
    "national_identifier_type", "theme_preference",
    "profile_photo_url", "signature_url",
)


def _persist_profile(current_user, db) -> None:
    """Persist in-memory profile changes to the database that actually owns the
    row. Tenant ``User`` records belong to the request's ``db`` session; platform
    ``SaaSAdmin`` records live in the master DB in a *separate* session, so they
    must be updated there (``db.refresh`` on them raises 'not persistent')."""
    from app.models.all_models import SaaSAdmin

    if isinstance(current_user, SaaSAdmin):
        from app.core.database import get_master_db_context
        with get_master_db_context() as mdb:
            row = mdb.query(SaaSAdmin).filter(SaaSAdmin.id == current_user.id).first()
            if row is not None:
                for f in _SELF_EDITABLE_FIELDS:
                    if hasattr(row, f) and hasattr(current_user, f):
                        setattr(row, f, getattr(current_user, f))
                mdb.commit()
        return

    db.commit()
    db.refresh(current_user)


def _profile_read(user: User) -> MyProfileReadSchema:
    """Serialize the profile, presigning the photo for display."""
    out = MyProfileReadSchema.model_validate(user)
    try:
        from app.utils.s3_utils import presign_stored_url
        if user.profile_photo_url:
            out.profile_photo_display_url = presign_stored_url(user.profile_photo_url)
        if getattr(user, "signature_url", None):
            out.signature_display_url = presign_stored_url(user.signature_url)
    except Exception:  # pragma: no cover - media must never break the profile
        pass
    return out


@router.get(
    "",
    response_model=MyProfileReadSchema,
    summary="Get my profile",
)
def read_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return _profile_read(current_user)


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
    _persist_profile(current_user, db)
    return _profile_read(current_user)


@router.put(
    "/theme",
    response_model=ThemePreferenceResponse,
    summary="Update my appearance (theme) preference",
)
def update_my_theme(
    payload: ThemePreferenceSchema,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Persist the user's Light/Dark theme choice to their profile so it follows
    them across devices. Lightweight endpoint for the frequent toggle.
    """
    current_user.theme_preference = payload.theme
    _persist_profile(current_user, db)
    return {"success": True, "theme": payload.theme}


@router.post(
    "/photo",
    response_model=MyProfileReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Upload my profile photo",
)
async def upload_photo(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Upload the current user's profile photo. Works for tenant staff AND
    platform (SaaS) admins: uses the tenant's S3 bucket when available and
    falls back to local ``/uploads`` storage otherwise."""
    current_user.profile_photo_url = await _store_user_image(
        current_user, file, request, folder="profile-photos",
    )
    _persist_profile(current_user, db)
    return _profile_read(current_user)


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
    _persist_profile(current_user, db)
    return _profile_read(current_user)


async def _store_user_image(current_user: User, file: UploadFile, request: Request, *, folder: str) -> str:
    """Validate an image and store it — tenant S3 bucket when configured,
    otherwise the local ``/uploads`` directory (served statically). Returns an
    absolute URL usable both for display and (for S3) presigning. Works whether
    or not a tenant context is present, so platform admins can upload too."""
    from app.core.config import settings as _settings

    file_ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "png"
    if file_ext not in {"png", "jpg", "jpeg", "webp", "gif"}:
        raise BadRequestError(message="Only image files are supported (png/jpg/jpeg/webp/gif).")

    raw = await file.read()
    if not raw:
        raise BadRequestError(message="The uploaded image is empty.")
    max_bytes = int(getattr(_settings, "MAX_UPLOAD_SIZE_MB", 20)) * 1024 * 1024
    if len(raw) > max_bytes:
        raise BadRequestError(
            message=f"Image exceeds the {getattr(_settings, 'MAX_UPLOAD_SIZE_MB', 20)}MB limit.",
        )

    # 1) Tenant S3 bucket (production isolation) when a tenant + S3 are present.
    tenant = get_current_tenant()
    if tenant is not None:
        try:
            from app.core.database import get_master_db_context
            s3_service = S3Service()
            if getattr(s3_service, "is_enabled", False):
                with get_master_db_context() as master_db:
                    master_tenant = master_db.query(Tenant).filter(Tenant.code == tenant.code).first()
                    bucket = s3_service.ensure_tenant_bucket(master_db, master_tenant)
                if bucket:
                    s3_key = f"{folder}/user-{current_user.id}-{uuid.uuid4().hex}.{file_ext}"
                    await file.seek(0)
                    url = s3_service.upload_file(bucket, file, s3_key)
                    if url:
                        return url
        except Exception:
            pass  # fall through to local storage

    # 2) Local storage (SaaS/platform admins, or no S3 in this environment).
    from app.utils.storage import uploads_base_dir
    dest_dir = os.path.join(uploads_base_dir(), folder)
    os.makedirs(dest_dir, exist_ok=True)
    stored = f"user-{current_user.id}-{uuid.uuid4().hex}.{file_ext}"
    with open(os.path.join(dest_dir, stored), "wb") as fh:
        fh.write(raw)
    origin = str(request.base_url).rstrip("/")
    return f"{origin}/uploads/{folder}/{stored}"


@router.post(
    "/signature",
    response_model=MyProfileReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Upload my signature",
)
async def upload_signature(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Store the user's handwritten-signature image (tenant S3 or local)."""
    current_user.signature_url = await _store_user_image(
        current_user, file, request, folder="signatures",
    )
    _persist_profile(current_user, db)
    return _profile_read(current_user)


@router.delete(
    "/signature",
    response_model=MyProfileReadSchema,
    summary="Remove my signature",
)
def remove_signature(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)],
):
    current_user.signature_url = None
    _persist_profile(current_user, db)
    return _profile_read(current_user)
