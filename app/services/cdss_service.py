# app/services/cdss_service.py
from sqlalchemy.orm import Session
from typing import Optional
from app.models.all_models import PatientAllergy, CdssAlert
from app.core.enums import CdssAlertType

class CdssService:
    def __init__(self, db: Session):
        self.db = db

    def check_allergies(self, patient_id: int, drug_name: str) -> bool:
        """
        Check if the prescribed drug triggers an allergy alert for the patient.
        Returns True if an allergy is found, otherwise False.
        """
        allergies = self.db.query(PatientAllergy).filter(
            PatientAllergy.patient_id == patient_id,
            PatientAllergy.is_active == True
        ).all()
        
        # Simple substring matching for demonstration. 
        # In a production CDSS, this would query a structured ontology like RxNorm.
        for allergy in allergies:
            if allergy.allergen_name.lower() in drug_name.lower():
                return True
        return False

    def log_alert(self, patient_id: int, clinician_id: int, alert_type: CdssAlertType, message: str, visit_id: Optional[int] = None) -> CdssAlert:
        """Logs a triggered CDSS alert for audit purposes."""
        alert = CdssAlert(
            patient_id=patient_id,
            clinician_staff_id=clinician_id,
            visit_id=visit_id,
            alert_type=alert_type,
            message=message,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert
