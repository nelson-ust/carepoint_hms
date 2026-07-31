from typing import Annotated, Any

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.schemas.reimbursement_schemas import (
    ReimbursementCreateSchema,
    ReimbursementReadSchema,
    ReimbursementUpdateSchema,
    ReimbursementSelfCreateSchema,
    ReimbursementSubmitSchema
)
from app.services.reimbursement_service import ReimbursementService
from app.core.exceptions import BadRequestError

router = APIRouter(
    prefix="/reimbursements",
    tags=["Reimbursements"],
    dependencies=[Depends(require_plan_feature("hr"))]
)

def get_reimbursement_service(db: Annotated[Session, Depends(get_db)]) -> ReimbursementService:
    return ReimbursementService(db)


def _reimb_read(req) -> ReimbursementReadSchema:
    """Serialize a claim, presigning the stored receipt for viewing."""
    out = ReimbursementReadSchema.model_validate(req)
    if req.receipt_url:
        try:
            from app.utils.s3_utils import presign_stored_url
            out.receipt_display_url = presign_stored_url(req.receipt_url)
        except Exception:  # pragma: no cover
            out.receipt_display_url = None
    return out

@router.post(
    "",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new reimbursement request",
)
def create_reimbursement(
    payload: ReimbursementCreateSchema,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    req = service.create_reimbursement(payload)
    return {
        "success": True,
        "message": "Reimbursement request created successfully.",
        "reimbursement": _reimb_read(req),
    }

@router.get(
    "",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List reimbursement requests",
)
def list_reimbursements(
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
    staff_profile_id: int = Query(None, description="Filter by staff profile ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    items, total = service.list_reimbursements(staff_profile_id=staff_profile_id, skip=skip, limit=limit)
    return {
        "success": True,
        "total": total,
        "items": [_reimb_read(req) for req in items],
    }

@router.get(
    "/me",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="List my own expense claims",
)
def list_my_reimbursements(
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    items, total = service.list_my_reimbursements(user_id=current_user.id, skip=skip, limit=limit)
    return {
        "success": True,
        "total": total,
        "items": [_reimb_read(req) for req in items],
    }

@router.post(
    "/me",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Create my own expense claim",
)
def create_my_reimbursement(
    payload: ReimbursementSelfCreateSchema,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    req = service.create_my_reimbursement(payload, user_id=current_user.id)
    return {
        "success": True,
        "message": "Expense claim created successfully.",
        "reimbursement": _reimb_read(req),
    }

@router.post(
    "/me/receipt",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Upload an expense receipt to the tenant's S3 bucket",
)
async def upload_my_receipt(
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
    file: UploadFile = File(..., description="Receipt image or PDF"),
):
    """
    Store the receipt in the TENANT's own bucket and return its permanent URL.
    The client then creates/updates the claim with ``receipt_url``.
    """
    from app.core.database import get_master_db_context
    from app.core.multitenancy import get_current_tenant
    from app.models.all_models import Tenant
    from app.services.aws_s3_service import S3Service

    tenant = get_current_tenant()
    if tenant is None:
        raise BadRequestError(message="Tenant context is required to upload a receipt.")

    s3_service = S3Service()
    with get_master_db_context() as master_db:
        master_tenant = master_db.query(Tenant).filter(Tenant.code == tenant.code).first()
        bucket = s3_service.ensure_tenant_bucket(master_db, master_tenant)
    if not getattr(s3_service, "is_enabled", False) or not bucket:
        raise BadRequestError(message="File storage is not configured for this tenant. Contact your administrator.")

    file_ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if file_ext not in {"png", "jpg", "jpeg", "webp", "gif", "pdf"}:
        raise BadRequestError(message="Only PNG, JPG, WEBP, GIF or PDF receipts are supported.")

    s3_key = f"receipts/user-{current_user.id}-{uuid.uuid4().hex}.{file_ext}"
    try:
        url = s3_service.upload_file(bucket, file, s3_key)
    except RuntimeError as exc:
        raise BadRequestError(message=f"Receipt upload failed: {s3_service.last_error or exc}")
    if not url:
        raise BadRequestError(message="Failed to upload the receipt.")
    return {"success": True, "receipt_url": url}


@router.post(
    "/me/{request_id}/submit",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Submit my own expense claim for approval",
)
def submit_my_reimbursement(
    request_id: int,
    payload: ReimbursementSubmitSchema,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    req = service.submit_my_reimbursement(request_id, payload, user_id=current_user.id)
    return {
        "success": True,
        "message": "Expense claim submitted for approval.",
        "reimbursement": _reimb_read(req),
    }

@router.delete(
    "/me/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete my own draft expense claim",
)
def delete_my_reimbursement(
    request_id: int,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    service.delete_my_reimbursement(request_id, user_id=current_user.id)

@router.get(
    "/{request_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get reimbursement request by ID",
)
def get_reimbursement(
    request_id: int,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    req = service.get_reimbursement(request_id)
    return {
        "success": True,
        "reimbursement": _reimb_read(req),
    }

@router.put(
    "/{request_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Update a reimbursement request",
)
def update_reimbursement(
    request_id: int,
    payload: ReimbursementUpdateSchema,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    req = service.update_reimbursement(request_id, payload)
    return {
        "success": True,
        "message": "Reimbursement request updated successfully.",
        "reimbursement": _reimb_read(req),
    }

@router.delete(
    "/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a reimbursement request",
)
def delete_reimbursement(
    request_id: int,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    service.delete_reimbursement(request_id)

@router.post(
    "/{request_id}/submit",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Submit a reimbursement request for approval",
)
def submit_reimbursement(
    request_id: int,
    payload: ReimbursementSubmitSchema,
    service: Annotated[ReimbursementService, Depends(get_reimbursement_service)],
    current_user: CurrentActiveUser,
):
    req = service.submit_reimbursement(request_id, payload, user_id=current_user.id)
    return {
        "success": True,
        "message": "Reimbursement request submitted for approval.",
        "reimbursement": _reimb_read(req),
    }
