from typing import List, Optional
from sqlalchemy.orm import Session
from jinja2 import Template
from app.models.all_models import NotificationTemplate, DocumentTemplate
from app.schemas.template_schemas import NotificationTemplateCreate, DocumentTemplateCreate
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

    def render_document(self, template_code: str, context: dict) -> str:
        template_record = self.db.query(DocumentTemplate).filter(DocumentTemplate.code == template_code).first()
        if not template_record:
            raise NotFoundError(message=f"Template with code {template_code} not found.")
        
        try:
            template = Template(template_record.body_html)
            return template.render(**context)
        except Exception as e:
            raise BadRequestError(message=f"Error rendering template: {str(e)}")
