# app/api/v1/api.py
from __future__ import annotations

"""
app.api.v1.api

Main API router aggregator for version 1 of the Carepoint HMS API.

Purpose
-------
This module centralizes all version 1 route registrations into a single
`APIRouter` instance.

Why this exists
---------------
- keeps the application entrypoint (`main.py`) clean
- provides one place to register all v1 endpoint modules
- makes it easier to add or remove modules over time
- keeps route organization consistent across the project

Typical usage
-------------
Example in `app/main.py`:

    from fastapi import FastAPI
    from app.api.v1.api import api_router

    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

Notes
-----
- Each endpoint module should expose a router object named `router`.
- This file should only aggregate routers, not contain business logic.
"""

from fastapi import APIRouter

# ---------------------------------------------------------------------
# Import endpoint routers here
# ---------------------------------------------------------------------

# Auth / RBAC
from app.api.v1.endpoints.auth_routes import router as auth_router
from app.api.v1.endpoints.role_routes import router as role_router
from app.api.v1.endpoints.permission_routes import router as permission_router
from app.api.v1.endpoints.user_routes import router as user_router
from app.api.v1.endpoints.staff_routes import router as staff_router
from app.api.v1.endpoints.two_factor_routes import router as two_factor_router
from app.api.v1.endpoints.tenant_routes import router as tenant_router
from app.api.v1.endpoints.tenant_settings_routes import router as tenant_settings_router
from app.api.v1.endpoints.tenant_module_routes import router as tenant_module_router
from app.api.v1.endpoints.tenant_domain_routes import router as tenant_domain_router
from app.api.v1.endpoints.tenant_job_routes import router as tenant_job_router
from app.api.v1.endpoints.support_access_routes import router as support_access_router
from app.api.v1.endpoints.invitation_routes import router as invitation_router
from app.api.v1.endpoints.user_profile_routes import router as user_profile_router
from app.api.v1.endpoints.subscription_billing_routes import (
    router as subscription_billing_router,
)
from app.api.v1.endpoints.tenant_payment_method_routes import (
    router as tenant_payment_method_router,
)
from app.api.v1.endpoints.patient_payment_routes import (
    router as patient_payment_router,
)
from app.api.v1.endpoints.tenant_email_routes import (
    router as tenant_email_router,
)
from app.api.v1.endpoints.edge_node_routes import (
    admin_router as edge_node_admin_router,
    sync_router as edge_sync_router,
    connectivity_router as connectivity_router,
)
from app.api.v1.endpoints.medication_adherence_routes import (
    router as medication_adherence_router,
)
from app.api.v1.endpoints.doctor_calendar_routes import (
    router as doctor_calendar_router,
)
from app.api.v1.endpoints.appointment_extension_routes import (
    router as appointment_extension_router,
)
from app.api.v1.endpoints.tax_routes import router as tax_router
from app.api.v1.endpoints.hr_routes import router as hr_router
from app.api.v1.endpoints.tenant_dashboard_routes import router as tenant_dashboard_router
from app.api.v1.endpoints.database_backup_routes import router as database_backup_router
from app.api.v1.endpoints.saas_notification_routes import router as saas_notification_router
from app.api.v1.endpoints.saas_dashboard_routes import router as saas_dashboard_router
from app.api.v1.endpoints.saas_subscription_plan_routes import router as saas_subscription_plan_router
from app.api.v1.endpoints.saas_usage_routes import router as saas_usage_router
from app.api.v1.endpoints.saas_admin_routes import router as saas_admin_router
from app.api.v1.endpoints.integration_routes import router as integration_router
from app.api.v1.endpoints.template_routes import router as template_router

# Organization / setup
from app.api.v1.endpoints.department_routes import router as department_router
from app.api.v1.endpoints.ward_routes import router as ward_router
from app.api.v1.endpoints.bed_routes import router as bed_router
from app.api.v1.endpoints.service_delivery_point_routes import router as service_delivery_point_router
from app.api.v1.endpoints.facility_routes import router as facility_router

# Patients & visits
from app.api.v1.endpoints.patient_routes import router as patient_router
from app.api.v1.endpoints.patient_registration_routes import router as patient_registration_router
from app.api.v1.endpoints.report_routes import router as report_router
from app.api.v1.endpoints.saas_admin_portal_routes import router as saas_admin_portal_router
from app.api.v1.endpoints.visit_routes import router as visit_router
from app.api.v1.endpoints.visit_flow_routes import router as visit_flow_router
from app.api.v1.endpoints.queue_routes import router as queue_router
from app.api.v1.endpoints.membership_card_routes import router as membership_card_router
from app.api.v1.endpoints.patient_portal_routes import router as patient_portal_router
from app.api.v1.endpoints.paystack_webhook_routes import router as paystack_webhook_router

# Clinical
from app.api.v1.endpoints.clinician_routes import router as clinician_router
from app.api.v1.endpoints.triage_routes import router as triage_router
from app.api.v1.endpoints.vital_sign_routes import router as vital_sign_router
from app.api.v1.endpoints.consultation_routes import router as consultation_router
from app.api.v1.endpoints.diagnosis_routes import router as diagnosis_router
from app.api.v1.endpoints.referral_routes import router as referral_router

# Laboratory
from app.api.v1.endpoints.lab_routes import router as lab_router
from app.api.v1.endpoints.lab_order_routes import router as lab_order_router
from app.api.v1.endpoints.lab_result_routes import router as lab_result_router

# Pharmacy / Inventory
from app.api.v1.endpoints.drug_routes import router as drug_router
from app.api.v1.endpoints.inventory_routes import router as inventory_router
from app.api.v1.endpoints.stock_movement_routes import router as stock_movement_router
from app.api.v1.endpoints.prescription_routes import router as prescription_router
from app.api.v1.endpoints.dispense_routes import router as dispense_router
from app.api.v1.endpoints.pharmacy_routes import router as pharmacy_router

# Inpatient: admission + discharge
from app.api.v1.endpoints.admission_routes import router as admission_router
from app.api.v1.endpoints.discharge_routes import router as discharge_router

# Billing / Charge-to-cash
from app.api.v1.endpoints.billing_routes import router as billing_router
from app.api.v1.endpoints.invoice_routes import router as invoice_router
from app.api.v1.endpoints.payment_routes import router as payment_router

# Operational core (Stages 7, 15, 17, 18)
from app.api.v1.endpoints.appointment_routes import router as appointment_router
from app.api.v1.endpoints.ambulance_routes import (
    router as ambulance_router,
    dispatch_router as ambulance_dispatch_router,
)
from app.api.v1.endpoints.notification_routes import router as notification_router
from app.api.v1.endpoints.push_device_routes import router as push_device_router
from app.api.v1.endpoints.compliance_routes import router as compliance_router

# Procedure orders (Stage 5b)
from app.api.v1.endpoints.procedure_routes import (
    catalog_router as procedure_catalog_router,
    order_router as procedure_order_router,
)

# Radiology / RIS
from app.api.v1.endpoints.radiology_routes import (
    catalog_router as radiology_catalog_router,
    order_router as radiology_order_router,
    exam_router as radiology_exam_router,
    report_router as radiology_report_router,
)

# Surgical / Theatre
from app.api.v1.endpoints.surgical_routes import (
    theatre_router as surgical_theatre_router,
    catalog_router as surgical_catalog_router,
    case_router as surgical_case_router,
    team_router as surgical_team_router,
    consent_router as surgical_consent_router,
    checklist_router as surgical_checklist_router,
    anaesthesia_router as surgical_anaesthesia_router,
    note_router as surgical_note_router,
    instrument_router as surgical_instrument_router,
)

# Insurance Claims
from app.api.v1.endpoints.insurance_claim_routes import (
    batch_router as insurance_batch_router,
    claim_router as insurance_claim_router,
    auth_router as insurance_auth_router,
    adjudication_router as insurance_adjudication_router,
    payment_router as insurance_payment_router,
    appeal_router as insurance_appeal_router,
)

# Aggregated patient medical history (read-only)
from app.api.v1.endpoints.medical_history_routes import router as medical_history_router

# Reports
# from app.api.v1.endpoints.report_routes import router as report_router


# ---------------------------------------------------------------------
# Main API router
# ---------------------------------------------------------------------

api_router = APIRouter()


# ---------------------------------------------------------------------
# Register module routers
# ---------------------------------------------------------------------

# Authentication & RBAC
api_router.include_router(tenant_router)
api_router.include_router(tenant_module_router)
api_router.include_router(tenant_domain_router)
api_router.include_router(tenant_job_router)
api_router.include_router(support_access_router)
api_router.include_router(invitation_router)
api_router.include_router(subscription_billing_router)
api_router.include_router(tenant_payment_method_router)
api_router.include_router(patient_payment_router)
api_router.include_router(tenant_email_router)
# Offline-resilience: edge-node management + sync + connectivity probe.
api_router.include_router(edge_node_admin_router)
api_router.include_router(edge_sync_router)
api_router.include_router(connectivity_router)

# Clinical / scheduling / finance verticals.
api_router.include_router(medication_adherence_router)
api_router.include_router(doctor_calendar_router)
api_router.include_router(appointment_extension_router)
api_router.include_router(tax_router)
api_router.include_router(hr_router)
api_router.include_router(tenant_dashboard_router)
# Self-service profile endpoints (must be registered BEFORE the generic
# /users admin router so /users/me does not collide with /users/{id}).
api_router.include_router(user_profile_router)
api_router.include_router(saas_notification_router)
api_router.include_router(saas_dashboard_router)
api_router.include_router(saas_subscription_plan_router)
api_router.include_router(saas_usage_router)
api_router.include_router(saas_admin_router)
api_router.include_router(auth_router)
api_router.include_router(role_router)
api_router.include_router(permission_router)

# Tenant Settings & Backups
api_router.include_router(tenant_settings_router)
api_router.include_router(database_backup_router)
api_router.include_router(integration_router)
api_router.include_router(template_router)
api_router.include_router(report_router)
api_router.include_router(saas_admin_portal_router)
api_router.include_router(user_router)
api_router.include_router(staff_router)
api_router.include_router(two_factor_router)

# Organization / setup
api_router.include_router(department_router)
api_router.include_router(service_delivery_point_router)
api_router.include_router(facility_router)
api_router.include_router(ward_router)
api_router.include_router(bed_router)

# Patients & visits
api_router.include_router(patient_router)
api_router.include_router(patient_registration_router)
api_router.include_router(visit_router)
api_router.include_router(visit_flow_router)
api_router.include_router(queue_router)
api_router.include_router(membership_card_router, prefix="/membership-cards", tags=["Membership Cards"])
api_router.include_router(patient_portal_router)
api_router.include_router(paystack_webhook_router)

# Clinical
api_router.include_router(clinician_router)
api_router.include_router(triage_router)
api_router.include_router(vital_sign_router)
api_router.include_router(consultation_router)
api_router.include_router(diagnosis_router)
api_router.include_router(referral_router)

# Laboratory
api_router.include_router(lab_router)
api_router.include_router(lab_order_router)
api_router.include_router(lab_result_router)

# Pharmacy / Inventory
api_router.include_router(drug_router)
api_router.include_router(inventory_router)
api_router.include_router(stock_movement_router)
api_router.include_router(prescription_router)
api_router.include_router(dispense_router)
api_router.include_router(pharmacy_router)

# Inpatient — admission + discharge
api_router.include_router(admission_router)
api_router.include_router(discharge_router)

# Billing / Charge-to-cash
api_router.include_router(billing_router)
api_router.include_router(invoice_router)
api_router.include_router(payment_router)

# Appointments — Stage 7
api_router.include_router(appointment_router)

# Ambulance / dispatch — Stage 15
api_router.include_router(ambulance_router)
api_router.include_router(ambulance_dispatch_router)
# Notifications + direct messages — Stage 17
api_router.include_router(notification_router)
api_router.include_router(push_device_router)

# Compliance / governance — Stage 18
api_router.include_router(compliance_router)

# Procedure orders — clinic-room procedures
api_router.include_router(procedure_catalog_router)
api_router.include_router(procedure_order_router)

# Radiology / RIS
api_router.include_router(radiology_catalog_router)
api_router.include_router(radiology_order_router)
api_router.include_router(radiology_exam_router)
api_router.include_router(radiology_report_router)

# Surgical / Theatre
api_router.include_router(surgical_theatre_router)
api_router.include_router(surgical_catalog_router)
api_router.include_router(surgical_case_router)
api_router.include_router(surgical_team_router)
api_router.include_router(surgical_consent_router)
api_router.include_router(surgical_checklist_router)
api_router.include_router(surgical_anaesthesia_router)
api_router.include_router(surgical_note_router)
api_router.include_router(surgical_instrument_router)

# Insurance Claims
api_router.include_router(insurance_batch_router)
api_router.include_router(insurance_claim_router)
api_router.include_router(insurance_auth_router)
api_router.include_router(insurance_adjudication_router)
api_router.include_router(insurance_payment_router)
api_router.include_router(insurance_appeal_router)

# Aggregated patient medical history (read-only) — provides the
# clinician-facing single-call view of all clinical context for a
# patient (visits, consults, diagnoses, lab + radiology, prescriptions,
# surgeries, admissions, vitals).
api_router.include_router(medical_history_router)

# Reports
# api_router.include_router(report_router)