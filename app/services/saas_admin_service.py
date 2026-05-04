# app/services/saas_admin_service.py
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.enums import SaaSRole, UserStatus
from app.core.security import get_password_hash
from app.models.all_models import SaaSAdmin
from app.models.base import utc_now
from app.schemas.saas_admin_schemas import SaaSAdminCreateSchema, SaaSAdminUpdateSchema


def _coerce_platform_role(value: Optional[str]) -> Optional[SaaSRole]:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    try:
        return SaaSRole(normalized)
    except ValueError:
        raise BadRequestError(
            message=f"Unsupported platform_role '{value}'.",
            detail={"allowed": [r.value for r in SaaSRole]},
        )

class SaaSAdminService:
    def __init__(self, db: Session):
        self.db = db

    def list_admins(self) -> List[SaaSAdmin]:
        return self.db.query(SaaSAdmin).filter(SaaSAdmin.is_deleted == False).order_by(SaaSAdmin.id.asc()).all()

    def get_admin(self, admin_id: int) -> SaaSAdmin:
        admin = self.db.query(SaaSAdmin).filter(SaaSAdmin.id == admin_id, SaaSAdmin.is_deleted == False).first()
        if not admin:
            raise NotFoundError(message="SaaS Admin not found.")
        return admin

    def create_admin(self, payload: SaaSAdminCreateSchema) -> SaaSAdmin:
        existing = self.db.query(SaaSAdmin).filter(SaaSAdmin.email == payload.email.lower()).first()
        if existing:
            raise BadRequestError(message="SaaS Admin with this email already exists.")

        platform_role = _coerce_platform_role(payload.platform_role) or SaaSRole.SUPPORT_ADMIN
        # ``is_superuser`` is auto-derived from SUPER_ADMIN. We honor an
        # explicit override only when it raises privilege; downgrading
        # SUPER_ADMIN to non-superuser is rejected.
        is_superuser = bool(payload.is_superuser) or platform_role == SaaSRole.SUPER_ADMIN
        if platform_role == SaaSRole.SUPER_ADMIN and not is_superuser:
            raise BadRequestError(message="SUPER_ADMIN must be flagged as a superuser.")

        admin = SaaSAdmin(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email.lower(),
            phone_number=payload.phone_number,
            password_hash=get_password_hash(payload.password),
            status=UserStatus.ACTIVE,
            is_superuser=is_superuser,
            platform_role=platform_role,
        )
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)
        return admin

    def update_admin_status(self, admin_id: int, new_status: str) -> SaaSAdmin:
        admin = self.get_admin(admin_id)
        
        try:
            status_enum = UserStatus[new_status.upper()]
        except KeyError:
            raise BadRequestError(message=f"Invalid status: {new_status}")
            
        admin.status = status_enum
        self.db.commit()
        self.db.refresh(admin)
        return admin

    def update_admin(self, admin_id: int, payload: SaaSAdminUpdateSchema) -> SaaSAdmin:
        admin = self.get_admin(admin_id)

        update_data = payload.model_dump(exclude_unset=True)

        if "email" in update_data:
            existing = self.db.query(SaaSAdmin).filter(
                SaaSAdmin.email == update_data["email"].lower(),
                SaaSAdmin.id != admin_id,
                SaaSAdmin.is_deleted == False,
            ).first()
            if existing:
                raise BadRequestError(message="Another SaaS Admin with this email already exists.")
            update_data["email"] = update_data["email"].lower()

        if "platform_role" in update_data and update_data["platform_role"] is not None:
            new_role = _coerce_platform_role(update_data["platform_role"])
            update_data["platform_role"] = new_role
            # Keep is_superuser in sync with SUPER_ADMIN unless the caller
            # explicitly set it in the same payload.
            if "is_superuser" not in update_data:
                if new_role == SaaSRole.SUPER_ADMIN:
                    update_data["is_superuser"] = True
                elif admin.is_superuser and admin.platform_role == SaaSRole.SUPER_ADMIN:
                    update_data["is_superuser"] = False

        for key, value in update_data.items():
            setattr(admin, key, value)

        self.db.commit()
        self.db.refresh(admin)
        return admin

    def delete_admin(self, admin_id: int, current_admin_id: int) -> dict:
        admin = self.get_admin(admin_id)
        
        if admin.id == current_admin_id:
            raise BadRequestError(message="You cannot delete your own account.")
            
        admin.is_deleted = True
        admin.status = UserStatus.SUSPENDED
        admin.date_deleted = utc_now()
        admin.deleted_by_id = current_admin_id
        
        self.db.commit()
        return {"success": True, "message": "SaaS Admin deleted successfully."}
