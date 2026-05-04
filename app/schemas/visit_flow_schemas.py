from __future__ import annotations

"""
app.schemas.visit_flow_schemas

Pydantic schemas for reusable visit flow templates and runtime visit flow steps.

Purpose
-------
This module defines request and response schemas for:

- creating reusable visit flow templates
- creating ordered template steps
- creating runtime visit flow steps for a specific visit
- bulk/single-endpoint creation of:
    1. VisitFlowTemplate
    2. VisitFlowTemplateStep
    3. VisitFlowStep

Design goals
------------
- support clean CRUD for template and runtime flow records
- support one-shot payloads that can create template + template steps + runtime steps
- support runtime rerouting, skipping, and current-step logic
- align with VisitFlowTemplate, VisitFlowTemplateStep, and VisitFlowStep models
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ============================================================
# SHARED LITE SCHEMAS
# ============================================================

class ServiceDeliveryPointVisitFlowLiteSchema(BaseModel):
    """
    Lightweight service delivery point representation for visit flow responses.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    service_point_type: str
    department_id: Optional[int] = None
    location_description: Optional[str] = None
    queue_prefix: Optional[str] = None
    supports_appointments: bool
    supports_walk_in: bool


# ============================================================
# VISIT FLOW TEMPLATE SCHEMAS
# ============================================================

class VisitFlowTemplateBaseSchema(BaseModel):
    """
    Base schema for reusable visit flow templates.
    """

    name: str = Field(..., min_length=1, max_length=150)
    code: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty.")
        return normalized

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("code cannot be empty.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitFlowTemplateCreateSchema(VisitFlowTemplateBaseSchema):
    """
    Schema for creating a reusable visit flow template.
    """
    pass


class VisitFlowTemplateUpdateSchema(BaseModel):
    """
    Schema for partially updating a reusable visit flow template.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=150)
    code: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty.")
        return normalized

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("code cannot be empty.")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitFlowTemplateStepBaseSchema(BaseModel):
    """
    Base schema for a step inside a reusable visit flow template.
    """

    service_delivery_point_id: int = Field(..., gt=0)
    step_order: int = Field(..., ge=1)
    is_required: bool = True
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitFlowTemplateStepCreateSchema(VisitFlowTemplateStepBaseSchema):
    """
    Schema for creating a template step when template_id is already known.
    """

    template_id: int = Field(..., gt=0)


class VisitFlowTemplateStepInlineCreateSchema(VisitFlowTemplateStepBaseSchema):
    """
    Inline schema for creating template steps together with a new template
    in one request payload.
    """
    pass


class VisitFlowTemplateStepUpdateSchema(BaseModel):
    """
    Schema for partially updating a visit flow template step.
    """

    service_delivery_point_id: Optional[int] = Field(None, gt=0)
    step_order: Optional[int] = Field(None, ge=1)
    is_required: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitFlowTemplateStepReadSchema(BaseModel):
    """
    Read schema for reusable visit flow template steps.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    service_delivery_point_id: int
    step_order: int
    is_required: bool
    notes: Optional[str] = None
    service_delivery_point: Optional[ServiceDeliveryPointVisitFlowLiteSchema] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class VisitFlowTemplateReadSchema(BaseModel):
    """
    Read schema for reusable visit flow templates.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    description: Optional[str] = None
    steps: list[VisitFlowTemplateStepReadSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# RUNTIME VISIT FLOW STEP SCHEMAS
# ============================================================

class VisitFlowStepBaseSchema(BaseModel):
    """
    Base schema for runtime visit flow steps.

    Supports:
    - current-step tracking
    - required/optional steps
    - skipped steps
    - rerouting metadata
    """

    service_delivery_point_id: int = Field(..., gt=0)
    step_order: int = Field(..., ge=1)
    status: Optional[str] = Field(None, max_length=50)
    is_current: bool = False
    is_required: bool = True
    is_skipped: bool = False
    routed_by_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitFlowStepCreateSchema(VisitFlowStepBaseSchema):
    """
    Schema for creating runtime visit flow steps when visit_id is already known.
    """

    visit_id: int = Field(..., gt=0)


class VisitFlowStepInlineCreateSchema(VisitFlowStepBaseSchema):
    """
    Inline schema for creating runtime visit flow steps within a combined payload.
    """
    pass


class VisitFlowStepUpdateSchema(BaseModel):
    """
    Schema for partially updating a runtime visit flow step.
    """

    service_delivery_point_id: Optional[int] = Field(None, gt=0)
    step_order: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, max_length=50)
    is_current: Optional[bool] = None
    is_required: Optional[bool] = None
    is_skipped: Optional[bool] = None
    routed_by_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class VisitFlowStepReadSchema(BaseModel):
    """
    Read schema for runtime visit flow steps.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    visit_id: int
    service_delivery_point_id: int
    step_order: int
    status: str
    is_current: bool
    is_required: bool
    is_skipped: bool
    routed_by_id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    service_delivery_point: Optional[ServiceDeliveryPointVisitFlowLiteSchema] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================
# SINGLE-ENDPOINT COMBINED CREATE SCHEMAS
# ============================================================

class VisitFlowCombinedCreateSchema(BaseModel):
    """
    Combined payload schema that makes provision for creating:

    - VisitFlowTemplate
    - VisitFlowTemplateStep
    - VisitFlowStep

    in one endpoint.

    Supported scenarios
    -------------------
    1. Create template only
    2. Create template + template steps
    3. Create runtime visit flow steps only
    4. Create template + template steps + runtime visit flow steps
    """

    template: Optional[VisitFlowTemplateCreateSchema] = None
    template_steps: list[VisitFlowTemplateStepInlineCreateSchema] = Field(default_factory=list)
    visit_id: Optional[int] = Field(
        None,
        description="Required if runtime visit_steps are being created.",
    )
    visit_steps: list[VisitFlowStepInlineCreateSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_combined_payload(self):
        """
        Enforce basic combined-payload consistency.
        """
        if self.template is None and self.template_steps:
            raise ValueError(
                "template_steps cannot be supplied unless template is provided."
            )

        if self.visit_steps and self.visit_id is None:
            raise ValueError(
                "visit_id is required when visit_steps are supplied."
            )

        if self.template is None and not self.visit_steps:
            raise ValueError(
                "At least one of template or visit_steps must be supplied."
            )

        template_step_orders = [step.step_order for step in self.template_steps]
        if len(template_step_orders) != len(set(template_step_orders)):
            raise ValueError("template_steps step_order values must be unique.")

        visit_step_orders = [step.step_order for step in self.visit_steps]
        if len(visit_step_orders) != len(set(visit_step_orders)):
            raise ValueError("visit_steps step_order values must be unique.")

        current_flags = [step for step in self.visit_steps if step.is_current]
        if len(current_flags) > 1:
            raise ValueError("Only one visit step can be marked as current.")

        return self


class VisitFlowCombinedCreateResultSchema(BaseModel):
    """
    Combined result schema for the single-endpoint create operation.
    """

    success: bool = True
    message: str
    template: Optional[VisitFlowTemplateReadSchema] = None
    created_template_steps: list[VisitFlowTemplateStepReadSchema] = Field(default_factory=list)
    created_visit_steps: list[VisitFlowStepReadSchema] = Field(default_factory=list)


# ============================================================
# LIST / ACTION RESPONSE SCHEMAS
# ============================================================

class VisitFlowTemplateListItemSchema(BaseModel):
    """
    List item schema for visit flow templates.
    """

    id: int
    name: str
    code: str
    description: Optional[str] = None


class VisitFlowTemplateListResponseSchema(BaseModel):
    """
    Paginated response schema for visit flow templates.
    """

    success: bool = True
    message: str = "Visit flow templates fetched successfully."
    items: list[VisitFlowTemplateListItemSchema]
    count: int
    meta: dict


class VisitFlowStepListResponseSchema(BaseModel):
    """
    Paginated response schema for runtime visit flow steps.
    """

    success: bool = True
    message: str = "Visit flow steps fetched successfully."
    items: list[VisitFlowStepReadSchema]
    count: int
    meta: dict


class VisitFlowActionResponseSchema(BaseModel):
    """
    Generic action response for visit-flow-related mutations.
    """

    success: bool = True
    message: str


'''
{
  "template": {
    "name": "Standard Outpatient Flow",
    "code": "OPD_STANDARD",
    "description": "Registration to clinician to lab to pharmacy"
  },
  "template_steps": [
    {
      "service_delivery_point_id": 1,
      "step_order": 1,
      "is_required": true,
      "notes": "Initial clinician review"
    },
    {
      "service_delivery_point_id": 2,
      "step_order": 2,
      "is_required": false,
      "notes": "Lab as needed"
    }
  ],
  "visit_id": 25,
  "visit_steps": [
    {
      "service_delivery_point_id": 1,
      "step_order": 1,
      "status": "PENDING",
      "is_current": true,
      "is_required": true,
      "is_skipped": false,
      "notes": "Current step for this visit"
    }
  ]
}

'''    