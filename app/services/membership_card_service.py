# app/services/membership_card_service.py
from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

import secrets

from app.core.enums import (
    MembershipCardStatus,
    MembershipCardTransactionType,
    CardFundingRequestStatus,
    NotificationChannel,
)
from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
    ValidationError,
    AlreadyExistsError,
)
from app.models.all_models import (
    Facility,
    MembershipCard,
    MembershipCardTransaction,
    MembershipCardFundingRequest,
    NotificationTemplate,
    Patient,
    User,
    PaystackTransaction,
)
from app.repositories.membership_card_repository import MembershipCardRepository
from app.services.notification_service import NotificationService
from app.schemas.notification_schema import NotificationDispatchSchema
from app.schemas.membership_card_schemas import (
    MembershipCardCreate,
    MembershipCardUpdate,
    MembershipCardFund,
    MembershipCardDebit,
)
from app.utils.security_event_util import record_security_event

logger = logging.getLogger(__name__)

# Stable template code for the membership-card payment receipt. The template is
# get-or-created on first use so the receipt works out of the box even when a
# tenant hasn't seeded notification templates.
MEMBERSHIP_CARD_DEBIT_TEMPLATE_CODE = "MEMBERSHIP_CARD_DEBIT"

_DEBIT_EMAIL_SUBJECT = (
    "Payment received — {amount} debited from your membership card"
)
_DEBIT_EMAIL_BODY = (
    "Dear {patient_name},\n\n"
    "This confirms a payment on your membership card ({card_number}).\n\n"
    "Amount debited: {amount}\n"
    "Paid for: {purpose}\n"
    "Date & time: {transaction_date}\n"
    "Reference: {reference}\n"
    "Remaining card balance: {balance}\n\n"
    "If you did not authorise this payment, please contact the hospital "
    "immediately.\n\n"
    "Thank you,\n{hospital_name}"
)


class MembershipCardService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = MembershipCardRepository(db)
        self.notification_service = NotificationService(db)

    def _generate_card_number(self) -> str:
        """A unique, human-friendly card number: MC-XXXX-XXXX-XXXX."""
        for _ in range(10):
            digits = "".join(secrets.choice("0123456789") for _ in range(12))
            number = f"MC-{digits[0:4]}-{digits[4:8]}-{digits[8:12]}"
            if not self.repository.get_by_card_number(number):
                return number
        raise BadRequestError(message="Could not allocate a unique card number. Please retry.")

    def _resolve_issuing_facility(self, facility_id: Optional[int]) -> int:
        if facility_id:
            facility = self.db.query(Facility).filter(Facility.id == facility_id).first()
            if not facility:
                raise NotFoundError(message=f"Facility {facility_id} not found.")
            return facility.id
        facility = (
            self.db.query(Facility)
            .filter(Facility.is_deleted.is_(False))
            .order_by(Facility.id.asc())
            .first()
        )
        if facility:
            return facility.id
        # No facility yet — provision a sensible default so card issuance (and
        # other facility-scoped features) work out of the box for a new tenant.
        return self._provision_default_facility().id

    def _provision_default_facility(self) -> Facility:
        from app.core.enums import FacilityStatus, FacilityType
        from app.core.multitenancy import get_current_tenant

        tenant = None
        try:
            tenant = get_current_tenant()
        except Exception:
            tenant = None

        base_name = (getattr(tenant, "name", None) or "Main Facility").strip()
        base_code = (getattr(tenant, "code", None) or "MAIN").strip().upper()

        # Ensure unique name/code even if a soft-deleted or partial row exists.
        name = base_name
        code = f"{base_code}-HQ"
        suffix = 1
        while self.db.query(Facility).filter(Facility.name == name).first():
            suffix += 1
            name = f"{base_name} {suffix}"
        suffix = 1
        while self.db.query(Facility).filter(Facility.code == code).first():
            suffix += 1
            code = f"{base_code}-HQ{suffix}"

        facility = Facility(
            name=name,
            code=code,
            facility_type=FacilityType.MAIN_HOSPITAL,
            status=FacilityStatus.ACTIVE,
        )
        self.db.add(facility)
        self.db.flush()
        return facility

    def create_card(self, payload: MembershipCardCreate, issued_by_id: int) -> MembershipCard:
        # Validate the patient exists.
        patient = self.db.query(Patient).filter(Patient.id == payload.patient_id).first()
        if not patient:
            raise NotFoundError(message=f"Patient {payload.patient_id} not found.")

        # Auto-generate a card number when one wasn't supplied.
        card_number = (payload.card_number or "").strip() or self._generate_card_number()
        existing = self.repository.get_by_card_number(card_number)
        if existing:
            raise AlreadyExistsError(f"Membership card with number {card_number} already exists.")

        facility_id = self._resolve_issuing_facility(payload.issuing_facility_id)

        card = MembershipCard(
            patient_id=payload.patient_id,
            card_number=card_number,
            balance=payload.initial_balance,
            status=payload.status,
            issuing_facility_id=facility_id,
            issued_by_id=issued_by_id,
            expiry_date=payload.expiry_date,
        )
        
        card = self.repository.create_card(card)

        # If initial balance > 0, create a transaction
        if payload.initial_balance > 0:
            transaction = MembershipCardTransaction(
                membership_card_id=card.id,
                patient_id=card.patient_id,
                amount=payload.initial_balance,
                transaction_type=MembershipCardTransactionType.CREDIT,
                payment_source="INITIAL_DEPOSIT",
                balance_before=Decimal("0.00"),
                balance_after=payload.initial_balance,
                facility_id=card.issuing_facility_id,
                processed_by_id=issued_by_id,
                transaction_date=datetime.utcnow(),
                narration="Initial card deposit",
            )
            self.repository.create_transaction(transaction)

        return card

    def get_card(self, card_id: int, include_transactions: bool = False) -> MembershipCard:
        card = self.repository.get_by_id(card_id, include_transactions=include_transactions)
        if not card:
            raise NotFoundError(f"Membership card with id {card_id} not found.")
        return card

    def _card_verify_url(self, card, base: Optional[str] = None) -> Optional[str]:
        """Build the public verification URL the card's QR should encode:
        ``<base>/verify-card?code=<card_number>&h=<hospital_code>``. ``base``
        defaults to the configured FRONTEND_URL; returns None if neither is set."""
        try:
            from urllib.parse import urlencode
            from app.core.config import settings as _settings
            from app.core.multitenancy import get_current_tenant
            b = (base or getattr(_settings, "FRONTEND_URL", "") or "").rstrip("/")
            if not b:
                return None
            params = {"code": card.card_number}
            try:
                tenant = get_current_tenant()
                code = getattr(tenant, "code", None) if tenant else None
                if code:
                    params["h"] = code
            except Exception:
                pass
            return f"{b}/verify-card?{urlencode(params)}"
        except Exception:
            return None

    def build_card_qr_png(self, card_id: int, base: Optional[str] = None) -> tuple[bytes, str]:
        """Render a scannable QR PNG for a card, encoding its verification URL
        (falls back to a text payload when no frontend URL is configured)."""
        import io
        import qrcode

        card = self.get_card(card_id)
        payload = self._card_verify_url(card, base) or f"CAREPOINT|MEMBERSHIP-CARD|{card.card_number}"
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        safe = "".join(ch for ch in (card.card_number or "card") if ch.isalnum() or ch in "-_")
        return buf.getvalue(), f"card-qr-{safe}.png"

    def generate_card_pdf(self, card_id: int) -> tuple[bytes, str]:
        """
        Render a printable PDF of a membership card.

        Returns ``(pdf_bytes, filename)``. The card shows the hospital name,
        the patient's full name, the card number, and a scannable QR code.
        """
        from app.utils.card_pdf import build_membership_card_pdf
        from app.core.multitenancy import get_current_tenant

        card = self.get_card(card_id)
        patient = getattr(card, "patient", None) or (
            self.db.query(Patient).filter(Patient.id == card.patient_id).first()
        )

        # Hospital name: the tenant name, falling back to the issuing facility.
        hospital_name = "Hospital"
        tenant_code = None
        try:
            tenant = get_current_tenant()
            if tenant:
                if getattr(tenant, "name", None):
                    hospital_name = tenant.name
                tenant_code = getattr(tenant, "code", None)
        except Exception:
            pass
        if hospital_name == "Hospital":
            facility = getattr(card, "issuing_facility", None)
            if facility and getattr(facility, "name", None):
                hospital_name = facility.name

        patient_name = "—"
        patient_mrn = None
        global_id = None
        if patient is not None:
            parts = [
                getattr(patient, "first_name", "") or "",
                getattr(patient, "middle_name", "") or "",
                getattr(patient, "last_name", "") or "",
            ]
            patient_name = " ".join(p for p in parts if p).strip() or "—"
            patient_mrn = getattr(patient, "hospital_number", None)
            global_id = getattr(patient, "global_patient_id", None)

        # QR links straight to the card-verification page (works from any phone
        # camera). Falls back to the legacy pipe payload if no frontend URL is
        # configured — either form is accepted by ``verify_card``.
        qr_payload = (
            f"CAREPOINT|MEMBERSHIP-CARD|{card.card_number}|"
            f"{patient_name}|{hospital_name}|{global_id or ''}"
        )
        verify_url = self._card_verify_url(card)
        if verify_url:
            qr_payload = verify_url

        # Resolve the patient's profile photo to a local PNG (best-effort).
        photo_path = self._load_patient_photo_png(patient) if patient is not None else None
        try:
            pdf_bytes = build_membership_card_pdf(
                hospital_name=hospital_name,
                patient_name=patient_name,
                card_number=card.card_number,
                patient_mrn=patient_mrn,
                global_id=global_id,
                status=str(getattr(card.status, "value", card.status) or ""),
                expiry=getattr(card, "expiry_date", None),
                date_issued=getattr(card, "date_issued", None),
                qr_payload=qr_payload,
                photo_path=photo_path,
            )
        finally:
            if photo_path:
                try:
                    import os as _os
                    _os.remove(photo_path)
                except OSError:
                    pass
        safe_number = "".join(ch for ch in (card.card_number or "card") if ch.isalnum() or ch in "-_")
        filename = f"membership-card-{safe_number}.pdf"
        return pdf_bytes, filename

    def _load_patient_photo_png(self, patient) -> Optional[str]:
        """Best-effort: fetch the patient's profile photo and normalise it to a
        temporary PNG for the card. Tries S3 by key, then any stored URL / data
        URI / local path. Returns the temp path, or None if unavailable."""
        import base64
        import io
        import os as _os
        import tempfile
        from urllib.parse import urlparse

        key = getattr(patient, "photo_file_key", None)
        url = (getattr(patient, "photo_file_url", None)
               or getattr(patient, "profile_photo_url", None))
        raw: Optional[bytes] = None

        # 0) Locally-stored photo: photo_file_key holds an absolute path.
        if not raw and key:
            try:
                if _os.path.isabs(str(key)) and _os.path.exists(str(key)):
                    with open(str(key), "rb") as fh:
                        raw = fh.read()
            except Exception:
                raw = None

        # 1) Direct S3/MinIO object fetch by key (most reliable).
        if not raw and key and not _os.path.isabs(str(key)):
            try:
                from app.core.config import settings as _settings
                from app.core.multitenancy import get_current_tenant
                from app.services.aws_s3_service import S3Service
                tenant = get_current_tenant()
                code = getattr(tenant, "code", None)
                if code:
                    env = "dev" if getattr(_settings, "is_development", True) else "prod"
                    bucket = f"carepoint-hms-{str(code).lower()}-{env}"
                    obj = S3Service().s3_client.get_object(Bucket=bucket, Key=key)
                    raw = obj["Body"].read()
            except Exception:
                raw = None

        # 2) Stored URL / data URI / local path.
        if not raw and url:
            try:
                u = str(url).strip()
                if u.startswith("data:"):
                    raw = base64.b64decode(u.split(",", 1)[1]) if "," in u else None
                elif u.startswith("http://") or u.startswith("https://"):
                    import httpx
                    resp = httpx.get(u, timeout=6.0, follow_redirects=True)
                    if resp.status_code < 400:
                        raw = resp.content
                elif u.startswith("file://"):
                    with open(urlparse(u).path, "rb") as fh:
                        raw = fh.read()
                elif u.startswith("/uploads/"):
                    from app.core.config import settings as _settings
                    base = getattr(_settings, "UPLOADS_DIR", None) or _os.path.join(_os.getcwd(), "uploads")
                    local = _os.path.join(base, u[len("/uploads/"):])
                    if _os.path.exists(local):
                        with open(local, "rb") as fh:
                            raw = fh.read()
                elif _os.path.exists(u):
                    with open(u, "rb") as fh:
                        raw = fh.read()
            except Exception:
                raw = None

        if not raw:
            return None

        # Normalise via Pillow so any format renders reliably in the PDF.
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img.thumbnail((600, 600))
            fd, path = tempfile.mkstemp(suffix=".png", prefix="cardphoto_")
            _os.close(fd)
            img.save(path, format="PNG")
            return path
        except Exception:
            return None

    def get_card_by_number(self, card_number: str) -> MembershipCard:
        card = self.repository.get_by_card_number(card_number)
        if not card:
            raise NotFoundError(f"Membership card with number {card_number} not found.")
        return card

    @staticmethod
    def _extract_card_number(code: str) -> str:
        """
        Pull a card number out of a scanned value. Accepts either a raw card
        number or the QR payload printed on the card
        (``CAREPOINT|MEMBERSHIP-CARD|<number>|<patient>|<hospital>``).
        """
        value = (code or "").strip()
        # Verification-URL form: ``https://app/verify-card?code=MC-...&h=CODE``
        if "://" in value or value.lower().startswith("http") or "code=" in value:
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(value)
                qs = parse_qs(parsed.query or "")
                if qs.get("code"):
                    return qs["code"][0].strip()
                seg = [p for p in (parsed.path or "").split("/") if p]
                if seg:
                    return seg[-1].strip()
            except Exception:
                pass
        if "|" in value:
            parts = [p.strip() for p in value.split("|")]
            # Prefer the token right after the MEMBERSHIP-CARD marker.
            for i, p in enumerate(parts):
                if p.upper() in {"MEMBERSHIP-CARD", "CARD"} and i + 1 < len(parts):
                    return parts[i + 1]
            # Otherwise, the first token that looks like a card number.
            for p in parts:
                if p.upper().startswith("MC-") or p.upper().startswith("MC"):
                    return p
            return parts[2] if len(parts) > 2 else (parts[-1] if parts else value)
        return value

    def verify_card_public(self, code: str) -> dict:
        """Verification result safe for public (QR-scan) exposure: confirms the
        card and cardholder without revealing wallet balance or internal IDs."""
        full = self.verify_card(code)
        allowed = {
            "valid", "usable", "expired", "message", "card_number", "status",
            "expiry_date", "date_issued", "patient_name", "hospital_name",
        }
        return {k: v for k, v in full.items() if k in allowed}

    def verify_card(self, code: str) -> dict:
        """
        Verify a scanned/typed membership-card code and return a structured
        result the UI can render (validity, cardholder, status, usability).
        """
        from datetime import date as _date
        from app.core.multitenancy import get_current_tenant

        number = self._extract_card_number(code)
        if not number:
            return {"valid": False, "message": "No code was provided."}

        card = self.repository.get_by_card_number(number)
        if not card:
            return {
                "valid": False,
                "card_number": number,
                "message": "No membership card matches this code.",
            }

        patient = getattr(card, "patient", None)
        patient_name = None
        patient_mrn = None
        if patient is not None:
            parts = [
                getattr(patient, "first_name", "") or "",
                getattr(patient, "middle_name", "") or "",
                getattr(patient, "last_name", "") or "",
            ]
            patient_name = " ".join(p for p in parts if p).strip() or None
            patient_mrn = getattr(patient, "hospital_number", None)

        hospital_name = None
        try:
            tenant = get_current_tenant()
            hospital_name = getattr(tenant, "name", None) if tenant else None
        except Exception:
            hospital_name = None

        status_val = str(getattr(card.status, "value", card.status) or "")
        expiry = getattr(card, "expiry_date", None)
        is_expired = bool(expiry and expiry < _date.today())
        is_usable = (status_val == "ACTIVE") and not is_expired

        if is_usable:
            message = "Card is valid and active."
        elif is_expired:
            message = "Card has expired."
        else:
            message = f"Card is not usable (status: {status_val or 'UNKNOWN'})."

        return {
            "valid": True,
            "usable": is_usable,
            "expired": is_expired,
            "message": message,
            "card_id": card.id,
            "card_number": card.card_number,
            "status": status_val,
            "balance": card.balance,
            "expiry_date": expiry,
            "date_issued": getattr(card, "date_issued", None),
            "patient_id": card.patient_id,
            "patient_name": patient_name,
            "patient_mrn": patient_mrn,
            "issuing_facility_id": getattr(card, "issuing_facility_id", None),
            "hospital_name": hospital_name,
        }

    def list_patient_cards(self, patient_id: int) -> List[MembershipCard]:
        return self.repository.get_by_patient_id(patient_id)

    def list_cards(
        self,
        skip: int = 0,
        limit: int = 100,
        *,
        search: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[MembershipCard]:
        return self.repository.list_cards(skip=skip, limit=limit, search=search, status=status)

    def get_stats(self) -> dict:
        """Aggregate counts by status and total wallet balance across all cards."""
        from sqlalchemy import func

        rows = (
            self.db.query(MembershipCard.status, func.count(MembershipCard.id), func.coalesce(func.sum(MembershipCard.balance), 0))
            .filter(MembershipCard.is_deleted.is_(False))
            .group_by(MembershipCard.status)
            .all()
        )
        stats = {
            "total": 0,
            "active": 0,
            "inactive": 0,
            "suspended": 0,
            "expired": 0,
            "lost": 0,
            "total_balance": Decimal("0.00"),
        }
        for status_val, count, balance in rows:
            key = str(getattr(status_val, "value", status_val) or "").lower()
            stats["total"] += int(count or 0)
            stats["total_balance"] += Decimal(str(balance or 0))
            if key in stats:
                stats[key] += int(count or 0)
        return stats

    def update_card(self, card_id: int, payload: MembershipCardUpdate) -> MembershipCard:
        card = self.get_card(card_id)
        
        if payload.status:
            card.status = payload.status
        if payload.expiry_date:
            card.expiry_date = payload.expiry_date
            
        return self.repository.update_card(card)

    def fund_card(
        self, card_id: int, payload: MembershipCardFund, processed_by_id: int, facility_id: int
    ) -> MembershipCardTransaction:
        card = self.get_card(card_id)
        
        if card.status != MembershipCardStatus.ACTIVE:
            raise ValidationError(f"Cannot fund a card that is in {card.status} status.")

        balance_before = card.balance
        card.balance += payload.amount
        balance_after = card.balance
        
        self.repository.update_card(card)

        transaction = MembershipCardTransaction(
            membership_card_id=card.id,
            patient_id=card.patient_id,
            amount=payload.amount,
            transaction_type=MembershipCardTransactionType.CREDIT,
            payment_source=payload.payment_source,
            payment_reference=payload.payment_reference,
            balance_before=balance_before,
            balance_after=balance_after,
            facility_id=facility_id,
            processed_by_id=processed_by_id,
            transaction_date=datetime.utcnow(),
            narration=payload.narration or f"Credit via {payload.payment_source}",
        )
        
        transaction = self.repository.create_transaction(transaction)
        
        # Trigger Notification
        try:
            self.notification_service.dispatch_from_template(
                payload=NotificationDispatchSchema(
                    template_code="MEMBERSHIP_CARD_CREDIT",
                    patient_id=card.patient_id,
                    context={
                        "amount": f"{payload.amount:,.2f}",
                        "balance": f"{card.balance:,.2f}",
                        "reference": payload.payment_reference or "N/A"
                    }
                )
            )
        except Exception as e:
            print(f"Error sending credit notification: {e}")

        return transaction

    def credit_via_paystack(
        self, tx: PaystackTransaction
    ) -> MembershipCardTransaction:
        """
        Credit a membership card using a verified Paystack transaction.
        """
        card = self.get_card(tx.membership_card_id)
        
        if card.status != MembershipCardStatus.ACTIVE:
            raise ValidationError(f"Cannot fund a card that is in {card.status} status.")

        balance_before = card.balance
        card.balance += tx.amount
        balance_after = card.balance
        
        self.repository.update_card(card)

        transaction = MembershipCardTransaction(
            membership_card_id=card.id,
            patient_id=card.patient_id,
            amount=tx.amount,
            transaction_type=MembershipCardTransactionType.CREDIT,
            payment_source="PAYSTACK",
            payment_reference=tx.reference,
            balance_before=balance_before,
            balance_after=balance_after,
            facility_id=1, # Default facility for online payments
            processed_by_id=tx.patient.user_id or 1, # Linked user or system admin
            transaction_date=datetime.utcnow(),
            narration=f"Online credit via Paystack. Ref: {tx.reference}",
        )
        
        transaction = self.repository.create_transaction(transaction)

        # Trigger Notification
        try:
            self.notification_service.dispatch_from_template(
                payload=NotificationDispatchSchema(
                    template_code="MEMBERSHIP_CARD_CREDIT",
                    patient_id=card.patient_id,
                    context={
                        "amount": f"{tx.amount:,.2f}",
                        "balance": f"{card.balance:,.2f}",
                        "reference": tx.reference
                    }
                )
            )
        except Exception as e:
            print(f"Error sending Paystack credit notification: {e}")

        return transaction

    def debit_card(
        self,
        card_id: int,
        payload: MembershipCardDebit,
        processed_by_id: int,
        facility_id: int,
        payment_id: Optional[int] = None,
        *,
        purpose: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> MembershipCardTransaction:
        """
        Authorise and debit a membership card for a payment.

        Validation & balance management: the card must be ACTIVE and hold a
        sufficient balance, otherwise a ValidationError is raised before any
        money moves. On success the balance is deducted, a
        ``MembershipCardTransaction`` (with before/after balances) is written,
        a security audit event is recorded, and the patient is sent a detailed
        payment receipt by email plus an in-app notification.

        ``purpose`` is the human-readable reason for the debit (e.g.
        "Consultation, Laboratory tests") used in the receipt. When omitted it
        falls back to the transaction narration.
        """
        card = self.get_card(card_id)

        if card.status != MembershipCardStatus.ACTIVE:
            raise ValidationError(f"Cannot debit a card that is in {card.status} status.")

        amount = Decimal(str(payload.amount))
        if amount <= 0:
            raise ValidationError("Debit amount must be greater than zero.")

        if Decimal(str(card.balance or 0)) < amount:
            raise ValidationError(
                "Insufficient membership card balance. "
                f"Balance is {Decimal(str(card.balance or 0)):,.2f}, "
                f"requested {amount:,.2f}."
            )

        balance_before = card.balance
        card.balance = Decimal(str(card.balance or 0)) - amount
        balance_after = card.balance

        self.repository.update_card(card)

        transaction = MembershipCardTransaction(
            membership_card_id=card.id,
            patient_id=card.patient_id,
            amount=amount,
            transaction_type=MembershipCardTransactionType.DEBIT,
            balance_before=balance_before,
            balance_after=balance_after,
            facility_id=facility_id,
            processed_by_id=processed_by_id,
            transaction_date=datetime.utcnow(),
            narration=payload.narration or "Debit for services",
            invoice_id=payload.invoice_id,
            visit_id=payload.visit_id,
            payment_id=payment_id,
        )

        transaction = self.repository.create_transaction(transaction)

        # Audit log — a card debit moves real money, so record it for review.
        try:
            record_security_event(
                self.db,
                user_id=actor_user_id or processed_by_id,
                event_type="MEMBERSHIP_CARD_DEBIT",
                severity="INFO",
                event_detail=(
                    f"Membership card {card.card_number} debited "
                    f"{amount:,.2f} for {purpose or payload.narration or 'services'}."
                ),
                event_metadata={
                    "membership_card_id": card.id,
                    "transaction_id": transaction.id,
                    "patient_id": card.patient_id,
                    "amount": str(amount),
                    "balance_after": str(balance_after),
                    "invoice_id": payload.invoice_id,
                    "visit_id": payload.visit_id,
                    "payment_id": payment_id,
                },
            )
            self.db.commit()
        except Exception as exc:  # pragma: no cover - audit must never block a debit
            logger.warning("Failed to record card-debit audit event: %s", exc)

        # Notify the patient (email receipt + in-app), best-effort.
        self._send_debit_receipt(
            card=card,
            transaction=transaction,
            amount=amount,
            balance_after=balance_after,
            purpose=purpose or payload.narration or "Hospital services",
            actor_user_id=actor_user_id,
        )

        return transaction

    # ------------------------------------------------------------------
    # Payment-receipt notification (email + in-app)
    # ------------------------------------------------------------------

    def _ensure_debit_email_template(self) -> Optional[NotificationTemplate]:
        """
        Return the membership-card debit EMAIL template, creating it on first
        use so receipts work without a separate seeding step.
        """
        try:
            existing = self.notification_service.template_repository.get_by_code(
                MEMBERSHIP_CARD_DEBIT_TEMPLATE_CODE
            )
            if existing is not None:
                return existing
            template = NotificationTemplate(
                name="Membership Card Payment Receipt",
                code=MEMBERSHIP_CARD_DEBIT_TEMPLATE_CODE,
                channel=NotificationChannel.EMAIL,
                subject_template=_DEBIT_EMAIL_SUBJECT,
                body_template=_DEBIT_EMAIL_BODY,
            )
            self.db.add(template)
            self.db.commit()
            self.db.refresh(template)
            return template
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not ensure card-debit email template: %s", exc)
            self.db.rollback()
            return None

    def _hospital_name(self) -> str:
        from app.core.multitenancy import get_current_tenant

        try:
            tenant = get_current_tenant()
            if tenant and getattr(tenant, "name", None):
                return tenant.name
        except Exception:
            pass
        return "Your hospital"

    def _send_debit_receipt(
        self,
        *,
        card: MembershipCard,
        transaction: MembershipCardTransaction,
        amount: Decimal,
        balance_after: Decimal,
        purpose: str,
        actor_user_id: Optional[int] = None,
    ) -> None:
        """Send the payment receipt by email and record an in-app copy."""
        patient = getattr(card, "patient", None) or (
            self.db.query(Patient).filter(Patient.id == card.patient_id).first()
        )
        patient_name = "Patient"
        if patient is not None:
            parts = [
                getattr(patient, "first_name", "") or "",
                getattr(patient, "last_name", "") or "",
            ]
            patient_name = " ".join(p for p in parts if p).strip() or "Patient"

        tx_date = transaction.transaction_date or datetime.utcnow()
        context = {
            "patient_name": patient_name,
            "card_number": card.card_number,
            "amount": f"NGN {amount:,.2f}",
            "purpose": purpose,
            "transaction_date": tx_date.strftime("%d %b %Y, %I:%M %p"),
            "reference": transaction.payment_reference or f"MCT-{transaction.id}",
            "balance": f"NGN {Decimal(str(balance_after or 0)):,.2f}",
            "hospital_name": self._hospital_name(),
        }

        template = self._ensure_debit_email_template()
        if template is None:
            return

        # Email receipt.
        try:
            self.notification_service.dispatch_from_template(
                payload=NotificationDispatchSchema(
                    template_code=MEMBERSHIP_CARD_DEBIT_TEMPLATE_CODE,
                    patient_id=card.patient_id,
                    channel_override="EMAIL",
                    context=context,
                ),
                actor_user_id=actor_user_id,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to send card-debit email receipt: %s", exc)

        # In-app copy so the patient sees it in their portal inbox.
        try:
            self.notification_service.dispatch_from_template(
                payload=NotificationDispatchSchema(
                    template_code=MEMBERSHIP_CARD_DEBIT_TEMPLATE_CODE,
                    patient_id=card.patient_id,
                    channel_override="IN_APP",
                    context=context,
                ),
                actor_user_id=actor_user_id,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to record in-app card-debit notification: %s", exc)

    def get_card_transactions(self, card_id: int) -> List[MembershipCardTransaction]:
        self.get_card(card_id) # Ensure exists
        return self.repository.get_transactions_by_card_id(card_id)

    # ------------------------------------------------------------------
    # Manual card-funding requests (patient-submitted, staff-approved)
    # ------------------------------------------------------------------

    def create_manual_funding_request(
        self,
        *,
        patient_id: int,
        membership_card_id: int,
        amount: Decimal,
        payment_method: str = "BANK_TRANSFER",
        payment_reference: Optional[str] = None,
        depositor_name: Optional[str] = None,
        note: Optional[str] = None,
        evidence_file_name: Optional[str] = None,
        evidence_file_path: Optional[str] = None,
        evidence_file_url: Optional[str] = None,
        evidence_content_type: Optional[str] = None,
    ) -> MembershipCardFundingRequest:
        """Record a PENDING manual funding request with uploaded evidence."""
        if amount is None or Decimal(str(amount)) <= 0:
            raise ValidationError("Funding amount must be greater than zero.")

        # Validate the card belongs to this patient.
        card = (
            self.db.query(MembershipCard)
            .filter(MembershipCard.id == membership_card_id)
            .first()
        )
        if not card:
            raise NotFoundError(message="Membership card not found.")
        if card.patient_id != patient_id:
            raise BadRequestError(message="This card does not belong to the patient.")

        request = MembershipCardFundingRequest(
            patient_id=patient_id,
            membership_card_id=membership_card_id,
            amount=Decimal(str(amount)),
            payment_method=(payment_method or "BANK_TRANSFER").strip().upper(),
            payment_reference=(payment_reference or None),
            depositor_name=(depositor_name or None),
            note=(note or None),
            evidence_file_name=evidence_file_name,
            evidence_file_path=evidence_file_path,
            evidence_file_url=evidence_file_url,
            evidence_content_type=evidence_content_type,
            status=CardFundingRequestStatus.PENDING,
        )
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def list_patient_funding_requests(
        self, patient_id: int, *, limit: int = 50
    ) -> List[MembershipCardFundingRequest]:
        return (
            self.db.query(MembershipCardFundingRequest)
            .filter(
                MembershipCardFundingRequest.patient_id == patient_id,
                MembershipCardFundingRequest.is_deleted.is_(False),
            )
            .order_by(MembershipCardFundingRequest.id.desc())
            .limit(limit)
            .all()
        )

    def list_funding_requests(
        self, *, status: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[MembershipCardFundingRequest]:
        from sqlalchemy.orm import joinedload

        query = (
            self.db.query(MembershipCardFundingRequest)
            .options(
                joinedload(MembershipCardFundingRequest.membership_card),
                joinedload(MembershipCardFundingRequest.patient),
            )
            .filter(MembershipCardFundingRequest.is_deleted.is_(False))
        )
        if status:
            query = query.filter(
                MembershipCardFundingRequest.status
                == CardFundingRequestStatus(status.upper())
            )
        return (
            query.order_by(MembershipCardFundingRequest.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_funding_request(self, request_id: int) -> MembershipCardFundingRequest:
        req = (
            self.db.query(MembershipCardFundingRequest)
            .filter(MembershipCardFundingRequest.id == request_id)
            .first()
        )
        if not req:
            raise NotFoundError(message="Funding request not found.")
        return req

    def approve_funding_request(
        self, request_id: int, *, reviewed_by_id: int, note: Optional[str] = None
    ) -> MembershipCardFundingRequest:
        """Approve a PENDING request: credit the wallet and link the transaction."""
        req = self.get_funding_request(request_id)
        if req.status != CardFundingRequestStatus.PENDING:
            raise BadRequestError(
                message=f"This request has already been {req.status.value.lower()}."
            )

        card = self.get_card(req.membership_card_id)
        if card.status != MembershipCardStatus.ACTIVE:
            raise ValidationError(
                f"Cannot credit a card that is in {card.status} status. "
                "Activate the card first."
            )

        # Credit the wallet directly (mirrors fund_card, but keyed to the request).
        balance_before = card.balance
        card.balance += req.amount
        balance_after = card.balance
        self.repository.update_card(card)

        transaction = MembershipCardTransaction(
            membership_card_id=card.id,
            patient_id=card.patient_id,
            amount=req.amount,
            transaction_type=MembershipCardTransactionType.CREDIT,
            payment_source=req.payment_method or "MANUAL",
            payment_reference=req.payment_reference,
            balance_before=balance_before,
            balance_after=balance_after,
            facility_id=card.issuing_facility_id,
            processed_by_id=reviewed_by_id,
            transaction_date=datetime.utcnow(),
            narration=note or f"Manual funding approved (ref {req.payment_reference or 'N/A'})",
        )
        transaction = self.repository.create_transaction(transaction)

        req.status = CardFundingRequestStatus.APPROVED
        req.reviewed_by_id = reviewed_by_id
        req.reviewed_at = datetime.utcnow()
        req.review_note = note
        req.transaction_id = transaction.id
        self.db.commit()
        self.db.refresh(req)

        # Notify the patient (best-effort).
        try:
            self.notification_service.dispatch_from_template(
                payload=NotificationDispatchSchema(
                    template_code="MEMBERSHIP_CARD_CREDIT",
                    patient_id=card.patient_id,
                    context={
                        "amount": f"{req.amount:,.2f}",
                        "balance": f"{card.balance:,.2f}",
                        "reference": req.payment_reference or "Manual funding",
                    },
                )
            )
        except Exception as e:  # pragma: no cover
            print(f"Error sending manual-funding credit notification: {e}")

        return req

    def reject_funding_request(
        self, request_id: int, *, reviewed_by_id: int, note: Optional[str] = None
    ) -> MembershipCardFundingRequest:
        req = self.get_funding_request(request_id)
        if req.status != CardFundingRequestStatus.PENDING:
            raise BadRequestError(
                message=f"This request has already been {req.status.value.lower()}."
            )
        req.status = CardFundingRequestStatus.REJECTED
        req.reviewed_by_id = reviewed_by_id
        req.reviewed_at = datetime.utcnow()
        req.review_note = note
        self.db.commit()
        self.db.refresh(req)
        return req
