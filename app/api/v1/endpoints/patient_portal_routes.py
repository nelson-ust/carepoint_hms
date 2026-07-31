# app/api/v1/endpoints/patient_portal_routes.py
from __future__ import annotations

import os
import uuid as _uuid
from typing import List, Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, File, Form, UploadFile, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.dependencies import get_current_user, require_plan_feature

from app.models.all_models import User
from app.services.patient_portal_service import PatientPortalService
from app.services.patient_portal_auth_service import PatientPortalAuthService
from app.services.paystack_service import PaystackService
from app.services.membership_card_service import MembershipCardService
from app.services.auth_service import AuthService
from app.schemas.patient_portal_schemas import (
    PatientPortalDashboard,
    PatientPortalProfile,
    PortalProfileUpdateSchema,
    PatientPortalAppointments,
    PatientPortalBranding,
    PatientFundCardRequest,
    PatientPortalOTPRequest,
    PatientPortalOTPVerify
)
from app.schemas.patient_portal_schema import (
    PatientPortalRequestOtpSchema,
    PatientPortalResendOtpSchema,
    PatientPortalRequestOtpResponseSchema,
    PatientPortalLoginResponseSchema,
    PatientPortalVerifyOtpSchema,
)
from app.schemas.paystack_schemas import PaystackTransactionRead
from app.schemas.membership_card_schemas import CardFundingRequestRead
from app.schemas.notification_schema import (
    NotificationReadSchema,
    NotificationMarkAllReadResponseSchema,
)
from app.schemas.auth_schemas import LoginSuccessSchema, OTPActionResponseSchema, OTPVerificationSuccessSchema
from app.services.patient_broadcast_service import PatientBroadcastService
from app.schemas.patient_broadcast_schemas import (
    PortalInboxMessageRead,
    PortalInboxListResponse,
    PortalInboxUnreadCountResponse,
)
from app.utils.pagination import paginate_response


router = APIRouter(
    prefix="/portal", 
    tags=["Patient Portal"],
    dependencies=[Depends(require_plan_feature("patient_portal"))]
)



def get_portal_service(db: Annotated[Session, Depends(get_db)]) -> PatientPortalService:
    return PatientPortalService(db)


def get_broadcast_service(
    db: Annotated[Session, Depends(get_db)],
) -> PatientBroadcastService:
    return PatientBroadcastService(db)

def get_paystack_service(db: Annotated[Session, Depends(get_db)]) -> PaystackService:
    return PaystackService(db)

def get_card_service(db: Annotated[Session, Depends(get_db)]) -> MembershipCardService:
    return MembershipCardService(db)

def get_auth_service(db: Annotated[Session, Depends(get_db)]) -> AuthService:
    return AuthService(db)


def get_portal_auth_service(
    db: Annotated[Session, Depends(get_db)],
) -> PatientPortalAuthService:
    """
    Auth service for the patient portal.

    Distinct from :class:`AuthService` (which assumes a pre-existing
    :class:`User`). The portal flow can authenticate a patient who has
    never logged in before — it auto-creates the User row on first
    successful OTP verification.
    """
    return PatientPortalAuthService(db)


@router.post(
    "/auth/request-otp",
    response_model=PatientPortalRequestOtpResponseSchema,
    summary="Request a 5-digit OTP for patient portal login",
)
async def request_otp(
    payload: PatientPortalRequestOtpSchema,
    request: Request,
    service: Annotated[PatientPortalAuthService, Depends(get_portal_auth_service)],
):
    """
    Generate and dispatch a 5-digit OTP to the patient via email or SMS.

    The patient is identified by email, phone, or hospital number. The OTP
    is short-lived (10 minutes) and is hashed at rest — only the patient
    receives the plaintext via the chosen channel.
    """
    result = service.request_otp(
        identifier=payload.identifier,
        channel=payload.channel,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {
        "success": True,
        "message": "OTP dispatched. Check your email or SMS for the code.",
        **result,
    }


@router.post(
    "/auth/verify-otp",
    response_model=PatientPortalLoginResponseSchema,
    summary="Verify the OTP and exchange it for a JWT pair",
)
async def verify_otp(
    payload: PatientPortalVerifyOtpSchema,
    request: Request,
    service: Annotated[PatientPortalAuthService, Depends(get_portal_auth_service)],
):
    """
    Verify the OTP and (on success) issue access + refresh tokens for the
    patient portal. If the patient has no linked :class:`User` yet, one
    is auto-created and assigned the ``PATIENT`` role.
    """
    result = service.verify_otp(
        otp_id=payload.otp_id,
        otp_code=payload.otp_code,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {
        "success": True,
        "message": "Patient portal access granted.",
        **result,
    }


@router.post(
    "/auth/resend-otp",
    response_model=PatientPortalRequestOtpResponseSchema,
    summary="Resend the active OTP",
)
async def resend_otp(
    payload: PatientPortalResendOtpSchema,
    request: Request,
    service: Annotated[PatientPortalAuthService, Depends(get_portal_auth_service)],
):
    """
    Re-dispatch the active OTP. A fresh code is generated and the
    expiry window is reset; previous codes are invalidated.
    """
    result = service.resend_otp(
        otp_id=payload.otp_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {
        "success": True,
        "message": "OTP resent. Please use the most recent code.",
        **result,
    }


@router.get("/branding", response_model=PatientPortalBranding)
async def get_branding(
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
):
    """
    Public hospital branding (name, logo, colours) for the portal shell.

    Unauthenticated — resolved from the X-Tenant-Code header — so the portal
    can show the hospital's identity on every page, including before/without a
    patient session.
    """
    return service.get_branding()


@router.get("/dashboard", response_model=PatientPortalDashboard)
async def get_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
):
    """Get summarized dashboard data for the logged-in patient."""
    return service.get_dashboard(current_user.id)


@router.get("/appointments", response_model=PatientPortalAppointments)
async def get_appointments(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
):
    """
    Every appointment the logged-in patient has ever scheduled, grouped into
    the next upcoming one (emphasised in the UI), the rest of the upcoming
    schedule, and past history.
    """
    return service.list_appointments(current_user.id)


@router.get("/profile", response_model=PatientPortalProfile)
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
):
    """Get detailed profile info for the logged-in patient."""
    return service.get_profile(current_user.id)


@router.patch("/profile", response_model=PatientPortalProfile)
async def update_profile(
    payload: PortalProfileUpdateSchema,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
):
    """
    Let the logged-in patient update a safe subset of their own record:
    national ID, contact details, and emergency / next-of-kin information.
    """
    return service.update_profile(current_user.id, payload)


def _patient_photo_storage_dir() -> str:
    """Local storage dir for patient profile photos, served via /uploads."""
    base = getattr(settings, "UPLOADS_DIR", None) or os.path.join(os.getcwd(), "uploads")
    path = os.path.join(base, "patient_photos")
    os.makedirs(path, exist_ok=True)
    return path


@router.post("/profile/photo", response_model=PatientPortalProfile,
             summary="Upload / replace the patient's profile picture")
async def upload_profile_photo(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
    photo: UploadFile = File(...),
):
    """The logged-in patient uploads their own profile picture. Stored locally
    and served via /uploads; the file also feeds the printed membership card."""
    max_bytes = int(getattr(settings, "MAX_UPLOAD_SIZE_MB", 20)) * 1024 * 1024
    raw = await photo.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Image exceeds the {getattr(settings, 'MAX_UPLOAD_SIZE_MB', 20)}MB limit.",
        )

    allowed_ext = {".jpg", ".jpeg", ".png", ".webp"}
    ctype = (photo.content_type or "").lower()
    safe_name = os.path.basename(photo.filename or "photo")
    ext = os.path.splitext(safe_name)[1].lower()[:10]
    if not ctype.startswith("image/") or (ext and ext not in allowed_ext):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a JPG, PNG or WEBP image.",
        )
    if not ext:
        ext = ".png"

    patient = service.get_patient_by_user_id(current_user.id)
    stored_name = f"patient{patient.id}_{_uuid.uuid4().hex[:12]}{ext}"
    dest = os.path.join(_patient_photo_storage_dir(), stored_name)
    with open(dest, "wb") as fh:
        fh.write(raw)
    photo_url = f"/uploads/patient_photos/{stored_name}"

    # ``photo_file_key`` holds the absolute local path so the membership-card
    # PDF generator can read the image directly.
    _patient, previous_key = service.set_profile_photo(
        current_user.id, file_name=safe_name, file_url=photo_url, file_key=dest,
    )

    # Best-effort cleanup of the previous local photo.
    if previous_key and previous_key != dest and os.path.isabs(previous_key):
        try:
            if os.path.exists(previous_key):
                os.remove(previous_key)
        except OSError:
            pass

    return service.get_profile(current_user.id)


@router.get("/invoices", summary="My invoices across all visits")
async def portal_invoices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Every visit bill for the logged-in patient: totals, payments,
    outstanding balance and payment status — for the portal Invoices page."""
    from decimal import Decimal
    from app.models.all_models import Billing, Patient, Visit
    from app.services.billing_service import BillingService

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient is None:
        return {"items": []}
    service = BillingService(db)
    visit_ids = [
        vid for (vid,) in (
            db.query(Billing.visit_id)
            .filter(Billing.patient_id == patient.id, Billing.is_deleted.is_(False))
            .distinct().all()
        ) if vid
    ]
    visits = {
        v.id: v for v in db.query(Visit).filter(Visit.id.in_(visit_ids or [0])).all()
    }
    items = []
    for vid in visit_ids:
        summary = service.get_visit_billing_summary(vid)
        if not summary.get("billing_id"):
            continue
        total = Decimal(str(summary.get("total_charges") or 0))
        paid = Decimal(str(summary.get("amount_paid") or 0))
        outstanding = Decimal(str(summary.get("outstanding") or 0))
        status_label = (
            "PAID" if total > 0 and outstanding <= 0
            else "PARTIALLY_PAID" if paid > 0
            else "UNPAID"
        )
        visit = visits.get(vid)
        items.append({
            "visit_id": vid,
            "visit_number": getattr(visit, "visit_number", None) if visit else None,
            "visit_date": (getattr(visit, "check_in_time", None)
                           or getattr(visit, "date_created", None)) if visit else None,
            "billing_no": summary.get("billing_no"),
            "invoice_no": (summary.get("invoice") or {}).get("invoice_no"),
            "total": str(total), "paid": str(paid), "outstanding": str(outstanding),
            "payment_status": status_label,
            "payments_count": len(summary.get("payments") or []),
        })
    items.sort(key=lambda i: str(i.get("visit_date") or ""), reverse=True)
    return {"items": items}


@router.get("/invoices/{visit_id}/invoice.pdf",
            summary="Download my invoice as a branded PDF")
async def portal_invoice_pdf(
    visit_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    from fastapi import Response
    from app.api.v1.endpoints.billing_routes import _render_visit_invoice_pdf
    from app.core.exceptions import NotFoundError
    from app.models.all_models import Patient
    from app.services.billing_service import BillingService
    from app.utils.security_event_util import record_security_event

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient is None:
        raise NotFoundError(message="No patient record is linked to this account.")
    service = BillingService(db)
    pdf_bytes, summary = _render_visit_invoice_pdf(db, service, visit_id)
    if summary.get("patient_id") != patient.id:
        raise NotFoundError(message="Invoice not found.")
    record_security_event(
        db, user_id=current_user.id,
        event_type="PORTAL_INVOICE_DOWNLOADED", severity="INFO",
        event_detail=f"Patient downloaded invoice {summary.get('billing_no')}.",
        event_metadata={"visit_id": visit_id},
    )
    db.commit()
    safe = "".join(ch for ch in (summary.get("billing_no") or "invoice")
                   if ch.isalnum() or ch in "-_")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="invoice-{safe}.pdf"'})


@router.get("/lab-results", summary="My released laboratory results")
async def portal_lab_results(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Released lab results for the logged-in patient, grouped per request,
    ready for display and PDF download in the portal."""
    from app.models.all_models import Patient
    from app.services.lab_result_service import LabResultService

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient is None:
        return {"items": []}
    return {"items": LabResultService(db).list_released_orders_for_patient(patient.id)}


@router.get("/lab-results/{order_id}/report.pdf",
            summary="Download my laboratory report as a branded PDF")
async def portal_lab_report_pdf(
    order_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    from fastapi import Response
    from app.api.v1.endpoints.hr_routes import _load_tenant_logo_path
    from app.core.exceptions import NotFoundError
    from app.core.multitenancy import get_current_tenant
    from app.models.all_models import Patient
    from app.services.lab_result_service import LabResultService
    from app.utils.lab_report_pdf import build_lab_report_pdf

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient is None:
        raise NotFoundError(message="No patient record is linked to this account.")

    data = LabResultService(db).get_order_report_data(
        order_id, restrict_patient_id=patient.id
    )
    hospital = "Hospital"
    contact = None
    try:
        tenant = get_current_tenant()
        if tenant is not None:
            hospital = getattr(tenant, "name", None) or hospital
            contact = getattr(tenant, "contact_email", None) or getattr(tenant, "billing_email", None)
    except Exception:
        pass
    logo_path = _load_tenant_logo_path(db)
    try:
        pdf_bytes = build_lab_report_pdf(
            hospital_name=hospital, hospital_contact=contact,
            lab_name="Medical Laboratory", logo_path=logo_path,
            patient=data["patient"], visit_number=data["visit_number"],
            order_no=data["order_no"], ordered_at=data["ordered_at"],
            reported_at=data["reported_at"], rows=data["rows"],
            interpretation=data["interpretation"],
            scientist_name=data["scientist_name"],
            approved_by=data["approved_by"], verify_code=data["verify_code"],
        )
    finally:
        if logo_path:
            try:
                import os as _os
                _os.remove(logo_path)
            except OSError:
                pass
    safe = "".join(ch for ch in data["order_no"] if ch.isalnum() or ch in "-_")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="lab-report-{safe}.pdf"'})


@router.get("/baseline-diagnostics",
            summary="My lifelong baseline diagnostic profile (read-only)")
async def portal_baseline_diagnostics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Read-only baseline diagnostic profile for the logged-in patient:
    grouped diagnostic records (value, interpretation, verification status,
    verifier, dates), maintained independently of visit-specific labs. Every
    access is audit-logged."""
    from app.api.v1.endpoints.baseline_profile_routes import (
        build_baseline_diagnostic_records, baseline_patient_dict,
    )
    from app.models.all_models import (
        Patient, PatientBaselineProfile, PatientBaselineProfileRevision,
    )
    from app.utils.security_event_util import record_security_event

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient is None:
        return {"patient": None, "categories": [], "version": 0, "record_count": 0}
    profile = (
        db.query(PatientBaselineProfile)
        .filter(PatientBaselineProfile.patient_id == patient.id,
                PatientBaselineProfile.is_deleted.is_(False))
        .first()
    )
    revisions = (
        db.query(PatientBaselineProfileRevision)
        .filter(PatientBaselineProfileRevision.patient_id == patient.id,
                PatientBaselineProfileRevision.is_deleted.is_(False))
        .order_by(PatientBaselineProfileRevision.version.desc())
        .all()
    )
    categories = build_baseline_diagnostic_records(db, patient, profile, revisions)
    record_security_event(
        db, user_id=current_user.id,
        event_type="PORTAL_BASELINE_DIAGNOSTICS_VIEWED", severity="INFO",
        event_detail=f"Patient viewed baseline diagnostic profile "
                     f"(v{getattr(profile, 'version', 0) if profile else 0}).",
        event_metadata={"patient_id": patient.id},
    )
    db.commit()
    return {
        "patient": baseline_patient_dict(patient),
        "version": getattr(profile, "version", 0) if profile else 0,
        "recorded_at": getattr(profile, "date_created", None) if profile else None,
        "updated_at": (getattr(profile, "date_updated", None)
                       or getattr(profile, "date_created", None)) if profile else None,
        "categories": categories,
        "record_count": sum(len(c["records"]) for c in categories),
    }


@router.get("/baseline-diagnostics/report.pdf",
            summary="Download my baseline diagnostic profile as a branded PDF")
async def portal_baseline_diagnostics_pdf(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    from fastapi import Response
    from datetime import datetime, timezone
    from app.api.v1.endpoints.hr_routes import _load_tenant_logo_path
    from app.api.v1.endpoints.baseline_profile_routes import (
        build_baseline_diagnostic_records, baseline_patient_dict,
    )
    from app.core.exceptions import NotFoundError
    from app.core.multitenancy import get_current_tenant
    from app.models.all_models import (
        Patient, PatientBaselineProfile, PatientBaselineProfileRevision,
        StaffProfile, User as _User,
    )
    from app.utils.baseline_diagnostics_pdf import (
        build_baseline_diagnostics_pdf, baseline_verify_code,
    )
    from app.utils.security_event_util import record_security_event

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if patient is None:
        raise NotFoundError(message="No patient record is linked to this account.")
    profile = (
        db.query(PatientBaselineProfile)
        .filter(PatientBaselineProfile.patient_id == patient.id,
                PatientBaselineProfile.is_deleted.is_(False))
        .first()
    )
    revisions = (
        db.query(PatientBaselineProfileRevision)
        .filter(PatientBaselineProfileRevision.patient_id == patient.id,
                PatientBaselineProfileRevision.is_deleted.is_(False))
        .order_by(PatientBaselineProfileRevision.version.desc())
        .all()
    )
    categories = build_baseline_diagnostic_records(db, patient, profile, revisions)
    version = getattr(profile, "version", 0) if profile else 0

    physician_name = None
    pid = getattr(profile, "primary_physician_staff_id", None) if profile else None
    if pid:
        pair = (db.query(StaffProfile, _User)
                .outerjoin(_User, _User.id == StaffProfile.user_id)
                .filter(StaffProfile.id == pid).first())
        if pair:
            sp, u = pair
            physician_name = (f"{getattr(u, 'first_name', '') or ''} "
                              f"{getattr(u, 'last_name', '') or ''}".strip()
                              or sp.staff_no)

    hospital, contact = "Hospital", None
    try:
        tenant = get_current_tenant()
        if tenant is not None:
            hospital = getattr(tenant, "name", None) or hospital
            contact = (getattr(tenant, "contact_email", None)
                       or getattr(tenant, "billing_email", None))
    except Exception:
        pass

    verify_code = baseline_verify_code(
        patient.global_patient_id or patient.hospital_number or "", version)
    logo_path = _load_tenant_logo_path(db)
    try:
        pdf_bytes = build_baseline_diagnostics_pdf(
            hospital_name=hospital, hospital_contact=contact, logo_path=logo_path,
            patient=baseline_patient_dict(patient),
            generated_at=datetime.now(timezone.utc), version=version,
            recorded_at=getattr(profile, "date_created", None) if profile else None,
            updated_at=getattr(profile, "date_updated", None) if profile else None,
            primary_physician_name=physician_name,
            categories=categories, verify_code=verify_code,
        )
    finally:
        if logo_path:
            try:
                import os as _os
                _os.remove(logo_path)
            except OSError:
                pass

    record_security_event(
        db, user_id=current_user.id,
        event_type="PORTAL_BASELINE_DIAGNOSTICS_DOWNLOADED", severity="INFO",
        event_detail=f"Patient downloaded baseline diagnostic profile PDF (v{version}).",
        event_metadata={"patient_id": patient.id, "version": version},
    )
    db.commit()
    safe = "".join(ch for ch in (patient.hospital_number or "profile")
                   if ch.isalnum() or ch in "-_")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition":
                             f'attachment; filename="baseline-diagnostics-{safe}.pdf"'})


@router.get("/notifications", response_model=List[NotificationReadSchema])
async def get_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(
        True,
        description=(
            "When true (default) only unread notifications are returned, so a "
            "notification clears out of the feed once it is marked as read. "
            "Set false to include already-read history."
        ),
    ),
):
    """Get notifications for the logged-in patient (unread by default)."""
    return service.list_notifications(
        current_user.id, skip=skip, limit=limit, unread_only=unread_only
    )


@router.post(
    "/notifications/read-all",
    response_model=NotificationMarkAllReadResponseSchema,
    summary="Mark all of the patient's notifications as read",
)
async def mark_all_notifications_read(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
):
    """Acknowledge every unread notification so the feed is cleared at once."""
    updated = service.mark_all_notifications_read(current_user.id)
    return NotificationMarkAllReadResponseSchema(
        success=True,
        message=(
            "All notifications marked as read."
            if updated
            else "No unread notifications to clear."
        ),
        updated=updated,
    )


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationReadSchema,
    summary="Mark a single notification as read",
)
async def mark_notification_read(
    notification_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientPortalService, Depends(get_portal_service)],
):
    """
    Mark one notification as read for the logged-in patient. Once read, it no
    longer appears in the default (unread) notification feed.
    """
    return service.mark_notification_read(current_user.id, notification_id)


@router.get("/payment-config", summary="Which card-funding methods are available")
async def get_payment_config(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Report which funding methods the patient can use so the portal can show
    the right options. ``online_enabled`` is False when no online gateway is
    configured (e.g. missing Paystack secret key), in which case the UI should
    steer the patient to the always-available manual payment flow.
    """
    online_enabled = bool(getattr(settings, "PAYSTACK_SECRET_KEY", None))
    return {
        "online_enabled": online_enabled,
        "online_provider": "PAYSTACK" if online_enabled else None,
        "manual_enabled": True,
    }


@router.post("/fund-card", response_model=PaystackTransactionRead)
async def initialize_card_funding(
    payload: PatientFundCardRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    portal_service: Annotated[PatientPortalService, Depends(get_portal_service)],
    paystack_service: Annotated[PaystackService, Depends(get_paystack_service)],
    card_service: Annotated[MembershipCardService, Depends(get_card_service)],
):
    """Initiate a Paystack transaction to fund the patient's membership card."""
    patient = portal_service.get_patient_by_user_id(current_user.id)
    cards = card_service.list_patient_cards(patient.id)
    if not cards:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No membership card found for this patient."
        )
    
    card = cards[0] # Funding the primary/first card
    tx = await paystack_service.initialize_transaction(patient, card, payload.amount)
    return tx


def _card_proof_storage_dir() -> str:
    """Local storage dir for manual card-funding evidence, served via /uploads."""
    base = getattr(settings, "UPLOADS_DIR", None) or os.path.join(os.getcwd(), "uploads")
    path = os.path.join(base, "card_funding_proofs")
    os.makedirs(path, exist_ok=True)
    return path


@router.post("/fund-card/manual", response_model=CardFundingRequestRead)
async def submit_manual_card_funding(
    current_user: Annotated[User, Depends(get_current_user)],
    portal_service: Annotated[PatientPortalService, Depends(get_portal_service)],
    card_service: Annotated[MembershipCardService, Depends(get_card_service)],
    amount: float = Form(..., gt=0),
    payment_method: str = Form("BANK_TRANSFER"),
    payment_reference: Optional[str] = Form(None),
    depositor_name: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    evidence: UploadFile = File(...),
):
    """
    Submit a **manual** card-funding request with proof of payment.

    The patient uploads evidence (bank transfer receipt, POS slip, etc.). The
    request is recorded PENDING and appears in the hospital's review queue; a
    staff member approves it to credit the wallet.
    """
    patient = portal_service.get_patient_by_user_id(current_user.id)
    cards = card_service.list_patient_cards(patient.id)
    if not cards:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No membership card found for this patient.",
        )
    card = cards[0]

    # Persist the evidence file (mirrors the subscription manual-payment flow).
    max_bytes = int(getattr(settings, "MAX_UPLOAD_SIZE_MB", 20)) * 1024 * 1024
    raw = await evidence.read()
    if not raw:
        raise HTTPException(status_code=400, detail="The uploaded evidence file is empty.")
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Evidence file exceeds the {getattr(settings, 'MAX_UPLOAD_SIZE_MB', 20)}MB limit.",
        )

    allowed_ext = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}
    safe_name = os.path.basename(evidence.filename or "evidence")
    ext = os.path.splitext(safe_name)[1].lower()[:10]
    if ext and ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload an image (JPG/PNG/WEBP/GIF) or a PDF.",
        )

    stored_name = f"card{card.id}_{_uuid.uuid4().hex[:12]}{ext}"
    dest = os.path.join(_card_proof_storage_dir(), stored_name)
    with open(dest, "wb") as fh:
        fh.write(raw)
    evidence_url = f"/uploads/card_funding_proofs/{stored_name}"

    request = card_service.create_manual_funding_request(
        patient_id=patient.id,
        membership_card_id=card.id,
        amount=amount,
        payment_method=payment_method,
        payment_reference=payment_reference,
        depositor_name=depositor_name,
        note=note,
        evidence_file_name=safe_name,
        evidence_file_path=dest,
        evidence_file_url=evidence_url,
        evidence_content_type=evidence.content_type,
    )
    return request


@router.get("/fund-card/manual", response_model=List[CardFundingRequestRead])
async def list_my_manual_card_funding(
    current_user: Annotated[User, Depends(get_current_user)],
    portal_service: Annotated[PatientPortalService, Depends(get_portal_service)],
    card_service: Annotated[MembershipCardService, Depends(get_card_service)],
):
    """List the patient's own manual funding requests (status tracking)."""
    patient = portal_service.get_patient_by_user_id(current_user.id)
    return card_service.list_patient_funding_requests(patient.id)



# ── Hospital → patient messages (inbox) ──────────────────────────────


@router.get(
    "/messages",
    response_model=PortalInboxListResponse,
    summary="List messages the hospital has sent to the patient",
)
async def list_portal_messages(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientBroadcastService, Depends(get_broadcast_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(
        False, description="Only messages the patient hasn't opened yet."
    ),
):
    """Messages sent to the logged-in patient by the hospital, newest first."""
    rows, total = service.list_inbox(
        current_user.id, skip=skip, limit=limit, unread_only=unread_only
    )
    items = [PortalInboxMessageRead.from_row(rec, bc) for rec, bc in rows]
    return paginate_response(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        message="Messages fetched successfully.",
    )


@router.get(
    "/messages/unread-count",
    response_model=PortalInboxUnreadCountResponse,
    summary="Count unread hospital messages",
)
async def portal_messages_unread_count(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientBroadcastService, Depends(get_broadcast_service)],
):
    return PortalInboxUnreadCountResponse(
        success=True, count=service.count_unread(current_user.id)
    )


@router.post(
    "/messages/read-all",
    response_model=NotificationMarkAllReadResponseSchema,
    summary="Mark all hospital messages as read",
)
async def mark_all_portal_messages_read(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientBroadcastService, Depends(get_broadcast_service)],
):
    updated = service.mark_all_read(current_user.id)
    return NotificationMarkAllReadResponseSchema(
        success=True,
        message=(
            "All messages marked as read." if updated else "No unread messages to clear."
        ),
        updated=updated,
    )


@router.post(
    "/messages/{recipient_id}/read",
    response_model=PortalInboxMessageRead,
    summary="Mark a single hospital message as read",
)
async def mark_portal_message_read(
    recipient_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[PatientBroadcastService, Depends(get_broadcast_service)],
):
    recipient, broadcast = service.mark_read(current_user.id, recipient_id)
    return PortalInboxMessageRead.from_row(recipient, broadcast)
