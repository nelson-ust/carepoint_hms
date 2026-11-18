import json
from datetime import datetime
from typing import Any, List, Optional

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


class ClinicalTemplateSectionRead(BaseModel):
    """
    Lenient section shape for READ responses.

    Unlike :class:`ClinicalTemplateSection` (used for create/update input,
    which requires a non-empty title), this tolerates legacy or bulk-seeded
    rows whose sections may have blank/missing titles or an unexpected shape.
    Read endpoints must never 500 because historical data doesn't satisfy
    the write-time rules.
    """

    title: str = "Untitled section"
    content: str = ""


class ClinicalTemplateRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    specialty: Optional[str] = None
    template_type: str = "SOAP"
    sections: List[ClinicalTemplateSectionRead] = Field(default_factory=list)
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
    def _coerce_sections(cls, v: Any):
        """Normalize any stored ``sections`` value into a clean list.

        Handles ``None``, a JSON-encoded string (double-encoded columns),
        non-list values, and individual entries that are plain strings or
        dicts with missing/blank keys — so one malformed row can never break
        the whole list response.
        """
        if v is None:
            return []
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except (ValueError, TypeError):
                return []
        if not isinstance(v, (list, tuple)):
            return []
        cleaned = []
        for item in v:
            if isinstance(item, dict):
                title = str(item.get("title") or "").strip() or "Untitled section"
                content = item.get("content")
                content = "" if content is None else str(content)
            elif isinstance(item, str):
                title, content = "Untitled section", item
            else:
                continue
            cleaned.append({"title": title, "content": content})
        return cleaned

    @computed_field  # serialized so the UI can show "N sections" cheaply
    @property
    def sections_count(self) -> int:
        return len(self.sections)


class ClinicalTemplateStats(BaseModel):
    total: int = 0
    commonly_used: int = 0
    specialties: List[str] = Field(default_factory=list)
