# app/repositories/membership_card_repository.py
from __future__ import annotations

from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from app.models.all_models import MembershipCard, MembershipCardTransaction
from app.core.enums import MembershipCardStatus


class MembershipCardRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, card_id: int) -> Optional[MembershipCard]:
        return (
            self.db.query(MembershipCard)
            .options(joinedload(MembershipCard.patient))
            .filter(MembershipCard.id == card_id)
            .first()
        )

    def get_by_card_number(self, card_number: str) -> Optional[MembershipCard]:
        return (
            self.db.query(MembershipCard)
            .options(joinedload(MembershipCard.patient))
            .filter(MembershipCard.card_number == card_number)
            .first()
        )

    def get_by_patient_id(self, patient_id: int) -> List[MembershipCard]:
        return (
            self.db.query(MembershipCard)
            .options(joinedload(MembershipCard.patient))
            .filter(MembershipCard.patient_id == patient_id)
            .all()
        )

    def list_cards(self, skip: int = 0, limit: int = 100) -> List[MembershipCard]:
        return (
            self.db.query(MembershipCard)
            .options(joinedload(MembershipCard.patient))
            .order_by(MembershipCard.date_issued.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create_card(self, card: MembershipCard) -> MembershipCard:
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        return card

    def update_card(self, card: MembershipCard) -> MembershipCard:
        self.db.add(card)
        self.db.flush()
        self.db.refresh(card)
        return card

    def create_transaction(self, transaction: MembershipCardTransaction) -> MembershipCardTransaction:
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)
        return transaction

    def get_transactions_by_card_id(self, card_id: int) -> List[MembershipCardTransaction]:
        return (
            self.db.query(MembershipCardTransaction)
            .filter(MembershipCardTransaction.membership_card_id == card_id)
            .order_by(MembershipCardTransaction.transaction_date.desc())
            .all()
        )
