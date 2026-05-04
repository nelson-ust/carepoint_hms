from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.core.enums import IntegrationProtocol, IntegrationDirection, IntegrationProviderType

class IntegrationCredentialBase(BaseModel):
    credential_type: str
    secret_reference: str # This will be encrypted before storage

class IntegrationCredentialRead(IntegrationCredentialBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class IntegrationEndpointBase(BaseModel):
    code: str
    name: str
    base_url: str
    protocol: IntegrationProtocol
    provider_type: IntegrationProviderType
    direction: IntegrationDirection = IntegrationDirection.OUTBOUND
    is_active: bool = True

class IntegrationEndpointCreate(IntegrationEndpointBase):
    credentials: Optional[List[IntegrationCredentialBase]] = None

class IntegrationEndpointUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    protocol: Optional[IntegrationProtocol] = None
    provider_type: Optional[IntegrationProviderType] = None
    direction: Optional[IntegrationDirection] = None
    is_active: Optional[bool] = None

class IntegrationEndpointRead(IntegrationEndpointBase):
    id: int
    credentials: List[IntegrationCredentialRead]
    model_config = ConfigDict(from_attributes=True)
