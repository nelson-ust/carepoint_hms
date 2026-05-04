# app/services/referral_service.py
from __future__ import annotations

"""
Service layer for patient referral operations.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import ReferralStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Referral, InterFacilityReferral
from app.repositories.referral_repository import ReferralRepository
from app.services.notification_service import NotificationService
from app.core.database import get_master_db_context
from app.schemas.referral_schemas import (
    ReferralCreateSchema, 
    ReferralUpdateSchema,
    InterFacilityReferralCreateSchema,
    InterFacilityReferralResponseSchema
)
from app.utils.security_event_util import record_security_event


class ReferralService:
    """Service layer for patient referral operations."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ReferralRepository(db)
        self.notification_service = NotificationService(db)

    def get(self, referral_id: int) -> Referral:
        """Return one referral, raising 404 when missing."""
        return self.repository.get_required_by_id(referral_id)

    def list_referrals(self, **filters):
        """Paginated list of referrals."""
        status = filters.get("status")
        if status is not None and isinstance(status, str):
            try:
                filters["status"] = ReferralStatus(status.strip().upper())
            except ValueError as exc:
                raise BadRequestError(
                    message="Invalid referral status filter.",
                    detail={"status": status},
                ) from exc
        return self.repository.list_referrals(**filters)

    def create_referral(
        self,
        payload: ReferralCreateSchema,
        *,
        referring_staff_id: int,
        actor_user_id: Optional[int] = None,
    ) -> Referral:
        """Create a new referral record."""
        # Validate existence
        if self.repository.get_patient(payload.patient_id) is None:
            raise NotFoundError(
                message="Patient not found.",
                detail={"patient_id": payload.patient_id},
            )

        if payload.visit_id is not None and self.repository.get_visit(payload.visit_id) is None:
            raise NotFoundError(
                message="Visit not found.",
                detail={"visit_id": payload.visit_id},
            )

        referral = self.repository.create_referral(
            patient_id=payload.patient_id,
            visit_id=payload.visit_id,
            referring_staff_id=referring_staff_id,
            destination_facility=payload.destination_facility,
            reason_for_referral=payload.reason_for_referral,
            clinical_summary=payload.clinical_summary,
            referral_date=payload.referral_date,
            priority=payload.priority,
        )

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PATIENT_REFERRAL_CREATED",
            severity="INFO",
            event_detail=f"Referral {referral.referral_no} created for patient {referral.patient_id}.",
            event_metadata={
                "referral_id": referral.id,
                "patient_id": referral.patient_id,
                "destination_facility": referral.destination_facility,
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(referral.id)

    def update_referral(
        self,
        referral_id: int,
        payload: ReferralUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Referral:
        """Update an existing referral."""
        referral = self.repository.get_required_by_id(referral_id)

        if referral.status in {ReferralStatus.COMPLETED, ReferralStatus.CANCELLED}:
             raise BadRequestError(
                message="Cannot update a referral that is already completed or cancelled.",
                detail={"status": str(referral.status)},
            )

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(referral, field, value)

        self.repository.save(referral)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PATIENT_REFERRAL_UPDATED",
            severity="INFO",
            event_detail=f"Referral {referral.referral_no} updated.",
            event_metadata={
                "referral_id": referral.id,
                "updates": update_data,
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(referral.id)

    def cancel_referral(
        self,
        referral_id: int,
        *,
        reason: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> Referral:
        """Cancel a referral."""
        referral = self.repository.get_required_by_id(referral_id)

        if referral.status in {ReferralStatus.COMPLETED, ReferralStatus.CANCELLED}:
            raise BadRequestError(
                message="Referral already in a terminal state.",
                detail={"status": str(referral.status)},
            )

        referral.status = ReferralStatus.CANCELLED
        self.repository.save(referral)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="PATIENT_REFERRAL_CANCELLED",
            severity="WARNING",
            event_detail=f"Referral {referral.referral_no} cancelled.",
            event_metadata={
                "referral_id": referral.id,
                "reason": reason,
            },
        )

        self.db.commit()
        return self.repository.get_required_by_id(referral.id)

    # ============================================================
    # INTER-FACILITY REFERRALS
    # ============================================================

    def create_inter_facility_referral(
        self,
        payload: InterFacilityReferralCreateSchema,
        *,
        source_tenant_id: int,
        source_facility_id: int,
        actor_user_id: Optional[int] = None,
    ) -> InterFacilityReferral:
        """Create a cross-tenant referral in the master database."""
        with get_master_db_context() as master_db:
            master_repo = ReferralRepository(master_db)
            referral = master_repo.create_inter_facility_referral(
                source_tenant_id=source_tenant_id,
                source_facility_id=source_facility_id,
                target_tenant_id=payload.target_tenant_id,
                target_facility_id=payload.target_facility_id,
                patient_global_id=payload.patient_global_id,
                reason_for_referral=payload.reason_for_referral,
                clinical_summary=payload.clinical_summary,
                referral_date=payload.referral_date,
            )
            master_db.commit()
            master_db.refresh(referral)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INTER_FACILITY_REFERRAL_CREATED",
            severity="INFO",
            event_detail=f"Inter-facility referral {referral.referral_no} created for patient {payload.patient_global_id}.",
            event_metadata={
                "referral_id": referral.id,
                "target_tenant_id": referral.target_tenant_id,
            },
        )

        # Notify target tenant
        self.notification_service.dispatch_ad_hoc(
            payload={
                "channel": "IN_APP",
                "subject": "New Incoming Referral",
                "body": f"New referral {referral.referral_no} received for patient {payload.patient_global_id}.",
                "payload_metadata": {"referral_id": referral.id, "target_tenant_id": referral.target_tenant_id}
            },
            actor_user_id=actor_user_id
        )

        return referral

    def respond_to_inter_facility_referral(
        self,
        referral_id: int,
        payload: InterFacilityReferralResponseSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> InterFacilityReferral:
        """Accept or decline an incoming inter-facility referral in the master database."""
        with get_master_db_context() as master_db:
            master_repo = ReferralRepository(master_db)
            referral = master_repo.get_inter_facility_referral(referral_id)
            if not referral:
                raise NotFoundError(message="Inter-facility referral not found.")

            if referral.status != ReferralStatus.PENDING:
                raise BadRequestError(message="Referral has already been responded to.")

            if payload.status not in {ReferralStatus.ACCEPTED, ReferralStatus.DECLINED}:
                raise BadRequestError(message="Status must be ACCEPTED or DECLINED.")

            referral.status = payload.status
            referral.responded_at = datetime.now(timezone.utc)
            
            if payload.status == ReferralStatus.ACCEPTED:
                referral.acceptance_note = payload.note
                referral.is_history_access_granted = True
                referral.access_expires_at = datetime.now(timezone.utc) + timedelta(days=payload.access_expiry_days)
                
                # Create explicit access grant record in master DB
                master_repo.create_access_grant(
                    referral_id=referral.id,
                    patient_global_id=referral.patient_global_id,
                    source_tenant_id=referral.source_tenant_id,
                    target_tenant_id=referral.target_tenant_id,
                    expires_at=referral.access_expires_at,
                )
            else:
                referral.declined_reason = payload.note

            master_repo.save(referral)
            master_db.commit()
            master_db.refresh(referral)

        record_security_event(
            self.db,
            user_id=actor_user_id,
            event_type="INTER_FACILITY_REFERRAL_RESPONDED",
            severity="INFO",
            event_detail=f"Inter-facility referral {referral.referral_no} {payload.status}.",
            event_metadata={
                "referral_id": referral.id,
                "status": str(payload.status),
            },
        )

        # Notify source tenant
        self.notification_service.dispatch_ad_hoc(
            payload={
                "channel": "IN_APP",
                "subject": f"Referral {payload.status}",
                "body": f"Referral {referral.referral_no} has been {payload.status.lower()}.",
                "payload_metadata": {"referral_id": referral.id, "source_tenant_id": referral.source_tenant_id}
            },
            actor_user_id=actor_user_id
        )

        return referral

    def list_incoming_referrals(self, tenant_id: int, **filters):
        """List incoming referrals for a tenant from the master database."""
        with get_master_db_context() as master_db:
            master_repo = ReferralRepository(master_db)
            return master_repo.list_incoming_inter_facility_referrals(tenant_id, **filters)

    def list_outgoing_referrals(self, tenant_id: int, **filters):
        """List outgoing referrals for a tenant from the master database."""
        with get_master_db_context() as master_db:
            master_repo = ReferralRepository(master_db)
            return master_repo.list_outgoing_inter_facility_referrals(tenant_id, **filters)
