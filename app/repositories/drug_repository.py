# app/repositories/drug_repository.py
from __future__ import annotations

"""
Repository for Drug and DrugCategory.
"""

from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import Drug, DrugCategory


class DrugCategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, cat_id: int) -> Optional[DrugCategory]:
        return (
            self.db.query(DrugCategory)
            .filter(DrugCategory.id == cat_id, DrugCategory.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, cat_id: int) -> DrugCategory:
        c = self.get_by_id(cat_id)
        if not c:
            raise NotFoundError(message="Drug category not found.", detail={"category_id": cat_id})
        return c

    def get_by_name(self, name: str) -> Optional[DrugCategory]:
        return (
            self.db.query(DrugCategory)
            .filter(
                func.lower(DrugCategory.name) == name.strip().lower(),
                DrugCategory.is_deleted.is_(False),
            )
            .first()
        )

    def list_categories(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> tuple[list[DrugCategory], int]:
        query = self.db.query(DrugCategory).filter(DrugCategory.is_deleted.is_(False))
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(DrugCategory.name).like(term),
                    func.lower(func.coalesce(DrugCategory.code, "")).like(term),
                )
            )
        total = query.with_entities(func.count(DrugCategory.id)).scalar() or 0
        items = query.order_by(DrugCategory.name.asc()).offset(skip).limit(limit).all()
        return items, int(total)

    def create(self, **kwargs) -> DrugCategory:
        if self.get_by_name(kwargs["name"]):
            raise AlreadyExistsError(
                message="A drug category with this name already exists.",
                detail={"name": kwargs["name"]},
            )
        c = DrugCategory(**kwargs)
        self.db.add(c)
        self.db.flush()
        self.db.refresh(c)
        return c

    def update(self, c: DrugCategory, **kwargs) -> DrugCategory:
        for field, value in kwargs.items():
            if value is not None:
                setattr(c, field, value)
        self.db.add(c)
        self.db.flush()
        self.db.refresh(c)
        return c

    def soft_delete(self, c: DrugCategory) -> DrugCategory:
        c.is_deleted = True
        self.db.add(c)
        self.db.flush()
        return c


class DrugRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, drug_id: int) -> Optional[Drug]:
        return (
            self.db.query(Drug)
            .filter(Drug.id == drug_id, Drug.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, drug_id: int) -> Drug:
        d = self.get_by_id(drug_id)
        if not d:
            raise NotFoundError(message="Drug not found.", detail={"drug_id": drug_id})
        return d

    def get_by_sku(self, sku: str) -> Optional[Drug]:
        if not sku:
            return None
        return (
            self.db.query(Drug)
            .filter(
                func.upper(Drug.sku) == sku.strip().upper(),
                Drug.is_deleted.is_(False),
            )
            .first()
        )

    def list_drugs(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
        category_id: Optional[int] = None,
        is_controlled: Optional[bool] = None,
    ) -> tuple[list[Drug], int]:
        query = self.db.query(Drug).filter(Drug.is_deleted.is_(False))
        if category_id is not None:
            query = query.filter(Drug.drug_category_id == category_id)
        if is_controlled is not None:
            query = query.filter(Drug.is_controlled.is_(is_controlled))
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(Drug.name).like(term),
                    func.lower(func.coalesce(Drug.generic_name, "")).like(term),
                    func.lower(func.coalesce(Drug.brand_name, "")).like(term),
                    func.lower(func.coalesce(Drug.sku, "")).like(term),
                )
            )
        total = query.with_entities(func.count(Drug.id)).scalar() or 0
        items = query.order_by(Drug.name.asc()).offset(skip).limit(limit).all()
        return items, int(total)

    def create(self, **kwargs) -> Drug:
        sku = kwargs.get("sku")
        if sku and self.get_by_sku(sku):
            raise AlreadyExistsError(
                message="A drug with this SKU already exists.",
                detail={"sku": sku},
            )
        d = Drug(**kwargs)
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d

    def update(self, d: Drug, **kwargs) -> Drug:
        for field, value in kwargs.items():
            if value is not None:
                setattr(d, field, value)
        self.db.add(d)
        self.db.flush()
        self.db.refresh(d)
        return d

    def soft_delete(self, d: Drug) -> Drug:
        d.is_deleted = True
        self.db.add(d)
        self.db.flush()
        return d
