# app/services/permission_service.py
from __future__ import annotations

"""
app.services.permission_service

Service layer for fine-grained permission management.

Responsibilities
----------------
- orchestrate permission CRUD
- resolve effective permission codes for a user
- bulk-upsert permissions during seeding
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.models.all_models import Permission
from app.repositories.permission_repository import PermissionRepository
from app.schemas.permission_schema import (
    PermissionBulkCreateSchema,
    PermissionCreateSchema,
    PermissionUpdateSchema,
)


class PermissionService:
    """
    Service layer for permission management.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = PermissionRepository(db)

    # ============================================================
    # READ
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
        Return paginated permissions.
        """
        return self.repository.list_permissions(
            skip=skip,
            limit=limit,
            module=module,
            search=search,
        )

    def list_modules(self) -> list[str]:
        """
        Return distinct module labels.
        """
        return self.repository.list_modules()

    def get_permission(self, permission_id: int) -> Permission:
        """
        Return a permission by ID.
        """
        return self.repository.get_required_by_id(permission_id)

    # ============================================================
    # WRITE
    # ============================================================

    def create_permission(self, payload: PermissionCreateSchema) -> Permission:
        """
        Create a new permission.
        """
        permission = self.repository.create_permission(
            name=payload.name,
            code=payload.code,
            module=payload.module,
            description=payload.description,
            is_system=payload.is_system,
        )
        self.db.commit()
        return permission

    def update_permission(
        self,
        permission_id: int,
        payload: PermissionUpdateSchema,
    ) -> Permission:
        """
        Update a permission.
        """
        permission = self.repository.get_required_by_id(permission_id)
        updated = self.repository.update_permission(
            permission,
            name=payload.name,
            code=payload.code,
            module=payload.module,
            description=payload.description,
        )
        self.db.commit()
        return updated

    def delete_permission(self, permission_id: int) -> Permission:
        """
        Soft-delete a permission. System permissions cannot be deleted.
        """
        permission = self.repository.get_required_by_id(permission_id)
        deleted = self.repository.soft_delete_permission(permission)
        self.db.commit()
        return deleted

    def bulk_upsert(self, payload: PermissionBulkCreateSchema) -> dict:
        """
        Bulk-upsert permissions keyed by code.

        Returns:
            dict: counts of created/updated/unchanged plus the resulting list.
        """
        if not payload.permissions:
            raise BadRequestError(message="At least one permission must be supplied.")

        created = 0
        updated = 0
        unchanged = 0
        items: list[Permission] = []

        for permission_payload in payload.permissions:
            permission, action = self.repository.upsert_permission(
                name=permission_payload.name,
                code=permission_payload.code,
                module=permission_payload.module,
                description=permission_payload.description,
                is_system=permission_payload.is_system,
            )
            items.append(permission)
            if action == "created":
                created += 1
            elif action == "updated":
                updated += 1
            else:
                unchanged += 1

        self.db.commit()
        return {
            "created_count": created,
            "updated_count": updated,
            "skipped_count": unchanged,
            "items": items,
        }

    # ============================================================
    # RESOLUTION
    # ============================================================

    def get_permission_codes_for_user(self, user_id: int) -> set[str]:
        """
        Return the set of permission codes a user has via roles.
        """
        return self.repository.get_permission_codes_for_user(user_id)

    def user_has_permission(self, user_id: int, permission_code: str) -> bool:
        """
        Check whether a user has a permission via roles.
        """
        return self.repository.user_has_permission(user_id, permission_code)
