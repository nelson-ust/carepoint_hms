from __future__ import annotations

"""
app.api.v1.endpoints.clinician_routes

FastAPI routes for listing clinicians (staff members holding clinical
roles such as DOCTOR, NURSE, or CLINICIAN).

Purpose
-------
Provides a lightweight, read-only directory of active clinicians for
use in scheduling, referrals, and clinical assignment UIs.

Security
--------
Endpoints require an authenticated, active user.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AnyAuthenticatedUser
from app.models.all_models import StaffProfile
from app.services.clinician_service import ClinicianService

router = APIRouter(prefix="/clinicians", tags=["Clinicians"])


def get_clinician_service(
    db: Annotated[Session, Depends(get_db)],
) -> ClinicianService:
    """
    Dependency provider for the clinician service.
    """
    return ClinicianService(db)


def _serialize_clinician(profile: StaffProfile) -> dict:
    """
    Flatten a StaffProfile (with joined user/department) into a
    directory-friendly item.
    """
    user = profile.user
    full_name = " ".join(
        part
        for part in [
            getattr(user, "first_name", None),
            getattr(user, "middle_name", None),
            getattr(user, "last_name", None),
        ]
        if part
    )
    roles = [role.code for role in (user.roles if user else [])]
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "staff_no": profile.staff_no,
        "full_name": full_name,
        "roles": roles,
        "job_title": profile.job_title,
        "department_id": profile.department_id,
        "department": profile.department.name if profile.department else None,
        "specialty": profile.specialty,
    }


@router.get(
    "/",
    summary="List clinicians",
)
def list_clinicians(
    _: AnyAuthenticatedUser,
    service: Annotated[ClinicianService, Depends(get_clinician_service)],
    skip: int = Query(0, ge=0, description="Number of records to skip."),
    limit: int = Query(20, ge=1, le=1000, description="Maximum records to return."),
    specialty: Optional[str] = Query(
        None, description="Filter by specialty (partial match)."
    ),
    search: Optional[str] = Query(
        None, description="Search by name, username, or specialty (partial match)."
    ),
):
    """
    Paginated list of active clinicians (staff with clinical roles).
    """
    items, count = service.list_clinicians(
        skip=skip, limit=limit, specialty=specialty, search=search
    )
    return {
        "success": True,
        "message": "Clinicians fetched successfully.",
        "items": [_serialize_clinician(p) for p in items],
        "count": count,
        "meta": {"skip": skip, "limit": limit, "total": count},
    }
