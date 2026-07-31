# app/api/v1/endpoints/surgical_routes.py
from __future__ import annotations

"""
FastAPI routes for the Surgical / Theatre module.

Routers:
- ``/theatres``                — operating-theatre CRUD + status transitions
- ``/surgical/procedures``     — surgical procedure catalog
- ``/surgical/cases``          — case lifecycle (book → complete) and worklist
- ``/surgical/team``           — team-member assignments
- ``/surgical/consents``       — patient consent records
- ``/surgical/checklists``     — WHO sign-in / time-out / sign-out
- ``/surgical/anaesthesia``    — anaesthesia records
- ``/surgical/notes``          — intra-op theatre notes
- ``/surgical/instrument-sets``— instrument sets + sterilization cycles

Permissions:
- ``THEATRE_MANAGE``          — manage theatre records and status
- ``SURGICAL_MANAGE``         — manage surgical catalog + soft-delete
- ``SURGICAL_BOOK``           — book / cancel a case
- ``SURGICAL_PERFORM``        — drive lifecycle transitions during a case
- ``SURGICAL_RECORD``         — record consent / checklist / notes / anaesthesia
- ``SURGICAL_READ``           — read-only access (worklists, lookups)
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.surgical_schemas import (
    AnaesthesiaRecordActionResponseSchema,
    AnaesthesiaRecordCreateSchema,
    InstrumentSterilizationLogActionResponseSchema,
    InstrumentSterilizationLogCreateSchema,
    OperatingTheatreActionResponseSchema,
    OperatingTheatreCreateSchema,
    OperatingTheatreListResponseSchema,
    OperatingTheatreStatusSchema,
    OperatingTheatreUpdateSchema,
    SurgicalCaseActionResponseSchema,
    SurgicalCaseBookSchema,
    SurgicalCaseListResponseSchema,
    SurgicalCaseTransitionSchema,
    SurgicalChecklistActionResponseSchema,
    SurgicalChecklistRecordSchema,
    SurgicalConsentActionResponseSchema,
    SurgicalConsentCreateSchema,
    SurgicalInstrumentSetActionResponseSchema,
    SurgicalInstrumentSetAssignSchema,
    SurgicalInstrumentSetCreateSchema,
    SurgicalProcedureCatalogActionResponseSchema,
    SurgicalProcedureCatalogCreateSchema,
    SurgicalProcedureCatalogListResponseSchema,
    SurgicalTeamMemberActionResponseSchema,
    SurgicalTeamMemberAddSchema,
    TheatreNoteActionResponseSchema,
    TheatreNoteCreateSchema,
)
from app.services.surgical_service import (
    AnaesthesiaService,
    InstrumentSetService,
    OperatingTheatreService,
    SurgicalCaseService,
    SurgicalCatalogService,
    SurgicalChecklistService,
    SurgicalConsentService,
    SurgicalTeamService,
    TheatreNoteService,
)
from app.utils.pagination import paginate_response

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

theatre_router = APIRouter(prefix="/theatres", tags=["Surgical - Theatres"], dependencies=[Depends(require_plan_feature("surgical"))])
catalog_router = APIRouter(prefix="/surgical/procedures", tags=["Surgical - Catalog"], dependencies=[Depends(require_plan_feature("surgical"))])
case_router = APIRouter(prefix="/surgical/cases", tags=["Surgical - Cases"], dependencies=[Depends(require_plan_feature("surgical"))])
team_router = APIRouter(prefix="/surgical/team", tags=["Surgical - Team"], dependencies=[Depends(require_plan_feature("surgical"))])
consent_router = APIRouter(prefix="/surgical/consents", tags=["Surgical - Consents"], dependencies=[Depends(require_plan_feature("surgical"))])
checklist_router = APIRouter(prefix="/surgical/checklists", tags=["Surgical - Checklists"], dependencies=[Depends(require_plan_feature("surgical"))])
anaesthesia_router = APIRouter(
    prefix="/surgical/anaesthesia", tags=["Surgical - Anaesthesia"], dependencies=[Depends(require_plan_feature("surgical"))]
)
note_router = APIRouter(prefix="/surgical/notes", tags=["Surgical - Notes"], dependencies=[Depends(require_plan_feature("surgical"))])
instrument_router = APIRouter(
    prefix="/surgical/instrument-sets", tags=["Surgical - Instruments"], dependencies=[Depends(require_plan_feature("surgical"))]
)



# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_theatre_service(db: Annotated[Session, Depends(get_db)]) -> OperatingTheatreService:
    return OperatingTheatreService(db)


def get_catalog_service(db: Annotated[Session, Depends(get_db)]) -> SurgicalCatalogService:
    return SurgicalCatalogService(db)


def get_case_service(db: Annotated[Session, Depends(get_db)]) -> SurgicalCaseService:
    return SurgicalCaseService(db)


def get_team_service(db: Annotated[Session, Depends(get_db)]) -> SurgicalTeamService:
    return SurgicalTeamService(db)


def get_consent_service(db: Annotated[Session, Depends(get_db)]) -> SurgicalConsentService:
    return SurgicalConsentService(db)


def get_checklist_service(db: Annotated[Session, Depends(get_db)]) -> SurgicalChecklistService:
    return SurgicalChecklistService(db)


def get_anaesthesia_service(db: Annotated[Session, Depends(get_db)]) -> AnaesthesiaService:
    return AnaesthesiaService(db)


def get_note_service(db: Annotated[Session, Depends(get_db)]) -> TheatreNoteService:
    return TheatreNoteService(db)


def get_instrument_service(db: Annotated[Session, Depends(get_db)]) -> InstrumentSetService:
    return InstrumentSetService(db)


# ---------------------------------------------------------------------------
# ORM -> dict helpers
# ---------------------------------------------------------------------------


def _theatre_dict(t) -> dict:
    return {
        "id": t.id,
        "code": t.code,
        "name": t.name,
        "facility_id": t.facility_id,
        "location_description": t.location_description,
        "status": str(t.status),
        "is_emergency_capable": bool(t.is_emergency_capable),
        "capabilities": t.capabilities,
        "notes": t.notes,
        "created_at": getattr(t, "created_at", None),
    }


def _surgical_catalog_dict(p) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "cpt_code": p.cpt_code,
        "typical_duration_minutes": p.typical_duration_minutes,
        "requires_blood_products": bool(p.requires_blood_products),
        "average_blood_loss_ml": p.average_blood_loss_ml,
        "default_price": p.default_price,
        "description": p.description,
        "pre_op_instructions": p.pre_op_instructions,
        "post_op_instructions": p.post_op_instructions,
    }


def _case_dict(c) -> dict:
    return {
        "id": c.id,
        "case_no": c.case_no,
        "patient_id": c.patient_id,
        "visit_id": c.visit_id,
        "facility_id": c.facility_id,
        "procedure_catalog_id": c.procedure_catalog_id,
        "operating_theatre_id": c.operating_theatre_id,
        "status": str(c.status),
        "is_emergency": bool(c.is_emergency),
        "asa_class": str(c.asa_class) if c.asa_class else None,
        "anaesthesia_type": str(c.anaesthesia_type) if c.anaesthesia_type else None,
        "scheduled_start_at": c.scheduled_start_at,
        "scheduled_end_at": c.scheduled_end_at,
        "pre_op_started_at": c.pre_op_started_at,
        "incision_at": c.incision_at,
        "closure_at": c.closure_at,
        "out_of_theatre_at": c.out_of_theatre_at,
        "diagnosis_text": c.diagnosis_text,
        "findings_text": c.findings_text,
        "cancellation_reason": c.cancellation_reason,
        "created_at": getattr(c, "created_at", None),
    }


def _team_member_dict(m) -> dict:
    return {
        "id": m.id,
        "surgical_case_id": m.surgical_case_id,
        "staff_profile_id": m.staff_profile_id,
        "role": str(m.role),
        "is_lead": bool(m.is_lead),
        "notes": m.notes,
    }


def _consent_dict(c) -> dict:
    return {
        "id": c.id,
        "surgical_case_id": c.surgical_case_id,
        "consent_text": c.consent_text,
        "consent_signed_by": c.consent_signed_by,
        "relationship_to_patient": c.relationship_to_patient,
        "witnessed_by_staff_id": c.witnessed_by_staff_id,
        "signed_at": c.signed_at,
        "signature_image_url": c.signature_image_url,
    }


def _checklist_dict(cl) -> dict:
    return {
        "id": cl.id,
        "surgical_case_id": cl.surgical_case_id,
        "phase": str(cl.phase),
        "completed_at": cl.completed_at,
        "completed_by_staff_id": cl.completed_by_staff_id,
        "items": cl.items,
        "notes": cl.notes,
    }


def _anaesthesia_dict(r) -> dict:
    return {
        "id": r.id,
        "surgical_case_id": r.surgical_case_id,
        "anaesthetist_staff_id": r.anaesthetist_staff_id,
        "anaesthesia_type": str(r.anaesthesia_type),
        "induction_time": r.induction_time,
        "emergence_time": r.emergence_time,
        "agents": r.agents,
        "monitoring_intervals": r.monitoring_intervals,
        "complications": r.complications,
        "notes": r.notes,
    }


def _note_dict(n) -> dict:
    return {
        "id": n.id,
        "surgical_case_id": n.surgical_case_id,
        "author_staff_id": n.author_staff_id,
        "note_type": n.note_type,
        "note": n.note,
        "captured_at": n.captured_at,
    }


def _instrument_set_dict(s) -> dict:
    return {
        "id": s.id,
        "code": s.code,
        "name": s.name,
        "facility_id": s.facility_id,
        "surgical_case_id": s.surgical_case_id,
        "sterilization_status": str(s.sterilization_status),
        "last_autoclaved_at": s.last_autoclaved_at,
        "next_required_sterilization_at": s.next_required_sterilization_at,
        "contents": s.contents,
        "notes": s.notes,
    }


def _sterilization_log_dict(log) -> dict:
    return {
        "id": log.id,
        "instrument_set_id": log.instrument_set_id,
        "performed_by_staff_id": log.performed_by_staff_id,
        "cycle_started_at": log.cycle_started_at,
        "cycle_ended_at": log.cycle_ended_at,
        "method": log.method,
        "machine_identifier": log.machine_identifier,
        "indicator_passed": log.indicator_passed,
        "notes": log.notes,
    }


# ============================================================
# THEATRE
# ============================================================


@theatre_router.get(
    "/",
    response_model=OperatingTheatreListResponseSchema,
    summary="List operating theatres",
)
def list_theatres(
    _: Annotated[User, Depends(require_permission("THEATRE_MANAGE", "SURGICAL_READ"))],
    service: Annotated[OperatingTheatreService, Depends(get_theatre_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    status_filter: Optional[str] = Query(None, alias="status"),
    facility_id: Optional[int] = Query(None),
    emergency_only: bool = Query(False),
    search: Optional[str] = Query(None),
):
    items, total = service.list_theatres(
        skip=skip,
        limit=limit,
        status=status_filter,
        facility_id=facility_id,
        emergency_only=emergency_only,
        search=search,
    )
    return paginate_response(
        items=[_theatre_dict(t) for t in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Operating theatres fetched successfully.",
    )


@theatre_router.post(
    "/",
    response_model=OperatingTheatreActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create an operating theatre",
)
def create_theatre(
    payload: OperatingTheatreCreateSchema,
    _: Annotated[User, Depends(require_permission("THEATRE_MANAGE"))],
    service: Annotated[OperatingTheatreService, Depends(get_theatre_service)],
):
    t = service.create(payload)
    return {
        "success": True,
        "message": "Operating theatre created.",
        "theatre": _theatre_dict(t),
    }


@theatre_router.get(
    "/{theatre_id}",
    summary="Get an operating theatre",
)
def get_theatre(
    theatre_id: int,
    _: Annotated[User, Depends(require_permission("THEATRE_MANAGE", "SURGICAL_READ"))],
    service: Annotated[OperatingTheatreService, Depends(get_theatre_service)],
):
    return _theatre_dict(service.get(theatre_id))


@theatre_router.put(
    "/{theatre_id}",
    response_model=OperatingTheatreActionResponseSchema,
    summary="Update an operating theatre",
)
def update_theatre(
    theatre_id: int,
    payload: OperatingTheatreUpdateSchema,
    _: Annotated[User, Depends(require_permission("THEATRE_MANAGE"))],
    service: Annotated[OperatingTheatreService, Depends(get_theatre_service)],
):
    t = service.update(theatre_id, payload)
    return {
        "success": True,
        "message": "Operating theatre updated.",
        "theatre": _theatre_dict(t),
    }


@theatre_router.post(
    "/{theatre_id}/status",
    response_model=OperatingTheatreActionResponseSchema,
    summary="Change operating-theatre status",
)
def change_theatre_status(
    theatre_id: int,
    payload: OperatingTheatreStatusSchema,
    user: Annotated[User, Depends(require_permission("THEATRE_MANAGE"))],
    service: Annotated[OperatingTheatreService, Depends(get_theatre_service)],
):
    t = service.change_status(theatre_id, payload, actor_user_id=user.id)
    return {
        "success": True,
        "message": "Operating-theatre status changed.",
        "theatre": _theatre_dict(t),
    }


@theatre_router.delete(
    "/{theatre_id}",
    summary="Soft-delete an operating theatre",
)
def soft_delete_theatre(
    theatre_id: int,
    user: Annotated[User, Depends(require_permission("THEATRE_MANAGE"))],
    service: Annotated[OperatingTheatreService, Depends(get_theatre_service)],
):
    t = service.soft_delete(theatre_id, actor_user_id=user.id)
    return {
        "success": True,
        "message": "Operating theatre deactivated.",
        "theatre_id": t.id,
    }


# ============================================================
# SURGICAL CATALOG
# ============================================================


@catalog_router.get(
    "/",
    response_model=SurgicalProcedureCatalogListResponseSchema,
    summary="List surgical procedures",
)
def list_procedures(
    _: Annotated[
        User, Depends(require_permission("SURGICAL_BOOK", "SURGICAL_PERFORM", "SURGICAL_READ"))
    ],
    service: Annotated[SurgicalCatalogService, Depends(get_catalog_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None),
):
    items, total = service.list_procedures(skip=skip, limit=limit, search=search)
    return paginate_response(
        items=[_surgical_catalog_dict(p) for p in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Surgical procedures fetched successfully.",
    )


@catalog_router.post(
    "/",
    response_model=SurgicalProcedureCatalogActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a surgical procedure",
)
def create_procedure(
    payload: SurgicalProcedureCatalogCreateSchema,
    _: Annotated[User, Depends(require_permission("SURGICAL_MANAGE"))],
    service: Annotated[SurgicalCatalogService, Depends(get_catalog_service)],
):
    p = service.create(payload)
    return {
        "success": True,
        "message": "Surgical procedure created.",
        "procedure": _surgical_catalog_dict(p),
    }


@catalog_router.get(
    "/{procedure_id}",
    summary="Get a surgical procedure",
)
def get_procedure(
    procedure_id: int,
    _: Annotated[
        User, Depends(require_permission("SURGICAL_BOOK", "SURGICAL_PERFORM", "SURGICAL_READ"))
    ],
    service: Annotated[SurgicalCatalogService, Depends(get_catalog_service)],
):
    return _surgical_catalog_dict(service.get(procedure_id))


@catalog_router.delete(
    "/{procedure_id}",
    summary="Soft-delete a surgical procedure",
)
def soft_delete_procedure(
    procedure_id: int,
    _: Annotated[User, Depends(require_permission("SURGICAL_MANAGE"))],
    service: Annotated[SurgicalCatalogService, Depends(get_catalog_service)],
):
    p = service.soft_delete(procedure_id)
    return {
        "success": True,
        "message": "Surgical procedure deactivated.",
        "procedure_id": p.id,
    }


# ============================================================
# SURGICAL CASES
# ============================================================


@case_router.get(
    "/visits/{visit_id}",
    response_model=SurgicalCaseListResponseSchema,
    summary="List surgical cases for a visit",
)
def list_cases_for_visit(
    visit_id: int,
    _: Annotated[
        User, Depends(require_permission("SURGICAL_READ", "SURGICAL_BOOK", "VISIT_READ"))
    ],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=[_case_dict(c) for c in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Surgical cases fetched successfully.",
    )


@case_router.get(
    "/worklist",
    response_model=SurgicalCaseListResponseSchema,
    summary="Theatre worklist (open cases)",
)
def case_worklist(
    _: Annotated[User, Depends(require_permission("SURGICAL_PERFORM", "SURGICAL_READ"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    statuses: Optional[list[str]] = Query(None),
    operating_theatre_id: Optional[int] = Query(None),
    emergency_only: bool = Query(False),
):
    items, total = service.list_worklist(
        skip=skip,
        limit=limit,
        statuses=statuses,
        operating_theatre_id=operating_theatre_id,
        emergency_only=emergency_only,
    )
    return paginate_response(
        items=[_case_dict(c) for c in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Surgical worklist fetched successfully.",
    )


@case_router.post(
    "/",
    response_model=SurgicalCaseActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Book a new surgical case",
)
def book_case(
    payload: SurgicalCaseBookSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_BOOK"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
):
    c = service.book_case(payload, actor_user_id=user.id)
    return {"success": True, "message": "Surgical case booked.", "case": _case_dict(c)}


@case_router.get(
    "/{case_id}",
    summary="Get a surgical case",
)
def get_case(
    case_id: int,
    _: Annotated[User, Depends(require_permission("SURGICAL_READ", "SURGICAL_PERFORM"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
):
    return _case_dict(service.get(case_id))


@case_router.post(
    "/{case_id}/confirm",
    response_model=SurgicalCaseActionResponseSchema,
    summary="Confirm a booked case",
)
def confirm_case(
    case_id: int,
    payload: SurgicalCaseTransitionSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_BOOK", "SURGICAL_PERFORM"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
):
    c = service.confirm(case_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Surgical case confirmed.", "case": _case_dict(c)}


@case_router.post(
    "/{case_id}/start-pre-op",
    response_model=SurgicalCaseActionResponseSchema,
    summary="Move case into PRE_OP",
)
def start_pre_op(
    case_id: int,
    payload: SurgicalCaseTransitionSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_PERFORM"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
):
    c = service.start_pre_op(case_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Pre-op started.", "case": _case_dict(c)}


@case_router.post(
    "/{case_id}/into-theatre",
    response_model=SurgicalCaseActionResponseSchema,
    summary="Move case INTO_THEATRE (after sign-in)",
)
def into_theatre(
    case_id: int,
    payload: SurgicalCaseTransitionSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_PERFORM"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
):
    c = service.into_theatre(case_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Patient brought into theatre.", "case": _case_dict(c)}


@case_router.post(
    "/{case_id}/incision",
    response_model=SurgicalCaseActionResponseSchema,
    summary="Mark incision (after time-out)",
)
def case_incision(
    case_id: int,
    payload: SurgicalCaseTransitionSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_PERFORM"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
):
    c = service.incision(case_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Incision recorded.", "case": _case_dict(c)}


@case_router.post(
    "/{case_id}/closure",
    response_model=SurgicalCaseActionResponseSchema,
    summary="Mark closure (procedure ended)",
)
def case_closure(
    case_id: int,
    payload: SurgicalCaseTransitionSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_PERFORM"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
):
    c = service.closure(case_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Closure recorded.", "case": _case_dict(c)}


@case_router.post(
    "/{case_id}/post-op",
    response_model=SurgicalCaseActionResponseSchema,
    summary="Move case to POST_OP (after sign-out)",
)
def case_post_op(
    case_id: int,
    payload: SurgicalCaseTransitionSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_PERFORM"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
):
    c = service.to_post_op(case_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Patient moved to post-op.", "case": _case_dict(c)}


@case_router.post(
    "/{case_id}/complete",
    response_model=SurgicalCaseActionResponseSchema,
    summary="Complete a case (captures charge + optional onward routing)",
)
def case_complete(
    case_id: int,
    payload: SurgicalCaseTransitionSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_PERFORM"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
    route_to_service_delivery_point_id: Optional[int] = Query(
        None, description="Optional SDP to route the visit to (e.g. recovery / ward)."
    ),
):
    c = service.complete(
        case_id,
        payload,
        actor_user_id=user.id,
        route_to_service_delivery_point_id=route_to_service_delivery_point_id,
    )
    return {"success": True, "message": "Surgical case completed.", "case": _case_dict(c)}


@case_router.post(
    "/{case_id}/cancel",
    response_model=SurgicalCaseActionResponseSchema,
    summary="Cancel a case",
)
def case_cancel(
    case_id: int,
    payload: SurgicalCaseTransitionSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_BOOK", "SURGICAL_PERFORM"))],
    service: Annotated[SurgicalCaseService, Depends(get_case_service)],
):
    c = service.cancel(case_id, payload, actor_user_id=user.id)
    return {"success": True, "message": "Surgical case cancelled.", "case": _case_dict(c)}


# ============================================================
# TEAM
# ============================================================


@team_router.get(
    "/cases/{case_id}",
    summary="List team members for a case",
)
def list_team(
    case_id: int,
    _: Annotated[User, Depends(require_permission("SURGICAL_READ", "SURGICAL_PERFORM"))],
    service: Annotated[SurgicalTeamService, Depends(get_team_service)],
):
    members = service.list_for_case(case_id)
    return {
        "success": True,
        "message": "Team members fetched successfully.",
        "items": [_team_member_dict(m) for m in members],
        "count": len(members),
    }


@team_router.post(
    "/",
    response_model=SurgicalTeamMemberActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add a team member to a case",
)
def add_team_member(
    payload: SurgicalTeamMemberAddSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_BOOK", "SURGICAL_PERFORM"))],
    service: Annotated[SurgicalTeamService, Depends(get_team_service)],
):
    m = service.add(payload, actor_user_id=user.id)
    return {"success": True, "message": "Team member added.", "member": _team_member_dict(m)}


@team_router.delete(
    "/{member_id}",
    summary="Remove a team member from a case",
)
def remove_team_member(
    member_id: int,
    user: Annotated[User, Depends(require_permission("SURGICAL_BOOK", "SURGICAL_PERFORM"))],
    service: Annotated[SurgicalTeamService, Depends(get_team_service)],
):
    m = service.remove(member_id, actor_user_id=user.id)
    return {"success": True, "message": "Team member removed.", "member_id": m.id}


# ============================================================
# CONSENT
# ============================================================


@consent_router.get(
    "/cases/{case_id}",
    summary="List consents for a case",
)
def list_consents(
    case_id: int,
    _: Annotated[User, Depends(require_permission("SURGICAL_READ", "SURGICAL_RECORD"))],
    service: Annotated[SurgicalConsentService, Depends(get_consent_service)],
):
    consents = service.list_for_case(case_id)
    return {
        "success": True,
        "message": "Consents fetched successfully.",
        "items": [_consent_dict(c) for c in consents],
        "count": len(consents),
    }


@consent_router.post(
    "/",
    response_model=SurgicalConsentActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record patient consent",
)
def record_consent(
    payload: SurgicalConsentCreateSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_RECORD"))],
    service: Annotated[SurgicalConsentService, Depends(get_consent_service)],
):
    c = service.record(payload, actor_user_id=user.id)
    return {"success": True, "message": "Consent recorded.", "consent": _consent_dict(c)}


# ============================================================
# CHECKLIST
# ============================================================


@checklist_router.get(
    "/cases/{case_id}",
    summary="List checklist phases for a case",
)
def list_checklists(
    case_id: int,
    _: Annotated[User, Depends(require_permission("SURGICAL_READ", "SURGICAL_RECORD"))],
    service: Annotated[SurgicalChecklistService, Depends(get_checklist_service)],
):
    items = service.list_for_case(case_id)
    return {
        "success": True,
        "message": "Checklist records fetched successfully.",
        "items": [_checklist_dict(cl) for cl in items],
        "count": len(items),
    }


@checklist_router.post(
    "/",
    response_model=SurgicalChecklistActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record a checklist phase (SIGN_IN / TIME_OUT / SIGN_OUT)",
)
def record_checklist(
    payload: SurgicalChecklistRecordSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_RECORD"))],
    service: Annotated[SurgicalChecklistService, Depends(get_checklist_service)],
):
    cl = service.record(payload, actor_user_id=user.id)
    return {
        "success": True,
        "message": "Checklist phase recorded.",
        "checklist": _checklist_dict(cl),
    }


# ============================================================
# ANAESTHESIA
# ============================================================


@anaesthesia_router.get(
    "/cases/{case_id}",
    summary="List anaesthesia records for a case",
)
def list_anaesthesia(
    case_id: int,
    _: Annotated[
        User, Depends(require_permission("SURGICAL_READ", "SURGICAL_RECORD", "ANAESTHESIA_RECORD"))
    ],
    service: Annotated[AnaesthesiaService, Depends(get_anaesthesia_service)],
):
    items = service.list_for_case(case_id)
    return {
        "success": True,
        "message": "Anaesthesia records fetched successfully.",
        "items": [_anaesthesia_dict(r) for r in items],
        "count": len(items),
    }


@anaesthesia_router.post(
    "/",
    response_model=AnaesthesiaRecordActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record an anaesthesia entry",
)
def record_anaesthesia(
    payload: AnaesthesiaRecordCreateSchema,
    user: Annotated[
        User, Depends(require_permission("ANAESTHESIA_RECORD", "SURGICAL_RECORD"))
    ],
    service: Annotated[AnaesthesiaService, Depends(get_anaesthesia_service)],
):
    r = service.record(payload, actor_user_id=user.id)
    return {
        "success": True,
        "message": "Anaesthesia record created.",
        "record": _anaesthesia_dict(r),
    }


# ============================================================
# THEATRE NOTES
# ============================================================


@note_router.get(
    "/cases/{case_id}",
    summary="List theatre notes for a case",
)
def list_notes(
    case_id: int,
    _: Annotated[User, Depends(require_permission("SURGICAL_READ", "SURGICAL_RECORD"))],
    service: Annotated[TheatreNoteService, Depends(get_note_service)],
):
    items = service.list_for_case(case_id)
    return {
        "success": True,
        "message": "Theatre notes fetched successfully.",
        "items": [_note_dict(n) for n in items],
        "count": len(items),
    }


@note_router.post(
    "/",
    response_model=TheatreNoteActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Add a theatre note",
)
def add_note(
    payload: TheatreNoteCreateSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_RECORD"))],
    service: Annotated[TheatreNoteService, Depends(get_note_service)],
):
    n = service.add(payload, actor_user_id=user.id)
    return {"success": True, "message": "Theatre note added.", "theatre_note": _note_dict(n)}


# ============================================================
# INSTRUMENT SETS
# ============================================================


@instrument_router.get(
    "/",
    summary="List instrument sets",
)
def list_instrument_sets(
    _: Annotated[User, Depends(require_permission("INSTRUMENT_MANAGE", "SURGICAL_READ"))],
    service: Annotated[InstrumentSetService, Depends(get_instrument_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    sterilization_status: Optional[str] = Query(None),
    facility_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
):
    items, total = service.list_sets(
        skip=skip,
        limit=limit,
        sterilization_status=sterilization_status,
        facility_id=facility_id,
        search=search,
    )
    return paginate_response(
        items=[_instrument_set_dict(s) for s in items],
        total=total,
        skip=skip,
        limit=limit,
        message="Instrument sets fetched successfully.",
    )


@instrument_router.post(
    "/",
    response_model=SurgicalInstrumentSetActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create an instrument set",
)
def create_instrument_set(
    payload: SurgicalInstrumentSetCreateSchema,
    user: Annotated[User, Depends(require_permission("INSTRUMENT_MANAGE"))],
    service: Annotated[InstrumentSetService, Depends(get_instrument_service)],
):
    s = service.create(payload, actor_user_id=user.id)
    return {
        "success": True,
        "message": "Instrument set created.",
        "instrument_set": _instrument_set_dict(s),
    }


@instrument_router.get(
    "/{set_id}",
    summary="Get an instrument set",
)
def get_instrument_set(
    set_id: int,
    _: Annotated[User, Depends(require_permission("INSTRUMENT_MANAGE", "SURGICAL_READ"))],
    service: Annotated[InstrumentSetService, Depends(get_instrument_service)],
):
    return _instrument_set_dict(service.get(set_id))


@instrument_router.post(
    "/{set_id}/assign",
    response_model=SurgicalInstrumentSetActionResponseSchema,
    summary="Assign an instrument set to a case",
)
def assign_instrument_set(
    set_id: int,
    payload: SurgicalInstrumentSetAssignSchema,
    user: Annotated[User, Depends(require_permission("SURGICAL_PERFORM", "INSTRUMENT_MANAGE"))],
    service: Annotated[InstrumentSetService, Depends(get_instrument_service)],
):
    s = service.assign_to_case(set_id, payload, actor_user_id=user.id)
    return {
        "success": True,
        "message": "Instrument set assigned to case.",
        "instrument_set": _instrument_set_dict(s),
    }


@instrument_router.post(
    "/{set_id}/sterilization",
    response_model=InstrumentSterilizationLogActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record a sterilization cycle for an instrument set",
)
def log_sterilization(
    set_id: int,
    payload: InstrumentSterilizationLogCreateSchema,
    user: Annotated[User, Depends(require_permission("INSTRUMENT_MANAGE"))],
    service: Annotated[InstrumentSetService, Depends(get_instrument_service)],
):
    # Force the set_id from the URL to be authoritative.
    payload = payload.model_copy(update={"instrument_set_id": set_id})
    log = service.record_sterilization_cycle(payload, actor_user_id=user.id)
    return {
        "success": True,
        "message": "Sterilization cycle recorded.",
        "log": _sterilization_log_dict(log),
    }
