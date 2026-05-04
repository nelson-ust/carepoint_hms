# app/services/patient_portal_service.py
from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, BadRequestError
from app.models.all_models import Patient, User, MembershipCard, Notification, LabResult, LabOrderItem, LabOrder, Visit
from app.repositories.membership_card_repository import MembershipCardRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.patient_portal_schemas import PatientPortalDashboard, PatientPortalProfile
from app.services.patient_service import PatientService
from app.services.membership_card_service import MembershipCardService
from app.services.notification_service import NotificationService


class PatientPortalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.patient_service = PatientService(db)
        self.membership_card_service = MembershipCardService(db)
        self.notification_service = NotificationService(db)
        self.card_repo = MembershipCardRepository(db)
        self.notification_repo = NotificationRepository(db)

    def get_patient_by_user_id(self, user_id: int) -> Patient:
        patient = self.db.query(Patient).filter(Patient.user_id == user_id).first()
        if not patient:
            raise NotFoundError(message="No patient record linked to this user account.")
        return patient

    def get_dashboard(self, user_id: int) -> PatientPortalDashboard:
        patient = self.get_patient_by_user_id(user_id)
        
        # Get active membership card
        cards = self.membership_card_service.list_patient_cards(patient.id)
        card = cards[0] if cards else None
        
        recent_transactions = []
        if card:
            recent_transactions = self.membership_card_service.get_card_transactions(card.id)[:5]
            
        # Get recent released lab results
        recent_lab_results = self.db.query(LabResult).join(
            LabOrderItem, LabResult.lab_order_item_id == LabOrderItem.id
        ).join(
            LabOrder, LabOrderItem.lab_order_id == LabOrder.id
        ).join(
            Visit, LabOrder.visit_id == Visit.id
        ).filter(
            Visit.patient_id == patient.id,
            LabResult.result_status == "RELEASED"
        ).order_by(LabResult.released_at.desc()).limit(5).all()

        unread_notifications = self.notification_repo.list_notifications(
            patient_id=patient.id,
            status="SENT", # SENT but not READ
            limit=1
        )[1] # total count

        wallet_balance = getattr(card, "balance", None) or 0

        return PatientPortalDashboard(
            patient=patient,
            card=card,
            wallet_balance=wallet_balance,
            recent_transactions=recent_transactions,
            recent_lab_results=recent_lab_results,
            unread_notifications_count=unread_notifications
        )

    def get_profile(self, user_id: int) -> PatientPortalProfile:
        patient = self.get_patient_by_user_id(user_id)
        user = self.db.query(User).get(user_id)
        
        return PatientPortalProfile(
            patient=patient,
            username=user.username,
            email=user.email
        )

    def list_notifications(self, user_id: int, skip: int = 0, limit: int = 20) -> List[Notification]:
        patient = self.get_patient_by_user_id(user_id)
        return self.notification_repo.list_notifications(
            patient_id=patient.id,
            skip=skip,
            limit=limit
        )[0]
