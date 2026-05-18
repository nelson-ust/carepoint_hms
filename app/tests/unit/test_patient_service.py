# app/tests/unit/test_patient_service.py
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from datetime import date
from decimal import Decimal

from app.services.patient_service import PatientService
from app.schemas.patient_schemas import PatientCreateSchema, PatientUpdateSchema
from app.core.exceptions import BadRequestError, NotFoundError, AlreadyExistsError

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def service(mock_db):
    with patch("app.services.patient_service.PatientRepository") as mock_repo_cls:
        svc = PatientService(mock_db)
        svc.repository = mock_repo_cls.return_value
        yield svc

class TestPatientService:

    def test_create_patient_checks_for_existing_hospital_number(self, service, mock_db):
        payload = PatientCreateSchema(
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="MALE",
            hospital_number="MRN-123"
        )
        
        # Mock repository to find existing patient
        existing_patient = MagicMock()
        service.repository.get_by_hospital_number = MagicMock(return_value=existing_patient)
        
        result = service.create_patient(payload)
        
        assert result == existing_patient
        service.repository.get_by_hospital_number.assert_called_once_with("MRN-123")

    def test_create_patient_raises_bad_request_on_possible_duplicate(self, service, mock_db):
        payload = PatientCreateSchema(
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="MALE"
        )
        
        service.repository.get_by_hospital_number = MagicMock(return_value=None)
        service.repository.find_possible_duplicates = MagicMock(return_value=[MagicMock(id=1)])
        
        with pytest.raises(BadRequestError) as excinfo:
            service.create_patient(payload)
        
        assert "Possible duplicate patient record" in str(excinfo.value)

    def test_get_patient_raises_not_found(self, service):
        service.repository.get_by_id = MagicMock(return_value=None)
        
        with pytest.raises(NotFoundError):
            service.get_patient(999)

    def test_delete_patient_blocks_if_has_visits(self, service):
        patient = MagicMock(id=1)
        service.repository.get_by_id = MagicMock(return_value=patient)
        service.repository.patient_has_visits = MagicMock(return_value=True)
        
        with pytest.raises(BadRequestError) as excinfo:
            service.delete_patient(1)
        
        assert "cannot be deleted because visit records already exist" in str(excinfo.value)

    def test_update_patient_logs_changes(self, service, mock_db):
        patient = MagicMock(id=1, first_name="John", last_name="Doe", chronic_conditions="None")
        service.repository.get_by_id = MagicMock(return_value=patient)
        service.repository.get_detailed_by_id = MagicMock(return_value=patient)
        
        # Mock snapshots
        service._build_demographic_snapshot = MagicMock(return_value={"first_name": "John", "chronic_conditions": "None"})
        service._calculate_changed_fields = MagicMock(return_value=["first_name", "chronic_conditions"])
        
        payload = PatientUpdateSchema(first_name="Johnny", chronic_conditions="Hypertension")
        
        with patch("app.services.patient_service.log_entity_change") as mock_log:
            service.update_patient(1, payload, changed_by_id=42)
            
            assert patient.first_name == "Johnny"
            assert patient.chronic_conditions == "Hypertension"
            mock_db.commit.assert_called_once()
            service.repository.log_patient_demographic_change.assert_called_once()
            mock_log.assert_called_once()

    def test_add_patient_allergy(self, service, mock_db):
        from app.schemas.patient_schemas import PatientAllergyCreateSchema
        payload = PatientAllergyCreateSchema(
            allergen_name="Peanuts",
            severity="SEVERE",
            reaction="Anaphylaxis"
        )
        
        patient = MagicMock(id=1)
        service.repository.get_by_id = MagicMock(return_value=patient)
        
        allergy = MagicMock(id=10, allergen_name="Peanuts")
        service.repository.create_patient_allergy = MagicMock(return_value=allergy)
        
        result = service.add_patient_allergy(1, payload)
        
        assert result == allergy
        service.repository.create_patient_allergy.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_update_patient_allergy(self, service, mock_db):
        from app.schemas.patient_schemas import PatientAllergyUpdateSchema
        payload = PatientAllergyUpdateSchema(severity="MILD")
        
        allergy = MagicMock(id=10, severity="SEVERE")
        service.repository.get_patient_allergy_by_id = MagicMock(return_value=allergy)
        service.repository.update_patient_allergy = MagicMock(return_value=allergy)
        
        result = service.update_patient_allergy(10, payload)
        
        assert allergy.severity == "MILD"
        assert result == allergy
        mock_db.commit.assert_called_once()
