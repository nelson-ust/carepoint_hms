# app/services/hmo_plan_service.py
from __future__ import annotations

"""
HMO payer/plan management: plans, benefit rules, negotiated tariffs
(with CSV import + dry-run validation), enrollee listing/dependents,
eligibility verification and policy-expiry sweeps.
"""

import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.enums import (
    BenefitLimitPeriod,
    EligibilityCheckMethod,
    EligibilityCheckResult,
    InsurancePolicyStatus,
    InsuranceProviderType,
    InsuranceVerificationStatus,
    PlanCoverageType,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    BillableService,
    Drug,
    InsuranceProvider,
    Patient,
    PatientInsurance,
)
from app.models.finance_models import (
    EligibilityCheck,
    HmoPlan,
    HmoPlanBenefit,
    HmoTariff,
)


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def _plan_read(p: HmoPlan) -> dict:
    return {
        "id": p.id,
        "insurance_provider_id": p.insurance_provider_id,
        "provider_name": p.insurance_provider.name if p.insurance_provider else None,
        "name": p.name, "code": p.code, "plan_tier": p.plan_tier,
        "coverage_type": p.coverage_type.value if hasattr(p.coverage_type, "value") else p.coverage_type,
        "default_coverage_percent": str(p.default_coverage_percent),
        "default_copay_percent": str(p.default_copay_percent),
        "default_copay_flat": str(p.default_copay_flat),
        "annual_limit": str(p.annual_limit) if p.annual_limit is not None else None,
        "per_visit_limit": str(p.per_visit_limit) if p.per_visit_limit is not None else None,
        "requires_referral": p.requires_referral,
        "is_active": p.is_active,
        "notes": p.notes,
        "benefit_count": len([b for b in (p.benefits or []) if not b.is_deleted]),
        "tariff_count": len([t for t in (p.tariffs or []) if not t.is_deleted]),
    }


def _benefit_read(b: HmoPlanBenefit) -> dict:
    return {
        "id": b.id, "hmo_plan_id": b.hmo_plan_id,
        "category": b.category,
        "billable_service_id": b.billable_service_id,
        "billable_service_name": b.billable_service.name if b.billable_service else None,
        "drug_id": b.drug_id,
        "coverage_percent": str(b.coverage_percent) if b.coverage_percent is not None else None,
        "copay_flat": str(b.copay_flat) if b.copay_flat is not None else None,
        "limit_amount": str(b.limit_amount) if b.limit_amount is not None else None,
        "limit_period": b.limit_period.value if b.limit_period is not None else None,
        "requires_preauth": b.requires_preauth,
        "is_excluded": b.is_excluded,
        "notes": b.notes,
    }


def _tariff_read(t: HmoTariff) -> dict:
    return {
        "id": t.id, "hmo_plan_id": t.hmo_plan_id,
        "billable_service_id": t.billable_service_id,
        "billable_service_name": t.billable_service.name if t.billable_service else None,
        "drug_id": t.drug_id, "service_code": t.service_code,
        "agreed_price": str(t.agreed_price),
        "effective_from": t.effective_from.isoformat() if t.effective_from else None,
        "effective_to": t.effective_to.isoformat() if t.effective_to else None,
    }


class HmoPlanService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------- providers (extension fields) ----------------

    def update_provider_profile(self, provider_id: int, **fields) -> dict:
        prov = (self.db.query(InsuranceProvider)
                .filter(InsuranceProvider.id == provider_id,
                        InsuranceProvider.is_deleted.is_(False)).first())
        if prov is None:
            raise NotFoundError("Insurance provider not found.")
        if "provider_type" in fields and fields["provider_type"]:
            try:
                fields["provider_type"] = InsuranceProviderType(fields["provider_type"]).value
            except ValueError:
                raise BadRequestError(f"Invalid provider_type '{fields['provider_type']}'.")
        allowed = {"provider_type", "nhia_accreditation_no", "bank_account_details",
                   "default_payment_terms_days", "capitation_supported",
                   "fee_for_service_supported", "contact_person", "phone_number",
                   "email", "address", "notes", "is_active"}
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(prov, k, v)
        self.db.flush()
        self.db.commit()
        return self.provider_read(prov)

    def provider_read(self, prov: InsuranceProvider) -> dict:
        plans = (self.db.query(HmoPlan)
                 .filter(HmoPlan.insurance_provider_id == prov.id,
                         HmoPlan.is_deleted.is_(False)).count())
        enrollees = (self.db.query(PatientInsurance)
                     .filter(PatientInsurance.insurance_provider_id == prov.id,
                             PatientInsurance.is_deleted.is_(False),
                             PatientInsurance.policy_status == InsurancePolicyStatus.ACTIVE)
                     .count())
        return {
            "id": prov.id, "name": prov.name, "code": prov.code,
            "provider_type": prov.provider_type,
            "nhia_accreditation_no": prov.nhia_accreditation_no,
            "contact_person": prov.contact_person, "phone_number": prov.phone_number,
            "email": prov.email, "address": prov.address, "notes": prov.notes,
            "bank_account_details": prov.bank_account_details,
            "default_payment_terms_days": prov.default_payment_terms_days,
            "capitation_supported": prov.capitation_supported,
            "fee_for_service_supported": prov.fee_for_service_supported,
            "is_active": prov.is_active,
            "plan_count": plans, "active_enrollee_count": enrollees,
        }

    def list_providers(self, *, search: Optional[str] = None) -> list[dict]:
        q = (self.db.query(InsuranceProvider)
             .filter(InsuranceProvider.is_deleted.is_(False)))
        if search:
            like = f"%{search}%"
            q = q.filter(or_(InsuranceProvider.name.ilike(like),
                             InsuranceProvider.code.ilike(like)))
        return [self.provider_read(p) for p in q.order_by(InsuranceProvider.name).all()]

    # ---------------- plans ----------------

    def _get_plan(self, plan_id: int) -> HmoPlan:
        p = (self.db.query(HmoPlan)
             .filter(HmoPlan.id == plan_id, HmoPlan.is_deleted.is_(False)).first())
        if p is None:
            raise NotFoundError("HMO plan not found.")
        return p

    def list_plans(self, *, provider_id: Optional[int] = None,
                   include_inactive: bool = False) -> list[dict]:
        q = self.db.query(HmoPlan).filter(HmoPlan.is_deleted.is_(False))
        if provider_id:
            q = q.filter(HmoPlan.insurance_provider_id == provider_id)
        if not include_inactive:
            q = q.filter(HmoPlan.is_active.is_(True))
        return [_plan_read(p) for p in q.order_by(HmoPlan.name).all()]

    def upsert_plan(self, *, plan_id: Optional[int] = None, **fields) -> dict:
        if fields.get("coverage_type"):
            try:
                fields["coverage_type"] = PlanCoverageType(fields["coverage_type"])
            except ValueError:
                raise BadRequestError(f"Invalid coverage_type '{fields['coverage_type']}'.")
        if plan_id:
            plan = self._get_plan(plan_id)
        else:
            if not fields.get("insurance_provider_id") or not fields.get("name"):
                raise BadRequestError("insurance_provider_id and name are required.")
            plan = HmoPlan(insurance_provider_id=fields["insurance_provider_id"],
                           name=fields["name"])
            self.db.add(plan)
        allowed = {"name", "code", "plan_tier", "coverage_type",
                   "default_coverage_percent", "default_copay_percent",
                   "default_copay_flat", "annual_limit", "per_visit_limit",
                   "requires_referral", "notes", "is_active"}
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(plan, k, v)
        self.db.flush()
        self.db.commit()
        return _plan_read(plan)

    def get_plan(self, plan_id: int) -> dict:
        plan = self._get_plan(plan_id)
        out = _plan_read(plan)
        out["benefits"] = [_benefit_read(b) for b in plan.benefits if not b.is_deleted]
        return out

    # ---------------- benefits ----------------

    def upsert_benefit(self, *, benefit_id: Optional[int] = None, **fields) -> dict:
        if fields.get("limit_period"):
            try:
                fields["limit_period"] = BenefitLimitPeriod(fields["limit_period"])
            except ValueError:
                raise BadRequestError(f"Invalid limit_period '{fields['limit_period']}'.")
        if benefit_id:
            b = (self.db.query(HmoPlanBenefit)
                 .filter(HmoPlanBenefit.id == benefit_id,
                         HmoPlanBenefit.is_deleted.is_(False)).first())
            if b is None:
                raise NotFoundError("Benefit rule not found.")
        else:
            if not fields.get("hmo_plan_id"):
                raise BadRequestError("hmo_plan_id is required.")
            self._get_plan(fields["hmo_plan_id"])
            b = HmoPlanBenefit(hmo_plan_id=fields["hmo_plan_id"])
            self.db.add(b)
        allowed = {"category", "billable_service_id", "drug_id", "coverage_percent",
                   "copay_flat", "limit_amount", "limit_period", "requires_preauth",
                   "is_excluded", "notes", "is_active"}
        for k, v in fields.items():
            if k in allowed:
                setattr(b, k, v)
        self.db.flush()
        self.db.commit()
        return _benefit_read(b)

    def delete_benefit(self, benefit_id: int) -> dict:
        b = (self.db.query(HmoPlanBenefit)
             .filter(HmoPlanBenefit.id == benefit_id,
                     HmoPlanBenefit.is_deleted.is_(False)).first())
        if b is None:
            raise NotFoundError("Benefit rule not found.")
        b.soft_delete()
        self.db.commit()
        return {"deleted": benefit_id}

    # ---------------- tariffs ----------------

    def list_tariffs(self, plan_id: int) -> list[dict]:
        self._get_plan(plan_id)
        rows = (self.db.query(HmoTariff)
                .filter(HmoTariff.hmo_plan_id == plan_id,
                        HmoTariff.is_deleted.is_(False))
                .order_by(HmoTariff.id.desc()).all())
        return [_tariff_read(t) for t in rows]

    def upsert_tariff(self, *, tariff_id: Optional[int] = None, **fields) -> dict:
        if tariff_id:
            t = (self.db.query(HmoTariff)
                 .filter(HmoTariff.id == tariff_id,
                         HmoTariff.is_deleted.is_(False)).first())
            if t is None:
                raise NotFoundError("Tariff not found.")
        else:
            if not fields.get("hmo_plan_id") or fields.get("agreed_price") is None:
                raise BadRequestError("hmo_plan_id and agreed_price are required.")
            self._get_plan(fields["hmo_plan_id"])
            t = HmoTariff(hmo_plan_id=fields["hmo_plan_id"],
                          agreed_price=_d(fields["agreed_price"]))
            self.db.add(t)
        allowed = {"billable_service_id", "drug_id", "service_code", "agreed_price",
                   "effective_from", "effective_to", "is_active"}
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(t, k, v)
        self.db.flush()
        self.db.commit()
        return _tariff_read(t)

    def delete_tariff(self, tariff_id: int) -> dict:
        t = (self.db.query(HmoTariff)
             .filter(HmoTariff.id == tariff_id, HmoTariff.is_deleted.is_(False)).first())
        if t is None:
            raise NotFoundError("Tariff not found.")
        t.soft_delete()
        self.db.commit()
        return {"deleted": tariff_id}

    def import_tariffs_csv(self, plan_id: int, *, content: bytes,
                           dry_run: bool = True) -> dict:
        """Import a tariff sheet. Expected headers (case-insensitive):
        ``service_code, service_name, agreed_price[, effective_from, effective_to]``.
        Matches by BillableService.code first, then exact name. Returns
        row-level errors; with ``dry_run`` nothing is written."""
        plan = self._get_plan(plan_id)
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            raise BadRequestError("Empty CSV file.")
        headers = {h.strip().lower(): h for h in reader.fieldnames}
        if "agreed_price" not in headers or ("service_code" not in headers and "service_name" not in headers):
            raise BadRequestError(
                "CSV must have 'agreed_price' and 'service_code' or 'service_name' columns.")

        ok_rows, errors = [], []
        for i, row in enumerate(reader, start=2):
            code = (row.get(headers.get("service_code", ""), "") or "").strip()
            name = (row.get(headers.get("service_name", ""), "") or "").strip()
            raw_price = (row.get(headers["agreed_price"], "") or "").strip()
            svc = None
            if code:
                svc = (self.db.query(BillableService)
                       .filter(func.lower(BillableService.code) == code.lower(),
                               BillableService.is_deleted.is_(False)).first())
            if svc is None and name:
                svc = (self.db.query(BillableService)
                       .filter(func.lower(BillableService.name) == name.lower(),
                               BillableService.is_deleted.is_(False)).first())
            if svc is None:
                errors.append({"row": i, "error": f"No billable service matches code='{code}' name='{name}'."})
                continue
            try:
                price = Decimal(raw_price.replace(",", ""))
                if price < 0:
                    raise InvalidOperation
            except (InvalidOperation, AttributeError):
                errors.append({"row": i, "error": f"Invalid agreed_price '{raw_price}'."})
                continue

            def _parse_date(key):
                v = (row.get(headers.get(key, ""), "") or "").strip()
                if not v:
                    return None
                try:
                    return date.fromisoformat(v)
                except ValueError:
                    errors.append({"row": i, "error": f"Invalid date '{v}' in {key}."})
                    return None

            ok_rows.append({"billable_service_id": svc.id, "service_name": svc.name,
                            "agreed_price": price,
                            "effective_from": _parse_date("effective_from"),
                            "effective_to": _parse_date("effective_to")})

        imported = 0
        if not dry_run and not errors:
            for r in ok_rows:
                existing = (self.db.query(HmoTariff)
                            .filter(HmoTariff.hmo_plan_id == plan.id,
                                    HmoTariff.billable_service_id == r["billable_service_id"],
                                    HmoTariff.is_deleted.is_(False)).first())
                if existing is not None:
                    existing.agreed_price = r["agreed_price"]
                    existing.effective_from = r["effective_from"]
                    existing.effective_to = r["effective_to"]
                else:
                    self.db.add(HmoTariff(
                        hmo_plan_id=plan.id,
                        billable_service_id=r["billable_service_id"],
                        agreed_price=r["agreed_price"],
                        effective_from=r["effective_from"],
                        effective_to=r["effective_to"]))
                imported += 1
            self.db.commit()
        return {"dry_run": dry_run, "valid_rows": len(ok_rows),
                "imported": imported, "errors": errors,
                "preview": [{**r, "agreed_price": str(r["agreed_price"]),
                             "effective_from": r["effective_from"].isoformat() if r["effective_from"] else None,
                             "effective_to": r["effective_to"].isoformat() if r["effective_to"] else None}
                            for r in ok_rows[:50]]}

    # ---------------- enrollees ----------------

    def list_enrollees(self, *, provider_id: Optional[int] = None,
                       plan_id: Optional[int] = None,
                       status: Optional[str] = None,
                       search: Optional[str] = None,
                       page: int = 1, page_size: int = 50) -> dict:
        q = (self.db.query(PatientInsurance)
             .join(Patient, Patient.id == PatientInsurance.patient_id)
             .filter(PatientInsurance.is_deleted.is_(False)))
        if provider_id:
            q = q.filter(PatientInsurance.insurance_provider_id == provider_id)
        if plan_id:
            q = q.filter(PatientInsurance.hmo_plan_id == plan_id)
        if status:
            try:
                q = q.filter(PatientInsurance.policy_status == InsurancePolicyStatus(status))
            except ValueError:
                raise BadRequestError(f"Invalid status '{status}'.")
        if search:
            like = f"%{search}%"
            q = q.filter(or_(Patient.first_name.ilike(like),
                             Patient.last_name.ilike(like),
                             PatientInsurance.policy_number.ilike(like),
                             PatientInsurance.member_id.ilike(like)))
        total = q.count()
        rows = (q.order_by(PatientInsurance.id.desc())
                .offset((page - 1) * page_size).limit(page_size).all())
        items = []
        for pi in rows:
            plan = (self.db.query(HmoPlan).filter(HmoPlan.id == pi.hmo_plan_id).first()
                    if pi.hmo_plan_id else None)
            items.append({
                "id": pi.id, "patient_id": pi.patient_id,
                "patient_name": f"{pi.patient.first_name} {pi.patient.last_name}" if pi.patient else None,
                "policy_number": pi.policy_number, "member_id": pi.member_id,
                "plan_id": pi.hmo_plan_id, "plan_name": plan.name if plan else pi.plan_name,
                "policy_status": pi.policy_status.value if hasattr(pi.policy_status, "value") else pi.policy_status,
                "verification_status": pi.verification_status or "UNVERIFIED",
                "valid_to": (pi.valid_to or pi.coverage_end_date).isoformat()
                            if (pi.valid_to or pi.coverage_end_date) else None,
                "is_primary": pi.is_primary,
                "principal_patient_insurance_id": pi.principal_patient_insurance_id,
                "relationship_to_principal": pi.relationship_to_principal,
            })
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def link_to_plan(self, patient_insurance_id: int, *, hmo_plan_id: int) -> dict:
        pi = (self.db.query(PatientInsurance)
              .filter(PatientInsurance.id == patient_insurance_id,
                      PatientInsurance.is_deleted.is_(False)).first())
        if pi is None:
            raise NotFoundError("Enrollment not found.")
        plan = self._get_plan(hmo_plan_id)
        if plan.insurance_provider_id != pi.insurance_provider_id:
            raise BadRequestError("Plan belongs to a different insurance provider.")
        pi.hmo_plan_id = plan.id
        pi.plan_name = plan.name
        self.db.commit()
        return {"id": pi.id, "hmo_plan_id": plan.id, "plan_name": plan.name}

    def set_dependent(self, patient_insurance_id: int, *,
                      principal_patient_insurance_id: Optional[int],
                      relationship_to_principal: Optional[str]) -> dict:
        pi = (self.db.query(PatientInsurance)
              .filter(PatientInsurance.id == patient_insurance_id,
                      PatientInsurance.is_deleted.is_(False)).first())
        if pi is None:
            raise NotFoundError("Enrollment not found.")
        if principal_patient_insurance_id:
            principal = (self.db.query(PatientInsurance)
                         .filter(PatientInsurance.id == principal_patient_insurance_id,
                                 PatientInsurance.is_deleted.is_(False)).first())
            if principal is None:
                raise NotFoundError("Principal enrollment not found.")
            if principal.id == pi.id:
                raise BadRequestError("An enrollment cannot be its own principal.")
        pi.principal_patient_insurance_id = principal_patient_insurance_id
        pi.relationship_to_principal = relationship_to_principal
        self.db.commit()
        return {"id": pi.id,
                "principal_patient_insurance_id": pi.principal_patient_insurance_id,
                "relationship_to_principal": pi.relationship_to_principal}

    # ---------------- eligibility ----------------

    def record_eligibility_check(self, *, patient_insurance_id: int,
                                 result: str, method: str = "CARD",
                                 visit_id: Optional[int] = None,
                                 authorization_code: Optional[str] = None,
                                 notes: Optional[str] = None,
                                 user_id: Optional[int] = None) -> dict:
        pi = (self.db.query(PatientInsurance)
              .filter(PatientInsurance.id == patient_insurance_id,
                      PatientInsurance.is_deleted.is_(False)).first())
        if pi is None:
            raise NotFoundError("Enrollment not found.")
        try:
            result_e = EligibilityCheckResult(result)
            method_e = EligibilityCheckMethod(method)
        except ValueError as exc:
            raise BadRequestError(str(exc))
        now = datetime.now(timezone.utc)
        check = EligibilityCheck(
            patient_insurance_id=pi.id, visit_id=visit_id,
            checked_by_user_id=user_id, method=method_e, result=result_e,
            authorization_code=authorization_code, notes=notes, checked_at=now)
        self.db.add(check)
        if result_e == EligibilityCheckResult.ELIGIBLE:
            pi.verification_status = InsuranceVerificationStatus.VERIFIED.value
        elif result_e == EligibilityCheckResult.INELIGIBLE:
            pi.verification_status = InsuranceVerificationStatus.SUSPENDED.value
        pi.last_verified_at = now
        pi.last_verified_by_user_id = user_id
        self.db.flush()
        self.db.commit()
        return {"id": check.id, "patient_insurance_id": pi.id,
                "result": result_e.value, "method": method_e.value,
                "authorization_code": authorization_code,
                "verification_status": pi.verification_status,
                "checked_at": now.isoformat()}

    def list_eligibility_checks(self, *, patient_insurance_id: Optional[int] = None,
                                visit_id: Optional[int] = None, limit: int = 50) -> list[dict]:
        q = (self.db.query(EligibilityCheck)
             .filter(EligibilityCheck.is_deleted.is_(False)))
        if patient_insurance_id:
            q = q.filter(EligibilityCheck.patient_insurance_id == patient_insurance_id)
        if visit_id:
            q = q.filter(EligibilityCheck.visit_id == visit_id)
        return [{
            "id": c.id, "patient_insurance_id": c.patient_insurance_id,
            "visit_id": c.visit_id,
            "method": c.method.value if hasattr(c.method, "value") else c.method,
            "result": c.result.value if hasattr(c.result, "value") else c.result,
            "authorization_code": c.authorization_code, "notes": c.notes,
            "checked_at": c.checked_at.isoformat() if c.checked_at else None,
        } for c in q.order_by(EligibilityCheck.id.desc()).limit(limit).all()]

    # ---------------- expiry sweep (scheduler + on-demand) ----------------

    def expire_lapsed_policies(self) -> dict:
        """Flip policies past their end date to EXPIRED. Idempotent."""
        today = date.today()
        rows = (self.db.query(PatientInsurance)
                .filter(PatientInsurance.is_deleted.is_(False),
                        PatientInsurance.policy_status == InsurancePolicyStatus.ACTIVE)
                .all())
        expired = 0
        for pi in rows:
            end = pi.valid_to or pi.coverage_end_date
            if end is not None and end < today:
                pi.policy_status = InsurancePolicyStatus.EXPIRED
                pi.verification_status = InsuranceVerificationStatus.EXPIRED.value
                expired += 1
        if expired:
            self.db.commit()
        return {"expired": expired}

    def expiring_soon(self, *, days: int = 30) -> list[dict]:
        today = date.today()
        rows = (self.db.query(PatientInsurance)
                .filter(PatientInsurance.is_deleted.is_(False),
                        PatientInsurance.policy_status == InsurancePolicyStatus.ACTIVE)
                .all())
        out = []
        for pi in rows:
            end = pi.valid_to or pi.coverage_end_date
            if end is not None and today <= end <= (today + timedelta(days=days)):
                out.append({"id": pi.id, "patient_id": pi.patient_id,
                            "policy_number": pi.policy_number,
                            "valid_to": end.isoformat(),
                            "insurance_provider_id": pi.insurance_provider_id})
        return out
