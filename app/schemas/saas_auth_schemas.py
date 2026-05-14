# app/schemas/saas_auth_schemas.py
from pydantic import BaseModel, EmailStr, ConfigDict

class SaaSAdminLoginSchema(BaseModel):
    email: EmailStr
    password: str

class SaaSAdminReadSchema(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    is_superuser: bool
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SaaSAdminLoginResponseSchema(BaseModel):
    success: bool
    message: str
    access_token: str
    refresh_token: str
    token_type: str
    user: SaaSAdminReadSchema

class SaaSImpersonateSchema(BaseModel):
    tenant_code: str

class SaaSImpersonateResponseSchema(BaseModel):
    success: bool
    message: str
    access_token: str
    refresh_token: str
    token_type: str
    tenant_code: str
    tenant_name: str
