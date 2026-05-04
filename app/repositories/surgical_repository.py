# app/repositories/surgical_repository.py
from __future__ import annotations

"""
Repository layer for the Surgical / Theatre module.

Each repository is a thin SQLAlchemy wrapper around one or two related
domain models. The service layer composes them.

Repositories:
- ``OperatingTheatreRepository``        — physical theatres
- ``SurgicalCatalogRepository``         — surgical procedure catalog
- ``SurgicalCaseRepository``            — surgical case header + lifecycle
- ``SurgicalTeamRepository``            — team members per case
- ``SurgicalConsentRepository``         — patient consents per case
- ``SurgicalChecklistRepository``       — WHO safety checklist phases
- ``AnaesthesiaRepository``             — anaesthesia records
- ``TheatreNoteRepository``             — intra-op notes
- ``InstrumentSetRepository``           — instrument sets + sterilization status
- ``InstrumentSterilizationRepository`` — per-cycle sterilization audit log
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.enums import (
    SterilizationStatus,
    SurgicalCaseStatus,
    TheatreStatus,
)
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.models.all_models import (
    AnaesthesiaRecord,
    InstrumentSterilizationLog,
    OperatingTheatre,
    SurgicalCase,
    SurgicalConsent,
    SurgicalInstrumentSet,
    SurgicalProcedureCatalog,
    SurgicalSafetyChecklist,
    SurgicalTeamMember,
    TheatreNote,
    Visit,
)
from app.utils.helpers import generate_uuid_str


# ============================================================
# OPERATING THEATRE
# ============================================================


class OperatingTheatreRepository:
    """CRUD over physical operating theatres."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, theatre_id: int) -> Optional[OperatingTheatre]:
        return (
            self.db.query(OperatingTheatre)
            .filter(
                OperatingTheatre.id == theatre_id,
                OperatingTheatre.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, theatre_id: int) -> OperatingTheatre:
        t = self.get_by_id(theatre_id)
        if not t:
            raise NotFoundError(
                message="Operating theatre not found.",
                detail={"theatre_id": theatre_id},
            )
        return t

    def get_by_code(self, code: str) -> Optional[OperatingTheatre]:
        return (
            self.db.query(OperatingTheatre)
            .filter(
                func.upper(OperatingTheatre.code) == code.strip().upper(),
                OperatingTheatre.is_deleted.is_(False),
            )
            .first()
        )

    def list_theatres(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        status: Optional[TheatreStatus] = None,
        facility_id: Optional[int] = None,
        emergency_only: bool = False,
        search: Optional[str] = None,
    ) -> tuple[list[OperatingTheatre], int]:
        query = self.db.query(OperatingTheatre).filter(
            OperatingTheatre.is_deleted.is_(False)
        )
        if status is not None:
            query = query.filter(OperatingTheatre.status == status)
        if facility_id is not None:
            query = query.filter(OperatingTheatre.facility_id == facility_id)
        if emergency_only:
            query = query.filter(OperatingTheatre.is_emergency_capable.is_(True))
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(OperatingTheatre.name).like(term),
                    func.lower(OperatingTheatre.code).like(term),
                )
            )
        total = query.with_entities(func.count(OperatingTheatre.id)).scalar() or 0
        items = (
            query.order_by(OperatingTheatre.code.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def create(self, **kwargs) -> OperatingTheatre:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="A theatre with this code already exists.",
                detail={"code": kwargs["code"]},
            )
        kwargs.setdefault("status", TheatreStatus.AVAILABLE)
        t = OperatingTheatre(**kwargs)
        self.db.add(t)
        self.db.flush()
        self.db.refresh(t)
        return t

    def update(self, t: OperatingTheatre, **kwargs) -> OperatingTheatre:
        for field, value in kwargs.items():
            if value is not None:
                setattr(t, field, value)
        self.db.add(t)
        self.db.flush()
        self.db.refresh(t)
        return t

    def save(self, t: OperatingTheatre) -> OperatingTheatre:
        self.db.add(t)
        self.db.flush()
        self.db.refresh(t)
        return t

    def soft_delete(self, t: OperatingTheatre) -> OperatingTheatre:
        t.is_deleted = True
        self.db.add(t)
        self.db.flush()
        return t


# ============================================================
# SURGICAL PROCEDURE CATALOG
# ============================================================


class SurgicalCatalogRepository:
    """CRUD over the surgical procedure master catalog."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, procedure_id: int) -> Optional[SurgicalProcedureCatalog]:
        return (
            self.db.query(SurgicalProcedureCatalog)
            .filter(
                SurgicalProcedureCatalog.id == procedure_id,
                SurgicalProcedureCatalog.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, procedure_id: int) -> SurgicalProcedureCatalog:
        p = self.get_by_id(procedure_id)
        if not p:
            raise NotFoundError(
                message="Surgical procedure not found.",
                detail={"procedure_id": procedure_id},
            )
        return p

    def get_by_code(self, code: str) -> Optional[SurgicalProcedureCatalog]:
        return (
            self.db.query(SurgicalProcedureCatalog)
            .filter(
                func.upper(SurgicalProcedureCatalog.code) == code.strip().upper(),
                SurgicalProcedureCatalog.is_deleted.is_(False),
            )
            .first()
        )

    def list_procedures(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> tuple[list[SurgicalProcedureCatalog], int]:
        query = self.db.query(SurgicalProcedureCatalog).filter(
            SurgicalProcedureCatalog.is_deleted.is_(False)
        )
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(SurgicalProcedureCatalog.name).like(term),
                    func.lower(SurgicalProcedureCatalog.code).like(term),
                    func.lower(SurgicalProcedureCatalog.cpt_code).like(term),
                )
            )
        total = (
            query.with_entities(func.count(SurgicalProcedureCatalog.id)).scalar() or 0
        )
        items = (
            query.order_by(SurgicalProcedureCatalog.name.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def create(self, **kwargs) -> SurgicalProcedureCatalog:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="A surgical procedure with this code already exists.",
                detail={"code": kwargs["code"]},
            )
        p = SurgicalProcedureCatalog(**kwargs)
        self.db.add(p)
        self.db.flush()
        self.db.refresh(p)
        return p

    def soft_delete(self, p: SurgicalProcedureCatalog) -> SurgicalProcedureCatalog:
        p.is_deleted = True
        self.db.add(p)
        self.db.flush()
        return p


# ============================================================
# SURGICAL CASE
# ============================================================


class SurgicalCaseRepository:
    """Surgical case header + lifecycle queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def get_by_id(self, case_id: int) -> Optional[SurgicalCase]:
        return (
            self.db.query(SurgicalCase)
            .options(
                selectinload(SurgicalCase.team_members),
                selectinload(SurgicalCase.consents),
                selectinload(SurgicalCase.checklists),
                selectinload(SurgicalCase.anaesthesia_records),
                selectinload(SurgicalCase.theatre_notes),
            )
            .filter(SurgicalCase.id == case_id, SurgicalCase.is_deleted.is_(False))
            .first()
        )

    def get_required_by_id(self, case_id: int) -> SurgicalCase:
        c = self.get_by_id(case_id)
        if not c:
            raise NotFoundError(
                message="Surgical case not found.",
                detail={"case_id": case_id},
            )
        return c

    def get_by_case_no(self, case_no: str) -> Optional[SurgicalCase]:
        return (
            self.db.query(SurgicalCase)
            .filter(
                SurgicalCase.case_no == case_no.strip(),
                SurgicalCase.is_deleted.is_(False),
            )
            .first()
        )

    def list_for_visit(
        self,
        visit_id: int,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[SurgicalCase], int]:
        query = self.db.query(SurgicalCase).filter(
            SurgicalCase.visit_id == visit_id,
            SurgicalCase.is_deleted.is_(False),
        )
        total = query.with_entities(func.count(SurgicalCase.id)).scalar() or 0
        items = query.order_by(SurgicalCase.id.desc()).offset(skip).limit(limit).all()
        return items, int(total)

    def list_worklist(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        statuses: Optional[list[SurgicalCaseStatus]] = None,
        operating_theatre_id: Optional[int] = None,
        emergency_only: bool = False,
    ) -> tuple[list[SurgicalCase], int]:
        """Theatre worklist — defaults to all non-terminal cases."""
        query = self.db.query(SurgicalCase).filter(
            SurgicalCase.is_deleted.is_(False)
        )
        if statuses:
            query = query.filter(SurgicalCase.status.in_(statuses))
        else:
            query = query.filter(
                SurgicalCase.status.notin_(
                    [SurgicalCaseStatus.COMPLETED, SurgicalCaseStatus.CANCELLED]
                )
            )
        if operating_theatre_id is not None:
            query = query.filter(SurgicalCase.operating_theatre_id == operating_theatre_id)
        if emergency_only:
            query = query.filter(SurgicalCase.is_emergency.is_(True))
        total = query.with_entities(func.count(SurgicalCase.id)).scalar() or 0
        items = (
            query.order_by(SurgicalCase.scheduled_start_at.asc().nulls_first())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def open_case_in_theatre(self, theatre_id: int) -> Optional[SurgicalCase]:
        """Find any active case currently occupying this theatre, if any."""
        return (
            self.db.query(SurgicalCase)
            .filter(
                SurgicalCase.operating_theatre_id == theatre_id,
                SurgicalCase.is_deleted.is_(False),
                SurgicalCase.status.in_(
                    [
                        SurgicalCaseStatus.PRE_OP,
                        SurgicalCaseStatus.IN_THEATRE,
                        SurgicalCaseStatus.PROCEDURE_STARTED,
                        SurgicalCaseStatus.PROCEDURE_ENDED,
                        SurgicalCaseStatus.POST_OP,
                    ]
                ),
            )
            .first()
        )

    def generate_case_no(self) -> str:
        return f"SUR-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create(self, **kwargs) -> SurgicalCase:
        kwargs.setdefault("case_no", self.generate_case_no())
        kwargs.setdefault("status", SurgicalCaseStatus.BOOKED)
        c = SurgicalCase(**kwargs)
        self.db.add(c)
        self.db.flush()
        self.db.refresh(c)
        return c

    def save(self, c: SurgicalCase) -> SurgicalCase:
        self.db.add(c)
        self.db.flush()
        self.db.refresh(c)
        return c


# ============================================================
# TEAM MEMBERS
# ============================================================


class SurgicalTeamRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, member_id: int) -> Optional[SurgicalTeamMember]:
        return (
            self.db.query(SurgicalTeamMember)
            .filter(
                SurgicalTeamMember.id == member_id,
                SurgicalTeamMember.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, member_id: int) -> SurgicalTeamMember:
        m = self.get_by_id(member_id)
        if not m:
            raise NotFoundError(
                message="Team member not found.",
                detail={"member_id": member_id},
            )
        return m

    def list_for_case(self, case_id: int) -> list[SurgicalTeamMember]:
        return (
            self.db.query(SurgicalTeamMember)
            .filter(
                SurgicalTeamMember.surgical_case_id == case_id,
                SurgicalTeamMember.is_deleted.is_(False),
            )
            .order_by(SurgicalTeamMember.id.asc())
            .all()
        )

    def find_existing(
        self, case_id: int, staff_profile_id: int, role: str
    ) -> Optional[SurgicalTeamMember]:
        return (
            self.db.query(SurgicalTeamMember)
            .filter(
                SurgicalTeamMember.surgical_case_id == case_id,
                SurgicalTeamMember.staff_profile_id == staff_profile_id,
                SurgicalTeamMember.role == role,
                SurgicalTeamMember.is_deleted.is_(False),
            )
            .first()
        )

    def create(self, **kwargs) -> SurgicalTeamMember:
        m = SurgicalTeamMember(**kwargs)
        self.db.add(m)
        self.db.flush()
        self.db.refresh(m)
        return m

    def soft_delete(self, m: SurgicalTeamMember) -> SurgicalTeamMember:
        m.is_deleted = True
        self.db.add(m)
        self.db.flush()
        return m


# ============================================================
# CONSENT
# ============================================================


class SurgicalConsentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_by_id(self, consent_id: int) -> SurgicalConsent:
        c = (
            self.db.query(SurgicalConsent)
            .filter(
                SurgicalConsent.id == consent_id,
                SurgicalConsent.is_deleted.is_(False),
            )
            .first()
        )
        if not c:
            raise NotFoundError(
                message="Consent record not found.",
                detail={"consent_id": consent_id},
            )
        return c

    def list_for_case(self, case_id: int) -> list[SurgicalConsent]:
        return (
            self.db.query(SurgicalConsent)
            .filter(
                SurgicalConsent.surgical_case_id == case_id,
                SurgicalConsent.is_deleted.is_(False),
            )
            .order_by(SurgicalConsent.id.asc())
            .all()
        )

    def has_consent(self, case_id: int) -> bool:
        return (
            self.db.query(SurgicalConsent.id)
            .filter(
                SurgicalConsent.surgical_case_id == case_id,
                SurgicalConsent.is_deleted.is_(False),
            )
            .first()
            is not None
        )

    def create(self, **kwargs) -> SurgicalConsent:
        kwargs.setdefault("signed_at", datetime.now(timezone.utc))
        c = SurgicalConsent(**kwargs)
        self.db.add(c)
        self.db.flush()
        self.db.refresh(c)
        return c


# ============================================================
# CHECKLIST
# ============================================================


class SurgicalChecklistRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_by_id(self, checklist_id: int) -> SurgicalSafetyChecklist:
        cl = (
            self.db.query(SurgicalSafetyChecklist)
            .filter(
                SurgicalSafetyChecklist.id == checklist_id,
                SurgicalSafetyChecklist.is_deleted.is_(False),
            )
            .first()
        )
        if not cl:
            raise NotFoundError(
                message="Checklist record not found.",
                detail={"checklist_id": checklist_id},
            )
        return cl

    def list_for_case(self, case_id: int) -> list[SurgicalSafetyChecklist]:
        return (
            self.db.query(SurgicalSafetyChecklist)
            .filter(
                SurgicalSafetyChecklist.surgical_case_id == case_id,
                SurgicalSafetyChecklist.is_deleted.is_(False),
            )
            .order_by(SurgicalSafetyChecklist.completed_at.asc())
            .all()
        )

    def get_phase(
        self, case_id: int, phase: str
    ) -> Optional[SurgicalSafetyChecklist]:
        return (
            self.db.query(SurgicalSafetyChecklist)
            .filter(
                SurgicalSafetyChecklist.surgical_case_id == case_id,
                SurgicalSafetyChecklist.phase == phase,
                SurgicalSafetyChecklist.is_deleted.is_(False),
            )
            .first()
        )

    def has_phase(self, case_id: int, phase: str) -> bool:
        return self.get_phase(case_id, phase) is not None

    def create(self, **kwargs) -> SurgicalSafetyChecklist:
        kwargs.setdefault("completed_at", datetime.now(timezone.utc))
        cl = SurgicalSafetyChecklist(**kwargs)
        self.db.add(cl)
        self.db.flush()
        self.db.refresh(cl)
        return cl


# ============================================================
# ANAESTHESIA
# ============================================================


class AnaesthesiaRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_by_id(self, record_id: int) -> AnaesthesiaRecord:
        r = (
            self.db.query(AnaesthesiaRecord)
            .filter(
                AnaesthesiaRecord.id == record_id,
                AnaesthesiaRecord.is_deleted.is_(False),
            )
            .first()
        )
        if not r:
            raise NotFoundError(
                message="Anaesthesia record not found.",
                detail={"record_id": record_id},
            )
        return r

    def list_for_case(self, case_id: int) -> list[AnaesthesiaRecord]:
        return (
            self.db.query(AnaesthesiaRecord)
            .filter(
                AnaesthesiaRecord.surgical_case_id == case_id,
                AnaesthesiaRecord.is_deleted.is_(False),
            )
            .order_by(AnaesthesiaRecord.id.asc())
            .all()
        )

    def create(self, **kwargs) -> AnaesthesiaRecord:
        r = AnaesthesiaRecord(**kwargs)
        self.db.add(r)
        self.db.flush()
        self.db.refresh(r)
        return r


# ============================================================
# THEATRE NOTE
# ============================================================


class TheatreNoteRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_by_id(self, note_id: int) -> TheatreNote:
        n = (
            self.db.query(TheatreNote)
            .filter(TheatreNote.id == note_id, TheatreNote.is_deleted.is_(False))
            .first()
        )
        if not n:
            raise NotFoundError(
                message="Theatre note not found.",
                detail={"note_id": note_id},
            )
        return n

    def list_for_case(self, case_id: int) -> list[TheatreNote]:
        return (
            self.db.query(TheatreNote)
            .filter(
                TheatreNote.surgical_case_id == case_id,
                TheatreNote.is_deleted.is_(False),
            )
            .order_by(TheatreNote.captured_at.asc())
            .all()
        )

    def create(self, **kwargs) -> TheatreNote:
        kwargs.setdefault("captured_at", datetime.now(timezone.utc))
        n = TheatreNote(**kwargs)
        self.db.add(n)
        self.db.flush()
        self.db.refresh(n)
        return n


# ============================================================
# INSTRUMENT SET
# ============================================================


class InstrumentSetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, set_id: int) -> Optional[SurgicalInstrumentSet]:
        return (
            self.db.query(SurgicalInstrumentSet)
            .filter(
                SurgicalInstrumentSet.id == set_id,
                SurgicalInstrumentSet.is_deleted.is_(False),
            )
            .first()
        )

    def get_required_by_id(self, set_id: int) -> SurgicalInstrumentSet:
        s = self.get_by_id(set_id)
        if not s:
            raise NotFoundError(
                message="Instrument set not found.",
                detail={"set_id": set_id},
            )
        return s

    def get_by_code(self, code: str) -> Optional[SurgicalInstrumentSet]:
        return (
            self.db.query(SurgicalInstrumentSet)
            .filter(
                func.upper(SurgicalInstrumentSet.code) == code.strip().upper(),
                SurgicalInstrumentSet.is_deleted.is_(False),
            )
            .first()
        )

    def list_sets(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        sterilization_status: Optional[SterilizationStatus] = None,
        facility_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> tuple[list[SurgicalInstrumentSet], int]:
        query = self.db.query(SurgicalInstrumentSet).filter(
            SurgicalInstrumentSet.is_deleted.is_(False)
        )
        if sterilization_status is not None:
            query = query.filter(
                SurgicalInstrumentSet.sterilization_status == sterilization_status
            )
        if facility_id is not None:
            query = query.filter(SurgicalInstrumentSet.facility_id == facility_id)
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    func.lower(SurgicalInstrumentSet.name).like(term),
                    func.lower(SurgicalInstrumentSet.code).like(term),
                )
            )
        total = (
            query.with_entities(func.count(SurgicalInstrumentSet.id)).scalar() or 0
        )
        items = (
            query.order_by(SurgicalInstrumentSet.code.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def create(self, **kwargs) -> SurgicalInstrumentSet:
        if self.get_by_code(kwargs["code"]):
            raise AlreadyExistsError(
                message="An instrument set with this code already exists.",
                detail={"code": kwargs["code"]},
            )
        kwargs.setdefault("sterilization_status", SterilizationStatus.READY)
        s = SurgicalInstrumentSet(**kwargs)
        self.db.add(s)
        self.db.flush()
        self.db.refresh(s)
        return s

    def save(self, s: SurgicalInstrumentSet) -> SurgicalInstrumentSet:
        self.db.add(s)
        self.db.flush()
        self.db.refresh(s)
        return s


# ============================================================
# STERILIZATION LOG
# ============================================================


class InstrumentSterilizationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_required_by_id(self, log_id: int) -> InstrumentSterilizationLog:
        log = (
            self.db.query(InstrumentSterilizationLog)
            .filter(
                InstrumentSterilizationLog.id == log_id,
                InstrumentSterilizationLog.is_deleted.is_(False),
            )
            .first()
        )
        if not log:
            raise NotFoundError(
                message="Sterilization log not found.",
                detail={"log_id": log_id},
            )
        return log

    def list_for_set(
        self, instrument_set_id: int, *, skip: int = 0, limit: int = 50
    ) -> tuple[list[InstrumentSterilizationLog], int]:
        query = self.db.query(InstrumentSterilizationLog).filter(
            InstrumentSterilizationLog.instrument_set_id == instrument_set_id,
            InstrumentSterilizationLog.is_deleted.is_(False),
        )
        total = (
            query.with_entities(func.count(InstrumentSterilizationLog.id)).scalar()
            or 0
        )
        items = (
            query.order_by(InstrumentSterilizationLog.cycle_started_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    def create(self, **kwargs) -> InstrumentSterilizationLog:
        log = InstrumentSterilizationLog(**kwargs)
        self.db.add(log)
        self.db.flush()
        self.db.refresh(log)
        return log
