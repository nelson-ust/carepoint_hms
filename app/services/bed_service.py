from __future__ import annotations

"""
app.services.bed_service

Service layer for bed management.

Purpose
-------
This module implements business logic for the bed module.

Responsibilities
----------------
- validate create/update payloads against current database state
- enforce ward existence
- enforce ward-scoped bed number uniqueness
- orchestrate create, update, read, list, and delete flows
- guard deletion when active admissions exist
- provide detailed bed summary responses for higher layers

Design goals
------------
- keep repositories focused on raw persistence/query logic
- keep route handlers thin
- centralize bed business rules in one place
"""

from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, BadRequestError, NotFoundError
from app.repositories.bed_repository import BedRepository
from app.schemas.bed_schemas import BedCreateSchema, BedUpdateSchema


class BedService:
    """
    Service layer for bed management workflows.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the service with an active SQLAlchemy session.

        Args:
            db: Active SQLAlchemy session.
        """
        self.db = db
        self.repository = BedRepository(db)

    # ============================================================
    # CREATE
    # ============================================================

    def create_bed(self, payload: BedCreateSchema):
        """
        Create a new bed after validating business rules.

        Business rules
        --------------
        - linked ward must exist
        - bed number must be unique within the ward

        Args:
            payload: Bed creation payload.

        Returns:
            Bed: Newly created bed.

        Raises:
            NotFoundError: If the linked ward does not exist.
            AlreadyExistsError: If the ward already contains the same bed number.
        """
        self._validate_ward_exists(payload.ward_id)

        existing = self.repository.get_by_ward_and_bed_no(
            payload.ward_id,
            payload.bed_no,
        )
        if existing:
            raise AlreadyExistsError(
                message="A bed with this bed number already exists in the selected ward.",
                detail={
                    "ward_id": payload.ward_id,
                    "bed_no": payload.bed_no,
                },
            )

        bed = self.repository.create_bed(
            ward_id=payload.ward_id,
            bed_no=payload.bed_no,
            bed_status=payload.bed_status,
            bed_type=payload.bed_type,
            notes=payload.notes,
        )

        self.db.commit()
        return self.get_bed(bed.id)

    # ============================================================
    # READ
    # ============================================================

    def get_bed(self, bed_id: int):
        """
        Return a bed by ID.

        Args:
            bed_id: Bed primary key.

        Returns:
            Bed: Matching bed.

        Raises:
            NotFoundError: If the bed does not exist.
        """
        bed = self.repository.get_by_id(bed_id)
        if not bed:
            raise NotFoundError(
                message="Bed not found.",
                detail={"bed_id": bed_id},
            )
        return bed

    def get_detailed_bed(self, bed_id: int) -> dict:
        """
        Return a detailed bed summary including ward and admission context.

        Args:
            bed_id: Bed primary key.

        Returns:
            dict: Bed summary payload.

        Raises:
            NotFoundError: If the bed does not exist.
        """
        summary = self.repository.get_bed_summary_by_id(bed_id)
        if not summary:
            raise NotFoundError(
                message="Bed not found.",
                detail={"bed_id": bed_id},
            )
        return summary

    def list_beds(self, *, skip: int = 0, limit: int = 20):
        """
        Return paginated bed summaries.

        Args:
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[dict], int]:
                - bed summary rows
                - total count
        """
        return self.repository.list_beds(skip=skip, limit=limit)

    # ============================================================
    # UPDATE
    # ============================================================

    def update_bed(self, bed_id: int, payload: BedUpdateSchema):
        """
        Update an existing bed.

        Business rules
        --------------
        - if ward_id changes, the new ward must exist
        - the final (ward_id, bed_no) combination must remain unique
        - moving a bed to another ward is blocked if it already has admissions

        Args:
            bed_id: Bed primary key.
            payload: Bed update payload.

        Returns:
            Bed: Updated bed.

        Raises:
            NotFoundError: If the bed does not exist, or target ward does not exist.
            AlreadyExistsError: If the new ward-scoped bed number conflicts.
            BadRequestError: If a restricted update is attempted.
        """
        bed = self.repository.get_by_id(bed_id)
        if not bed:
            raise NotFoundError(
                message="Bed not found.",
                detail={"bed_id": bed_id},
            )

        target_ward_id = payload.ward_id if payload.ward_id is not None else bed.ward_id
        target_bed_no = payload.bed_no if payload.bed_no is not None else bed.bed_no

        # Validate new ward when provided.
        if payload.ward_id is not None:
            self._validate_ward_exists(payload.ward_id)

        # Guard moving bed across wards when admissions already exist.
        if payload.ward_id is not None and payload.ward_id != bed.ward_id:
            if self.repository.has_admissions(bed.id):
                raise BadRequestError(
                    message="This bed cannot be moved to another ward because it already has linked admissions.",
                    detail={
                        "bed_id": bed.id,
                        "current_ward_id": bed.ward_id,
                        "target_ward_id": payload.ward_id,
                    },
                )

        # Enforce ward-scoped uniqueness for the final ward/bed number combination.
        existing = self.repository.get_by_ward_and_bed_no(target_ward_id, target_bed_no)
        if existing and existing.id != bed.id:
            raise AlreadyExistsError(
                message="A bed with this bed number already exists in the selected ward.",
                detail={
                    "ward_id": target_ward_id,
                    "bed_no": target_bed_no,
                },
            )

        updated = self.repository.update_bed(
            bed,
            ward_id=payload.ward_id,
            bed_no=payload.bed_no,
            bed_status=payload.bed_status,
            bed_type=payload.bed_type,
            notes=payload.notes,
        )

        self.db.commit()
        return self.get_bed(updated.id)

    # ============================================================
    # DELETE
    # ============================================================

    def delete_bed(self, bed_id: int):
        """
        Soft-delete a bed.

        Business rules
        --------------
        A bed cannot be deleted when it still has an active admission.

        Args:
            bed_id: Bed primary key.

        Returns:
            Bed: Soft-deleted bed.

        Raises:
            NotFoundError: If the bed does not exist.
            BadRequestError: If delete is blocked by an active admission.
        """
        bed = self.repository.get_by_id(bed_id)
        if not bed:
            raise NotFoundError(
                message="Bed not found.",
                detail={"bed_id": bed_id},
            )

        if self.repository.has_active_admission(bed_id):
            raise BadRequestError(
                message="This bed cannot be deleted because it currently has an active admission.",
                detail={"bed_id": bed_id},
            )

        deleted = self.repository.soft_delete_bed(bed)
        self.db.commit()
        return deleted

    # ============================================================
    # HELPERS
    # ============================================================

    def _validate_ward_exists(self, ward_id: int) -> None:
        """
        Validate that a ward exists.

        Args:
            ward_id: Ward primary key.

        Raises:
            NotFoundError: If the ward does not exist.
        """
        if not self.repository.ward_exists(ward_id):
            raise NotFoundError(
                message="Ward not found.",
                detail={"ward_id": ward_id},
            )