from __future__ import annotations

"""
app.services.clinician_service

Service layer for clinician management.
"""

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.all_models import StaffProfile
from app.repositories.clinician_repository import ClinicianRepository


class ClinicianService:
    """
    Service layer for clinician-related workflows.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the service.
        """
        self.db = db
        self.repository = ClinicianRepository(db)

    def list_clinicians(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        specialty: str | None = None,
    ) -> tuple[list[StaffProfile], int]:
        """
        Return paginated clinicians.
        """
        return self.repository.list_clinicians(skip=skip, limit=limit, specialty=specialty)

    def get_clinician(self, clinician_id: int) -> StaffProfile:
        """
        Return a clinician by ID or raise NotFoundError.
        """
        clinician = self.repository.get_clinician_by_id(clinician_id)
        if not clinician:
            raise NotFoundError(
                message="Clinician not found.",
                detail={"clinician_id": clinician_id},
            )
        return clinician
