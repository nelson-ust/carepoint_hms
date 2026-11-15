# app/services/data_protection_service.py
from __future__ import annotations

"""Service layer for the Data Protection / NDPA module."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.enums import (
    ConsentStatus,
    ConsentType,
    DataBreachSeverity,
    DataBreachStatus,
    DataSubjectRequestStatus,
    DataSubjectRequestType,
    LawfulBasis,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    ConsentRecord,
    DataBreach,
    DataProtectionSetting,
    DataSubjectRequest,
    Patient,
    ProcessingActivity,
    Visit,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DataProtectionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ settings
    def _settings_row(self) -> DataProtectionSetting:
        row = self.db.query(DataProtectionSetting).filter(DataProtectionSetting.is_deleted.is_(False)).first()
        if not row:
            row = DataProtectionSetting(breach_notify_hours=72, dsr_response_days=30, retention_months=84)
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def get_settings(self) -> dict:
        r = self._settings_row()
        return {
            "id": r.id, "dpo_name": r.dpo_name, "dpo_email": r.dpo_email, "dpo_phone": r.dpo_phone,
            "privacy_policy_version": r.privacy_policy_version, "privacy_policy_url": r.privacy_policy_url,
            "privacy_policy_text": r.privacy_policy_text, "retention_months": r.retention_months,
            "breach_notify_hours": r.breach_notify_hours, "dsr_response_days": r.dsr_response_days,
            "ndpc_registered": bool(r.ndpc_registered), "updated_at": r.updated_at,
        }

    def update_settings(self, payload) -> dict:
        r = self._settings_row()
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(r, k, v)
        self.db.commit()
        return self.get_settings()

    # ------------------------------------------------------------------ consent
    def consent_dict(self, c: ConsentRecord) -> dict:
        return {
            "id": c.id, "patient_id": c.patient_id, "subject_name": c.subject_name,
            "consent_type": str(c.consent_type), "status": str(c.status), "lawful_basis": str(c.lawful_basis),
            "purpose": c.purpose, "policy_version": c.policy_version, "method": c.method,
            "granted_at": c.granted_at, "withdrawn_at": c.withdrawn_at, "notes": c.notes, "created_at": c.created_at,
        }

    def list_consents(self, *, patient_id=None, consent_type=None, status=None, search=None, skip=0, limit=100):
        q = self.db.query(ConsentRecord).filter(ConsentRecord.is_deleted.is_(False))
        if patient_id:
            q = q.filter(ConsentRecord.patient_id == patient_id)
        if consent_type:
            q = q.filter(ConsentRecord.consent_type == ConsentType(consent_type.strip().upper()))
        if status:
            q = q.filter(ConsentRecord.status == ConsentStatus(status.strip().upper()))
        if search:
            q = q.filter(ConsentRecord.subject_name.ilike(f"%{search.strip()}%"))
        total = q.count()
        items = q.order_by(ConsentRecord.granted_at.desc()).offset(skip).limit(limit).all()
        return items, total

    def record_consent(self, payload) -> ConsentRecord:
        pol = payload.policy_version or self._settings_row().privacy_policy_version
        c = ConsentRecord(
            patient_id=payload.patient_id, subject_name=payload.subject_name,
            consent_type=ConsentType(payload.consent_type.strip().upper()),
            status=ConsentStatus.GRANTED, lawful_basis=LawfulBasis(payload.lawful_basis.strip().upper()),
            purpose=payload.purpose, policy_version=pol, method=payload.method, granted_at=_now(), notes=payload.notes,
        )
        self.db.add(c); self.db.commit(); self.db.refresh(c); return c

    def withdraw_consent(self, consent_id) -> ConsentRecord:
        c = self.db.query(ConsentRecord).filter(ConsentRecord.id == consent_id, ConsentRecord.is_deleted.is_(False)).first()
        if not c:
            raise NotFoundError(message="Consent record not found.", detail={"consent_id": consent_id})
        c.status = ConsentStatus.WITHDRAWN
        c.withdrawn_at = _now()
        self.db.commit(); self.db.refresh(c); return c

    # ------------------------------------------------------------------ DSR
    def dsr_dict(self, r: DataSubjectRequest) -> dict:
        overdue = bool(
            r.due_at and r.due_at < _now()
            and r.status in (DataSubjectRequestStatus.RECEIVED, DataSubjectRequestStatus.IN_PROGRESS)
        )
        return {
            "id": r.id, "patient_id": r.patient_id, "subject_name": r.subject_name,
            "subject_contact": r.subject_contact, "request_type": str(r.request_type), "status": str(r.status),
            "received_at": r.received_at, "due_at": r.due_at, "details": r.details,
            "resolution_notes": r.resolution_notes, "completed_at": r.completed_at,
            "overdue": overdue, "created_at": r.created_at,
        }

    def list_dsr(self, *, status=None, request_type=None, skip=0, limit=100):
        q = self.db.query(DataSubjectRequest).filter(DataSubjectRequest.is_deleted.is_(False))
        if status:
            q = q.filter(DataSubjectRequest.status == DataSubjectRequestStatus(status.strip().upper()))
        if request_type:
            q = q.filter(DataSubjectRequest.request_type == DataSubjectRequestType(request_type.strip().upper()))
        total = q.count()
        items = q.order_by(DataSubjectRequest.received_at.desc()).offset(skip).limit(limit).all()
        return items, total

    def create_dsr(self, payload) -> DataSubjectRequest:
        days = self._settings_row().dsr_response_days or 30
        now = _now()
        r = DataSubjectRequest(
            patient_id=payload.patient_id, subject_name=payload.subject_name, subject_contact=payload.subject_contact,
            request_type=DataSubjectRequestType(payload.request_type.strip().upper()),
            status=DataSubjectRequestStatus.RECEIVED, received_at=now, due_at=now + timedelta(days=days),
            details=payload.details,
        )
        self.db.add(r); self.db.commit(); self.db.refresh(r); return r

    def get_dsr(self, dsr_id) -> DataSubjectRequest:
        r = self.db.query(DataSubjectRequest).filter(DataSubjectRequest.id == dsr_id, DataSubjectRequest.is_deleted.is_(False)).first()
        if not r:
            raise NotFoundError(message="Request not found.", detail={"dsr_id": dsr_id})
        return r

    def update_dsr(self, dsr_id, payload) -> DataSubjectRequest:
        r = self.get_dsr(dsr_id)
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"]:
            r.status = DataSubjectRequestStatus(data.pop("status").strip().upper())
            if r.status in (DataSubjectRequestStatus.COMPLETED, DataSubjectRequestStatus.REJECTED) and not r.completed_at:
                r.completed_at = _now()
        for k, v in data.items():
            setattr(r, k, v)
        self.db.commit(); self.db.refresh(r); return r

    def export_subject_data(self, dsr_id) -> dict:
        """Assemble a data-subject's held personal data (ACCESS / PORTABILITY)."""
        r = self.get_dsr(dsr_id)
        if not r.patient_id:
            raise BadRequestError(message="This request is not linked to a patient record to export.", detail={"dsr_id": dsr_id})
        p = self.db.query(Patient).filter(Patient.id == r.patient_id).first()
        if not p:
            raise NotFoundError(message="Linked patient not found.", detail={"patient_id": r.patient_id})
        visits = self.db.query(Visit).filter(Visit.patient_id == p.id, Visit.is_deleted.is_(False)).all()
        consents = self.db.query(ConsentRecord).filter(ConsentRecord.patient_id == p.id, ConsentRecord.is_deleted.is_(False)).all()
        return {
            "generated_at": _now().isoformat(),
            "request": self.dsr_dict(r),
            "patient": {
                "hospital_number": getattr(p, "hospital_number", None),
                "first_name": getattr(p, "first_name", None),
                "last_name": getattr(p, "last_name", None),
                "gender": str(getattr(p, "gender", "") or ""),
                "date_of_birth": str(getattr(p, "date_of_birth", "") or ""),
                "phone_number": getattr(p, "phone_number", None),
            },
            "visits": [
                {"visit_code": getattr(v, "visit_code", None), "visit_date": str(getattr(v, "visit_date", "") or ""),
                 "status": str(getattr(v, "status", "") or "")}
                for v in visits
            ],
            "consents": [self.consent_dict(c) for c in consents],
        }

    # ------------------------------------------------------------------ breaches
    def breach_dict(self, b: DataBreach) -> dict:
        overdue = bool(b.notify_due_at and not b.ndpc_notified and b.notify_due_at < _now())
        return {
            "id": b.id, "title": b.title, "description": b.description, "severity": str(b.severity),
            "status": str(b.status), "discovered_at": b.discovered_at, "notify_due_at": b.notify_due_at,
            "data_categories": b.data_categories, "subjects_affected": b.subjects_affected,
            "ndpc_notified": bool(b.ndpc_notified), "ndpc_notified_at": b.ndpc_notified_at,
            "subjects_notified": bool(b.subjects_notified), "remediation": b.remediation,
            "notify_overdue": overdue, "created_at": b.created_at,
        }

    def list_breaches(self, *, status=None, skip=0, limit=100):
        q = self.db.query(DataBreach).filter(DataBreach.is_deleted.is_(False))
        if status:
            q = q.filter(DataBreach.status == DataBreachStatus(status.strip().upper()))
        total = q.count()
        items = q.order_by(DataBreach.discovered_at.desc()).offset(skip).limit(limit).all()
        return items, total

    def create_breach(self, payload) -> DataBreach:
        hours = self._settings_row().breach_notify_hours or 72
        discovered = payload.discovered_at or _now()
        b = DataBreach(
            title=payload.title, description=payload.description,
            severity=DataBreachSeverity(payload.severity.strip().upper()),
            status=DataBreachStatus.OPEN, discovered_at=discovered,
            notify_due_at=discovered + timedelta(hours=hours),
            data_categories=payload.data_categories, subjects_affected=payload.subjects_affected,
        )
        self.db.add(b); self.db.commit(); self.db.refresh(b); return b

    def _get_breach(self, breach_id) -> DataBreach:
        b = self.db.query(DataBreach).filter(DataBreach.id == breach_id, DataBreach.is_deleted.is_(False)).first()
        if not b:
            raise NotFoundError(message="Breach not found.", detail={"breach_id": breach_id})
        return b

    def update_breach(self, breach_id, payload) -> DataBreach:
        b = self._get_breach(breach_id)
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"]:
            b.status = DataBreachStatus(data.pop("status").strip().upper())
        if "severity" in data and data["severity"]:
            b.severity = DataBreachSeverity(data.pop("severity").strip().upper())
        for k, v in data.items():
            setattr(b, k, v)
        self.db.commit(); self.db.refresh(b); return b

    def notify_ndpc(self, breach_id) -> DataBreach:
        b = self._get_breach(breach_id)
        b.ndpc_notified = True
        b.ndpc_notified_at = _now()
        self.db.commit(); self.db.refresh(b); return b

    # ------------------------------------------------------------------ RoPA
    def ropa_dict(self, a: ProcessingActivity) -> dict:
        return {
            "id": a.id, "name": a.name, "purpose": a.purpose, "lawful_basis": str(a.lawful_basis),
            "data_categories": a.data_categories, "data_subjects": a.data_subjects, "recipients": a.recipients,
            "retention_period": a.retention_period, "cross_border": bool(a.cross_border),
            "cross_border_detail": a.cross_border_detail, "owner": a.owner, "created_at": a.created_at,
        }

    def list_ropa(self, *, skip=0, limit=200):
        q = self.db.query(ProcessingActivity).filter(ProcessingActivity.is_deleted.is_(False))
        total = q.count()
        items = q.order_by(ProcessingActivity.name.asc()).offset(skip).limit(limit).all()
        return items, total

    def create_ropa(self, payload) -> ProcessingActivity:
        a = ProcessingActivity(
            name=payload.name, purpose=payload.purpose,
            lawful_basis=LawfulBasis(payload.lawful_basis.strip().upper()),
            data_categories=payload.data_categories, data_subjects=payload.data_subjects,
            recipients=payload.recipients, retention_period=payload.retention_period,
            cross_border=bool(payload.cross_border), cross_border_detail=payload.cross_border_detail, owner=payload.owner,
        )
        self.db.add(a); self.db.commit(); self.db.refresh(a); return a

    def update_ropa(self, ropa_id, payload) -> ProcessingActivity:
        a = self.db.query(ProcessingActivity).filter(ProcessingActivity.id == ropa_id, ProcessingActivity.is_deleted.is_(False)).first()
        if not a:
            raise NotFoundError(message="Processing activity not found.", detail={"ropa_id": ropa_id})
        data = payload.model_dump(exclude_unset=True)
        if "lawful_basis" in data and data["lawful_basis"]:
            a.lawful_basis = LawfulBasis(data.pop("lawful_basis").strip().upper())
        for k, v in data.items():
            setattr(a, k, v)
        self.db.commit(); self.db.refresh(a); return a

    def delete_ropa(self, ropa_id) -> ProcessingActivity:
        a = self.db.query(ProcessingActivity).filter(ProcessingActivity.id == ropa_id, ProcessingActivity.is_deleted.is_(False)).first()
        if not a:
            raise NotFoundError(message="Processing activity not found.", detail={"ropa_id": ropa_id})
        a.soft_delete()
        self.db.commit(); return a

    # ------------------------------------------------------------------ dashboard
    def dashboard(self) -> dict:
        now = _now()
        consents = self.db.query(ConsentRecord).filter(ConsentRecord.is_deleted.is_(False)).all()
        dsrs = self.db.query(DataSubjectRequest).filter(DataSubjectRequest.is_deleted.is_(False)).all()
        breaches = self.db.query(DataBreach).filter(DataBreach.is_deleted.is_(False)).all()
        ropa_count = self.db.query(ProcessingActivity).filter(ProcessingActivity.is_deleted.is_(False)).count()
        s = self._settings_row()

        open_dsr = [r for r in dsrs if r.status in (DataSubjectRequestStatus.RECEIVED, DataSubjectRequestStatus.IN_PROGRESS)]
        overdue_dsr = [r for r in open_dsr if r.due_at and r.due_at < now]
        open_breaches = [b for b in breaches if b.status != DataBreachStatus.RESOLVED]
        breaches_awaiting_ndpc = [b for b in breaches if not b.ndpc_notified and b.notify_due_at]
        breaches_overdue_ndpc = [b for b in breaches_awaiting_ndpc if b.notify_due_at and b.notify_due_at < now]

        return {
            "consents_active": sum(1 for c in consents if c.status == ConsentStatus.GRANTED),
            "consents_withdrawn": sum(1 for c in consents if c.status == ConsentStatus.WITHDRAWN),
            "dsr_open": len(open_dsr),
            "dsr_overdue": len(overdue_dsr),
            "dsr_total": len(dsrs),
            "breaches_open": len(open_breaches),
            "breaches_awaiting_ndpc": len(breaches_awaiting_ndpc),
            "breaches_overdue_ndpc": len(breaches_overdue_ndpc),
            "ropa_count": ropa_count,
            "dpo_set": bool(s.dpo_name and s.dpo_email),
            "privacy_policy_set": bool(s.privacy_policy_version or s.privacy_policy_url),
            "ndpc_registered": bool(s.ndpc_registered),
        }
