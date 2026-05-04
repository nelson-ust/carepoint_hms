# app/services/pharmacy_service.py
from __future__ import annotations

"""
Aggregate pharmacy operations: worklist + drug stock summary.

Day-to-day prescription and dispense use the dedicated services. This service
exposes higher-level read endpoints needed by the pharmacy workstation UI.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.inventory_repository import InventoryStockItemRepository
from app.repositories.prescription_repository import PrescriptionRepository


class PharmacyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.prescription_repository = PrescriptionRepository(db)
        self.stock_repository = InventoryStockItemRepository(db)

    def worklist(self, *, skip: int = 0, limit: int = 50):
        """Open prescriptions for the pharmacy."""
        return self.prescription_repository.list_pharmacy_worklist(skip=skip, limit=limit)

    def stock_alerts(self, *, store_id: Optional[int] = None, expiring_within_days: int = 30):
        """Low stock + expiry-soon alerts."""
        low_stock, _ = self.stock_repository.list_items(
            store_id=store_id, only_low_stock=True, limit=200,
        )
        expiring_soon, _ = self.stock_repository.list_items(
            store_id=store_id,
            only_expiring_within_days=expiring_within_days,
            limit=200,
        )
        return {
            "low_stock": low_stock,
            "expiring_soon": expiring_soon,
        }
