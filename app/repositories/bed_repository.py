from __future__ import annotations

"""
app.repositories.bed_repository

Repository layer for bed persistence and bed summary queries.

Purpose
-------
This module centralizes direct database operations for the bed module.

It supports:
- creating beds
- updating beds
- soft-deleting beds
- fetching beds by id or ward-scoped bed number
- listing beds with pagination
- returning detailed bed operational summaries
- checking whether a bed has linked admissions

Design goals
------------
- keep raw SQLAlchemy query logic out of route handlers
- keep business rules out of the repository layer
- expose reusable persistence/query helpers for the service layer

Current model alignment
-----------------------
This repository is aligned with the current ORM models where:

- Bed has:
    - ward_id
    - bed_no
    - bed_status
    - bed_type
    - notes

- Bed belongs to Ward
- Admission can optionally be linked to Bed

Notes
-----
- Bed uniqueness is ward-scoped via (ward_id, bed_no).
- "Active admission" is inferred using Admission.admission_status values.
- The repository only performs persistence/query work; business rules such as
  valid status transitions should remain in the service layer.
"""

from typing import Optional

from sqlalchemy import String, case, func
from sqlalchemy.orm import Session, joinedload

from app.models.all_models import Admission, Bed, Ward


class BedRepository:
    """
    Repository for bed CRUD and bed summary database operations.
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

    def get_by_id(self, bed_id: int) -> Optional[Bed]:
        """
        Return a bed by ID.

        Args:
            bed_id: Bed primary key.

        Returns:
            Optional[Bed]: Matching bed or None.
        """
        return (
            self.db.query(Bed)
            .filter(
                Bed.id == bed_id,
                Bed.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_ward_and_bed_no(self, ward_id: int, bed_no: str) -> Optional[Bed]:
        """
        Return a bed by ward-scoped bed number.

        Args:
            ward_id: Ward primary key.
            bed_no: Bed number/code.

        Returns:
            Optional[Bed]: Matching bed or None.
        """
        return (
            self.db.query(Bed)
            .filter(
                Bed.ward_id == ward_id,
                Bed.bed_no == bed_no,
                Bed.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, bed_id: int) -> Bed:
        """
        Return a bed by ID or raise a repository-level ValueError.

        Args:
            bed_id: Bed primary key.

        Returns:
            Bed: Matching bed.

        Raises:
            ValueError: If the bed is not found.
        """
        bed = self.get_by_id(bed_id)
        if not bed:
            raise ValueError(f"Bed with id={bed_id} was not found.")
        return bed

    # ============================================================
    # CREATE / UPDATE / DELETE
    # ============================================================

    def create_bed(
        self,
        *,
        ward_id: int,
        bed_no: str,
        bed_status: str,
        bed_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Bed:
        """
        Create and persist a new bed.

        Args:
            ward_id: Linked ward ID.
            bed_no: Ward-scoped bed number/code.
            bed_status: Current bed status.
            bed_type: Optional bed type.
            notes: Optional notes.

        Returns:
            Bed: Persisted bed.
        """
        bed = Bed(
            ward_id=ward_id,
            bed_no=bed_no,
            bed_status=bed_status,
            bed_type=bed_type,
            notes=notes,
        )
        self.db.add(bed)
        self.db.flush()
        self.db.refresh(bed)
        return bed

    def update_bed(
        self,
        bed: Bed,
        *,
        ward_id: Optional[int] = None,
        bed_no: Optional[str] = None,
        bed_status: Optional[str] = None,
        bed_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Bed:
        """
        Persist updates to an existing bed.

        Args:
            bed: Target bed ORM instance.
            ward_id: Optional new ward ID.
            bed_no: Optional new bed number/code.
            bed_status: Optional new bed status.
            bed_type: Optional new bed type.
            notes: Optional new notes.

        Returns:
            Bed: Updated bed.
        """
        if ward_id is not None:
            bed.ward_id = ward_id
        if bed_no is not None:
            bed.bed_no = bed_no
        if bed_status is not None:
            bed.bed_status = bed_status
        if bed_type is not None:
            bed.bed_type = bed_type
        if notes is not None:
            bed.notes = notes

        self.db.add(bed)
        self.db.flush()
        self.db.refresh(bed)
        return bed

    def soft_delete_bed(self, bed: Bed) -> Bed:
        """
        Soft-delete a bed.

        Args:
            bed: Target bed ORM instance.

        Returns:
            Bed: Soft-deleted bed.
        """
        bed.is_deleted = True
        self.db.add(bed)
        self.db.flush()
        return bed

    # ============================================================
    # DETAILED LOOKUPS
    # ============================================================

    def get_detailed_by_id(self, bed_id: int) -> Optional[Bed]:
        """
        Return a bed by ID with ward and admissions eagerly loaded.

        Args:
            bed_id: Bed primary key.

        Returns:
            Optional[Bed]: Matching bed or None.
        """
        return (
            self.db.query(Bed)
            .options(
                joinedload(Bed.ward),
                joinedload(Bed.admissions),
            )
            .filter(
                Bed.id == bed_id,
                Bed.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # LIST / SUMMARY QUERIES
    # ============================================================

    def list_beds(self, *, skip: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        """
        Return paginated bed summaries with ward context and admission counts.

        Summary fields returned
        -----------------------
        - ward_name
        - ward_code
        - admission_count
        - has_active_admission

        Args:
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[dict], int]:
                - list of bed summary dictionaries
                - total count of beds
        """
        total = (
            self.db.query(func.count(Bed.id))
            .filter(Bed.is_deleted.is_(False))
            .scalar()
            or 0
        )

        rows = (
            self.db.query(
                Bed,
                Ward,
                func.count(func.distinct(Admission.id)).label("admission_count"),
                func.coalesce(
                    func.max(
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
                ).label("has_active_admission"),
            )
            .join(Ward, Ward.id == Bed.ward_id)
            .outerjoin(Admission, Admission.bed_id == Bed.id)
            .filter(
                Bed.is_deleted.is_(False),
                Ward.is_deleted.is_(False),
            )
            .group_by(Bed.id, Ward.id)
            .order_by(Ward.name.asc(), Bed.bed_no.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        items: list[dict] = []
        for bed, ward, admission_count, has_active_admission in rows:
            items.append(
                {
                    "id": bed.id,
                    "ward_id": bed.ward_id,
                    "bed_no": bed.bed_no,
                    "bed_status": bed.bed_status,
                    "bed_type": bed.bed_type,
                    "notes": bed.notes,
                    "ward_name": ward.name,
                    "ward_code": ward.code,
                    "admission_count": int(admission_count or 0),
                    "has_active_admission": bool(has_active_admission or 0),
                }
            )

        return items, int(total)

    def get_bed_summary_by_id(self, bed_id: int) -> Optional[dict]:
        """
        Return a detailed bed summary by bed ID.

        Summary fields returned
        -----------------------
        - ward
        - admission_count
        - has_active_admission

        Args:
            bed_id: Bed primary key.

        Returns:
            Optional[dict]: Bed summary dictionary or None.
        """
        row = (
            self.db.query(
                Bed,
                Ward,
                func.count(func.distinct(Admission.id)).label("admission_count"),
                func.coalesce(
                    func.max(
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
                ).label("has_active_admission"),
            )
            .join(Ward, Ward.id == Bed.ward_id)
            .outerjoin(Admission, Admission.bed_id == Bed.id)
            .filter(
                Bed.id == bed_id,
                Bed.is_deleted.is_(False),
                Ward.is_deleted.is_(False),
            )
            .group_by(Bed.id, Ward.id)
            .first()
        )

        if not row:
            return None

        bed, ward, admission_count, has_active_admission = row

        return {
            "id": bed.id,
            "ward_id": bed.ward_id,
            "bed_no": bed.bed_no,
            "bed_status": bed.bed_status,
            "bed_type": bed.bed_type,
            "notes": bed.notes,
            "date_created": bed.date_created,
            "date_updated": bed.date_updated,
            "ward": {
                "id": ward.id,
                "name": ward.name,
                "code": ward.code,
                "ward_type": ward.ward_type,
                "description": ward.description,
            },
            "admission_count": int(admission_count or 0),
            "has_active_admission": bool(has_active_admission or 0),
        }

    # ============================================================
    # SUPPORTING CHECKS
    # ============================================================

    def ward_exists(self, ward_id: int) -> bool:
        """
        Return whether a ward exists and is not soft-deleted.

        Args:
            ward_id: Ward primary key.

        Returns:
            bool: True if the ward exists.
        """
        count = (
            self.db.query(func.count(Ward.id))
            .filter(
                Ward.id == ward_id,
                Ward.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )
        return count > 0

    def has_admissions(self, bed_id: int) -> bool:
        """
        Return whether the bed has any linked admissions.

        Args:
            bed_id: Bed primary key.

        Returns:
            bool: True if at least one admission exists.
        """
        count = (
            self.db.query(func.count(Admission.id))
            .filter(
                Admission.bed_id == bed_id,
                Admission.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )
        return count > 0

    def has_active_admission(self, bed_id: int) -> bool:
        """
        Return whether the bed currently has an active admission.

        Args:
            bed_id: Bed primary key.

        Returns:
            bool: True if an active admission exists.
        """
        count = (
            self.db.query(func.count(Admission.id))
            .filter(
                Admission.bed_id == bed_id,
                Admission.is_deleted.is_(False),
                func.upper(func.cast(Admission.admission_status, String)).in_(
                    ["ACTIVE", "ADMITTED", "INPATIENT"]
                ),
            )
            .scalar()
            or 0
        )
        return count > 0