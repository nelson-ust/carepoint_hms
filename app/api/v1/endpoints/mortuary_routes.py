# app/api/v1/endpoints/mortuary_routes.py
from __future__ import annotations

"""
FastAPI routes for the Mortuary / Morgue management module.

Sub-routes
----------
- ``/mortuary/units``     — storage units (cold chamber / freezer / shelf)
- ``/mortuary/deceased``  — deceased records (IN_HOSPITAL + BROUGHT_IN)
- ``/mortuary/stats``     — dashboard aggregates

Permission codes
----------------
- ``MORTUARY_READ``   — listing / details / stats
- ``MORTUARY_MANAGE`` — create / update / assign storage / release
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.mortuary_schemas import (
    AutopsyCreateSchema,
    MortuaryAnalyticsResponseSchema,
    MortuaryBillSummarySchema,
    MortuaryPaymentCreateSchema,
    StorageAccrualSchema,
    AutopsyUpdateSchema,
    CertificateCreateSchema,
    ChargeCreateSchema,
    MortuaryFeeCreateSchema,
    MortuaryFeeUpdateSchema,
    ChargeStatusSchema,
    EffectCreateSchema,
    EffectReleaseSchema,
    EmbalmingCreateSchema,
    SimpleActionResponseSchema,
    SimpleListResponseSchema,
    ViewingCreateSchema,
    DeathRecordActionResponseSchema,
    DeathRecordCreateSchema,
    DeathRecordListResponseSchema,
    DeceasedActionResponseSchema,
    DeceasedAssignStorageSchema,
    DeceasedListResponseSchema,
    DeceasedReadSchema,
    DeceasedRegisterSchema,
    DeceasedReleaseSchema,
    DeceasedUpdateSchema,
    MortuaryStatsResponseSchema,
    MortuaryUnitActionResponseSchema,
    MortuaryUnitCreateSchema,
    MortuaryUnitListResponseSchema,
    MortuaryUnitReadSchema,
    MortuaryUnitUpdateSchema,
)
from app.services.mortuary_service import MortuaryService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/mortuary",
    tags=["Mortuary"],
    dependencies=[Depends(require_plan_feature("mortuary"))],
)


def get_mortuary_service(db: Annotated[Session, Depends(get_db)]) -> MortuaryService:
    return MortuaryService(db)


# ============================================================
# STATS
# ============================================================


@router.get("/stats", response_model=MortuaryStatsResponseSchema, summary="Mortuary dashboard statistics")
def get_stats(
    _: Annotated[User, Depends(require_permission("MORTUARY_READ"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    data = service.stats()
    return {"success": True, "message": "Mortuary statistics computed successfully.", **data}


@router.get("/analytics", response_model=MortuaryAnalyticsResponseSchema, summary="Decision-support analytics for the mortuary")
def get_analytics(
    _: Annotated[User, Depends(require_permission("MORTUARY_READ"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
    months: int = Query(6, ge=1, le=24, description="Months of intake trend history."),
):
    data = service.analytics(months=months)
    return {"success": True, "message": "Mortuary analytics computed successfully.", **data}


# ============================================================
# STORAGE UNITS
# ============================================================


@router.get("/units", response_model=MortuaryUnitListResponseSchema, summary="List storage units")
def list_units(
    _: Annotated[User, Depends(require_permission("MORTUARY_READ"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: Optional[str] = Query(
        None, alias="status", description="AVAILABLE, PARTIAL, FULL, OUT_OF_SERVICE."
    ),
):
    items, total = service.list_units(skip=skip, limit=limit, status=status_filter)
    return paginate_response(
        items=[service.unit_dict(u) for u in items],
        total=total, skip=skip, limit=limit,
        message="Storage units fetched successfully.",
    )


@router.post(
    "/units",
    response_model=MortuaryUnitActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add a storage unit",
)
def create_unit(
    payload: MortuaryUnitCreateSchema,
    _: Annotated[User, Depends(require_permission("MORTUARY_MANAGE"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    u = service.create_unit(payload)
    return {"success": True, "message": "Storage unit added.", "unit": service.unit_dict(u)}


@router.get("/units/{unit_id}", response_model=MortuaryUnitReadSchema, summary="Get a storage unit")
def get_unit(
    unit_id: int,
    _: Annotated[User, Depends(require_permission("MORTUARY_READ"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    return service.unit_dict(service.get_unit(unit_id))


@router.put("/units/{unit_id}", response_model=MortuaryUnitActionResponseSchema, summary="Update a storage unit")
def update_unit(
    unit_id: int,
    payload: MortuaryUnitUpdateSchema,
    current_user: Annotated[User, Depends(require_permission("MORTUARY_MANAGE"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    u = service.update_unit(unit_id, payload, actor=current_user)
    return {"success": True, "message": "Storage unit updated.", "unit": service.unit_dict(u)}


@router.get("/units/{unit_id}/rate-history", response_model=SimpleListResponseSchema, summary="Rate-change history for a storage unit")
def unit_rate_history(
    unit_id: int,
    _: Annotated[User, Depends(require_permission("MORTUARY_READ"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    rows = service.unit_rate_history(unit_id)
    return _list(rows, service.rate_history_dict, "Rate history fetched.")


@router.delete("/units/{unit_id}", summary="Remove a storage unit")
def delete_unit(
    unit_id: int,
    _: Annotated[User, Depends(require_permission("MORTUARY_MANAGE"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    u = service.delete_unit(unit_id)
    return {"success": True, "message": "Storage unit removed.", "unit_id": u.id}


# ============================================================
# DECEASED RECORDS
# ============================================================


@router.get("/deceased", response_model=DeceasedListResponseSchema, summary="List deceased records")
def list_deceased(
    _: Annotated[User, Depends(require_permission("MORTUARY_READ"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    status_filter: Optional[str] = Query(
        None, alias="status", description="REGISTERED, IN_STORAGE, RELEASED, TRANSFERRED."
    ),
    source: Optional[str] = Query(None, description="IN_HOSPITAL or BROUGHT_IN."),
    unit_id: Optional[int] = Query(None),
    police_only: bool = Query(False),
    search: Optional[str] = Query(None, description="Match on deceased name or tag number."),
):
    items, total = service.list_deceased(
        skip=skip, limit=limit, status=status_filter, source=source,
        unit_id=unit_id, police_only=police_only, search=search,
    )
    return paginate_response(
        items=[service.record_dict(r) for r in items],
        total=total, skip=skip, limit=limit,
        message="Deceased records fetched successfully.",
    )


@router.post(
    "/deceased",
    response_model=DeceasedActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register a deceased person (in-hospital or brought-in)",
)
def register_deceased(
    payload: DeceasedRegisterSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("MORTUARY_MANAGE"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    r = service.register(payload)
    return {"success": True, "message": "Deceased record registered.", "record": service.record_dict(r)}


@router.get("/deceased/{record_id}", response_model=DeceasedReadSchema, summary="Get a deceased record")
def get_deceased(
    record_id: int,
    _: Annotated[User, Depends(require_permission("MORTUARY_READ"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    return service.record_dict(service.get_deceased(record_id))


@router.put("/deceased/{record_id}", response_model=DeceasedActionResponseSchema, summary="Update a deceased record")
def update_deceased(
    record_id: int,
    payload: DeceasedUpdateSchema,
    _: Annotated[User, Depends(require_permission("MORTUARY_MANAGE"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    r = service.update(record_id, payload)
    return {"success": True, "message": "Deceased record updated.", "record": service.record_dict(r)}


@router.post(
    "/deceased/{record_id}/assign-storage",
    response_model=DeceasedActionResponseSchema,
    summary="Place / move a body into a storage unit",
)
def assign_storage(
    record_id: int,
    payload: DeceasedAssignStorageSchema,
    _: Annotated[User, Depends(require_permission("MORTUARY_MANAGE"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    r = service.assign_storage(record_id, payload)
    return {"success": True, "message": "Body assigned to storage.", "record": service.record_dict(r)}


@router.post(
    "/deceased/{record_id}/release",
    response_model=DeceasedActionResponseSchema,
    summary="Release (or transfer) a body to next of kin / another facility",
)
def release_deceased(
    record_id: int,
    payload: DeceasedReleaseSchema,
    _: Annotated[User, Depends(require_permission("MORTUARY_MANAGE"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    r = service.release(record_id, payload)
    verb = "transferred" if str(r.status) == "TRANSFERRED" else "released"
    return {"success": True, "message": f"Deceased record {verb}.", "record": service.record_dict(r)}


# ============================================================
# PATIENT DEATH RECORDS (clinical declaration -> mortuary intake)
# ============================================================


@router.post(
    "/deaths",
    response_model=DeathRecordActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record a patient's death (optionally deposit the body to the mortuary)",
)
def record_death(
    payload: DeathRecordCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("MORTUARY_MANAGE"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    death, record = service.record_death(payload)
    return {
        "success": True,
        "message": "Patient death recorded." + (" Body deposited to mortuary." if record else ""),
        "death": service.death_dict(death),
        "record": service.record_dict(record) if record else None,
    }


@router.get(
    "/deaths/pending",
    response_model=DeathRecordListResponseSchema,
    summary="Deceased patients not yet deposited at the mortuary",
)
def list_pending_deaths(
    _: Annotated[User, Depends(require_permission("MORTUARY_READ"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
):
    items, total = service.list_deaths(skip=skip, limit=limit, deposited=False)
    return paginate_response(
        items=[service.death_dict(d) for d in items],
        total=total, skip=skip, limit=limit,
        message="Pending deposits fetched successfully.",
    )


@router.get(
    "/deaths",
    response_model=DeathRecordListResponseSchema,
    summary="List recorded patient deaths",
)
def list_deaths(
    _: Annotated[User, Depends(require_permission("MORTUARY_READ"))],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    deposited: Optional[bool] = Query(None, description="Filter by mortuary-deposit state."),
):
    items, total = service.list_deaths(skip=skip, limit=limit, deposited=deposited)
    return paginate_response(
        items=[service.death_dict(d) for d in items],
        total=total, skip=skip, limit=limit,
        message="Death records fetched successfully.",
    )


# ============================================================
# STANDARD MORTUARY OPERATIONS
# ============================================================

READ = require_permission("MORTUARY_READ")
MANAGE = require_permission("MORTUARY_MANAGE")


def _list(items, builder, msg):
    return paginate_response(items=[builder(i) for i in items], total=len(items), skip=0, limit=len(items) or 1, message=msg)


# ---- Autopsies ----
@router.get("/autopsies", response_model=SimpleListResponseSchema, summary="List autopsies (hospital-wide)")
def list_all_autopsies(
    _: Annotated[User, Depends(READ)],
    service: Annotated[MortuaryService, Depends(get_mortuary_service)],
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000),
):
    items, total = service.list_autopsies(status=status_filter, skip=skip, limit=limit)
    return paginate_response(items=[service.autopsy_dict(a) for a in items], total=total, skip=skip, limit=limit, message="Autopsies fetched successfully.")


@router.get("/deceased/{record_id}/autopsies", response_model=SimpleListResponseSchema, summary="List autopsies for a record")
def list_record_autopsies(record_id: int, _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    items, _t = service.list_autopsies(record_id=record_id, limit=1000)
    return _list(items, service.autopsy_dict, "Autopsies fetched successfully.")


@router.post("/deceased/{record_id}/autopsies", response_model=SimpleActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Request / schedule an autopsy")
def create_autopsy(record_id: int, payload: AutopsyCreateSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    a = service.create_autopsy(record_id, payload)
    return {"success": True, "message": "Autopsy recorded.", "data": service.autopsy_dict(a)}


@router.put("/autopsies/{autopsy_id}", response_model=SimpleActionResponseSchema, summary="Update an autopsy (status / findings)")
def update_autopsy(autopsy_id: int, payload: AutopsyUpdateSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    a = service.update_autopsy(autopsy_id, payload)
    return {"success": True, "message": "Autopsy updated.", "data": service.autopsy_dict(a)}


# ---- Embalming ----
@router.get("/deceased/{record_id}/embalming", response_model=SimpleListResponseSchema, summary="List embalming records")
def list_embalming(record_id: int, _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    return _list(service.list_embalming(record_id), service.embalming_dict, "Embalming records fetched.")


@router.post("/deceased/{record_id}/embalming", response_model=SimpleActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Record embalming / body prep")
def create_embalming(record_id: int, payload: EmbalmingCreateSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    e = service.create_embalming(record_id, payload)
    return {"success": True, "message": "Embalming recorded.", "data": service.embalming_dict(e)}


# ---- Personal effects ----
@router.get("/deceased/{record_id}/effects", response_model=SimpleListResponseSchema, summary="List personal effects")
def list_effects(record_id: int, _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    return _list(service.list_effects(record_id), service.effect_dict, "Effects fetched.")


@router.post("/deceased/{record_id}/effects", response_model=SimpleActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Log a personal effect")
def create_effect(record_id: int, payload: EffectCreateSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    e = service.create_effect(record_id, payload)
    return {"success": True, "message": "Effect logged.", "data": service.effect_dict(e)}


@router.post("/effects/{effect_id}/release", response_model=SimpleActionResponseSchema, summary="Release a personal effect to next of kin")
def release_effect(effect_id: int, payload: EffectReleaseSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    e = service.release_effect(effect_id, payload)
    return {"success": True, "message": "Effect released.", "data": service.effect_dict(e)}


# ---- Viewings ----
@router.get("/deceased/{record_id}/viewings", response_model=SimpleListResponseSchema, summary="List viewings")
def list_viewings(record_id: int, _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    return _list(service.list_viewings(record_id), service.viewing_dict, "Viewings fetched.")


@router.post("/deceased/{record_id}/viewings", response_model=SimpleActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Log a family viewing")
def create_viewing(record_id: int, payload: ViewingCreateSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    v = service.create_viewing(record_id, payload)
    return {"success": True, "message": "Viewing logged.", "data": service.viewing_dict(v)}


# ---- Charges / billing ----
@router.get("/charges", response_model=SimpleListResponseSchema, summary="List mortuary charges (hospital-wide)")
def list_all_charges(
    _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)],
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000),
):
    items, total = service.list_charges(status=status_filter, skip=skip, limit=limit)
    return paginate_response(items=[service.charge_dict(c) for c in items], total=total, skip=skip, limit=limit, message="Charges fetched successfully.")


@router.get("/deceased/{record_id}/charges", response_model=SimpleListResponseSchema, summary="List charges for a record")
def list_record_charges(record_id: int, _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    items, _t = service.list_charges(record_id=record_id, limit=1000)
    summary = service.charges_summary(record_id)
    resp = _list(items, service.charge_dict, "Charges fetched.")
    resp["meta"] = {**resp.get("meta", {}), "summary": {k: str(v) for k, v in summary.items()}}
    return resp


@router.post("/deceased/{record_id}/charges", response_model=SimpleActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Add a mortuary charge")
def create_charge(record_id: int, payload: ChargeCreateSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    c = service.create_charge(record_id, payload)
    return {"success": True, "message": "Charge added.", "data": service.charge_dict(c)}


@router.post("/charges/{charge_id}/status", response_model=SimpleActionResponseSchema, summary="Mark a charge paid / waived")
def set_charge_status(charge_id: int, payload: ChargeStatusSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    c = service.set_charge_status(charge_id, payload.status)
    return {"success": True, "message": f"Charge marked {payload.status}.", "data": service.charge_dict(c)}


# ---- Chart-of-accounts codes available to the mortuary module ----
@router.get("/accounts", response_model=SimpleListResponseSchema, summary="Account codes available for mortuary costings")
def list_mortuary_accounts(
    _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)],
):
    rows = service.list_mortuary_accounts()
    return _list(rows, service.account_dict, "Mortuary account codes fetched.")


# ---- Fee schedule (price list) — every costing points at a chart-of-accounts code ----
@router.get("/fee-schedule", response_model=SimpleListResponseSchema, summary="List mortuary fee items (price list)")
def list_fee_schedule(
    _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)],
    active_only: bool = Query(False),
):
    items = service.list_fees(active_only=active_only)
    return _list(items, service.fee_dict, "Fee schedule fetched.")


@router.post("/fee-schedule", response_model=SimpleActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Add a fee item")
def create_fee_item(payload: MortuaryFeeCreateSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    f = service.create_fee(payload)
    return {"success": True, "message": "Fee item added.", "data": service.fee_dict(f)}


@router.put("/fee-schedule/{fee_id}", response_model=SimpleActionResponseSchema, summary="Update a fee item")
def update_fee_item(fee_id: int, payload: MortuaryFeeUpdateSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    f = service.update_fee(fee_id, payload)
    return {"success": True, "message": "Fee item updated.", "data": service.fee_dict(f)}


@router.delete("/fee-schedule/{fee_id}", response_model=SimpleActionResponseSchema, summary="Remove a fee item")
def delete_fee_item(fee_id: int, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    service.delete_fee(fee_id)
    return {"success": True, "message": "Fee item removed."}


@router.post("/fee-schedule/seed-defaults", response_model=SimpleActionResponseSchema, summary="Seed the default Nigerian mortuary price list")
def seed_fee_schedule(_: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    n = service.ensure_default_fees()
    return {"success": True, "message": f"Seeded {n} default fee item(s)." if n else "Fee schedule already set up."}


@router.post("/deceased/{record_id}/accrue-storage", response_model=SimpleActionResponseSchema, summary="Accrue storage charges to date")
def accrue_storage(record_id: int, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    c = service.accrue_storage(record_id)
    return {"success": True, "message": "Storage accrued to date.", "data": service.charge_dict(c)}


# ---- Death certificate ----
@router.get("/deceased/{record_id}/certificate", response_model=SimpleActionResponseSchema, summary="Get the death certificate (if issued)")
def get_certificate(record_id: int, _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    c = service.get_certificate(record_id)
    return {"success": True, "message": "Certificate fetched." if c else "No certificate issued.", "data": service.certificate_dict(c) if c else {}}


@router.post("/deceased/{record_id}/certificate", response_model=SimpleActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Issue a death certificate")
def issue_certificate(record_id: int, payload: CertificateCreateSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    c = service.issue_certificate(record_id, payload)
    return {"success": True, "message": "Death certificate issued.", "data": service.certificate_dict(c)}


# ---- Billing / finance (per record) ----
@router.get("/deceased/{record_id}/billing-summary", response_model=MortuaryBillSummarySchema, summary="Billing summary for a deceased record")
def billing_summary(record_id: int, _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    data = service.bill_summary(record_id)
    return {"success": True, "message": "Billing summary computed.", **data}


@router.post("/deceased/{record_id}/payments", response_model=SimpleActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Record a mortuary payment")
def add_payment(record_id: int, payload: MortuaryPaymentCreateSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    p = service.add_payment(record_id, payload)
    return {"success": True, "message": "Payment recorded.", "data": service.payment_dict(p)}


@router.get("/deceased/{record_id}/payments", response_model=SimpleListResponseSchema, summary="List payments for a record")
def list_payments(record_id: int, _: Annotated[User, Depends(READ)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    return _list(service.list_payments(record_id), service.payment_dict, "Payments fetched.")


@router.post("/deceased/{record_id}/accrue-storage", response_model=SimpleActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Accrue the cold-storage charge for days held")
def accrue_storage(record_id: int, payload: StorageAccrualSchema, _: Annotated[User, Depends(MANAGE)], service: Annotated[MortuaryService, Depends(get_mortuary_service)]):
    c = service.accrue_storage(record_id, payload.daily_rate)
    return {"success": True, "message": "Storage charge accrued.", "data": service.charge_dict(c)}
