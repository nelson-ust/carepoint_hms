from __future__ import annotations

"""
app.repositories.ward_repository

Repository layer for ward persistence and ward summary queries.

Purpose
-------
This module centralizes direct database operations for the ward module.

It supports:
- creating wards
- updating wards
- soft-deleting wards
- fetching wards by id, code, or name
- listing wards with pagination
- returning detailed ward operational summaries

Design goals
------------
- keep raw SQLAlchemy query logic out of route handlers
- keep business rules out of the repository layer
- expose reusable persistence/query helpers for the service layer

Current model alignment
-----------------------
This repository is aligned with the current ORM models where:

- Ward has:
    - id
    - name
    - code
    - ward_type
    - description
    - beds relationship
    - admissions relationship

- Bed belongs to a Ward
- Admission belongs to a Ward

Notes
-----
- Bed occupancy logic is inferred from the current Bed.bed_status value.
- Admission "active" logic is inferred from the current Admission.admission_status
  value.
- These are intentionally repository-level summaries; stricter business
  interpretation can be applied in the service layer if needed.
"""

from typing import Optional

from sqlalchemy import String, case, func
from sqlalchemy.orm import Session, joinedload

from app.models.all_models import Admission, Bed, Ward


class WardRepository:
    """
    Repository for ward CRUD and ward summary database operations.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the repository with an active SQLAlchemy session.

        Args:
            db: Active SQLAlchemy session.
        """
        self.db = db

    # ============================================================
    # BASIC LOOKUPS
    # ============================================================

    def get_by_id(self, ward_id: int) -> Optional[Ward]:
        """
        Return a ward by ID.

        Args:
            ward_id: Ward primary key.

        Returns:
            Optional[Ward]: Matching ward or None.
        """
        return (
            self.db.query(Ward)
            .filter(
                Ward.id == ward_id,
                Ward.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_code(self, code: str) -> Optional[Ward]:
        """
        Return a ward by code.

        Args:
            code: Ward code.

        Returns:
            Optional[Ward]: Matching ward or None.
        """
        return (
            self.db.query(Ward)
            .filter(
                Ward.code == code,
                Ward.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_name(self, name: str) -> Optional[Ward]:
        """
        Return a ward by name.

        Args:
            name: Ward name.

        Returns:
            Optional[Ward]: Matching ward or None.
        """
        return (
            self.db.query(Ward)
            .filter(
                Ward.name == name,
                Ward.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, ward_id: int) -> Ward:
        """
        Return a ward by ID or raise a ValueError-style repository exception.

        Args:
            ward_id: Ward primary key.

        Returns:
            Ward: Matching ward.

        Raises:
            ValueError: If the ward is not found.
        """
        ward = self.get_by_id(ward_id)
        if not ward:
            raise ValueError(f"Ward with id={ward_id} was not found.")
        return ward

    # ============================================================
    # CREATE / UPDATE / DELETE
    # ============================================================

    def create_ward(
        self,
        *,
        name: str,
        code: str,
        ward_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Ward:
        """
        Create and persist a new ward.

        Args:
            name: Ward name.
            code: Ward code.
            ward_type: Optional ward type.
            description: Optional ward description.

        Returns:
            Ward: Persisted ward.
        """
        ward = Ward(
            name=name,
            code=code,
            ward_type=ward_type,
            description=description,
        )
        self.db.add(ward)
        self.db.flush()
        self.db.refresh(ward)
        return ward

    def update_ward(
        self,
        ward: Ward,
        *,
        name: Optional[str] = None,
        code: Optional[str] = None,
        ward_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Ward:
        """
        Persist updates to an existing ward.

        Args:
            ward: Target ward ORM instance.
            name: Optional new ward name.
            code: Optional new ward code.
            ward_type: Optional new ward type.
            description: Optional new ward description.

        Returns:
            Ward: Updated ward.
        """
        if name is not None:
            ward.name = name
        if code is not None:
            ward.code = code
        if ward_type is not None:
            ward.ward_type = ward_type
        if description is not None:
            ward.description = description

        self.db.add(ward)
        self.db.flush()
        self.db.refresh(ward)
        return ward

    def soft_delete_ward(self, ward: Ward) -> Ward:
        """
        Soft-delete a ward.

        Args:
            ward: Target ward ORM instance.

        Returns:
            Ward: Soft-deleted ward.
        """
        ward.is_deleted = True
        self.db.add(ward)
        self.db.flush()
        return ward

    # ============================================================
    # DETAILED LOOKUPS
    # ============================================================

    def get_detailed_by_id(self, ward_id: int) -> Optional[Ward]:
        """
        Return a ward by ID with related beds and admissions eagerly loaded.

        Args:
            ward_id: Ward primary key.

        Returns:
            Optional[Ward]: Matching ward or None.
        """
        return (
            self.db.query(Ward)
            .options(
                joinedload(Ward.beds),
                joinedload(Ward.admissions),
            )
            .filter(
                Ward.id == ward_id,
                Ward.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # LIST / SUMMARY QUERIES
    # ============================================================

    def list_wards(self, *, skip: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        """
        Return paginated ward summaries with bed and admission counts.

        Summary fields returned
        -----------------------
        - total_beds
        - available_beds
        - occupied_beds
        - active_admissions

        Args:
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[dict], int]:
                - list of ward summary dictionaries
                - total count of wards
        """
        total = (
            self.db.query(func.count(Ward.id))
            .filter(Ward.is_deleted.is_(False))
            .scalar()
            or 0
        )

        # Bed status classification:
        # - AVAILABLE => available bed
        # - any other non-null/non-available status => occupied/unavailable
        # Admission status classification:
        # - ACTIVE or ADMITTED-like values are counted as active admissions
        rows = (
            self.db.query(
                Ward,
                func.count(func.distinct(Bed.id)).label("total_beds"),
                func.coalesce(
                    func.sum(
                        case(
                            (func.upper(func.cast(Bed.bed_status, String)) == "AVAILABLE", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("available_beds"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (Bed.bed_status.isnot(None)) & (func.upper(func.cast(Bed.bed_status, String)) != "AVAILABLE"),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("occupied_beds"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                func.upper(func.cast(Admission.admission_status, String)).in_(
                                    ["ACTIVE", "ADMITTED", "INPATIENT"]
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("active_admissions"),
            )
            .outerjoin(Bed, Bed.ward_id == Ward.id)
            .outerjoin(Admission, Admission.ward_id == Ward.id)
            .filter(Ward.is_deleted.is_(False))
            .group_by(Ward.id)
            .order_by(Ward.name.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        items: list[dict] = []
        for ward, total_beds, available_beds, occupied_beds, active_admissions in rows:
            items.append(
                {
                    "id": ward.id,
                    "name": ward.name,
                    "code": ward.code,
                    "ward_type": ward.ward_type,
                    "description": ward.description,
                    "total_beds": int(total_beds or 0),
                    "available_beds": int(available_beds or 0),
                    "occupied_beds": int(occupied_beds or 0),
                    "active_admissions": int(active_admissions or 0),
                }
            )

        return items, int(total)

    def get_ward_summary_by_id(self, ward_id: int) -> Optional[dict]:
        """
        Return a detailed ward summary by ward ID.

        Summary fields returned
        -----------------------
        - total_beds
        - available_beds
        - occupied_beds
        - total_admissions
        - active_admissions

        Args:
            ward_id: Ward primary key.

        Returns:
            Optional[dict]: Ward summary dictionary or None.
        """
        row = (
            self.db.query(
                Ward,
                func.count(func.distinct(Bed.id)).label("total_beds"),
                func.coalesce(
                    func.sum(
                        case(
                            (func.upper(func.cast(Bed.bed_status, String)) == "AVAILABLE", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("available_beds"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (Bed.bed_status.isnot(None)) & (func.upper(func.cast(Bed.bed_status, String)) != "AVAILABLE"),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("occupied_beds"),
                func.count(func.distinct(Admission.id)).label("total_admissions"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                func.upper(func.cast(Admission.admission_status, String)).in_(
                                    ["ACTIVE", "ADMITTED", "INPATIENT"]
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("active_admissions"),
            )
            .outerjoin(Bed, Bed.ward_id == Ward.id)
            .outerjoin(Admission, Admission.ward_id == Ward.id)
            .filter(
                Ward.id == ward_id,
                Ward.is_deleted.is_(False),
            )
            .group_by(Ward.id)
            .first()
        )

        if not row:
            return None

        ward, total_beds, available_beds, occupied_beds, total_admissions, active_admissions = row

        return {
            "id": ward.id,
            "name": ward.name,
            "code": ward.code,
            "ward_type": ward.ward_type,
            "description": ward.description,
            "date_created": ward.date_created,
            "date_updated": ward.date_updated,
            "total_beds": int(total_beds or 0),
            "available_beds": int(available_beds or 0),
            "occupied_beds": int(occupied_beds or 0),
            "total_admissions": int(total_admissions or 0),
            "active_admissions": int(active_admissions or 0),
        }

    # ============================================================
    # SUPPORTING CHECKS
    # ============================================================

    def has_beds(self, ward_id: int) -> bool:
        """
        Return whether the ward currently has linked bed records.

        Args:
            ward_id: Ward primary key.

        Returns:
            bool: True if at least one bed exists for the ward.
        """
        count = (
            self.db.query(func.count(Bed.id))
            .filter(
                Bed.ward_id == ward_id,
                Bed.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )
        return count > 0

    def has_admissions(self, ward_id: int) -> bool:
        """
        Return whether the ward currently has linked admission records.

        Args:
            ward_id: Ward primary key.

        Returns:
            bool: True if at least one admission exists for the ward.
        """
        count = (
            self.db.query(func.count(Admission.id))
            .filter(
                Admission.ward_id == ward_id,
                Admission.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )
        return count > 0