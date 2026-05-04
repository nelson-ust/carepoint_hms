# app/services/vital_sign_service.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import VisitStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import VitalSign
from app.repositories.vital_sign_repository import VitalSignRepository
from app.schemas.vital_sign_schema import VitalSignCreateSchema


_TERMINAL = {VisitStatus.COMPLETED, VisitStatus.CANCELLED}


def _compute_bmi(weight_kg: Optional[Decimal], height_cm: Optional[Decimal]) -> Optional[Decimal]:
    if not weight_kg or not height_cm:
        return None
    try:
        height_m = Decimal(height_cm) / Decimal("100")
        if height_m <= 0:
            return None
        bmi = Decimal(weight_kg) / (height_m * height_m)
        return bmi.quantize(Decimal("0.01"))
    except Exception:
        return None


class VitalSignService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = VitalSignRepository(db)

    def list_for_visit(self, visit_id: int, *, skip: int = 0, limit: int = 50):
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)

    def latest_for_visit(self, visit_id: int) -> Optional[VitalSign]:
        return self.repository.latest_for_visit(visit_id)

    def get(self, vital_id: int) -> VitalSign:
        return self.repository.get_required_by_id(vital_id)

    def create(self, payload: VitalSignCreateSchema, *, actor_user_id: Optional[int] = None) -> VitalSign:
        visit = self.repository.get_required_visit(payload.visit_id)
        if visit.status in _TERMINAL:
            raise BadRequestError(
                message="Cannot record vital signs for a closed visit.",
                detail={"visit_status": str(visit.status)},
            )

        data = payload.model_dump(exclude_unset=True)
        # Auto-derive BMI when weight + height are given but BMI is not.
        if data.get("bmi") is None:
            derived_bmi = _compute_bmi(data.get("weight_kg"), data.get("height_cm"))
            if derived_bmi is not None:
                data["bmi"] = derived_bmi

        data.setdefault("recorded_at", datetime.now(timezone.utc))
        record = self.repository.create(**data)
        self.db.commit()
        return self.repository.get_required_by_id(record.id)
