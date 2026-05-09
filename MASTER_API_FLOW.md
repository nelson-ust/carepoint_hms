# Carepoint HMS — Master API Sequential Flow

## 📖 Introduction
This guide explains the logical order in which the Carepoint HMS API should be consumed. Following this sequence ensures that all dependencies (like Visit IDs, Patient IDs, and Staff IDs) are correctly established before dependent actions are taken.

---

## 🛠️ Step 1: System Bootstrapping (SaaS Level)
**Required for: Initial platform setup.**

1. **Register Tenant**: `POST /api/v1/tenants/register`
2. **Approve Tenant**: `POST /api/v1/tenants/{id}/approve`
3. **Setup Admin Account**: (Created automatically during approval using onboarding data).

## 🏢 Step 2: Organizational Configuration (Tenant Level)
**Required for: Defining the hospital's structure.**

1. **Define Network**: `POST /api/v1/facilities/networks/create`
2. **Create Branch**: `POST /api/v1/facilities`
3. **Create Departments**: `POST /api/v1/departments`
4. **Create Service Points**: `POST /api/v1/service-delivery-points`
5. **Onboard Staff**: `POST /api/v1/staff-profiles/users`

## 🏥 Step 3: Clinical Operations (The "Visit" Lifecycle)
**Required for: Daily hospital operations.**

1. **Register Patient**: `POST /api/v1/patients` (Returns `patient_id`)
2. **Initiate Visit**: `POST /api/v1/visits/initiate` (Returns `visit_id`)
3. **Queue Patient**: `POST /api/v1/queue/check-in`
4. **Record Vitals**: `POST /api/v1/vital-signs` (Requires `visit_id`)
5. **Perform Consultation**: `POST /api/v1/consultations` (Requires `visit_id`)
6. **Raise Orders**:
    - **Lab**: `POST /api/v1/lab/orders`
    - **Prescription**: `POST /api/v1/prescriptions`
    - **Radiology**: `POST /api/v1/radiology/orders`

## 💊 Step 4: Ancillary Fulfillment
**Required for: Lab, Pharmacy, and Radiology staff.**

1. **Dispense Drugs**: `POST /api/v1/dispense` (Links to prescription)
2. **Record Lab Results**: `POST /api/v1/lab/results` (Links to order)

## 💰 Step 5: Finance & Exit
**Required for: Cashier and Front Desk staff.**

1. **Generate Invoice**: `POST /api/v1/invoices` (Aggregates all charges for a `visit_id`)
2. **Record Payment**: `POST /api/v1/payments` (Clears an invoice)
3. **Close Visit**: `POST /api/v1/visits/{id}/close`

---

## 🔗 Entity Dependency Map
- **Patient** -> **Visit** (1:M)
- **Visit** -> **Vitals / Consults / Orders / Invoices** (1:M)
- **Order** -> **Lab Results / Pharmacy Dispensing** (1:1)
- **Invoice** -> **Payments** (1:M)

---
*Generated: May 2026*
