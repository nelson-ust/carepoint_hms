from datetime import datetime
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field, field_validator

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


# ---------------------------------------------------------------------------
# Clinical documentation templates (SOAP / history / examination / procedure)
# ---------------------------------------------------------------------------

CLINICAL_TEMPLATE_TYPES = {"SOAP", "HISTORY", "EXAMINATION", "PROCEDURE", "GENERAL"}


class ClinicalTemplateSection(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)
    content: str = Field("", description="Pre-filled text or placeholder guidance for this section")


class ClinicalTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    specialty: Optional[str] = Field(None, max_length=100)
    template_type: str = Field("SOAP")
    sections: List[ClinicalTemplateSection] = Field(default_factory=list)
    is_favorite: bool = False

    @field_validator("template_type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        v = (v or "SOAP").upper()
        if v not in CLINICAL_TEMPLATE_TYPES:
            raise ValueError(
                f"template_type must be one of {sorted(CLINICAL_TEMPLATE_TYPES)}"
            )
        return v


class ClinicalTemplateCreate(ClinicalTemplateBase):
    pass


class ClinicalTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    specialty: Optional[str] = Field(None, max_length=100)
    template_type: Optional[str] = None
    sections: Optional[List[ClinicalTemplateSection]] = None
    is_favorite: Optional[bool] = None

    @field_validator("template_type")
    @classmethod
    def _valid_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.upper()
        if v not in CLINICAL_TEMPLATE_TYPES:
            raise ValueError(
                f"template_type must be one of {sorted(CLINICAL_TEMPLATE_TYPES)}"
            )
        return v


class ClinicalTemplateRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    specialty: Optional[str] = None
    template_type: str = "SOAP"
    sections: List[ClinicalTemplateSection] = Field(default_factory=list)
    usage_count: int = 0
    is_favorite: bool = False
    date_created: Optional[datetime] = None
    # The UI reads ``updated_at``; the ORM base column is ``date_updated``.
    updated_at: Optional[datetime] = Field(
        None, validation_alias=AliasChoices("updated_at", "date_updated")
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("sections", mode="before")
    @classmethod
    def _none_sections(cls, v):
        return v or []

    @computed_field  # serialized so the UI can show "N sections" cheaply
    @property
    def sections_count(self) -> int:
        return len(self.sections)


class ClinicalTemplateStats(BaseModel):
    total: int = 0
    commonly_used: int = 0
    specialties: List[str] = Field(default_factory=list)
