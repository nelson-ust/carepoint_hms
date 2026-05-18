# app/tests/unit/test_medical_history_service.py
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import NotFoundError
from app.core.enums import AllergySeverity
from app.services.medical_history_service import PatientMedicalHistoryService, _years_between


def test_years_between():
    assert _years_between(date(1990, 5, 10), date(2026, 5, 10)) == 36
    assert _years_between(date(1990, 5, 10), date(2026, 5, 9)) == 35
    assert _years_between(date(1990, 5, 10), date(1990, 5, 10)) == 0


class TestMedicalHistoryConstruction:
    def test_holds_session(self):
        db = MagicMock()
        svc = PatientMedicalHistoryService(db)
        assert svc.db is db


class TestPatientMedicalHistoryService:
    def test_demographic_dict_formatting(self):
        db = MagicMock()
        svc = PatientMedicalHistoryService(db)
        
        patient = MagicMock()
        patient.id = 123
        patient.hospital_number = "HOSP-12345"
        patient.first_name = "Jane"
        patient.last_name = "Doe"
        patient.middle_name = "Marie"
        patient.date_of_birth = date(1995, 10, 15)
        patient.gender = "FEMALE"
        patient.blood_group = "O_POSITIVE"
        patient.genotype = "AA"
        patient.allergies = "Shellfish"
        patient.patient_type = "OUTPATIENT"
        patient.phone_number = "+1234567890"
        patient.email = "jane.doe@example.com"
        patient.chronic_conditions = "Hypertension, Diabetes"

        with patch("app.services.medical_history_service.date") as mock_date:
            mock_date.today.return_value = date(2026, 10, 15)
            res = svc._demographic_dict(patient)
            
        assert res["id"] == 123
        assert res["hospital_number"] == "HOSP-12345"
        assert res["first_name"] == "Jane"
        assert res["last_name"] == "Doe"
        assert res["middle_name"] == "Marie"
        assert res["date_of_birth"] == date(1995, 10, 15)
        assert res["age_years"] == 31
        assert res["gender"] == "FEMALE"
        assert res["blood_group"] == "O_POSITIVE"
        assert res["genotype"] == "AA"
        assert res["allergies"] == "Shellfish"
        assert res["patient_type"] == "OUTPATIENT"
        assert res["phone_number"] == "+1234567890"
        assert res["email"] == "jane.doe@example.com"
        assert res["chronic_conditions"] == "Hypertension, Diabetes"

    def test_structured_allergies_query(self):
        db = MagicMock()
        svc = PatientMedicalHistoryService(db)
        
        # Mock the query builder
        query_mock = db.query.return_value
        filter_mock = query_mock.filter.return_value
        order_mock = filter_mock.order_by.return_value
        allergy_mock = MagicMock(id=1, allergen_name="Latex", severity=AllergySeverity.SEVERE)
        order_mock.all.return_value = [allergy_mock]

        result = svc._structured_allergies(123)

        assert len(result) == 1
        assert result[0] == allergy_mock
        db.query.assert_called_once()

    def test_get_patient_history_not_found(self):
        db = MagicMock()
        svc = PatientMedicalHistoryService(db)
        
        # Mock get patient query returning None
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(NotFoundError) as excinfo:
            svc.get_patient_history(999)
        assert "Patient not found." in str(excinfo.value)

    def test_get_patient_history_aggregation(self):
        db = MagicMock()
        svc = PatientMedicalHistoryService(db)
        
        # Mock Patient
        patient = MagicMock(
            id=123,
            allergies="Shellfish",
            chronic_conditions="Asthma",
            date_of_birth=None,
            gender=None,
            blood_group=None,
            genotype=None,
            patient_type=None,
            middle_name=None,
        )
        db.query.return_value.filter.return_value.first.return_value = patient

        # Mock all related queries/loaders on the service
        svc._visits_for_patient = MagicMock(return_value=[MagicMock(id=1)])
        svc._consultations = MagicMock(return_value=[])
        svc._diagnoses = MagicMock(return_value=[])
        svc._triage_assessments = MagicMock(return_value=[])
        svc._vital_signs = MagicMock(return_value=[])
        svc._lab_orders = MagicMock(return_value=[])
        svc._radiology_orders = MagicMock(return_value=[])
        svc._radiology_reports_for_orders = MagicMock(return_value={})
        svc._prescriptions = MagicMock(return_value=[])
        svc._procedure_orders = MagicMock(return_value=[])
        svc._surgical_cases = MagicMock(return_value=[])
        svc._admissions = MagicMock(return_value=[])
        
        # Mock active allergy list
        allergy = MagicMock(id=5, allergen_name="Latex", severity=AllergySeverity.SEVERE, reaction_description="Rash", is_active=True)
        svc._structured_allergies = MagicMock(return_value=[allergy])

        res = svc.get_patient_history(123)

        assert "patient" in res
        assert "summary" in res
        assert "structured_allergies" in res
        assert res["allergies"] == "Shellfish"
        assert len(res["structured_allergies"]) == 1
        assert res["structured_allergies"][0]["allergen_name"] == "Latex"
        assert res["structured_allergies"][0]["reaction"] == "Rash"
        assert res["structured_allergies"][0]["severity"] == "SEVERE"
        
        # Verify method calls
        svc._visits_for_patient.assert_called_once_with(123)
        svc._structured_allergies.assert_called_once_with(123)
