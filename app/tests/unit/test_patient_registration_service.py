"""Unit tests for PatientRegistrationService."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.all_models import Patient, VisitFlowTemplate, Visit, QueueTicket, Admission
from app.schemas.patient_registration_schema import (
    ReturningPatientLookupSchema,
    UnifiedVisitInitiationSchema,
    VisitFlowOptionsSchema,
    UnifiedAdmissionOptionsSchema,
)
from app.services.patient_registration_service import PatientRegistrationService


class TestPatientRegistrationService:
    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.patient_registration_service.PatientService"), \
             patch("app.services.patient_registration_service.PatientRepository"), \
             patch("app.services.patient_registration_service.VisitService"), \
             patch("app.services.patient_registration_service.VisitFlowRepository"), \
             patch("app.services.patient_registration_service.AdmissionService"):
            svc = PatientRegistrationService(mock_db)
            return svc

    def test_find_returning_patient_by_hospital_number(self, service):
        mock_patient = MagicMock(spec=Patient)
        service.patient_repository.get_by_hospital_number.return_value = mock_patient
        
        result = service.find_returning_patient(hospital_number="HN123")
        
        assert result == mock_patient
        service.patient_repository.get_by_hospital_number.assert_called_once_with("HN123")

    def test_find_returning_patient_by_national_identifier(self, service):
        mock_patient = MagicMock(spec=Patient)
        service.patient_repository.get_by_national_identifier.return_value = mock_patient
        
        result = service.find_returning_patient(national_identifier="NID123")
        
        assert result == mock_patient
        service.patient_repository.get_by_national_identifier.assert_called_once_with("NID123")

    def test_find_returning_patient_by_phone(self, service):
        mock_patient = MagicMock(spec=Patient)
        service.patient_repository.search_patients.return_value = ([mock_patient], 1)
        
        result = service.find_returning_patient(phone_number="080123")
        
        assert result == mock_patient
        service.patient_repository.search_patients.assert_called_once_with(
            phone_number="080123", skip=0, limit=1
        )

    def test_find_returning_patient_not_found(self, service):
        service.patient_repository.get_by_hospital_number.return_value = None
        service.patient_repository.search_patients.return_value = ([], 0)
        
        result = service.find_returning_patient(hospital_number="MISSING")
        
        assert result is None

    def test_initiate_visit_returning_patient_success(self, service):
        # Setup
        patient = MagicMock(spec=Patient, id=1)
        template = MagicMock(spec=VisitFlowTemplate, id=10)
        visit = MagicMock(spec=Visit, id=100)
        ticket = MagicMock(spec=QueueTicket, id=1000)
        
        service.find_returning_patient = MagicMock(return_value=patient)
        service.flow_repository.get_template_by_code.return_value = template
        service.visit_service.initiate_visit.return_value = {
            "visit": visit,
            "first_queue_ticket": ticket
        }
        
        payload = UnifiedVisitInitiationSchema(
            existing_patient=ReturningPatientLookupSchema(hospital_number="HN123"),
            options=VisitFlowOptionsSchema(visit_reason="Routine Check")
        )
        
        # Execute
        result = service.initiate_visit_with_registration(payload, actor_user_id=5)
        
        # Assert
        assert result["is_returning_patient"] is True
        assert result["patient"] == patient
        assert result["visit"] == visit
        assert result["queue_ticket"] == ticket
        service.visit_service.initiate_visit.assert_called_once()

    def test_initiate_visit_returning_patient_not_found(self, service):
        service.find_returning_patient = MagicMock(return_value=None)
        
        payload = UnifiedVisitInitiationSchema(
            existing_patient=ReturningPatientLookupSchema(hospital_number="MISSING"),
            options=VisitFlowOptionsSchema()
        )
        
        with pytest.raises(NotFoundError):
            service.initiate_visit_with_registration(payload)

    def test_initiate_visit_new_patient_success(self, service):
        # Setup
        patient = MagicMock(spec=Patient, id=1)
        visit = MagicMock(spec=Visit, id=100)
        
        service.patient_service.create_patient.return_value = patient
        service.visit_service.initiate_visit.return_value = {"visit": visit}
        service.flow_repository.get_template_by_code.return_value = None
        
        # We need a mock PatientCreateSchema, but we can't easily create one with all required fields
        # So we patch the schema validation or just use a mock that looks like it
        from app.schemas.patient_schemas import PatientCreateSchema
        mock_new_patient = MagicMock(spec=PatientCreateSchema)
        
        payload = UnifiedVisitInitiationSchema(
            new_patient=mock_new_patient,
            options=VisitFlowOptionsSchema()
        )
        
        # Execute
        result = service.initiate_visit_with_registration(payload, actor_user_id=5)
        
        # Assert
        assert result["is_returning_patient"] is False
        assert result["patient"] == patient
        service.patient_service.create_patient.assert_called_once_with(mock_new_patient, registered_by_id=5)

    def test_initiate_visit_with_admission(self, service):
        # Setup
        patient = MagicMock(spec=Patient, id=1)
        visit = MagicMock(spec=Visit, id=100)
        admission = MagicMock(spec=Admission, id=500)
        
        service.find_returning_patient = MagicMock(return_value=patient)
        service.visit_service.initiate_visit.return_value = {"visit": visit}
        service.admission_service.admit.return_value = admission
        
        payload = UnifiedVisitInitiationSchema(
            existing_patient=ReturningPatientLookupSchema(hospital_number="HN123"),
            options=VisitFlowOptionsSchema(),
            admission=UnifiedAdmissionOptionsSchema(ward_id=1, bed_id=2)
        )
        
        # Execute
        result = service.initiate_visit_with_registration(payload, actor_user_id=5)
        
        # Assert
        assert result["admission"] == admission
        assert result["bed_day_charges_captured"] == 1
        service.admission_service.admit.assert_called_once()

    def test_initiate_visit_admission_fails_if_no_visit(self, service):
        patient = MagicMock(spec=Patient, id=1)
        service.find_returning_patient = MagicMock(return_value=patient)
        # Mock visit_service to return nothing or no visit
        service.visit_service.initiate_visit.return_value = {}
        
        payload = UnifiedVisitInitiationSchema(
            existing_patient=ReturningPatientLookupSchema(hospital_number="HN123"),
            options=VisitFlowOptionsSchema(),
            admission=UnifiedAdmissionOptionsSchema(ward_id=1)
        )
        
        with pytest.raises(BadRequestError, match="Visit could not be created"):
            service.initiate_visit_with_registration(payload)
