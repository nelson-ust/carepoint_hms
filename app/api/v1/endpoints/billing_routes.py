# app/api/v1/endpoints/billing_routes.py
from __future__ import annotations

from typing import Annotated, Optional
from decimal import Decimal
from pydantic import BaseModel

from io import BytesIO

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.core.exceptions import BadRequestError
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.billing_schemas import (
    BillableServiceActionResponseSchema,
    BillingMappingHealthSchema,
    BillableServiceCreateSchema,
    BillableServiceListResponseSchema,
    BillableServiceReadSchema,
    BillableServiceUpdateSchema,
    BillingActionResponseSchema,
    BillingCreateSchema,
    BillingItemCreateSchema,
    BillingListResponseSchema,
    BillingReadSchema,
    VisitBillingSummarySchema,
    VisitFinalizeSchema,
    VisitPaymentCreateSchema,
)
from app.schemas.account_schemas import (
    AccountActionResponseSchema,
    AccountCreateSchema,
    AccountListResponseSchema,
    AccountUpdateSchema,
)
from app.services.account_service import AccountService
from app.services.billing_service import BillableServiceService, BillingService
from app.services.invoice_service import InvoiceService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/billing", 
    tags=["Billing"],
    dependencies=[Depends(require_plan_feature("billing"))]
)


def get_billable_service_service(db: Annotated[Session, Depends(get_db)]) -> BillableServiceService:
    return BillableServiceService(db)


def get_billing_service(db: Annotated[Session, Depends(get_db)]) -> BillingService:
    return BillingService(db)


def get_account_service(db: Annotated[Session, Depends(get_db)]) -> AccountService:
    return AccountService(db)


# --- BILLABLE SERVICES ---

@router.get(
    "/services",
    response_model=BillableServiceListResponseSchema,
    summary="List billable services",
)
def list_services(
    _: Annotated[User, Depends(require_permission("BILLING_READ", "BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    items, total = service.list(skip=skip, limit=limit, search=search, category=category)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Billable services fetched successfully.",
    )


@router.post(
    "/services",
    response_model=BillableServiceActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a billable service",
)
def create_billable_service(
    payload: BillableServiceCreateSchema,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
):
    s = service.create(payload)
    return {"success": True, "message": "Billable service created.", "service": s}


@router.get(
    "/services/template",
    summary="Download the billable-services upload template",
)
def download_service_template(
    _: Annotated[User, Depends(require_permission("BILLING_READ", "BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
):
    content = service.build_import_template()
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="billable_services_template.xlsx"'},
    )


@router.get(
    "/services/mapping-health",
    response_model=BillingMappingHealthSchema,
    summary="Billable services still missing a ledger account",
)
def billable_services_mapping_health(
    _: Annotated[User, Depends(require_permission("BILLING_READ", "BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
):
    return service.mapping_health()


@router.post(
    "/services/bulk-upload",
    summary="Bulk-upload billable services from a filled template",
)
async def bulk_upload_services(
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
    file: UploadFile = File(..., description="Filled .xlsx template"),
):
    from app.utils.account_import import parse_billable_service_rows

    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".xlsm")):
        raise BadRequestError(message="Please upload the .xlsx template file.")
    content = await file.read()
    if not content:
        raise BadRequestError(message="The uploaded file is empty.")
    try:
        rows = parse_billable_service_rows(content)
    except ValueError as exc:
        raise BadRequestError(message=str(exc))
    except Exception:
        raise BadRequestError(message="Could not read the spreadsheet. Please upload the provided .xlsx template.")
    return service.bulk_create(rows)


@router.put(
    "/services/{sid}",
    response_model=BillableServiceActionResponseSchema,
    summary="Update a billable service",
)
def update_billable_service(
    sid: int,
    payload: BillableServiceUpdateSchema,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
):
    s = service.update(sid, payload)
    return {"success": True, "message": "Billable service updated.", "service": s}


@router.delete(
    "/services/{sid}",
    summary="Soft-delete a billable service",
)
def delete_billable_service(
    sid: int,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillableServiceService, Depends(get_billable_service_service)],
):
    s = service.soft_delete(sid)
    return {"success": True, "message": "Billable service deactivated.", "service_id": s.id}


# --- CHART OF ACCOUNTS ---

@router.get(
    "/accounts",
    response_model=AccountListResponseSchema,
    summary="List chart-of-accounts",
)
def list_accounts(
    _: Annotated[User, Depends(require_permission("BILLING_READ", "BILLING_CREATE"))],
    service: Annotated[AccountService, Depends(get_account_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    search: Optional[str] = Query(None),
    account_type: Optional[str] = Query(None),
):
    items, total = service.list(skip=skip, limit=limit, search=search, account_type=account_type)
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Accounts fetched successfully.",
    )


@router.post(
    "/accounts",
    response_model=AccountActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
def create_account(
    payload: AccountCreateSchema,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[AccountService, Depends(get_account_service)],
):
    a = service.create(payload)
    return {"success": True, "message": "Account created.", "account": a}


@router.get(
    "/accounts/template",
    summary="Download the chart-of-accounts upload template",
)
def download_account_template(
    _: Annotated[User, Depends(require_permission("BILLING_READ", "BILLING_CREATE"))],
    service: Annotated[AccountService, Depends(get_account_service)],
):
    content = service.build_import_template()
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="chart_of_accounts_template.xlsx"'},
    )


@router.post(
    "/accounts/bulk-upload",
    summary="Bulk-upload accounts from a filled template",
)
async def bulk_upload_accounts(
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[AccountService, Depends(get_account_service)],
    file: UploadFile = File(..., description="Filled .xlsx template"),
):
    from app.utils.account_import import parse_account_rows

    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".xlsm")):
        raise BadRequestError(message="Please upload the .xlsx template file.")
    content = await file.read()
    if not content:
        raise BadRequestError(message="The uploaded file is empty.")
    try:
        rows = parse_account_rows(content)
    except ValueError as exc:
        raise BadRequestError(message=str(exc))
    except Exception:
        raise BadRequestError(message="Could not read the spreadsheet. Please upload the provided .xlsx template.")
    return service.bulk_create(rows)


@router.put(
    "/accounts/{aid}",
    response_model=AccountActionResponseSchema,
    summary="Update an account",
)
def update_account(
    aid: int,
    payload: AccountUpdateSchema,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[AccountService, Depends(get_account_service)],
):
    a = service.update(aid, payload)
    return {"success": True, "message": "Account updated.", "account": a}


@router.delete(
    "/accounts/{aid}",
    summary="Soft-delete an account",
)
def delete_account(
    aid: int,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[AccountService, Depends(get_account_service)],
):
    a = service.soft_delete(aid)
    return {"success": True, "message": "Account deactivated.", "account_id": a.id}


# --- BILLINGS ---

@router.get(
    "/",
    response_model=BillingListResponseSchema,
    summary="List billings",
)
def list_billings(
    _: Annotated[User, Depends(require_permission("BILLING_READ"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    patient_id: Optional[int] = Query(None),
    visit_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    items, total = service.list_billings(
        skip=skip, limit=limit, patient_id=patient_id, visit_id=visit_id, status=status_filter,
    )
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Billings fetched successfully.",
    )


@router.get(
    "/visits/{visit_id}",
    response_model=BillingListResponseSchema,
    summary="List billings for a visit",
)
def list_for_visit(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    items = service.list_for_visit(visit_id)
    return paginate_response(
        items=items,
        total=len(items),
        skip=0,
        limit=len(items) or 1,
        message="Billings fetched successfully.",
    )


# --- VISIT CHARGE SHEET: summary, partial payments, finalize invoice ---

@router.get(
    "/visits/{visit_id}/summary",
    response_model=VisitBillingSummarySchema,
    summary="Visit billing summary (charges, paid, outstanding)",
)
def visit_billing_summary(
    visit_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    return service.get_visit_billing_summary(visit_id)


@router.post(
    "/visits/{visit_id}/payments",
    response_model=VisitBillingSummarySchema,
    status_code=status.HTTP_201_CREATED,
    summary="Record a partial payment against a visit's charges",
)
def receive_visit_payment(
    visit_id: int,
    payload: VisitPaymentCreateSchema,
    user: Annotated[User, Depends(require_permission("PAYMENT_RECEIVE", "BILLING_CREATE"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    service.receive_visit_payment(
        visit_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        payment_reference=payload.payment_reference,
        received_by_staff_id=payload.received_by_staff_id,
        membership_card_id=payload.membership_card_id,
        note=payload.note,
        actor_user_id=user.id,
    )
    # Electronic delivery: updated invoice + payment confirmation to the
    # patient (best-effort; never blocks the payment itself).
    _deliver_invoice_to_patient(
        _get_db_from_service(service), service, visit_id,
        reason="updated with your payment", actor_user_id=user.id,
    )
    return service.get_visit_billing_summary(visit_id)


def _get_db_from_service(service: BillingService) -> Session:
    return service.db


@router.post(
    "/visits/{visit_id}/finalize",
    summary="Finalize a visit's billing and issue the invoice",
)
def finalize_visit_billing(
    visit_id: int,
    user: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    db: Annotated[Session, Depends(get_db)],
    payload: Optional[VisitFinalizeSchema] = None,
):
    invoice = InvoiceService(db).issue_for_visit(
        visit_id,
        actor_user_id=user.id,
        due_date=payload.due_date if payload else None,
        note=payload.note if payload else None,
        payer_id=payload.payer_id if payload else None,
    )
    # Electronic delivery: email the branded invoice PDF to the patient and
    # raise a portal notification (best-effort).
    _deliver_invoice_to_patient(
        db, BillingService(db), visit_id,
        reason="issued", actor_user_id=user.id,
    )
    return {
        "success": True,
        "message": f"Invoice {invoice.invoice_no} issued for the visit.",
        "invoice_id": invoice.id,
        "invoice_no": invoice.invoice_no,
        "total_amount": float(invoice.total_amount or 0),
        "amount_paid": float(invoice.amount_paid or 0),
        "balance_due": float(invoice.balance_due or 0),
        "status": invoice.status.value if hasattr(invoice.status, "value") else str(invoice.status),
    }


@router.post(
    "/",
    response_model=BillingActionResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a billing",
)
def create_billing(
    payload: BillingCreateSchema,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    b = service.create_billing(payload)
    return {"success": True, "message": "Billing created.", "billing": b}


@router.get(
    "/{billing_id}",
    response_model=BillingReadSchema,
    summary="Get a billing",
)
def get_billing(
    billing_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_READ"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    return service.get(billing_id)


@router.post(
    "/{billing_id}/items",
    response_model=BillingActionResponseSchema,
    summary="Add a charge line to a billing",
)
def add_item(
    billing_id: int,
    payload: BillingItemCreateSchema,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    b = service.add_item(billing_id, payload)
    return {"success": True, "message": "Item added to billing.", "billing": b}


class _RecordedServiceLine(BaseModel):
    billable_service_id: Optional[int] = None
    service_name: Optional[str] = None
    service_code: Optional[str] = None
    quantity: Decimal = Decimal("1")
    unit_price: Optional[Decimal] = None
    discount_amount: Decimal = Decimal("0")


class RecordServicesRequestSchema(BaseModel):
    """Services rendered at the current service delivery point, captured from
    the Patient Queue."""
    service_delivery_point_id: Optional[int] = None
    items: list[_RecordedServiceLine] = []


@router.post(
    "/visits/{visit_id}/record-services",
    summary="Record services rendered for a visit at the current service point",
)
def record_visit_services(
    visit_id: int,
    payload: RecordServicesRequestSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    """Capture one or more services rendered onto the visit's running charge
    sheet (creating it if needed), each stamped with the service delivery point
    and the recording user. Returns the refreshed billing summary."""
    result = service.record_visit_services(
        visit_id,
        [i.model_dump() for i in payload.items],
        service_delivery_point_id=payload.service_delivery_point_id,
        rendered_by_user_id=getattr(actor, "id", None),
    )
    return {"success": True,
            "message": f"{result['recorded']} service(s) recorded.",
            **result}



@router.post(
    "/{billing_id}/cancel",
    response_model=BillingActionResponseSchema,
    summary="Cancel a billing",
)
def cancel_billing(
    billing_id: int,
    _: Annotated[User, Depends(require_permission("BILLING_CREATE"))],
    service: Annotated[BillingService, Depends(get_billing_service)],
    reason: Optional[str] = Query(None, max_length=500),
):
    b = service.cancel_billing(billing_id, reason=reason)
    return {"success": True, "message": "Billing cancelled.", "billing": b}


# ---------------------------------------------------------------------------
# Branded visit invoice PDF
# ---------------------------------------------------------------------------

def _render_visit_invoice_pdf(db: Session, service: BillingService,
                              visit_id: int) -> tuple[bytes, dict]:
    """Assemble the branded consolidated invoice PDF for a visit.

    Returns (pdf_bytes, billing_summary). Shared by the staff download
    endpoint, the automatic patient email delivery, and the portal download.
    """
    from datetime import datetime, timezone
    from app.api.v1.endpoints.hr_routes import _load_tenant_logo_path
    from app.core.exceptions import NotFoundError
    from app.core.multitenancy import get_current_tenant
    from app.models.all_models import Patient, Visit
    from app.utils.invoice_pdf import build_invoice_pdf, invoice_verify_code

    summary = service.get_visit_billing_summary(visit_id)
    if not summary.get("billing_id"):
        raise NotFoundError(message="No billing exists for this visit yet.")

    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    patient = (
        db.query(Patient).filter(Patient.id == summary.get("patient_id")).first()
        if summary.get("patient_id") else None
    )

    # Group charge lines by service category for the statement.
    grouped: dict[str, list[dict]] = {}
    for it in summary.get("items") or []:
        category = (getattr(it, "category", None) or "Other services").replace("_", " ").title()
        grouped.setdefault(category, []).append({
            "name": it.service_name,
            "code": it.service_code,
            "qty": it.quantity,
            "unit_price": it.unit_price,
            "line_total": it.line_total,
        })
    payments = [{
        "amount": getattr(p, "amount", None),
        "method": str(getattr(getattr(p, "payment_method", None), "value",
                              getattr(p, "payment_method", "")) or ""),
        "paid_at": getattr(p, "payment_date", None) or getattr(p, "date_created", None),
        "reference": getattr(p, "reference", None) or getattr(p, "transaction_reference", None),
    } for p in (summary.get("payments") or [])]

    hospital, contact = "Hospital", None
    try:
        tenant = get_current_tenant()
        if tenant is not None:
            hospital = getattr(tenant, "name", None) or hospital
            contact = getattr(tenant, "contact_email", None) or getattr(tenant, "billing_email", None)
    except Exception:
        pass

    verify = invoice_verify_code(summary["billing_no"], summary.get("total_charges"))
    logo_path = _load_tenant_logo_path(db)
    try:
        pdf_bytes = build_invoice_pdf(
            hospital_name=hospital, hospital_contact=contact, logo_path=logo_path,
            patient={
                "name": " ".join(x for x in (getattr(patient, "first_name", None),
                                             getattr(patient, "last_name", None)) if x) or "-",
                "hospital_number": getattr(patient, "hospital_number", None),
            },
            visit_number=getattr(visit, "visit_number", None) if visit else None,
            billing_no=summary["billing_no"],
            generated_at=datetime.now(timezone.utc),
            grouped_items=sorted(grouped.items()),
            gross=summary.get("gross_amount"), discount=summary.get("discount_amount"),
            total=summary.get("total_charges"), paid=summary.get("amount_paid"),
            outstanding=summary.get("outstanding"), payments=payments,
            verify_code=verify,
        )
    finally:
        if logo_path:
            try:
                import os as _os
                _os.remove(logo_path)
            except OSError:
                pass
    return pdf_bytes, summary


def _deliver_invoice_to_patient(db: Session, service: BillingService,
                                visit_id: int, *, reason: str,
                                actor_user_id=None) -> None:
    """Best-effort electronic delivery: email the branded invoice PDF to the
    patient (with outstanding balance and portal pointer) and raise an
    in-app portal notification. Never fails the calling transaction."""
    import os as _os
    import tempfile as _tempfile
    from app.core.enums import NotificationChannel, NotificationStatus
    from app.core.multitenancy import get_current_tenant
    from app.models.all_models import Notification, Patient
    from app.utils.security_event_util import record_security_event

    try:
        pdf_bytes, summary = _render_visit_invoice_pdf(db, service, visit_id)
        patient = (
            db.query(Patient).filter(Patient.id == summary.get("patient_id")).first()
            if summary.get("patient_id") else None
        )
        if patient is None:
            return
        outstanding = summary.get("outstanding") or 0
        billing_no = summary.get("billing_no") or ""
        hospital = "your hospital"
        try:
            tenant = get_current_tenant()
            if tenant is not None and getattr(tenant, "name", None):
                hospital = tenant.name
        except Exception:
            pass

        # In-app portal notification (delivered/retried by the worker).
        try:
            db.add(Notification(
                patient_id=patient.id, channel=NotificationChannel.IN_APP,
                status=NotificationStatus.PENDING, event_code="INVOICE_" + reason.upper(),
                subject=f"Invoice {billing_no} — {reason}",
                body=(f"Your invoice {billing_no} has been {reason}. "
                      + (f"Outstanding balance: NGN {outstanding}. " if float(outstanding or 0) > 0
                         else "It is fully settled. ")
                      + "Open the patient portal to view and download it."),
                payload_metadata={"visit_id": visit_id, "billing_no": billing_no},
            ))
        except Exception:
            pass

        # Email with the PDF attached (skipped when no address on record).
        email = (getattr(patient, "email", None) or "").strip()
        if email:
            from app.utils.email_utils import (
                render_branded_email, render_branded_email_text, send_email,
            )
            fd, path = _tempfile.mkstemp(suffix=".pdf", prefix=f"invoice-{visit_id}-")
            _os.close(fd)
            try:
                with open(path, "wb") as fh:
                    fh.write(pdf_bytes)
                common = dict(
                    title=f"Your invoice {billing_no}",
                    intro=(f"Your invoice from {hospital} has been {reason}. "
                           + (f"The outstanding balance is NGN {outstanding}."
                              if float(outstanding or 0) > 0
                              else "It is fully settled — thank you.")),
                    details=[("Invoice", billing_no),
                             ("Total", f"NGN {summary.get('total_charges')}"),
                             ("Paid", f"NGN {summary.get('amount_paid')}"),
                             ("Outstanding", f"NGN {outstanding}")],
                    cta_label="Open Patient Portal", cta_url=None,
                    footer_note="The invoice is attached as a PDF. For billing "
                                "enquiries, reply to this email or contact the hospital.",
                )
                send_email(subject=f"{hospital}: invoice {billing_no}",
                           recipients=email,
                           body_text=render_branded_email_text(**common),
                           body_html=render_branded_email(**common),
                           attachments=[path])
            finally:
                try:
                    _os.remove(path)
                except OSError:
                    pass

        record_security_event(
            db, user_id=actor_user_id,
            event_type="INVOICE_DELIVERED", severity="INFO",
            event_detail=f"Invoice {billing_no} {reason}; patient notified"
                         + (" + emailed." if email else " (no email on record)."),
            event_metadata={"visit_id": visit_id, "reason": reason},
        )
        db.commit()
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Invoice delivery for visit %s failed.", visit_id
        )


@router.get(
    "/visits/{visit_id}/invoice.pdf",
    summary="Branded consolidated invoice PDF for a visit",
)
def visit_invoice_pdf(
    visit_id: int,
    actor: CurrentActiveUser,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[BillingService, Depends(get_billing_service)],
):
    from fastapi import Response
    from app.utils.security_event_util import record_security_event

    pdf_bytes, summary = _render_visit_invoice_pdf(db, service, visit_id)
    record_security_event(
        db, user_id=getattr(actor, "id", None),
        event_type="VISIT_INVOICE_PDF_GENERATED", severity="INFO",
        event_detail=f"Invoice PDF for billing {summary['billing_no']} generated.",
        event_metadata={"visit_id": visit_id, "billing_id": summary["billing_id"]},
    )
    db.commit()
    safe = "".join(ch for ch in summary["billing_no"] if ch.isalnum() or ch in "-_")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="invoice-{safe}.pdf"'})
