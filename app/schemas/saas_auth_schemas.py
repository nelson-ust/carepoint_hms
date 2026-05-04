# app/schemas/saas_auth_schemas.py
from pydantic import BaseModel, EmailStr

class SaaSAdminLoginSchema(BaseModel):
    email: EmailStr
    password: str

class SaaSAdminLoginResponseSchema(BaseModel):
    success: bool
    message: str
    access_token: str
    refresh_token: str
    token_type: str
    admin_id: int
    email: str
    first_name: str
    last_name: str

class SaaSAdminReadSchema(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    is_superuser: bool
    is_active: bool

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
