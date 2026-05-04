# app/repositories/permission_repository.py
from __future__ import annotations

"""
app.repositories.permission_repository

Repository layer for fine-grained permission CRUD and lookup logic.

Purpose
-------
Centralizes direct database operations for the Permission model and the
RolePermissionAssociation join table.

Responsibilities
----------------
- create / read / update / soft-delete permissions
- list and search permissions with pagination
- resolve a user's effective permission set via Role -> RolePermissionAssociation
- bulk upsert permissions during seeding
"""

from typing import Iterable, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import (
    Permission,
    Role,
    RolePermissionAssociation,
    User,
    UserRoleAssociation,
)


class PermissionRepository:
    """
    Repository for permission persistence and lookup operations.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the repository with an active SQLAlchemy session.
        """
        self.db = db

    # ============================================================
    # SINGLE-RECORD LOOKUPS
    # ============================================================

    def get_by_id(self, permission_id: int) -> Optional[Permission]:
        """
        Return a permission by primary key (excludes soft-deleted rows).
        """
        return (
            self.db.query(Permission)
            .filter(
                Permission.id == permission_id,
                Permission.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, permission_id: int) -> Permission:
        """
        Return a permission by ID or raise NotFoundError.
        """
        permission = self.get_by_id(permission_id)
        if not permission:
            raise NotFoundError(
                message="Permission not found.",
                detail={"permission_id": permission_id},
            )
        return permission

    def get_by_code(self, code: str) -> Optional[Permission]:
        """
        Return a permission by code (case-insensitive, soft-deleted excluded).
        """
        normalized = code.strip().upper()
        return (
            self.db.query(Permission)
            .filter(
                func.upper(Permission.code) == normalized,
                Permission.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_name(self, name: str) -> Optional[Permission]:
        """
        Return a permission by name.
        """
        normalized = name.strip().lower()
        return (
            self.db.query(Permission)
            .filter(
                func.lower(Permission.name) == normalized,
                Permission.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # LISTING
    # ============================================================

    def list_permissions(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        module: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[list[Permission], int]:
        """
        List permissions with optional filtering and pagination.

        Args:
            skip: Pagination offset.
            limit: Pagination size.
            module: Optional module filter (case-insensitive exact match).
            search: Optional substring search across name/code/description.

        Returns:
            tuple[list[Permission], int]:
                - permissions matching the filters for the current page
                - total count
        """
        query = self.db.query(Permission).filter(Permission.is_deleted.is_(False))

        if module:
            query = query.filter(func.upper(Permission.module) == module.strip().upper())

        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(Permission.name).like(term),
                    func.lower(Permission.code).like(term),
                    func.lower(func.coalesce(Permission.description, "")).like(term),
                )
            )

        total = query.with_entities(func.count(Permission.id)).scalar() or 0
        items = (
            query.order_by(Permission.module.asc().nullsfirst(), Permission.code.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def list_modules(self) -> list[str]:
        """
        Return distinct module names that have permissions.
        """
        rows = (
            self.db.query(Permission.module)
            .filter(
                Permission.is_deleted.is_(False),
                Permission.module.isnot(None),
            )
            .distinct()
            .order_by(Permission.module.asc())
            .all()
        )
        return [r[0] for r in rows if r[0]]

    # ============================================================
    # CRUD
    # ============================================================

    def create_permission(
        self,
        *,
        name: str,
        code: str,
        module: Optional[str] = None,
        description: Optional[str] = None,
        is_system: bool = False,
    ) -> Permission:
        """
        Create a new permission.

        Raises:
            AlreadyExistsError: If a permission with this code/name already exists.
        """
        if self.get_by_code(code):
            raise AlreadyExistsError(
                message="A permission with this code already exists.",
                detail={"code": code},
            )

        if self.get_by_name(name):
            raise AlreadyExistsError(
                message="A permission with this name already exists.",
                detail={"name": name},
            )

        permission = Permission(
            name=name,
            code=code,
            module=module,
            description=description,
            is_system=is_system,
        )
        self.db.add(permission)
        self.db.flush()
        self.db.refresh(permission)
        return permission

    def update_permission(
        self,
        permission: Permission,
        *,
        name: Optional[str] = None,
        code: Optional[str] = None,
        module: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Permission:
        """
        Update mutable fields on a permission.

        System permissions are immutable except for description.
        """
        if permission.is_system and (name is not None or code is not None):
            # Allow description tweaks but block code/name changes on system permissions.
            name = None
            code = None

        if code and code != permission.code:
            existing = self.get_by_code(code)
            if existing and existing.id != permission.id:
                raise AlreadyExistsError(
                    message="A permission with this code already exists.",
                    detail={"code": code},
                )

        if name and name != permission.name:
            existing = self.get_by_name(name)
            if existing and existing.id != permission.id:
                raise AlreadyExistsError(
                    message="A permission with this name already exists.",
                    detail={"name": name},
                )

        if name is not None:
            permission.name = name
        if code is not None:
            permission.code = code
        if module is not None:
            permission.module = module
        if description is not None:
            permission.description = description

        self.db.add(permission)
        self.db.flush()
        self.db.refresh(permission)
        return permission

    def soft_delete_permission(self, permission: Permission) -> Permission:
        """
        Soft-delete a permission. System permissions cannot be deleted.
        """
        if permission.is_system:
            raise AlreadyExistsError(
                message="System permissions cannot be deleted.",
                error_code="SYSTEM_PERMISSION_PROTECTED",
                detail={"permission_id": permission.id, "code": permission.code},
            )

        permission.is_deleted = True
        self.db.add(permission)
        self.db.flush()
        return permission

    # ============================================================
    # BULK / UPSERT
    # ============================================================

    def upsert_permission(
        self,
        *,
        name: str,
        code: str,
        module: Optional[str] = None,
        description: Optional[str] = None,
        is_system: bool = False,
    ) -> tuple[Permission, str]:
        """
        Insert or update a permission keyed by code.

        Returns:
            tuple[Permission, str]:
                - the persisted permission
                - "created", "updated", or "unchanged"
        """
        existing = self.get_by_code(code)
        if existing is None:
            permission = self.create_permission(
                name=name,
                code=code,
                module=module,
                description=description,
                is_system=is_system,
            )
            return permission, "created"

        changed = False
        if existing.name != name:
            existing.name = name
            changed = True
        if module is not None and existing.module != module:
            existing.module = module
            changed = True
        if description is not None and existing.description != description:
            existing.description = description
            changed = True
        if existing.is_system != is_system:
            existing.is_system = is_system
            changed = True

        if changed:
            self.db.add(existing)
            self.db.flush()
            self.db.refresh(existing)
            return existing, "updated"

        return existing, "unchanged"

    # ============================================================
    # RESOLUTION HELPERS
    # ============================================================

    def get_permissions_for_role(self, role_id: int) -> list[Permission]:
        """
        Return all active permissions linked to a role.
        """
        return (
            self.db.query(Permission)
            .join(
                RolePermissionAssociation,
                RolePermissionAssociation.permission_id == Permission.id,
            )
            .filter(
                RolePermissionAssociation.role_id == role_id,
                RolePermissionAssociation.is_deleted.is_(False),
                Permission.is_deleted.is_(False),
            )
            .order_by(Permission.module.asc().nullsfirst(), Permission.code.asc())
            .all()
        )

    def get_permission_codes_for_user(self, user_id: int) -> set[str]:
        """
        Return the set of permission codes a user has via assigned roles.

        Notes
        -----
        Superusers have all permissions. This helper does not return a
        wildcard for superusers; the dependency layer applies that policy.
        """
        rows = (
            self.db.query(Permission.code)
            .join(
                RolePermissionAssociation,
                RolePermissionAssociation.permission_id == Permission.id,
            )
            .join(
                Role,
                Role.id == RolePermissionAssociation.role_id,
            )
            .join(
                UserRoleAssociation,
                UserRoleAssociation.role_id == Role.id,
            )
            .filter(
                UserRoleAssociation.user_id == user_id,
                UserRoleAssociation.is_deleted.is_(False),
                Role.is_deleted.is_(False),
                Permission.is_deleted.is_(False),
                RolePermissionAssociation.is_deleted.is_(False),
            )
            .distinct()
            .all()
        )
        return {row[0].upper() for row in rows if row[0]}

    def user_has_permission(self, user_id: int, permission_code: str) -> bool:
        """
        Return whether a user has a given permission via any assigned role.
        """
        normalized = permission_code.strip().upper()
        if not normalized:
            return False

        # Cheap superuser bypass — the dependency layer also handles this,
        # but having it here keeps repository-level checks safe.
        is_superuser = (
            self.db.query(User.is_superuser)
            .filter(User.id == user_id, User.is_deleted.is_(False))
            .scalar()
        )
        if is_superuser:
            return True

        exists = (
            self.db.query(Permission.id)
            .join(
                RolePermissionAssociation,
                RolePermissionAssociation.permission_id == Permission.id,
            )
            .join(
                Role,
                Role.id == RolePermissionAssociation.role_id,
            )
            .join(
                UserRoleAssociation,
                UserRoleAssociation.role_id == Role.id,
            )
            .filter(
                UserRoleAssociation.user_id == user_id,
                UserRoleAssociation.is_deleted.is_(False),
                Role.is_deleted.is_(False),
                Permission.is_deleted.is_(False),
                RolePermissionAssociation.is_deleted.is_(False),
                func.upper(Permission.code) == normalized,
            )
            .first()
        )
        return exists is not None

    def get_permissions_by_codes(self, codes: Iterable[str]) -> list[Permission]:
        """
        Return permissions matching any of the supplied codes.
        """
        normalized = [c.strip().upper() for c in codes if c and c.strip()]
        if not normalized:
            return []

        return (
            self.db.query(Permission)
            .filter(
                func.upper(Permission.code).in_(normalized),
                Permission.is_deleted.is_(False),
            )
            .all()
        )
