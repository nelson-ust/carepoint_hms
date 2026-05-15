# app/api/v1/endpoints/radiology_routes.py
from __future__ import annotations

"""
FastAPI routes for the Radiology / RIS module.

Three routers:
- ``/radiology/procedures``  — catalog
- ``/radiology/orders``      — orders + items + worklist
- ``/radiology/exams``       — exam scheduling/execution + images
- ``/radiology/reports``     — drafting / finalization / release

Permissions: RADIOLOGY_ORDER, RADIOLOGY_PERFORM, RADIOLOGY_REPORT, RADIOLOGY_RELEASE.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.radiology_schemas import (
    RadiologyExamActionResponseSchema,
    RadiologyExamCompleteSchema,
    RadiologyExamReadSchema,
    RadiologyExamScheduleSchema,
    RadiologyExamStartSchema,
    RadiologyImageActionResponseSchema,
    RadiologyImageAttachSchema,
    RadiologyImageReadSchema,
    RadiologyOrderActionResponseSchema,
    RadiologyOrderCancelSchema,
    RadiologyOrderCreateSchema,
    RadiologyOrderListResponseSchema,
    RadiologyOrderReadSchema,
    RadiologyProcedureCatalogActionResponseSchema,
    RadiologyProcedureCatalogCreateSchema,
    RadiologyProcedureCatalogListResponseSchema,
    RadiologyProcedureCatalogReadSchema,
    RadiologyProcedureCatalogUpdateSchema,
    RadiologyReportActionResponseSchema,
    RadiologyReportDraftSchema,
    RadiologyReportFinalizeSchema,
    RadiologyReportReadSchema,
    RadiologyReportReleaseSchema,
)
from app.services.radiology_service import (
    RadiologyCatalogService,
    RadiologyExamService,
    RadiologyOrderService,
    RadiologyReportService,
)
from app.utils.pagination import paginate_response

catalog_router = APIRouter(prefix="/radiology/procedures", tags=["Radiology - Catalog"], dependencies=[Depends(require_plan_feature("radiology"))])
order_router = APIRouter(prefix="/radiology/orders", tags=["Radiology - Orders"], dependencies=[Depends(require_plan_feature("radiology"))])
exam_router = APIRouter(prefix="/radiology/exams", tags=["Radiology - Exams"], dependencies=[Depends(require_plan_feature("radiology"))])
report_router = APIRouter(prefix="/radiology/reports", tags=["Radiology - Reports"], dependencies=[Depends(require_plan_feature("radiology"))])



# ---- Service factories ----------------------------------------------------


def get_catalog_service(db: Annotated[Session, Depends(get_db)]) -> RadiologyCatalogService:
    return RadiologyCatalogService(db)


def get_order_service(db: Annotated[Session, Depends(get_db)]) -> RadiologyOrderService:
    return RadiologyOrderService(db)


def get_exam_service(db: Annotated[Session, Depends(get_db)]) -> RadiologyExamService:
    return RadiologyExamService(db)


def get_report_service(db: Annotated[Session, Depends(get_db)]) -> RadiologyReportService:
    return RadiologyReportService(db)


# ---- ORM -> dict helpers --------------------------------------------------


def _catalog_dict(p) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "name": p.name,
        "modality": str(p.modality),
        "body_part": p.body_part,
        "cpt_code": p.cpt_code,
        "typical_duration_minutes": p.typical_duration_minutes,
        "contrast_required": bool(p.contrast_required),
        "radiation_dose_msv": p.radiation_dose_msv,
        "preparation_instructions": p.preparation_instructions,
        "default_price": p.default_price,
        "description": p.description,
        "created_at": getattr(p, "created_at", None),
    }


def _order_item_dict(i) -> dict:
    return {
        "id": i.id,
        "radiology_order_id": i.radiology_order_id,
        "procedure_catalog_id": i.procedure_catalog_id,
        "status": str(i.status),
        "laterality": i.laterality,
        "notes": i.notes,
        "created_at": getattr(i, "created_at", None),
    }


def _order_dict(o) -> dict:
    return {
        "id": o.id,
        "visit_id": o.visit_id,
        "consultation_id": o.consultation_id,
        "facility_id": o.facility_id,
        "ordered_by_staff_id": o.ordered_by_staff_id,
        "order_no": o.order_no,
        "status": str(o.status),
        "priority": str(o.priority),
        "clinical_indication": o.clinical_indication,
        "pregnancy_screening": o.pregnancy_screening,
        "creatinine_value": o.creatinine_value,
        "ordered_at": o.ordered_at,
        "items": [
            _order_item_dict(i) for i in (o.items or []) if not getattr(i, "is_deleted", False)
        ],
        "created_at": getattr(o, "created_at", None),
        "updated_at": getattr(o, "updated_at", None),
    }


def _exam_dict(e) -> dict:
    return {
        "id": e.id,
        "order_item_id": e.order_item_id,
        "facility_id": e.facility_id,
        "performed_by_staff_id": e.performed_by_staff_id,
        "machine_identifier": e.machine_identifier,
        "accession_number": e.accession_number,
        "status": str(e.status),
        "scheduled_at": e.scheduled_at,
        "started_at": e.started_at,
        "ended_at": e.ended_at,
        "contrast_administered": e.contrast_administered,
        "technical_notes": e.technical_notes,
        "created_at": getattr(e, "created_at", None),
    }


def _image_dict(i) -> dict:
    return {
        "id": i.id,
        "exam_id": i.exam_id,
        "sop_instance_uid": i.sop_instance_uid,
        "series_instance_uid": i.series_instance_uid,
        "study_instance_uid": i.study_instance_uid,
        "image_url": i.image_url,
        "pacs_archive_id": i.pacs_archive_id,
        "image_count": i.image_count,
        "captured_at": i.captured_at,
        "notes": i.notes,
    }


def _report_dict(r) -> dict:
    return {
        "id": r.id,
        "exam_id": r.exam_id,
        "reported_by_staff_id": r.reported_by_staff_id,
        "verified_by_staff_id": r.verified_by_staff_id,
        "status": str(r.status),
        "findings": r.findings,
        "impression": r.impression,
        "recommendations": r.recommendations,
        "drafted_at": r.drafted_at,
        "finalized_at": r.finalized_at,
        "released_at": r.released_at,
    }


# ============================================================
# CATALOG
# ============================================================


@catalog_router.get(
    "/",
    response_model=RadiologyProcedureCatalogListResponseSchema,
    summary="List radiology procedures",
)
def list_procedures(
    _: Annotated[User, Depends(require_permission("RADIOLOGY_ORDER", "RADIOLOGY_PERFORM"))],
    service: Annotated[RadiologyCatalogService, Depends(get_catalog_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    modality: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    items, total = service.list_procedures(skip=skip, limit=limit, modality=modality, search=search)
    return paginate_response(
        items=[_catalog_dict(p) for p in items],
        total=total, skip=skip, limit=limit,
        message="Radiology procedures fetched successfully.",
    )


@catalog_router.post(
    "/",
    response_model=RadiologyProcedureCatalogActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a radiology procedure",
)
def create_procedure(
    payload: RadiologyProcedureCatalogCreateSchema,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_MANAGE"))],
    service: Annotated[RadiologyCatalogService, Depends(get_catalog_service)],
):
    p = service.create(payload)
    return {"success": True, "message": "Radiology procedure created.", "procedure": _catalog_dict(p)}


@catalog_router.get(
    "/{procedure_id}",
    response_model=RadiologyProcedureCatalogReadSchema,
    summary="Get a radiology procedure",
)
def get_procedure(
    procedure_id: int,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_ORDER", "RADIOLOGY_PERFORM"))],
    service: Annotated[RadiologyCatalogService, Depends(get_catalog_service)],
):
    return _catalog_dict(service.get(procedure_id))


@catalog_router.put(
    "/{procedure_id}",
    response_model=RadiologyProcedureCatalogActionResponseSchema,
    summary="Update a radiology procedure",
)
def update_procedure(
    procedure_id: int,
    payload: RadiologyProcedureCatalogUpdateSchema,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_MANAGE"))],
    service: Annotated[RadiologyCatalogService, Depends(get_catalog_service)],
):
    p = service.update(procedure_id, payload)
    return {"success": True, "message": "Radiology procedure updated.", "procedure": _catalog_dict(p)}


@catalog_router.delete(
    "/{procedure_id}",
    summary="Soft-delete a radiology procedure",
)
def soft_delete_procedure(
    procedure_id: int,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_MANAGE"))],
    service: Annotated[RadiologyCatalogService, Depends(get_catalog_service)],
):
    p = service.soft_delete(procedure_id)
    return {"success": True, "message": "Radiology procedure deactivated.", "procedure_id": p.id}


# ============================================================
# ORDERS
# ============================================================


@order_router.get(
    "/visits/{visit_id}",
    response_model=RadiologyOrderListResponseSchema,
    summary="List radiology orders for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_ORDER", "RADIOLOGY_PERFORM", "VISIT_READ"))],
    service: Annotated[RadiologyOrderService, Depends(get_order_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    items, total = service.list_for_visit(visit_id, skip=skip, limit=limit)
    return paginate_response(
        items=[_order_dict(o) for o in items],
        total=total, skip=skip, limit=limit,
        message="Radiology orders fetched successfully.",
    )


@order_router.get(
    "/worklist",
    response_model=RadiologyOrderListResponseSchema,
    summary="Radiology worklist (open orders)",
)
def list_worklist(
    _: Annotated[User, Depends(require_permission("RADIOLOGY_PERFORM"))],
    service: Annotated[RadiologyOrderService, Depends(get_order_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    statuses: Optional[list[str]] = Query(None),
):
    items, total = service.list_worklist(skip=skip, limit=limit, statuses=statuses)
    return paginate_response(
        items=[_order_dict(o) for o in items],
        total=total, skip=skip, limit=limit,
        message="Radiology worklist fetched successfully.",
    )


@order_router.post(
    "/",
    response_model=RadiologyOrderActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a radiology order",
)
def create_order(
    payload: RadiologyOrderCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_ORDER"))],
    service: Annotated[RadiologyOrderService, Depends(get_order_service)],
):
    order = service.create_order(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Radiology order created.", "order": _order_dict(order)}


@order_router.get(
    "/{order_id}",
    response_model=RadiologyOrderReadSchema,
    summary="Get a radiology order",
)
def get_order(
    order_id: int,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_ORDER", "RADIOLOGY_PERFORM", "VISIT_READ"))],
    service: Annotated[RadiologyOrderService, Depends(get_order_service)],
):
    return _order_dict(service.get(order_id))


@order_router.post(
    "/{order_id}/cancel",
    response_model=RadiologyOrderActionResponseSchema,
    summary="Cancel a radiology order",
)
def cancel_order(
    order_id: int,
    payload: RadiologyOrderCancelSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_ORDER"))],
    service: Annotated[RadiologyOrderService, Depends(get_order_service)],
):
    order = service.cancel_order(order_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Radiology order cancelled.", "order": _order_dict(order)}


# ============================================================
# EXAMS
# ============================================================


@exam_router.post(
    "/schedule",
    response_model=RadiologyExamActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule an exam against an order item",
)
def schedule_exam(
    payload: RadiologyExamScheduleSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_PERFORM"))],
    service: Annotated[RadiologyExamService, Depends(get_exam_service)],
):
    e = service.schedule_exam(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Exam scheduled.", "exam": _exam_dict(e)}


@exam_router.post(
    "/{exam_id}/start",
    response_model=RadiologyExamActionResponseSchema,
    summary="Start an exam",
)
def start_exam(
    exam_id: int,
    payload: RadiologyExamStartSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_PERFORM"))],
    service: Annotated[RadiologyExamService, Depends(get_exam_service)],
):
    e = service.start_exam(exam_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Exam started.", "exam": _exam_dict(e)}


@exam_router.post(
    "/{exam_id}/complete",
    response_model=RadiologyExamActionResponseSchema,
    summary="Complete an exam",
)
def complete_exam(
    exam_id: int,
    payload: RadiologyExamCompleteSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_PERFORM"))],
    service: Annotated[RadiologyExamService, Depends(get_exam_service)],
):
    e = service.complete_exam(exam_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Exam completed.", "exam": _exam_dict(e)}


@exam_router.post(
    "/{exam_id}/images",
    response_model=RadiologyImageActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Attach an image to an exam",
)
def attach_image(
    exam_id: int,
    payload: RadiologyImageAttachSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_PERFORM"))],
    service: Annotated[RadiologyExamService, Depends(get_exam_service)],
):
    if payload.exam_id != exam_id:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(
            message="exam_id in payload must match URL.",
            detail={"path_id": exam_id, "payload_id": payload.exam_id},
        )
    img = service.attach_image(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Image attached.", "image": _image_dict(img)}


@exam_router.get(
    "/{exam_id}/images",
    summary="List images attached to an exam",
)
def list_images(
    exam_id: int,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_PERFORM", "RADIOLOGY_REPORT"))],
    service: Annotated[RadiologyExamService, Depends(get_exam_service)],
):
    items = service.list_images(exam_id)
    return {
        "success": True,
        "message": "Images fetched successfully.",
        "items": [_image_dict(i) for i in items],
        "count": len(items),
    }


# ============================================================
# REPORTS
# ============================================================


@report_router.post(
    "/draft",
    response_model=RadiologyReportActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Draft a radiology report",
)
def draft_report(
    payload: RadiologyReportDraftSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_REPORT"))],
    service: Annotated[RadiologyReportService, Depends(get_report_service)],
):
    r = service.draft_report(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Report drafted.", "report": _report_dict(r)}


@report_router.post(
    "/{report_id}/finalize",
    response_model=RadiologyReportActionResponseSchema,
    summary="Finalize a radiology report (4-eyes)",
)
def finalize_report(
    report_id: int,
    payload: RadiologyReportFinalizeSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_REPORT"))],
    service: Annotated[RadiologyReportService, Depends(get_report_service)],
):
    r = service.finalize_report(report_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Report finalized.", "report": _report_dict(r)}


@report_router.post(
    "/{report_id}/release",
    response_model=RadiologyReportActionResponseSchema,
    summary="Release a finalized radiology report",
)
def release_report(
    report_id: int,
    payload: RadiologyReportReleaseSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_RELEASE"))],
    service: Annotated[RadiologyReportService, Depends(get_report_service)],
):
    r = service.release_report(report_id, payload, actor_user_id=actor.id)
    return {"success": True, "message": "Report released.", "report": _report_dict(r)}


@report_router.get(
    "/{report_id}",
    response_model=RadiologyReportReadSchema,
    summary="Get a radiology report",
)
def get_report(
    report_id: int,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_REPORT", "RADIOLOGY_RELEASE"))],
    service: Annotated[RadiologyReportService, Depends(get_report_service)],
):
    return _report_dict(service.get(report_id))


@report_router.get(
    "/exams/{exam_id}",
    response_model=RadiologyReportReadSchema,
    summary="Get the report for a given exam",
)
def get_report_for_exam(
    exam_id: int,
    _: Annotated[User, Depends(require_permission("RADIOLOGY_REPORT", "RADIOLOGY_RELEASE"))],
    service: Annotated[RadiologyReportService, Depends(get_report_service)],
):
    r = service.get_for_exam(exam_id)
    if r is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="No report yet for this exam.")
    return _report_dict(r)
