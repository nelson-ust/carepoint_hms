# app/api/v1/endpoints/hmo_routes.py
from __future__ import annotations

"""
HMO / Health-insurance module API: payer profiles, plans, benefit rules,
tariffs (+CSV import), enrollees, eligibility verification, coverage preview,
capitation (contracts, schedules, variance, payments, loss-ratio report),
remittance advices with bulk allocation, payer ledger/statement,
disallowance write-offs and claims extensions (batching, aging, rejection
analytics, resubmission).

Read = CLAIM_READ · manage payers/plans/claims = CLAIM_MANAGE ·
adjudication-side actions & money = CLAIM_REVIEW.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.all_models import User

router = APIRouter(prefix="/hmo", tags=["HMO / Insurance"])

Reader = Annotated[User, Depends(require_permission("CLAIM_READ", "CLAIM_MANAGE", "CLAIM_REVIEW"))]
Manager = Annotated[User, Depends(require_permission("CLAIM_MANAGE", "CLAIM_REVIEW"))]
Reviewer = Annotated[User, Depends(require_permission("CLAIM_REVIEW"))]
Db = Annotated[Session, Depends(get_db)]


def _uid(actor) -> Optional[int]:
    return getattr(actor, "id", None)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProviderProfileSchema(BaseModel):
    provider_type: Optional[str] = None
    nhia_accreditation_no: Optional[str] = None
    bank_account_details: Optional[dict] = None
    default_payment_terms_days: Optional[int] = Field(None, ge=0, le=365)
    capitation_supported: Optional[bool] = None
    fee_for_service_supported: Optional[bool] = None
    contact_person: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class PlanSchema(BaseModel):
    insurance_provider_id: Optional[int] = None
    name: Optional[str] = None
    code: Optional[str] = None
    plan_tier: Optional[str] = None
    coverage_type: Optional[str] = None
    default_coverage_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    default_copay_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    default_copay_flat: Optional[Decimal] = Field(None, ge=0)
    annual_limit: Optional[Decimal] = Field(None, ge=0)
    per_visit_limit: Optional[Decimal] = Field(None, ge=0)
    requires_referral: Optional[bool] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class BenefitSchema(BaseModel):
    hmo_plan_id: Optional[int] = None
    category: Optional[str] = None
    billable_service_id: Optional[int] = None
    drug_id: Optional[int] = None
    coverage_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    copay_flat: Optional[Decimal] = Field(None, ge=0)
    limit_amount: Optional[Decimal] = Field(None, ge=0)
    limit_period: Optional[str] = None
    requires_preauth: Optional[bool] = None
    is_excluded: Optional[bool] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class TariffSchema(BaseModel):
    hmo_plan_id: Optional[int] = None
    billable_service_id: Optional[int] = None
    drug_id: Optional[int] = None
    service_code: Optional[str] = None
    agreed_price: Optional[Decimal] = Field(None, ge=0)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class EligibilitySchema(BaseModel):
    patient_insurance_id: int
    result: str
    method: str = "CARD"
    visit_id: Optional[int] = None
    authorization_code: Optional[str] = None
    notes: Optional[str] = None


class LinkPlanSchema(BaseModel):
    hmo_plan_id: int


class DependentSchema(BaseModel):
    principal_patient_insurance_id: Optional[int] = None
    relationship_to_principal: Optional[str] = None


class CoveragePreviewSchema(BaseModel):
    patient_id: int
    unit_price: Decimal = Field(..., ge=0)
    quantity: Decimal = Field(1, gt=0)
    billable_service_id: Optional[int] = None
    drug_id: Optional[int] = None
    service_code: Optional[str] = None
    category: Optional[str] = None


class ContractSchema(BaseModel):
    insurance_provider_id: Optional[int] = None
    hmo_plan_id: Optional[int] = None
    rate_per_enrollee: Optional[Decimal] = Field(None, ge=0)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    payment_day: Optional[int] = Field(None, ge=1, le=31)
    status: Optional[str] = None
    notes: Optional[str] = None


class CapitationRunSchema(BaseModel):
    contract_id: int
    period_code: str = Field(..., pattern=r"^\d{4}-\d{2}$")


class CapitationPaymentSchema(BaseModel):
    line_id: int
    amount: Decimal = Field(..., gt=0)
    paid_at: date
    reference: Optional[str] = None
    bank_account_id: Optional[int] = None
    notes: Optional[str] = None


class RemittanceCreateSchema(BaseModel):
    insurance_provider_id: int
    total_amount: Decimal = Field(..., gt=0)
    received_at: date
    reference: Optional[str] = None
    bank_account_id: Optional[int] = None
    document_url: Optional[str] = None
    notes: Optional[str] = None


class AllocationSchema(BaseModel):
    claim_id: Optional[int] = None
    capitation_schedule_line_id: Optional[int] = None
    amount: Decimal = Field(..., gt=0)


class AllocateSchema(BaseModel):
    allocations: list[AllocationSchema] = Field(..., min_length=1)


class WriteOffSchema(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0)
    reason_code: Optional[str] = None
    reason_text: Optional[str] = None


class RejectionReasonSchema(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class BatchGenerateSchema(BaseModel):
    provider_id: int
    period_code: str = Field(..., pattern=r"^\d{4}-\d{2}$")


# ---------------------------------------------------------------------------
# Providers / plans / benefits / tariffs
# ---------------------------------------------------------------------------

@router.get("/providers", summary="Payers with plan/enrollee counts")
def list_providers(actor: Reader, db: Db, search: Optional[str] = Query(None)):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "items": HmoPlanService(db).list_providers(search=search)}


@router.put("/providers/{provider_id}", summary="Update payer profile (type, NHIA no, terms)")
def update_provider(provider_id: int, payload: ProviderProfileSchema, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "provider": HmoPlanService(db).update_provider_profile(
        provider_id, **payload.model_dump(exclude_none=True))}


@router.get("/plans", summary="List HMO plans")
def list_plans(actor: Reader, db: Db, provider_id: Optional[int] = Query(None),
               include_inactive: bool = Query(False)):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "items": HmoPlanService(db).list_plans(
        provider_id=provider_id, include_inactive=include_inactive)}


@router.post("/plans", status_code=status.HTTP_201_CREATED, summary="Create a plan")
def create_plan(payload: PlanSchema, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "plan": HmoPlanService(db).upsert_plan(
        **payload.model_dump(exclude_none=True))}


@router.get("/plans/{plan_id}", summary="Plan detail with benefit rules")
def get_plan(plan_id: int, actor: Reader, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "plan": HmoPlanService(db).get_plan(plan_id)}


@router.put("/plans/{plan_id}", summary="Update a plan")
def update_plan(plan_id: int, payload: PlanSchema, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "plan": HmoPlanService(db).upsert_plan(
        plan_id=plan_id, **payload.model_dump(exclude_none=True))}


@router.post("/benefits", status_code=status.HTTP_201_CREATED, summary="Add a benefit rule")
def create_benefit(payload: BenefitSchema, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "benefit": HmoPlanService(db).upsert_benefit(
        **payload.model_dump(exclude_none=True))}


@router.put("/benefits/{benefit_id}", summary="Update a benefit rule")
def update_benefit(benefit_id: int, payload: BenefitSchema, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "benefit": HmoPlanService(db).upsert_benefit(
        benefit_id=benefit_id, **payload.model_dump(exclude_none=True))}


@router.delete("/benefits/{benefit_id}", summary="Remove a benefit rule")
def delete_benefit(benefit_id: int, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, **HmoPlanService(db).delete_benefit(benefit_id)}


@router.get("/plans/{plan_id}/tariffs", summary="Plan tariff (negotiated price list)")
def list_tariffs(plan_id: int, actor: Reader, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "items": HmoPlanService(db).list_tariffs(plan_id)}


@router.post("/tariffs", status_code=status.HTTP_201_CREATED, summary="Add a tariff line")
def create_tariff(payload: TariffSchema, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "tariff": HmoPlanService(db).upsert_tariff(
        **payload.model_dump(exclude_none=True))}


@router.put("/tariffs/{tariff_id}", summary="Update a tariff line")
def update_tariff(tariff_id: int, payload: TariffSchema, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "tariff": HmoPlanService(db).upsert_tariff(
        tariff_id=tariff_id, **payload.model_dump(exclude_none=True))}


@router.delete("/tariffs/{tariff_id}", summary="Remove a tariff line")
def delete_tariff(tariff_id: int, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, **HmoPlanService(db).delete_tariff(tariff_id)}


@router.post("/plans/{plan_id}/tariffs/import",
             summary="Import a tariff CSV (dry_run=true validates only)")
async def import_tariffs(plan_id: int, actor: Manager, db: Db,
                         file: UploadFile = File(...),
                         dry_run: bool = Query(True)):
    from app.services.hmo_plan_service import HmoPlanService
    content = await file.read()
    return {"success": True, **HmoPlanService(db).import_tariffs_csv(
        plan_id, content=content, dry_run=dry_run)}


# ---------------------------------------------------------------------------
# Enrollees & eligibility
# ---------------------------------------------------------------------------

@router.get("/enrollees", summary="Enrollee register")
def list_enrollees(actor: Reader, db: Db,
                   provider_id: Optional[int] = Query(None),
                   plan_id: Optional[int] = Query(None),
                   enrollee_status: Optional[str] = Query(None, alias="status"),
                   search: Optional[str] = Query(None),
                   page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, **HmoPlanService(db).list_enrollees(
        provider_id=provider_id, plan_id=plan_id, status=enrollee_status,
        search=search, page=page, page_size=page_size)}


@router.post("/enrollees/{patient_insurance_id}/link-plan", summary="Attach enrollment to a plan")
def link_plan(patient_insurance_id: int, payload: LinkPlanSchema, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, **HmoPlanService(db).link_to_plan(
        patient_insurance_id, hmo_plan_id=payload.hmo_plan_id)}


@router.post("/enrollees/{patient_insurance_id}/dependent", summary="Set principal/dependent link")
def set_dependent(patient_insurance_id: int, payload: DependentSchema, actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, **HmoPlanService(db).set_dependent(
        patient_insurance_id,
        principal_patient_insurance_id=payload.principal_patient_insurance_id,
        relationship_to_principal=payload.relationship_to_principal)}


@router.post("/eligibility-checks", status_code=status.HTTP_201_CREATED,
             summary="Record a front-desk eligibility verification")
def record_eligibility(payload: EligibilitySchema, actor: Reader, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "check": HmoPlanService(db).record_eligibility_check(
        patient_insurance_id=payload.patient_insurance_id, result=payload.result,
        method=payload.method, visit_id=payload.visit_id,
        authorization_code=payload.authorization_code, notes=payload.notes,
        user_id=_uid(actor))}


@router.get("/eligibility-checks", summary="Eligibility check history")
def list_eligibility(actor: Reader, db: Db,
                     patient_insurance_id: Optional[int] = Query(None),
                     visit_id: Optional[int] = Query(None)):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "items": HmoPlanService(db).list_eligibility_checks(
        patient_insurance_id=patient_insurance_id, visit_id=visit_id)}


@router.get("/enrollees/expiring", summary="Policies expiring within N days")
def expiring(actor: Reader, db: Db, days: int = Query(30, ge=1, le=365)):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, "items": HmoPlanService(db).expiring_soon(days=days)}


@router.post("/enrollees/expire-lapsed", summary="Flip lapsed policies to EXPIRED (idempotent)")
def expire_lapsed(actor: Manager, db: Db):
    from app.services.hmo_plan_service import HmoPlanService
    return {"success": True, **HmoPlanService(db).expire_lapsed_policies()}


@router.post("/coverage/preview", summary="Preview the HMO/patient split for a chargeable item")
def coverage_preview(payload: CoveragePreviewSchema, actor: Reader, db: Db):
    from app.services.coverage_engine import CoverageEngine
    engine = CoverageEngine(db)
    enrollment = engine.active_insurance_for_patient(payload.patient_id)
    decision = engine.evaluate(
        enrollment=enrollment, unit_price=payload.unit_price,
        quantity=payload.quantity, billable_service_id=payload.billable_service_id,
        drug_id=payload.drug_id, service_code=payload.service_code,
        category=payload.category)
    has_auth = (engine.has_valid_preauth(enrollment) if enrollment is not None else False)
    return {"success": True, "insured": enrollment is not None,
            "patient_insurance_id": enrollment.id if enrollment else None,
            "decision": {
                "unit_price": str(decision.unit_price),
                "line_total": str(decision.line_total),
                "covered_amount": str(decision.covered_amount),
                "patient_amount": str(decision.patient_amount),
                "is_covered": decision.is_covered,
                "requires_preauth": decision.requires_preauth,
                "has_valid_preauth": has_auth,
                "coverage_source": decision.coverage_source,
                "notes": decision.notes,
            }}


# ---------------------------------------------------------------------------
# Capitation
# ---------------------------------------------------------------------------

@router.get("/capitation/contracts", summary="Capitation contracts")
def list_contracts(actor: Reader, db: Db, provider_id: Optional[int] = Query(None)):
    from app.services.capitation_service import CapitationService
    return {"success": True, "items": CapitationService(db).list_contracts(provider_id=provider_id)}


@router.post("/capitation/contracts", status_code=status.HTTP_201_CREATED,
             summary="Create a capitation contract")
def create_contract(payload: ContractSchema, actor: Manager, db: Db):
    from app.services.capitation_service import CapitationService
    return {"success": True, "contract": CapitationService(db).upsert_contract(
        **payload.model_dump(exclude_none=True))}


@router.put("/capitation/contracts/{contract_id}", summary="Update a capitation contract")
def update_contract(contract_id: int, payload: ContractSchema, actor: Manager, db: Db):
    from app.services.capitation_service import CapitationService
    return {"success": True, "contract": CapitationService(db).upsert_contract(
        contract_id=contract_id, **payload.model_dump(exclude_none=True))}


@router.post("/capitation/run", summary="Generate the monthly capitation schedule")
def run_capitation(payload: CapitationRunSchema, actor: Manager, db: Db):
    from app.services.capitation_service import CapitationService
    return {"success": True, "schedule_line": CapitationService(db).run_month(
        contract_id=payload.contract_id, period_code=payload.period_code)}


@router.get("/capitation/schedule", summary="Capitation schedule lines")
def list_schedule(actor: Reader, db: Db,
                  contract_id: Optional[int] = Query(None),
                  provider_id: Optional[int] = Query(None),
                  period_code: Optional[str] = Query(None)):
    from app.services.capitation_service import CapitationService
    return {"success": True, "items": CapitationService(db).list_schedule(
        contract_id=contract_id, provider_id=provider_id, period_code=period_code)}


@router.post("/capitation/schedule/{line_id}/confirm",
             summary="Confirm a schedule (posts the receivable on next sweep)")
def confirm_schedule(line_id: int, actor: Manager, db: Db):
    from app.services.capitation_service import CapitationService
    return {"success": True, "schedule_line": CapitationService(db).confirm_schedule(line_id)}


@router.post("/capitation/schedule/{line_id}/import-hmo-list",
             summary="Upload the HMO's enrollee list and compute the variance")
async def import_hmo_list(line_id: int, actor: Manager, db: Db,
                          file: UploadFile = File(...)):
    from app.services.capitation_service import CapitationService
    content = await file.read()
    return {"success": True, **CapitationService(db).import_hmo_list(line_id, content=content)}


@router.post("/capitation/payments", status_code=status.HTTP_201_CREATED,
             summary="Record a capitation receipt")
def record_cap_payment(payload: CapitationPaymentSchema, actor: Reviewer, db: Db):
    from app.services.capitation_service import CapitationService
    return {"success": True, **CapitationService(db).record_payment(
        line_id=payload.line_id, amount=payload.amount, paid_at=payload.paid_at,
        reference=payload.reference, bank_account_id=payload.bank_account_id,
        notes=payload.notes)}


@router.get("/capitation/utilization", summary="Capitation vs utilization (loss ratio)")
def capitation_utilization(actor: Reader, db: Db,
                           provider_id: int = Query(...),
                           period_from: str = Query(...),
                           period_to: str = Query(...)):
    from app.services.capitation_service import CapitationService
    return {"success": True, **CapitationService(db).utilization_report(
        provider_id=provider_id, period_from=period_from, period_to=period_to)}


# ---------------------------------------------------------------------------
# Remittances, payer ledger, write-offs
# ---------------------------------------------------------------------------

@router.get("/remittances", summary="Remittance advices")
def list_remittances(actor: Reader, db: Db, provider_id: Optional[int] = Query(None)):
    from app.services.remittance_service import RemittanceService
    return {"success": True, "items": RemittanceService(db).list_advices(provider_id=provider_id)}


@router.post("/remittances", status_code=status.HTTP_201_CREATED,
             summary="Record a bulk payer payment")
def create_remittance(payload: RemittanceCreateSchema, actor: Reviewer, db: Db):
    from app.services.remittance_service import RemittanceService
    return {"success": True, "advice": RemittanceService(db).create_advice(
        insurance_provider_id=payload.insurance_provider_id,
        total_amount=payload.total_amount, received_at=payload.received_at,
        reference=payload.reference, bank_account_id=payload.bank_account_id,
        document_url=payload.document_url, notes=payload.notes, user_id=_uid(actor))}


@router.get("/remittances/{advice_id}/suggestions",
            summary="Fuzzy-matched open claims/capitation for allocation")
def remittance_suggestions(advice_id: int, actor: Reader, db: Db):
    from app.services.remittance_service import RemittanceService
    return {"success": True, **RemittanceService(db).suggest_matches(advice_id)}


@router.post("/remittances/{advice_id}/allocate", summary="Allocate the remittance")
def allocate_remittance(advice_id: int, payload: AllocateSchema, actor: Reviewer, db: Db):
    from app.services.remittance_service import RemittanceService
    return {"success": True, "advice": RemittanceService(db).allocate(
        advice_id,
        allocations=[a.model_dump() for a in payload.allocations],
        user_id=_uid(actor))}


@router.get("/payers/balances", summary="Outstanding balance per payer")
def payer_balances(actor: Reader, db: Db):
    from app.services.remittance_service import RemittanceService
    return {"success": True, "items": RemittanceService(db).payer_balances()}


@router.get("/payers/{provider_id}/statement", summary="Payer ledger / statement")
def payer_statement(provider_id: int, actor: Reader, db: Db,
                    date_from: Optional[date] = Query(None),
                    date_to: Optional[date] = Query(None)):
    from app.services.remittance_service import RemittanceService
    return {"success": True, **RemittanceService(db).payer_statement(
        provider_id, date_from=date_from, date_to=date_to)}


@router.post("/claims/{claim_id}/write-off", summary="Write off a disallowed amount")
def write_off(claim_id: int, payload: WriteOffSchema, actor: Reviewer, db: Db):
    from app.services.remittance_service import RemittanceService
    return {"success": True, **RemittanceService(db).write_off_claim(
        claim_id=claim_id, amount=payload.amount,
        reason_code=payload.reason_code, reason_text=payload.reason_text,
        user_id=_uid(actor))}


@router.post("/claims/{claim_id}/push-patient-responsibility",
             summary="Invoice the patient-responsibility amount")
def push_patient_responsibility(claim_id: int, actor: Reviewer, db: Db):
    from app.services.remittance_service import RemittanceService
    return {"success": True, **RemittanceService(db).push_patient_responsibility(
        claim_id=claim_id, user_id=_uid(actor))}


# ---------------------------------------------------------------------------
# Claims extensions
# ---------------------------------------------------------------------------

@router.get("/rejection-reasons", summary="Rejection reason codes")
def rejection_reasons(actor: Reader, db: Db):
    from app.services.claims_ext_service import ClaimsExtService
    return {"success": True, "items": ClaimsExtService(db).list_rejection_reasons()}


@router.post("/rejection-reasons", status_code=status.HTTP_201_CREATED,
             summary="Add a rejection reason code")
def create_rejection_reason(payload: RejectionReasonSchema, actor: Manager, db: Db):
    from app.services.claims_ext_service import ClaimsExtService
    return {"success": True, "reason": ClaimsExtService(db).upsert_rejection_reason(
        **payload.model_dump(exclude_none=True))}


@router.put("/rejection-reasons/{reason_id}", summary="Update a rejection reason code")
def update_rejection_reason(reason_id: int, payload: RejectionReasonSchema,
                            actor: Manager, db: Db):
    from app.services.claims_ext_service import ClaimsExtService
    return {"success": True, "reason": ClaimsExtService(db).upsert_rejection_reason(
        reason_id=reason_id, **payload.model_dump(exclude_none=True))}


@router.post("/claims/{claim_id}/resubmit", summary="Spawn a corrected claim from a rejection")
def resubmit_claim(claim_id: int, actor: Manager, db: Db):
    from app.services.claims_ext_service import ClaimsExtService
    return {"success": True, **ClaimsExtService(db).resubmit_claim(
        claim_id, user_id=_uid(actor))}


@router.post("/batches/generate-monthly", summary="Batch a month's draft claims for one payer")
def generate_batch(payload: BatchGenerateSchema, actor: Manager, db: Db):
    from app.services.claims_ext_service import ClaimsExtService
    return {"success": True, **ClaimsExtService(db).generate_monthly_batch(
        provider_id=payload.provider_id, period_code=payload.period_code,
        user_id=_uid(actor))}


@router.get("/batches/{batch_id}/export.xlsx", summary="Submission workbook for a batch")
def export_batch(batch_id: int, actor: Reader, db: Db):
    from app.services.claims_ext_service import ClaimsExtService
    name, blob = ClaimsExtService(db).export_batch_xlsx(batch_id)
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/reports/claim-aging", summary="Claim aging per payer")
def claim_aging(actor: Reader, db: Db, provider_id: Optional[int] = Query(None),
                as_of: Optional[date] = Query(None)):
    from app.services.claims_ext_service import ClaimsExtService
    return {"success": True, **ClaimsExtService(db).claim_aging(
        provider_id=provider_id, as_of=as_of)}


@router.get("/reports/rejection-analysis", summary="Denial analytics")
def rejection_analysis(actor: Reader, db: Db,
                       provider_id: Optional[int] = Query(None),
                       date_from: Optional[date] = Query(None),
                       date_to: Optional[date] = Query(None)):
    from app.services.claims_ext_service import ClaimsExtService
    return {"success": True, **ClaimsExtService(db).rejection_analysis(
        provider_id=provider_id, date_from=date_from, date_to=date_to)}


@router.get("/reports/settlement", summary="Days-to-settlement metrics")
def settlement(actor: Reader, db: Db, provider_id: Optional[int] = Query(None)):
    from app.services.claims_ext_service import ClaimsExtService
    return {"success": True, **ClaimsExtService(db).settlement_metrics(provider_id=provider_id)}


@router.get("/dashboard", summary="Insurance dashboard KPIs")
def insurance_dashboard(actor: Reader, db: Db):
    from datetime import datetime, timezone
    from sqlalchemy import func as _f
    from app.core.enums import InsuranceClaimStatus as _ICS
    from app.models.all_models import InsuranceClaim as _IC
    from app.services.claims_ext_service import ClaimsExtService
    from app.services.hmo_plan_service import HmoPlanService
    from app.services.remittance_service import RemittanceService
    from app.services.capitation_service import CapitationService

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_claims = (db.query(_f.count(_IC.id),
                             _f.coalesce(_f.sum(_IC.billed_amount), 0))
                    .filter(_IC.is_deleted.is_(False),
                            _IC.date_created >= month_start).first())
    balances = RemittanceService(db).payer_balances()
    period_code = now.strftime("%Y-%m")
    cap_lines = CapitationService(db).list_schedule(period_code=period_code)
    cap_expected = sum(Decimal(l["expected_amount"]) for l in cap_lines) if cap_lines else Decimal("0")
    cap_received = sum(Decimal(l["received_amount"]) for l in cap_lines) if cap_lines else Decimal("0")
    return {"success": True,
            "outstanding_by_payer": balances[:10],
            "total_outstanding": str(sum((Decimal(b["total_outstanding"]) for b in balances), Decimal("0"))),
            "claims_this_month": {"count": month_claims[0] or 0,
                                  "value": str(Decimal(str(month_claims[1] or 0)))},
            "capitation_this_month": {"expected": str(cap_expected),
                                      "received": str(cap_received)},
            "rejection": ClaimsExtService(db).rejection_analysis(),
            "settlement": ClaimsExtService(db).settlement_metrics(),
            "expiring_policies": HmoPlanService(db).expiring_soon(days=30)[:20]}
