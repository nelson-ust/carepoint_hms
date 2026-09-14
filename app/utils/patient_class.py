# app/utils/patient_class.py
from __future__ import annotations

"""
Resolve a patient's effective billing class (SELF_PAY / HMO / RETAINERSHIP).

The class declared at registration is stored on ``Patient.patient_class``, but
the *effective* class is reconciled against the patient's active coverage
enrolment so it can never drift: an active enrolment whose provider is a
corporate retainer makes the patient RETAINERSHIP; any other active enrolment
makes them HMO; with no active enrolment the stored class (default SELF_PAY)
stands.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import InsuranceProviderType, PatientClass
from app.models.all_models import InsuranceProvider, Patient


def _provider_is_retainer(db: Session, insurance_provider_id: Optional[int]) -> bool:
    if not insurance_provider_id:
        return False
    provider = (
        db.query(InsuranceProvider)
        .filter(InsuranceProvider.id == insurance_provider_id)
        .first()
    )
    if provider is None:
        return False
    return str(provider.provider_type or "").upper() == InsuranceProviderType.CORPORATE_RETAINER.value


def resolve_patient_class(db: Session, patient: "Patient") -> PatientClass:
    """Return the patient's effective billing class."""
    # Reconcile against the active coverage enrolment (HMO or corporate retainer).
    try:
        from app.services.coverage_engine import CoverageEngine

        enrollment = CoverageEngine(db).active_insurance_for_patient(patient.id)
    except Exception:  # pragma: no cover - coverage lookup must never crash billing UI
        enrollment = None

    if enrollment is not None:
        if _provider_is_retainer(db, getattr(enrollment, "insurance_provider_id", None)):
            return PatientClass.RETAINERSHIP
        return PatientClass.HMO

    # No active coverage — fall back to the declared class (default SELF_PAY).
    declared = getattr(patient, "patient_class", None)
    if isinstance(declared, PatientClass):
        return declared
    try:
        return PatientClass(str(declared).upper()) if declared else PatientClass.SELF_PAY
    except ValueError:
        return PatientClass.SELF_PAY
