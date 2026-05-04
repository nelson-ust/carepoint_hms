from typing import Annotated
from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_permission
from app.core.multitenancy import get_current_tenant
from app.schemas.tenant_setting_schemas import TenantSettingReadSchema, TenantSettingUpdateSchema
from app.services.tenant_setting_service import TenantSettingService

router = APIRouter(prefix="/settings", tags=["Tenant - Settings"])

def get_setting_service(db: Annotated[Session, Depends(get_db)]) -> TenantSettingService:
    tenant = get_current_tenant()
    return TenantSettingService(db, tenant.code)

@router.get(
    "",
    response_model=TenantSettingReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Get Tenant Settings",
)
def get_settings(
    _: CurrentActiveUser,
    service: Annotated[TenantSettingService, Depends(get_setting_service)]
):
    """
    Retrieve settings (Logo, Theme, Timezone, Currency) for the current tenant.
    """
    return service.get_settings()

@router.put(
    "",
    response_model=TenantSettingReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Update Tenant Settings",
)
def update_settings(
    payload: TenantSettingUpdateSchema,
    _: Annotated[bool, Depends(require_permission("SETTING_UPDATE"))],
    service: Annotated[TenantSettingService, Depends(get_setting_service)]
):
    """
    Update tenant settings. Requires SETTING_UPDATE permission.
    """
    return service.update_settings(payload)

@router.post(
    "/logo",
    response_model=TenantSettingReadSchema,
    status_code=status.HTTP_200_OK,
    summary="Upload Tenant Logo",
)
def upload_logo(
    file: UploadFile = File(...),
    _: Annotated[bool, Depends(require_permission("SETTING_UPDATE"))] = None,
    service: TenantSettingService = Depends(get_setting_service)
):
    """
    Upload a logo to the tenant's AWS S3 bucket and update the settings.
    Requires SETTING_UPDATE permission.
    """
    return service.upload_logo(file)
