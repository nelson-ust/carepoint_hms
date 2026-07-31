# app/repositories/admission_repository.py
from __future__ import annotations

"""
Repository for the inpatient admission lifecycle.

Responsibilities
----------------
- generate unique admission numbers
- create admission rows with ward + bed assignment
- find available beds in a ward
- list active admissions per ward / per facility
- update admission status (transfer / cancel / death)
- locate the admission tied to a visit (used by discharge + bed-day capture)

The admission repository does NOT mutate billing or stock — those side
effects belong to the service layer where charge capture is also coordinated.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.enums import AdmissionStatus, BedStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import Admission, Bed, Consultation, Visit, Ward
from app.utils.helpers import generate_uuid_str


class AdmissionRepository:
    """Persistence layer for ``Admission`` and related ward/bed lookups."""

    def __init__(self, db: Session) -> None:
        # Caller-managed session — repositories never commit; that's the
        # service layer's job so transactions stay coherent across modules.
        self.db = db

    # ============================================================
    # LOOKUPS
    # ============================================================

    def get_by_id(self, admission_id: int) -> Optional[Admission]:
        """Return the admission with the bed/ward eagerly loaded, or None."""
        return (
            self.db.query(Admission)
            .options(
                joinedload(Admission.bed),
                joinedload(Admission.ward),
                joinedload(Admission.visit),
            )
            .filter(
                Admission.id == admission_id,
                Admission.is_deleted.is_(False),
            )
            .first()
        )


    def get_required_by_id(self, admission_id: int) -> Admission:
        """Return the admission or raise NotFoundError. Service-layer ergonomic."""
        a = self.get_by_id(admission_id)
        if not a:
            raise NotFoundError(
                message="Admission not found.",
                detail={"admission_id": admission_id},
            )
        return a

    def get_active_for_visit(self, visit_id: int) -> Optional[Admission]:
        """
        Return the open admission tied to a visit.

        Used by the unified registration / inpatient flow and by discharge.
        """
        return (
            self.db.query(Admission)
            .filter(
                Admission.visit_id == visit_id,
                Admission.is_deleted.is_(False),
                Admission.admission_status.in_(
                    [AdmissionStatus.PENDING, AdmissionStatus.ADMITTED, AdmissionStatus.TRANSFERRED]
                ),
            )
            .order_by(Admission.id.desc())
            .first()
        )

    def get_active_for_patient(self, patient_id: int) -> Optional[Admission]:
        """Return the patient's current open admission, if any.

        A patient may hold only one active admission at a time; this backs the
        duplicate-admission guard in the service layer.
        """
        return (
            self.db.query(Admission)
            .filter(
                Admission.patient_id == patient_id,
                Admission.is_deleted.is_(False),
                Admission.admission_status.in_(
                    [AdmissionStatus.PENDING, AdmissionStatus.ADMITTED, AdmissionStatus.TRANSFERRED]
                ),
            )
            .order_by(Admission.id.desc())
            .first()
        )

    def get_visit(self, visit_id: int) -> Optional[Visit]:
        return (
            self.db.query(Visit)
            .filter(Visit.id == visit_id, Visit.is_deleted.is_(False))
            .first()
        )

    def has_admission_recommendation(self, visit_id: int) -> bool:
        """
        True when a clinician has recommended admission on this visit (i.e. the
        patient has been seen by a doctor who documented an admit recommendation
        on a consultation). Cancelled consultations do not count.
        """
        from app.core.enums import EncounterStatus

        q = (
            self.db.query(Consultation.id)
            .filter(
                Consultation.visit_id == visit_id,
                Consultation.recommends_admission.is_(True),
                Consultation.is_deleted.is_(False),
                Consultation.status != EncounterStatus.CANCELLED,
            )
        )
        return self.db.query(q.exists()).scalar() or False

    # ============================================================
    # WARD / BED RESOLUTION
    # ============================================================

    def get_ward(self, ward_id: int) -> Optional[Ward]:
        return (
            self.db.query(Ward)
            .filter(Ward.id == ward_id, Ward.is_deleted.is_(False))
            .first()
        )

    def get_bed(self, bed_id: int) -> Optional[Bed]:
        return (
            self.db.query(Bed)
            .filter(Bed.id == bed_id, Bed.is_deleted.is_(False))
            .first()
        )

    def first_available_bed(self, ward_id: int) -> Optional[Bed]:
        """
        Pick the lowest-numbered AVAILABLE bed in the ward.

        The service layer should hold a row-level lock here in production
        (``with_for_update``) to avoid two admissions racing for the same bed.
        That's omitted here because SQLite doesn't support it — production
        deployments use Postgres which honours it transparently.
        """
        return (
            self.db.query(Bed)
            .filter(
                Bed.ward_id == ward_id,
                Bed.is_deleted.is_(False),
                Bed.bed_status == BedStatus.AVAILABLE,
            )
            .order_by(Bed.bed_no.asc(), Bed.id.asc())
            .first()
        )

    def update_bed_status(self, bed: Bed, status: BedStatus) -> Bed:
        """Update bed.bed_status and flush. Caller commits."""
        bed.bed_status = status
        self.db.add(bed)
        self.db.flush()
        self.db.refresh(bed)
        return bed

    # ============================================================
    # LISTINGS
    # ============================================================

    def list_active_for_ward(self, ward_id: int) -> list[Admission]:
        """Active admissions currently sitting in beds of a given ward."""
        return (
            self.db.query(Admission)
            .options(joinedload(Admission.bed))
            .filter(
                Admission.ward_id == ward_id,
                Admission.is_deleted.is_(False),
                Admission.admission_status.in_(
                    [AdmissionStatus.PENDING, AdmissionStatus.ADMITTED, AdmissionStatus.TRANSFERRED]
                ),
            )
            .order_by(Admission.admitted_at.asc().nullsfirst(), Admission.id.asc())
            .all()
        )

    def list_admissions(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        patient_id: Optional[int] = None,
        ward_id: Optional[int] = None,
        status: Optional[AdmissionStatus] = None,
        facility_id: Optional[int] = None,
    ) -> tuple[list[Admission], int]:
        """Paginated list of admissions with the most common filters."""
        query = self.db.query(Admission).filter(Admission.is_deleted.is_(False))
        if patient_id is not None:
            query = query.filter(Admission.patient_id == patient_id)
        if ward_id is not None:
            query = query.filter(Admission.ward_id == ward_id)
        if status is not None:
            query = query.filter(Admission.admission_status == status)
        if facility_id is not None:
            # Admissions don't carry facility_id directly; resolve through the ward.
            query = (
                query.join(Ward, Ward.id == Admission.ward_id)
                .filter(Ward.facility_id == facility_id)
            )

        total = query.with_entities(func.count(Admission.id)).scalar() or 0
        items = (
            query.order_by(Admission.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    # ============================================================
    # CREATE / SAVE
    # ============================================================

    def generate_admission_no(self) -> str:
        """
        Build a deterministic admission number: ``ADM-YYYYMMDD-XXXXXXXX``.

        Format keeps the date inline so paper-trail backfill from downtime
        events (see DowntimeRegistrationLog) can correlate quickly.
        """
        return f"ADM-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{generate_uuid_str()[:8].upper()}"

    def create_admission(
        self,
        *,
        patient_id: int,
        visit_id: Optional[int],
        ward_id: int,
        bed_id: Optional[int],
        admitting_staff_id: Optional[int],
        admission_reason: Optional[str],
        admitted_at: datetime,
        expected_discharge_at: Optional[datetime],
        status: AdmissionStatus = AdmissionStatus.ADMITTED,
    ) -> Admission:
        """Persist a new admission row and return it. Caller manages commit."""
        admission = Admission(
            patient_id=patient_id,
            visit_id=visit_id,
            ward_id=ward_id,
            bed_id=bed_id,
            admitted_by_staff_id=admitting_staff_id,
            admission_no=self.generate_admission_no(),
            admission_status=status,
            admission_reason=admission_reason,
            admitted_at=admitted_at,
            expected_discharge_at=expected_discharge_at,
        )
        self.db.add(admission)
        self.db.flush()
        self.db.refresh(admission)
        return admission

    def save(self, admission: Admission) -> Admission:
        """Generic upsert helper used by status-update flows."""
        self.db.add(admission)
        self.db.flush()
        self.db.refresh(admission)
        return admission
