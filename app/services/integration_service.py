# app/services/integration_service.py
from __future__ import annotations

"""
Two-way integration with third-party Hospital Management applications.

- Management: register/list/rotate/revoke partner connections (master DB).
- Inbound (partner -> us): patient search, full-record export, patient upsert,
  and a generic data-push ingestion sink (operate on the tenant DB).
- Outbound (us -> partner): call the partner's registered endpoint with the
  stored credentials and return their response.
"""

import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.api_key import generate_api_key
from app.core.cryptography import decrypt_string, encrypt_string
from app.core.database import get_master_db_context
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import ExternalDataRecord, IntegrationPartner, Patient
from app.schemas.integration_schemas import DataPushSchema, PatientUpsertSchema
from app.utils.patient_export import build_patient_full_export


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm_scopes(scopes: Optional[list[str]]) -> str:
    allowed = {"READ", "WRITE"}
    vals = [s.strip().upper() for s in (scopes or []) if s and s.strip().upper() in allowed]
    return ",".join(dict.fromkeys(vals)) or "READ"


def _partner_read(p: IntegrationPartner) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "is_active": bool(p.is_active),
        "key_prefix": p.key_prefix,
        "scopes": p.scopes,
        "expires_at": p.expires_at,
        "last_used_at": p.last_used_at,
        "base_url": p.base_url,
        "auth_header": p.auth_header,
        "has_outbound_secret": bool(p.auth_secret_encrypted),
        "created_at": getattr(p, "created_at", None),
    }


class IntegrationService:
    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db  # tenant session (inbound reads/writes)

    # ------------------------------------------------------------------
    # Partner management (master DB)
    # ------------------------------------------------------------------

    def create_partner(self, *, tenant_id: int, name: str, description: Optional[str],
                       scopes: Optional[list[str]], expiry_days: Optional[int],
                       base_url: Optional[str], auth_header: Optional[str],
                       auth_secret: Optional[str], created_by_user_id: Optional[int]) -> tuple[dict, str]:
        full_key, prefix, key_hash = generate_api_key()
        with get_master_db_context() as mdb:
            partner = IntegrationPartner(
                tenant_id=tenant_id,
                name=name.strip(),
                description=(description or None),
                is_active=True,
                key_prefix=prefix,
                key_hash=key_hash,
                scopes=_norm_scopes(scopes),
                expires_at=(_now() + timedelta(days=expiry_days)) if expiry_days else None,
                base_url=(base_url or None),
                auth_header=(auth_header or "X-API-Key"),
                auth_secret_encrypted=encrypt_string(auth_secret) if auth_secret else None,
                created_by_user_id=created_by_user_id,
            )
            mdb.add(partner)
            mdb.commit()
            mdb.refresh(partner)
            return _partner_read(partner), full_key

    def list_partners(self, *, tenant_id: int) -> list[dict]:
        with get_master_db_context() as mdb:
            rows = (
                mdb.query(IntegrationPartner)
                .filter(IntegrationPartner.tenant_id == tenant_id, IntegrationPartner.is_deleted.is_(False))
                .order_by(IntegrationPartner.id.desc())
                .all()
            )
            return [_partner_read(p) for p in rows]

    def _get_owned(self, mdb, partner_id: int, tenant_id: int) -> IntegrationPartner:
        p = (
            mdb.query(IntegrationPartner)
            .filter(IntegrationPartner.id == partner_id,
                    IntegrationPartner.tenant_id == tenant_id,
                    IntegrationPartner.is_deleted.is_(False))
            .first()
        )
        if p is None:
            raise NotFoundError(message="Integration partner not found.")
        return p

    def update_partner(self, *, partner_id: int, tenant_id: int, changes: dict) -> dict:
        with get_master_db_context() as mdb:
            p = self._get_owned(mdb, partner_id, tenant_id)
            if "name" in changes and changes["name"] is not None:
                p.name = changes["name"].strip()
            if "description" in changes:
                p.description = changes["description"] or None
            if changes.get("is_active") is not None:
                p.is_active = bool(changes["is_active"])
            if changes.get("scopes") is not None:
                p.scopes = _norm_scopes(changes["scopes"])
            if changes.get("expiry_days") is not None:
                p.expires_at = _now() + timedelta(days=int(changes["expiry_days"]))
            if "base_url" in changes:
                p.base_url = changes["base_url"] or None
            if changes.get("auth_header"):
                p.auth_header = changes["auth_header"]
            if changes.get("auth_secret") is not None:
                p.auth_secret_encrypted = encrypt_string(changes["auth_secret"]) if changes["auth_secret"] else None
            mdb.add(p)
            mdb.commit()
            mdb.refresh(p)
            return _partner_read(p)

    def rotate_key(self, *, partner_id: int, tenant_id: int) -> tuple[dict, str]:
        full_key, prefix, key_hash = generate_api_key()
        with get_master_db_context() as mdb:
            p = self._get_owned(mdb, partner_id, tenant_id)
            p.key_prefix = prefix
            p.key_hash = key_hash
            mdb.add(p)
            mdb.commit()
            mdb.refresh(p)
            return _partner_read(p), full_key

    def revoke_partner(self, *, partner_id: int, tenant_id: int) -> dict:
        with get_master_db_context() as mdb:
            p = self._get_owned(mdb, partner_id, tenant_id)
            p.is_active = False
            mdb.add(p)
            mdb.commit()
            mdb.refresh(p)
            return _partner_read(p)

    # ------------------------------------------------------------------
    # Outbound (CarePoint -> partner)
    # ------------------------------------------------------------------

    def outbound_request(self, *, partner_id: int, tenant_id: int, path: str,
                        method: str = "GET", params: Optional[dict] = None,
                        payload: Optional[dict] = None) -> dict:
        with get_master_db_context() as mdb:
            p = self._get_owned(mdb, partner_id, tenant_id)
            if not p.base_url:
                raise BadRequestError(message="This partner has no outbound base URL configured.")
            base = p.base_url.rstrip("/")
            header_name = p.auth_header or "X-API-Key"
            secret = decrypt_string(p.auth_secret_encrypted) if p.auth_secret_encrypted else None

        url = f"{base}/{path.lstrip('/')}"
        headers = {"Accept": "application/json"}
        if secret:
            headers[header_name] = secret
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.request(method.upper(), url, params=params or None,
                                      json=payload if payload else None, headers=headers)
            try:
                body: Any = resp.json()
            except Exception:
                body = resp.text
            return {"status_code": resp.status_code, "ok": resp.is_success, "data": body}
        except httpx.HTTPError as exc:
            raise BadRequestError(message=f"Could not reach the partner endpoint: {exc}")

    # ------------------------------------------------------------------
    # Inbound (partner -> CarePoint) — operate on the tenant DB (self.db)
    # ------------------------------------------------------------------

    def search_patients(self, *, query: Optional[str], limit: int = 25) -> list[dict]:
        from sqlalchemy import func, or_

        q = self.db.query(Patient).filter(Patient.is_deleted.is_(False))
        if query and query.strip():
            term = f"%{query.strip().lower()}%"
            q = q.filter(or_(
                func.lower(Patient.first_name).like(term),
                func.lower(Patient.last_name).like(term),
                func.lower(Patient.global_patient_id).like(term),
                func.lower(Patient.hospital_number).like(term),
            ))
        rows = q.order_by(Patient.id.desc()).limit(min(limit, 100)).all()
        return [self._patient_summary(p) for p in rows]

    def patient_record(self, *, global_patient_id: str) -> Optional[dict]:
        return build_patient_full_export(self.db, global_patient_id)

    def _patient_summary(self, p: Patient) -> dict:
        return {
            "global_patient_id": p.global_patient_id,
            "hospital_number": getattr(p, "hospital_number", None),
            "first_name": p.first_name,
            "last_name": p.last_name,
            "date_of_birth": p.date_of_birth.isoformat() if getattr(p, "date_of_birth", None) else None,
            "gender": getattr(getattr(p, "gender", None), "value", getattr(p, "gender", None)),
            "phone_number": getattr(p, "phone_number", None),
        }

    def upsert_patient(self, *, data: PatientUpsertSchema) -> dict:
        existing = None
        if data.global_patient_id:
            existing = self.db.query(Patient).filter(Patient.global_patient_id == data.global_patient_id).first()
        if existing is None and data.hospital_number:
            existing = self.db.query(Patient).filter(Patient.hospital_number == data.hospital_number).first()

        created = False
        if existing is None:
            existing = Patient(
                global_patient_id=data.global_patient_id or f"GPID-{_uuid.uuid4().hex[:12].upper()}",
                hospital_number=data.hospital_number or f"EXT-{_uuid.uuid4().hex[:10].upper()}",
                first_name=data.first_name.strip(),
                last_name=data.last_name.strip(),
            )
            created = True
        else:
            existing.first_name = data.first_name.strip()
            existing.last_name = data.last_name.strip()

        # Optional scalar fields (only set attributes that exist on the model)
        for field in ("phone_number", "email", "address"):
            val = getattr(data, field, None)
            if val is not None and hasattr(existing, field):
                setattr(existing, field, val)
        if data.date_of_birth:
            try:
                from datetime import date as _date
                existing.date_of_birth = _date.fromisoformat(data.date_of_birth)
            except Exception:
                pass
        if data.gender and hasattr(existing, "gender"):
            try:
                from app.core.enums import Gender
                existing.gender = Gender(data.gender.strip().upper())
            except Exception:
                pass
        if data.extra:
            for k, v in data.extra.items():
                if hasattr(existing, k) and k not in {"id", "global_patient_id", "hospital_number"}:
                    try:
                        setattr(existing, k, v)
                    except Exception:
                        continue

        try:
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
        except Exception as exc:
            self.db.rollback()
            raise BadRequestError(message=f"Could not save patient: {exc}")

        summary = self._patient_summary(existing)
        summary["created"] = created
        return summary

    def ingest_record(self, *, partner_id: Optional[int], partner_name: Optional[str],
                     data: DataPushSchema) -> dict:
        rec = ExternalDataRecord(
            source_partner_id=partner_id,
            source_partner_name=partner_name,
            resource_type=data.resource_type.strip(),
            external_id=data.external_id,
            patient_global_id=data.patient_global_id,
            payload_json=data.payload or {},
            received_at=_now(),
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return {"id": rec.id, "resource_type": rec.resource_type, "received": True}
