# app/services/account_service.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import AccountType
from app.models.all_models import Account
from app.repositories.account_repository import AccountRepository
from app.schemas.account_schemas import AccountCreateSchema, AccountUpdateSchema


class AccountService:
    """CRUD for the tenant chart of accounts."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AccountRepository(db)

    def list(self, *, skip: int = 0, limit: int = 100, search: Optional[str] = None,
             account_type: Optional[str] = None):
        at = None
        if account_type:
            try:
                at = AccountType(account_type.strip().upper())
            except ValueError:
                at = None
        return self.repository.list_accounts(
            skip=skip, limit=limit, search=search, account_type=at
        )

    def get(self, aid: int) -> Account:
        return self.repository.get_required_by_id(aid)

    def create(self, payload: AccountCreateSchema) -> Account:
        a = self.repository.create(**payload.model_dump())
        self.db.commit()
        return self.repository.get_required_by_id(a.id)

    def update(self, aid: int, payload: AccountUpdateSchema) -> Account:
        a = self.repository.get_required_by_id(aid)
        updated = self.repository.update(a, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        return self.repository.get_required_by_id(updated.id)

    def soft_delete(self, aid: int) -> Account:
        a = self.repository.get_required_by_id(aid)
        deleted = self.repository.soft_delete(a)
        self.db.commit()
        return deleted

    # ------------------------------------------------------------------
    # Bulk import
    # ------------------------------------------------------------------

    def build_import_template(self) -> bytes:
        from app.utils.account_import import build_account_template

        return build_account_template()

    def bulk_create(self, rows: list) -> dict:
        from app.core.exceptions import AlreadyExistsError
        from app.utils.account_import import ACCOUNT_TYPES

        errors: list = []
        created = 0
        seen_codes: set = set()
        for entry in rows:
            row_no = entry.get("row")
            data = entry.get("data", {}) or {}
            try:
                code = str(data.get("code") or "").strip()
                name = str(data.get("name") or "").strip()
                if not code:
                    raise ValueError("Account Code is required.")
                if not name:
                    raise ValueError("Account Name is required.")
                norm_code = code.upper().replace(" ", "-")
                if norm_code in seen_codes:
                    raise ValueError(f"Duplicate code '{code}' in this file.")
                at_raw = str(data.get("account_type") or "REVENUE").strip().upper()
                if at_raw not in ACCOUNT_TYPES:
                    raise ValueError(
                        f"Invalid account type '{at_raw}'. Use one of: {', '.join(ACCOUNT_TYPES)}."
                    )
                with self.db.begin_nested():
                    self.repository.create(
                        code=norm_code,
                        name=name,
                        account_type=AccountType(at_raw),
                        description=data.get("description"),
                    )
                seen_codes.add(norm_code)
                created += 1
            except AlreadyExistsError as exc:
                errors.append({"row": row_no, "message": getattr(exc, "message", None) or "An account with this code already exists."})
            except ValueError as exc:
                errors.append({"row": row_no, "message": str(exc)})
            except Exception as exc:  # pragma: no cover
                errors.append({"row": row_no, "message": f"Could not save this row: {exc}"})

        if created:
            self.db.commit()
        total = len(rows)
        failed = len(errors)
        if created and not failed:
            message = f"All {created} account(s) imported successfully."
        elif created and failed:
            message = f"Imported {created} account(s); {failed} row(s) had problems."
        elif failed:
            message = f"No accounts imported \u2014 all {failed} row(s) had problems."
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
