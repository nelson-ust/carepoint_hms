# app/repositories/meal_repository.py
from __future__ import annotations

"""
Repository for Dietary & Meal Management.
Handles persistence for MealType catalog and MealOrder transactions.
"""

from typing import List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.all_models import MealOrder, MealType, Patient


class MealRepository:
    """Persistence layer for Meal Management."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- MealType (Catalog) ---

    def get_meal_type_by_id(self, meal_type_id: int) -> Optional[MealType]:
        stmt = select(MealType).filter(MealType.id == meal_type_id, MealType.is_deleted.is_(False))
        return self.db.execute(stmt).scalar_one_or_none()

    def get_meal_type_by_code(self, code: str) -> Optional[MealType]:
        stmt = select(MealType).filter(func.upper(MealType.code) == code.strip().upper(), MealType.is_deleted.is_(False))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_meal_types(self) -> List[MealType]:
        stmt = select(MealType).filter(MealType.is_deleted.is_(False)).order_by(MealType.name.asc())
        return list(self.db.execute(stmt).scalars().all())

    def create_meal_type(self, **kwargs) -> MealType:
        meal_type = MealType(**kwargs)
        self.db.add(meal_type)
        self.db.flush()
        return meal_type

    # --- MealOrder (Transactions) ---

    def get_order_by_id(self, order_id: int) -> Optional[MealOrder]:
        stmt = select(MealOrder).filter(MealOrder.id == order_id, MealOrder.is_deleted.is_(False))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_orders(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        visit_id: Optional[int] = None,
        patient_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[MealOrder], int]:
        stmt = select(MealOrder).filter(MealOrder.is_deleted.is_(False))
        
        if visit_id:
            stmt = stmt.filter(MealOrder.visit_id == visit_id)
        if patient_id:
            stmt = stmt.filter(MealOrder.patient_id == patient_id)
        if status:
            stmt = stmt.filter(MealOrder.status == status)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # Paginate and fetch
        stmt = stmt.order_by(MealOrder.ordered_at.desc()).offset(skip).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        
        return items, int(total)

    def create_order(self, **kwargs) -> MealOrder:
        order = MealOrder(**kwargs)
        self.db.add(order)
        self.db.flush()
        return order

    def save(self, obj) -> None:
        self.db.add(obj)
        self.db.flush()
