# app/repositories/account_repository.py
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import Account


class AccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, aid: int) -> Optional[Account]:
        return (
            self.db.query(Account)
            .filter(Account.id == aid, Account.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, aid: int) -> Account:
        a = self.get_by_id(aid)
        if not a:
            raise NotFoundError(message="Account not found.", detail={"id": aid})
        return a

    def get_by_code(self, code: str) -> Optional[Account]:
        return (
            self.db.query(Account)
            .filter(Account.code == code.strip().upper(), Account.is_deleted.is_(False))
            .first()
        )

    def list_accounts(self, *, skip=0, limit=100, search=None, account_type=None):
        query = self.db.query(Account).filter(Account.is_deleted.is_(False))
        if account_type:
            query = query.filter(Account.account_type == account_type)
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                func.lower(Account.name).like(term) | func.lower(Account.code).like(term)
            )
        total = query.with_entities(func.count(Account.id)).scalar() or 0
        items = query.order_by(Account.code.asc()).offset(skip).limit(limit).all()
        return items, int(total)

    def create(self, **kwargs) -> Account:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="An account with this code already exists.",
                detail={"code": kwargs["code"]},
            )
        a = Account(**kwargs)
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a

    def update(self, a: Account, **kwargs) -> Account:
        for field, value in kwargs.items():
            if value is not None:
                setattr(a, field, value)
        self.db.add(a)
        self.db.flush()
        self.db.refresh(a)
        return a

    def soft_delete(self, a: Account) -> Account:
        a.is_deleted = True
        self.db.add(a)
        self.db.flush()
        return a
