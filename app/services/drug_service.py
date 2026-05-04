# app/services/drug_service.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.all_models import Drug, DrugCategory
from app.repositories.drug_repository import DrugCategoryRepository, DrugRepository
from app.schemas.drug_schema import (
    DrugCategoryCreateSchema,
    DrugCategoryUpdateSchema,
    DrugCreateSchema,
    DrugUpdateSchema,
)


class DrugCategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DrugCategoryRepository(db)

    def list(self, *, skip=0, limit=50, search=None):
        return self.repository.list_categories(skip=skip, limit=limit, search=search)

    def get(self, cat_id: int) -> DrugCategory:
        return self.repository.get_required_by_id(cat_id)

    def create(self, payload: DrugCategoryCreateSchema) -> DrugCategory:
        c = self.repository.create(
            name=payload.name,
            code=payload.code,
            description=payload.description,
        )
        self.db.commit()
        return self.repository.get_required_by_id(c.id)

    def update(self, cat_id: int, payload: DrugCategoryUpdateSchema) -> DrugCategory:
        c = self.repository.get_required_by_id(cat_id)
        updated = self.repository.update(c, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, cat_id: int) -> DrugCategory:
        c = self.repository.get_required_by_id(cat_id)
        deleted = self.repository.soft_delete(c)
        self.db.commit()
        return deleted


class DrugService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DrugRepository(db)
        self.category_repository = DrugCategoryRepository(db)

    def list(
        self,
        *,
        skip=0,
        limit=50,
        search=None,
        category_id: Optional[int] = None,
        is_controlled: Optional[bool] = None,
    ):
        return self.repository.list_drugs(
            skip=skip, limit=limit, search=search,
            category_id=category_id, is_controlled=is_controlled,
        )

    def get(self, drug_id: int) -> Drug:
        return self.repository.get_required_by_id(drug_id)

    def create(self, payload: DrugCreateSchema) -> Drug:
        if payload.drug_category_id is not None:
            self.category_repository.get_required_by_id(payload.drug_category_id)
        drug = self.repository.create(**payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(drug.id)

    def update(self, drug_id: int, payload: DrugUpdateSchema) -> Drug:
        drug = self.repository.get_required_by_id(drug_id)
        if payload.drug_category_id is not None:
            self.category_repository.get_required_by_id(payload.drug_category_id)
        updated = self.repository.update(drug, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, drug_id: int) -> Drug:
        drug = self.repository.get_required_by_id(drug_id)
        deleted = self.repository.soft_delete(drug)
        self.db.commit()
        return deleted
