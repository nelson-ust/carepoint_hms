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


# ---------------------------------------------------------------------------
# Hospital Membership Number configuration (configurable numbering scheme)
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field  # noqa: E402
from typing import Optional  # noqa: E402


class HospitalNumberConfigSchema(BaseModel):
    prefix: Optional[str] = Field(None, max_length=24)
    suffix: Optional[str] = Field(None, max_length=24)
    branch_code: Optional[str] = Field(None, max_length=24)
    separator: Optional[str] = Field(None, max_length=4)
    include_year: Optional[bool] = None
    year_format: Optional[str] = None  # "YYYY" | "YY"
    include_month: Optional[bool] = None
    min_digits: Optional[int] = Field(None, ge=1, le=12)
    reset_mode: Optional[str] = None  # CONTINUOUS | ANNUAL | MONTHLY
    next_sequence: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


@router.get(
    "/hospital-number-config",
    summary="Get the tenant's Hospital Membership Number numbering scheme",
)
def get_hospital_number_config(
    _: Annotated[bool, Depends(require_permission("SETTING"))],
    db: Annotated[Session, Depends(get_db)],
):
    from app.services.hospital_number_service import HospitalNumberService
    svc = HospitalNumberService(db)
    cfg = svc.get_or_create_config()
    db.commit()
    return {"success": True, "config": svc.to_dict(cfg)}


@router.put(
    "/hospital-number-config",
    summary="Update the tenant's Hospital Membership Number numbering scheme",
)
def update_hospital_number_config(
    payload: HospitalNumberConfigSchema,
    _: Annotated[bool, Depends(require_permission("SETTING_UPDATE"))],
    db: Annotated[Session, Depends(get_db)],
):
    from app.services.hospital_number_service import HospitalNumberService
    svc = HospitalNumberService(db)
    cfg = svc.update_config(payload.model_dump(exclude_unset=True))
    return {"success": True, "message": "Numbering scheme updated.",
            "config": svc.to_dict(cfg)}


@router.get(
    "/hospital-number-config/preview",
    summary="Preview the next Hospital Membership Number for the current scheme",
)
def preview_hospital_number(
    _: Annotated[bool, Depends(require_permission("SETTING"))],
    db: Annotated[Session, Depends(get_db)],
):
    from app.services.hospital_number_service import HospitalNumberService
    return {"success": True, "sample": HospitalNumberService(db).preview()}
