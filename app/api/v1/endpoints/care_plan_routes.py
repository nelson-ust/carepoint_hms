# app/api/v1/endpoints/care_plan_routes.py
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentActiveUser, require_plan_feature
from app.dependencies.role import require_permission
from app.models.all_models import User
from app.schemas.care_plan_schemas import (
    CarePlanActionResponseSchema,
    CarePlanCreateSchema,
    CarePlanDetailSchema,
    CarePlanGoalCreateSchema,
    CarePlanGoalReadSchema,
    CarePlanGoalUpdateSchema,
    CarePlanInterventionCreateSchema,
    CarePlanInterventionReadSchema,
    CarePlanInterventionUpdateSchema,
    CarePlanListResponseSchema,
    CarePlanProgressNoteCreateSchema,
    CarePlanReadSchema,
    CarePlanProgressNoteReadSchema,
    CarePlanReviewCreateSchema,
    CarePlanReviewReadSchema,
    CarePlanUpdateSchema,
    CareTaskCompleteSchema,
    CareTaskCreateSchema,
    CareTaskListResponseSchema,
    CareTaskReadSchema,
    CareTaskUpdateSchema,
)
from app.services.care_plan_service import CarePlanService
from app.utils.pagination import paginate_response

router = APIRouter(
    prefix="/care-plans",
    tags=["Home Health - Care Plans"],
    dependencies=[Depends(require_plan_feature("clinical"))],
)

_READ = require_permission("CARE_PLAN_READ", "CARE_PLAN_CREATE", "CARE_PLAN_MANAGE")
_MANAGE = require_permission("CARE_PLAN_MANAGE", "CARE_PLAN_UPDATE")


def get_service(db: Annotated[Session, Depends(get_db)]) -> CarePlanService:
    return CarePlanService(db)


# ----- Tasks (worklist) — declared before /{plan_id} to avoid path capture -----
@router.get("/tasks", response_model=CareTaskListResponseSchema, summary="List care tasks (worklist)")
def list_tasks(
    _: Annotated[User, Depends(_READ)],
    service: Annotated[CarePlanService, Depends(get_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    patient_id: Optional[int] = Query(None),
    assigned_staff_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    items, total = service.list_tasks(
        patient_id=patient_id, assigned_staff_id=assigned_staff_id, status=status_filter, skip=skip, limit=limit
    )
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Care tasks fetched successfully.")


@router.patch("/tasks/{task_id}", response_model=CareTaskReadSchema, summary="Update a care task")
def update_task(
    task_id: int,
    payload: CareTaskUpdateSchema,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    return service.update_task(task_id, payload)


@router.post("/tasks/{task_id}/complete", response_model=CareTaskReadSchema, summary="Complete a care task")
def complete_task(
    task_id: int,
    payload: CareTaskCompleteSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    return service.complete_task(task_id, payload, actor_user_id=actor.id)


# ----- Goal / intervention updates by id -----
@router.patch("/goals/{goal_id}", response_model=CarePlanGoalReadSchema, summary="Update a goal")
def update_goal(
    goal_id: int,
    payload: CarePlanGoalUpdateSchema,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    return service.update_goal(goal_id, payload)


@router.patch("/interventions/{intervention_id}", response_model=CarePlanInterventionReadSchema, summary="Update an intervention")
def update_intervention(
    intervention_id: int,
    payload: CarePlanInterventionUpdateSchema,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    return service.update_intervention(intervention_id, payload)


# ----- Care plans -----
@router.get("/", response_model=CarePlanListResponseSchema, summary="List care plans")
def list_plans(
    _: Annotated[User, Depends(_READ)],
    service: Annotated[CarePlanService, Depends(get_service)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    patient_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    lead_staff_id: Optional[int] = Query(None),
):
    items, total = service.list(patient_id=patient_id, status=status_filter, lead_staff_id=lead_staff_id, skip=skip, limit=limit)
    return paginate_response(items=items, total=total, skip=skip, limit=limit, message="Care plans fetched successfully.")


@router.post("/", response_model=CarePlanActionResponseSchema, status_code=status.HTTP_201_CREATED, summary="Create a care plan")
def create_plan(
    payload: CarePlanCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(require_permission("CARE_PLAN_CREATE", "CARE_PLAN_MANAGE"))],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    plan = service.create(payload, actor_user_id=actor.id)
    return {"success": True, "message": "Care plan created.", "care_plan": plan}


@router.get("/{plan_id}", response_model=CarePlanDetailSchema, summary="Get a care plan with all children")
def get_plan(
    plan_id: int,
    _: Annotated[User, Depends(_READ)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    detail = service.get_detail(plan_id)
    base = CarePlanReadSchema.model_validate(detail["plan"]).model_dump()
    return CarePlanDetailSchema(
        **base,
        goals=[CarePlanGoalReadSchema.model_validate(x) for x in detail["goals"]],
        interventions=[CarePlanInterventionReadSchema.model_validate(x) for x in detail["interventions"]],
        tasks=[CareTaskReadSchema.model_validate(x) for x in detail["tasks"]],
        progress_notes=[CarePlanProgressNoteReadSchema.model_validate(x) for x in detail["progress_notes"]],
        reviews=[CarePlanReviewReadSchema.model_validate(x) for x in detail["reviews"]],
    )


@router.patch("/{plan_id}", response_model=CarePlanActionResponseSchema, summary="Update a care plan")
def update_plan(
    plan_id: int,
    payload: CarePlanUpdateSchema,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    plan = service.update(plan_id, payload)
    return {"success": True, "message": "Care plan updated.", "care_plan": plan}


# ----- Children creation under a plan -----
@router.post("/{plan_id}/goals", response_model=CarePlanGoalReadSchema, status_code=status.HTTP_201_CREATED, summary="Add a goal")
def add_goal(
    plan_id: int,
    payload: CarePlanGoalCreateSchema,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    return service.add_goal(plan_id, payload)


@router.post("/{plan_id}/interventions", response_model=CarePlanInterventionReadSchema, status_code=status.HTTP_201_CREATED, summary="Add an intervention")
def add_intervention(
    plan_id: int,
    payload: CarePlanInterventionCreateSchema,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    return service.add_intervention(plan_id, payload)


@router.post("/{plan_id}/tasks", response_model=CareTaskReadSchema, status_code=status.HTTP_201_CREATED, summary="Add a task")
def add_task(
    plan_id: int,
    payload: CareTaskCreateSchema,
    actor: CurrentActiveUser,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    return service.add_task(plan_id, payload, actor_user_id=actor.id)


@router.post("/{plan_id}/progress-notes", response_model=CarePlanProgressNoteReadSchema, status_code=status.HTTP_201_CREATED, summary="Add a progress note")
def add_progress_note(
    plan_id: int,
    payload: CarePlanProgressNoteCreateSchema,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    return service.add_progress_note(plan_id, payload)


@router.post("/{plan_id}/reviews", response_model=CarePlanReviewReadSchema, status_code=status.HTTP_201_CREATED, summary="Add a review")
def add_review(
    plan_id: int,
    payload: CarePlanReviewCreateSchema,
    _: Annotated[User, Depends(_MANAGE)],
    service: Annotated[CarePlanService, Depends(get_service)],
):
    return service.add_review(plan_id, payload)
