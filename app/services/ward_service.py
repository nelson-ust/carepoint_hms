from __future__ import annotations

"""
app.services.ward_service

Service layer for ward management.

Purpose
-------
This module implements business logic for the ward module.

Responsibilities
----------------
- validate create/update payloads against current database state
- enforce ward code and ward name uniqueness
- orchestrate create, update, read, list, and delete flows
- guard deletion when linked beds or admissions exist
- provide detailed ward summary responses for higher layers

Design goals
------------
- keep repositories focused on raw persistence/query logic
- keep route handlers thin
- centralize ward business rules in one place
"""

from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, BadRequestError, NotFoundError
from app.repositories.ward_repository import WardRepository
from app.schemas.ward_schemas import WardCreateSchema, WardUpdateSchema


class WardService:
    """
    Service layer for ward management workflows.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the service with an active SQLAlchemy session.

        Args:
            db: Active SQLAlchemy session.
        """
        self.db = db
        self.repository = WardRepository(db)

    # ============================================================
    # CREATE
    # ============================================================

    def create_ward(self, payload: WardCreateSchema):
        """
        Create a new ward after validating uniqueness rules.

        Business rules
        --------------
        - ward code must be unique
        - ward name must be unique

        Args:
            payload: Ward creation payload.

        Returns:
            Ward: Newly created ward.

        Raises:
            AlreadyExistsError: If name or code already exists.
        """
        existing_by_code = self.repository.get_by_code(payload.code)
        if existing_by_code:
            raise AlreadyExistsError(
                message="A ward with this code already exists.",
                detail={"code": payload.code},
            )

        existing_by_name = self.repository.get_by_name(payload.name)
        if existing_by_name:
            raise AlreadyExistsError(
                message="A ward with this name already exists.",
                detail={"name": payload.name},
            )

        ward = self.repository.create_ward(
            name=payload.name,
            code=payload.code,
            ward_type=payload.ward_type,
            description=payload.description,
        )

        self.db.commit()
        return self.get_ward(ward.id)

    # ============================================================
    # READ
    # ============================================================

    def get_ward(self, ward_id: int):
        """
        Return a ward by ID.

        Args:
            ward_id: Ward primary key.

        Returns:
            Ward: Matching ward.

        Raises:
            NotFoundError: If the ward does not exist.
        """
        ward = self.repository.get_by_id(ward_id)
        if not ward:
            raise NotFoundError(
                message="Ward not found.",
                detail={"ward_id": ward_id},
            )
        return ward

    def get_detailed_ward(self, ward_id: int) -> dict:
        """
        Return a detailed ward summary including operational counts.

        Args:
            ward_id: Ward primary key.

        Returns:
            dict: Ward summary payload.

        Raises:
            NotFoundError: If the ward does not exist.
        """
        summary = self.repository.get_ward_summary_by_id(ward_id)
        if not summary:
            raise NotFoundError(
                message="Ward not found.",
                detail={"ward_id": ward_id},
            )
        return summary

    def list_wards(self, *, skip: int = 0, limit: int = 20):
        """
        Return paginated ward summaries.

        Args:
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[dict], int]:
                - ward summary rows
                - total count
        """
        return self.repository.list_wards(skip=skip, limit=limit)

    # ============================================================
    # UPDATE
    # ============================================================

    def update_ward(self, ward_id: int, payload: WardUpdateSchema):
        """
        Update an existing ward.

        Business rules
        --------------
        - updated ward code must remain unique
        - updated ward name must remain unique

        Args:
            ward_id: Ward primary key.
            payload: Ward update payload.

        Returns:
            Ward: Updated ward.

        Raises:
            NotFoundError: If the ward does not exist.
            AlreadyExistsError: If the updated name or code conflicts.
        """
        ward = self.repository.get_by_id(ward_id)
        if not ward:
            raise NotFoundError(
                message="Ward not found.",
                detail={"ward_id": ward_id},
            )

        if payload.code and payload.code != ward.code:
            existing_by_code = self.repository.get_by_code(payload.code)
            if existing_by_code and existing_by_code.id != ward.id:
                raise AlreadyExistsError(
                    message="A ward with this code already exists.",
                    detail={"code": payload.code},
                )

        if payload.name and payload.name != ward.name:
            existing_by_name = self.repository.get_by_name(payload.name)
            if existing_by_name and existing_by_name.id != ward.id:
                raise AlreadyExistsError(
                    message="A ward with this name already exists.",
                    detail={"name": payload.name},
                )

        updated = self.repository.update_ward(
            ward,
            name=payload.name,
            code=payload.code,
            ward_type=payload.ward_type,
            description=payload.description,
        )

        self.db.commit()
        return self.get_ward(updated.id)

    # ============================================================
    # DELETE
    # ============================================================

    def delete_ward(self, ward_id: int):
        """
        Soft-delete a ward.

        Business rules
        --------------
        A ward cannot be deleted when it still has:
        - linked beds
        - linked admissions

        Args:
            ward_id: Ward primary key.

        Returns:
            Ward: Soft-deleted ward.

        Raises:
            NotFoundError: If the ward does not exist.
            BadRequestError: If delete is blocked by linked records.
        """
        ward = self.repository.get_by_id(ward_id)
        if not ward:
            raise NotFoundError(
                message="Ward not found.",
                detail={"ward_id": ward_id},
            )

        has_beds = self.repository.has_beds(ward_id)
        if has_beds:
            raise BadRequestError(
                message="This ward cannot be deleted because it still has linked bed records.",
                detail={"ward_id": ward_id},
            )

        has_admissions = self.repository.has_admissions(ward_id)
        if has_admissions:
            raise BadRequestError(
                message="This ward cannot be deleted because it still has linked admission records.",
                detail={"ward_id": ward_id},
            )

        deleted = self.repository.soft_delete_ward(ward)
        self.db.commit()
        return deleted