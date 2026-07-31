# app/services/drug_service.py
from __future__ import annotations

from typing import Any, Optional

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError
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

    # ------------------------------------------------------------------
    # Bulk import
    # ------------------------------------------------------------------

    def build_import_template(self) -> bytes:
        """Generate the .xlsx drug-category bulk-upload template."""
        from app.utils.drug_import import build_category_template

        return build_category_template()

    def bulk_create(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Create drug categories from parsed template rows.

        Each row is validated and inserted inside its own savepoint. Name is
        required and must be unique; Code is optional but unique when supplied.
        """
        errors: list[dict[str, Any]] = []
        created = 0
        seen_names: set[str] = set()
        seen_codes: set[str] = set()

        for entry in rows:
            row_no = entry.get("row")
            data = entry.get("data", {}) or {}
            try:
                name = str(data.get("name") or "").strip()
                if not name:
                    raise ValueError("Category Name is required.")
                if name.upper() in seen_names:
                    raise ValueError(f"Duplicate name '{name}' in this file.")

                payload = DrugCategoryCreateSchema(
                    name=name,
                    code=data.get("code"),
                    description=data.get("description"),
                )
                if payload.code and payload.code.upper() in seen_codes:
                    raise ValueError(f"Duplicate code '{payload.code}' in this file.")

                with self.db.begin_nested():
                    self.repository.create(
                        name=payload.name,
                        code=payload.code,
                        description=payload.description,
                    )
                seen_names.add(name.upper())
                if payload.code:
                    seen_codes.add(payload.code.upper())
                created += 1
            except AlreadyExistsError as exc:
                msg = getattr(exc, "message", None) or "A category with this name already exists."
                errors.append({"row": row_no, "message": msg})
            except ValidationError as exc:
                errors.append({"row": row_no, "message": _format_drug_validation_error(exc)})
            except ValueError as exc:
                errors.append({"row": row_no, "message": str(exc)})
            except Exception as exc:  # pragma: no cover
                errors.append({"row": row_no, "message": f"Could not save this row: {exc}"})

        if created:
            self.db.commit()

        total = len(rows)
        failed = len(errors)
        if created and not failed:
            message = f"All {created} categor(y/ies) imported successfully."
        elif created and failed:
            message = f"Imported {created} categor(y/ies); {failed} row(s) had problems."
        elif not created and failed:
            message = f"No categories imported \u2014 all {failed} row(s) had problems."
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

    # ------------------------------------------------------------------
    # Bulk import
    # ------------------------------------------------------------------

    def build_import_template(self) -> bytes:
        """Generate the .xlsx bulk-upload template, seeded with this tenant's categories."""
        from app.utils.drug_import import build_drug_template

        categories, _ = self.category_repository.list_categories(skip=0, limit=100_000)
        cat_rows = [(c.name, c.code) for c in categories]
        return build_drug_template(cat_rows)

    def bulk_create(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Create drugs from parsed template rows.

        Each row is validated and inserted inside its own savepoint so one bad
        row never aborts the rest. Category is matched by name or code
        (case-insensitive); SKUs must be unique. Returns a per-row summary.
        """
        errors: list[dict[str, Any]] = []
        created = 0

        # Resolve categories once (by name and by code, case-insensitive).
        categories, _ = self.category_repository.list_categories(skip=0, limit=100_000)
        name_to_id = {c.name.strip().upper(): c.id for c in categories}
        code_to_id = {c.code.strip().upper(): c.id for c in categories if c.code}

        seen_skus: set[str] = set()

        for entry in rows:
            row_no = entry.get("row")
            data = entry.get("data", {}) or {}
            try:
                name = str(data.get("name") or "").strip()
                if not name:
                    raise ValueError("Drug Name is required.")

                # Optional category by name/code.
                category_id = None
                cat_raw = data.get("category")
                if cat_raw is not None and str(cat_raw).strip():
                    key = str(cat_raw).strip().upper()
                    category_id = name_to_id.get(key) or code_to_id.get(key)
                    if category_id is None:
                        raise ValueError(f"Unknown category '{cat_raw}'.")

                # SKU uniqueness (within the file and against existing drugs).
                sku = data.get("sku")
                sku_norm = str(sku).strip() if sku is not None else None
                if sku_norm:
                    if sku_norm.upper() in seen_skus:
                        raise ValueError(f"Duplicate SKU '{sku_norm}' in this file.")
                    if self.repository.get_by_sku(sku_norm) is not None:
                        raise ValueError(f"A drug with SKU '{sku_norm}' already exists.")

                payload = DrugCreateSchema(
                    name=name,
                    generic_name=data.get("generic_name"),
                    brand_name=data.get("brand_name"),
                    strength=data.get("strength"),
                    dosage_form=data.get("dosage_form"),
                    pack_size=data.get("pack_size"),
                    sku=sku_norm,
                    drug_category_id=category_id,
                    unit_price=data.get("unit_price"),
                    reorder_level=data.get("reorder_level"),
                    is_controlled=_parse_bool(data.get("is_controlled")),
                )

                with self.db.begin_nested():
                    self.repository.create(**payload.model_dump(exclude_unset=True))
                if sku_norm:
                    seen_skus.add(sku_norm.upper())
                created += 1
            except ValidationError as exc:
                errors.append({"row": row_no, "message": _format_drug_validation_error(exc)})
            except ValueError as exc:
                errors.append({"row": row_no, "message": str(exc)})
            except Exception as exc:  # pragma: no cover - unexpected DB errors
                errors.append({"row": row_no, "message": f"Could not save this row: {exc}"})

        if created:
            self.db.commit()

        total = len(rows)
        failed = len(errors)
        if created and not failed:
            message = f"All {created} drug(s) imported successfully."
        elif created and failed:
            message = f"Imported {created} drug(s); {failed} row(s) had problems."
        elif not created and failed:
            message = f"No drugs imported \u2014 all {failed} row(s) had problems."
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


def _parse_bool(value: Any) -> bool:
    """Interpret spreadsheet truthiness: YES/Y/TRUE/1 -> True, else False."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().upper() in {"YES", "Y", "TRUE", "1", "CONTROLLED"}


def _format_drug_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        field = str(loc[-1]) if loc else ""
        msg = err.get("msg", "is invalid")
        parts.append(f"{field}: {msg}" if field else msg)
    return "; ".join(parts) or "Row failed validation."
