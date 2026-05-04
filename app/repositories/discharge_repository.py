# app/repositories/discharge_repository.py
from __future__ import annotations

"""
Repository for the inpatient discharge record.

A ``Discharge`` row is the clinical artefact attached to a single admission.
Each admission can have at most one discharge — enforced at the model layer
by the ``unique=True`` constraint on ``Discharge.admission_id``.

This repository is deliberately small. The heavy orchestration (free the
bed, flip admission status, capture final bed-day charges, optionally close
the visit) lives in :mod:`app.services.discharge_service` so a single
transaction covers the entire close-out.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import NotFoundError
from app.models.all_models import Discharge


class DischargeRepository:
    """Persistence helpers for ``Discharge``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ============================================================
    # LOOKUPS
    # ============================================================

    def get_by_id(self, discharge_id: int) -> Optional[Discharge]:
        """Fetch a discharge by primary key."""
        return (
            self.db.query(Discharge)
            .options(joinedload(Discharge.admission))
            .filter(
                Discharge.id == discharge_id,
                Discharge.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, discharge_id: int) -> Discharge:
        d = self.get_by_id(discharge_id)
        if not d:
            raise NotFoundError(
                message="Discharge not found.",
                detail={"discharge_id": discharge_id},
            )
        return d

    def get_for_admission(self, admission_id: int) -> Optional[Discharge]:
        """Discharge tied to an admission, or None if not yet discharged."""
        return (
            self.db.query(Discharge)
            .filter(
                Discharge.admission_id == admission_id,
                Discharge.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # CREATE / SAVE
    # ============================================================

    def create_discharge(
        self,
        *,
        admission_id: int,
        discharged_by_staff_id: Optional[int],
        discharge_date: datetime,
        discharge_condition: Optional[str],
        discharge_summary: Optional[str],
        follow_up_instruction: Optional[str],
    ) -> Discharge:
        """Persist a new discharge row. The caller manages commit."""
        discharge = Discharge(
            admission_id=admission_id,
            discharged_by_staff_id=discharged_by_staff_id,
            discharge_date=discharge_date or datetime.now(timezone.utc),
            discharge_condition=discharge_condition,
            discharge_summary=discharge_summary,
            follow_up_instruction=follow_up_instruction,
        )
        self.db.add(discharge)
        self.db.flush()
        self.db.refresh(discharge)
        return discharge

    def save(self, discharge: Discharge) -> Discharge:
        """Generic upsert."""
        self.db.add(discharge)
        self.db.flush()
        self.db.refresh(discharge)
        return discharge
