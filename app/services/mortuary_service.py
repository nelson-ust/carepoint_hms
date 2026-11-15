# app/services/mortuary_service.py
from __future__ import annotations

"""
Service layer for the Mortuary / Morgue management module.

Responsibilities
----------------
- Storage-unit master data (cold chambers / freezers / shelves) and live
  occupancy / status derivation.
- Deceased-record lifecycle for both IN_HOSPITAL deaths (linked to a patient /
  visit) and BROUGHT_IN bodies (self-contained demographics):
  REGISTERED -> IN_STORAGE -> RELEASED / TRANSFERRED.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.enums import (
    DeceasedSource,
    DeceasedStatus,
    MortuaryUnitStatus,
    MortuaryUnitType,
    VisitStatus,
    AutopsyType,
    AutopsyStatus,
    EmbalmingStatus,
    MortuaryEffectStatus,
    MortuaryChargeType,
    MortuaryChargeStatus,
    MortuaryPaymentMethod,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import (
    DeceasedRecord,
    MortuaryUnit,
    Patient,
    PatientDeathRecord,
    Visit,
    MortuaryAutopsy,
    MortuaryEmbalming,
    MortuaryEffect,
    MortuaryViewing,
    MortuaryCharge,
    MortuaryDeathCertificate,
    MortuaryPayment,
)
from app.schemas.mortuary_schemas import (
    DeathRecordCreateSchema,
    DeceasedAssignStorageSchema,
    MortuaryPaymentCreateSchema,
    DeceasedRegisterSchema,
    DeceasedReleaseSchema,
    DeceasedUpdateSchema,
    MortuaryUnitCreateSchema,
    MortuaryUnitUpdateSchema,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Records that still physically occupy a storage slot.
_ACTIVE_STATUSES = (DeceasedStatus.REGISTERED, DeceasedStatus.IN_STORAGE)


class MortuaryService:
    """Mortuary storage + deceased-record operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ============================================================
    # STORAGE UNITS
    # ============================================================

    def _unit_occupancy(self, unit_id: int) -> int:
        return (
            self.db.query(func.count(DeceasedRecord.id))
            .filter(
                DeceasedRecord.is_deleted.is_(False),
                DeceasedRecord.mortuary_unit_id == unit_id,
                DeceasedRecord.status.in_(_ACTIVE_STATUSES),
            )
            .scalar()
            or 0
        )

    def _derive_unit_status(self, unit: MortuaryUnit, occupied: int) -> MortuaryUnitStatus:
        if unit.status == MortuaryUnitStatus.OUT_OF_SERVICE:
            return MortuaryUnitStatus.OUT_OF_SERVICE
        if occupied <= 0:
            return MortuaryUnitStatus.AVAILABLE
        if occupied >= unit.capacity:
            return MortuaryUnitStatus.FULL
        return MortuaryUnitStatus.PARTIAL

    def _refresh_unit_status(self, unit: MortuaryUnit) -> None:
        if unit.status == MortuaryUnitStatus.OUT_OF_SERVICE:
            return
        occupied = self._unit_occupancy(unit.id)
        unit.status = self._derive_unit_status(unit, occupied)

    def unit_dict(self, unit: MortuaryUnit) -> dict:
        occupied = self._unit_occupancy(unit.id)
        return {
            "id": unit.id,
            "code": unit.code,
            "name": unit.name,
            "unit_type": str(unit.unit_type),
            "capacity": unit.capacity,
            "status": str(unit.status),
            "location": unit.location,
            "temperature_c": unit.temperature_c,
            "notes": unit.notes,
            "occupied": occupied,
            "available_slots": max(unit.capacity - occupied, 0),
            "created_at": unit.created_at,
            "updated_at": unit.updated_at,
        }

    def list_units(self, *, skip=0, limit=100, status: Optional[str] = None):
        q = self.db.query(MortuaryUnit).filter(MortuaryUnit.is_deleted.is_(False))
        if status:
            q = q.filter(MortuaryUnit.status == MortuaryUnitStatus(status.strip().upper()))
        total = q.count()
        items = q.order_by(MortuaryUnit.code.asc()).offset(skip).limit(limit).all()
        return items, total

    def get_unit(self, unit_id: int) -> MortuaryUnit:
        unit = (
            self.db.query(MortuaryUnit)
            .filter(MortuaryUnit.id == unit_id, MortuaryUnit.is_deleted.is_(False))
            .first()
        )
        if not unit:
            raise NotFoundError(message="Storage unit not found.", detail={"unit_id": unit_id})
        return unit

    def create_unit(self, payload: MortuaryUnitCreateSchema) -> MortuaryUnit:
        exists = (
            self.db.query(MortuaryUnit)
            .filter(MortuaryUnit.code == payload.code, MortuaryUnit.is_deleted.is_(False))
            .first()
        )
        if exists:
            raise BadRequestError(message="A storage unit with this code already exists.", detail={"code": payload.code})
        data = payload.model_dump(exclude_unset=True)
        unit = MortuaryUnit(
            unit_type=MortuaryUnitType(data.pop("unit_type", "COLD_CHAMBER")),
            status=MortuaryUnitStatus.AVAILABLE,
            **data,
        )
        self.db.add(unit)
        self.db.commit()
        self.db.refresh(unit)
        return unit

    def update_unit(self, unit_id: int, payload: MortuaryUnitUpdateSchema) -> MortuaryUnit:
        unit = self.get_unit(unit_id)
        data = payload.model_dump(exclude_unset=True)
        if "unit_type" in data and data["unit_type"]:
            unit.unit_type = MortuaryUnitType(data.pop("unit_type"))
        if "status" in data and data["status"]:
            unit.status = MortuaryUnitStatus(data.pop("status"))
        for k, v in data.items():
            setattr(unit, k, v)
        # Keep derived status honest unless the caller forced OUT_OF_SERVICE.
        self._refresh_unit_status(unit)
        self.db.commit()
        self.db.refresh(unit)
        return unit

    def delete_unit(self, unit_id: int) -> MortuaryUnit:
        unit = self.get_unit(unit_id)
        if self._unit_occupancy(unit.id) > 0:
            raise BadRequestError(
                message="Cannot remove a storage unit that still holds bodies.",
                detail={"unit_id": unit.id},
            )
        unit.soft_delete()
        self.db.commit()
        return unit

    # ============================================================
    # DECEASED RECORDS
    # ============================================================

    def _generate_tag(self) -> str:
        year = _utcnow().year
        count = (
            self.db.query(func.count(DeceasedRecord.id))
            .filter(func.extract("year", DeceasedRecord.registered_at) == year)
            .scalar()
            or 0
        )
        # Find the next free tag defensively (gaps / races).
        n = count + 1
        while True:
            tag = f"MG-{year}-{n:04d}"
            clash = self.db.query(DeceasedRecord.id).filter(DeceasedRecord.tag_number == tag).first()
            if not clash:
                return tag
            n += 1

    def record_dict(self, r: DeceasedRecord) -> dict:
        return {
            "id": r.id,
            "tag_number": r.tag_number,
            "source": str(r.source),
            "status": str(r.status),
            "patient_id": r.patient_id,
            "visit_id": r.visit_id,
            "deceased_name": r.deceased_name,
            "gender": r.gender,
            "age_years": r.age_years,
            "date_of_death": r.date_of_death,
            "cause_of_death": r.cause_of_death,
            "brought_in_by": r.brought_in_by,
            "brought_in_contact": r.brought_in_contact,
            "from_location": r.from_location,
            "next_of_kin_name": r.next_of_kin_name,
            "next_of_kin_phone": r.next_of_kin_phone,
            "next_of_kin_relationship": r.next_of_kin_relationship,
            "is_police_case": bool(r.is_police_case),
            "police_reference": r.police_reference,
            "mortuary_unit_id": r.mortuary_unit_id,
            "mortuary_unit_name": r.mortuary_unit.name if r.mortuary_unit else None,
            "received_by_staff_id": r.received_by_staff_id,
            "registered_at": r.registered_at,
            "released_to_name": r.released_to_name,
            "released_to_relationship": r.released_to_relationship,
            "released_to_contact": r.released_to_contact,
            "release_authorized_by": r.release_authorized_by,
            "released_by_staff_id": r.released_by_staff_id,
            "released_at": r.released_at,
            "release_notes": r.release_notes,
            "notes": r.notes,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }

    def list_deceased(
        self,
        *,
        skip=0,
        limit=50,
        status: Optional[str] = None,
        source: Optional[str] = None,
        unit_id: Optional[int] = None,
        police_only: bool = False,
        search: Optional[str] = None,
    ):
        q = self.db.query(DeceasedRecord).filter(DeceasedRecord.is_deleted.is_(False))
        if status:
            q = q.filter(DeceasedRecord.status == DeceasedStatus(status.strip().upper()))
        if source:
            q = q.filter(DeceasedRecord.source == DeceasedSource(source.strip().upper()))
        if unit_id:
            q = q.filter(DeceasedRecord.mortuary_unit_id == unit_id)
        if police_only:
            q = q.filter(DeceasedRecord.is_police_case.is_(True))
        if search:
            like = f"%{search.strip()}%"
            q = q.filter(or_(DeceasedRecord.deceased_name.ilike(like), DeceasedRecord.tag_number.ilike(like)))
        total = q.count()
        items = q.order_by(DeceasedRecord.registered_at.desc()).offset(skip).limit(limit).all()
        return items, total

    def get_deceased(self, record_id: int) -> DeceasedRecord:
        r = (
            self.db.query(DeceasedRecord)
            .filter(DeceasedRecord.id == record_id, DeceasedRecord.is_deleted.is_(False))
            .first()
        )
        if not r:
            raise NotFoundError(message="Deceased record not found.", detail={"record_id": record_id})
        return r

    def _hydrate_from_patient(self, payload_data: dict) -> dict:
        """Fill missing demographics from the linked patient when available."""
        pid = payload_data.get("patient_id")
        if not pid:
            return payload_data
        patient = self.db.query(Patient).filter(Patient.id == pid, Patient.is_deleted.is_(False)).first()
        if not patient:
            raise BadRequestError(message="Linked patient not found.", detail={"patient_id": pid})
        if not payload_data.get("deceased_name"):
            name = (
                getattr(patient, "full_name", None)
                or " ".join(x for x in [getattr(patient, "first_name", None), getattr(patient, "last_name", None)] if x)
                or None
            )
            if name:
                payload_data["deceased_name"] = name
        if not payload_data.get("gender") and getattr(patient, "gender", None):
            payload_data["gender"] = str(patient.gender)
        return payload_data

    def register(self, payload: DeceasedRegisterSchema) -> DeceasedRecord:
        data = payload.model_dump(exclude_unset=True)
        source = DeceasedSource(data.pop("source", "IN_HOSPITAL"))

        # Depositing an already-recorded in-hospital death: copy everything from
        # the death record and mark it deposited.
        death_id = data.pop("death_record_id", None)
        if death_id:
            death = self.get_death(death_id)
            if death.is_deposited:
                raise BadRequestError(
                    message="This death has already been deposited to the mortuary.",
                    detail={"death_record_id": death_id},
                )
            rec = self._build_deceased_from_death(
                death,
                mortuary_unit_id=data.get("mortuary_unit_id"),
                received_by_staff_id=data.get("received_by_staff_id"),
                next_of_kin_name=data.get("next_of_kin_name"),
                next_of_kin_phone=data.get("next_of_kin_phone"),
                next_of_kin_relationship=data.get("next_of_kin_relationship"),
                is_police_case=bool(data.get("is_police_case", False)),
                police_reference=data.get("police_reference"),
                tag_number=data.get("tag_number"),
                notes=data.get("notes"),
            )
            self.db.commit()
            self.db.refresh(rec)
            return rec

        if source == DeceasedSource.IN_HOSPITAL and data.get("patient_id"):
            data = self._hydrate_from_patient(data)
        if not data.get("deceased_name"):
            raise BadRequestError(message="deceased_name is required (or link a patient).")

        unit_id = data.get("mortuary_unit_id")
        tag = data.pop("tag_number", None)
        status = DeceasedStatus.IN_STORAGE if unit_id else DeceasedStatus.REGISTERED

        if unit_id:
            unit = self.get_unit(unit_id)
            if unit.status == MortuaryUnitStatus.OUT_OF_SERVICE:
                raise BadRequestError(message="Storage unit is out of service.", detail={"unit_id": unit_id})
            if self._unit_occupancy(unit.id) >= unit.capacity:
                raise BadRequestError(message="Storage unit is full.", detail={"unit_id": unit_id})

        record = DeceasedRecord(source=source, status=status, registered_at=_utcnow(), **data)
        record.tag_number = tag or self._generate_tag()
        self.db.add(record)
        self.db.flush()

        if unit_id:
            self._refresh_unit_status(self.get_unit(unit_id))
        self.db.commit()
        self.db.refresh(record)
        return record

    def update(self, record_id: int, payload: DeceasedUpdateSchema) -> DeceasedRecord:
        r = self.get_deceased(record_id)
        if r.status in (DeceasedStatus.RELEASED, DeceasedStatus.TRANSFERRED):
            raise BadRequestError(message="A released record can no longer be edited.", detail={"record_id": record_id})
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(r, k, v)
        self.db.commit()
        self.db.refresh(r)
        return r

    def assign_storage(self, record_id: int, payload: DeceasedAssignStorageSchema) -> DeceasedRecord:
        r = self.get_deceased(record_id)
        if r.status in (DeceasedStatus.RELEASED, DeceasedStatus.TRANSFERRED):
            raise BadRequestError(message="A released record cannot be moved into storage.", detail={"record_id": record_id})

        new_unit = self.get_unit(payload.mortuary_unit_id)
        if new_unit.status == MortuaryUnitStatus.OUT_OF_SERVICE:
            raise BadRequestError(message="Storage unit is out of service.", detail={"unit_id": new_unit.id})
        if new_unit.id != r.mortuary_unit_id and self._unit_occupancy(new_unit.id) >= new_unit.capacity:
            raise BadRequestError(message="Storage unit is full.", detail={"unit_id": new_unit.id})

        old_unit_id = r.mortuary_unit_id
        r.mortuary_unit_id = new_unit.id
        r.status = DeceasedStatus.IN_STORAGE
        if payload.received_by_staff_id is not None:
            r.received_by_staff_id = payload.received_by_staff_id
        self.db.flush()

        self._refresh_unit_status(new_unit)
        if old_unit_id and old_unit_id != new_unit.id:
            self._refresh_unit_status(self.get_unit(old_unit_id))
        self.db.commit()
        self.db.refresh(r)
        return r

    def release(self, record_id: int, payload: DeceasedReleaseSchema) -> DeceasedRecord:
        from decimal import Decimal as _D
        r = self.get_deceased(record_id)
        if r.status in (DeceasedStatus.RELEASED, DeceasedStatus.TRANSFERRED):
            raise BadRequestError(message="This record has already been released.", detail={"record_id": record_id})

        data = payload.model_dump(exclude_unset=True)
        transfer = data.pop("transfer", False)
        storage_rate = data.pop("storage_daily_rate", None)
        payment = data.pop("payment", None)
        waive = data.pop("waive_outstanding", False)
        waiver_reason = data.pop("waiver_reason", None)

        # 1) Accrue a storage charge for the time held (if a daily rate is given).
        if storage_rate is not None and _D(str(storage_rate)) > 0:
            self._accrue_storage_fee(r, _D(str(storage_rate)))

        # 2) Collect payment presented at release.
        if payment and payment.get("amount") is not None and _D(str(payment["amount"])) > 0:
            self._record_payment(
                r.id,
                amount=_D(str(payment["amount"])),
                method=payment.get("method", "CASH"),
                reference=payment.get("reference"),
                payer_name=payment.get("payer_name") or data.get("released_to_name"),
                received_by_staff_id=payment.get("received_by_staff_id") or data.get("released_by_staff_id"),
                notes=payment.get("notes"),
            )

        # 3) Settlement gate — the bill must be cleared (paid or waived) to release.
        summary = self._bill_figures(r.id)
        outstanding = summary["outstanding"]
        if outstanding > 0:
            if waive:
                authoriser = data.get("release_authorized_by") or waiver_reason
                if not authoriser:
                    raise BadRequestError(
                        message="Waiving an outstanding balance requires an authoriser.",
                        detail={"outstanding": str(outstanding)},
                    )
                self._waive_pending(r.id, waiver_reason or "Waived at release")
            else:
                raise BadRequestError(
                    message=f"Outstanding balance of {outstanding} must be settled or waived before release.",
                    detail={
                        "outstanding": str(outstanding),
                        "total_billed": str(summary["total_billed"]),
                        "total_paid": str(summary["total_paid"]),
                    },
                )

        # 4) Perform the release.
        for k, v in data.items():
            setattr(r, k, v)
        r.released_at = r.released_at or _utcnow()
        r.status = DeceasedStatus.TRANSFERRED if transfer else DeceasedStatus.RELEASED

        freed_unit_id = r.mortuary_unit_id
        self.db.flush()
        if freed_unit_id:
            self._refresh_unit_status(self.get_unit(freed_unit_id))
        self.db.commit()
        self.db.refresh(r)
        return r

    # ============================================================
    # STATS
    # ============================================================

    def stats(self) -> dict:
        base = self.db.query(DeceasedRecord).filter(DeceasedRecord.is_deleted.is_(False))

        def count_status(st: DeceasedStatus) -> int:
            return base.filter(DeceasedRecord.status == st).count()

        by_status = {str(st): count_status(st) for st in DeceasedStatus}
        units = self.db.query(MortuaryUnit).filter(MortuaryUnit.is_deleted.is_(False)).all()
        capacity_total = sum(u.capacity for u in units)
        occupied_total = sum(self._unit_occupancy(u.id) for u in units)

        return {
            "in_storage": by_status.get(str(DeceasedStatus.IN_STORAGE), 0),
            "registered": by_status.get(str(DeceasedStatus.REGISTERED), 0),
            "released": by_status.get(str(DeceasedStatus.RELEASED), 0)
            + by_status.get(str(DeceasedStatus.TRANSFERRED), 0),
            "in_hospital_total": base.filter(DeceasedRecord.source == DeceasedSource.IN_HOSPITAL).count(),
            "brought_in_total": base.filter(DeceasedRecord.source == DeceasedSource.BROUGHT_IN).count(),
            "police_cases": base.filter(DeceasedRecord.is_police_case.is_(True)).count(),
            "units_total": len(units),
            "capacity_total": capacity_total,
            "occupied_total": occupied_total,
            "by_status": by_status,
        }

    # ============================================================
    # PATIENT DEATH RECORDS
    # ============================================================

    def _patient_name(self, patient: Optional[Patient]) -> str:
        if not patient:
            return "Unknown"
        name = " ".join(
            x for x in [getattr(patient, "first_name", None), getattr(patient, "last_name", None)] if x
        )
        return name or getattr(patient, "full_name", None) or f"Patient #{patient.id}"

    def _build_deceased_from_death(
        self,
        death: PatientDeathRecord,
        *,
        mortuary_unit_id: Optional[int] = None,
        received_by_staff_id: Optional[int] = None,
        next_of_kin_name: Optional[str] = None,
        next_of_kin_phone: Optional[str] = None,
        next_of_kin_relationship: Optional[str] = None,
        is_police_case: bool = False,
        police_reference: Optional[str] = None,
        tag_number: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> DeceasedRecord:
        """Create the mortuary record for a declared death and mark it deposited.

        Does NOT commit — the caller owns the transaction.
        """
        patient = death.patient or self.db.query(Patient).filter(Patient.id == death.patient_id).first()
        name = self._patient_name(patient)
        gender = str(patient.gender) if patient and getattr(patient, "gender", None) else None

        if mortuary_unit_id:
            unit = self.get_unit(mortuary_unit_id)
            if unit.status == MortuaryUnitStatus.OUT_OF_SERVICE:
                raise BadRequestError(message="Storage unit is out of service.", detail={"unit_id": mortuary_unit_id})
            if self._unit_occupancy(unit.id) >= unit.capacity:
                raise BadRequestError(message="Storage unit is full.", detail={"unit_id": mortuary_unit_id})

        rec = DeceasedRecord(
            source=DeceasedSource.IN_HOSPITAL,
            status=DeceasedStatus.IN_STORAGE if mortuary_unit_id else DeceasedStatus.REGISTERED,
            registered_at=_utcnow(),
            patient_id=death.patient_id,
            visit_id=death.visit_id,
            deceased_name=name,
            gender=gender,
            date_of_death=death.date_of_death,
            cause_of_death=death.cause_of_death,
            mortuary_unit_id=mortuary_unit_id,
            received_by_staff_id=received_by_staff_id,
            next_of_kin_name=next_of_kin_name,
            next_of_kin_phone=next_of_kin_phone,
            next_of_kin_relationship=next_of_kin_relationship,
            is_police_case=bool(is_police_case),
            police_reference=police_reference if is_police_case else None,
            notes=notes,
        )
        rec.tag_number = tag_number or self._generate_tag()
        self.db.add(rec)
        self.db.flush()
        if mortuary_unit_id:
            self._refresh_unit_status(self.get_unit(mortuary_unit_id))
        death.is_deposited = True
        death.deceased_record_id = rec.id
        return rec

    def death_dict(self, d: PatientDeathRecord) -> dict:
        patient = d.patient
        return {
            "id": d.id,
            "patient_id": d.patient_id,
            "visit_id": d.visit_id,
            "patient_name": self._patient_name(patient),
            "hospital_number": getattr(patient, "hospital_number", None),
            "visit_code": d.visit.visit_code if d.visit else None,
            "date_of_death": d.date_of_death,
            "cause_of_death": d.cause_of_death,
            "place_of_death": d.place_of_death,
            "declared_by_staff_id": d.declared_by_staff_id,
            "notes": d.notes,
            "is_deposited": bool(d.is_deposited),
            "deceased_record_id": d.deceased_record_id,
            "created_at": d.created_at,
            "updated_at": d.updated_at,
        }

    def get_death(self, death_id: int) -> PatientDeathRecord:
        d = (
            self.db.query(PatientDeathRecord)
            .filter(PatientDeathRecord.id == death_id, PatientDeathRecord.is_deleted.is_(False))
            .first()
        )
        if not d:
            raise NotFoundError(message="Death record not found.", detail={"death_id": death_id})
        return d

    def list_deaths(self, *, skip=0, limit=100, deposited: Optional[bool] = None):
        q = self.db.query(PatientDeathRecord).filter(PatientDeathRecord.is_deleted.is_(False))
        if deposited is not None:
            q = q.filter(PatientDeathRecord.is_deposited.is_(deposited))
        total = q.count()
        items = q.order_by(PatientDeathRecord.date_of_death.desc()).offset(skip).limit(limit).all()
        return items, total

    def record_death(self, payload: DeathRecordCreateSchema):
        """Declare a patient dead against a visit; optionally deposit to mortuary.

        Returns a tuple (death_record, deceased_record_or_None).
        """
        patient = (
            self.db.query(Patient)
            .filter(Patient.id == payload.patient_id, Patient.is_deleted.is_(False))
            .first()
        )
        if not patient:
            raise BadRequestError(message="Patient not found.", detail={"patient_id": payload.patient_id})

        visit = (
            self.db.query(Visit)
            .filter(Visit.id == payload.visit_id, Visit.is_deleted.is_(False))
            .first()
        )
        if not visit:
            raise BadRequestError(message="Visit not found.", detail={"visit_id": payload.visit_id})
        if visit.patient_id != payload.patient_id:
            raise BadRequestError(
                message="The visit does not belong to this patient.",
                detail={"visit_id": payload.visit_id, "patient_id": payload.patient_id},
            )

        existing = (
            self.db.query(PatientDeathRecord)
            .filter(
                PatientDeathRecord.patient_id == payload.patient_id,
                PatientDeathRecord.is_deleted.is_(False),
            )
            .first()
        )
        if existing:
            raise BadRequestError(
                message="A death has already been recorded for this patient.",
                detail={"patient_id": payload.patient_id, "death_record_id": existing.id},
            )

        death = PatientDeathRecord(
            patient_id=payload.patient_id,
            visit_id=payload.visit_id,
            declared_by_staff_id=payload.declared_by_staff_id,
            date_of_death=payload.date_of_death,
            cause_of_death=payload.cause_of_death,
            place_of_death=payload.place_of_death or "Hospital",
            notes=payload.notes,
            is_deposited=False,
        )
        self.db.add(death)

        # Close the visit and mark it deceased.
        visit.status = VisitStatus.DECEASED
        if not visit.check_out_time:
            visit.check_out_time = payload.date_of_death or _utcnow()
        self.db.flush()

        created_record = None
        if payload.deposit_to_mortuary:
            created_record = self._build_deceased_from_death(
                death,
                mortuary_unit_id=payload.mortuary_unit_id,
                next_of_kin_name=payload.next_of_kin_name,
                next_of_kin_phone=payload.next_of_kin_phone,
                next_of_kin_relationship=payload.next_of_kin_relationship,
                is_police_case=payload.is_police_case,
                police_reference=payload.police_reference,
                tag_number=payload.tag_number,
            )

        self.db.commit()
        self.db.refresh(death)
        if created_record is not None:
            self.db.refresh(created_record)
        return death, created_record

    # ============================================================
    # STANDARD MORTUARY SUB-OPERATIONS
    # ============================================================

    def _label(self, rec: DeceasedRecord) -> dict:
        return {"deceased_name": rec.deceased_name, "tag_number": rec.tag_number}

    # ---- Autopsies ----
    def autopsy_dict(self, a: MortuaryAutopsy) -> dict:
        d = {
            "id": a.id, "deceased_record_id": a.deceased_record_id,
            "autopsy_type": str(a.autopsy_type), "status": str(a.status),
            "requested_by": a.requested_by, "pathologist": a.pathologist,
            "scheduled_at": a.scheduled_at, "performed_at": a.performed_at,
            "findings": a.findings, "cause_of_death_confirmed": a.cause_of_death_confirmed,
            "consent_by": a.consent_by, "notes": a.notes,
            "created_at": a.created_at, "updated_at": a.updated_at,
        }
        if a.deceased_record:
            d.update(self._label(a.deceased_record))
        return d

    def create_autopsy(self, record_id, payload):
        self.get_deceased(record_id)
        status = AutopsyStatus.SCHEDULED if payload.scheduled_at else AutopsyStatus.REQUESTED
        a = MortuaryAutopsy(
            deceased_record_id=record_id,
            autopsy_type=AutopsyType(payload.autopsy_type.strip().upper()),
            status=status, requested_by=payload.requested_by, pathologist=payload.pathologist,
            scheduled_at=payload.scheduled_at, consent_by=payload.consent_by, notes=payload.notes,
        )
        self.db.add(a); self.db.commit(); self.db.refresh(a); return a

    def update_autopsy(self, autopsy_id, payload):
        a = self.db.query(MortuaryAutopsy).filter(MortuaryAutopsy.id == autopsy_id, MortuaryAutopsy.is_deleted.is_(False)).first()
        if not a:
            raise NotFoundError(message="Autopsy not found.", detail={"autopsy_id": autopsy_id})
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"]:
            a.status = AutopsyStatus(data.pop("status").strip().upper())
            if a.status == AutopsyStatus.COMPLETED and not a.performed_at:
                a.performed_at = _utcnow()
        for k, v in data.items():
            setattr(a, k, v)
        self.db.commit(); self.db.refresh(a); return a

    def list_autopsies(self, *, record_id=None, status=None, skip=0, limit=100):
        q = self.db.query(MortuaryAutopsy).filter(MortuaryAutopsy.is_deleted.is_(False))
        if record_id:
            q = q.filter(MortuaryAutopsy.deceased_record_id == record_id)
        if status:
            q = q.filter(MortuaryAutopsy.status == AutopsyStatus(status.strip().upper()))
        total = q.count()
        items = q.order_by(MortuaryAutopsy.date_created.desc()).offset(skip).limit(limit).all()
        return items, total

    # ---- Embalming ----
    def embalming_dict(self, e: MortuaryEmbalming) -> dict:
        return {
            "id": e.id, "deceased_record_id": e.deceased_record_id, "status": str(e.status),
            "embalmer_name": e.embalmer_name, "method": e.method, "chemicals_used": e.chemicals_used,
            "embalmed_at": e.embalmed_at, "notes": e.notes,
            "created_at": e.created_at, "updated_at": e.updated_at,
        }

    def create_embalming(self, record_id, payload):
        self.get_deceased(record_id)
        completed = payload.mark_completed or payload.embalmed_at is not None
        e = MortuaryEmbalming(
            deceased_record_id=record_id,
            status=EmbalmingStatus.COMPLETED if completed else EmbalmingStatus.PENDING,
            embalmer_name=payload.embalmer_name, method=payload.method,
            chemicals_used=payload.chemicals_used,
            embalmed_at=payload.embalmed_at or (_utcnow() if completed else None),
            notes=payload.notes,
        )
        self.db.add(e); self.db.commit(); self.db.refresh(e); return e

    def list_embalming(self, record_id):
        return (
            self.db.query(MortuaryEmbalming)
            .filter(MortuaryEmbalming.deceased_record_id == record_id, MortuaryEmbalming.is_deleted.is_(False))
            .order_by(MortuaryEmbalming.date_created.desc()).all()
        )

    # ---- Personal effects ----
    def effect_dict(self, e: MortuaryEffect) -> dict:
        return {
            "id": e.id, "deceased_record_id": e.deceased_record_id, "status": str(e.status),
            "item": e.item, "quantity": e.quantity, "description": e.description,
            "received_from": e.received_from, "received_at": e.received_at,
            "released_to": e.released_to, "released_at": e.released_at, "created_at": e.created_at,
        }

    def create_effect(self, record_id, payload):
        self.get_deceased(record_id)
        e = MortuaryEffect(
            deceased_record_id=record_id, item=payload.item, quantity=payload.quantity,
            description=payload.description, received_from=payload.received_from,
            received_at=_utcnow(), status=MortuaryEffectStatus.HELD,
        )
        self.db.add(e); self.db.commit(); self.db.refresh(e); return e

    def release_effect(self, effect_id, payload):
        e = self.db.query(MortuaryEffect).filter(MortuaryEffect.id == effect_id, MortuaryEffect.is_deleted.is_(False)).first()
        if not e:
            raise NotFoundError(message="Effect not found.", detail={"effect_id": effect_id})
        e.status = MortuaryEffectStatus.RELEASED
        e.released_to = payload.released_to
        e.released_at = _utcnow()
        self.db.commit(); self.db.refresh(e); return e

    def list_effects(self, record_id):
        return (
            self.db.query(MortuaryEffect)
            .filter(MortuaryEffect.deceased_record_id == record_id, MortuaryEffect.is_deleted.is_(False))
            .order_by(MortuaryEffect.date_created.desc()).all()
        )

    # ---- Viewings ----
    def viewing_dict(self, v: MortuaryViewing) -> dict:
        return {
            "id": v.id, "deceased_record_id": v.deceased_record_id, "visitor_name": v.visitor_name,
            "relationship_to_deceased": v.relationship_to_deceased, "contact": v.contact,
            "viewed_at": v.viewed_at, "authorized_by": v.authorized_by, "notes": v.notes,
            "created_at": v.created_at,
        }

    def create_viewing(self, record_id, payload):
        self.get_deceased(record_id)
        v = MortuaryViewing(
            deceased_record_id=record_id, visitor_name=payload.visitor_name,
            relationship_to_deceased=payload.relationship_to_deceased, contact=payload.contact,
            viewed_at=payload.viewed_at or _utcnow(), authorized_by=payload.authorized_by, notes=payload.notes,
        )
        self.db.add(v); self.db.commit(); self.db.refresh(v); return v

    def list_viewings(self, record_id):
        return (
            self.db.query(MortuaryViewing)
            .filter(MortuaryViewing.deceased_record_id == record_id, MortuaryViewing.is_deleted.is_(False))
            .order_by(MortuaryViewing.viewed_at.desc()).all()
        )

    # ---- Charges / billing ----
    def charge_dict(self, c: MortuaryCharge) -> dict:
        d = {
            "id": c.id, "deceased_record_id": c.deceased_record_id, "charge_type": str(c.charge_type),
            "status": str(c.status), "description": c.description, "quantity": c.quantity,
            "unit_amount": c.unit_amount, "amount": c.amount, "charged_at": c.charged_at,
            "notes": c.notes, "created_at": c.created_at,
        }
        if c.deceased_record:
            d.update(self._label(c.deceased_record))
        return d

    def create_charge(self, record_id, payload):
        self.get_deceased(record_id)
        from decimal import Decimal as _D
        qty = _D(str(payload.quantity or 1))
        unit = _D(str(payload.unit_amount or 0))
        c = MortuaryCharge(
            deceased_record_id=record_id,
            charge_type=MortuaryChargeType(payload.charge_type.strip().upper()),
            status=MortuaryChargeStatus.PENDING, description=payload.description,
            quantity=qty, unit_amount=unit, amount=qty * unit, charged_at=_utcnow(), notes=payload.notes,
        )
        self.db.add(c); self.db.commit(); self.db.refresh(c); return c

    def set_charge_status(self, charge_id, status):
        c = self.db.query(MortuaryCharge).filter(MortuaryCharge.id == charge_id, MortuaryCharge.is_deleted.is_(False)).first()
        if not c:
            raise NotFoundError(message="Charge not found.", detail={"charge_id": charge_id})
        c.status = MortuaryChargeStatus(status.strip().upper())
        self.db.commit(); self.db.refresh(c); return c

    def list_charges(self, *, record_id=None, status=None, skip=0, limit=200):
        q = self.db.query(MortuaryCharge).filter(MortuaryCharge.is_deleted.is_(False))
        if record_id:
            q = q.filter(MortuaryCharge.deceased_record_id == record_id)
        if status:
            q = q.filter(MortuaryCharge.status == MortuaryChargeStatus(status.strip().upper()))
        total = q.count()
        items = q.order_by(MortuaryCharge.charged_at.desc()).offset(skip).limit(limit).all()
        return items, total

    def charges_summary(self, record_id):
        from decimal import Decimal as _D
        items = self.list_charges(record_id=record_id, limit=1000)[0]
        total = sum((c.amount for c in items), _D("0"))
        outstanding = sum((c.amount for c in items if c.status == MortuaryChargeStatus.PENDING), _D("0"))
        return {"total": total, "outstanding": outstanding, "count": len(items)}

    # ---- Death certificate ----
    def certificate_dict(self, c: MortuaryDeathCertificate) -> dict:
        return {
            "id": c.id, "deceased_record_id": c.deceased_record_id, "certificate_number": c.certificate_number,
            "issued_by": c.issued_by, "certifying_doctor": c.certifying_doctor, "issued_at": c.issued_at,
            "cause_of_death": c.cause_of_death, "manner_of_death": c.manner_of_death,
            "place_of_death": c.place_of_death, "notes": c.notes, "created_at": c.created_at,
        }

    def _generate_cert_number(self):
        year = _utcnow().year
        n = (self.db.query(func.count(MortuaryDeathCertificate.id)).scalar() or 0) + 1
        while True:
            num = f"MDC-{year}-{n:04d}"
            if not self.db.query(MortuaryDeathCertificate.id).filter(MortuaryDeathCertificate.certificate_number == num).first():
                return num
            n += 1

    def get_certificate(self, record_id):
        return (
            self.db.query(MortuaryDeathCertificate)
            .filter(MortuaryDeathCertificate.deceased_record_id == record_id, MortuaryDeathCertificate.is_deleted.is_(False))
            .first()
        )

    def issue_certificate(self, record_id, payload):
        rec = self.get_deceased(record_id)
        if self.get_certificate(record_id):
            raise BadRequestError(message="A death certificate has already been issued for this record.", detail={"record_id": record_id})
        c = MortuaryDeathCertificate(
            deceased_record_id=record_id,
            certificate_number=payload.certificate_number or self._generate_cert_number(),
            issued_by=payload.issued_by, certifying_doctor=payload.certifying_doctor,
            cause_of_death=payload.cause_of_death or rec.cause_of_death,
            manner_of_death=payload.manner_of_death,
            place_of_death=payload.place_of_death, notes=payload.notes, issued_at=_utcnow(),
        )
        self.db.add(c); self.db.commit(); self.db.refresh(c); return c

    # ============================================================
    # ANALYTICS
    # ============================================================

    def analytics(self, *, months: int = 6) -> dict:
        """Decision-support analytics across the whole mortuary."""
        from decimal import Decimal as _D
        now = _utcnow()

        records = (
            self.db.query(DeceasedRecord).filter(DeceasedRecord.is_deleted.is_(False)).all()
        )
        units = self.db.query(MortuaryUnit).filter(MortuaryUnit.is_deleted.is_(False)).all()
        autopsies = self.db.query(MortuaryAutopsy).filter(MortuaryAutopsy.is_deleted.is_(False)).all()
        charges = self.db.query(MortuaryCharge).filter(MortuaryCharge.is_deleted.is_(False)).all()
        deaths = self.db.query(PatientDeathRecord).filter(PatientDeathRecord.is_deleted.is_(False)).all()

        active = (DeceasedStatus.REGISTERED, DeceasedStatus.IN_STORAGE)
        closed = (DeceasedStatus.RELEASED, DeceasedStatus.TRANSFERRED)

        # ---- summary ----
        in_storage = [r for r in records if r.status == DeceasedStatus.IN_STORAGE]
        capacity_total = sum(u.capacity for u in units)
        occupied_total = sum(self._unit_occupancy(u.id) for u in units)
        utilization = round((occupied_total / capacity_total) * 100, 1) if capacity_total else 0.0

        # ---- length of stay ----
        def days_between(a, b):
            try:
                return max((b - a).days, 0)
            except Exception:
                return 0

        released_los = [
            days_between(r.registered_at, r.released_at)
            for r in records
            if r.status in closed and r.registered_at and r.released_at
        ]
        current_los = [days_between(r.registered_at, now) for r in in_storage if r.registered_at]
        avg_released_los = round(sum(released_los) / len(released_los), 1) if released_los else 0.0
        avg_current_los = round(sum(current_los) / len(current_los), 1) if current_los else 0.0

        # LOS buckets (current in-storage bodies)
        buckets = {"0-1": 0, "2-3": 0, "4-7": 0, "8-14": 0, "15+": 0}
        for d in current_los:
            if d <= 1:
                buckets["0-1"] += 1
            elif d <= 3:
                buckets["2-3"] += 1
            elif d <= 7:
                buckets["4-7"] += 1
            elif d <= 14:
                buckets["8-14"] += 1
            else:
                buckets["15+"] += 1
        los_buckets = [{"bucket": k, "count": v} for k, v in buckets.items()]

        # long-stay bodies (> 14 days in storage) — actionable
        long_stay = sorted(
            (
                {
                    "id": r.id,
                    "tag_number": r.tag_number,
                    "deceased_name": r.deceased_name,
                    "unit": r.mortuary_unit.name if r.mortuary_unit else None,
                    "days": days_between(r.registered_at, now),
                }
                for r in in_storage
                if r.registered_at and days_between(r.registered_at, now) > 14
            ),
            key=lambda x: x["days"],
            reverse=True,
        )

        # ---- intake trend (last N months) ----
        import calendar as _cal
        month_keys = []
        y, m = now.year, now.month
        for _ in range(months):
            month_keys.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        month_keys.reverse()

        def mk(dt):
            return (dt.year, dt.month) if dt else None

        trend = []
        for (yy, mm) in month_keys:
            label = f"{_cal.month_abbr[mm]} {str(yy)[2:]}"
            trend.append({
                "month": label,
                "registrations": sum(1 for r in records if mk(r.registered_at) == (yy, mm)),
                "releases": sum(1 for r in records if r.released_at and mk(r.released_at) == (yy, mm)),
                "deaths": sum(1 for d in deaths if mk(d.date_of_death) == (yy, mm)),
            })

        # ---- unit utilization ----
        unit_util = []
        for u in units:
            occ = self._unit_occupancy(u.id)
            unit_util.append({
                "name": u.name,
                "code": u.code,
                "capacity": u.capacity,
                "occupied": occ,
                "pct": round((occ / u.capacity) * 100, 1) if u.capacity else 0.0,
                "status": str(u.status),
            })

        # ---- autopsy stats ----
        autopsy_stats = {
            "requested": sum(1 for a in autopsies if a.status == AutopsyStatus.REQUESTED),
            "scheduled": sum(1 for a in autopsies if a.status == AutopsyStatus.SCHEDULED),
            "completed": sum(1 for a in autopsies if a.status == AutopsyStatus.COMPLETED),
            "cancelled": sum(1 for a in autopsies if a.status == AutopsyStatus.CANCELLED),
            "clinical": sum(1 for a in autopsies if a.autopsy_type == AutopsyType.CLINICAL),
            "medico_legal": sum(1 for a in autopsies if a.autopsy_type == AutopsyType.MEDICO_LEGAL),
            "total": len(autopsies),
        }

        # ---- billing ----
        total_billed = sum((c.amount for c in charges), _D("0"))
        collected = sum((c.amount for c in charges if c.status == MortuaryChargeStatus.PAID), _D("0"))
        outstanding = sum((c.amount for c in charges if c.status == MortuaryChargeStatus.PENDING), _D("0"))
        waived = sum((c.amount for c in charges if c.status == MortuaryChargeStatus.WAIVED), _D("0"))
        by_type_map: dict[str, _D] = {}
        for c in charges:
            by_type_map[str(c.charge_type)] = by_type_map.get(str(c.charge_type), _D("0")) + c.amount
        billing_by_type = [{"type": k, "amount": str(v)} for k, v in sorted(by_type_map.items(), key=lambda x: x[1], reverse=True)]

        # ---- top causes of death ----
        cause_map: dict[str, int] = {}
        for r in records:
            if r.cause_of_death:
                key = r.cause_of_death.strip()[:80] or "Unspecified"
                cause_map[key] = cause_map.get(key, 0) + 1
        top_causes = [{"cause": k, "count": v} for k, v in sorted(cause_map.items(), key=lambda x: x[1], reverse=True)[:8]]

        return {
            "summary": {
                "total_records": len(records),
                "in_storage": len(in_storage),
                "registered_pending": sum(1 for r in records if r.status == DeceasedStatus.REGISTERED),
                "released": sum(1 for r in records if r.status == DeceasedStatus.RELEASED),
                "transferred": sum(1 for r in records if r.status == DeceasedStatus.TRANSFERRED),
                "in_hospital": sum(1 for r in records if r.source == DeceasedSource.IN_HOSPITAL),
                "brought_in": sum(1 for r in records if r.source == DeceasedSource.BROUGHT_IN),
                "police_cases": sum(1 for r in records if r.is_police_case),
                "capacity_total": capacity_total,
                "occupied_total": occupied_total,
                "utilization_pct": utilization,
                "avg_released_los_days": avg_released_los,
                "avg_current_los_days": avg_current_los,
                "pending_deposits": sum(1 for d in deaths if not d.is_deposited),
            },
            "source_split": [
                {"name": "In-hospital", "value": sum(1 for r in records if r.source == DeceasedSource.IN_HOSPITAL)},
                {"name": "Brought-in", "value": sum(1 for r in records if r.source == DeceasedSource.BROUGHT_IN)},
            ],
            "status_breakdown": [
                {"name": str(st).replace("_", " ").title(), "value": sum(1 for r in records if r.status == st)}
                for st in DeceasedStatus
            ],
            "intake_trend": trend,
            "unit_utilization": unit_util,
            "los_buckets": los_buckets,
            "long_stay": long_stay,
            "autopsy": autopsy_stats,
            "billing": {
                "total": str(total_billed),
                "collected": str(collected),
                "outstanding": str(outstanding),
                "waived": str(waived),
                "collection_rate": round((float(collected) / float(total_billed)) * 100, 1) if total_billed else 0.0,
                "by_type": billing_by_type,
            },
            "top_causes": top_causes,
        }

    # ============================================================
    # MORTUARY BILLING / FINANCE (payments, settlement, release)
    # ============================================================

    def _days_in_storage(self, r: DeceasedRecord) -> int:
        start = r.registered_at
        if not start:
            return 0
        end = r.released_at or _utcnow()
        try:
            return max((end - start).days, 0)
        except Exception:
            return 0

    def _bill_figures(self, record_id: int) -> dict:
        from decimal import Decimal as _D
        charges = (
            self.db.query(MortuaryCharge)
            .filter(MortuaryCharge.deceased_record_id == record_id, MortuaryCharge.is_deleted.is_(False))
            .all()
        )
        payments = (
            self.db.query(MortuaryPayment)
            .filter(MortuaryPayment.deceased_record_id == record_id, MortuaryPayment.is_deleted.is_(False))
            .all()
        )
        total_billed = sum((c.amount for c in charges if c.status != MortuaryChargeStatus.WAIVED), _D("0"))
        waived = sum((c.amount for c in charges if c.status == MortuaryChargeStatus.WAIVED), _D("0"))
        total_paid = sum((p.amount for p in payments), _D("0"))
        outstanding = total_billed - total_paid
        if outstanding < 0:
            outstanding = _D("0")
        return {
            "charges": charges,
            "payments": payments,
            "total_billed": total_billed,
            "waived": waived,
            "total_paid": total_paid,
            "outstanding": outstanding,
        }

    def bill_summary(self, record_id: int) -> dict:
        r = self.get_deceased(record_id)
        f = self._bill_figures(record_id)
        return {
            "deceased_record_id": record_id,
            "total_billed": str(f["total_billed"]),
            "total_paid": str(f["total_paid"]),
            "waived": str(f["waived"]),
            "outstanding": str(f["outstanding"]),
            "days_in_storage": self._days_in_storage(r),
            "charges": [self.charge_dict(c) for c in f["charges"]],
            "payments": [self.payment_dict(p) for p in f["payments"]],
        }

    def payment_dict(self, p: MortuaryPayment) -> dict:
        return {
            "id": p.id, "deceased_record_id": p.deceased_record_id, "amount": p.amount,
            "method": str(p.method), "reference": p.reference, "payer_name": p.payer_name,
            "received_by_staff_id": p.received_by_staff_id, "paid_at": p.paid_at,
            "notes": p.notes, "created_at": p.created_at,
        }

    def _settle_pending_if_covered(self, record_id: int) -> None:
        """When cumulative payments cover the billed total, mark PENDING charges PAID."""
        f = self._bill_figures(record_id)
        if f["total_paid"] >= f["total_billed"] and f["total_billed"] > 0:
            for c in f["charges"]:
                if c.status == MortuaryChargeStatus.PENDING:
                    c.status = MortuaryChargeStatus.PAID

    def _record_payment(self, record_id, *, amount, method="CASH", reference=None, payer_name=None, received_by_staff_id=None, notes=None) -> MortuaryPayment:
        p = MortuaryPayment(
            deceased_record_id=record_id,
            amount=amount,
            method=MortuaryPaymentMethod(str(method).strip().upper()),
            reference=reference, payer_name=payer_name,
            received_by_staff_id=received_by_staff_id, paid_at=_utcnow(), notes=notes,
        )
        self.db.add(p)
        self.db.flush()
        self._settle_pending_if_covered(record_id)
        return p

    def add_payment(self, record_id: int, payload: MortuaryPaymentCreateSchema) -> MortuaryPayment:
        self.get_deceased(record_id)
        p = self._record_payment(
            record_id,
            amount=payload.amount, method=payload.method, reference=payload.reference,
            payer_name=payload.payer_name, received_by_staff_id=payload.received_by_staff_id, notes=payload.notes,
        )
        self.db.commit()
        self.db.refresh(p)
        return p

    def list_payments(self, record_id: int):
        return (
            self.db.query(MortuaryPayment)
            .filter(MortuaryPayment.deceased_record_id == record_id, MortuaryPayment.is_deleted.is_(False))
            .order_by(MortuaryPayment.paid_at.desc()).all()
        )

    def _accrue_storage_fee(self, r: DeceasedRecord, daily_rate) -> MortuaryCharge:
        """Create a STORAGE charge for the days held, once per record."""
        from decimal import Decimal as _D
        existing = (
            self.db.query(MortuaryCharge)
            .filter(
                MortuaryCharge.deceased_record_id == r.id,
                MortuaryCharge.charge_type == MortuaryChargeType.STORAGE,
                MortuaryCharge.is_deleted.is_(False),
            )
            .first()
        )
        if existing:
            return existing
        days = max(self._days_in_storage(r), 1)
        qty = _D(str(days))
        unit = _D(str(daily_rate))
        c = MortuaryCharge(
            deceased_record_id=r.id,
            charge_type=MortuaryChargeType.STORAGE,
            status=MortuaryChargeStatus.PENDING,
            description=f"{days} day(s) cold storage",
            quantity=qty, unit_amount=unit, amount=qty * unit, charged_at=_utcnow(),
        )
        self.db.add(c)
        self.db.flush()
        return c

    def accrue_storage(self, record_id: int, daily_rate) -> MortuaryCharge:
        r = self.get_deceased(record_id)
        c = self._accrue_storage_fee(r, daily_rate)
        self.db.commit()
        self.db.refresh(c)
        return c

    def _waive_pending(self, record_id: int, reason: str) -> None:
        charges = (
            self.db.query(MortuaryCharge)
            .filter(
                MortuaryCharge.deceased_record_id == record_id,
                MortuaryCharge.status == MortuaryChargeStatus.PENDING,
                MortuaryCharge.is_deleted.is_(False),
            )
            .all()
        )
        for c in charges:
            c.status = MortuaryChargeStatus.WAIVED
            c.notes = (c.notes + " | " if c.notes else "") + f"Waived: {reason}"
