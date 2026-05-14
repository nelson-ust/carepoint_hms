from __future__ import annotations

"""
app.repositories.visit_flow_repository

Repository layer for reusable visit flow templates and runtime visit flow steps.

Purpose
-------
This module centralizes direct database operations for:

- creating and updating VisitFlowTemplate
- creating and updating VisitFlowTemplateStep
- creating and updating VisitFlowStep
- listing and retrieving templates and runtime steps
- creating template + template steps + runtime visit steps in a single transaction

Design goals
------------
- keep raw SQLAlchemy query logic out of route handlers
- keep service layer focused on business rules/orchestration
- support both reusable workflow design and runtime workflow execution
- support bulk/combined creation payloads cleanly
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.all_models import (
    ServiceDeliveryPoint,
    Visit,
    VisitFlowStep,
    VisitFlowTemplate,
    VisitFlowTemplateStep,
)


class VisitFlowRepository:
    """
    Repository for visit flow templates and runtime visit flow steps.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize repository with active SQLAlchemy session.
        """
        self.db = db

    # ============================================================
    # BASIC LOOKUPS
    # ============================================================

    def get_service_delivery_point_by_id(
        self,
        service_delivery_point_id: int,
    ) -> Optional[ServiceDeliveryPoint]:
        """
        Return a service delivery point by ID if not soft-deleted.
        """
        return (
            self.db.query(ServiceDeliveryPoint)
            .filter(
                ServiceDeliveryPoint.id == service_delivery_point_id,
                ServiceDeliveryPoint.is_deleted.is_(False),
            )
            .first()
        )

    def get_visit_by_id(self, visit_id: int) -> Optional[Visit]:
        """
        Return a visit by ID if not soft-deleted.
        """
        return (
            self.db.query(Visit)
            .filter(
                Visit.id == visit_id,
                Visit.is_deleted.is_(False),
            )
            .first()
        )

    # ============================================================
    # TEMPLATE LOOKUPS
    # ============================================================

    def get_template_by_id(self, template_id: int) -> Optional[VisitFlowTemplate]:
        """
        Return a reusable visit flow template by ID with ordered steps.
        """
        return (
            self.db.query(VisitFlowTemplate)
            .options(
                selectinload(
                    VisitFlowTemplate.steps
                ).filter(
                    VisitFlowTemplateStep.is_deleted.is_(False)
                ).joinedload(
                    VisitFlowTemplateStep.service_delivery_point
                )
            )
            .filter(
                VisitFlowTemplate.id == template_id,
                VisitFlowTemplate.is_deleted.is_(False),
            )
            .first()
        )

    def get_template_by_code(self, code: str) -> Optional[VisitFlowTemplate]:
        """
        Return a reusable visit flow template by code with ordered steps.
        """
        return (
            self.db.query(VisitFlowTemplate)
            .options(
                selectinload(
                    VisitFlowTemplate.steps
                ).filter(
                    VisitFlowTemplateStep.is_deleted.is_(False)
                ).joinedload(
                    VisitFlowTemplateStep.service_delivery_point
                )
            )
            .filter(
                VisitFlowTemplate.code == code,
                VisitFlowTemplate.is_deleted.is_(False),
            )
            .first()
        )

    def list_templates(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        code: Optional[str] = None,
        name: Optional[str] = None,
    ) -> tuple[list[VisitFlowTemplate], int]:
        """
        Return paginated reusable visit flow templates.
        """
        # Define base filters to reuse in both count and data queries
        base_filters = [VisitFlowTemplate.is_deleted.is_(False)]
        if code:
            base_filters.append(VisitFlowTemplate.code == code)
        if name:
            base_filters.append(VisitFlowTemplate.name.ilike(f"%{name.strip()}%"))

        # 1. Count query - Keep it lightweight by avoiding eager loads
        total = (
            self.db.query(func.count(VisitFlowTemplate.id))
            .filter(*base_filters)
            .scalar()
        ) or 0

        if total == 0:
            return [], 0

        # 2. Data query - Load only required relationships and filter nested steps
        items = (
            self.db.query(VisitFlowTemplate)
            .filter(*base_filters)
            .options(
                selectinload(
                    VisitFlowTemplate.steps
                ).filter(
                    VisitFlowTemplateStep.is_deleted.is_(False)
                ).joinedload(
                    VisitFlowTemplateStep.service_delivery_point
                )
            )
            .order_by(VisitFlowTemplate.name.asc(), VisitFlowTemplate.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, int(total)

    # ============================================================
    # TEMPLATE CREATE / UPDATE
    # ============================================================

    def create_template(
        self,
        *,
        name: str,
        code: str,
        description: Optional[str] = None,
    ) -> VisitFlowTemplate:
        """
        Create and persist a reusable visit flow template.
        """
        template = VisitFlowTemplate(
            name=name,
            code=code,
            description=description,
        )
        self.db.add(template)
        self.db.flush()
        self.db.refresh(template)
        return template

    def update_template(self, template: VisitFlowTemplate) -> VisitFlowTemplate:
        """
        Persist updates to a reusable visit flow template.
        """
        self.db.add(template)
        self.db.flush()
        self.db.refresh(template)
        return template

    def soft_delete_template(self, template: VisitFlowTemplate) -> VisitFlowTemplate:
        """
        Soft-delete a reusable visit flow template.
        """
        template.is_deleted = True
        self.db.add(template)
        self.db.flush()
        return template

    # ============================================================
    # TEMPLATE STEP LOOKUPS
    # ============================================================

    def get_template_step_by_id(
        self,
        template_step_id: int,
    ) -> Optional[VisitFlowTemplateStep]:
        """
        Return a template step by ID if not soft-deleted.
        """
        return (
            self.db.query(VisitFlowTemplateStep)
            .options(joinedload(VisitFlowTemplateStep.service_delivery_point))
            .filter(
                VisitFlowTemplateStep.id == template_step_id,
                VisitFlowTemplateStep.is_deleted.is_(False),
            )
            .first()
        )

    def list_template_steps(
        self,
        template_id: int,
    ) -> list[VisitFlowTemplateStep]:
        """
        Return ordered template steps for a reusable template.
        """
        return (
            self.db.query(VisitFlowTemplateStep)
            .options(joinedload(VisitFlowTemplateStep.service_delivery_point))
            .filter(
                VisitFlowTemplateStep.template_id == template_id,
                VisitFlowTemplateStep.is_deleted.is_(False),
            )
            .order_by(VisitFlowTemplateStep.step_order.asc(), VisitFlowTemplateStep.id.asc())
            .all()
        )

    def create_template_step(
        self,
        *,
        template_id: int,
        service_delivery_point_id: int,
        step_order: int,
        is_required: bool = True,
        notes: Optional[str] = None,
    ) -> VisitFlowTemplateStep:
        """
        Create and persist a reusable template step.
        """
        step = VisitFlowTemplateStep(
            template_id=template_id,
            service_delivery_point_id=service_delivery_point_id,
            step_order=step_order,
            is_required=is_required,
            notes=notes,
        )
        self.db.add(step)
        self.db.flush()
        self.db.refresh(step)
        return step

    def update_template_step(
        self,
        template_step: VisitFlowTemplateStep,
    ) -> VisitFlowTemplateStep:
        """
        Persist updates to a reusable template step.
        """
        self.db.add(template_step)
        self.db.flush()
        self.db.refresh(template_step)
        return template_step

    def soft_delete_template_step(
        self,
        template_step: VisitFlowTemplateStep,
    ) -> VisitFlowTemplateStep:
        """
        Soft-delete a reusable template step.
        """
        template_step.is_deleted = True
        self.db.add(template_step)
        self.db.flush()
        return template_step

    # ============================================================
    # RUNTIME VISIT STEP LOOKUPS
    # ============================================================

    def get_visit_step_by_id(self, visit_step_id: int) -> Optional[VisitFlowStep]:
        """
        Return a runtime visit flow step by ID if not soft-deleted.
        """
        return (
            self.db.query(VisitFlowStep)
            .options(joinedload(VisitFlowStep.service_delivery_point))
            .filter(
                VisitFlowStep.id == visit_step_id,
                VisitFlowStep.is_deleted.is_(False),
            )
            .first()
        )

    def get_current_visit_step(self, visit_id: int) -> Optional[VisitFlowStep]:
        """
        Return the current runtime step for a visit.
        """
        return (
            self.db.query(VisitFlowStep)
            .options(joinedload(VisitFlowStep.service_delivery_point))
            .filter(
                VisitFlowStep.visit_id == visit_id,
                VisitFlowStep.is_current.is_(True),
                VisitFlowStep.is_deleted.is_(False),
            )
            .first()
        )

    def list_visit_steps(
        self,
        *,
        visit_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[VisitFlowStep], int]:
        """
        Return paginated runtime visit flow steps.
        """
        base_filters = [VisitFlowStep.is_deleted.is_(False)]
        if visit_id is not None:
            base_filters.append(VisitFlowStep.visit_id == visit_id)

        # 1. Count query
        total = (
            self.db.query(func.count(VisitFlowStep.id))
            .filter(*base_filters)
            .scalar()
        ) or 0

        if total == 0:
            return [], 0

        # 2. Data query
        items = (
            self.db.query(VisitFlowStep)
            .filter(*base_filters)
            .options(joinedload(VisitFlowStep.service_delivery_point))
            .order_by(VisitFlowStep.visit_id.asc(), VisitFlowStep.step_order.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, int(total)

    def get_next_visit_step_order(self, visit_id: int) -> int:
        """
        Return the next runtime step order for a visit.
        """
        current_max = (
            self.db.query(func.max(VisitFlowStep.step_order))
            .filter(
                VisitFlowStep.visit_id == visit_id,
                VisitFlowStep.is_deleted.is_(False),
            )
            .scalar()
        )
        return int(current_max or 0) + 1

    # ============================================================
    # RUNTIME VISIT STEP CREATE / UPDATE
    # ============================================================

    def create_visit_step(
        self,
        *,
        visit_id: int,
        service_delivery_point_id: int,
        step_order: int,
        status,
        is_current: bool = False,
        is_required: bool = True,
        is_skipped: bool = False,
        routed_by_id: Optional[int] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> VisitFlowStep:
        """
        Create and persist a runtime visit flow step.
        """
        step = VisitFlowStep(
            visit_id=visit_id,
            service_delivery_point_id=service_delivery_point_id,
            step_order=step_order,
            status=status,
            is_current=is_current,
            is_required=is_required,
            is_skipped=is_skipped,
            routed_by_id=routed_by_id,
            started_at=started_at,
            completed_at=completed_at,
            notes=notes,
        )
        self.db.add(step)
        self.db.flush()
        self.db.refresh(step)
        return step

    def update_visit_step(self, visit_step: VisitFlowStep) -> VisitFlowStep:
        """
        Persist updates to a runtime visit flow step.
        """
        self.db.add(visit_step)
        self.db.flush()
        self.db.refresh(visit_step)
        return visit_step

    def soft_delete_visit_step(self, visit_step: VisitFlowStep) -> VisitFlowStep:
        """
        Soft-delete a runtime visit flow step.
        """
        visit_step.is_deleted = True
        self.db.add(visit_step)
        self.db.flush()
        return visit_step

    def clear_current_flags_for_visit(self, visit_id: int) -> None:
        """
        Clear all current flags for runtime steps of a visit.
        """
        steps = (
            self.db.query(VisitFlowStep)
            .filter(
                VisitFlowStep.visit_id == visit_id,
                VisitFlowStep.is_current.is_(True),
                VisitFlowStep.is_deleted.is_(False),
            )
            .all()
        )
        for step in steps:
            step.is_current = False
            self.db.add(step)
        self.db.flush()

    def mark_visit_step_as_current(self, visit_step: VisitFlowStep) -> VisitFlowStep:
        """
        Mark one runtime visit step as current.
        """
        self.clear_current_flags_for_visit(visit_step.visit_id)
        visit_step.is_current = True
        self.db.add(visit_step)
        self.db.flush()
        self.db.refresh(visit_step)
        return visit_step

    # ============================================================
    # COMBINED CREATE
    # ============================================================

    def create_combined_flow_records(
        self,
        *,
        template_payload: Optional[dict] = None,
        template_steps_payload: Optional[list[dict]] = None,
        visit_id: Optional[int] = None,
        visit_steps_payload: Optional[list[dict]] = None,
    ) -> dict:
        """
        Create VisitFlowTemplate, VisitFlowTemplateStep, and VisitFlowStep
        in a single repository operation.

        Notes
        -----
        - This method assumes validation has already happened in schemas/service.
        - It performs all creates in the current transaction scope.
        - Caller decides when to commit/rollback.

        Returns
        -------
        dict with keys:
        - template
        - created_template_steps
        - created_visit_steps
        """
        created_template: Optional[VisitFlowTemplate] = None
        created_template_steps: list[VisitFlowTemplateStep] = []
        created_visit_steps: list[VisitFlowStep] = []

        if template_payload is not None:
            created_template = self.create_template(
                name=template_payload["name"],
                code=template_payload["code"],
                description=template_payload.get("description"),
            )

        if template_steps_payload:
            if not created_template:
                raise ValueError(
                    "Template must be created or provided before template steps can be created."
                )

            for step_data in sorted(
                template_steps_payload,
                key=lambda item: item["step_order"],
            ):
                step = self.create_template_step(
                    template_id=created_template.id,
                    service_delivery_point_id=step_data["service_delivery_point_id"],
                    step_order=step_data["step_order"],
                    is_required=step_data.get("is_required", True),
                    notes=step_data.get("notes"),
                )
                created_template_steps.append(step)

        if visit_steps_payload:
            if visit_id is None:
                raise ValueError("visit_id is required when visit steps are supplied.")

            for step_data in sorted(
                visit_steps_payload,
                key=lambda item: item["step_order"],
            ):
                step = self.create_visit_step(
                    visit_id=visit_id,
                    service_delivery_point_id=step_data["service_delivery_point_id"],
                    step_order=step_data["step_order"],
                    status=step_data["status"],
                    is_current=step_data.get("is_current", False),
                    is_required=step_data.get("is_required", True),
                    is_skipped=step_data.get("is_skipped", False),
                    routed_by_id=step_data.get("routed_by_id"),
                    started_at=step_data.get("started_at"),
                    completed_at=step_data.get("completed_at"),
                    notes=step_data.get("notes"),
                )
                created_visit_steps.append(step)

            current_steps = [step for step in created_visit_steps if step.is_current]
            if current_steps:
                self.mark_visit_step_as_current(current_steps[-1])

        return {
            "template": created_template,
            "created_template_steps": created_template_steps,
            "created_visit_steps": created_visit_steps,
        }

    # ============================================================
    # EXISTENCE / UNIQUENESS HELPERS
    # ============================================================

    def template_code_exists(self, code: str) -> bool:
        """
        Return whether a template code already exists.
        """
        count = (
            self.db.query(func.count(VisitFlowTemplate.id))
            .filter(
                VisitFlowTemplate.code == code,
                VisitFlowTemplate.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )
        return count > 0

    def template_has_steps(self, template_id: int) -> bool:
        """
        Return whether a template has active steps.
        """
        count = (
            self.db.query(func.count(VisitFlowTemplateStep.id))
            .filter(
                VisitFlowTemplateStep.template_id == template_id,
                VisitFlowTemplateStep.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )
        return count > 0

    def visit_has_steps(self, visit_id: int) -> bool:
        """
        Return whether a visit already has runtime steps.
        """
        count = (
            self.db.query(func.count(VisitFlowStep.id))
            .filter(
                VisitFlowStep.visit_id == visit_id,
                VisitFlowStep.is_deleted.is_(False),
            )
            .scalar()
            or 0
        )
        return count > 0