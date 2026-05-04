# app/services/diagnosis_service.py
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import VisitStatus
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Diagnosis
from app.repositories.diagnosis_repository import DiagnosisRepository
from app.schemas.diagnosis_schema import DiagnosisCreateSchema, DiagnosisUpdateSchema


_TERMINAL = {VisitStatus.COMPLETED, VisitStatus.CANCELLED}


class DiagnosisService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = DiagnosisRepository(db)

    def list_for_visit(self, visit_id: int, *, skip: int = 0, limit: int = 50):
        return self.repository.list_for_visit(visit_id, skip=skip, limit=limit)

    def get(self, diagnosis_id: int) -> Diagnosis:
        return self.repository.get_required_by_id(diagnosis_id)

    def create(self, payload: DiagnosisCreateSchema, *, actor_user_id: Optional[int] = None) -> Diagnosis:
        visit = self.repository.get_visit(payload.visit_id)
        if not visit:
            raise NotFoundError(message="Visit not found.", detail={"visit_id": payload.visit_id})
        if visit.status in _TERMINAL:
            raise BadRequestError(
                message="Cannot record a diagnosis for a closed visit.",
                detail={"visit_status": str(visit.status)},
            )

        diagnosis = self.repository.create(
            visit_id=visit.id,
            consultation_id=payload.consultation_id,
            diagnosis_name=payload.diagnosis_name,
            diagnosis_code=payload.diagnosis_code,
            diagnosis_type=payload.diagnosis_type,
            diagnosis_note=payload.diagnosis_note,
        )
        self.db.commit()
        return self.repository.get_required_by_id(diagnosis.id)

    def update(
        self,
        diagnosis_id: int,
        payload: DiagnosisUpdateSchema,
        *,
        actor_user_id: Optional[int] = None,
    ) -> Diagnosis:
        diagnosis = self.repository.get_required_by_id(diagnosis_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(diagnosis, field, value)
        self.repository.save(diagnosis)
        self.db.commit()
        return self.repository.get_required_by_id(diagnosis.id)
