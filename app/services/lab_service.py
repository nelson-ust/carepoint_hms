# app/services/lab_service.py
from __future__ import annotations

"""
Service layer for the LabTestCatalog.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError
from app.models.all_models import LabTestCatalog
from app.repositories.lab_repository import LabCatalogRepository
from app.schemas.lab_schema import LabTestCatalogCreateSchema, LabTestCatalogUpdateSchema


class LabCatalogService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = LabCatalogRepository(db)

    def list_tests(self, *, skip: int = 0, limit: int = 50, search: Optional[str] = None):
        return self.repository.list_tests(skip=skip, limit=limit, search=search)

    def get(self, test_id: int) -> LabTestCatalog:
        return self.repository.get_required_by_id(test_id)

    def create(self, payload: LabTestCatalogCreateSchema) -> LabTestCatalog:
        test = self.repository.create(
            code=payload.code,
            name=payload.name,
            sample_type=payload.sample_type,
            unit_of_measure=payload.unit_of_measure,
            reference_range=payload.reference_range,
            default_price=payload.default_price,
            description=payload.description,
        )
        self.db.commit()
        return self.repository.get_required_by_id(test.id)

    def update(self, test_id: int, payload: LabTestCatalogUpdateSchema) -> LabTestCatalog:
        test = self.repository.get_required_by_id(test_id)
        updated = self.repository.update(test, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, test_id: int) -> LabTestCatalog:
        test = self.repository.get_required_by_id(test_id)
        deleted = self.repository.soft_delete(test)
        self.db.commit()
        return deleted
