from __future__ import annotations

"""
app.repositories.clinician_repository

Repository layer for clinician-specific data access.
Clinicians are defined as staff members with clinical roles (DOCTOR, NURSE, etc.).
"""

from typing import Optional
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.all_models import Role, StaffProfile, User, UserRoleAssociation


class ClinicianRepository:
    """
    Repository for retrieving and managing clinician-specific data.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize with an active SQLAlchemy session.
        """
        self.db = db

    def list_clinicians(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        specialty: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[StaffProfile], int]:
        """
        Return paginated staff profiles who have clinical roles.

        Clinical roles include DOCTOR, NURSE, and CLINICIAN by default.
        ``search`` performs a case-insensitive match against the user's
        first/last name, username, and the profile's specialty.
        """
        clinician_roles = ["DOCTOR", "NURSE", "CLINICIAN"]

        query = (
            self.db.query(StaffProfile)
            .join(User, StaffProfile.user_id == User.id)
            .join(UserRoleAssociation, UserRoleAssociation.user_id == User.id)
            .join(Role, UserRoleAssociation.role_id == Role.id)
            .filter(
                Role.code.in_(clinician_roles),
                StaffProfile.is_deleted.is_(False),
                User.is_deleted.is_(False),
            )
            .options(
                joinedload(StaffProfile.user),
                joinedload(StaffProfile.department),
            )
        )

        if specialty:
            query = query.filter(StaffProfile.specialty.ilike(f"%{specialty}%"))

        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    User.first_name.ilike(pattern),
                    User.last_name.ilike(pattern),
                    User.username.ilike(pattern),
                    StaffProfile.specialty.ilike(pattern),
                )
            )

        # Use distinct to avoid duplicate staff rows if they have multiple clinical roles
        query = query.distinct()

        total = query.with_entities(func.count(func.distinct(StaffProfile.id))).scalar() or 0
        items = query.offset(skip).limit(limit).all()

        return items, int(total)

    def get_clinician_by_id(self, clinician_id: int) -> Optional[StaffProfile]:
        """
        Return a single staff profile if they are active.
        """
        return (
            self.db.query(StaffProfile)
            .options(
                joinedload(StaffProfile.user),
                joinedload(StaffProfile.department),
            )
            .filter(
                StaffProfile.id == clinician_id,
                StaffProfile.is_deleted.is_(False),
            )
            .first()
        )
