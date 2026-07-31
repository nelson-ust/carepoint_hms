# app/repositories/referral_repository.py
from __future__ import annotations

"""
Repository for the patient referral module.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.enums import ReferralStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import (
    Referral, Patient, Visit, StaffProfile, 
    InterFacilityReferral, InterFacilityAccessGrant, PatientRecordTransferRequest
)
from app.utils.helpers import generate_uuid_str


class ReferralRepository:
    """Persistence layer for ``Referral``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, referral_id: int) -> Optional[Referral]:
        """Single referral with patient, visit, and staff eagerly loaded."""
        return (
            self.db.query(Referral)
            .options(
                joinedload(Referral.patient),
                joinedload(Referral.visit),
                joinedload(Referral.referring_staff),
            )
            .filter(
                Referral.id == referral_id,
                Referral.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, referral_id: int) -> Referral:
        """Service-layer ergonomic: 404 if missing."""
        r = self.get_by_id(referral_id)
        if not r:
            raise NotFoundError(
                message="Referral not found.",
                detail={"referral_id": referral_id},
            )
        return r

    def get_by_no(self, referral_no: str) -> Optional[Referral]:
        return (
            self.db.query(Referral)
            .filter(
                Referral.referral_no == referral_no.strip(),
                Referral.is_deleted.is_(False),
            )
            .first()
        )

    def list_referrals(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        patient_id: Optional[int] = None,
        visit_id: Optional[int] = None,
        referring_staff_id: Optional[int] = None,
        status: Optional[ReferralStatus] = None,
        source_facility_id: Optional[int] = None,
        destination_facility_id: Optional[int] = None,
    ) -> tuple[list[Referral], int]:
        """Paginated list with common filters."""
        query = (
            self.db.query(Referral)
            .options(joinedload(Referral.patient))
            .filter(Referral.is_deleted.is_(False))
        )

        if patient_id is not None:
            query = query.filter(Referral.patient_id == patient_id)
        if visit_id is not None:
            query = query.filter(Referral.visit_id == visit_id)
        if referring_staff_id is not None:
            query = query.filter(Referral.referring_staff_id == referring_staff_id)
        if status is not None:
            query = query.filter(Referral.status == status)
        if source_facility_id is not None:
            query = query.filter(Referral.source_facility_id == source_facility_id)
        if destination_facility_id is not None:
            query = query.filter(Referral.destination_facility_id == destination_facility_id)

        total = query.with_entities(func.count(Referral.id)).scalar() or 0
        items = (
            query.order_by(Referral.referral_date.desc(), Referral.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def generate_referral_no(self) -> str:
        """Deterministic code: ``REF-YYYYMMDD-XXXXXXXX``."""
        return f"REF-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create_referral(
        self,
        *,
        patient_id: int,
        visit_id: Optional[int],
        referring_staff_id: int,
        destination_facility: str,
        reason_for_referral: str,
        clinical_summary: Optional[str] = None,
        referral_date: datetime,
        status: ReferralStatus = ReferralStatus.PENDING,
        priority = None,
        source_facility_id: Optional[int] = None,
        destination_facility_id: Optional[int] = None,
    ) -> Referral:
        referral = Referral(
            patient_id=patient_id,
            visit_id=visit_id,
            referring_staff_id=referring_staff_id,
            referral_no=self.generate_referral_no(),
            destination_facility=destination_facility,
            reason_for_referral=reason_for_referral,
            clinical_summary=clinical_summary,
            referral_date=referral_date,
            status=status,
            priority=priority,
            source_facility_id=source_facility_id,
            destination_facility_id=destination_facility_id,
        )
        self.db.add(referral)
        self.db.flush()
        self.db.refresh(referral)
        return referral

    def save(self, referral: Referral) -> Referral:
        self.db.add(referral)
        self.db.flush()
        self.db.refresh(referral)
        return referral

    def get_patient(self, patient_id: int) -> Optional[Patient]:
        return (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
            .first()
        )

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def get_staff(self, staff_id: int) -> Optional[StaffProfile]:
        return (
            self.db.query(StaffProfile)
            .filter(
                StaffProfile.id == staff_id,
                StaffProfile.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # INTER-FACILITY REFERRALS
    # ============================================================

    def create_inter_facility_referral(
        self,
        *,
        source_tenant_id: int,
        source_facility_id: int,
        target_tenant_id: int,
        target_facility_id: int,
        patient_global_id: str,
        reason_for_referral: str,
        clinical_summary: Optional[str] = None,
        referral_date: Optional[datetime] = None,
    ) -> InterFacilityReferral:
        referral = InterFacilityReferral(
            referral_no=self.generate_referral_no(),
            source_tenant_id=source_tenant_id,
            source_facility_id=source_facility_id,
            target_tenant_id=target_tenant_id,
            target_facility_id=target_facility_id,
            patient_global_id=patient_global_id,
            reason_for_referral=reason_for_referral,
            clinical_summary=clinical_summary,
            referral_date=referral_date or datetime.now(timezone.utc),
            status=ReferralStatus.PENDING,
        )
        self.db.add(referral)
        self.db.flush()
        self.db.refresh(referral)
        return referral

    def get_inter_facility_referral(self, referral_id: int) -> Optional[InterFacilityReferral]:
        return (
            self.db.query(InterFacilityReferral)
            .filter(InterFacilityReferral.id == referral_id, InterFacilityReferral.is_deleted.is_(False))
            .first()
        )

    def list_incoming_inter_facility_referrals(
        self,
        target_tenant_id: int,
        *,
        skip: int = 0,
        limit: int = 50,
        status: Optional[ReferralStatus] = None,
    ) -> tuple[list[InterFacilityReferral], int]:
        query = self.db.query(InterFacilityReferral).filter(
            InterFacilityReferral.target_tenant_id == target_tenant_id,
            InterFacilityReferral.is_deleted.is_(False),
        )
        if status:
            query = query.filter(InterFacilityReferral.status == status)
        
        total = query.with_entities(func.count(InterFacilityReferral.id)).scalar() or 0
        items = query.order_by(InterFacilityReferral.referral_date.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def list_outgoing_inter_facility_referrals(
        self,
        source_tenant_id: int,
        *,
        skip: int = 0,
        limit: int = 50,
        status: Optional[ReferralStatus] = None,
    ) -> tuple[list[InterFacilityReferral], int]:
        query = self.db.query(InterFacilityReferral).filter(
            InterFacilityReferral.source_tenant_id == source_tenant_id,
            InterFacilityReferral.is_deleted.is_(False),
        )
        if status:
            query = query.filter(InterFacilityReferral.status == status)
        
        total = query.with_entities(func.count(InterFacilityReferral.id)).scalar() or 0
        items = query.order_by(InterFacilityReferral.referral_date.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def create_access_grant(
        self,
        *,
        referral_id: int,
        patient_global_id: str,
        source_tenant_id: int,
        target_tenant_id: int,
        expires_at: Optional[datetime] = None,
    ) -> InterFacilityAccessGrant:
        grant = InterFacilityAccessGrant(
            referral_id=referral_id,
            patient_global_id=patient_global_id,
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            expires_at=expires_at,
            is_active=True,
        )
        self.db.add(grant)
        self.db.flush()
        self.db.refresh(grant)
        return grant
