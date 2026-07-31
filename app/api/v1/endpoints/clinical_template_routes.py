# app/api/v1/endpoints/clinical_template_routes.py
"""
Clinical documentation template management.

Backs the "Clinical Templates" page in the tenant UI: reusable SOAP,
history, examination, and procedure note templates. Reads are gated by
TEMPLATE_READ and writes by TEMPLATE_CREATE (both already seeded and
granted to tenant admin roles; superusers bypass).
"""
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.role import require_permission
from app.schemas.template_schemas import (
    ClinicalTemplateCreate,
    ClinicalTemplateRead,
    ClinicalTemplateStats,
    ClinicalTemplateUpdate,
)
from app.services.template_service import TemplateService

router = APIRouter(prefix="/clinical-templates", tags=["Clinical Templates"])


@router.get("", response_model=List[ClinicalTemplateRead])
def list_clinical_templates(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_READ"))],
    search: Optional[str] = Query(None, description="Match name, specialty, or description"),
    specialty: Optional[str] = Query(None),
    template_type: Optional[str] = Query(None),
):
    return TemplateService(db).get_clinical_templates(
        search=search, specialty=specialty, template_type=template_type
    )


@router.get("/stats", response_model=ClinicalTemplateStats)
def get_clinical_template_stats(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_READ"))],
):
    return TemplateService(db).get_clinical_template_stats()


@router.get("/{template_id}", response_model=ClinicalTemplateRead)
def get_clinical_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_READ"))],
):
    return TemplateService(db).get_clinical_template(template_id)


@router.post("", response_model=ClinicalTemplateRead, status_code=status.HTTP_201_CREATED)
def create_clinical_template(
    payload: ClinicalTemplateCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_CREATE"))],
):
    return TemplateService(db).create_clinical_template(payload)


@router.put("/{template_id}", response_model=ClinicalTemplateRead)
def update_clinical_template(
    template_id: int,
    payload: ClinicalTemplateUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_CREATE"))],
):
    return TemplateService(db).update_clinical_template(template_id, payload)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_clinical_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_CREATE"))],
):
    TemplateService(db).delete_clinical_template(template_id)


@router.post("/{template_id}/duplicate", response_model=ClinicalTemplateRead, status_code=status.HTTP_201_CREATED)
def duplicate_clinical_template(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_CREATE"))],
):
    return TemplateService(db).duplicate_clinical_template(template_id)


@router.post("/{template_id}/use", response_model=ClinicalTemplateRead)
def record_clinical_template_use(
    template_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[bool, Depends(require_permission("TEMPLATE_READ"))],
):
    """Increment the usage counter when a clinician applies a template."""
    return TemplateService(db).record_clinical_template_use(template_id)
