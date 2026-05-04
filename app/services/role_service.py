from __future__ import annotations

"""
app.services.role_service

Service layer for role and role-permission management.

Purpose
-------
This module orchestrates business logic for the RBAC role module.

Responsibilities
----------------
- validate repository results
- coordinate create/update/delete flows
- validate permission assignment inputs
- format role responses for route handlers
"""

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Role
from app.repositories.role_repository import RoleRepository
from app.schemas.role_schemas import (
    RoleCreateSchema,
    RoleUpdateSchema,
)


class RoleService:
    """
    Service layer for role management.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the service with a database session.
        """
        self.db = db
        self.repository = RoleRepository(db)

    def list_roles(self, *, skip: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        """
        Return paginated role summaries.
        """
        return self.repository.list_roles(skip=skip, limit=limit)

    def get_role(self, role_id: int) -> Role:
        """
        Return a role by ID.
        """
        return self.repository.get_required_by_id(role_id)

    def create_role(self, payload: RoleCreateSchema) -> Role:
        """
        Create a role and optionally attach permissions.
        """
        role = self.repository.create_role(
            name=payload.name,
            code=payload.code,
            description=payload.description,
        )

        if payload.permission_ids:
            self._validate_permissions_exist(payload.permission_ids)
            role = self.repository.assign_permissions(role, payload.permission_ids)

        self.db.commit()
        return self.repository.get_required_by_id(role.id)

    def update_role(self, role_id: int, payload: RoleUpdateSchema) -> Role:
        """
        Update an existing role.
        """
        role = self.repository.get_required_by_id(role_id)

        updated = self.repository.update_role(
            role,
            name=payload.name,
            code=payload.code,
            description=payload.description,
        )

        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def delete_role(self, role_id: int) -> Role:
        """
        Soft-delete a role.

        Business rule:
        --------------
        A role that is still assigned to users should not be deleted.
        """
        role = self.repository.get_required_by_id(role_id)

        user_count = len(role.user_roles or [])
        if user_count > 0:
            raise BadRequestError(
                message="This role cannot be deleted because it is assigned to one or more users.",
                detail={"role_id": role_id, "assigned_user_count": user_count},
            )

        deleted = self.repository.soft_delete_role(role)
        self.db.commit()
        return deleted

    def assign_permissions(self, role_id: int, permission_ids: list[int]) -> Role:
        """
        Assign permissions to a role.
        """
        if not permission_ids:
            raise BadRequestError(message="At least one permission ID must be supplied.")

        role = self.repository.get_required_by_id(role_id)
        self._validate_permissions_exist(permission_ids)

        updated = self.repository.assign_permissions(role, permission_ids)
        self.db.commit()
        return updated

    def remove_permissions(self, role_id: int, permission_ids: list[int]) -> Role:
        """
        Remove permissions from a role.
        """
        if not permission_ids:
            raise BadRequestError(message="At least one permission ID must be supplied.")

        role = self.repository.get_required_by_id(role_id)
        updated = self.repository.remove_permissions(role, permission_ids)
        self.db.commit()
        return updated

    def _validate_permissions_exist(self, permission_ids: list[int]) -> None:
        """
        Validate that all supplied permission IDs exist.

        Raises:
            NotFoundError: If one or more permissions do not exist.
        """
        permissions = self.repository.get_permissions_by_ids(permission_ids)
        found_ids = {permission.id for permission in permissions}
        missing_ids = sorted(set(permission_ids) - found_ids)

        if missing_ids:
            raise NotFoundError(
                message="One or more permissions were not found.",
                detail={"missing_permission_ids": missing_ids},
            )