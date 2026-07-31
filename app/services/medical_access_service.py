# app/services/medical_access_service.py
from __future__ import annotations

"""
Consent-gated medical-record access workflow.

A hospital or a registered developer app requests a patient's medical history.
The system notifies the patient and the patient's primary hospital (email +
in-app), both of whom must approve. Only once every required approval is
satisfied does the system mint a **secure, one-time, read-only access link**
that expires after a configurable window and becomes invalid once used. Every
step is recorded in an append-only audit trail.

All coordination rows live in the master DB; patient data is read from the
holding tenant's own database and frozen into a point-in-time snapshot at
approval time.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.api_key import generate_prefixed_key, extract_scheme_prefix, verify_api_key
from app.core.database import get_master_db_context, get_tenant_db_context
from app.core.enums import (
    MedicalAccessActorType,
    MedicalAccessAuditEvent,
    MedicalAccessDecision,
    MedicalAccessRequesterType,
    MedicalAccessStatus,
    NotificationChannel,
    NotificationStatus,
)
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.utils.patient_export import (
    build_patient_baseline_diagnostics,
    build_patient_medical_history,
)

_PATIENT_TOKEN_SCHEME = "cpa"    # patient decision token
_ACCESS_TOKEN_SCHEME = "cpl"     # one-time access link token
_DEFAULT_EXPIRY_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _frontend_base() -> str:
    try:
        from app.core.config import settings
        return (getattr(settings, "FRONTEND_URL", "") or "").rstrip("/")
    except Exception:
        return ""


def _default_expiry_hours() -> int:
    try:
        from app.core.config import settings
        return int(getattr(settings, "MEDICAL_ACCESS_LINK_EXPIRY_HOURS", _DEFAULT_EXPIRY_HOURS))
    except Exception:
        return _DEFAULT_EXPIRY_HOURS


# ===========================================================================
# Serialization
# ===========================================================================

def _req_read(r, *, include_secrets: bool = False) -> dict:
    data = {
        "id": r.id,
        "request_no": r.request_no,
        "requester_type": r.requester_type.value if hasattr(r.requester_type, "value") else r.requester_type,
        "requester_name": r.requester_name,
        "requesting_tenant_id": r.requesting_tenant_id,
        "requesting_facility_id": r.requesting_facility_id,
        "holding_tenant_id": r.holding_tenant_id,
        "patient_global_id": r.patient_global_id,
        "patient_display_name": r.patient_display_name,
        "reason": r.reason,
        "scope": r.scope,
        "status": r.status.value if hasattr(r.status, "value") else r.status,
        "requires_patient_approval": r.requires_patient_approval,
        "requires_hospital_approval": r.requires_hospital_approval,
        "patient_decision": r.patient_decision.value if hasattr(r.patient_decision, "value") else r.patient_decision,
        "patient_decided_at": _as_utc(r.patient_decided_at).isoformat() if r.patient_decided_at else None,
        "hospital_decision": r.hospital_decision.value if hasattr(r.hospital_decision, "value") else r.hospital_decision,
        "hospital_decided_at": _as_utc(r.hospital_decided_at).isoformat() if r.hospital_decided_at else None,
        "decline_reason": r.decline_reason,
        "link_expiry_hours": r.link_expiry_hours,
        "link_generated_at": _as_utc(r.link_generated_at).isoformat() if r.link_generated_at else None,
        "link_expires_at": _as_utc(r.link_expires_at).isoformat() if r.link_expires_at else None,
        "link_used_at": _as_utc(r.link_used_at).isoformat() if r.link_used_at else None,
        "requested_at": _as_utc(r.requested_at).isoformat() if r.requested_at else None,
    }
    return data


def _audit_read(a) -> dict:
    return {
        "id": a.id,
        "event": a.event.value if hasattr(a.event, "value") else a.event,
        "actor_type": a.actor_type.value if hasattr(a.actor_type, "value") else a.actor_type,
        "actor_display": a.actor_display,
        "detail": a.detail,
        "ip_address": a.ip_address,
        "occurred_at": _as_utc(a.occurred_at).isoformat() if a.occurred_at else None,
    }


class MedicalAccessService:
    # -------------------------------------------------------------------
    # Audit helper
    # -------------------------------------------------------------------
    def _audit(self, mdb, req, event: MedicalAccessAuditEvent, actor_type: MedicalAccessActorType,
               *, actor_id: Optional[int] = None, actor_display: Optional[str] = None,
               detail: Optional[str] = None, ip: Optional[str] = None) -> None:
        from app.models.all_models import MedicalRecordAccessAudit
        mdb.add(MedicalRecordAccessAudit(
            request_id=req.id, request_no=req.request_no, event=event,
            actor_type=actor_type, actor_id=actor_id, actor_display=actor_display,
            detail=detail, ip_address=ip, occurred_at=_now(),
        ))

    # -------------------------------------------------------------------
    # Patient lookup + notifications inside the holding tenant DB
    # -------------------------------------------------------------------
    def _resolve_patient(self, holding_tenant_id: int, global_patient_id: str) -> Optional[dict]:
        from app.models.all_models import Patient
        try:
            with get_tenant_db_context(holding_tenant_id) as tdb:
                q = tdb.query(Patient).filter(Patient.global_patient_id == global_patient_id)
                if hasattr(Patient, "is_deleted"):
                    q = q.filter(Patient.is_deleted.is_(False))
                p = q.first()
                if p is None:
                    return None
                name = " ".join(x for x in [p.first_name, getattr(p, "last_name", None)] if x)
                return {"id": p.id, "name": name.strip() or global_patient_id, "email": getattr(p, "email", None)}
        except Exception:
            return None

    def _inapp_notify(self, holding_tenant_id: int, *, patient_id: Optional[int],
                      subject: str, body: str, event_code: str, metadata: dict) -> None:
        """Best-effort in-app notifications inside the holding tenant DB: one to
        the patient, and one to each tenant admin user."""
        from app.models.all_models import Notification, Role, User, UserRoleAssociation
        try:
            with get_tenant_db_context(holding_tenant_id) as tdb:
                rows = []
                if patient_id is not None:
                    rows.append(Notification(
                        patient_id=patient_id, channel=NotificationChannel.IN_APP,
                        status=NotificationStatus.PENDING, event_code=event_code,
                        subject=subject, body=body, payload_metadata=metadata,
                    ))
                try:
                    admin_user_ids = [
                        uid for (uid,) in tdb.query(UserRoleAssociation.user_id)
                        .join(Role, Role.id == UserRoleAssociation.role_id)
                        .filter(Role.code.in_(["TENANT_ADMIN", "ADMIN"]))
                        .distinct().all()
                    ]
                except Exception:
                    admin_user_ids = []
                for uid in admin_user_ids:
                    rows.append(Notification(
                        user_id=uid, channel=NotificationChannel.IN_APP,
                        status=NotificationStatus.PENDING, event_code=event_code,
                        subject=subject, body=body, payload_metadata=metadata,
                    ))
                if rows:
                    tdb.add_all(rows)
                    tdb.commit()
        except Exception:
            pass

    def _email(self, *, to: Optional[str], subject: str, title: str, intro: str,
               details: Optional[list] = None, cta_label: Optional[str] = None,
               cta_url: Optional[str] = None, footer: Optional[str] = None) -> bool:
        if not to:
            return False
        try:
            from app.utils.email_utils import send_email, render_branded_email, render_branded_email_text
            common = dict(title=title, intro=intro, details=details,
                          cta_label=cta_label, cta_url=cta_url, footer_note=footer)
            res = send_email(subject=subject, recipients=to,
                             body_text=render_branded_email_text(**common),
                             body_html=render_branded_email(**common))
            return bool(res.get("success"))
        except Exception:
            return False

    def _tenant_name_email(self, tenant_id: int) -> tuple[str, Optional[str]]:
        from app.models.all_models import Tenant
        with get_master_db_context() as mdb:
            t = mdb.query(Tenant).filter(Tenant.id == tenant_id).first()
            if t is None:
                return (f"Tenant #{tenant_id}", None)
            return (t.name, getattr(t, "billing_email", None))

    # -------------------------------------------------------------------
    # Submit a request
    # -------------------------------------------------------------------
    def submit_request(self, *, requester_type: MedicalAccessRequesterType,
                       holding_tenant_id: int, patient_global_id: str, reason: str,
                       scope: str = "MEDICAL_HISTORY",
                       requesting_tenant_id: Optional[int] = None,
                       requesting_facility_id: Optional[int] = None,
                       requesting_developer_app_id: Optional[int] = None,
                       requester_name: str = "", requester_contact_email: Optional[str] = None,
                       requested_by_user_id: Optional[int] = None,
                       requires_patient_approval: bool = True,
                       requires_hospital_approval: bool = True,
                       link_expiry_hours: Optional[int] = None) -> dict:
        from app.models.all_models import MedicalRecordAccessRequest, Tenant

        if not (reason or "").strip():
            raise BadRequestError(message="A reason for the request is required.")
        if requesting_tenant_id is not None and requesting_tenant_id == holding_tenant_id:
            raise BadRequestError(message="The requesting and holding hospital are the same.")

        patient = self._resolve_patient(holding_tenant_id, patient_global_id)
        if patient is None:
            raise NotFoundError(message="No patient with that global ID at the holding hospital.")

        expiry_hours = int(link_expiry_hours or _default_expiry_hours())
        patient_full_token, patient_prefix, patient_hash = generate_prefixed_key(_PATIENT_TOKEN_SCHEME)
        request_no = f"MRA-{uuid.uuid4().hex[:12].upper()}"

        with get_master_db_context() as mdb:
            holding = mdb.query(Tenant).filter(Tenant.id == holding_tenant_id).first()
            if holding is None:
                raise NotFoundError(message="Holding hospital not found.")

            req = MedicalRecordAccessRequest(
                request_no=request_no,
                requester_type=requester_type,
                requesting_tenant_id=requesting_tenant_id,
                requesting_facility_id=requesting_facility_id,
                requesting_developer_app_id=requesting_developer_app_id,
                requester_name=requester_name or "Unknown requester",
                requester_contact_email=requester_contact_email,
                holding_tenant_id=holding_tenant_id,
                patient_global_id=patient_global_id,
                patient_display_name=patient["name"],
                patient_email=patient.get("email"),
                reason=reason.strip(),
                scope=(scope or "MEDICAL_HISTORY").strip().upper(),
                status=MedicalAccessStatus.PENDING,
                requires_patient_approval=requires_patient_approval,
                requires_hospital_approval=requires_hospital_approval,
                patient_decision=MedicalAccessDecision.PENDING,
                hospital_decision=MedicalAccessDecision.PENDING,
                patient_decision_token_prefix=patient_prefix,
                patient_decision_token_hash=patient_hash,
                link_expiry_hours=expiry_hours,
                requested_by_user_id=requested_by_user_id,
                requested_at=_now(),
            )
            mdb.add(req)
            mdb.flush()

            self._audit(mdb, req, MedicalAccessAuditEvent.REQUEST_SUBMITTED,
                        MedicalAccessActorType.REQUESTER, actor_id=requested_by_user_id,
                        actor_display=req.requester_name,
                        detail=f"Requested {req.scope} for {req.patient_display_name}. Reason: {req.reason}")
            mdb.commit()
            mdb.refresh(req)
            snapshot = _req_read(req)
            holding_name = holding.name
            req_id = req.id

        # ---- Notifications (best-effort) ----
        base = _frontend_base()
        patient_url = f"{base}/medical-access/patient/{patient_full_token}" if base else None
        when = _as_utc(snapshot["requested_at"]) if isinstance(snapshot["requested_at"], datetime) else snapshot["requested_at"]
        details = [
            ("Requesting party", requester_name or "Unknown"),
            ("Primary hospital", holding_name),
            ("Reason", reason.strip()),
            ("Requested at", str(snapshot["requested_at"])),
        ]
        patient_email_ok = self._email(
            to=patient.get("email"),
            subject="A hospital has requested access to your medical records",
            title="Medical records access request",
            intro=(f"{requester_name or 'A healthcare provider'} has requested access to your "
                   "medical history for continuity of care. Your explicit approval is required "
                   "before any records are shared."),
            details=details,
            cta_label="Review this request" if patient_url else None,
            cta_url=patient_url,
            footer="If you did not expect this, you can decline the request.",
        )
        _, holding_email = self._tenant_name_email(holding_tenant_id)
        hosp_review_url = f"{base}/medical-access?tab=incoming" if base else None
        self._email(
            to=holding_email,
            subject=f"Medical records access request for {patient['name']}",
            title="Incoming medical records access request",
            intro=(f"{requester_name or 'A healthcare provider'} has requested access to a "
                   f"patient's medical history held at your hospital. Review and authorize it in "
                   "the Medical Record Sharing console."),
            details=details, cta_label="Review requests" if hosp_review_url else None,
            cta_url=hosp_review_url,
        )
        self._inapp_notify(
            holding_tenant_id, patient_id=patient["id"],
            subject="Medical records access request",
            body=(f"{requester_name or 'A healthcare provider'} requested access to "
                  f"{patient['name']}'s medical history. Reason: {reason.strip()}"),
            event_code="MEDICAL_ACCESS_REQUEST",
            metadata={"request_no": request_no, "requester": requester_name},
        )
        with get_master_db_context() as mdb:
            req = mdb.query(MedicalRecordAccessRequest).filter(MedicalRecordAccessRequest.id == req_id).first()
            self._audit(mdb, req, MedicalAccessAuditEvent.NOTIFICATION_SENT, MedicalAccessActorType.SYSTEM,
                        detail=f"Notified patient ({'sent' if patient_email_ok else 'no email on file'}) and holding hospital.")
            mdb.commit()

        snapshot["patient_decision_url"] = patient_url
        return snapshot

    # -------------------------------------------------------------------
    # Decisions
    # -------------------------------------------------------------------
    def _load_by_prefix(self, mdb, *, patient_token: Optional[str] = None, access_token: Optional[str] = None):
        from app.models.all_models import MedicalRecordAccessRequest
        if patient_token:
            prefix = extract_scheme_prefix(patient_token)
            if not prefix:
                return None
            return mdb.query(MedicalRecordAccessRequest).filter(
                MedicalRecordAccessRequest.patient_decision_token_prefix == prefix,
                MedicalRecordAccessRequest.is_deleted.is_(False)).first()
        if access_token:
            prefix = extract_scheme_prefix(access_token)
            if not prefix:
                return None
            return mdb.query(MedicalRecordAccessRequest).filter(
                MedicalRecordAccessRequest.access_token_prefix == prefix,
                MedicalRecordAccessRequest.is_deleted.is_(False)).first()
        return None

    def get_by_patient_token(self, token: str) -> dict:
        with get_master_db_context() as mdb:
            req = self._load_by_prefix(mdb, patient_token=token)
            if req is None or not verify_api_key(token, req.patient_decision_token_hash or ""):
                raise NotFoundError(message="Request not found or link invalid.")
            return _req_read(req)

    def patient_decision_by_token(self, *, token: str, approve: bool,
                                  reason: Optional[str] = None, ip: Optional[str] = None) -> dict:
        with get_master_db_context() as mdb:
            req = self._load_by_prefix(mdb, patient_token=token)
            if req is None or not verify_api_key(token, req.patient_decision_token_hash or ""):
                raise NotFoundError(message="Request not found or link invalid.")
            return self._apply_patient_decision(mdb, req, approve, reason, ip,
                                                actor_display=req.patient_display_name)

    def patient_decision_by_portal(self, *, holding_tenant_id: int, patient_global_id: str,
                                   request_no: str, approve: bool, reason: Optional[str] = None,
                                   ip: Optional[str] = None) -> dict:
        from app.models.all_models import MedicalRecordAccessRequest
        with get_master_db_context() as mdb:
            req = mdb.query(MedicalRecordAccessRequest).filter(
                MedicalRecordAccessRequest.request_no == request_no,
                MedicalRecordAccessRequest.holding_tenant_id == holding_tenant_id,
                MedicalRecordAccessRequest.patient_global_id == patient_global_id,
                MedicalRecordAccessRequest.is_deleted.is_(False)).first()
            if req is None:
                raise NotFoundError(message="Request not found for this patient.")
            return self._apply_patient_decision(mdb, req, approve, reason, ip,
                                                actor_display=req.patient_display_name)

    def _apply_patient_decision(self, mdb, req, approve: bool, reason, ip, *, actor_display) -> dict:
        if req.status not in (MedicalAccessStatus.PENDING,):
            raise BadRequestError(message=f"This request is already {req.status.value.lower()}.")
        if req.patient_decision != MedicalAccessDecision.PENDING:
            raise BadRequestError(message="You have already responded to this request.")
        if approve:
            req.patient_decision = MedicalAccessDecision.APPROVED
            req.patient_decided_at = _now()
            self._audit(mdb, req, MedicalAccessAuditEvent.PATIENT_APPROVED, MedicalAccessActorType.PATIENT,
                        actor_display=actor_display, ip=ip)
        else:
            req.patient_decision = MedicalAccessDecision.DECLINED
            req.patient_decided_at = _now()
            req.status = MedicalAccessStatus.DECLINED
            req.decline_reason = (reason or "Declined by patient.")
            self._audit(mdb, req, MedicalAccessAuditEvent.PATIENT_DECLINED, MedicalAccessActorType.PATIENT,
                        actor_display=actor_display, detail=reason, ip=ip)
        mdb.flush()
        self._maybe_finalize(mdb, req)
        mdb.commit()
        mdb.refresh(req)
        return _req_read(req)

    def hospital_decision(self, *, holding_tenant_id: int, request_id: int, approve: bool,
                          user_id: Optional[int] = None, actor_display: Optional[str] = None,
                          reason: Optional[str] = None, ip: Optional[str] = None) -> dict:
        from app.models.all_models import MedicalRecordAccessRequest
        with get_master_db_context() as mdb:
            req = mdb.query(MedicalRecordAccessRequest).filter(
                MedicalRecordAccessRequest.id == request_id,
                MedicalRecordAccessRequest.holding_tenant_id == holding_tenant_id,
                MedicalRecordAccessRequest.is_deleted.is_(False)).first()
            if req is None:
                raise NotFoundError(message="Request not found for this hospital.")
            if req.status != MedicalAccessStatus.PENDING:
                raise BadRequestError(message=f"This request is already {req.status.value.lower()}.")
            if req.hospital_decision != MedicalAccessDecision.PENDING:
                raise BadRequestError(message="Your hospital has already responded to this request.")

            if approve:
                req.hospital_decision = MedicalAccessDecision.APPROVED
                req.hospital_decided_at = _now()
                req.hospital_decided_by_user_id = user_id
                self._audit(mdb, req, MedicalAccessAuditEvent.HOSPITAL_APPROVED, MedicalAccessActorType.HOSPITAL,
                            actor_id=user_id, actor_display=actor_display, ip=ip)
            else:
                req.hospital_decision = MedicalAccessDecision.DECLINED
                req.hospital_decided_at = _now()
                req.hospital_decided_by_user_id = user_id
                req.status = MedicalAccessStatus.DECLINED
                req.decline_reason = (reason or "Declined by hospital.")
                self._audit(mdb, req, MedicalAccessAuditEvent.HOSPITAL_DECLINED, MedicalAccessActorType.HOSPITAL,
                            actor_id=user_id, actor_display=actor_display, detail=reason, ip=ip)
            mdb.flush()
            self._maybe_finalize(mdb, req)
            mdb.commit()
            mdb.refresh(req)
            return _req_read(req)

    # -------------------------------------------------------------------
    # Finalize -> snapshot + one-time link + notify requester
    # -------------------------------------------------------------------
    def _all_approvals_met(self, req) -> bool:
        if req.requires_patient_approval and req.patient_decision != MedicalAccessDecision.APPROVED:
            return False
        if req.requires_hospital_approval and req.hospital_decision != MedicalAccessDecision.APPROVED:
            return False
        return True

    def _maybe_finalize(self, mdb, req) -> None:
        if req.status != MedicalAccessStatus.PENDING or not self._all_approvals_met(req):
            return

        # Build the frozen, read-only snapshot from the holding tenant DB.
        payload = None
        try:
            with get_tenant_db_context(req.holding_tenant_id) as tdb:
                if req.scope == "BASELINE_DIAGNOSTICS":
                    payload = build_patient_baseline_diagnostics(tdb, req.patient_global_id)
                else:
                    payload = build_patient_medical_history(tdb, req.patient_global_id)
        except Exception:
            payload = None

        full_token, prefix, token_hash = generate_prefixed_key(_ACCESS_TOKEN_SCHEME)
        now = _now()
        req.access_token_prefix = prefix
        req.access_token_hash = token_hash
        req.link_generated_at = now
        req.link_expires_at = now + timedelta(hours=int(req.link_expiry_hours or _default_expiry_hours()))
        req.payload_json = payload
        req.status = MedicalAccessStatus.APPROVED
        self._audit(mdb, req, MedicalAccessAuditEvent.LINK_GENERATED, MedicalAccessActorType.SYSTEM,
                    detail=f"One-time link generated; expires {req.link_expires_at.isoformat()}.")

        base = _frontend_base()
        access_url = f"{base}/medical-access/view/{full_token}" if base else None
        self._email(
            to=req.requester_contact_email,
            subject="Your medical records access request was approved",
            title="Access approved — one-time secure link",
            intro=(f"Your request ({req.request_no}) for {req.patient_display_name}'s "
                   f"{req.scope.replace('_', ' ').lower()} was approved. Use the secure, read-only "
                   f"link below. It can be opened once and expires in {req.link_expiry_hours} hours."),
            details=[("Request", req.request_no), ("Patient", req.patient_display_name),
                     ("Expires in (hours)", str(req.link_expiry_hours))],
            cta_label="Open records (one-time)" if access_url else None,
            cta_url=access_url,
            footer="For security this link works only once and then becomes invalid.",
        )

    # -------------------------------------------------------------------
    # One-time link consumption
    # -------------------------------------------------------------------
    def consume_link(self, *, token: str, ip: Optional[str] = None) -> dict:
        from app.models.all_models import MedicalRecordAccessRequest
        with get_master_db_context() as mdb:
            req = self._load_by_prefix(mdb, access_token=token)
            if req is None or not req.access_token_hash or not verify_api_key(token, req.access_token_hash):
                raise NotFoundError(message="Invalid or unknown access link.")

            # Expiry check (lazily flip status).
            if req.link_expires_at and _now() > _as_utc(req.link_expires_at):
                if req.status not in (MedicalAccessStatus.EXPIRED, MedicalAccessStatus.FULFILLED):
                    req.status = MedicalAccessStatus.EXPIRED
                    self._audit(mdb, req, MedicalAccessAuditEvent.LINK_EXPIRED, MedicalAccessActorType.SYSTEM,
                                detail="Link accessed after expiry.", ip=ip)
                    mdb.commit()
                raise ForbiddenError(message="This access link has expired.")

            if req.link_used_at is not None or req.status == MedicalAccessStatus.FULFILLED:
                raise ForbiddenError(message="This access link has already been used.")

            if req.status != MedicalAccessStatus.APPROVED:
                raise ForbiddenError(message="This link is not active.")

            # Consume (one-time).
            req.link_used_at = _now()
            req.status = MedicalAccessStatus.FULFILLED
            self._audit(mdb, req, MedicalAccessAuditEvent.LINK_ACCESSED, MedicalAccessActorType.REQUESTER,
                        actor_display=req.requester_name, ip=ip)
            self._audit(mdb, req, MedicalAccessAuditEvent.RECORD_ACCESSED, MedicalAccessActorType.REQUESTER,
                        actor_display=req.requester_name,
                        detail=f"Read-only {req.scope} served for {req.patient_display_name}.", ip=ip)
            self._audit(mdb, req, MedicalAccessAuditEvent.REQUEST_FULFILLED, MedicalAccessActorType.SYSTEM)
            record = req.payload_json
            meta = {
                "request_no": req.request_no, "patient": req.patient_display_name,
                "scope": req.scope, "served_at": _now().isoformat(),
            }
            mdb.commit()
        return {"meta": meta, "record": record}

    # -------------------------------------------------------------------
    # Listing / detail / cancel / audit
    # -------------------------------------------------------------------
    def list_for_hospital(self, *, tenant_id: int, direction: str = "incoming",
                          status: Optional[str] = None) -> list[dict]:
        from app.models.all_models import MedicalRecordAccessRequest as M
        with get_master_db_context() as mdb:
            q = mdb.query(M).filter(M.is_deleted.is_(False))
            if direction == "outgoing":
                q = q.filter(M.requesting_tenant_id == tenant_id)
            else:
                q = q.filter(M.holding_tenant_id == tenant_id)
            if status:
                try:
                    q = q.filter(M.status == MedicalAccessStatus(status.strip().upper()))
                except Exception:
                    pass
            return [_req_read(r) for r in q.order_by(M.id.desc()).all()]

    def list_for_patient(self, *, holding_tenant_id: int, patient_global_id: str) -> list[dict]:
        from app.models.all_models import MedicalRecordAccessRequest as M
        with get_master_db_context() as mdb:
            rows = mdb.query(M).filter(
                M.holding_tenant_id == holding_tenant_id,
                M.patient_global_id == patient_global_id,
                M.is_deleted.is_(False)).order_by(M.id.desc()).all()
            return [_req_read(r) for r in rows]

    def get_detail(self, *, request_id: int, tenant_id: Optional[int] = None) -> dict:
        from app.models.all_models import MedicalRecordAccessRequest as M
        with get_master_db_context() as mdb:
            req = mdb.query(M).filter(M.id == request_id, M.is_deleted.is_(False)).first()
            if req is None:
                raise NotFoundError(message="Request not found.")
            if tenant_id is not None and tenant_id not in (req.requesting_tenant_id, req.holding_tenant_id):
                raise ForbiddenError(message="Not authorized for this request.")
            return _req_read(req)

    def get_audit(self, *, request_id: int, tenant_id: Optional[int] = None) -> list[dict]:
        from app.models.all_models import MedicalRecordAccessAudit as A, MedicalRecordAccessRequest as M
        with get_master_db_context() as mdb:
            req = mdb.query(M).filter(M.id == request_id, M.is_deleted.is_(False)).first()
            if req is None:
                raise NotFoundError(message="Request not found.")
            if tenant_id is not None and tenant_id not in (req.requesting_tenant_id, req.holding_tenant_id):
                raise ForbiddenError(message="Not authorized for this request.")
            rows = mdb.query(A).filter(A.request_id == request_id).order_by(A.id.asc()).all()
            return [_audit_read(a) for a in rows]

    # -------------------------------------------------------------------
    # Developer poll + one-time retrieval (programmatic requester)
    # -------------------------------------------------------------------
    def retrieve_for_hospital(self, *, requesting_tenant_id: int, request_id: int,
                              actor_id: Optional[int] = None, actor_display: Optional[str] = None,
                              ip: Optional[str] = None) -> dict:
        """In-app one-time retrieval for the requesting hospital (owner of the
        request). Serves the read-only snapshot once, then FULFILLED."""
        from app.models.all_models import MedicalRecordAccessRequest as M
        with get_master_db_context() as mdb:
            req = mdb.query(M).filter(
                M.id == request_id,
                M.requesting_tenant_id == requesting_tenant_id,
                M.is_deleted.is_(False)).first()
            if req is None:
                raise NotFoundError(message="Request not found for this hospital.")
            if req.status == MedicalAccessStatus.FULFILLED or req.link_used_at is not None:
                raise ForbiddenError(message="These records have already been retrieved (one-time access).")
            if req.status == MedicalAccessStatus.EXPIRED:
                raise ForbiddenError(message="This access has expired.")
            if req.status != MedicalAccessStatus.APPROVED:
                raise BadRequestError(message="This request is not approved yet.")
            if req.link_expires_at and _now() > _as_utc(req.link_expires_at):
                req.status = MedicalAccessStatus.EXPIRED
                self._audit(mdb, req, MedicalAccessAuditEvent.LINK_EXPIRED, MedicalAccessActorType.SYSTEM,
                            detail="Access expired before retrieval.", ip=ip)
                mdb.commit()
                raise ForbiddenError(message="This access has expired.")
            req.link_used_at = _now()
            req.status = MedicalAccessStatus.FULFILLED
            self._audit(mdb, req, MedicalAccessAuditEvent.LINK_ACCESSED, MedicalAccessActorType.REQUESTER,
                        actor_id=actor_id, actor_display=actor_display, ip=ip)
            self._audit(mdb, req, MedicalAccessAuditEvent.RECORD_ACCESSED, MedicalAccessActorType.REQUESTER,
                        actor_id=actor_id, actor_display=actor_display,
                        detail=f"Read-only {req.scope} served for {req.patient_display_name}.", ip=ip)
            self._audit(mdb, req, MedicalAccessAuditEvent.REQUEST_FULFILLED, MedicalAccessActorType.SYSTEM)
            record = req.payload_json
            meta = {"request_no": req.request_no, "patient": req.patient_display_name,
                    "scope": req.scope, "served_at": _now().isoformat()}
            mdb.commit()
        return {"meta": meta, "record": record}

    def developer_retrieve(self, *, app_id: int, request_no: str, ip: Optional[str] = None) -> dict:
        """Poll a developer-initiated request. Pending/declined/expired return
        status only; on first poll after approval the one-time payload is served
        and the request becomes FULFILLED."""
        from app.models.all_models import MedicalRecordAccessRequest as M
        with get_master_db_context() as mdb:
            req = mdb.query(M).filter(
                M.request_no == request_no,
                M.requesting_developer_app_id == app_id,
                M.is_deleted.is_(False)).first()
            if req is None:
                raise NotFoundError(message="Request not found for this app.")

            status = req.status
            if status == MedicalAccessStatus.APPROVED:
                if req.link_expires_at and _now() > _as_utc(req.link_expires_at):
                    req.status = MedicalAccessStatus.EXPIRED
                    self._audit(mdb, req, MedicalAccessAuditEvent.LINK_EXPIRED, MedicalAccessActorType.SYSTEM,
                                detail="Access expired before retrieval.", ip=ip)
                    mdb.commit()
                    return {"request_no": request_no, "status": "EXPIRED", "record": None}
                # One-time consume.
                req.link_used_at = _now()
                req.status = MedicalAccessStatus.FULFILLED
                self._audit(mdb, req, MedicalAccessAuditEvent.LINK_ACCESSED, MedicalAccessActorType.DEVELOPER,
                            actor_id=app_id, actor_display=req.requester_name, ip=ip)
                self._audit(mdb, req, MedicalAccessAuditEvent.RECORD_ACCESSED, MedicalAccessActorType.DEVELOPER,
                            actor_id=app_id, actor_display=req.requester_name,
                            detail=f"Read-only {req.scope} served.", ip=ip)
                self._audit(mdb, req, MedicalAccessAuditEvent.REQUEST_FULFILLED, MedicalAccessActorType.SYSTEM)
                record = req.payload_json
                mdb.commit()
                return {"request_no": request_no, "status": "FULFILLED", "record": record}

            return {"request_no": request_no,
                    "status": status.value if hasattr(status, "value") else status,
                    "record": None,
                    "patient_decision": req.patient_decision.value if hasattr(req.patient_decision, "value") else req.patient_decision,
                    "hospital_decision": req.hospital_decision.value if hasattr(req.hospital_decision, "value") else req.hospital_decision}

    def cancel(self, *, request_id: int, requesting_tenant_id: int, user_id: Optional[int] = None) -> dict:
        from app.models.all_models import MedicalRecordAccessRequest as M
        with get_master_db_context() as mdb:
            req = mdb.query(M).filter(
                M.id == request_id, M.requesting_tenant_id == requesting_tenant_id,
                M.is_deleted.is_(False)).first()
            if req is None:
                raise NotFoundError(message="Request not found.")
            if req.status not in (MedicalAccessStatus.PENDING, MedicalAccessStatus.APPROVED):
                raise BadRequestError(message=f"Cannot cancel a {req.status.value.lower()} request.")
            req.status = MedicalAccessStatus.CANCELLED
            # Invalidate any issued link.
            req.access_token_hash = None
            self._audit(mdb, req, MedicalAccessAuditEvent.REQUEST_CANCELLED, MedicalAccessActorType.REQUESTER,
                        actor_id=user_id)
            mdb.commit()
            mdb.refresh(req)
            return _req_read(req)
