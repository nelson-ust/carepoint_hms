from __future__ import annotations

"""
app.services.visit_flow_service

Service layer for reusable visit flow templates and runtime visit flow steps.

Purpose
-------
This module implements business logic for:

- creating reusable visit flow templates
- creating reusable template steps
- creating runtime visit flow steps
- combined creation of template + template steps + runtime visit steps
- validating service delivery point existence
- validating visit existence for runtime steps
- enforcing template code uniqueness
- enforcing one current runtime step per visit
- updating and soft-deleting visit flow records

Design goals
------------
- keep repository focused on persistence/query logic
- centralize business rules and validation here
- support a single endpoint that can create:
    1. VisitFlowTemplate
    2. VisitFlowTemplateStep
    3. VisitFlowStep
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import VisitFlowStepStatus
from app.core.exceptions import AlreadyExistsError, BadRequestError, NotFoundError
from app.repositories.visit_flow_repository import VisitFlowRepository
from app.schemas.visit_flow_schemas import (
    VisitFlowCombinedCreateSchema,
    VisitFlowTemplateCreateSchema,
    VisitFlowTemplateStepCreateSchema,
    VisitFlowTemplateStepUpdateSchema,
    VisitFlowTemplateUpdateSchema,
    VisitFlowStepCreateSchema,
    VisitFlowStepUpdateSchema,
)


class VisitFlowService:
    """
    Service layer for reusable visit flow templates and runtime visit flow steps.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = VisitFlowRepository(db)

    # ============================================================
    # TEMPLATE CRUD
    # ============================================================

    def create_template(
        self,
        payload: VisitFlowTemplateCreateSchema,
    ):
        """
        Create a reusable visit flow template.

        Business rules
        --------------
        - template code must be unique
        """
        if self.repository.template_code_exists(payload.code):
            raise AlreadyExistsError(
                message="A visit flow template with this code already exists.",
                detail={"code": payload.code},
            )

        template = self.repository.create_template(
            name=payload.name,
            code=payload.code,
            description=payload.description,
        )
        self.db.commit()
        return self.repository.get_template_by_id(template.id)

    def get_template(self, template_id: int):
        """
        Return a reusable visit flow template by ID.
        """
        template = self.repository.get_template_by_id(template_id)
        if not template:
            raise NotFoundError(
                message="Visit flow template not found.",
                detail={"template_id": template_id},
            )
        return template

    def list_templates(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        code: Optional[str] = None,
        name: Optional[str] = None,
    ):
        """
        Return paginated reusable visit flow templates.
        """
        return self.repository.list_templates(
            skip=skip,
            limit=limit,
            code=code,
            name=name,
        )

    def update_template(
        self,
        template_id: int,
        payload: VisitFlowTemplateUpdateSchema,
    ):
        """
        Update a reusable visit flow template.
        """
        template = self.repository.get_template_by_id(template_id)
        if not template:
            raise NotFoundError(
                message="Visit flow template not found.",
                detail={"template_id": template_id},
            )

        if payload.code is not None and payload.code != template.code:
            if self.repository.template_code_exists(payload.code):
                raise AlreadyExistsError(
                    message="A visit flow template with this code already exists.",
                    detail={"code": payload.code},
                )
            template.code = payload.code

        if payload.name is not None:
            template.name = payload.name

        if payload.description is not None:
            template.description = payload.description

        updated = self.repository.update_template(template)
        self.db.commit()
        return self.repository.get_template_by_id(updated.id)

    def delete_template(self, template_id: int):
        """
        Soft-delete a reusable visit flow template.

        Notes
        -----
        Existing template steps are not auto-deleted here unless you later
        decide to cascade this behavior in service logic.
        """
        template = self.repository.get_template_by_id(template_id)
        if not template:
            raise NotFoundError(
                message="Visit flow template not found.",
                detail={"template_id": template_id},
            )

        deleted = self.repository.soft_delete_template(template)
        self.db.commit()
        return deleted

    # ============================================================
    # TEMPLATE STEP CRUD
    # ============================================================

    def create_template_step(
        self,
        payload: VisitFlowTemplateStepCreateSchema,
    ):
        """
        Create a reusable template step.

        Business rules
        --------------
        - template must exist
        - service delivery point must exist
        - step_order must be unique within the template
        """
        template = self.repository.get_template_by_id(payload.template_id)
        if not template:
            raise NotFoundError(
                message="Visit flow template not found.",
                detail={"template_id": payload.template_id},
            )

        self._ensure_service_delivery_point_exists(payload.service_delivery_point_id)
        self._ensure_template_step_order_available(
            template_id=payload.template_id,
            step_order=payload.step_order,
        )

        step = self.repository.create_template_step(
            template_id=payload.template_id,
            service_delivery_point_id=payload.service_delivery_point_id,
            step_order=payload.step_order,
            is_required=payload.is_required,
            notes=payload.notes,
        )
        self.db.commit()
        return self.repository.get_template_step_by_id(step.id)

    def update_template_step(
        self,
        template_step_id: int,
        payload: VisitFlowTemplateStepUpdateSchema,
    ):
        """
        Update a reusable template step.
        """
        step = self.repository.get_template_step_by_id(template_step_id)
        if not step:
            raise NotFoundError(
                message="Visit flow template step not found.",
                detail={"template_step_id": template_step_id},
            )

        if payload.service_delivery_point_id is not None:
            self._ensure_service_delivery_point_exists(payload.service_delivery_point_id)
            step.service_delivery_point_id = payload.service_delivery_point_id

        if payload.step_order is not None and payload.step_order != step.step_order:
            self._ensure_template_step_order_available(
                template_id=step.template_id,
                step_order=payload.step_order,
                exclude_step_id=step.id,
            )
            step.step_order = payload.step_order

        if payload.is_required is not None:
            step.is_required = payload.is_required

        if payload.notes is not None:
            step.notes = payload.notes

        updated = self.repository.update_template_step(step)
        self.db.commit()
        return self.repository.get_template_step_by_id(updated.id)

    def delete_template_step(self, template_step_id: int):
        """
        Soft-delete a reusable template step.
        """
        step = self.repository.get_template_step_by_id(template_step_id)
        if not step:
            raise NotFoundError(
                message="Visit flow template step not found.",
                detail={"template_step_id": template_step_id},
            )

        deleted = self.repository.soft_delete_template_step(step)
        self.db.commit()
        return deleted

    # ============================================================
    # RUNTIME VISIT STEP CRUD
    # ============================================================

    def create_visit_step(
        self,
        payload: VisitFlowStepCreateSchema,
    ):
        """
        Create a runtime visit flow step.

        Business rules
        --------------
        - visit must exist
        - service delivery point must exist
        - step_order should be unique within the visit
        - if is_current=True, clear any existing current step
        """
        self._ensure_visit_exists(payload.visit_id)
        self._ensure_service_delivery_point_exists(payload.service_delivery_point_id)
        self._ensure_visit_step_order_available(
            visit_id=payload.visit_id,
            step_order=payload.step_order,
        )

        status = self._resolve_flow_step_status(payload.status)

        step = self.repository.create_visit_step(
            visit_id=payload.visit_id,
            service_delivery_point_id=payload.service_delivery_point_id,
            step_order=payload.step_order,
            status=status,
            is_current=False,
            is_required=payload.is_required,
            is_skipped=payload.is_skipped,
            routed_by_id=payload.routed_by_id,
            started_at=payload.started_at,
            completed_at=payload.completed_at,
            notes=payload.notes,
        )

        if payload.is_current:
            self.repository.mark_visit_step_as_current(step)

        self.db.commit()
        return self.repository.get_visit_step_by_id(step.id)

    def get_visit_step(self, visit_step_id: int):
        """
        Return a runtime visit flow step by ID.
        """
        step = self.repository.get_visit_step_by_id(visit_step_id)
        if not step:
            raise NotFoundError(
                message="Visit flow step not found.",
                detail={"visit_step_id": visit_step_id},
            )
        return step

    def list_visit_steps(
        self,
        *,
        visit_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50,
    ):
        """
        Return paginated runtime visit steps.
        """
        if visit_id is not None:
            self._ensure_visit_exists(visit_id)

        return self.repository.list_visit_steps(
            visit_id=visit_id,
            skip=skip,
            limit=limit,
        )

    def update_visit_step(
        self,
        visit_step_id: int,
        payload: VisitFlowStepUpdateSchema,
    ):
        """
        Update a runtime visit flow step.
        """
        step = self.repository.get_visit_step_by_id(visit_step_id)
        if not step:
            raise NotFoundError(
                message="Visit flow step not found.",
                detail={"visit_step_id": visit_step_id},
            )

        if payload.service_delivery_point_id is not None:
            self._ensure_service_delivery_point_exists(payload.service_delivery_point_id)
            step.service_delivery_point_id = payload.service_delivery_point_id

        if payload.step_order is not None and payload.step_order != step.step_order:
            self._ensure_visit_step_order_available(
                visit_id=step.visit_id,
                step_order=payload.step_order,
                exclude_step_id=step.id,
            )
            step.step_order = payload.step_order

        if payload.status is not None:
            step.status = self._resolve_flow_step_status(payload.status)

        if payload.is_required is not None:
            step.is_required = payload.is_required

        if payload.is_skipped is not None:
            step.is_skipped = payload.is_skipped

        if payload.routed_by_id is not None:
            step.routed_by_id = payload.routed_by_id

        if payload.started_at is not None:
            step.started_at = payload.started_at

        if payload.completed_at is not None:
            step.completed_at = payload.completed_at

        if payload.notes is not None:
            step.notes = payload.notes

        updated = self.repository.update_visit_step(step)

        if payload.is_current is True:
            self.repository.mark_visit_step_as_current(updated)
        elif payload.is_current is False and updated.is_current:
            updated.is_current = False
            self.repository.update_visit_step(updated)

        self.db.commit()
        return self.repository.get_visit_step_by_id(updated.id)

    def delete_visit_step(self, visit_step_id: int):
        """
        Soft-delete a runtime visit flow step.
        """
        step = self.repository.get_visit_step_by_id(visit_step_id)
        if not step:
            raise NotFoundError(
                message="Visit flow step not found.",
                detail={"visit_step_id": visit_step_id},
            )

        deleted = self.repository.soft_delete_visit_step(step)
        self.db.commit()
        return deleted

    # ============================================================
    # COMBINED CREATE
    # ============================================================

    def create_combined_flow_records(
        self,
        payload: VisitFlowCombinedCreateSchema,
    ):
        """
        Create VisitFlowTemplate, VisitFlowTemplateStep, and VisitFlowStep
        in a single transaction.

        Business rules
        --------------
        - template code must be unique if template supplied
        - every referenced service delivery point must exist
        - visit must exist if runtime visit steps are supplied
        - template step orders must be unique
        - visit step orders must be unique
        - only one visit step may be current
        """
        template_payload = None
        if payload.template is not None:
            if self.repository.template_code_exists(payload.template.code):
                raise AlreadyExistsError(
                    message="A visit flow template with this code already exists.",
                    detail={"code": payload.template.code},
                )
            template_payload = payload.template.model_dump()

        if payload.template_steps:
            for step in payload.template_steps:
                self._ensure_service_delivery_point_exists(step.service_delivery_point_id)

        if payload.visit_steps:
            self._ensure_visit_exists(payload.visit_id)  # type: ignore[arg-type]
            for step in payload.visit_steps:
                self._ensure_service_delivery_point_exists(step.service_delivery_point_id)

        result = self.repository.create_combined_flow_records(
            template_payload=template_payload,
            template_steps_payload=[s.model_dump() for s in payload.template_steps],
            visit_id=payload.visit_id,
            visit_steps_payload=[
                {
                    **s.model_dump(),
                    "status": self._resolve_flow_step_status(s.status),
                }
                for s in payload.visit_steps
            ],
        )

        self.db.commit()

        created_template = None
        if result["template"] is not None:
            created_template = self.repository.get_template_by_id(result["template"].id)

        created_template_steps = [
            self.repository.get_template_step_by_id(step.id)
            for step in result["created_template_steps"]
        ]
        created_visit_steps = [
            self.repository.get_visit_step_by_id(step.id)
            for step in result["created_visit_steps"]
        ]

        return {
            "success": True,
            "message": "Visit flow records created successfully.",
            "template": created_template,
            "created_template_steps": [s for s in created_template_steps if s is not None],
            "created_visit_steps": [s for s in created_visit_steps if s is not None],
        }

    # ============================================================
    # HELPERS
    # ============================================================

    def _ensure_service_delivery_point_exists(self, service_delivery_point_id: int) -> None:
        service_point = self.repository.get_service_delivery_point_by_id(
            service_delivery_point_id
        )
        if not service_point:
            raise NotFoundError(
                message="Service delivery point not found.",
                detail={"service_delivery_point_id": service_delivery_point_id},
            )

    def _ensure_visit_exists(self, visit_id: int) -> None:
        visit = self.repository.get_visit_by_id(visit_id)
        if not visit:
            raise NotFoundError(
                message="Visit not found.",
                detail={"visit_id": visit_id},
            )

    def _ensure_template_step_order_available(
        self,
        *,
        template_id: int,
        step_order: int,
        exclude_step_id: Optional[int] = None,
    ) -> None:
        steps = self.repository.list_template_steps(template_id)
        for step in steps:
            if step.step_order == step_order and step.id != exclude_step_id:
                raise AlreadyExistsError(
                    message="This step_order already exists in the visit flow template.",
                    detail={
                        "template_id": template_id,
                        "step_order": step_order,
                    },
                )

    def _ensure_visit_step_order_available(
        self,
        *,
        visit_id: int,
        step_order: int,
        exclude_step_id: Optional[int] = None,
    ) -> None:
        steps, _ = self.repository.list_visit_steps(
            visit_id=visit_id,
            skip=0,
            limit=1000,
        )
        for step in steps:
            if step.step_order == step_order and step.id != exclude_step_id:
                raise AlreadyExistsError(
                    message="This step_order already exists in the visit.",
                    detail={
                        "visit_id": visit_id,
                        "step_order": step_order,
                    },
                )

    def _resolve_flow_step_status(
        self,
        status: Optional[str | VisitFlowStepStatus],
    ) -> VisitFlowStepStatus:
        """
        Normalize flow-step status to VisitFlowStepStatus enum.
        """
        if isinstance(status, VisitFlowStepStatus):
            return status

        if status is None:
            return VisitFlowStepStatus.PENDING

        normalized = str(status).strip().upper()
        try:
            return VisitFlowStepStatus[normalized]
        except KeyError:
            raise BadRequestError(
                message=f"Unsupported visit flow step status: {status}",
                detail={"status": status},
            )