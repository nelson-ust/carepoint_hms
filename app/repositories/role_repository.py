#app/repositories/role_repository
from __future__ import annotations

"""
app.repositories.role_repository

Repository layer for role and role-permission persistence logic.

Purpose
-------
This module encapsulates direct database operations for:
- creating roles
- updating roles
- soft-deleting roles
- listing roles
- reading role details
- assigning permissions to roles
- removing permissions from roles

Design goals
------------
- keep query logic out of route handlers
- keep service layer focused on orchestration and validation
- centralize all Role / Permission / RolePermissionAssociation DB access
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import (
    Permission,
    Role,
    RolePermissionAssociation,
    UserRoleAssociation,
)


class RoleRepository:
    """
    Repository for role-related database operations.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the repository with a SQLAlchemy session.
        """
        self.db = db

    def get_by_id(self, role_id: int) -> Optional[Role]:
        """
        Return a role by ID, including attached permissions.

        Args:
            role_id: Role primary key.

        Returns:
            Optional[Role]: Matching role or None.
        """
        return (
            self.db.query(Role)
            .options(
                joinedload(Role.role_permissions).joinedload(RolePermissionAssociation.permission)
            )
            .filter(Role.id == role_id, Role.is_deleted.is_(False))
            .first()
        )

    def get_by_code(self, code: str) -> Optional[Role]:
        """
        Return a role by code.

        Args:
            code: Role code.

        Returns:
            Optional[Role]: Matching role or None.
        """
        return (
            self.db.query(Role)
            .filter(Role.code == code, Role.is_deleted.is_(False))
            .first()
        )

    def get_by_name(self, name: str) -> Optional[Role]:
        """
        Return a role by name.

        Args:
            name: Role name.

        Returns:
            Optional[Role]: Matching role or None.
        """
        return (
            self.db.query(Role)
            .filter(Role.name == name, Role.is_deleted.is_(False))
            .first()
        )

    def list_roles(self, *, skip: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        """
        List roles with permission and user counts.

        Args:
            skip: Pagination offset.
            limit: Pagination limit.

        Returns:
            tuple[list[dict], int]:
                - list of role summary dictionaries
                - total count
        """
        total = (
            self.db.query(func.count(Role.id))
            .filter(Role.is_deleted.is_(False))
            .scalar()
            or 0
        )

        rows = (
            self.db.query(
                Role,
                func.count(func.distinct(RolePermissionAssociation.permission_id)).label("permission_count"),
                func.count(func.distinct(UserRoleAssociation.user_id)).label("user_count"),
            )
            .outerjoin(
                RolePermissionAssociation,
                RolePermissionAssociation.role_id == Role.id,
            )
            .outerjoin(
                UserRoleAssociation,
                UserRoleAssociation.role_id == Role.id,
            )
            .filter(Role.is_deleted.is_(False))
            .group_by(Role.id)
            .order_by(Role.name.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        items: list[dict] = []
        for role, permission_count, user_count in rows:
            items.append(
                {
                    "id": role.id,
                    "name": role.name,
                    "code": role.code,
                    "description": role.description,
                    "permission_count": int(permission_count or 0),
                    "user_count": int(user_count or 0),
                }
            )

        return items, int(total)

    def create_role(
        self,
        *,
        name: str,
        code: str,
        description: Optional[str] = None,
    ) -> Role:
        """
        Create a new role.

        Raises:
            AlreadyExistsError: If a role with the same name or code already exists.
        """
        existing_by_code = self.get_by_code(code)
        if existing_by_code:
            raise AlreadyExistsError(
                message="A role with this code already exists.",
                detail={"code": code},
            )

        existing_by_name = self.get_by_name(name)
        if existing_by_name:
            raise AlreadyExistsError(
                message="A role with this name already exists.",
                detail={"name": name},
            )

        role = Role(
            name=name,
            code=code,
            description=description,
        )

        self.db.add(role)
        self.db.flush()
        self.db.refresh(role)
        return role

    def update_role(
        self,
        role: Role,
        *,
        name: Optional[str] = None,
        code: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Role:
        """
        Update an existing role.

        Raises:
            AlreadyExistsError: If the new name or code conflicts with another role.
        """
        if code and code != role.code:
            existing = self.get_by_code(code)
            if existing and existing.id != role.id:
                raise AlreadyExistsError(
                    message="A role with this code already exists.",
                    detail={"code": code},
                )

        if name and name != role.name:
            existing = self.get_by_name(name)
            if existing and existing.id != role.id:
                raise AlreadyExistsError(
                    message="A role with this name already exists.",
                    detail={"name": name},
                )

        if name is not None:
            role.name = name
        if code is not None:
            role.code = code
        if description is not None:
            role.description = description

        self.db.add(role)
        self.db.flush()
        self.db.refresh(role)
        return role

    def soft_delete_role(self, role: Role) -> Role:
        """
        Soft-delete a role.

        Notes
        -----
        This marks the role as deleted rather than physically removing it.
        """
        role.is_deleted = True
        self.db.add(role)
        self.db.flush()
        return role

    def get_permissions_by_ids(self, permission_ids: list[int]) -> list[Permission]:
        """
        Return permission rows for the supplied IDs.

        Args:
            permission_ids: Permission primary keys.

        Returns:
            list[Permission]: Matching permissions.
        """
        if not permission_ids:
            return []

        return (
            self.db.query(Permission)
            .filter(
                Permission.id.in_(permission_ids),
                Permission.is_deleted.is_(False),
            )
            .all()
        )

    def assign_permissions(self, role: Role, permission_ids: list[int]) -> Role:
        """
        Attach permissions to a role.

        Existing links are preserved.

        Args:
            role: Target role.
            permission_ids: Permission IDs to attach.

        Returns:
            Role: Refreshed role with permission relationships loaded.
        """
        existing_permission_ids = {
            link.permission_id
            for link in role.role_permissions
        }

        for permission_id in permission_ids:
            if permission_id in existing_permission_ids:
                continue

            link = RolePermissionAssociation(
                role_id=role.id,
                permission_id=permission_id,
            )
            self.db.add(link)

        self.db.flush()
        return self.get_required_by_id(role.id)

    def remove_permissions(self, role: Role, permission_ids: list[int]) -> Role:
        """
        Remove permission links from a role.

        Args:
            role: Target role.
            permission_ids: Permission IDs to remove.

        Returns:
            Role: Refreshed role with permission relationships loaded.
        """
        if permission_ids:
            (
                self.db.query(RolePermissionAssociation)
                .filter(
                    RolePermissionAssociation.role_id == role.id,
                    RolePermissionAssociation.permission_id.in_(permission_ids),
                )
                .delete(synchronize_session=False)
            )

        self.db.flush()
        return self.get_required_by_id(role.id)

    def get_required_by_id(self, role_id: int) -> Role:
        """
        Return a role by ID or raise NotFoundError.

        Args:
            role_id: Role primary key.

        Returns:
            Role: Matching role.

        Raises:
            NotFoundError: If the role does not exist.
        """
        role = self.get_by_id(role_id)
        if not role:
            raise NotFoundError(
                message="Role not found.",
                detail={"role_id": role_id},
            )
        return role