# Carepoint HMS — Full API Reference & Payload Catalog

## 📦 1. Multi-Tenant SaaS Management
### 1.1 Tenant Registration & Approval
- **POST `/api/v1/tenants/register`**
  ```json
  {
    "tenant_name": "St. Nicholas Hospital",
    "tenant_code": "stnicholas",
    "domain_url": "stnicholas.carepoint.com",
    "admin_email": "admin@stnicholas.com",
    "admin_username": "stadmin",
    "admin_password": "S3curePassword!",
    "plan_code": "ENTERPRISE"
  }
  ```
- **POST `/api/v1/tenants/{id}/approve`** (No body required)

---

## 🏥 2. Organizational Setup
### 2.1 Facilities & Departments
- **POST `/api/v1/facilities`**
  ```json
  {
    "name": "Victoria Island Branch",
    "code": "VI-BRANCH",
    "facility_type": "GENERAL_HOSPITAL",
    "phone_number": "+2348000000001",
    "email": "vi@stnicholas.com",
    "address": "123 Adetokunbo Ademola St",
    "city": "Lagos",
    "state": "Lagos",
    "country": "Nigeria"
  }
  ```
- **POST `/api/v1/departments`**
  ```json
  {
    "name": "Cardiology",
    "code": "CARD-01",
    "facility_id": 1,
    "is_clinical": true
  }
  ```

---

## 🧑‍⚕️ 3. Clinical Workflows (Outpatient)
### 3.1 Patient Management
- **POST `/api/v1/patients`**
  ```json
  {
    "first_name": "Nelson",
    "last_name": "Attah",
    "date_of_birth": "1985-10-15",
    "gender": "MALE",
    "phone_number": "+2348022334455",
    "email": "nelson@example.com",
    "blood_group": "O_POSITIVE",
    "genotype": "AA"
  }
  ```
- **POST `/api/v1/visits/initiate`**
  ```json
  {
    "patient_id": 1,
    "facility_id": 1,
    "visit_type": "OUTPATIENT",
    "priority": "NORMAL",
    "reason_for_visit": "General checkup"
  }
  ```

### 3.2 Triage & Consultation
- **POST `/api/v1/vital-signs`**
  ```json
  {
    "visit_id": 10,
    "systolic_bp": 120,
    "diastolic_bp": 80,
    "temperature": 36.8,
    "heart_rate": 72,
    "respiratory_rate": 16,
    "weight": 78.5,
    "height": 180.0
  }
  ```
- **POST `/api/v1/consultations`**
  ```json
  {
    "visit_id": 10,
    "subjective": "Patient reports persistent headaches for 3 days.",
    "objective": "Neurological exam normal. Pupils reactive.",
    "assessment": "Tension headache vs Migraine.",
    "plan": "Start on analgesics and monitor. Schedule MRI if pain persists."
  }
  ```

---

## 🧪 4. Laboratory & Pharmacy
### 4.1 Lab Orders & Results
- **POST `/api/v1/lab/orders`**
  ```json
  {
    "visit_id": 10,
    "test_catalogue_id": 5,
    "priority": "NORMAL",
    "clinical_notes": "Rule out malaria"
  }
  ```
- **POST `/api/v1/lab/results`**
  ```json
  {
    "order_id": 50,
    "test_component_id": 1,
    "result_value": "Negative",
    "is_abnormal": false
  }
  ```

### 4.2 Pharmacy Dispensing
- **POST `/api/v1/dispense`**
  ```json
  {
    "prescription_item_id": 100,
    "quantity_dispensed": 15,
    "batch_number": "BATCH-XYZ",
    "notes": "Full dose dispensed"
  }
  ```

---

## 💰 5. Finance & Billing
### 5.1 Invoicing & Payments
- **POST `/api/v1/invoices`**
  ```json
  {
    "visit_id": 10,
    "due_date": "2026-05-15",
    "notes": "Consolidated visit invoice"
  }
  ```
- **POST `/api/v1/payments`**
  ```json
  {
    "invoice_id": 200,
    "amount": 12500.00,
    "payment_method": "POS",
    "transaction_reference": "POS-889900"
  }
  ```

---

## 🛌 6. Inpatient (IPD) & Surgical
### 6.1 Admissions & Bed Management
- **POST `/api/v1/admissions`**
  ```json
  {
    "visit_id": 10,
    "ward_id": 2,
    "bed_id": 15,
    "admission_reason": "Post-operative monitoring",
    "provisional_diagnosis": "Acute Appendicitis"
  }
  ```

---

## 📱 7. Patient Portal & Loyalty
- **POST `/api/v1/portal/auth/request-otp`**
  ```json
  {
    "identifier": "+2348022334455",
    "channel": "SMS"
  }
  ```
- **POST `/api/v1/portal/fund-card`**
  ```json
  {
    "amount": 50000.00,
    "currency": "NGN"
  }
  ```

---
*Documentation v1.1 — Comprehensive Reference*

---

# HMO / Insurance & Advanced Accounting (added by the HMO+Accounting build)

Full details in `../IMPLEMENTATION_NOTES.md`. Highlights (all under `/api/v1`, JWT + permission gated):

## /hmo — HMO / Health Insurance (perm: CLAIM_READ / CLAIM_MANAGE / CLAIM_REVIEW)
- `GET/PUT /hmo/providers` — payer profiles (type, NHIA no, capitation/FFS support)
- `GET/POST/PUT /hmo/plans`, `/hmo/benefits`, `/hmo/tariffs`; `POST /hmo/plans/{id}/tariffs/import?dry_run=` (CSV)
- `GET /hmo/enrollees`, `POST /hmo/enrollees/{id}/link-plan|dependent`, `GET /hmo/enrollees/expiring`
- `POST/GET /hmo/eligibility-checks`; `POST /hmo/coverage/preview` (HMO-vs-patient split for any item)
- Capitation: `GET/POST/PUT /hmo/capitation/contracts`, `POST /hmo/capitation/run`,
  `GET /hmo/capitation/schedule`, `POST .../confirm`, `POST .../import-hmo-list`,
  `POST /hmo/capitation/payments`, `GET /hmo/capitation/utilization`
- Remittances: `GET/POST /hmo/remittances`, `GET /hmo/remittances/{id}/suggestions`, `POST .../allocate`
- Payer ledger: `GET /hmo/payers/balances`, `GET /hmo/payers/{id}/statement`
- Claims ext: `POST /hmo/claims/{id}/write-off|resubmit|push-patient-responsibility`,
  `GET/POST/PUT /hmo/rejection-reasons`, `POST /hmo/batches/generate-monthly`,
  `GET /hmo/batches/{id}/export.xlsx`
- Reports: `GET /hmo/reports/claim-aging|rejection-analysis|settlement`, `GET /hmo/dashboard`

## /banking — Bank & Cash (perm: ACCOUNTING_*)
- `GET/POST/PUT /banking/accounts`, `POST /banking/deposits`, `POST /banking/transfers`
- `POST /banking/accounts/{id}/statements/import` (CSV)
- `GET/POST /banking/reconciliations`, `GET /banking/reconciliations/{id}`,
  `POST .../auto-match|match|adjustments|complete`
- Petty cash: `GET/POST /banking/petty-cash/floats`, `POST .../top-up|vouchers|retire`,
  `GET /banking/petty-cash/vouchers`, `POST /banking/petty-cash/vouchers/{id}/decide`
- Cashier: `GET /banking/cashier-sessions[/mine|/daily-summary]`,
  `POST /banking/cashier-sessions/open`, `POST .../attach-payment|close`

## /accounting-ext — Accounting completeness (perm: ACCOUNTING_*)
- `GET /accounting-ext/accounts/tree`, `PUT /accounting-ext/accounts/{id}`
- `GET/PUT /accounting-ext/system-accounts` (posting map), `GET/PUT /accounting-ext/config`
- `POST /accounting-ext/opening-balances`, `POST /accounting-ext/seed-default-coa`, `POST .../seed-demo-hmos`
- `GET/POST/PUT /accounting-ext/cost-centers`, `POST .../generate-from-departments`
- Reports: `GET /accounting-ext/reports/cash-flow|general-ledger[.xlsx]|departmental-pnl|ar-segments`
- Controls: `GET /accounting-ext/periods/{id}/pre-close-checklist`, `GET /accounting-ext/posting-status`,
  `GET /accounting-ext/audit-log`
- AR/AP docs: `GET/POST /accounting-ext/credit-notes`, `POST .../issue`,
  `GET/POST /accounting-ext/refunds`, `POST .../pay`, `POST /accounting-ext/invoices/{id}/write-off`,
  `GET /accounting-ext/patients/{id}/statement`, `GET /accounting-ext/vendors/{id}/statement`,
  `POST /accounting-ext/vendor-credit-notes`, `POST /accounting-ext/payment-runs`

## /accounting additions
- `POST /accounting/journal-entries/{id}/approve` — maker-checker approval for PENDING_APPROVAL entries
- `POST /accounting/auto-post` — now also sweeps claims, capitation, disallowances, payroll
  statutory liabilities, pharmacy COGS and VAT (idempotent via `source_ref`)
