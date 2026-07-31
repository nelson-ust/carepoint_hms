# app/services/patient_loyalty_service.py
"""
Patient loyalty service — the read/write logic behind the Patient Loyalty page.

Wraps the PatientLoyalty membership + LoyaltyTransaction ledger with the simple
operations the UI needs: read the current balance, list history, and award or
redeem points. A patient with no membership yet is auto-enrolled into the
tenant's default loyalty program the first time points are awarded.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import LoyaltyTransactionType
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    LoyaltyProgram,
    LoyaltyTransaction,
    Patient,
    PatientLoyalty,
)

_DEFAULT_PROGRAM_CODE = "DEFAULT"


class PatientLoyaltyService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_patient(self, patient_id: int) -> Patient:
        patient = (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
            .first()
        )
        if not patient:
            raise NotFoundError(message="Patient not found.")
        return patient

    def _memberships(self, patient_id: int) -> list[PatientLoyalty]:
        return (
            self.db.query(PatientLoyalty)
            .filter(
                PatientLoyalty.patient_id == patient_id,
                PatientLoyalty.is_deleted.is_(False),
            )
            .order_by(PatientLoyalty.id.desc())
            .all()
        )

    def _get_or_create_default_program(self) -> LoyaltyProgram:
        program = (
            self.db.query(LoyaltyProgram)
            .filter(LoyaltyProgram.is_deleted.is_(False))
            .order_by(LoyaltyProgram.id.asc())
            .first()
        )
        if program:
            return program
        program = LoyaltyProgram(
            name="Patient Loyalty",
            code=_DEFAULT_PROGRAM_CODE,
            description="Default patient rewards program.",
            points_per_currency_unit=Decimal("1"),
            minimum_redemption_points=Decimal("0"),
            is_auto_enroll=True,
        )
        self.db.add(program)
        self.db.flush()
        return program

    def _get_or_create_membership(self, patient_id: int) -> PatientLoyalty:
        memberships = self._memberships(patient_id)
        if memberships:
            return memberships[0]
        program = self._get_or_create_default_program()
        membership = PatientLoyalty(
            patient_id=patient_id,
            loyalty_program_id=program.id,
            membership_no=f"LOY-{patient_id}-{uuid.uuid4().hex[:8].upper()}",
            points_balance=Decimal("0"),
            joined_date=datetime.now(timezone.utc),
        )
        self.db.add(membership)
        self.db.flush()
        return membership

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def get_points(self, patient_id: int) -> dict:
        self._get_patient(patient_id)
        memberships = self._memberships(patient_id)
        total = sum((m.points_balance or Decimal("0")) for m in memberships)

        last_updated: Optional[datetime] = None
        if memberships:
            ids = [m.id for m in memberships]
            last_txn = (
                self.db.query(LoyaltyTransaction)
                .filter(
                    LoyaltyTransaction.patient_loyalty_id.in_(ids),
                    LoyaltyTransaction.is_deleted.is_(False),
                )
                .order_by(LoyaltyTransaction.transaction_date.desc())
                .first()
            )
            if last_txn:
                last_updated = last_txn.transaction_date
            else:
                last_updated = max(
                    (getattr(m, "updated_at", None) or m.joined_date) for m in memberships
                )

        return {
            "patient_id": patient_id,
            "total_points": int(total),
            "last_updated_at": last_updated,
        }

    def get_history(self, patient_id: int) -> list[dict]:
        self._get_patient(patient_id)
        memberships = self._memberships(patient_id)
        ids = [m.id for m in memberships]
        if not ids:
            return []
        txns = (
            self.db.query(LoyaltyTransaction)
            .filter(
                LoyaltyTransaction.patient_loyalty_id.in_(ids),
                LoyaltyTransaction.is_deleted.is_(False),
            )
            .order_by(
                LoyaltyTransaction.transaction_date.desc(),
                LoyaltyTransaction.id.desc(),
            )
            .all()
        )
        out: list[dict] = []
        for t in txns:
            ttype = t.transaction_type
            out.append(
                {
                    "id": t.id,
                    "patient_id": patient_id,
                    "points": int(t.points or 0),
                    "transaction_type": ttype.value if hasattr(ttype, "value") else str(ttype),
                    "reason": t.description or "",
                    "created_at": t.transaction_date,
                }
            )
        return out

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def earn(self, patient_id: int, points: int, reason: str) -> int:
        self._get_patient(patient_id)
        if points <= 0:
            raise BadRequestError(message="Points must be greater than zero.")
        membership = self._get_or_create_membership(patient_id)
        pts = Decimal(str(points))
        membership.points_balance = (membership.points_balance or Decimal("0")) + pts
        self.db.add(
            LoyaltyTransaction(
                patient_loyalty_id=membership.id,
                transaction_type=LoyaltyTransactionType.EARN,
                points=pts,
                description=(reason or "Points awarded").strip(),
                transaction_date=datetime.now(timezone.utc),
            )
        )
        self.db.commit()
        self.db.refresh(membership)
        return int(membership.points_balance or 0)

    def redeem(self, patient_id: int, points: int, reason: str) -> int:
        self._get_patient(patient_id)
        if points <= 0:
            raise BadRequestError(message="Points must be greater than zero.")
        memberships = self._memberships(patient_id)
        membership = memberships[0] if memberships else None
        if membership is None:
            raise BadRequestError(message="This patient has no loyalty points to redeem.")

        balance = membership.points_balance or Decimal("0")
        pts = Decimal(str(points))
        if pts > balance:
            raise BadRequestError(
                message=f"Insufficient points. Available balance is {int(balance)}."
            )

        program = membership.loyalty_program
        minimum = getattr(program, "minimum_redemption_points", None)
        if minimum and pts < Decimal(str(minimum)):
            raise BadRequestError(
                message=f"Minimum redemption is {int(minimum)} points."
            )

        membership.points_balance = balance - pts
        self.db.add(
            LoyaltyTransaction(
                patient_loyalty_id=membership.id,
                transaction_type=LoyaltyTransactionType.REDEEM,
                points=pts,
                description=(reason or "Points redeemed").strip(),
                transaction_date=datetime.now(timezone.utc),
            )
        )
        self.db.commit()
        self.db.refresh(membership)
        return int(membership.points_balance or 0)
