from __future__ import annotations

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class DepartmentBaseSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = None
    is_active: bool = True

class DepartmentCreateSchema(DepartmentBaseSchema):
    pass

class DepartmentUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    code: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = None
    is_active: Optional[bool] = None

class DepartmentReadSchema(DepartmentBaseSchema):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class DepartmentListResponseSchema(BaseModel):
    success: bool = True
    items: list[DepartmentReadSchema]
    count: int
