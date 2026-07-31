# app/services/inventory_service.py
from __future__ import annotations

from typing import Any, Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.enums import InventoryItemType
from app.core.exceptions import BadRequestError
from app.models.all_models import InventoryStockItem, InventoryStore, StockMovement
from app.repositories.drug_repository import DrugRepository
from app.repositories.inventory_repository import (
    InventoryStockItemRepository,
    InventoryStoreRepository,
    StockMovementRepository,
)
from app.schemas.inventory_schema import (
    InventoryStockItemCreateSchema,
    InventoryStockItemUpdateSchema,
    InventoryStoreCreateSchema,
    InventoryStoreUpdateSchema,
    StockMovementCreateSchema,
    StockMovementReadSchema,
)


class InventoryStoreService:
    """Service for managing physical or logical inventory stores."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InventoryStoreRepository(db)

    def list(self, *, skip=0, limit=50, search=None):
        """List stores with optional search and pagination."""
        return self.repository.list_stores(skip=skip, limit=limit, search=search)

    def get(self, store_id: int) -> InventoryStore:
        """Fetch store details by ID."""
        return self.repository.get_required_by_id(store_id)

    def create(self, payload: InventoryStoreCreateSchema) -> InventoryStore:
        """Create a new store record."""
        s = self.repository.create(
            name=payload.name,
            code=payload.code,
            location_description=payload.location_description,
            description=payload.description,
        )
        self.db.commit()
        return self.repository.get_required_by_id(s.id)

    def update(self, store_id: int, payload: InventoryStoreUpdateSchema) -> InventoryStore:
        """Update store metadata."""
        s = self.repository.get_required_by_id(store_id)
        updated = self.repository.update(s, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, store_id: int) -> InventoryStore:
        """Logical delete of a store."""
        s = self.repository.get_required_by_id(store_id)
        deleted = self.repository.soft_delete(s)
        self.db.commit()
        return deleted


class InventoryStockItemService:
    """Service for managing individual stock records and their quantities."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = InventoryStockItemRepository(db)
        self.store_repository = InventoryStoreRepository(db)
        self.drug_repository = DrugRepository(db)

    def list(
        self,
        *,
        skip=0,
        limit=50,
        store_id: Optional[int] = None,
        drug_id: Optional[int] = None,
        item_type: Optional[str] = None,
        only_low_stock: bool = False,
        only_expiring_within_days: Optional[int] = None,
        search: Optional[str] = None,
    ):
        """Query stock items with advanced business filters (low stock, expiring soon)."""
        item_type_enum = InventoryItemType(item_type) if item_type else None
        return self.repository.list_items(
            skip=skip, limit=limit, search=search,
            store_id=store_id, drug_id=drug_id, item_type=item_type_enum,
            only_low_stock=only_low_stock,
            only_expiring_within_days=only_expiring_within_days,
        )

    def get(self, item_id: int) -> InventoryStockItem:
        """Fetch stock item details."""
        return self.repository.get_required_by_id(item_id)

    def create(self, payload: InventoryStockItemCreateSchema) -> InventoryStockItem:
        """Register a new stock item in a specific store.

        When a drug is linked, the descriptive fields (name / SKU / unit /
        default reorder level) are inherited from the formulary drug so the
        catalogue stays the single source of truth.
        """
        # Ensure the store exists before adding stock to it.
        self.store_repository.get_required_by_id(payload.store_id)
        data = self._apply_drug_link(payload.model_dump(exclude_unset=True))
        if not str(data.get("item_name") or "").strip():
            raise BadRequestError(message="Item name is required (or link a drug to inherit it).")
        i = self.repository.create(**data)
        self.db.commit()
        return self.repository.get_required_by_id(i.id)

    def _apply_drug_link(self, data: dict[str, Any]) -> dict[str, Any]:
        """Fill missing descriptive fields from the linked drug (single source)."""
        drug_id = data.get("drug_id")
        if not drug_id:
            return data
        drug = self.drug_repository.get_by_id(drug_id)
        if drug is None:
            raise BadRequestError(message=f"Linked drug (id {drug_id}) was not found.")
        data.setdefault("item_type", "DRUG")
        if not str(data.get("item_name") or "").strip():
            data["item_name"] = drug.name
        if not str(data.get("sku") or "").strip() and drug.sku:
            data["sku"] = drug.sku
        if not str(data.get("unit_of_measure") or "").strip() and drug.dosage_form:
            data["unit_of_measure"] = drug.dosage_form
        if data.get("reorder_level") in (None, "") and drug.reorder_level is not None:
            data["reorder_level"] = drug.reorder_level
        return data

    def update(self, item_id: int, payload: InventoryStockItemUpdateSchema) -> InventoryStockItem:
        """Update stock item metadata (non-quantity fields)."""
        i = self.repository.get_required_by_id(item_id)
        updated = self.repository.update(i, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, item_id: int) -> InventoryStockItem:
        """Logical delete of a stock item."""
        i = self.repository.get_required_by_id(item_id)
        deleted = self.repository.soft_delete(i)
        self.db.commit()
        return deleted

    # ------------------------------------------------------------------
    # Bulk import
    # ------------------------------------------------------------------

    def build_import_template(self) -> bytes:
        """Generate the .xlsx template, seeded with this tenant's stores and drugs."""
        from app.utils.inventory_import import build_stock_item_template

        stores, _ = self.store_repository.list_stores(skip=0, limit=100_000)
        store_rows = [(s.code, s.name) for s in stores]
        drugs, _ = self.drug_repository.list_drugs(skip=0, limit=100_000)
        drug_rows = [(d.name, d.sku or "") for d in drugs]
        return build_stock_item_template(store_rows, drug_rows)

    def bulk_create(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Create stock items from parsed template rows.

        Each row is validated and inserted inside its own savepoint so one bad
        row never aborts the rest. Returns a per-row result summary.
        """
        errors: list[dict[str, Any]] = []
        created = 0

        # Resolve store codes once (case-insensitive).
        stores, _ = self.store_repository.list_stores(skip=0, limit=100_000)
        code_to_id = {s.code.strip().upper(): s.id for s in stores}

        # Resolve drugs once, by SKU and by name, so medicine rows link to the
        # formulary instead of creating parallel catalogue entries.
        drugs, _ = self.drug_repository.list_drugs(skip=0, limit=100_000)
        drug_by_sku = {d.sku.strip().upper(): d for d in drugs if d.sku}
        drug_by_name = {d.name.strip().upper(): d for d in drugs}

        for entry in rows:
            row_no = entry.get("row")
            data = entry.get("data", {}) or {}
            try:
                store_code = str(data.get("store_code") or "").strip().upper()
                if not store_code:
                    raise ValueError("Store Code is required.")
                store_id = code_to_id.get(store_code)
                if store_id is None:
                    raise ValueError(f"Unknown store code '{store_code}'.")

                item_type = str(data.get("item_type") or "DRUG").strip().upper()

                # Resolve the linked drug: explicit "Drug (SKU or Name)" wins;
                # otherwise auto-link DRUG rows whose own SKU/name matches one.
                drug = None
                ref = data.get("drug_ref")
                if ref is not None and str(ref).strip():
                    key = str(ref).strip().upper()
                    drug = drug_by_sku.get(key) or drug_by_name.get(key)
                    if drug is None:
                        raise ValueError(
                            f"Unknown drug '{ref}' — no formulary match by SKU or name."
                        )
                elif item_type == "DRUG":
                    sku_key = str(data.get("sku") or "").strip().upper()
                    name_key = str(data.get("item_name") or "").strip().upper()
                    drug = (
                        (drug_by_sku.get(sku_key) if sku_key else None)
                        or (drug_by_name.get(name_key) if name_key else None)
                    )

                item_name = data.get("item_name")
                sku = data.get("sku")
                uom = data.get("unit_of_measure")
                reorder = data.get("reorder_level")
                drug_id = None
                if drug is not None:
                    drug_id = drug.id
                    if not str(item_name or "").strip():
                        item_name = drug.name
                    if not str(sku or "").strip() and drug.sku:
                        sku = drug.sku
                    if not str(uom or "").strip() and drug.dosage_form:
                        uom = drug.dosage_form
                    if reorder in (None, "") and drug.reorder_level is not None:
                        reorder = drug.reorder_level

                if not str(item_name or "").strip():
                    raise ValueError("Item Name is required (or link a drug to inherit it).")

                payload = InventoryStockItemCreateSchema(
                    store_id=store_id,
                    drug_id=drug_id,
                    item_type=item_type,
                    item_name=item_name,
                    sku=sku,
                    unit_of_measure=uom,
                    quantity_on_hand=data.get("quantity_on_hand", 0) or 0,
                    reorder_level=reorder,
                    unit_cost=data.get("unit_cost"),
                    batch_no=data.get("batch_no"),
                    expiry_date=data.get("expiry_date"),
                )

                # Isolate each insert so a DB error on one row doesn't poison
                # the whole batch.
                with self.db.begin_nested():
                    self.repository.create(**payload.model_dump(exclude_unset=True))
                created += 1
            except ValidationError as exc:
                errors.append({"row": row_no, "message": _format_validation_error(exc)})
            except ValueError as exc:
                errors.append({"row": row_no, "message": str(exc)})
            except Exception as exc:  # pragma: no cover - unexpected DB errors
                errors.append({"row": row_no, "message": f"Could not save this row: {exc}"})

        if created:
            self.db.commit()

        total = len(rows)
        failed = len(errors)
        if created and not failed:
            message = f"All {created} item(s) imported successfully."
        elif created and failed:
            message = f"Imported {created} item(s); {failed} row(s) had problems."
        elif not created and failed:
            message = f"No items imported — all {failed} row(s) had problems."
        else:
            message = "The file had no data rows to import."

        return {
            "success": failed == 0 and created > 0,
            "message": message,
            "total_rows": total,
            "created": created,
            "failed": failed,
            "errors": errors,
        }


def _format_validation_error(exc: ValidationError) -> str:
    """Turn a pydantic ValidationError into a short, human-readable message."""
    parts: list[str] = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        field = str(loc[-1]) if loc else ""
        msg = err.get("msg", "is invalid")
        parts.append(f"{field}: {msg}" if field else msg)
    return "; ".join(parts) or "Row failed validation."


class StockMovementService:
    """
    Orchestrator for stock adjustments.
    
    This service is responsible for the atomic transaction of recording a
    movement (audit) and updating the stock item's balance (current state).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = StockMovementRepository(db)
        self.item_repository = InventoryStockItemRepository(db)

    def list(
        self,
        *,
        skip=0,
        limit=50,
        store_id: Optional[int] = None,
        stock_item_id: Optional[int] = None,
        movement_type: Optional[str] = None,
    ):
        """List historical movements with filtering."""
        from app.core.enums import StockMovementType
        m_type = StockMovementType(movement_type) if movement_type else None
        return self.repository.list_movements(
            skip=skip, limit=limit,
            store_id=store_id, stock_item_id=stock_item_id, movement_type=m_type
        )

    def get(self, movement_id: int) -> StockMovement:
        """Fetch movement record details."""
        return self.repository.get_required_by_id(movement_id)

    def create(self, payload: StockMovementCreateSchema) -> StockMovement:
        """
        Record a stock movement and atomically adjust the stock item quantity.
        
        Business Logic:
        1. Validates that the store_id matches the stock item's store.
        2. Determines if the movement is additive or subtractive based on type.
        3. Updates the InventoryStockItem.quantity_on_hand.
        4. Records the StockMovement audit row with a 'balance_after' snapshot.
        """
        from app.core.enums import StockMovementType
        item = self.item_repository.get_required_by_id(payload.stock_item_id)
        
        # Guard: Movements cannot move stock between different physical stores.
        if payload.store_id != item.store_id:
             from app.core.exceptions import BadRequestError
             raise BadRequestError(
                 message="Store mismatch. Item belongs to a different store.",
                 detail={"item_store_id": item.store_id, "payload_store_id": payload.store_id}
             )

        m_type = StockMovementType(payload.movement_type)
        
        # Categorize movement direction.
        # Additive: Stock entering the system (Purchases, Returns, Adjustments IN).
        # Subtractive: Stock leaving the system (Issues, Dispensing, Adjustments OUT, Waste).
        additive_types = {
            StockMovementType.OPENING_BALANCE,
            StockMovementType.PURCHASE,
            StockMovementType.TRANSFER_IN,
            StockMovementType.ADJUSTMENT_IN,
            StockMovementType.RETURN_IN
        }
        
        delta = payload.quantity
        if m_type not in additive_types:
            # Force negative delta for subtractive movements
            delta = -abs(delta)
        else:
            # Force positive delta for additive movements
            delta = abs(delta)

        # Update the live balance in the stock item record
        item = self.item_repository.adjust_quantity(item, delta)
        
        # Record the audit row with the final balance snapshot
        m = self.repository.create(
            **payload.model_dump(exclude_unset=True),
            balance_after=item.quantity_on_hand
        )
        
        self.db.commit()
        return self.repository.get_required_by_id(m.id)
