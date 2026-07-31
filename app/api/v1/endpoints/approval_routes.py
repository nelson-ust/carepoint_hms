# app/api/v1/endpoints/approval_routes.py
from __future__ import annotations

"""
Generic approval-engine API.

* Request types + flow configuration require ``AdminUser``.
* Submitting / deciding / cancelling requires ``CurrentActiveUser``; the
  engine enforces per-step approver eligibility.
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AdminUser, CurrentActiveUser
from app.core.enums import ApprovalRequestStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import ApprovalRequest, ApprovalFlow, Role, User
from app.schemas.approval_schemas import (
    ApprovalDecisionCreateSchema,
    ApprovalFlowCreateSchema,
    ApprovalFlowReadSchema,
    ApprovalFlowUpdateSchema,
    ApprovalLogReadSchema,
    ApprovalRequestCreateSchema,
    ApprovalRequestListResponse,
    ApprovalRequestReadSchema,
    ApprovalStepReadSchema,
    RequestTypeCreateSchema,
    RequestTypeReadSchema,
)
from app.services.approval_service import (
    ApprovalFlowService,
    ApprovalRequestService,
    RequestTypeService,
)
from app.utils.pagination import paginate_response
from app.utils import approval_import

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def _flow_svc(db: Annotated[Session, Depends(get_db)]) -> ApprovalFlowService:
    return ApprovalFlowService(db)


def _req_svc(db: Annotated[Session, Depends(get_db)]) -> ApprovalRequestService:
    return ApprovalRequestService(db)


def _type_svc(db: Annotated[Session, Depends(get_db)]) -> RequestTypeService:
    return RequestTypeService(db)


# ── bulk import helpers ──────────────────────────────────────────────

_XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _read_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise BadRequestError(message="Please upload the .xlsx template file.")
    content = await file.read()
    if not content:
        raise BadRequestError(message="The uploaded file is empty.")
    return content




# ── serialization helpers ────────────────────────────────────────────

def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return None
    return f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username


def _flow_read(flow: ApprovalFlow) -> ApprovalFlowReadSchema:
    return ApprovalFlowReadSchema(
        id=flow.id,
        request_type_id=flow.request_type_id,
        request_type_code=getattr(flow.request_type, "code", None),
        code=flow.code,
        name=flow.name,
        description=flow.description,
        is_default=flow.is_default,
        is_active=flow.is_active,
        steps=[ApprovalStepReadSchema.model_validate(s) for s in sorted(flow.steps, key=lambda x: x.step_order)],
    )


def _actor_media_map(db: Session, user_ids: set[int]) -> dict[int, tuple[Optional[str], Optional[str]]]:
    """Presigned (photo, signature) for the request's actors — one presign per asset."""
    ids = {i for i in user_ids if i}
    if not ids:
        return {}
    try:
        from app.utils.s3_utils import presign_stored_url
        rows = db.query(User.id, User.profile_photo_url, User.signature_url).filter(User.id.in_(ids)).all()
        return {
            uid: (
                presign_stored_url(photo) if photo else None,
                presign_stored_url(sig) if sig else None,
            )
            for uid, photo, sig in rows
        }
    except Exception:  # pragma: no cover - media must never break the read
        return {}


def _request_read(db: Session, svc: ApprovalRequestService, req: ApprovalRequest) -> ApprovalRequestReadSchema:
    steps = svc.steps_for(req)
    current_name = next((s.name for s in steps if s.step_order == req.current_step_order), None)
    media = _actor_media_map(
        db,
        {req.requester_user_id, req.assigned_approver_user_id}
        | {l.actor_user_id for l in req.logs},
    )
    _photo = lambda uid: media.get(uid, (None, None))[0]
    _sig = lambda uid: media.get(uid, (None, None))[1]
    logs = [
        ApprovalLogReadSchema(
            id=l.id,
            step_order=l.step_order,
            step_name=l.step_name,
            action=l.action,
            actor_user_id=l.actor_user_id,
            actor_name=_user_name(db, l.actor_user_id),
            actor_photo_url=_photo(l.actor_user_id),
            actor_signature_url=_sig(l.actor_user_id),
            comment=l.comment,
            resulting_status=l.resulting_status,
            created_at=getattr(l, "created_at_ts", None) or getattr(l, "date_created", None),
        )
        for l in sorted(req.logs, key=lambda x: x.id)
    ]
    return ApprovalRequestReadSchema(
        id=req.id,
        request_type_code=req.request_type_code,
        flow_id=req.flow_id,
        flow_name=getattr(req.flow, "name", None),
        subject_id=req.subject_id,
        requester_user_id=req.requester_user_id,
        requester_name=_user_name(db, req.requester_user_id),
        requester_photo_url=_photo(req.requester_user_id),
        requester_signature_url=_sig(req.requester_user_id),
        assigned_approver_user_id=req.assigned_approver_user_id,
        assigned_approver_name=_user_name(db, req.assigned_approver_user_id),
        assigned_approver_photo_url=_photo(req.assigned_approver_user_id),
        assigned_approver_signature_url=_sig(req.assigned_approver_user_id),
        title=req.title,
        description=req.description,
        payload=req.payload,
        status=req.status,
        current_step_order=req.current_step_order,
        current_step_name=current_name,
        submitted_at=req.submitted_at,
        completed_at=req.completed_at,
        decision_summary=req.decision_summary,
        steps=[ApprovalStepReadSchema.model_validate(s) for s in steps],
        logs=logs,
        created_at=getattr(req, "date_created", None),
    )


# ── Request types ────────────────────────────────────────────────────

@router.get("/request-types", response_model=list[RequestTypeReadSchema], summary="List request types")
def list_request_types(_: CurrentActiveUser, svc: Annotated[RequestTypeService, Depends(_type_svc)], only_active: bool = False):
    return svc.list(only_active=only_active)


@router.post("/request-types", response_model=RequestTypeReadSchema, status_code=status.HTTP_201_CREATED, summary="Create a request type")
def create_request_type(payload: RequestTypeCreateSchema, _: AdminUser, svc: Annotated[RequestTypeService, Depends(_type_svc)]):
    return svc.create(**payload.model_dump())


@router.get("/request-types/template", summary="Download the bulk request-type upload template")
def download_request_type_template(_: CurrentActiveUser):
    content = approval_import.build_request_type_template()
    return StreamingResponse(
        iter([content]), media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="request_types_template.xlsx"'},
    )


@router.post("/request-types/bulk-upload", summary="Bulk-upload request types from a filled template")
async def bulk_upload_request_types(
    _: AdminUser,
    svc: Annotated[RequestTypeService, Depends(_type_svc)],
    file: UploadFile = File(..., description="Filled .xlsx template"),
):
    content = await _read_upload(file)
    try:
        rows = approval_import.parse_request_type_rows(content)
    except ValueError as exc:
        raise BadRequestError(message=str(exc))
    return svc.bulk_create(rows)


@router.get(
    "/request-types/{code}/first-step-approvers",
    summary="Eligible approvers for the first step of a request type's flow",
)
def first_step_approvers(
    code: str,
    actor: CurrentActiveUser,
    svc: Annotated[ApprovalRequestService, Depends(_req_svc)],
    flow_id: Optional[int] = None,
):
    """Used by the submit dialog: the requester picks who actions step one."""
    return svc.first_step_approvers(code, flow_id=flow_id, exclude_user_id=actor.id)


# ── Flows ────────────────────────────────────────────────────────────

@router.get("/flows", response_model=list[ApprovalFlowReadSchema], summary="List approval flows")
def list_flows(_: CurrentActiveUser, svc: Annotated[ApprovalFlowService, Depends(_flow_svc)], request_type: Optional[str] = None):
    return [_flow_read(f) for f in svc.list_flows(request_type=request_type)]


@router.post("/flows", response_model=ApprovalFlowReadSchema, status_code=status.HTTP_201_CREATED, summary="Create a flow with steps")
def create_flow(payload: ApprovalFlowCreateSchema, _: AdminUser, svc: Annotated[ApprovalFlowService, Depends(_flow_svc)]):
    return _flow_read(svc.create(payload))


@router.get("/flows/template", summary="Download the bulk approval-flow upload template")
def download_flow_template(_: CurrentActiveUser, type_svc: Annotated[RequestTypeService, Depends(_type_svc)]):
    request_types = [(t.code, t.name) for t in type_svc.list()]
    content = approval_import.build_flow_template(request_types)
    return StreamingResponse(
        iter([content]), media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="approval_flows_template.xlsx"'},
    )


@router.post("/flows/bulk-upload", summary="Bulk-upload approval flows from a filled template")
async def bulk_upload_flows(
    _: AdminUser,
    svc: Annotated[ApprovalFlowService, Depends(_flow_svc)],
    file: UploadFile = File(..., description="Filled .xlsx template"),
):
    content = await _read_upload(file)
    try:
        rows = approval_import.parse_flow_rows(content)
    except ValueError as exc:
        raise BadRequestError(message=str(exc))
    return svc.bulk_create_flows(rows)


@router.get("/steps/template", summary="Download the bulk approval-step upload template")
def download_step_template(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    flow_svc: Annotated[ApprovalFlowService, Depends(_flow_svc)],
    type_svc: Annotated[RequestTypeService, Depends(_type_svc)],
):
    code_by_type = {t.id: t.code for t in type_svc.list()}
    flows = [
        (code_by_type.get(f.request_type_id, ""), f.code, f.name)
        for f in flow_svc.list_flows()
    ]
    roles = [(r.code, r.name) for r in db.query(Role).order_by(Role.code.asc()).all()]
    content = approval_import.build_step_template(flows, roles)
    return StreamingResponse(
        iter([content]), media_type=_XLSX_MEDIA,
        headers={"Content-Disposition": 'attachment; filename="approval_steps_template.xlsx"'},
    )


@router.post("/steps/bulk-upload", summary="Bulk-upload approval steps from a filled template")
async def bulk_upload_steps(
    _: AdminUser,
    svc: Annotated[ApprovalFlowService, Depends(_flow_svc)],
    file: UploadFile = File(..., description="Filled .xlsx template"),
):
    content = await _read_upload(file)
    try:
        rows = approval_import.parse_step_rows(content)
    except ValueError as exc:
        raise BadRequestError(message=str(exc))
    return svc.bulk_create_steps(rows)


@router.get("/flows/{flow_id}", response_model=ApprovalFlowReadSchema, summary="Read a flow")
def get_flow(flow_id: int, _: CurrentActiveUser, svc: Annotated[ApprovalFlowService, Depends(_flow_svc)]):
    return _flow_read(svc.get(flow_id))


@router.put("/flows/{flow_id}", response_model=ApprovalFlowReadSchema, summary="Update a flow (and optionally replace steps)")
def update_flow(flow_id: int, payload: ApprovalFlowUpdateSchema, _: AdminUser, svc: Annotated[ApprovalFlowService, Depends(_flow_svc)]):
    return _flow_read(svc.update(flow_id, payload))


@router.delete("/flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete (soft) a flow")
def delete_flow(flow_id: int, _: AdminUser, svc: Annotated[ApprovalFlowService, Depends(_flow_svc)]):
    svc.soft_delete(flow_id)
    return None


# ── Requests ─────────────────────────────────────────────────────────

@router.get("/requests", response_model=ApprovalRequestListResponse, summary="List approval requests")
def list_requests(
    _: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    svc: Annotated[ApprovalRequestService, Depends(_req_svc)],
    request_type: Optional[str] = None,
    request_status: Optional[ApprovalRequestStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    rows, total = svc.list_requests(request_type=request_type, status=request_status, skip=skip, limit=limit)
    items = [_request_read(db, svc, r) for r in rows]
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Approval requests fetched.")


@router.get("/requests/mine", response_model=list[ApprovalRequestReadSchema], summary="Requests I raised")
def list_my_requests(actor: CurrentActiveUser, db: Annotated[Session, Depends(get_db)], svc: Annotated[ApprovalRequestService, Depends(_req_svc)]):
    rows, _total = svc.list_requests(requester_user_id=getattr(actor, "id", None), limit=200)
    return [_request_read(db, svc, r) for r in rows]


@router.get("/requests/pending", response_model=list[ApprovalRequestReadSchema], summary="Requests awaiting my decision")
def list_pending(actor: CurrentActiveUser, db: Annotated[Session, Depends(get_db)], svc: Annotated[ApprovalRequestService, Depends(_req_svc)]):
    return [_request_read(db, svc, r) for r in svc.list_my_pending(getattr(actor, "id", 0))]


@router.post("/requests", response_model=ApprovalRequestReadSchema, status_code=status.HTTP_201_CREATED, summary="Submit a new approval request")
def submit_request(payload: ApprovalRequestCreateSchema, actor: CurrentActiveUser, db: Annotated[Session, Depends(get_db)], svc: Annotated[ApprovalRequestService, Depends(_req_svc)]):
    req = svc.submit(payload, requester_user_id=getattr(actor, "id", 0))
    if req is None:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(message="Could not submit the approval request.")
    return _request_read(db, svc, svc.get(req.id))


@router.get("/requests/{request_id}", response_model=ApprovalRequestReadSchema, summary="Read a request with steps + logs")
def get_request(request_id: int, _: CurrentActiveUser, db: Annotated[Session, Depends(get_db)], svc: Annotated[ApprovalRequestService, Depends(_req_svc)]):
    return _request_read(db, svc, svc.get(request_id))


@router.post("/requests/{request_id}/decisions", response_model=ApprovalRequestReadSchema, summary="Record an action (APPROVE/RETURN/REJECT/COMMENT/CANCEL) on the active step")
def decide_request(request_id: int, payload: ApprovalDecisionCreateSchema, actor: CurrentActiveUser, db: Annotated[Session, Depends(get_db)], svc: Annotated[ApprovalRequestService, Depends(_req_svc)]):
    svc.decide(request_id, payload, actor_user_id=getattr(actor, "id", 0))
    return _request_read(db, svc, svc.get(request_id))


@router.post("/requests/{request_id}/cancel", response_model=ApprovalRequestReadSchema, summary="Cancel a request")
def cancel_request(request_id: int, actor: CurrentActiveUser, db: Annotated[Session, Depends(get_db)], svc: Annotated[ApprovalRequestService, Depends(_req_svc)]):
    svc.cancel(request_id, actor_user_id=getattr(actor, "id", 0))
    return _request_read(db, svc, svc.get(request_id))
