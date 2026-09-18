# app/repositories/care_plan_repository.py
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import CareTaskStatus
from app.core.exceptions import NotFoundError
from app.models.all_models import Patient, StaffProfile, User
from app.models.home_health_models import (
    CarePlan,
    CarePlanGoal,
    CarePlanIntervention,
    CarePlanProgressNote,
    CarePlanReview,
    CareTask,
)


class CarePlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -- shared lookups --
    def get_required_patient(self, patient_id: int) -> Patient:
        p = (
            self.db.query(Patient)
            .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
            .first()
        )
        if not p:
            raise NotFoundError(message="Patient not found.", detail={"patient_id": patient_id})
        return p

    def staff_display_name(self, staff_id: Optional[int]) -> Optional[str]:
        if not staff_id:
            return None
        row = (
            self.db.query(User.first_name, User.last_name)
            .join(StaffProfile, StaffProfile.user_id == User.id)
            .filter(StaffProfile.id == staff_id)
            .first()
        )
        if not row:
            return None
        return " ".join(x for x in [row[0], row[1]] if x).strip() or None

    # -- care plan --
    def get_by_id(self, plan_id: int) -> Optional[CarePlan]:
        return (
            self.db.query(CarePlan)
            .filter(CarePlan.id == plan_id, CarePlan.is_deleted.is_(False))
            .first()
        )

    def get_required(self, plan_id: int) -> CarePlan:
        p = self.get_by_id(plan_id)
        if not p:
            raise NotFoundError(message="Care plan not found.", detail={"care_plan_id": plan_id})
        return p

    def create(self, **kwargs) -> CarePlan:
        record = CarePlan(**kwargs)
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list(
        self,
        *,
        patient_id: Optional[int] = None,
        status: Optional[str] = None,
        lead_staff_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CarePlan], int]:
        query = self.db.query(CarePlan).filter(CarePlan.is_deleted.is_(False))
        if patient_id:
            query = query.filter(CarePlan.patient_id == patient_id)
        if status:
            query = query.filter(CarePlan.status == status)
        if lead_staff_id:
            query = query.filter(CarePlan.lead_staff_id == lead_staff_id)
        total = query.with_entities(func.count(CarePlan.id)).scalar() or 0
        items = (
            query.order_by(CarePlan.id.desc()).offset(skip).limit(limit).all()
        )
        return items, int(total)

    def goal_count(self, plan_id: int) -> int:
        return int(
            self.db.query(func.count(CarePlanGoal.id))
            .filter(CarePlanGoal.care_plan_id == plan_id, CarePlanGoal.is_deleted.is_(False))
            .scalar()
            or 0
        )

    def open_task_count(self, plan_id: int) -> int:
        return int(
            self.db.query(func.count(CareTask.id))
            .filter(
                CareTask.care_plan_id == plan_id,
                CareTask.is_deleted.is_(False),
                CareTask.status.in_([CareTaskStatus.PENDING, CareTaskStatus.IN_PROGRESS]),
            )
            .scalar()
            or 0
        )

    # -- goals --
    def get_goal(self, goal_id: int) -> CarePlanGoal:
        g = (
            self.db.query(CarePlanGoal)
            .filter(CarePlanGoal.id == goal_id, CarePlanGoal.is_deleted.is_(False))
            .first()
        )
        if not g:
            raise NotFoundError(message="Goal not found.", detail={"goal_id": goal_id})
        return g

    def create_goal(self, **kwargs) -> CarePlanGoal:
        g = CarePlanGoal(**kwargs)
        self.db.add(g)
        self.db.flush()
        self.db.refresh(g)
        return g

    def list_goals(self, plan_id: int) -> list[CarePlanGoal]:
        return (
            self.db.query(CarePlanGoal)
            .filter(CarePlanGoal.care_plan_id == plan_id, CarePlanGoal.is_deleted.is_(False))
            .order_by(CarePlanGoal.id.asc())
            .all()
        )

    # -- interventions --
    def get_intervention(self, intervention_id: int) -> CarePlanIntervention:
        i = (
            self.db.query(CarePlanIntervention)
            .filter(
                CarePlanIntervention.id == intervention_id,
                CarePlanIntervention.is_deleted.is_(False),
            )
            .first()
        )
        if not i:
            raise NotFoundError(message="Intervention not found.", detail={"intervention_id": intervention_id})
        return i

    def create_intervention(self, **kwargs) -> CarePlanIntervention:
        i = CarePlanIntervention(**kwargs)
        self.db.add(i)
        self.db.flush()
        self.db.refresh(i)
        return i

    def list_interventions(self, plan_id: int) -> list[CarePlanIntervention]:
        return (
            self.db.query(CarePlanIntervention)
            .filter(
                CarePlanIntervention.care_plan_id == plan_id,
                CarePlanIntervention.is_deleted.is_(False),
            )
            .order_by(CarePlanIntervention.id.asc())
            .all()
        )

    # -- tasks --
    def get_task(self, task_id: int) -> CareTask:
        t = (
            self.db.query(CareTask)
            .filter(CareTask.id == task_id, CareTask.is_deleted.is_(False))
            .first()
        )
        if not t:
            raise NotFoundError(message="Care task not found.", detail={"task_id": task_id})
        return t

    def create_task(self, **kwargs) -> CareTask:
        t = CareTask(**kwargs)
        self.db.add(t)
        self.db.flush()
        self.db.refresh(t)
        return t

    def list_tasks_for_plan(self, plan_id: int) -> list[CareTask]:
        return (
            self.db.query(CareTask)
            .filter(CareTask.care_plan_id == plan_id, CareTask.is_deleted.is_(False))
            .order_by(CareTask.due_at.asc().nullslast(), CareTask.id.asc())
            .all()
        )

    def list_tasks(
        self,
        *,
        patient_id: Optional[int] = None,
        assigned_staff_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CareTask], int]:
        query = self.db.query(CareTask).filter(CareTask.is_deleted.is_(False))
        if patient_id:
            query = query.filter(CareTask.patient_id == patient_id)
        if assigned_staff_id:
            query = query.filter(CareTask.assigned_staff_id == assigned_staff_id)
        if status:
            query = query.filter(CareTask.status == status)
        total = query.with_entities(func.count(CareTask.id)).scalar() or 0
        items = (
            query.order_by(CareTask.due_at.asc().nullslast(), CareTask.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, int(total)

    # -- progress notes --
    def create_progress_note(self, **kwargs) -> CarePlanProgressNote:
        n = CarePlanProgressNote(**kwargs)
        self.db.add(n)
        self.db.flush()
        self.db.refresh(n)
        return n

    def list_progress_notes(self, plan_id: int) -> list[CarePlanProgressNote]:
        return (
            self.db.query(CarePlanProgressNote)
            .filter(
                CarePlanProgressNote.care_plan_id == plan_id,
                CarePlanProgressNote.is_deleted.is_(False),
            )
            .order_by(CarePlanProgressNote.recorded_at.desc(), CarePlanProgressNote.id.desc())
            .all()
        )

    # -- reviews --
    def create_review(self, **kwargs) -> CarePlanReview:
        r = CarePlanReview(**kwargs)
        self.db.add(r)
        self.db.flush()
        self.db.refresh(r)
        return r

    def list_reviews(self, plan_id: int) -> list[CarePlanReview]:
        return (
            self.db.query(CarePlanReview)
            .filter(CarePlanReview.care_plan_id == plan_id, CarePlanReview.is_deleted.is_(False))
            .order_by(CarePlanReview.review_date.desc(), CarePlanReview.id.desc())
            .all()
        )
