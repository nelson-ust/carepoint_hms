# app/services/ambulance_ext_service.py
from __future__ import annotations

"""Service for extended ambulance EMS processes: crew, PCR, fuel, trip billing, analytics."""

import calendar as _cal
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import AmbulanceChargeStatus, AmbulanceCrewRole, AmbulanceDispatchStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import (
    Ambulance,
    AmbulanceCrew,
    AmbulanceDispatch,
    AmbulanceFuelLog,
    AmbulancePatientCareReport,
    AmbulanceTripCharge,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AmbulanceExtService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _dispatch(self, dispatch_id: int) -> AmbulanceDispatch:
        d = self.db.query(AmbulanceDispatch).filter(AmbulanceDispatch.id == dispatch_id, AmbulanceDispatch.is_deleted.is_(False)).first()
        if not d:
            raise NotFoundError(message="Dispatch not found.", detail={"dispatch_id": dispatch_id})
        return d

    # ---- crew ----
    def crew_dict(self, c: AmbulanceCrew) -> dict:
        name = c.member_name
        if not name and c.staff_profile:
            name = " ".join(x for x in [getattr(c.staff_profile, "first_name", None), getattr(c.staff_profile, "last_name", None)] if x) or None
        return {"id": c.id, "dispatch_id": c.dispatch_id, "role": str(c.role), "staff_profile_id": c.staff_profile_id, "member_name": name, "notes": c.notes}

    def list_crew(self, dispatch_id: int):
        return self.db.query(AmbulanceCrew).filter(AmbulanceCrew.dispatch_id == dispatch_id, AmbulanceCrew.is_deleted.is_(False)).all()

    def add_crew(self, dispatch_id: int, payload):
        self._dispatch(dispatch_id)
        c = AmbulanceCrew(dispatch_id=dispatch_id, role=AmbulanceCrewRole(payload.role.strip().upper()), staff_profile_id=payload.staff_profile_id, member_name=payload.member_name, notes=payload.notes)
        self.db.add(c); self.db.commit(); self.db.refresh(c); return c

    def remove_crew(self, crew_id: int):
        c = self.db.query(AmbulanceCrew).filter(AmbulanceCrew.id == crew_id, AmbulanceCrew.is_deleted.is_(False)).first()
        if not c:
            raise NotFoundError(message="Crew member not found.", detail={"crew_id": crew_id})
        c.soft_delete(); self.db.commit(); return c

    # ---- PCR ----
    def pcr_dict(self, p: Optional[AmbulancePatientCareReport]) -> dict:
        if not p:
            return {}
        return {
            "id": p.id, "dispatch_id": p.dispatch_id, "chief_complaint": p.chief_complaint,
            "blood_pressure": p.blood_pressure, "pulse_rate": p.pulse_rate, "temperature_celsius": p.temperature_celsius,
            "oxygen_saturation": p.oxygen_saturation, "respiratory_rate": p.respiratory_rate,
            "interventions": p.interventions, "medications_given": p.medications_given,
            "condition_on_handover": p.condition_on_handover, "receiving_facility": p.receiving_facility,
            "receiving_staff": p.receiving_staff, "narrative": p.narrative, "updated_at": p.updated_at,
        }

    def get_pcr(self, dispatch_id: int) -> Optional[AmbulancePatientCareReport]:
        return self.db.query(AmbulancePatientCareReport).filter(AmbulancePatientCareReport.dispatch_id == dispatch_id, AmbulancePatientCareReport.is_deleted.is_(False)).first()

    def upsert_pcr(self, dispatch_id: int, payload):
        self._dispatch(dispatch_id)
        p = self.get_pcr(dispatch_id)
        data = payload.model_dump(exclude_unset=True)
        if not p:
            p = AmbulancePatientCareReport(dispatch_id=dispatch_id, **data)
            self.db.add(p)
        else:
            for k, v in data.items():
                setattr(p, k, v)
        self.db.commit(); self.db.refresh(p); return p

    # ---- fuel ----
    def fuel_dict(self, f: AmbulanceFuelLog) -> dict:
        return {"id": f.id, "ambulance_id": f.ambulance_id, "logged_at": f.logged_at, "litres": f.litres, "cost": f.cost, "odometer": f.odometer, "station": f.station, "filled_by": f.filled_by, "notes": f.notes}

    def list_fuel(self, ambulance_id: int):
        return self.db.query(AmbulanceFuelLog).filter(AmbulanceFuelLog.ambulance_id == ambulance_id, AmbulanceFuelLog.is_deleted.is_(False)).order_by(AmbulanceFuelLog.logged_at.desc()).all()

    def add_fuel(self, ambulance_id: int, payload):
        if not self.db.query(Ambulance).filter(Ambulance.id == ambulance_id, Ambulance.is_deleted.is_(False)).first():
            raise NotFoundError(message="Ambulance not found.", detail={"ambulance_id": ambulance_id})
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("logged_at", _now())
        f = AmbulanceFuelLog(ambulance_id=ambulance_id, **data)
        self.db.add(f); self.db.commit(); self.db.refresh(f); return f

    # ---- trip charges ----
    def charge_dict(self, c: AmbulanceTripCharge) -> dict:
        return {"id": c.id, "dispatch_id": c.dispatch_id, "description": c.description, "amount": c.amount, "status": str(c.status), "payer_name": c.payer_name, "charged_at": c.charged_at, "notes": c.notes}

    def list_charges(self, dispatch_id: int):
        return self.db.query(AmbulanceTripCharge).filter(AmbulanceTripCharge.dispatch_id == dispatch_id, AmbulanceTripCharge.is_deleted.is_(False)).order_by(AmbulanceTripCharge.charged_at.desc()).all()

    def add_charge(self, dispatch_id: int, payload):
        self._dispatch(dispatch_id)
        c = AmbulanceTripCharge(dispatch_id=dispatch_id, description=payload.description, amount=payload.amount, status=AmbulanceChargeStatus.PENDING, payer_name=payload.payer_name, charged_at=_now(), notes=payload.notes)
        self.db.add(c); self.db.commit(); self.db.refresh(c); return c

    def set_charge_status(self, charge_id: int, status: str):
        c = self.db.query(AmbulanceTripCharge).filter(AmbulanceTripCharge.id == charge_id, AmbulanceTripCharge.is_deleted.is_(False)).first()
        if not c:
            raise NotFoundError(message="Charge not found.", detail={"charge_id": charge_id})
        c.status = AmbulanceChargeStatus(status.strip().upper())
        self.db.commit(); self.db.refresh(c); return c

    # ---- analytics ----
    def analytics(self, *, months: int = 6) -> dict:
        now = _now()
        dispatches = self.db.query(AmbulanceDispatch).filter(AmbulanceDispatch.is_deleted.is_(False)).all()
        ambulances = self.db.query(Ambulance).filter(Ambulance.is_deleted.is_(False)).all()
        fuel = self.db.query(AmbulanceFuelLog).filter(AmbulanceFuelLog.is_deleted.is_(False)).all()
        charges = self.db.query(AmbulanceTripCharge).filter(AmbulanceTripCharge.is_deleted.is_(False)).all()

        def minutes(a, b):
            try:
                return (b - a).total_seconds() / 60.0 if a and b else None
            except Exception:
                return None

        response_times = [m for d in dispatches if (m := minutes(d.requested_at, d.arrived_at)) is not None and m >= 0]
        transport_times = [m for d in dispatches if (m := minutes(d.arrived_at, d.completed_at)) is not None and m >= 0]
        avg_response = round(sum(response_times) / len(response_times), 1) if response_times else 0.0
        avg_transport = round(sum(transport_times) / len(transport_times), 1) if transport_times else 0.0

        by_status = {str(st): sum(1 for d in dispatches if d.dispatch_status == st) for st in AmbulanceDispatchStatus}

        # monthly trip trend
        keys = []
        y, m = now.year, now.month
        for _ in range(months):
            keys.append((y, m)); m -= 1
            if m == 0:
                m = 12; y -= 1
        keys.reverse()
        trend = []
        for (yy, mm) in keys:
            trend.append({
                "month": f"{_cal.month_abbr[mm]} {str(yy)[2:]}",
                "trips": sum(1 for d in dispatches if d.requested_at and d.requested_at.year == yy and d.requested_at.month == mm),
            })

        active = (AmbulanceDispatchStatus.ASSIGNED, AmbulanceDispatchStatus.EN_ROUTE, AmbulanceDispatchStatus.ARRIVED, AmbulanceDispatchStatus.PATIENT_PICKED)
        total_fuel_litres = sum((f.litres for f in fuel), Decimal("0"))
        total_fuel_cost = sum((f.cost for f in fuel if f.cost is not None), Decimal("0"))
        billed = sum((c.amount for c in charges), Decimal("0"))
        collected = sum((c.amount for c in charges if c.status == AmbulanceChargeStatus.PAID), Decimal("0"))

        return {
            "fleet_total": len(ambulances),
            "trips_total": len(dispatches),
            "trips_completed": by_status.get(str(AmbulanceDispatchStatus.COMPLETED), 0),
            "trips_active": sum(1 for d in dispatches if d.dispatch_status in active),
            "avg_response_minutes": avg_response,
            "avg_transport_minutes": avg_transport,
            "by_status": by_status,
            "trip_trend": trend,
            "fuel_litres": str(total_fuel_litres),
            "fuel_cost": str(total_fuel_cost),
            "revenue_billed": str(billed),
            "revenue_collected": str(collected),
        }
