from typing import List, Optional
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session
from jinja2 import Template
from app.models.all_models import ClinicalTemplate, NotificationTemplate, DocumentTemplate
from app.schemas.template_schemas import (
    ClinicalTemplateCreate,
    ClinicalTemplateUpdate,
    NotificationTemplateCreate,
    DocumentTemplateCreate,
)
from app.core.exceptions import NotFoundError, BadRequestError

class TemplateService:
    def __init__(self, db: Session):
        self.db = db

    # Notification Templates
    def get_notification_templates(self) -> List[NotificationTemplate]:
        return self.db.query(NotificationTemplate).all()

    def create_notification_template(self, payload: NotificationTemplateCreate) -> NotificationTemplate:
        template = NotificationTemplate(**payload.model_dump())
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    # Document Templates
    def get_document_templates(self) -> List[DocumentTemplate]:
        return self.db.query(DocumentTemplate).all()

    def create_document_template(self, payload: DocumentTemplateCreate) -> DocumentTemplate:
        # If this is set as default, unset others of the same type
        if payload.is_default:
            self.db.query(DocumentTemplate).filter(
                DocumentTemplate.template_type == payload.template_type
            ).update({"is_default": False})

        template = DocumentTemplate(**payload.model_dump())
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    # ------------------------------------------------------------------
    # Clinical documentation templates
    # ------------------------------------------------------------------

    def _clinical_query(self):
        return self.db.query(ClinicalTemplate).filter(ClinicalTemplate.is_deleted.is_(False))

    def get_clinical_templates(
        self,
        *,
        search: Optional[str] = None,
        specialty: Optional[str] = None,
        template_type: Optional[str] = None,
    ) -> List[ClinicalTemplate]:
        query = self._clinical_query()
        if search:
            like = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    ClinicalTemplate.name.ilike(like),
                    ClinicalTemplate.specialty.ilike(like),
                    ClinicalTemplate.description.ilike(like),
                )
            )
        if specialty:
            query = query.filter(ClinicalTemplate.specialty.ilike(specialty.strip()))
        if template_type:
            query = query.filter(ClinicalTemplate.template_type == template_type.upper())
        return query.order_by(
            desc(ClinicalTemplate.is_favorite),
            desc(ClinicalTemplate.date_updated),
        ).all()

    def get_clinical_template(self, template_id: int) -> ClinicalTemplate:
        record = self._clinical_query().filter(ClinicalTemplate.id == template_id).first()
        if record is None:
            raise NotFoundError(message="Clinical template not found.")
        return record

    def get_clinical_template_stats(self) -> dict:
        rows = self._clinical_query().all()
        specialties = sorted({r.specialty for r in rows if r.specialty})
        commonly_used = len([r for r in rows if r.is_favorite or (r.usage_count or 0) >= 5])
        return {"total": len(rows), "commonly_used": commonly_used, "specialties": specialties}

    def create_clinical_template(self, payload: ClinicalTemplateCreate) -> ClinicalTemplate:
        record = ClinicalTemplate(
            name=payload.name.strip(),
            description=payload.description,
            specialty=(payload.specialty or None) and payload.specialty.strip(),
            template_type=payload.template_type,
            sections=[s.model_dump() for s in payload.sections],
            is_favorite=payload.is_favorite,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_clinical_template(self, template_id: int, payload: ClinicalTemplateUpdate) -> ClinicalTemplate:
        record = self.get_clinical_template(template_id)
        data = payload.model_dump(exclude_unset=True)
        if "sections" in data and data["sections"] is not None:
            data["sections"] = [
                s.model_dump() if hasattr(s, "model_dump") else s for s in payload.sections
            ]
        for key, value in data.items():
            setattr(record, key, value)
        self.db.commit()
        self.db.refresh(record)
        return record

    def delete_clinical_template(self, template_id: int) -> None:
        record = self.get_clinical_template(template_id)
        record.soft_delete()
        self.db.commit()

    def duplicate_clinical_template(self, template_id: int) -> ClinicalTemplate:
        source = self.get_clinical_template(template_id)
        copy = ClinicalTemplate(
            name=f"{source.name} (Copy)"[:150],
            description=source.description,
            specialty=source.specialty,
            template_type=source.template_type,
            sections=list(source.sections or []),
            is_favorite=False,
        )
        self.db.add(copy)
        self.db.commit()
        self.db.refresh(copy)
        return copy

    def record_clinical_template_use(self, template_id: int) -> ClinicalTemplate:
        record = self.get_clinical_template(template_id)
        record.usage_count = (record.usage_count or 0) + 1
        self.db.commit()
        self.db.refresh(record)
        return record

    def render_document(self, template_code: str, context: dict) -> str:
        template_record = self.db.query(DocumentTemplate).filter(DocumentTemplate.code == template_code).first()
        if not template_record:
            raise NotFoundError(message=f"Template with code {template_code} not found.")
        
        try:
            template = Template(template_record.body_html)
            return template.render(**context)
        except Exception as e:
            raise BadRequestError(message=f"Error rendering template: {str(e)}")
