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
from app.core.database import get_master_db_context, get_tenant_db_context
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

    def list_facility_referrals(self, *, facility_id: int, direction: str, **filters):
        """List internal (within-tenant) facility referrals for a facility.
        direction='incoming' -> referrals sent TO this facility;
        direction='outgoing' -> referrals sent FROM this facility."""
        if direction == "incoming":
            filters["destination_facility_id"] = facility_id
        else:
            filters["source_facility_id"] = facility_id
        status = filters.get("status")
        if status is not None and isinstance(status, str):
            try:
                filters["status"] = ReferralStatus(status.strip().upper())
            except ValueError as exc:
                raise BadRequestError(message="Invalid referral status filter.", detail={"status": status}) from exc
        return self.repository.list_referrals(**filters)

    def create_referral(
        self,
        payload: ReferralCreateSchema,
        *,
        referring_staff_id: int,
        source_facility_id: Optional[int] = None,
        actor_user_id: Optional[int] = None,
    ) -> Referral:
        """Create a new referral record.

        When ``destination_facility_id`` is supplied the referral is *internal*
        (facility-to-facility within this tenant): the receiving facility can
        open the patient's record directly since it shares this database. The
        free-text ``destination_facility`` is auto-filled from the facility name.
        """
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

        destination_text = payload.destination_facility
        destination_facility_id = payload.destination_facility_id
        if destination_facility_id is not None:
            from app.models.all_models import Facility

            facility = (
                self.db.query(Facility)
                .filter(Facility.id == destination_facility_id, Facility.is_deleted.is_(False))
                .first()
            )
            if facility is None:
                raise NotFoundError(message="Destination facility not found.",
                                    detail={"destination_facility_id": destination_facility_id})
            destination_text = destination_text or facility.name
        if not destination_text:
            raise BadRequestError(message="Provide a destination facility (internal facility or free-text).")

        referral = self.repository.create_referral(
            patient_id=payload.patient_id,
            visit_id=payload.visit_id,
            referring_staff_id=referring_staff_id,
            destination_facility=destination_text,
            reason_for_referral=payload.reason_for_referral,
            clinical_summary=payload.clinical_summary,
            referral_date=payload.referral_date,
            priority=payload.priority,
            source_facility_id=source_facility_id,
            destination_facility_id=destination_facility_id,
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

    def _tenant_name_email(self, tenant_id: int):
        """(name, contact_email) for a tenant, from the master registry."""
        from app.models.all_models import Tenant
        with get_master_db_context() as mdb:
            t = mdb.query(Tenant).filter(Tenant.id == tenant_id).first()
            if t is None:
                return (f"Hospital #{tenant_id}", None)
            return (t.name, getattr(t, "billing_email", None) or getattr(t, "contact_email", None))

    def _notify_tenant_cross(self, tenant_id: int, *, subject: str, body: str,
                             event_code: str, metadata: dict) -> None:
        """Best-effort notification INTO another tenant.

        Cross-hospital events (referrals in/out, responses) must be written to
        the RECEIVING tenant's database — a notification created in the acting
        tenant's own DB is invisible to the other hospital. Creates an IN_APP
        notification for each admin/superuser there, plus a branded email to
        the hospital's contact address. Never raises: the business record is
        already committed by the time this runs.
        """
        from app.core.enums import NotificationChannel, NotificationStatus
        from app.models.all_models import Notification, Role, User, UserRoleAssociation

        # In-app rows inside the target tenant's own DB.
        try:
            with get_tenant_db_context(tenant_id) as tdb:
                recipient_ids: set[int] = set()
                try:
                    recipient_ids.update(
                        uid for (uid,) in tdb.query(UserRoleAssociation.user_id)
                        .join(Role, Role.id == UserRoleAssociation.role_id)
                        .filter(Role.code.in_(["TENANT_ADMIN", "ADMIN"]),
                                UserRoleAssociation.is_deleted.is_(False))
                        .distinct().all()
                    )
                except Exception:
                    pass
                try:
                    recipient_ids.update(
                        uid for (uid,) in tdb.query(User.id)
                        .filter(User.is_superuser.is_(True), User.is_deleted.is_(False))
                        .all()
                    )
                except Exception:
                    pass
                rows = [
                    Notification(
                        user_id=uid, channel=NotificationChannel.IN_APP,
                        status=NotificationStatus.PENDING, event_code=event_code,
                        subject=subject, body=body, payload_metadata=metadata,
                    )
                    for uid in recipient_ids
                ]
                if rows:
                    tdb.add_all(rows)
                    tdb.commit()
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Cross-tenant in-app notification to tenant %s failed.", tenant_id
            )

        # Email to the hospital's contact address (best-effort).
        try:
            _, email = self._tenant_name_email(tenant_id)
            if email:
                from app.utils.email_utils import (
                    render_branded_email, render_branded_email_text, send_email,
                )
                common = dict(title=subject, intro=body, details=None,
                              cta_label=None, cta_url=None, footer_note=None)
                send_email(subject=subject, recipients=email,
                           body_text=render_branded_email_text(**common),
                           body_html=render_branded_email(**common))
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Cross-tenant email notification to tenant %s failed.", tenant_id
            )

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

        # Notify the RECEIVING hospital — in ITS tenant DB, not ours. A
        # notification written to the sending tenant's DB is invisible to the
        # target hospital, which is exactly the "referral sent but nobody was
        # told" failure. Best-effort: the referral is already committed.
        source_name, _ = self._tenant_name_email(source_tenant_id)
        self._notify_tenant_cross(
            referral.target_tenant_id,
            subject="New incoming referral",
            body=(
                f"{source_name} has referred patient {payload.patient_global_id} "
                f"to your hospital (referral {referral.referral_no}). "
                f"Reason: {payload.reason_for_referral}. "
                "Open Interoperability → Referrals Received to accept or decline."
            ),
            event_code="INTER_FACILITY_REFERRAL_RECEIVED",
            metadata={"referral_id": referral.id, "referral_no": referral.referral_no,
                      "source_tenant_id": source_tenant_id},
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

        # Notify the SENDING hospital — in ITS tenant DB (same cross-tenant
        # rule as creation; the previous dispatch landed in the responder's
        # own DB where the sender could never see it).
        target_name, _ = self._tenant_name_email(referral.target_tenant_id)
        status_word = str(getattr(payload.status, "value", payload.status)).lower()
        self._notify_tenant_cross(
            referral.source_tenant_id,
            subject=f"Referral {status_word}",
            body=(
                f"{target_name} has {status_word} referral {referral.referral_no} "
                f"for patient {referral.patient_global_id}."
                + (f" Note: {payload.note}" if payload.note else "")
            ),
            event_code="INTER_FACILITY_REFERRAL_RESPONDED",
            metadata={"referral_id": referral.id, "referral_no": referral.referral_no,
                      "status": str(getattr(payload.status, "value", payload.status))},
        )

        return referral

    def get_referral_record(self, referral_id: int, *,
                            requesting_tenant_id: int,
                            actor_user_id: Optional[int] = None) -> dict:
        """The post-acceptance payoff: the RECEIVING hospital pulls the
        patient's record (history + baseline diagnostics such as blood group
        and genotype) live from the referring hospital's database.

        Guards: only the target tenant, only after ACCEPTED, only while the
        access grant is active and unexpired. The export is generated fresh
        on each read so the receiving clinicians always see current data.
        """
        now = datetime.now(timezone.utc)
        from app.models.all_models import InterFacilityAccessGrant

        with get_master_db_context() as master_db:
            master_repo = ReferralRepository(master_db)
            referral = master_repo.get_inter_facility_referral(referral_id)
            if referral is None:
                raise NotFoundError(message="Inter-facility referral not found.")
            if referral.target_tenant_id != requesting_tenant_id:
                raise BadRequestError(
                    message="Only the receiving hospital can open this referral's record."
                )
            if referral.status != ReferralStatus.ACCEPTED or not referral.is_history_access_granted:
                raise BadRequestError(
                    message="Record access is only available after the referral is accepted."
                )

            expires_at = referral.access_expires_at
            if expires_at is not None and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at is not None and now > expires_at:
                raise BadRequestError(
                    message="The time-limited access for this referral has expired. "
                            "Ask the referring hospital to re-share, or raise a records request."
                )

            grant = (
                master_db.query(InterFacilityAccessGrant)
                .filter(InterFacilityAccessGrant.referral_id == referral.id,
                        InterFacilityAccessGrant.target_tenant_id == requesting_tenant_id,
                        InterFacilityAccessGrant.is_active.is_(True))
                .order_by(InterFacilityAccessGrant.id.desc())
                .first()
            )
            if grant is None:
                raise BadRequestError(
                    message="No active access grant exists for this referral."
                )

            source_tenant_id = referral.source_tenant_id
            referral_no = referral.referral_no
            patient_global_id = referral.patient_global_id
            access_expires_at = referral.access_expires_at

        # Live export from the REFERRING hospital's own database.
        from app.utils.patient_export import build_patient_full_export
        with get_tenant_db_context(source_tenant_id) as tdb:
            export = build_patient_full_export(tdb, patient_global_id)
        if export is None:
            raise NotFoundError(
                message="The patient could not be found in the referring hospital's records."
            )

        record_security_event(
            self.db, user_id=actor_user_id,
            event_type="INTER_FACILITY_REFERRAL_RECORD_ACCESSED", severity="INFO",
            event_detail=f"Record for referral {referral_no} accessed by receiving hospital.",
            event_metadata={"referral_id": referral_id,
                            "patient_global_id": patient_global_id},
        )

        # Resolve the referring hospital's display name for provenance tagging.
        source_hospital_name = None
        try:
            from app.models.all_models import Tenant
            with get_master_db_context() as _mdb:
                _t = _mdb.query(Tenant).filter(Tenant.id == source_tenant_id).first()
                source_hospital_name = getattr(_t, "name", None) if _t else None
        except Exception:
            source_hospital_name = None

        return {
            "id": referral_id,
            "referral_no": referral_no,
            "patient_global_id": patient_global_id,
            "access_expires_at": access_expires_at,
            "source_tenant_id": source_tenant_id,
            "source_hospital_name": source_hospital_name,
            "payload": export,
        }

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
