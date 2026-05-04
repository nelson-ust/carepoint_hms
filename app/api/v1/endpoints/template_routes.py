from typing import List, Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.template_schemas import (
    NotificationTemplateRead, NotificationTemplateCreate,
    DocumentTemplateRead, DocumentTemplateCreate
)
from app.services.template_service import TemplateService
from app.dependencies.role import require_permission

router = APIRouter(prefix="/templates", tags=["Template Management"])

@router.get("/notifications", response_model=List[NotificationTemplateRead])
def list_notification_templates(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_READ"))]
):
    return TemplateService(db).get_notification_templates()

@router.post("/notifications", response_model=NotificationTemplateRead, status_code=status.HTTP_201_CREATED)
def create_notification_template(
    payload: NotificationTemplateCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_CREATE"))]
):
    return TemplateService(db).create_notification_template(payload)

@router.get("/documents", response_model=List[DocumentTemplateRead])
def list_document_templates(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_READ"))]
):
    return TemplateService(db).get_document_templates()

@router.post("/documents", response_model=DocumentTemplateRead, status_code=status.HTTP_201_CREATED)
def create_document_template(
    payload: DocumentTemplateCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_CREATE"))]
):
    return TemplateService(db).create_document_template(payload)
