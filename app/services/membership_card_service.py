# app/services/membership_card_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.enums import MembershipCardStatus, MembershipCardTransactionType
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    AlreadyExistsError,
)
from app.models.all_models import MembershipCard, MembershipCardTransaction, User, PaystackTransaction
from app.repositories.membership_card_repository import MembershipCardRepository
from app.services.notification_service import NotificationService
from app.schemas.notification_schema import NotificationDispatchSchema
from app.schemas.membership_card_schemas import (
    MembershipCardCreate,
    MembershipCardUpdate,
    MembershipCardFund,
    MembershipCardDebit,
)


class MembershipCardService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = MembershipCardRepository(db)
        self.notification_service = NotificationService(db)

    def create_card(self, payload: MembershipCardCreate, issued_by_id: int) -> MembershipCard:
        # Check if card number already exists
        existing = self.repository.get_by_card_number(payload.card_number)
        if existing:
            raise AlreadyExistsError(f"Membership card with number {payload.card_number} already exists.")

        card = MembershipCard(
            patient_id=payload.patient_id,
            card_number=payload.card_number,
            balance=payload.initial_balance,
            status=payload.status,
            issuing_facility_id=payload.issuing_facility_id,
            issued_by_id=issued_by_id,
            expiry_date=payload.expiry_date,
        )
        
        card = self.repository.create_card(card)

        # If initial balance > 0, create a transaction
        if payload.initial_balance > 0:
            transaction = MembershipCardTransaction(
                membership_card_id=card.id,
                patient_id=card.patient_id,
                amount=payload.initial_balance,
                transaction_type=MembershipCardTransactionType.CREDIT,
                payment_source="INITIAL_DEPOSIT",
                balance_before=Decimal("0.00"),
                balance_after=payload.initial_balance,
                facility_id=card.issuing_facility_id,
                processed_by_id=issued_by_id,
                transaction_date=datetime.utcnow(),
                narration="Initial card deposit",
            )
            self.repository.create_transaction(transaction)

        return card

    def get_card(self, card_id: int, include_transactions: bool = False) -> MembershipCard:
        card = self.repository.get_by_id(card_id, include_transactions=include_transactions)
        if not card:
            raise NotFoundError(f"Membership card with id {card_id} not found.")
        return card

    def get_card_by_number(self, card_number: str) -> MembershipCard:
        card = self.repository.get_by_card_number(card_number)
        if not card:
            raise NotFoundError(f"Membership card with number {card_number} not found.")
        return card

    def list_patient_cards(self, patient_id: int) -> List[MembershipCard]:
        return self.repository.get_by_patient_id(patient_id)

    def list_cards(self, skip: int = 0, limit: int = 100) -> List[MembershipCard]:
        return self.repository.list_cards(skip=skip, limit=limit)

    def update_card(self, card_id: int, payload: MembershipCardUpdate) -> MembershipCard:
        card = self.get_card(card_id)
        
        if payload.status:
            card.status = payload.status
        if payload.expiry_date:
            card.expiry_date = payload.expiry_date
            
        return self.repository.update_card(card)

    def fund_card(
        self, card_id: int, payload: MembershipCardFund, processed_by_id: int, facility_id: int
    ) -> MembershipCardTransaction:
        card = self.get_card(card_id)
        
        if card.status != MembershipCardStatus.ACTIVE:
            raise ValidationError(f"Cannot fund a card that is in {card.status} status.")

        balance_before = card.balance
        card.balance += payload.amount
        balance_after = card.balance
        
        self.repository.update_card(card)

        transaction = MembershipCardTransaction(
            membership_card_id=card.id,
            patient_id=card.patient_id,
            amount=payload.amount,
            transaction_type=MembershipCardTransactionType.CREDIT,
            payment_source=payload.payment_source,
            payment_reference=payload.payment_reference,
            balance_before=balance_before,
            balance_after=balance_after,
            facility_id=facility_id,
            processed_by_id=processed_by_id,
            transaction_date=datetime.utcnow(),
            narration=payload.narration or f"Credit via {payload.payment_source}",
        )
        
        transaction = self.repository.create_transaction(transaction)
        
        # Trigger Notification
        try:
            self.notification_service.dispatch_from_template(
                payload=NotificationDispatchSchema(
                    template_code="MEMBERSHIP_CARD_CREDIT",
                    patient_id=card.patient_id,
                    context={
                        "amount": f"{payload.amount:,.2f}",
                        "balance": f"{card.balance:,.2f}",
                        "reference": payload.payment_reference or "N/A"
                    }
                )
            )
        except Exception as e:
            print(f"Error sending credit notification: {e}")

        return transaction

    def credit_via_paystack(
        self, tx: PaystackTransaction
    ) -> MembershipCardTransaction:
        """
        Credit a membership card using a verified Paystack transaction.
        """
        card = self.get_card(tx.membership_card_id)
        
        if card.status != MembershipCardStatus.ACTIVE:
            raise ValidationError(f"Cannot fund a card that is in {card.status} status.")

        balance_before = card.balance
        card.balance += tx.amount
        balance_after = card.balance
        
        self.repository.update_card(card)

        transaction = MembershipCardTransaction(
            membership_card_id=card.id,
            patient_id=card.patient_id,
            amount=tx.amount,
            transaction_type=MembershipCardTransactionType.CREDIT,
            payment_source="PAYSTACK",
            payment_reference=tx.reference,
            balance_before=balance_before,
            balance_after=balance_after,
            facility_id=1, # Default facility for online payments
            processed_by_id=tx.patient.user_id or 1, # Linked user or system admin
            transaction_date=datetime.utcnow(),
            narration=f"Online credit via Paystack. Ref: {tx.reference}",
        )
        
        transaction = self.repository.create_transaction(transaction)

        # Trigger Notification
        try:
            self.notification_service.dispatch_from_template(
                payload=NotificationDispatchSchema(
                    template_code="MEMBERSHIP_CARD_CREDIT",
                    patient_id=card.patient_id,
                    context={
                        "amount": f"{tx.amount:,.2f}",
                        "balance": f"{card.balance:,.2f}",
                        "reference": tx.reference
                    }
                )
            )
        except Exception as e:
            print(f"Error sending Paystack credit notification: {e}")

        return transaction

    def debit_card(
        self, card_id: int, payload: MembershipCardDebit, processed_by_id: int, facility_id: int, payment_id: Optional[int] = None
    ) -> MembershipCardTransaction:
        card = self.get_card(card_id)
        
        if card.status != MembershipCardStatus.ACTIVE:
            raise ValidationError(f"Cannot debit a card that is in {card.status} status.")

        if card.balance < payload.amount:
            raise ValidationError("Insufficient membership card balance.")

        balance_before = card.balance
        card.balance -= payload.amount
        balance_after = card.balance
        
        self.repository.update_card(card)

        transaction = MembershipCardTransaction(
            membership_card_id=card.id,
            patient_id=card.patient_id,
            amount=payload.amount,
            transaction_type=MembershipCardTransactionType.DEBIT,
            balance_before=balance_before,
            balance_after=balance_after,
            facility_id=facility_id,
            processed_by_id=processed_by_id,
            transaction_date=datetime.utcnow(),
            narration=payload.narration or "Debit for services",
            invoice_id=payload.invoice_id,
            visit_id=payload.visit_id,
            payment_id=payment_id,
        )
        
        transaction = self.repository.create_transaction(transaction)
        
        # Trigger Notification
        try:
            self.notification_service.dispatch_from_template(
                payload=NotificationDispatchSchema(
                    template_code="MEMBERSHIP_CARD_DEBIT",
                    patient_id=card.patient_id,
                    context={
                        "amount": f"{payload.amount:,.2f}",
                        "balance": f"{card.balance:,.2f}",
                        "narration": payload.narration or "Services"
                    }
                )
            )
        except Exception as e:
            print(f"Error sending debit notification: {e}")

        return transaction

    def get_card_transactions(self, card_id: int) -> List[MembershipCardTransaction]:
        self.get_card(card_id) # Ensure exists
        return self.repository.get_transactions_by_card_id(card_id)
