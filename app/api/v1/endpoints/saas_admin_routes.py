# app/api/v1/endpoints/saas_admin_routes.py
from typing import Annotated, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_master_db
from app.core.dependencies import CurrentSaaSAdmin, CurrentSaaSSuperuser
from app.schemas.saas_auth_schemas import SaaSAdminReadSchema
from app.schemas.saas_admin_schemas import (
    SaaSAdminCreateSchema, 
    SaaSAdminUpdateStatusSchema,
    SaaSAdminUpdateSchema
)
from app.services.saas_admin_service import SaaSAdminService

router = APIRouter(prefix="/saas/admins", tags=["SaaS - Administrators"])

def get_admin_service(db: Annotated[Session, Depends(get_master_db)]) -> SaaSAdminService:
    return SaaSAdminService(db)

@router.get(
    "",
    response_model=List[SaaSAdminReadSchema],
    status_code=status.HTTP_200_OK,
    summary="List all SaaS administrators",
)
def list_admins(
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSAdminService, Depends(get_admin_service)],
):
    """
    List all global SaaS administrators.
    """
    return service.list_admins()

@router.post(
    "",
    response_model=SaaSAdminReadSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new SaaS administrator",
)
def create_admin(
    payload: SaaSAdminCreateSchema,
    _: CurrentSaaSSuperuser,
    service: Annotated[SaaSAdminService, Depends(get_admin_service)],
):
    """
    Create a new global SaaS administrator.
    Requires SaaS Superuser access.
    """
    return service.create_admin(payload)

@router.put(
    "/{admin_id}/status",
    response_model=SaaSAdminReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update SaaS administrator status",
)
def update_admin_status(
    admin_id: int,
    payload: SaaSAdminUpdateStatusSchema,
    _: CurrentSaaSSuperuser,
    service: Annotated[SaaSAdminService, Depends(get_admin_service)],
):
    """
    Suspend or activate a SaaS administrator.
    Requires SaaS Superuser access.
    """
    return service.update_admin_status(admin_id, payload.status)

@router.get(
    "/{admin_id}",
    response_model=SaaSAdminReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get SaaS administrator details",
)
def get_admin(
    admin_id: int,
    _: CurrentSaaSAdmin,
    service: Annotated[SaaSAdminService, Depends(get_admin_service)],
):
    """
    Retrieve details of a specific SaaS administrator.
    """
    return service.get_admin(admin_id)

@router.put(
    "/{admin_id}",
    response_model=SaaSAdminReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update SaaS administrator",
)
def update_admin(
    admin_id: int,
    payload: SaaSAdminUpdateSchema,
    _: CurrentSaaSSuperuser,
    service: Annotated[SaaSAdminService, Depends(get_admin_service)],
):
    """
    Update a SaaS administrator's details.
    Requires SaaS Superuser access.
    """
    return service.update_admin(admin_id, payload)

@router.delete(
    "/{admin_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Delete a SaaS administrator",
)
def delete_admin(
    admin_id: int,
    current_admin: CurrentSaaSSuperuser,
    service: Annotated[SaaSAdminService, Depends(get_admin_service)],
):
    """
    Soft delete a SaaS administrator.
    Requires SaaS Superuser access.
    """
    return service.delete_admin(admin_id, current_admin.id)
