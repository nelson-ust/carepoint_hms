from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.core.enums import NotificationChannel, DocumentTemplateType

class NotificationTemplateBase(BaseModel):
    name: str
    code: str
    channel: NotificationChannel
    subject_template: Optional[str] = None
    body_template: str

class NotificationTemplateCreate(NotificationTemplateBase):
    pass

class NotificationTemplateRead(NotificationTemplateBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class DocumentTemplateBase(BaseModel):
    name: str
    code: str
    template_type: DocumentTemplateType
    body_html: str
    is_default: bool = False

class DocumentTemplateCreate(DocumentTemplateBase):
    pass

class DocumentTemplateRead(DocumentTemplateBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
