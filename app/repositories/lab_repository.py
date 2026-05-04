# app/repositories/lab_repository.py
from __future__ import annotations

"""
Repository for the LabTestCatalog (master list of lab tests).
"""

from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import LabTestCatalog


class LabCatalogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, test_id: int) -> Optional[LabTestCatalog]:
        return (
            self.db.query(LabTestCatalog)
            .filter(LabTestCatalog.id == test_id, LabTestCatalog.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, test_id: int) -> LabTestCatalog:
        t = self.get_by_id(test_id)
        if not t:
            raise NotFoundError(message="Lab test not found.", detail={"lab_test_id": test_id})
        return t

    def get_by_code(self, code: str) -> Optional[LabTestCatalog]:
        return (
            self.db.query(LabTestCatalog)
            .filter(
                func.upper(LabTestCatalog.code) == code.strip().upper(),
                LabTestCatalog.is_deleted.is_(False),
            )
            .first()
        )

    def list_tests(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> tuple[list[LabTestCatalog], int]:
        query = self.db.query(LabTestCatalog).filter(LabTestCatalog.is_deleted.is_(False))
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(LabTestCatalog.name).like(term),
                    func.lower(LabTestCatalog.code).like(term),
                    func.lower(func.coalesce(LabTestCatalog.description, "")).like(term),
                )
            )
        total = query.with_entities(func.count(LabTestCatalog.id)).scalar() or 0
        items = (
            query.order_by(LabTestCatalog.name.asc()).offset(skip).limit(limit).all()
        )
        return items, int(total)

    def create(self, **kwargs) -> LabTestCatalog:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="A lab test with this code already exists.",
                detail={"code": kwargs["code"]},
            )
        t = LabTestCatalog(**kwargs)
        self.db.add(t)
        self.db.flush()
        self.db.refresh(t)
        return t

    def update(self, test: LabTestCatalog, **kwargs) -> LabTestCatalog:
        for field, value in kwargs.items():
            if value is not None:
                setattr(test, field, value)
        self.db.add(test)
        self.db.flush()
        self.db.refresh(test)
        return test

    def soft_delete(self, test: LabTestCatalog) -> LabTestCatalog:
        test.is_deleted = True
        self.db.add(test)
        self.db.flush()
        return test
