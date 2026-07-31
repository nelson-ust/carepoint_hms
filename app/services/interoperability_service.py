# app/services/interoperability_service.py
from __future__ import annotations

"""
Cross-tenant interoperability: request a patient's records from another hospital
and, once patient consent is confirmed and the holding hospital approves,
generate and hand over a full-record export.

All exchange rows live in the master database so both hospitals see the same
request. The actual patient data is only ever read from the holding tenant's
own database, at approval time, and only after consent + approval.
"""

import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import get_master_db_context, get_tenant_db_context
from app.core.enums import DataExchangeStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import DataExchangeRequest, Tenant
from app.utils.patient_export import build_patient_full_export
from app.utils.security_event_util import record_security_event


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _request_no() -> str:
    return f"DXR-{datetime.utcnow():%Y%m%d}-{_uuid.uuid4().hex[:8].upper()}"


class InteroperabilityService:
    def __init__(self, db: Session) -> None:
        # `db` is the caller's (current tenant) session — used only for audit.
        self.db = db

    # ------------------------------------------------------------------
    # Partner directory + cross-tenant patient lookup
    # ------------------------------------------------------------------

    def list_partner_tenants(self, *, exclude_tenant_id: Optional[int] = None) -> list[dict]:
        with get_master_db_context() as master_db:
            q = master_db.query(Tenant).filter(
                Tenant.is_active.is_(True),
                Tenant.is_provisioned.is_(True),
                Tenant.is_deleted.is_(False),
            )
            rows = q.order_by(Tenant.name.asc()).all()
            return [
                {"id": t.id, "name": t.name, "code": t.code}
                for t in rows
                if exclude_tenant_id is None or t.id != exclude_tenant_id
            ]

    def _tenant_names(self) -> dict[int, str]:
        with get_master_db_context() as master_db:
            return {t.id: t.name for t in master_db.query(Tenant).all()}

    def lookup_patient(self, *, holding_tenant_id: int, patient_global_id: str) -> dict:
        """Confirm a patient exists at the holding hospital by exact global ID and
        return minimal identifying info to help the requester confirm identity.
        The full record is only released later, after consent + approval."""
        result = {
            "found": False,
            "holding_tenant_id": holding_tenant_id,
            "patient_global_id": patient_global_id,
            "display_name": None,
            "sex": None,
            "date_of_birth": None,
        }
        try:
            with get_tenant_db_context(holding_tenant_id) as tdb:
                from app.models.all_models import Patient

                q = tdb.query(Patient).filter(Patient.global_patient_id == patient_global_id)
                if hasattr(Patient, "is_deleted"):
                    q = q.filter(Patient.is_deleted.is_(False))
                p = q.first()
                if p is not None:
                    name = f"{getattr(p, 'first_name', '') or ''} {getattr(p, 'last_name', '') or ''}".strip()
                    dob = getattr(p, "date_of_birth", None)
                    result.update({
                        "found": True,
                        "display_name": name or None,
                        "sex": _enum_val(getattr(p, "gender", None) or getattr(p, "sex", None)),
                        "date_of_birth": dob.isoformat() if dob else None,
                    })
        except Exception:
            # Unreachable tenant / no such patient — report not found.
            pass
        return result

    # ------------------------------------------------------------------
    # Data-exchange request lifecycle
    # ------------------------------------------------------------------

    def create_request(
        self,
        *,
        requesting_tenant_id: int,
        requesting_facility_id: Optional[int],
        holding_tenant_id: int,
        patient_global_id: str,
        patient_display_name: Optional[str],
        purpose: str,
        scope: str = "FULL_RECORD",
        requested_by_user_id: Optional[int] = None,
    ) -> dict:
        if holding_tenant_id == requesting_tenant_id:
            raise BadRequestError(message="Holding hospital must be different from the requesting hospital.")

        with get_master_db_context() as master_db:
            holding = master_db.query(Tenant).filter(Tenant.id == holding_tenant_id).first()
            if holding is None:
                raise NotFoundError(message="Holding hospital not found.")
            req = DataExchangeRequest(
                request_no=_request_no(),
                requesting_tenant_id=requesting_tenant_id,
                requesting_facility_id=requesting_facility_id,
                holding_tenant_id=holding_tenant_id,
                patient_global_id=patient_global_id.strip(),
                patient_display_name=patient_display_name,
                purpose=purpose.strip(),
                scope=scope or "FULL_RECORD",
                status=DataExchangeStatus.PENDING,
                requested_by_user_id=requested_by_user_id,
                requested_at=_utcnow(),
            )
            master_db.add(req)
            master_db.commit()
            master_db.refresh(req)
            out = self._read(req, master_db)

        record_security_event(
            self.db, user_id=requested_by_user_id,
            event_type="DATA_EXCHANGE_REQUEST_CREATED", severity="INFO",
            event_detail=f"Data request {out['request_no']} to tenant {holding_tenant_id} for patient {patient_global_id}.",
            event_metadata={"request_id": out["id"], "holding_tenant_id": holding_tenant_id},
        )
        return out

    def approve_request(
        self,
        *,
        request_id: int,
        holding_tenant_id: int,
        approver_user_id: Optional[int],
        consent_confirmed: bool,
        consent_reference: str,
        access_expiry_days: int = 30,
    ) -> dict:
        if not consent_confirmed:
            raise BadRequestError(message="Patient consent must be confirmed before approving a data share.")
        if not (consent_reference or "").strip():
            raise BadRequestError(message="A patient consent reference is required.")

        with get_master_db_context() as master_db:
            req = master_db.query(DataExchangeRequest).filter(DataExchangeRequest.id == request_id).first()
            if req is None:
                raise NotFoundError(message="Data request not found.")
            if req.holding_tenant_id != holding_tenant_id:
                raise BadRequestError(message="Only the holding hospital can approve this request.")
            if req.status != DataExchangeStatus.PENDING:
                raise BadRequestError(message=f"Request is already {req.status}.")

            # Generate the export from the holding tenant's OWN database.
            with get_tenant_db_context(holding_tenant_id) as tdb:
                export = build_patient_full_export(tdb, req.patient_global_id)
            if export is None:
                raise NotFoundError(message="Patient not found in the holding hospital's records.")

            req.status = DataExchangeStatus.APPROVED
            req.consent_confirmed = True
            req.consent_reference = consent_reference.strip()
            req.approved_by_user_id = approver_user_id
            req.approved_at = _utcnow()
            req.payload_json = export
            req.payload_generated_at = _utcnow()
            req.expires_at = _utcnow() + timedelta(days=access_expiry_days)
            master_db.add(req)
            master_db.commit()
            master_db.refresh(req)
            out = self._read(req, master_db)

        record_security_event(
            self.db, user_id=approver_user_id,
            event_type="DATA_EXCHANGE_REQUEST_APPROVED", severity="INFO",
            event_detail=f"Data request {out['request_no']} approved; full record shared (consent {consent_reference}).",
            event_metadata={"request_id": request_id, "consent_reference": consent_reference},
        )
        return out

    def deny_request(self, *, request_id: int, holding_tenant_id: int, reason: str,
                     actor_user_id: Optional[int] = None) -> dict:
        with get_master_db_context() as master_db:
            req = master_db.query(DataExchangeRequest).filter(DataExchangeRequest.id == request_id).first()
            if req is None:
                raise NotFoundError(message="Data request not found.")
            if req.holding_tenant_id != holding_tenant_id:
                raise BadRequestError(message="Only the holding hospital can deny this request.")
            if req.status != DataExchangeStatus.PENDING:
                raise BadRequestError(message=f"Request is already {req.status}.")
            req.status = DataExchangeStatus.DENIED
            req.denied_reason = (reason or "").strip() or "Denied."
            master_db.add(req)
            master_db.commit()
            master_db.refresh(req)
            out = self._read(req, master_db)
        record_security_event(
            self.db, user_id=actor_user_id,
            event_type="DATA_EXCHANGE_REQUEST_DENIED", severity="INFO",
            event_detail=f"Data request {out['request_no']} denied.",
            event_metadata={"request_id": request_id},
        )
        return out

    def cancel_request(self, *, request_id: int, requesting_tenant_id: int,
                       actor_user_id: Optional[int] = None) -> dict:
        with get_master_db_context() as master_db:
            req = master_db.query(DataExchangeRequest).filter(DataExchangeRequest.id == request_id).first()
            if req is None:
                raise NotFoundError(message="Data request not found.")
            if req.requesting_tenant_id != requesting_tenant_id:
                raise BadRequestError(message="Only the requesting hospital can cancel this request.")
            if req.status not in {DataExchangeStatus.PENDING, DataExchangeStatus.APPROVED}:
                raise BadRequestError(message=f"Request is already {req.status}.")
            req.status = DataExchangeStatus.CANCELLED
            master_db.add(req)
            master_db.commit()
            master_db.refresh(req)
            return self._read(req, master_db)

    def retrieve_payload(self, *, request_id: int, requesting_tenant_id: int,
                         actor_user_id: Optional[int] = None) -> dict:
        with get_master_db_context() as master_db:
            req = master_db.query(DataExchangeRequest).filter(DataExchangeRequest.id == request_id).first()
            if req is None:
                raise NotFoundError(message="Data request not found.")
            if req.requesting_tenant_id != requesting_tenant_id:
                raise BadRequestError(message="Only the requesting hospital can retrieve this record.")
            if req.status not in {DataExchangeStatus.APPROVED, DataExchangeStatus.FULFILLED}:
                raise BadRequestError(message="This request has not been approved.")
            if req.expires_at is not None and _utcnow() > _as_utc(req.expires_at):
                req.status = DataExchangeStatus.EXPIRED
                master_db.add(req)
                master_db.commit()
                raise BadRequestError(message="The shared record has expired. Raise a new request.")
            payload = req.payload_json
            if req.status == DataExchangeStatus.APPROVED:
                req.status = DataExchangeStatus.FULFILLED
                req.retrieved_at = _utcnow()
                master_db.add(req)
                master_db.commit()
            out = {"id": req.id, "request_no": req.request_no, "status": str(_enum_val(req.status)),
                   "patient_global_id": req.patient_global_id, "payload": payload}

        record_security_event(
            self.db, user_id=actor_user_id,
            event_type="DATA_EXCHANGE_RECORD_RETRIEVED", severity="INFO",
            event_detail=f"Shared record for request {out['request_no']} retrieved.",
            event_metadata={"request_id": request_id},
        )
        return out

    # ------------------------------------------------------------------
    # Lists
    # ------------------------------------------------------------------

    def list_incoming(self, *, holding_tenant_id: int, status: Optional[str] = None) -> list[dict]:
        return self._list(holding_col="holding_tenant_id", tenant_id=holding_tenant_id, status=status)

    def list_outgoing(self, *, requesting_tenant_id: int, status: Optional[str] = None) -> list[dict]:
        return self._list(holding_col="requesting_tenant_id", tenant_id=requesting_tenant_id, status=status)

    def _list(self, *, holding_col: str, tenant_id: int, status: Optional[str]) -> list[dict]:
        with get_master_db_context() as master_db:
            col = getattr(DataExchangeRequest, holding_col)
            q = master_db.query(DataExchangeRequest).filter(col == tenant_id)
            if status:
                try:
                    q = q.filter(DataExchangeRequest.status == DataExchangeStatus(status.strip().upper()))
                except ValueError:
                    pass
            rows = q.order_by(DataExchangeRequest.requested_at.desc()).all()
            names = {t.id: t.name for t in master_db.query(Tenant).all()}
            return [self._read(r, master_db, names=names) for r in rows]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _read(self, req: DataExchangeRequest, master_db: Session, *, names: Optional[dict] = None) -> dict:
        if names is None:
            names = {t.id: t.name for t in master_db.query(Tenant).all()}
        return {
            "id": req.id,
            "request_no": req.request_no,
            "requesting_tenant_id": req.requesting_tenant_id,
            "holding_tenant_id": req.holding_tenant_id,
            "patient_global_id": req.patient_global_id,
            "patient_display_name": req.patient_display_name,
            "purpose": req.purpose,
            "scope": req.scope,
            "status": str(_enum_val(req.status)),
            "requested_by_user_id": req.requested_by_user_id,
            "requested_at": req.requested_at,
            "consent_confirmed": bool(req.consent_confirmed),
            "consent_reference": req.consent_reference,
            "approved_by_user_id": req.approved_by_user_id,
            "approved_at": req.approved_at,
            "denied_reason": req.denied_reason,
            "payload_generated_at": req.payload_generated_at,
            "retrieved_at": req.retrieved_at,
            "expires_at": req.expires_at,
            "requesting_tenant_name": names.get(req.requesting_tenant_id),
            "holding_tenant_name": names.get(req.holding_tenant_id),
        }


def _enum_val(v):
    return v.value if hasattr(v, "value") else v


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
