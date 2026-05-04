from typing import List, Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.integration_schemas import IntegrationEndpointRead, IntegrationEndpointCreate, IntegrationEndpointUpdate
from app.services.integration_service import IntegrationService
from app.dependencies.role import require_permission

router = APIRouter(prefix="/integrations", tags=["Integrations Management"])

@router.get("/", response_model=List[IntegrationEndpointRead])
def list_integrations(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("INTEGRATION_READ"))]
):
    return IntegrationService(db).get_endpoints()

@router.post("/", response_model=IntegrationEndpointRead, status_code=status.HTTP_201_CREATED)
def create_integration(
    payload: IntegrationEndpointCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("INTEGRATION_CREATE"))]
):
    return IntegrationService(db).create_endpoint(payload)

@router.get("/{endpoint_id}", response_model=IntegrationEndpointRead)
def get_integration(
    endpoint_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("INTEGRATION_READ"))]
):
    return IntegrationService(db).get_endpoint(endpoint_id)

@router.put("/{endpoint_id}", response_model=IntegrationEndpointRead)
def update_integration(
    endpoint_id: int,
    payload: IntegrationEndpointUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("INTEGRATION_UPDATE"))]
):
    return IntegrationService(db).update_endpoint(endpoint_id, payload)

@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_integration(
    endpoint_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("INTEGRATION_DELETE"))]
):
    IntegrationService(db).delete_endpoint(endpoint_id)
    return None
