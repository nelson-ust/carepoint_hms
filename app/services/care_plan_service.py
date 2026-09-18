# app/services/care_plan_service.py
from __future__ import annotations

"""Care Plan engine service (goals, interventions, tasks, progress, reviews)."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import (
    AlertSeverity,
    AlertType,
    CarePlanReviewOutcome,
    CareTaskStatus,
)
from app.core.exceptions import BadRequestError
from app.core.logger import get_logger
from app.models.home_health_models import CarePlan, CareTask
from app.repositories.care_plan_repository import CarePlanRepository
from app.services.clinical_alert_service import ClinicalAlertService

logger = get_logger(__name__)


class CarePlanService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = CarePlanRepository(db)
        self.alerts = ClinicalAlertService(db)

    # -- decoration --
    def _decorate(self, plan: CarePlan) -> CarePlan:
        try:
            p = self.repository.get_required_patient(plan.patient_id)
            plan.patient_name = " ".join(x for x in [p.first_name, p.last_name] if x).strip() or None
        except Exception:
            plan.patient_name = None
        try:
            plan.lead_staff_name = self.repository.staff_display_name(plan.lead_staff_id)
            plan.goal_count = self.repository.goal_count(plan.id)
            plan.open_task_count = self.repository.open_task_count(plan.id)
        except Exception:
            pass
        return plan

    # -- plan --
    def create(self, payload, *, actor_user_id: Optional[int] = None) -> CarePlan:
        self.repository.get_required_patient(payload.patient_id)
        data = payload.model_dump(exclude_unset=True)
        data["created_by_id"] = actor_user_id
        plan = self.repository.create(**data)
        self.db.commit()
        self.db.refresh(plan)
        return self._decorate(plan)

    def get(self, plan_id: int) -> CarePlan:
        return self._decorate(self.repository.get_required(plan_id))

    def get_detail(self, plan_id: int) -> dict:
        plan = self._decorate(self.repository.get_required(plan_id))
        return {
            "plan": plan,
            "goals": self.repository.list_goals(plan_id),
            "interventions": self.repository.list_interventions(plan_id),
            "tasks": self.repository.list_tasks_for_plan(plan_id),
            "progress_notes": self.repository.list_progress_notes(plan_id),
            "reviews": self.repository.list_reviews(plan_id),
        }

    def list(self, **kwargs):
        items, total = self.repository.list(**kwargs)
        for p in items:
            self._decorate(p)
        return items, total

    def update(self, plan_id: int, payload) -> CarePlan:
        plan = self.repository.get_required(plan_id)
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(plan, k, v)
        self.db.commit()
        self.db.refresh(plan)
        return self._decorate(plan)

    # -- goals --
    def add_goal(self, plan_id: int, payload):
        self.repository.get_required(plan_id)
        g = self.repository.create_goal(care_plan_id=plan_id, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        self.db.refresh(g)
        return g

    def update_goal(self, goal_id: int, payload):
        g = self.repository.get_goal(goal_id)
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(g, k, v)
        self.db.commit()
        self.db.refresh(g)
        return g

    # -- interventions --
    def add_intervention(self, plan_id: int, payload):
        self.repository.get_required(plan_id)
        i = self.repository.create_intervention(care_plan_id=plan_id, **payload.model_dump(exclude_unset=True))
        self.db.commit()
        self.db.refresh(i)
        return i

    def update_intervention(self, intervention_id: int, payload):
        i = self.repository.get_intervention(intervention_id)
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(i, k, v)
        self.db.commit()
        self.db.refresh(i)
        return i

    # -- tasks --
    def add_task(self, plan_id: int, payload, *, actor_user_id: Optional[int] = None):
        plan = self.repository.get_required(plan_id)
        t = self.repository.create_task(
            care_plan_id=plan_id, patient_id=plan.patient_id, created_by_id=actor_user_id,
            **payload.model_dump(exclude_unset=True),
        )
        self.db.commit()
        self.db.refresh(t)
        return t

    def update_task(self, task_id: int, payload):
        t = self.repository.get_task(task_id)
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(t, k, v)
        self.db.commit()
        self.db.refresh(t)
        return t

    def complete_task(self, task_id: int, payload, *, actor_user_id: Optional[int] = None) -> CareTask:
        t = self.repository.get_task(task_id)
        if t.status == CareTaskStatus.COMPLETED:
            raise BadRequestError(message="Task already completed.")
        t.status = CareTaskStatus.COMPLETED
        t.completed_at = datetime.now(timezone.utc)
        t.completed_by_staff_id = payload.completed_by_staff_id
        t.completion_note = payload.completion_note
        self.db.commit()
        self.db.refresh(t)
        return t

    def list_tasks(self, **kwargs):
        return self.repository.list_tasks(**kwargs)

    # -- progress --
    def add_progress_note(self, plan_id: int, payload):
        self.repository.get_required(plan_id)
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("recorded_at", datetime.now(timezone.utc))
        n = self.repository.create_progress_note(care_plan_id=plan_id, **data)
        self.db.commit()
        self.db.refresh(n)
        return n

    # -- reviews --
    def add_review(self, plan_id: int, payload):
        plan = self.repository.get_required(plan_id)
        data = payload.model_dump(exclude_unset=True)
        data.setdefault("review_date", date.today())
        r = self.repository.create_review(care_plan_id=plan_id, **data)
        if r.next_review_date:
            plan.next_review_date = r.next_review_date
        self.db.commit()
        self.db.refresh(r)

        if r.outcome == CarePlanReviewOutcome.ESCALATE:
            try:
                self.alerts.raise_alert(
                    patient_id=plan.patient_id,
                    alert_type=AlertType.CARE_PLAN_DEVIATION,
                    severity=AlertSeverity.URGENT,
                    title=f"Care plan escalation — {plan.title}",
                    message=r.summary or "Care-plan review flagged escalation.",
                    care_plan_id=plan.id,
                    dedupe_key=f"careplan_escalate:{plan.id}:{r.id}",
                )
            except Exception as exc:
                logger.warning("Care-plan escalation alert failed for %s: %s", plan.id, exc)
        return r
