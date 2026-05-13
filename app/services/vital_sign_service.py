# app/services/vital_sign_service.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import ServicePointType, VisitStatus
from app.core.exceptions import BadRequestError
from app.models.all_models import VitalSign
from app.repositories.vital_sign_repository import VitalSignRepository
from app.schemas.vital_sign_schema import VitalSignCreateSchema
from app.utils.visit_routing import validate_visit_sdp_activity


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


def _compute_mews(pulse_rate: Optional[int], respiratory_rate: Optional[int], systolic_bp: Optional[int], temp: Optional[Decimal]) -> Optional[int]:
    """Calculates Modified Early Warning Score (MEWS). Returns None if not enough data."""
    if pulse_rate is None or respiratory_rate is None or systolic_bp is None or temp is None:
        return None
    
    score = 0
    
    # Respiratory Rate
    if respiratory_rate <= 8: score += 2
    elif 15 <= respiratory_rate <= 20: score += 1
    elif 21 <= respiratory_rate <= 29: score += 2
    elif respiratory_rate >= 30: score += 3

    # Pulse
    if pulse_rate <= 40: score += 2
    elif 41 <= pulse_rate <= 50: score += 1
    elif 101 <= pulse_rate <= 110: score += 1
    elif 111 <= pulse_rate <= 129: score += 2
    elif pulse_rate >= 130: score += 3

    # Systolic BP
    if systolic_bp <= 70: score += 3
    elif 71 <= systolic_bp <= 80: score += 2
    elif 81 <= systolic_bp <= 100: score += 1
    elif systolic_bp >= 200: score += 2

    # Temperature
    t = float(temp)
    if t <= 35.0: score += 2
    elif 35.1 <= t <= 36.0: score += 1
    elif 38.1 <= t <= 38.5: score += 1
    elif t >= 38.6: score += 2

    return score


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

        # Enforce SDP validation and get current step
        current_step = validate_visit_sdp_activity(
            self.db,
            visit_id=visit.id,
            required_sdp_types=[ServicePointType.TRIAGE, ServicePointType.EMERGENCY, ServicePointType.WARD],
            activity_name="Vital Signs capture",
        )

        data = payload.model_dump(exclude_unset=True)
        data["visit_flow_step_id"] = current_step.id
        # Auto-derive BMI when weight + height are given but BMI is not.
        if data.get("bmi") is None:
            derived_bmi = _compute_bmi(data.get("weight_kg"), data.get("height_cm"))
            if derived_bmi is not None:
                data["bmi"] = derived_bmi
                
        # Auto-compute MEWS
        mews = _compute_mews(data.get("pulse_rate"), data.get("respiratory_rate"), data.get("systolic_bp"), data.get("temperature_celsius"))
        if mews is not None:
            data["mews_score"] = mews
            # If MEWS is critically high (e.g., >= 5), we would trigger an emergency push notification to ward nurses
            if mews >= 5:
                # TODO: Trigger NotificationDispatcher.dispatch(SYSTEM_ALERT, message="Sepsis Alert / Code Blue Triggered!")
                pass

        data.setdefault("recorded_at", datetime.now(timezone.utc))
        record = self.repository.create(**data)
        self.db.commit()
        return self.repository.get_required_by_id(record.id)
