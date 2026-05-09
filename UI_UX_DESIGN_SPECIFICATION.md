# Carepoint HMS — UI/UX Design Specification & API Form Registry

## 🎨 1. Design Language & Aesthetics
- **Core Branding**: Deep Navy (#0F172A)
- **Action Colors**: Emerald (#10B981) for Success, Rose (#E11D48) for STAT/Critical.
- **Backgrounds**: Neutral Gray (#F8FAFC)
- **Typography**: Inter / Outfit

## 🏗️ 2. Frontend Architecture
- **SPA**: Next.js / React
- **Headers**: Mandatory `Authorization: Bearer <JWT>` and `X-Tenant-Code: <slug>`.

---

## 🗺️ 3. Master Form & Endpoint Registry
This section contains **every form and page** in the system, mapped to their specific API endpoints and Pydantic schemas.

### 📦 Module: TENANT (File: tenant_routes.py)
#### Form/Action: Register Tenant
- **Endpoint**: `POST /tenants/register`
**Request Payload:**
```json
{
  "tenant_name": "string",
  "tenant_code": "string",
  "domain_url": "string",
  "billing_email": "string",
  "billing_phone": "string",
  "billing_contact_name": "string",
  "billing_address": "string",
  "tax_id": "string",
  "plan_code": "string",
  "admin_email": "string",
  "admin_username": "string",
  "admin_password": "string",
  "admin_first_name": "string",
  "admin_last_name": "string"
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Approve Tenant
- **Endpoint**: `POST /tenants/{tenant_id}/approve`
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Tenants
- **Endpoint**: `GET /tenants`
**Response Body:**
```json
{
  "total_count": 0,
  "page": 0,
  "page_size": 0,
  "tenants": [
    {
      "id": "...",
      "name": "...",
      "code": "...",
      "db_connection_string": "...",
      "status": "...",
      "domain_url": "...",
      "custom_domain": "...",
      "billing_email": "...",
      "billing_phone": "...",
      "billing_contact_name": "...",
      "billing_address": "...",
      "tax_id": "...",
      "subscriptions": "..."
    }
  ]
}
```
---

#### Form/Action: Get Tenant
- **Endpoint**: `GET /tenants/{tenant_id}`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "db_connection_string": "string",
  "status": "string",
  "domain_url": "string",
  "custom_domain": "string",
  "billing_email": "string",
  "billing_phone": "string",
  "billing_contact_name": "string",
  "billing_address": "string",
  "tax_id": "string",
  "subscriptions": [
    {
      "id": "...",
      "tenant_id": "...",
      "plan_id": "...",
      "status": "...",
      "start_date": "...",
      "end_date": "...",
      "trial_end_date": "...",
      "auto_renew": "...",
      "plan": "..."
    }
  ]
}
```
---

#### Form/Action: Update Tenant Status
- **Endpoint**: `PUT /tenants/{tenant_id}/status`
**Request Payload:**
```json
{
  "status": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "db_connection_string": "string",
  "status": "string",
  "domain_url": "string",
  "custom_domain": "string",
  "billing_email": "string",
  "billing_phone": "string",
  "billing_contact_name": "string",
  "billing_address": "string",
  "tax_id": "string",
  "subscriptions": [
    {
      "id": "...",
      "tenant_id": "...",
      "plan_id": "...",
      "status": "...",
      "start_date": "...",
      "end_date": "...",
      "trial_end_date": "...",
      "auto_renew": "...",
      "plan": "..."
    }
  ]
}
```
---


### 📦 Module: TENANT_MODULE (File: tenant_module_routes.py)
#### Form/Action: List Module Catalog
- **Endpoint**: `GET /tenant-modules/catalog`
---

#### Form/Action: List Modules For Tenant
- **Endpoint**: `GET /tenant-modules/{tenant_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Set Module For Tenant
- **Endpoint**: `PUT /tenant-modules/{tenant_id}`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Bulk Set Modules For Tenant
- **Endpoint**: `PUT /tenant-modules/{tenant_id}/bulk`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Reset Module For Tenant
- **Endpoint**: `DELETE /tenant-modules/{tenant_id}/{module_code}`
---

#### Form/Action: List My Tenant Modules
- **Endpoint**: `GET /tenant-modules/me/list`
**Response Body:**
```json
"string"
```
---


### 📦 Module: TENANT_DOMAIN (File: tenant_domain_routes.py)
#### Form/Action: List Domains
- **Endpoint**: `GET /tenant-domains/{tenant_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Add Domain
- **Endpoint**: `POST /tenant-domains/{tenant_id}`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Get Verification Instructions
- **Endpoint**: `GET /tenant-domains/{tenant_id}/{domain_id}/verification`
---

#### Form/Action: Verify Domain
- **Endpoint**: `POST /tenant-domains/{tenant_id}/{domain_id}/verify`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Make Primary
- **Endpoint**: `POST /tenant-domains/{tenant_id}/{domain_id}/make-primary`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Remove Domain
- **Endpoint**: `DELETE /tenant-domains/{tenant_id}/{domain_id}`
---

#### Form/Action: Update Ssl Status
- **Endpoint**: `PUT /tenant-domains/{tenant_id}/{domain_id}/ssl`
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```
---


### 📦 Module: TENANT_JOB (File: tenant_job_routes.py)
#### Form/Action: List Handlers
- **Endpoint**: `GET /tenant-jobs/handlers`
---

#### Form/Action: List Jobs
- **Endpoint**: `GET /tenant-jobs`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Job
- **Endpoint**: `POST /tenant-jobs`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Job
- **Endpoint**: `PUT /tenant-jobs/{job_id}`
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Delete Job
- **Endpoint**: `DELETE /tenant-jobs/{job_id}`
---


### 📦 Module: SUPPORT_ACCESS (File: support_access_routes.py)
#### Form/Action: Request Grant
- **Endpoint**: `POST /support-access/request`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List My Grants
- **Endpoint**: `GET /support-access/me`
**Response Body:**
```json
"string"
```
---

#### Form/Action: List All Grants
- **Endpoint**: `GET /support-access`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Approve Grant
- **Endpoint**: `POST /support-access/{grant_id}/approve`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Revoke Grant
- **Endpoint**: `POST /support-access/{grant_id}/revoke`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Sweep Expired
- **Endpoint**: `POST /support-access/sweep`
---


### 📦 Module: INVITATION (File: invitation_routes.py)
#### Form/Action: Create Invitation
- **Endpoint**: `POST /invitations`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Invitations
- **Endpoint**: `GET /invitations`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Cancel Invitation
- **Endpoint**: `POST /invitations/{invitation_id}/cancel`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Resend Invitation
- **Endpoint**: `POST /invitations/{invitation_id}/resend`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Sweep Expired
- **Endpoint**: `POST /invitations/sweep`
---

#### Form/Action: Accept Invitation
- **Endpoint**: `POST /invitations/accept`
**Request Payload:**
```json
"string"
```
---


### 📦 Module: SUBSCRIPTION_BILLING (File: subscription_billing_routes.py)
#### Form/Action: List Invoices
- **Endpoint**: `GET /subscription-billing/invoices`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Issue Invoice
- **Endpoint**: `POST /subscription-billing/invoices/issue`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "billing_id": 0,
  "payer_id": 0,
  "invoice_no": "string",
  "status": "string",
  "invoice_date": "2026-05-09T00:00:00Z",
  "due_date": "2026-05-09T00:00:00Z",
  "subtotal_amount": 0.0,
  "discount_amount": 0.0,
  "tax_amount": 0.0,
  "total_amount": 0.0,
  "amount_paid": 0.0,
  "balance_due": 0.0,
  "note": "string",
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Run Due Invoice Generation
- **Endpoint**: `POST /subscription-billing/invoices/run-due`
---

#### Form/Action: Record Payment
- **Endpoint**: `POST /subscription-billing/invoices/{invoice_id}/payments`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
{
  "id": 0,
  "invoice_id": 0,
  "received_by_staff_id": 0,
  "payment_reference": "string",
  "payment_method": "string",
  "payment_status": "string",
  "amount": 0.0,
  "currency": "string",
  "paid_at": "2026-05-09T00:00:00Z",
  "transaction_metadata": "string",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Sweep Overdue
- **Endpoint**: `POST /subscription-billing/invoices/sweep-overdue`
---

#### Form/Action: List My Invoices
- **Endpoint**: `GET /subscription-billing/invoices/me`
**Response Body:**
```json
"string"
```
---


### 📦 Module: TENANT_PAYMENT_METHOD (File: tenant_payment_method_routes.py)
#### Form/Action: List Payment Methods
- **Endpoint**: `GET /tenant-payment-methods`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Payment Method
- **Endpoint**: `POST /tenant-payment-methods`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Payment Method
- **Endpoint**: `PUT /tenant-payment-methods/{config_id}`
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Delete Payment Method
- **Endpoint**: `DELETE /tenant-payment-methods/{config_id}`
---

#### Form/Action: Test Payment Method
- **Endpoint**: `POST /tenant-payment-methods/{config_id}/test`
---


### 📦 Module: PATIENT_PAYMENT (File: patient_payment_routes.py)
#### Form/Action: List Methods
- **Endpoint**: `GET /patient-payments/methods`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Pay Invoice
- **Endpoint**: `POST /patient-payments/pay`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Confirm Gateway
- **Endpoint**: `POST /patient-payments/confirm-gateway`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
{
  "id": 0,
  "invoice_id": 0,
  "received_by_staff_id": 0,
  "payment_reference": "string",
  "payment_method": "string",
  "payment_status": "string",
  "amount": 0.0,
  "currency": "string",
  "paid_at": "2026-05-09T00:00:00Z",
  "transaction_metadata": "string",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: TENANT_EMAIL (File: tenant_email_routes.py)
#### Form/Action: List Email Configs
- **Endpoint**: `GET /tenant-email-config`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Email Config
- **Endpoint**: `POST /tenant-email-config`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Email Config
- **Endpoint**: `PUT /tenant-email-config/{config_id}`
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Delete Email Config
- **Endpoint**: `DELETE /tenant-email-config/{config_id}`
---

#### Form/Action: Test Email Config
- **Endpoint**: `POST /tenant-email-config/{config_id}/test`
---

#### Form/Action: Send Test Email
- **Endpoint**: `POST /tenant-email-config/{config_id}/send-test`
**Request Payload:**
```json
"string"
```
---


### 📦 Module: EDGE_NODE_ADMIN (File: edge_node_routes.py)
#### Form/Action: List Edge Nodes
- **Endpoint**: `GET /edge-nodes`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Register Edge Node
- **Endpoint**: `POST /edge-nodes`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Rotate Edge Node Token
- **Endpoint**: `POST /edge-nodes/{node_id}/rotate-token`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Decommission Edge Node
- **Endpoint**: `POST /edge-nodes/{node_id}/decommission`
**Response Body:**
```json
"string"
```
---


### 📦 Module: EDGE_SYNC (File: edge_node_routes.py)
#### Form/Action: Edge Handshake
- **Endpoint**: `POST /sync/handshake`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Edge Pull
- **Endpoint**: `GET /sync/pull`
---

#### Form/Action: Edge Push
- **Endpoint**: `POST /sync/push`
**Request Payload:**
```json
"string"
```
---


### 📦 Module: CONNECTIVITY (File: edge_node_routes.py)
#### Form/Action: Connectivity Probe
- **Endpoint**: `GET /connectivity/probe`
---


### 📦 Module: MEDICATION_ADHERENCE (File: medication_adherence_routes.py)
#### Form/Action: List Profiles
- **Endpoint**: `GET /medication-adherence/profiles`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Materialise Profile
- **Endpoint**: `POST /medication-adherence/profiles/from-prescription/{prescription_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Schedule
- **Endpoint**: `POST /medication-adherence/schedules`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Schedules
- **Endpoint**: `GET /medication-adherence/schedules`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Generate Doses
- **Endpoint**: `POST /medication-adherence/schedules/{schedule_id}/generate-doses`
---

#### Form/Action: List Doses
- **Endpoint**: `GET /medication-adherence/doses`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Confirm Dose
- **Endpoint**: `POST /medication-adherence/doses/{dose_id}/confirm`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Read Reminder Prefs
- **Endpoint**: `GET /medication-adherence/patients/{patient_id}/reminder-preferences`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Reminder Prefs
- **Endpoint**: `PUT /medication-adherence/patients/{patient_id}/reminder-preferences`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Compute Adherence
- **Endpoint**: `POST /medication-adherence/adherence/compute`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Snapshots
- **Endpoint**: `GET /medication-adherence/adherence/snapshots`
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Alerts
- **Endpoint**: `GET /medication-adherence/alerts`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Acknowledge Alert
- **Endpoint**: `POST /medication-adherence/alerts/{alert_id}/acknowledge`
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Refills
- **Endpoint**: `GET /medication-adherence/refills`
---

#### Form/Action: Sweep Refills
- **Endpoint**: `POST /medication-adherence/refills/sweep-overdue`
---

#### Form/Action: Create Follow Up
- **Endpoint**: `POST /medication-adherence/follow-ups`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Follow Ups
- **Endpoint**: `GET /medication-adherence/follow-ups`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Complete Follow Up
- **Endpoint**: `POST /medication-adherence/follow-ups/{task_id}/complete`
**Response Body:**
```json
"string"
```
---


### 📦 Module: DOCTOR_CALENDAR (File: doctor_calendar_routes.py)
#### Form/Action: List Templates
- **Endpoint**: `GET /doctor-calendar/templates`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Template
- **Endpoint**: `POST /doctor-calendar/templates`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Deactivate Template
- **Endpoint**: `POST /doctor-calendar/templates/{template_id}/deactivate`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Add Time Off
- **Endpoint**: `POST /doctor-calendar/time-off`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Materialise Slots
- **Endpoint**: `POST /doctor-calendar/slots/materialise`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Slots
- **Endpoint**: `GET /doctor-calendar/slots`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Doctor Workload
- **Endpoint**: `GET /doctor-calendar/workload/{staff_profile_id}`
---

#### Form/Action: Reserve Slot
- **Endpoint**: `POST /doctor-calendar/slots/{slot_id}/reserve`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Release Slot
- **Endpoint**: `POST /doctor-calendar/slots/{slot_id}/release`
**Response Body:**
```json
"string"
```
---


### 📦 Module: APPOINTMENT_EXTENSION (File: appointment_extension_routes.py)
#### Form/Action: Schedule Reminders
- **Endpoint**: `POST /appointment-scheduling/reminders/schedule`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Dispatch Due Reminders
- **Endpoint**: `POST /appointment-scheduling/reminders/dispatch-due`
---

#### Form/Action: Log History
- **Endpoint**: `POST /appointment-scheduling/history/{appointment_id}/log`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Read History
- **Endpoint**: `GET /appointment-scheduling/history/{appointment_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Recurrence
- **Endpoint**: `POST /appointment-scheduling/recurrence`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Expand Recurrence
- **Endpoint**: `POST /appointment-scheduling/recurrence/{rule_id}/expand`
---


### 📦 Module: TAX (File: tax_routes.py)
#### Form/Action: List Types
- **Endpoint**: `GET /tax/types`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Type
- **Endpoint**: `POST /tax/types`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Type
- **Endpoint**: `PUT /tax/types/{tax_type_id}`
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Add Rate
- **Endpoint**: `POST /tax/rates`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Rates
- **Endpoint**: `GET /tax/rates`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Add Rule
- **Endpoint**: `POST /tax/rules`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Rules
- **Endpoint**: `GET /tax/rules`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Add Exemption
- **Endpoint**: `POST /tax/exemptions`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Exemptions
- **Endpoint**: `GET /tax/exemptions`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Compute Invoice Tax
- **Endpoint**: `POST /tax/invoices/{invoice_id}/compute`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Read Invoice Lines
- **Endpoint**: `GET /tax/invoices/{invoice_id}/lines`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Record Withholding
- **Endpoint**: `POST /tax/withholding`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Withholding
- **Endpoint**: `GET /tax/withholding`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Remit Withholding
- **Endpoint**: `POST /tax/withholding/{record_id}/remit`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Audit Log
- **Endpoint**: `GET /tax/audit-log`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Tax Summary
- **Endpoint**: `GET /tax/reports/summary`
---


### 📦 Module: HR (File: hr_routes.py)
#### Form/Action: Seed Onboarding
- **Endpoint**: `POST /hr/onboarding/{staff_profile_id}/seed`
---

#### Form/Action: Complete Onboarding Item
- **Endpoint**: `POST /hr/onboarding/items/{item_id}/complete`
---

#### Form/Action: Seed Offboarding
- **Endpoint**: `POST /hr/offboarding/{staff_profile_id}/seed`
---

#### Form/Action: Complete Offboarding Item
- **Endpoint**: `POST /hr/offboarding/items/{item_id}/complete`
---

#### Form/Action: Transition Status
- **Endpoint**: `POST /hr/profiles/{staff_profile_id}/status`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Status History
- **Endpoint**: `GET /hr/profiles/{staff_profile_id}/status-history`
---

#### Form/Action: Create Contract
- **Endpoint**: `POST /hr/contracts`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Contracts
- **Endpoint**: `GET /hr/contracts`
---

#### Form/Action: Create Document
- **Endpoint**: `POST /hr/documents`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Documents
- **Endpoint**: `GET /hr/documents`
---

#### Form/Action: Create License
- **Endpoint**: `POST /hr/licenses`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Licenses
- **Endpoint**: `GET /hr/licenses`
---

#### Form/Action: Sweep License Expiries
- **Endpoint**: `POST /hr/licenses/sweep-expiries`
---

#### Form/Action: Create Shift Template
- **Endpoint**: `POST /hr/roster/shift-templates`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Shift Templates
- **Endpoint**: `GET /hr/roster/shift-templates`
---

#### Form/Action: Create Roster
- **Endpoint**: `POST /hr/roster/rosters`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Create Assignment
- **Endpoint**: `POST /hr/roster/assignments`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Swap Assignment
- **Endpoint**: `POST /hr/roster/assignments/{assignment_id}/swap`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Assignments
- **Endpoint**: `GET /hr/roster/assignments`
---

#### Form/Action: Clock In
- **Endpoint**: `POST /hr/attendance/clock-in`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Clock Out
- **Endpoint**: `POST /hr/attendance/clock-out`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Attendance
- **Endpoint**: `GET /hr/attendance`
---

#### Form/Action: Generate Timesheet
- **Endpoint**: `POST /hr/timesheets/generate`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Submit Timesheet
- **Endpoint**: `POST /hr/timesheets/{timesheet_id}/submit`
---

#### Form/Action: Approve Timesheet
- **Endpoint**: `POST /hr/timesheets/{timesheet_id}/approve`
---

#### Form/Action: Lock Timesheet
- **Endpoint**: `POST /hr/timesheets/{timesheet_id}/lock`
---

#### Form/Action: List Timesheets
- **Endpoint**: `GET /hr/timesheets`
---

#### Form/Action: Create Leave Type
- **Endpoint**: `POST /hr/leave/types`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Leave Types
- **Endpoint**: `GET /hr/leave/types`
---

#### Form/Action: Submit Leave
- **Endpoint**: `POST /hr/leave/requests`
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "leave_type_id": 0,
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "days_requested": 0.0,
  "reason": "string",
  "handover_notes": "string",
  "cover_staff_id": 0
}
```
---

#### Form/Action: Decide Leave
- **Endpoint**: `POST /hr/leave/requests/{request_id}/decide`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Leave Requests
- **Endpoint**: `GET /hr/leave/requests`
---

#### Form/Action: List Leave Balances
- **Endpoint**: `GET /hr/leave/balances`
---

#### Form/Action: Create Holiday
- **Endpoint**: `POST /hr/leave/holidays`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Holidays
- **Endpoint**: `GET /hr/leave/holidays`
---

#### Form/Action: Create Payroll Run
- **Endpoint**: `POST /hr/payroll/runs`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Calculate Payroll
- **Endpoint**: `POST /hr/payroll/runs/{run_id}/calculate`
---

#### Form/Action: Approve Payroll
- **Endpoint**: `POST /hr/payroll/runs/{run_id}/approve`
---

#### Form/Action: Lock Payroll
- **Endpoint**: `POST /hr/payroll/runs/{run_id}/lock`
---

#### Form/Action: List Payroll Runs
- **Endpoint**: `GET /hr/payroll/runs`
---

#### Form/Action: List Payroll Lines
- **Endpoint**: `GET /hr/payroll/runs/{run_id}/lines`
---

#### Form/Action: Submit Overtime
- **Endpoint**: `POST /hr/overtime`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Decide Overtime
- **Endpoint**: `POST /hr/overtime/{record_id}/decide`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Request Loan
- **Endpoint**: `POST /hr/loans`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Approve Loan
- **Endpoint**: `POST /hr/loans/{loan_id}/approve`
---

#### Form/Action: Repay Loan
- **Endpoint**: `POST /hr/loans/{loan_id}/repay`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Set Staff Salary
- **Endpoint**: `POST /hr/payroll/salary`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Create Task
- **Endpoint**: `POST /hr/tasks`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Tasks
- **Endpoint**: `GET /hr/tasks`
---

#### Form/Action: Send Announcement
- **Endpoint**: `POST /hr/announcements`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: List Announcements
- **Endpoint**: `GET /hr/announcements`
---

#### Form/Action: Create Incident
- **Endpoint**: `POST /hr/incidents`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Create Disciplinary Action
- **Endpoint**: `POST /hr/incidents/actions`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Create Staff Request
- **Endpoint**: `POST /hr/requests`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Decide Staff Request
- **Endpoint**: `POST /hr/requests/{request_id}/decide`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Create Appraisal Cycle
- **Endpoint**: `POST /hr/appraisals/cycles`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Create Training Record
- **Endpoint**: `POST /hr/training/records`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Headcount Report
- **Endpoint**: `GET /hr/reports/headcount`
---

#### Form/Action: List Audit Log
- **Endpoint**: `GET /hr/audit-log`
---


### 📦 Module: APPROVAL (File: approval_routes.py)
#### Form/Action: List Flows
- **Endpoint**: `GET /approvals/flows`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Flow
- **Endpoint**: `POST /approvals/flows`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "description": "string",
  "subject_type": "string",
  "is_default": false,
  "sla_hours": 0,
  "auto_cancel_after_hours": 0,
  "notify_on_submit": false,
  "notify_on_decision": false,
  "steps": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "flow": {
    "id": 0,
    "code": "string",
    "name": "string",
    "description": "string",
    "subject_type": "string",
    "is_default": false,
    "is_active": false,
    "version": 0,
    "sla_hours": 0,
    "auto_cancel_after_hours": 0,
    "notify_on_submit": false,
    "notify_on_decision": false,
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Flow
- **Endpoint**: `GET /approvals/flows/{flow_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "flow": {
    "id": 0,
    "code": "string",
    "name": "string",
    "description": "string",
    "subject_type": "string",
    "is_default": false,
    "is_active": false,
    "version": 0,
    "sla_hours": 0,
    "auto_cancel_after_hours": 0,
    "notify_on_submit": false,
    "notify_on_decision": false,
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Update Flow
- **Endpoint**: `PATCH /approvals/flows/{flow_id}`
**Request Payload:**
```json
{
  "name": "string",
  "description": "string",
  "is_default": false,
  "is_active": false,
  "sla_hours": 0,
  "auto_cancel_after_hours": 0,
  "notify_on_submit": false,
  "notify_on_decision": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "flow": {
    "id": 0,
    "code": "string",
    "name": "string",
    "description": "string",
    "subject_type": "string",
    "is_default": false,
    "is_active": false,
    "version": 0,
    "sla_hours": 0,
    "auto_cancel_after_hours": 0,
    "notify_on_submit": false,
    "notify_on_decision": false,
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Delete Flow
- **Endpoint**: `DELETE /approvals/flows/{flow_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "flow": {
    "id": 0,
    "code": "string",
    "name": "string",
    "description": "string",
    "subject_type": "string",
    "is_default": false,
    "is_active": false,
    "version": 0,
    "sla_hours": 0,
    "auto_cancel_after_hours": 0,
    "notify_on_submit": false,
    "notify_on_decision": false,
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: List Requests
- **Endpoint**: `GET /approvals/requests`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: My Inbox
- **Endpoint**: `GET /approvals/requests/inbox`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: My Requests
- **Endpoint**: `GET /approvals/requests/mine`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Submit Request
- **Endpoint**: `POST /approvals/requests`
**Request Payload:**
```json
{
  "flow_id": 0,
  "flow_code": "string",
  "subject_type": "string",
  "subject_id": 0,
  "title": "string",
  "description": "string",
  "payload": "string",
  "priority": "string",
  "department_id": 0,
  "facility_id": 0,
  "submit_now": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Read Request
- **Endpoint**: `GET /approvals/requests/{request_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Record Decision
- **Endpoint**: `POST /approvals/requests/{request_id}/decisions`
**Request Payload:**
```json
{
  "action": "string",
  "comment": "string",
  "delegated_to_user_id": 0,
  "step_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "decision": {
    "id": 0,
    "request_id": 0,
    "request_step_id": 0,
    "decided_by_user_id": 0,
    "action": "string",
    "comment": "string",
    "delegated_to_user_id": 0,
    "decided_at": "2026-05-09T00:00:00Z"
  },
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Add Comment
- **Endpoint**: `POST /approvals/requests/{request_id}/comments`
**Request Payload:**
```json
{
  "body": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "comment": {
    "id": 0,
    "request_id": 0,
    "author_user_id": 0,
    "body": "string",
    "posted_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Request
- **Endpoint**: `POST /approvals/requests/{request_id}/cancel`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Admin Force Close
- **Endpoint**: `POST /approvals/requests/{request_id}/force-close`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Admin Reopen Step
- **Endpoint**: `POST /approvals/requests/{request_id}/steps/{step_id}/reopen`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "request": {
    "id": 0,
    "flow_id": 0,
    "subject_type": "string",
    "subject_id": 0,
    "requester_user_id": 0,
    "requester_staff_profile_id": 0,
    "department_id": 0,
    "facility_id": 0,
    "title": "string",
    "description": "string",
    "payload": "string",
    "priority": "string",
    "status": "string",
    "submitted_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "current_step_id": 0,
    "decision_summary": "string",
    "steps": "string",
    "comments": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Expire Stale
- **Endpoint**: `POST /approvals/maintenance/expire-stale`
---


### 📦 Module: TIMESHEET (File: timesheet_routes.py)
#### Form/Action: Create Timesheet
- **Endpoint**: `POST /timesheets`
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "period_start": "2026-05-09T00:00:00Z",
  "period_end": "2026-05-09T00:00:00Z",
  "notes": "string",
  "entries": [
    {
      "work_date": "...",
      "regular_hours": "...",
      "overtime_hours": "...",
      "night_hours": "...",
      "weekend_hours": "...",
      "holiday_hours": "...",
      "is_absent": "...",
      "note": "..."
    }
  ]
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Timesheets
- **Endpoint**: `GET /timesheets`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Get Timesheet
- **Endpoint**: `GET /timesheets/{timesheet_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Timesheet
- **Endpoint**: `PUT /timesheets/{timesheet_id}`
**Request Payload:**
```json
{
  "notes": "string",
  "entries": [
    {
      "work_date": "...",
      "regular_hours": "...",
      "overtime_hours": "...",
      "night_hours": "...",
      "weekend_hours": "...",
      "holiday_hours": "...",
      "is_absent": "...",
      "note": "..."
    }
  ]
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Delete Timesheet
- **Endpoint**: `DELETE /timesheets/{timesheet_id}`
---

#### Form/Action: Submit Timesheet
- **Endpoint**: `POST /timesheets/{timesheet_id}/submit`
**Request Payload:**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body:**
```json
"string"
```
---


### 📦 Module: LEAVE_REQUEST (File: leave_request_routes.py)
#### Form/Action: Create Leave Request
- **Endpoint**: `POST /leave-requests`
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "leave_type_id": 0,
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "days_requested": 0.0,
  "reason": "string",
  "handover_notes": "string",
  "cover_staff_id": 0
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Leave Requests
- **Endpoint**: `GET /leave-requests`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Get Leave Request
- **Endpoint**: `GET /leave-requests/{request_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Leave Request
- **Endpoint**: `PUT /leave-requests/{request_id}`
**Request Payload:**
```json
{
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "days_requested": 0.0,
  "reason": "string",
  "handover_notes": "string",
  "cover_staff_id": 0
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Delete Leave Request
- **Endpoint**: `DELETE /leave-requests/{request_id}`
---

#### Form/Action: Submit Leave Request
- **Endpoint**: `POST /leave-requests/{request_id}/submit`
**Request Payload:**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body:**
```json
"string"
```
---


### 📦 Module: REIMBURSEMENT (File: reimbursement_routes.py)
#### Form/Action: Create Reimbursement
- **Endpoint**: `POST /reimbursements`
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "expense_date": "2026-05-09T00:00:00Z",
  "amount": 0.0,
  "category": "string",
  "description": "string",
  "receipt_url": "string"
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Reimbursements
- **Endpoint**: `GET /reimbursements`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Get Reimbursement
- **Endpoint**: `GET /reimbursements/{request_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Reimbursement
- **Endpoint**: `PUT /reimbursements/{request_id}`
**Request Payload:**
```json
{
  "expense_date": "2026-05-09T00:00:00Z",
  "amount": 0.0,
  "category": "string",
  "description": "string",
  "receipt_url": "string"
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Delete Reimbursement
- **Endpoint**: `DELETE /reimbursements/{request_id}`
---

#### Form/Action: Submit Reimbursement
- **Endpoint**: `POST /reimbursements/{request_id}/submit`
**Request Payload:**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body:**
```json
"string"
```
---


### 📦 Module: SALARY_ADVANCE (File: salary_advance_routes.py)
#### Form/Action: Create Salary Advance
- **Endpoint**: `POST /salary-advances`
**Request Payload:**
```json
{
  "amount": 0.0,
  "reason": "string",
  "repayment_month": "2026-05-09T00:00:00Z",
  "staff_profile_id": 0
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Salary Advances
- **Endpoint**: `GET /salary-advances`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Get Salary Advance
- **Endpoint**: `GET /salary-advances/{request_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Salary Advance
- **Endpoint**: `PATCH /salary-advances/{request_id}`
**Request Payload:**
```json
{
  "amount": 0.0,
  "reason": "string",
  "repayment_month": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Delete Salary Advance
- **Endpoint**: `DELETE /salary-advances/{request_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Submit Salary Advance
- **Endpoint**: `POST /salary-advances/{request_id}/submit`
**Request Payload:**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body:**
```json
"string"
```
---


### 📦 Module: PROCUREMENT (File: procurement_routes.py)
#### Form/Action: Create Rfq
- **Endpoint**: `POST /procurements/rfqs`
**Request Payload:**
```json
{
  "title": "string",
  "description": "string",
  "bid_deadline": "2026-05-09T00:00:00Z",
  "vendor_ids": [
    0
  ],
  "items": [
    {
      "requisition_item_id": "...",
      "quantity": "..."
    }
  ]
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Po
- **Endpoint**: `POST /procurements/purchase-orders`
**Request Payload:**
```json
{
  "supplier_id": 0,
  "rfq_id": 0,
  "requisition_id": 0,
  "expected_delivery_date": "2026-05-09T00:00:00Z",
  "notes": "string",
  "items": [
    {
      "item_name": "...",
      "quantity_ordered": "...",
      "unit_price": "...",
      "tax_amount": "...",
      "discount_amount": "...",
      "drug_id": "...",
      "inventory_stock_item_id": "..."
    }
  ]
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Requisition
- **Endpoint**: `POST /procurements/requisitions`
**Request Payload:**
```json
{
  "facility_id": 0,
  "department_id": 0,
  "needed_by": "2026-05-09T00:00:00Z",
  "justification": "string",
  "requested_by_staff_id": 0,
  "items": [
    {
      "drug_id": "...",
      "inventory_stock_item_id": "...",
      "item_name": "...",
      "item_description": "...",
      "quantity_requested": "...",
      "unit_of_measure": "...",
      "estimated_unit_price": "..."
    }
  ]
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Requisitions
- **Endpoint**: `GET /procurements/requisitions`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Get Requisition
- **Endpoint**: `GET /procurements/requisitions/{requisition_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Requisition
- **Endpoint**: `PATCH /procurements/requisitions/{requisition_id}`
**Request Payload:**
```json
{
  "facility_id": 0,
  "department_id": 0,
  "needed_by": "2026-05-09T00:00:00Z",
  "justification": "string",
  "items": [
    {
      "drug_id": "...",
      "inventory_stock_item_id": "...",
      "item_name": "...",
      "item_description": "...",
      "quantity_requested": "...",
      "unit_of_measure": "...",
      "estimated_unit_price": "..."
    }
  ]
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Delete Requisition
- **Endpoint**: `DELETE /procurements/requisitions/{requisition_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Submit Requisition
- **Endpoint**: `POST /procurements/requisitions/{requisition_id}/submit`
**Request Payload:**
```json
{
  "flow_id": 0,
  "title": "string",
  "submit_now": false
}
```
**Response Body:**
```json
"string"
```
---


### 📦 Module: SHIFT (File: shift_routes.py)
#### Form/Action: Create Shift Definition
- **Endpoint**: `POST /shifts/definitions`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "shift_type": "string",
  "start_time": "string",
  "end_time": "string",
  "break_duration_minutes": 0,
  "color_hex": "string",
  "description": "string",
  "department_id": 0
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Shift Definitions
- **Endpoint**: `GET /shifts/definitions`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Get Shift Definition
- **Endpoint**: `GET /shifts/definitions/{definition_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Shift Definition
- **Endpoint**: `PATCH /shifts/definitions/{definition_id}`
**Request Payload:**
```json
{
  "name": "string",
  "shift_type": "string",
  "start_time": "string",
  "end_time": "string",
  "break_duration_minutes": 0,
  "color_hex": "string",
  "description": "string"
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Delete Shift Definition
- **Endpoint**: `DELETE /shifts/definitions/{definition_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Shift Assignment
- **Endpoint**: `POST /shifts/assignments`
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "shift_definition_id": 0,
  "shift_date": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Shift Assignments
- **Endpoint**: `GET /shifts/assignments`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Get Shift Assignment
- **Endpoint**: `GET /shifts/assignments/{assignment_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Shift Assignment
- **Endpoint**: `PATCH /shifts/assignments/{assignment_id}`
**Request Payload:**
```json
{
  "shift_definition_id": 0,
  "shift_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "notes": "string"
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Check In Shift
- **Endpoint**: `POST /shifts/assignments/{assignment_id}/check-in`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Check Out Shift
- **Endpoint**: `POST /shifts/assignments/{assignment_id}/check-out`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Delete Shift Assignment
- **Endpoint**: `DELETE /shifts/assignments/{assignment_id}`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Swap Request
- **Endpoint**: `POST /shifts/swaps`
**Request Payload:**
```json
{
  "requester_assignment_id": 0,
  "target_staff_id": 0,
  "target_assignment_id": 0,
  "reason": "string"
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Approve Swap Request
- **Endpoint**: `POST /shifts/swaps/{swap_id}/approve`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Reject Swap Request
- **Endpoint**: `POST /shifts/swaps/{swap_id}/reject`
**Response Body:**
```json
"string"
```
---


### 📦 Module: ONBOARDING (File: onboarding_routes.py)
#### Form/Action: Create Onboarding Invitation
- **Endpoint**: `POST /onboarding/invitations`
**Request Payload:**
```json
{
  "candidate_email": "string",
  "candidate_phone": "string",
  "notes": "string",
  "expiry_days": 0,
  "staff_profile_id": 0,
  "salary_grade_id": 0,
  "salary_step_id": 0
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Send Onboarding Link
- **Endpoint**: `POST /onboarding/invitations/{invitation_id}/send`
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Onboarding Invitations
- **Endpoint**: `GET /onboarding/invitations`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Get Onboarding Session
- **Endpoint**: `GET /onboarding/session`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Upload Onboarding Document
- **Endpoint**: `POST /onboarding/upload`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Complete Onboarding
- **Endpoint**: `POST /onboarding/complete`
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "nationality": "string",
  "address_line_1": "string",
  "city": "string",
  "state_region": "string",
  "country": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contacts": [
    {
      "full_name": "...",
      "relationship": "...",
      "phone_number": "...",
      "email": "...",
      "address": "...",
      "is_primary": "..."
    }
  ],
  "licenses": [
    {
      "license_type": "...",
      "license_number": "...",
      "issuing_body": "...",
      "issue_date": "...",
      "expiry_date": "...",
      "notes": "..."
    }
  ],
  "bank_name": "string",
  "bank_account_no": "string",
  "bank_account_name": "string"
}
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Get Onboarding Progress
- **Endpoint**: `GET /onboarding/progress`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Bulk Complete Onboarding
- **Endpoint**: `POST /onboarding/bulk-complete`
**Response Body:**
```json
"string"
```
---


### 📦 Module: PATIENT_IDENTITY (File: patient_identity_routes.py)
#### Form/Action: Add Identifier
- **Endpoint**: `POST /patient-master/{patient_id}/identifiers`
**Request Payload:**
```json
{
  "identifier_type": "string",
  "identifier_value": "string",
  "issuing_authority": "string",
  "is_primary": false,
  "is_active": false,
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "identifier_type": "string",
  "identifier_value": "string",
  "issuing_authority": "string",
  "is_primary": false,
  "is_active": false,
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: List Identifiers
- **Endpoint**: `GET /patient-master/{patient_id}/identifiers`
**Response Body:**
```json
[
  {
    "id": 0,
    "patient_id": 0,
    "identifier_type": "string",
    "identifier_value": "string",
    "issuing_authority": "string",
    "is_primary": false,
    "is_active": false,
    "note": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
]
```
---

#### Form/Action: Add Attachment
- **Endpoint**: `POST /patient-master/{patient_id}/attachments`
**Request Payload:**
```json
{
  "attachment_type": "string",
  "title": "string",
  "file_name": "string",
  "file_key": "string",
  "file_url": "string",
  "content_type": "string",
  "checksum": "string",
  "is_primary": false,
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "uploaded_by_id": 0,
  "attachment_type": "string",
  "title": "string",
  "file_name": "string",
  "file_key": "string",
  "file_url": "string",
  "content_type": "string",
  "checksum": "string",
  "is_primary": false,
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Record Consent
- **Endpoint**: `POST /patient-master/{patient_id}/consents`
**Request Payload:**
```json
{
  "consent_type": "string",
  "consent_status": "string",
  "consent_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "document_file_name": "string",
  "document_file_key": "string",
  "document_file_url": "string",
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "recorded_by_id": 0,
  "consent_type": "string",
  "consent_status": "string",
  "consent_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "document_file_name": "string",
  "document_file_key": "string",
  "document_file_url": "string",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Create Provider
- **Endpoint**: `POST /patient-master/insurance-providers`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "contact_person": "string",
  "email": "string",
  "phone_number": "string",
  "address": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "contact_person": "string",
  "email": "string",
  "phone_number": "string",
  "address": "string",
  "notes": "string",
  "id": 0
}
```
---

#### Form/Action: List Providers
- **Endpoint**: `GET /patient-master/insurance-providers`
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "contact_person": "string",
    "email": "string",
    "phone_number": "string",
    "address": "string",
    "notes": "string",
    "id": 0
  }
]
```
---

#### Form/Action: Link Insurance
- **Endpoint**: `POST /patient-master/{patient_id}/insurance`
**Request Payload:**
```json
{
  "insurance_provider_id": 0,
  "policy_number": "string",
  "member_name": "string",
  "relationship_to_member": "string",
  "plan_name": "string",
  "start_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "insurance_provider_id": 0,
  "policy_number": "string",
  "member_id": "string",
  "plan_name": "string",
  "coverage_details": "string",
  "status": "string",
  "valid_from": "2026-05-09T00:00:00Z",
  "valid_to": "2026-05-09T00:00:00Z",
  "note": "string",
  "insurance_provider": {
    "id": 0,
    "name": "string",
    "code": "string",
    "phone_number": "string",
    "email": "string"
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: PORTAL_SELF_SERVICE (File: portal_routes.py)
#### Form/Action: Register Account
- **Endpoint**: `POST /portal/register`
**Request Payload:**
```json
{
  "portal_username": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "patient_id": 0,
  "password": "string"
}
```
**Response Body:**
```json
{
  "portal_username": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "id": 0,
  "patient_id": 0,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Request Appointment
- **Endpoint**: `POST /portal/{account_id}/appointment-requests`
**Request Payload:**
```json
{
  "requested_date": "2026-05-09T00:00:00Z",
  "requested_sdp_id": 0,
  "requested_clinician_id": 0,
  "reason": "string",
  "priority": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "account_id": 0,
  "requested_date": "2026-05-09T00:00:00Z",
  "reason": "string",
  "status": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Send Message
- **Endpoint**: `POST /portal/{account_id}/messages`
**Request Payload:**
```json
{
  "subject": "string",
  "body": "string",
  "parent_message_id": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "subject": "string",
  "body": "string",
  "sender_type": "string",
  "is_read": false,
  "created_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Share Document
- **Endpoint**: `POST /portal/{account_id}/document-shares`
**Request Payload:**
```json
{
  "document_title": "string",
  "attachment_id": 0,
  "share_expiry": "2026-05-09T00:00:00Z",
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "document_title": "string",
  "file_url": "string",
  "share_expiry": "2026-05-09T00:00:00Z",
  "is_revoked": false
}
```
---


### 📦 Module: HR_PAYROLL (File: hr_payroll_routes.py)
#### Form/Action: Create Allowance Type
- **Endpoint**: `POST /hr/payroll-config/allowance-types`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "is_taxable": false,
  "default_amount": 0.0,
  "default_percent_of_base": 0.0,
  "description": "string",
  "is_active": false
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "is_taxable": false,
  "default_amount": 0.0,
  "default_percent_of_base": 0.0,
  "description": "string",
  "is_active": false,
  "id": 0
}
```
---

#### Form/Action: List Allowance Types
- **Endpoint**: `GET /hr/payroll-config/allowance-types`
**Response Body:**
```json
[
  {
    "code": "string",
    "name": "string",
    "is_taxable": false,
    "default_amount": 0.0,
    "default_percent_of_base": 0.0,
    "description": "string",
    "is_active": false,
    "id": 0
  }
]
```
---

#### Form/Action: Create Deduction Type
- **Endpoint**: `POST /hr/payroll-config/deduction-types`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "is_statutory": false,
  "default_amount": 0.0,
  "default_percent_of_base": 0.0,
  "description": "string",
  "is_active": false
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "is_statutory": false,
  "default_amount": 0.0,
  "default_percent_of_base": 0.0,
  "description": "string",
  "is_active": false,
  "id": 0
}
```
---

#### Form/Action: List Deduction Types
- **Endpoint**: `GET /hr/payroll-config/deduction-types`
**Response Body:**
```json
[
  {
    "code": "string",
    "name": "string",
    "is_statutory": false,
    "default_amount": 0.0,
    "default_percent_of_base": 0.0,
    "description": "string",
    "is_active": false,
    "id": 0
  }
]
```
---

#### Form/Action: Create Statutory Config
- **Endpoint**: `POST /hr/payroll-config/statutory-configs`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "rate_percent": 0.0,
  "bands_json": [
    "string"
  ],
  "employer_rate_percent": 0.0,
  "effective_from": "2026-05-09T00:00:00Z",
  "effective_to": "2026-05-09T00:00:00Z",
  "note": "string"
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "rate_percent": 0.0,
  "bands_json": [
    "string"
  ],
  "employer_rate_percent": 0.0,
  "effective_from": "2026-05-09T00:00:00Z",
  "effective_to": "2026-05-09T00:00:00Z",
  "note": "string",
  "id": 0
}
```
---

#### Form/Action: List Statutory Configs
- **Endpoint**: `GET /hr/payroll-config/statutory-configs`
**Response Body:**
```json
[
  {
    "code": "string",
    "name": "string",
    "rate_percent": 0.0,
    "bands_json": [
      "..."
    ],
    "employer_rate_percent": 0.0,
    "effective_from": "2026-05-09T00:00:00Z",
    "effective_to": "2026-05-09T00:00:00Z",
    "note": "string",
    "id": 0
  }
]
```
---


### 📦 Module: LOYALTY (File: loyalty_routes.py)
#### Form/Action: Create Program
- **Endpoint**: `POST /loyalty-network/programs`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "points_per_currency_unit": 0.0,
  "minimum_redemption_points": 0.0,
  "is_auto_enroll": false
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "points_per_currency_unit": 0.0,
  "minimum_redemption_points": 0.0,
  "is_auto_enroll": false,
  "id": 0
}
```
---

#### Form/Action: List Programs
- **Endpoint**: `GET /loyalty-network/programs`
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "description": "string",
    "points_per_currency_unit": 0.0,
    "minimum_redemption_points": 0.0,
    "is_auto_enroll": false,
    "id": 0
  }
]
```
---

#### Form/Action: Create Network
- **Endpoint**: `POST /loyalty-network/networks`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "id": 0
}
```
---

#### Form/Action: List Networks
- **Endpoint**: `GET /loyalty-network/networks`
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "description": "string",
    "id": 0
  }
]
```
---


### 📦 Module: TENANT_DASHBOARD (File: tenant_dashboard_routes.py)
#### Form/Action: Overview
- **Endpoint**: `GET /dashboard/overview`
---

#### Form/Action: Today Snapshot
- **Endpoint**: `GET /dashboard/today`
---

#### Form/Action: Patients
- **Endpoint**: `GET /dashboard/patients`
---

#### Form/Action: Visits
- **Endpoint**: `GET /dashboard/visits`
---

#### Form/Action: Appointments
- **Endpoint**: `GET /dashboard/appointments`
---

#### Form/Action: Inpatient
- **Endpoint**: `GET /dashboard/inpatient`
---

#### Form/Action: Billing
- **Endpoint**: `GET /dashboard/billing`
---

#### Form/Action: Lab Pharmacy Backlog
- **Endpoint**: `GET /dashboard/lab-pharmacy-backlog`
---

#### Form/Action: Inventory Alerts
- **Endpoint**: `GET /dashboard/inventory-alerts`
---

#### Form/Action: Hr
- **Endpoint**: `GET /dashboard/hr`
---

#### Form/Action: Medication Adherence
- **Endpoint**: `GET /dashboard/medication-adherence`
---

#### Form/Action: Recent Activity
- **Endpoint**: `GET /dashboard/recent-activity`
---


### 📦 Module: USER_PROFILE (File: user_profile_routes.py)
#### Form/Action: Read Me
- **Endpoint**: `GET /users/me`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Update Me
- **Endpoint**: `PUT /users/me`
**Request Payload:**
```json
"2026-05-09T00:00:00Z"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Upload Photo
- **Endpoint**: `POST /users/me/photo`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Remove Photo
- **Endpoint**: `DELETE /users/me/photo`
**Response Body:**
```json
"string"
```
---


### 📦 Module: SAAS_NOTIFICATION (File: saas_notification_routes.py)
#### Form/Action: List Saas Notifications
- **Endpoint**: `GET /saas/notifications`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Mark Notification Read
- **Endpoint**: `PATCH /saas/notifications/{notification_id}/read`
**Response Body:**
```json
"string"
```
---


### 📦 Module: SAAS_DASHBOARD (File: saas_dashboard_routes.py)
#### Form/Action: Get Metrics
- **Endpoint**: `GET /saas/dashboard/metrics`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Overview
- **Endpoint**: `GET /saas/dashboard/overview`
---

#### Form/Action: Tenant Summary
- **Endpoint**: `GET /saas/dashboard/tenants`
---

#### Form/Action: Onboarding Pipeline
- **Endpoint**: `GET /saas/dashboard/onboarding-pipeline`
---

#### Form/Action: Subscription Summary
- **Endpoint**: `GET /saas/dashboard/subscriptions`
---

#### Form/Action: Billing Summary
- **Endpoint**: `GET /saas/dashboard/billing`
---

#### Form/Action: Billing Ageing
- **Endpoint**: `GET /saas/dashboard/billing/ageing`
---

#### Form/Action: Edge Node Summary
- **Endpoint**: `GET /saas/dashboard/edge-nodes`
---

#### Form/Action: Support Access Summary
- **Endpoint**: `GET /saas/dashboard/support-access`
---

#### Form/Action: Usage Summary
- **Endpoint**: `GET /saas/dashboard/usage`
---

#### Form/Action: Top Tenants
- **Endpoint**: `GET /saas/dashboard/top-tenants`
---

#### Form/Action: Recent Activity
- **Endpoint**: `GET /saas/dashboard/recent-activity`
---


### 📦 Module: SAAS_SUBSCRIPTION_PLAN (File: saas_subscription_plan_routes.py)
#### Form/Action: List Plans
- **Endpoint**: `GET /saas/plans`
**Response Body:**
```json
[
  {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "price": 0.0,
    "currency": "string",
    "interval": 0,
    "max_facilities": 0,
    "max_users": 0,
    "max_patients": 0,
    "has_clinical": false,
    "has_inpatient": false,
    "has_laboratory": false,
    "has_pharmacy": false,
    "has_inventory": false,
    "has_billing": false,
    "has_reporting": false,
    "is_active": false
  }
]
```
---

#### Form/Action: Create Plan
- **Endpoint**: `POST /saas/plans`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "price": 0.0,
  "currency": "string",
  "interval": 0,
  "max_facilities": 0,
  "max_users": 0,
  "max_patients": 0,
  "has_clinical": false,
  "has_inpatient": false,
  "has_laboratory": false,
  "has_pharmacy": false,
  "has_inventory": false,
  "has_billing": false,
  "has_reporting": false,
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "price": 0.0,
  "currency": "string",
  "interval": 0,
  "max_facilities": 0,
  "max_users": 0,
  "max_patients": 0,
  "has_clinical": false,
  "has_inpatient": false,
  "has_laboratory": false,
  "has_pharmacy": false,
  "has_inventory": false,
  "has_billing": false,
  "has_reporting": false,
  "is_active": false
}
```
---

#### Form/Action: Update Plan
- **Endpoint**: `PUT /saas/plans/{plan_id}`
**Request Payload:**
```json
{
  "name": "string",
  "description": "string",
  "price": 0.0,
  "max_facilities": 0,
  "max_users": 0,
  "max_patients": 0,
  "has_clinical": false,
  "has_inpatient": false,
  "has_laboratory": false,
  "has_pharmacy": false,
  "has_inventory": false,
  "has_billing": false,
  "has_reporting": false,
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "price": 0.0,
  "currency": "string",
  "interval": 0,
  "max_facilities": 0,
  "max_users": 0,
  "max_patients": 0,
  "has_clinical": false,
  "has_inpatient": false,
  "has_laboratory": false,
  "has_pharmacy": false,
  "has_inventory": false,
  "has_billing": false,
  "has_reporting": false,
  "is_active": false
}
```
---


### 📦 Module: SAAS_USAGE (File: saas_usage_routes.py)
#### Form/Action: Get Tenant Usage
- **Endpoint**: `GET /saas/usage/{tenant_id}`
**Response Body:**
```json
{
  "id": 0,
  "tenant_id": 0,
  "user_count": 0,
  "storage_usage_bytes": 0,
  "api_call_count": 0,
  "transaction_count": 0,
  "sms_count": 0,
  "email_count": 0,
  "login_count": 0,
  "last_sync_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Sync Tenant Metrics
- **Endpoint**: `POST /saas/usage/{tenant_id}/sync`
**Response Body:**
```json
{
  "id": 0,
  "tenant_id": 0,
  "user_count": 0,
  "storage_usage_bytes": 0,
  "api_call_count": 0,
  "transaction_count": 0,
  "sms_count": 0,
  "email_count": 0,
  "login_count": 0,
  "last_sync_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: SAAS_ADMIN (File: saas_admin_routes.py)
#### Form/Action: List Admins
- **Endpoint**: `GET /saas/admins`
**Response Body:**
```json
[
  {
    "id": 0,
    "first_name": "string",
    "last_name": "string",
    "email": "string",
    "phone_number": "string",
    "status": "string",
    "is_superuser": false,
    "platform_role": "string"
  }
]
```
---

#### Form/Action: Create Admin
- **Endpoint**: `POST /saas/admins`
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "password": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```
---

#### Form/Action: Update Admin Status
- **Endpoint**: `PUT /saas/admins/{admin_id}/status`
**Request Payload:**
```json
{
  "status": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```
---

#### Form/Action: Get Admin
- **Endpoint**: `GET /saas/admins/{admin_id}`
**Response Body:**
```json
{
  "id": 0,
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```
---

#### Form/Action: Update Admin
- **Endpoint**: `PUT /saas/admins/{admin_id}`
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "first_name": "string",
  "last_name": "string",
  "email": "string",
  "phone_number": "string",
  "status": "string",
  "is_superuser": false,
  "platform_role": "string"
}
```
---

#### Form/Action: Delete Admin
- **Endpoint**: `DELETE /saas/admins/{admin_id}`
**Response Body:**
```json
"string"
```
---


### 📦 Module: AUTH (File: auth_routes.py)
#### Form/Action: Login
- **Endpoint**: `POST /auth/login`
**Request Payload:**
```json
{
  "identifier": "string",
  "password": "string",
  "remember_me": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "is_two_factor_enabled": false
  },
  "tokens": {
    "access_token": "string",
    "refresh_token": "string",
    "token_type": "string",
    "expires_in": 0,
    "refresh_expires_in": 0,
    "two_factor_required": false,
    "two_factor_verified": false
  }
}
```
---

#### Form/Action: Refresh Access Token
- **Endpoint**: `POST /auth/refresh`
**Request Payload:**
```json
{
  "refresh_token": "string"
}
```
**Response Body:**
```json
{
  "access_token": "string",
  "token_type": "string",
  "expires_in": 0
}
```
---

#### Form/Action: Impersonate Tenant
- **Endpoint**: `POST /auth/impersonate`
**Request Payload:**
```json
{
  "tenant_code": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "string",
  "tenant_code": "string",
  "tenant_name": "string"
}
```
---

#### Form/Action: Logout
- **Endpoint**: `POST /auth/logout`
**Request Payload:**
```json
{
  "refresh_token": "string",
  "all_sessions": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---

#### Form/Action: Get Authenticated Profile
- **Endpoint**: `GET /auth/me`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "tenant_id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "is_two_factor_enabled": false,
    "two_factor_method": "string",
    "two_factor_email_enabled": false,
    "two_factor_sms_enabled": false,
    "two_factor_whatsapp_enabled": false,
    "two_factor_authenticator_enabled": false,
    "roles": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "session": {
    "jti": "string",
    "issued_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "two_factor_verified": false,
    "ip_address": "string",
    "user_agent": "string"
  }
}
```
---

#### Form/Action: Change Password
- **Endpoint**: `POST /auth/change-password`
**Request Payload:**
```json
{
  "current_password": "string",
  "new_password": "string",
  "confirm_new_password": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---

#### Form/Action: Forgot Password
- **Endpoint**: `POST /auth/forgot-password`
**Request Payload:**
```json
{
  "identifier": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---

#### Form/Action: Reset Password
- **Endpoint**: `POST /auth/reset-password`
**Request Payload:**
```json
{
  "reset_token": "string",
  "new_password": "string",
  "confirm_new_password": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---

#### Form/Action: Verify Otp
- **Endpoint**: `POST /auth/otp/verify`
**Request Payload:**
```json
{
  "user_id": 0,
  "identifier": "string",
  "otp_code": "string",
  "challenge_reference": "string",
  "purpose": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "verified": false,
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "is_two_factor_enabled": false
  },
  "tokens": {
    "access_token": "string",
    "refresh_token": "string",
    "token_type": "string",
    "expires_in": 0,
    "refresh_expires_in": 0,
    "two_factor_required": false,
    "two_factor_verified": false
  }
}
```
---

#### Form/Action: Resend Otp
- **Endpoint**: `POST /auth/otp/resend`
**Request Payload:**
```json
{
  "user_id": 0,
  "identifier": "string",
  "purpose": "string",
  "delivery_method": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "challenge_reference": "string",
  "delivery_method": "string"
}
```
---

#### Form/Action: Setup Two Factor
- **Endpoint**: `POST /auth/two-factor/setup`
**Request Payload:**
```json
{
  "enable_two_factor": false,
  "method": "string",
  "enable_email": false,
  "enable_sms": false,
  "enable_whatsapp": false,
  "enable_authenticator": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "two_factor_enabled": false,
  "method": "string",
  "setup_secret": "string",
  "provisioning_uri": "string",
  "qr_code_data": "string"
}
```
---

#### Form/Action: Verify Two Factor
- **Endpoint**: `POST /auth/two-factor/verify`
**Request Payload:**
```json
{
  "user_id": 0,
  "identifier": "string",
  "otp_code": "string",
  "method": "string",
  "challenge_reference": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "verified": false,
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "is_two_factor_enabled": false
  },
  "tokens": {
    "access_token": "string",
    "refresh_token": "string",
    "token_type": "string",
    "expires_in": 0,
    "refresh_expires_in": 0,
    "two_factor_required": false,
    "two_factor_verified": false
  }
}
```
---

#### Form/Action: Request Email Verification
- **Endpoint**: `POST /auth/email-verification/request`
**Request Payload:**
```json
{
  "user_id": 0,
  "email": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "challenge_reference": "string",
  "delivery_method": "string"
}
```
---

#### Form/Action: Confirm Email Verification
- **Endpoint**: `POST /auth/email-verification/confirm`
**Request Payload:**
```json
{
  "token": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---

#### Form/Action: Request Phone Verification
- **Endpoint**: `POST /auth/phone-verification/request`
**Request Payload:**
```json
{
  "user_id": 0,
  "phone_number": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "challenge_reference": "string",
  "delivery_method": "string"
}
```
---

#### Form/Action: Confirm Phone Verification
- **Endpoint**: `POST /auth/phone-verification/confirm`
**Request Payload:**
```json
{
  "token": "string",
  "otp_code": "string",
  "challenge_reference": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---


### 📦 Module: ROLE (File: role_routes.py)
#### Form/Action: List Roles
- **Endpoint**: `GET /roles/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Role
- **Endpoint**: `GET /roles/{role_id}`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "permissions": "string"
}
```
---

#### Form/Action: Create Role
- **Endpoint**: `POST /roles/`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "permission_ids": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "permissions": "string"
}
```
---

#### Form/Action: Update Role
- **Endpoint**: `PUT /roles/{role_id}`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "permissions": "string"
}
```
---

#### Form/Action: Delete Role
- **Endpoint**: `DELETE /roles/{role_id}`
---

#### Form/Action: Assign Permissions To Role
- **Endpoint**: `POST /roles/{role_id}/permissions`
**Request Payload:**
```json
{
  "permission_ids": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "role": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "permissions": "string"
  }
}
```
---

#### Form/Action: Remove Permissions From Role
- **Endpoint**: `DELETE /roles/{role_id}/permissions`
**Request Payload:**
```json
{
  "permission_ids": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "role": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "permissions": "string"
  }
}
```
---


### 📦 Module: PERMISSION (File: permission_routes.py)
#### Form/Action: List Permissions
- **Endpoint**: `GET /permissions/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List Permission Modules
- **Endpoint**: `GET /permissions/modules`
---

#### Form/Action: Get My Permissions
- **Endpoint**: `GET /permissions/me`
---

#### Form/Action: Get Permission
- **Endpoint**: `GET /permissions/{permission_id}`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string",
  "is_system": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Create Permission
- **Endpoint**: `POST /permissions/`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string",
  "is_system": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string",
  "is_system": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Permission
- **Endpoint**: `PUT /permissions/{permission_id}`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "module": "string",
  "description": "string",
  "is_system": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Delete Permission
- **Endpoint**: `DELETE /permissions/{permission_id}`
---

#### Form/Action: Bulk Upsert Permissions
- **Endpoint**: `POST /permissions/bulk-upsert`
**Request Payload:**
```json
{
  "permissions": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "created_count": 0,
  "updated_count": 0,
  "skipped_count": 0,
  "items": "string"
}
```
---


### 📦 Module: TENANT_SETTINGS (File: tenant_settings_routes.py)
#### Form/Action: Get Settings
- **Endpoint**: `GET /settings`
**Response Body:**
```json
{
  "logo_url": "string",
  "theme_config": "string",
  "primary_color": "string",
  "secondary_color": "string",
  "default_currency": "string",
  "timezone": "string",
  "date_format": "string",
  "time_format": "string",
  "invoice_prefix": "string",
  "invoice_next_number": 0,
  "invoice_number_format": "string",
  "receipt_prefix": "string",
  "receipt_next_number": 0,
  "receipt_number_format": "string",
  "appointment_prefix": "string",
  "appointment_next_number": 0,
  "approval_workflows": "string",
  "notify_in_app_enabled": false,
  "notify_email_enabled": false,
  "notify_sms_enabled": false,
  "notify_whatsapp_enabled": false,
  "notify_push_enabled": false,
  "notification_channels": "string",
  "quiet_hours": "string",
  "notification_from_email": "string",
  "notification_from_name": "string",
  "notification_sms_sender_id": "string"
}
```
---

#### Form/Action: Update Settings
- **Endpoint**: `PUT /settings`
**Request Payload:**
```json
{
  "logo_url": "string",
  "theme_config": "string",
  "primary_color": "string",
  "secondary_color": "string",
  "default_currency": "string",
  "timezone": "string",
  "date_format": "string",
  "time_format": "string",
  "invoice_prefix": "string",
  "invoice_next_number": 0,
  "invoice_number_format": "string",
  "receipt_prefix": "string",
  "receipt_next_number": 0,
  "receipt_number_format": "string",
  "appointment_prefix": "string",
  "appointment_next_number": 0,
  "approval_workflows": "string",
  "notify_in_app_enabled": false,
  "notify_email_enabled": false,
  "notify_sms_enabled": false,
  "notify_whatsapp_enabled": false,
  "notify_push_enabled": false,
  "notification_channels": "string",
  "quiet_hours": "string",
  "notification_from_email": "string",
  "notification_from_name": "string",
  "notification_sms_sender_id": "string"
}
```
**Response Body:**
```json
{
  "logo_url": "string",
  "theme_config": "string",
  "primary_color": "string",
  "secondary_color": "string",
  "default_currency": "string",
  "timezone": "string",
  "date_format": "string",
  "time_format": "string",
  "invoice_prefix": "string",
  "invoice_next_number": 0,
  "invoice_number_format": "string",
  "receipt_prefix": "string",
  "receipt_next_number": 0,
  "receipt_number_format": "string",
  "appointment_prefix": "string",
  "appointment_next_number": 0,
  "approval_workflows": "string",
  "notify_in_app_enabled": false,
  "notify_email_enabled": false,
  "notify_sms_enabled": false,
  "notify_whatsapp_enabled": false,
  "notify_push_enabled": false,
  "notification_channels": "string",
  "quiet_hours": "string",
  "notification_from_email": "string",
  "notification_from_name": "string",
  "notification_sms_sender_id": "string"
}
```
---

#### Form/Action: Upload Logo
- **Endpoint**: `POST /settings/logo`
**Response Body:**
```json
{
  "logo_url": "string",
  "theme_config": "string",
  "primary_color": "string",
  "secondary_color": "string",
  "default_currency": "string",
  "timezone": "string",
  "date_format": "string",
  "time_format": "string",
  "invoice_prefix": "string",
  "invoice_next_number": 0,
  "invoice_number_format": "string",
  "receipt_prefix": "string",
  "receipt_next_number": 0,
  "receipt_number_format": "string",
  "appointment_prefix": "string",
  "appointment_next_number": 0,
  "approval_workflows": "string",
  "notify_in_app_enabled": false,
  "notify_email_enabled": false,
  "notify_sms_enabled": false,
  "notify_whatsapp_enabled": false,
  "notify_push_enabled": false,
  "notification_channels": "string",
  "quiet_hours": "string",
  "notification_from_email": "string",
  "notification_from_name": "string",
  "notification_sms_sender_id": "string"
}
```
---


### 📦 Module: DATABASE_BACKUP (File: database_backup_routes.py)
#### Form/Action: List Backups
- **Endpoint**: `GET /backups`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Create Backup
- **Endpoint**: `POST /backups`
**Response Body:**
```json
{
  "id": 0,
  "filename": "string",
  "s3_url": "string",
  "s3_key": "string",
  "size_bytes": 0,
  "status": "string",
  "error_message": "string",
  "is_encrypted": false,
  "encryption_algo": "string",
  "checksum_sha256": "string",
  "backup_type": "string",
  "pg_dump_format": "string",
  "backup_started_at": "2026-05-09T00:00:00Z",
  "backup_finished_at": "2026-05-09T00:00:00Z",
  "pitr_lsn": "string",
  "pitr_timestamp": "2026-05-09T00:00:00Z",
  "retention_until": "2026-05-09T00:00:00Z",
  "triggered_by": "string",
  "date_created": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Download Backup
- **Endpoint**: `GET /backups/{backup_id}/download`
---

#### Form/Action: Restore Backup
- **Endpoint**: `POST /backups/{backup_id}/restore`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: Apply Retention
- **Endpoint**: `POST /backups/retention/sweep`
**Response Body:**
```json
"string"
```
---


### 📦 Module: INTEGRATION (File: integration_routes.py)
#### Form/Action: List Integrations
- **Endpoint**: `GET /integrations/`
**Response Body:**
```json
[
  {
    "code": "string",
    "name": "string",
    "base_url": "string",
    "protocol": 0,
    "provider_type": 0,
    "direction": 0,
    "is_active": false,
    "id": 0,
    "credentials": [
      "..."
    ]
  }
]
```
---

#### Form/Action: Create Integration
- **Endpoint**: `POST /integrations/`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "base_url": "string",
  "protocol": 0,
  "provider_type": 0,
  "direction": 0,
  "is_active": false,
  "credentials": [
    {
      "credential_type": "...",
      "secret_reference": "..."
    }
  ]
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "base_url": "string",
  "protocol": 0,
  "provider_type": 0,
  "direction": 0,
  "is_active": false,
  "id": 0,
  "credentials": [
    {
      "credential_type": "...",
      "secret_reference": "...",
      "id": "..."
    }
  ]
}
```
---

#### Form/Action: Get Integration
- **Endpoint**: `GET /integrations/{endpoint_id}`
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "base_url": "string",
  "protocol": 0,
  "provider_type": 0,
  "direction": 0,
  "is_active": false,
  "id": 0,
  "credentials": [
    {
      "credential_type": "...",
      "secret_reference": "...",
      "id": "..."
    }
  ]
}
```
---

#### Form/Action: Update Integration
- **Endpoint**: `PUT /integrations/{endpoint_id}`
**Request Payload:**
```json
{
  "name": "string",
  "base_url": "string",
  "protocol": 0,
  "provider_type": 0,
  "direction": 0,
  "is_active": false
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "base_url": "string",
  "protocol": 0,
  "provider_type": 0,
  "direction": 0,
  "is_active": false,
  "id": 0,
  "credentials": [
    {
      "credential_type": "...",
      "secret_reference": "...",
      "id": "..."
    }
  ]
}
```
---

#### Form/Action: Delete Integration
- **Endpoint**: `DELETE /integrations/{endpoint_id}`
---


### 📦 Module: TEMPLATE (File: template_routes.py)
#### Form/Action: List Notification Templates
- **Endpoint**: `GET /templates/notifications`
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "channel": "string",
    "subject_template": "string",
    "body_template": "string",
    "id": 0
  }
]
```
---

#### Form/Action: Create Notification Template
- **Endpoint**: `POST /templates/notifications`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "channel": "string",
  "subject_template": "string",
  "body_template": "string"
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "channel": "string",
  "subject_template": "string",
  "body_template": "string",
  "id": 0
}
```
---

#### Form/Action: List Document Templates
- **Endpoint**: `GET /templates/documents`
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "template_type": "string",
    "body_html": "string",
    "is_default": false,
    "id": 0
  }
]
```
---

#### Form/Action: Create Document Template
- **Endpoint**: `POST /templates/documents`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "template_type": "string",
  "body_html": "string",
  "is_default": false
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "template_type": "string",
  "body_html": "string",
  "is_default": false,
  "id": 0
}
```
---


### 📦 Module: REPORT (File: report_routes.py)
#### Form/Action: Get Financial Summary
- **Endpoint**: `GET /reports/financial-summary`
**Response Body:**
```json
{
  "total_revenue": 0.0,
  "total_invoiced": 0.0,
  "total_paid": 0.0,
  "currency": "string"
}
```
---

#### Form/Action: Get Operational Summary
- **Endpoint**: `GET /reports/operational-summary`
**Response Body:**
```json
{
  "total_patients": 0,
  "total_active_visits": 0,
  "total_admissions": 0,
  "total_staff": 0
}
```
---

#### Form/Action: Get Platform Overview
- **Endpoint**: `GET /reports/platform-overview`
**Response Body:**
```json
{
  "total_tenants": 0,
  "active_tenants": 0,
  "total_revenue_platform": 0.0,
  "total_api_calls": 0,
  "system_health_status": "string"
}
```
---


### 📦 Module: SAAS_ADMIN_PORTAL (File: saas_admin_portal_routes.py)
#### Form/Action: Get System Health
- **Endpoint**: `GET /saas/admin/health`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Sync Tenant Migrations
- **Endpoint**: `POST /saas/admin/migrations/sync`
**Response Body:**
```json
"string"
```
---


### 📦 Module: USER (File: user_routes.py)
#### Form/Action: List Users
- **Endpoint**: `GET /users`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create User
- **Endpoint**: `POST /users`
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "password": "string",
  "role_ids": 0,
  "staff_profile": {
    "department_id": 0,
    "service_delivery_point_id": 0,
    "facility_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string"
  }
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Invite User
- **Endpoint**: `POST /users/invite`
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "role_ids": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Get User
- **Endpoint**: `GET /users/{user_id}`
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": "string",
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Update User
- **Endpoint**: `PUT /users/{user_id}`
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "status": "string",
  "staff_profile": {
    "department_id": 0,
    "service_delivery_point_id": 0,
    "facility_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string"
  }
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Update User Status
- **Endpoint**: `PUT /users/{user_id}/status`
**Request Payload:**
```json
{
  "status": "string",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Unlock User
- **Endpoint**: `POST /users/{user_id}/unlock`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Lock User
- **Endpoint**: `POST /users/{user_id}/lock`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Deactivate User
- **Endpoint**: `POST /users/{user_id}/deactivate`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Reactivate User
- **Endpoint**: `POST /users/{user_id}/reactivate`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Assign Roles
- **Endpoint**: `POST /users/{user_id}/roles`
**Request Payload:**
```json
{
  "role_ids": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Revoke Roles
- **Endpoint**: `DELETE /users/{user_id}/roles`
**Request Payload:**
```json
{
  "role_ids": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Force Password Reset
- **Endpoint**: `POST /users/{user_id}/password-reset`
**Request Payload:**
```json
{
  "new_password": "string",
  "require_change_on_next_login": false,
  "revoke_active_sessions": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: List User Sessions
- **Endpoint**: `GET /users/{user_id}/sessions`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "sessions": "string"
}
```
---

#### Form/Action: Revoke All Sessions
- **Endpoint**: `POST /users/{user_id}/revoke-sessions`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "roles": "string",
    "staff_profile": {
      "id": "...",
      "user_id": "...",
      "department_id": "...",
      "service_delivery_point_id": "...",
      "staff_no": "...",
      "job_title": "...",
      "professional_license_no": "...",
      "specialty": "...",
      "facility_id": "...",
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```
---

#### Form/Action: Delete User
- **Endpoint**: `DELETE /users/{user_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user_id": 0
}
```
---


### 📦 Module: STAFF (File: staff_routes.py)
#### Form/Action: Create Staff
- **Endpoint**: `POST /staff/`
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "password": "string",
  "role_ids": 0,
  "staff_profile": {
    "department_id": 0,
    "service_delivery_point_id": 0,
    "facility_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string"
  }
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": "string",
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: List Staff
- **Endpoint**: `GET /staff/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Staff
- **Endpoint**: `GET /staff/{user_id}`
**Response Body:**
```json
{
  "Includes": "string",
  "id": 0,
  "user_id": 0,
  "department_id": 0,
  "service_delivery_point_id": 0,
  "facility_id": 0,
  "staff_no": "string",
  "job_title": "string",
  "professional_license_no": "string",
  "specialty": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "user": {
    "id": 0,
    "username": "string",
    "email": "string",
    "phone_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "status": "string",
    "is_superuser": false,
    "is_two_factor_enabled": false,
    "is_email_verified": false,
    "is_phone_verified": false,
    "last_login_at": "2026-05-09T00:00:00Z",
    "password_changed_at": "2026-05-09T00:00:00Z",
    "failed_login_attempts": 0,
    "locked_until": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "department": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string"
  },
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "roles": "string"
}
```
---

#### Form/Action: Update Staff
- **Endpoint**: `PATCH /staff/{user_id}`
**Request Payload:**
```json
{
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "status": "string",
  "staff_profile": {
    "department_id": 0,
    "service_delivery_point_id": 0,
    "facility_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string"
  }
}
```
**Response Body:**
```json
{
  "id": 0,
  "username": "string",
  "email": "string",
  "phone_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "status": "string",
  "is_superuser": false,
  "is_two_factor_enabled": false,
  "is_email_verified": false,
  "is_phone_verified": false,
  "last_login_at": "2026-05-09T00:00:00Z",
  "password_changed_at": "2026-05-09T00:00:00Z",
  "failed_login_attempts": 0,
  "locked_until": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "roles": "string",
  "staff_profile": {
    "id": 0,
    "user_id": 0,
    "department_id": 0,
    "service_delivery_point_id": 0,
    "staff_no": "string",
    "job_title": "string",
    "professional_license_no": "string",
    "specialty": "string",
    "facility_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Delete Staff Profile
- **Endpoint**: `DELETE /staff/{staff_profile_id}`
---


### 📦 Module: TWO_FACTOR (File: two_factor_routes.py)
#### Form/Action: List Challenges
- **Endpoint**: `GET /two-factor/challenges`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Challenge
- **Endpoint**: `GET /two-factor/challenges/{challenge_id}`
**Response Body:**
```json
{
  "id": 0,
  "user_id": 0,
  "challenge_type": "string",
  "purpose": "string",
  "destination": "string",
  "attempt_count": 0,
  "max_attempts": 0,
  "is_verified": false,
  "verified_at": "2026-05-09T00:00:00Z",
  "expires_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Expire Challenge
- **Endpoint**: `POST /two-factor/challenges/{challenge_id}/expire`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "challenge": {
    "id": 0,
    "user_id": 0,
    "challenge_type": "string",
    "purpose": "string",
    "destination": "string",
    "attempt_count": 0,
    "max_attempts": 0,
    "is_verified": false,
    "verified_at": "2026-05-09T00:00:00Z",
    "expires_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Expire Open Challenges For User
- **Endpoint**: `POST /two-factor/users/{user_id}/expire-open-challenges`
---

#### Form/Action: Update User Policy
- **Endpoint**: `POST /two-factor/users/{user_id}/policy`
**Request Payload:**
```json
{
  "enable_two_factor": false,
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "user_id": 0,
  "is_two_factor_enabled": false
}
```
---


### 📦 Module: DEPARTMENT (File: department_routes.py)
#### Form/Action: Create Department
- **Endpoint**: `POST /departments/`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false,
  "id": 0,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: List Departments
- **Endpoint**: `GET /departments/`
**Response Body:**
```json
{
  "success": false,
  "items": "string",
  "count": 0
}
```
---

#### Form/Action: Get Department
- **Endpoint**: `GET /departments/{department_id}`
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false,
  "id": 0,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Department
- **Endpoint**: `PATCH /departments/{department_id}`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "is_active": false,
  "id": 0,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Delete Department
- **Endpoint**: `DELETE /departments/{department_id}`
---


### 📦 Module: SERVICE_DELIVERY_POINT (File: service_delivery_point_routes.py)
#### Form/Action: Create Service Delivery Point
- **Endpoint**: `POST /service-delivery-points/`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: List Service Delivery Points
- **Endpoint**: `GET /service-delivery-points/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List Active Service Delivery Points
- **Endpoint**: `GET /service-delivery-points/active`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Service Delivery Point By Code
- **Endpoint**: `GET /service-delivery-points/by-code/{code}`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Get Service Delivery Point
- **Endpoint**: `GET /service-delivery-points/{service_delivery_point_id}`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Service Delivery Point
- **Endpoint**: `PUT /service-delivery-points/{service_delivery_point_id}`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Set Service Delivery Point Status
- **Endpoint**: `PATCH /service-delivery-points/{service_delivery_point_id}/status`
**Request Payload:**
```json
{
  "is_active": false
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "service_point_type": "string",
  "department_id": 0,
  "location_description": "string",
  "queue_prefix": "string",
  "supports_appointments": false,
  "supports_walk_in": false,
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Delete Service Delivery Point
- **Endpoint**: `DELETE /service-delivery-points/{service_delivery_point_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---


### 📦 Module: FACILITY (File: facility_routes.py)
#### Form/Action: List Facilities
- **Endpoint**: `GET /facilities`
**Response Body:**
```json
[
  {
    "code": "string",
    "name": "string",
    "facility_type": "string",
    "status": "string",
    "phone_number": "string",
    "email": "string",
    "website": "string",
    "address_line_1": "string",
    "address_line_2": "string",
    "city": "string",
    "state": "string",
    "country": "string",
    "postal_code": "string",
    "timezone": "string",
    "id": 0,
    "network_id": 0,
    "parent_facility_id": 0,
    "network": {
      "name": "...",
      "code": "...",
      "description": "...",
      "id": "...",
      "head_office_facility_id": "..."
    },
    "service_areas": [
      "..."
    ]
  }
]
```
---

#### Form/Action: Get Facility
- **Endpoint**: `GET /facilities/{facility_id}`
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "facility_type": "string",
  "status": "string",
  "phone_number": "string",
  "email": "string",
  "website": "string",
  "address_line_1": "string",
  "address_line_2": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "postal_code": "string",
  "timezone": "string",
  "id": 0,
  "network_id": 0,
  "parent_facility_id": 0,
  "network": {
    "name": "string",
    "code": "string",
    "description": "string",
    "id": 0,
    "head_office_facility_id": 0
  },
  "service_areas": [
    {
      "area_name": "...",
      "region_code": "...",
      "notes": "...",
      "id": "...",
      "facility_id": "..."
    }
  ]
}
```
---

#### Form/Action: Create Facility
- **Endpoint**: `POST /facilities`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "facility_type": "string",
  "status": "string",
  "phone_number": "string",
  "email": "string",
  "website": "string",
  "address_line_1": "string",
  "address_line_2": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "postal_code": "string",
  "timezone": "string",
  "network_id": 0,
  "parent_facility_id": 0
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "facility_type": "string",
  "status": "string",
  "phone_number": "string",
  "email": "string",
  "website": "string",
  "address_line_1": "string",
  "address_line_2": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "postal_code": "string",
  "timezone": "string",
  "id": 0,
  "network_id": 0,
  "parent_facility_id": 0,
  "network": {
    "name": "string",
    "code": "string",
    "description": "string",
    "id": 0,
    "head_office_facility_id": 0
  },
  "service_areas": [
    {
      "area_name": "...",
      "region_code": "...",
      "notes": "...",
      "id": "...",
      "facility_id": "..."
    }
  ]
}
```
---

#### Form/Action: Update Facility
- **Endpoint**: `PUT /facilities/{facility_id}`
**Request Payload:**
```json
{
  "name": "string",
  "status": "string",
  "phone_number": "string",
  "email": "string",
  "address_line_1": "string",
  "city": "string",
  "state": "string",
  "network_id": 0,
  "parent_facility_id": 0
}
```
**Response Body:**
```json
{
  "code": "string",
  "name": "string",
  "facility_type": "string",
  "status": "string",
  "phone_number": "string",
  "email": "string",
  "website": "string",
  "address_line_1": "string",
  "address_line_2": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "postal_code": "string",
  "timezone": "string",
  "id": 0,
  "network_id": 0,
  "parent_facility_id": 0,
  "network": {
    "name": "string",
    "code": "string",
    "description": "string",
    "id": 0,
    "head_office_facility_id": 0
  },
  "service_areas": [
    {
      "area_name": "...",
      "region_code": "...",
      "notes": "...",
      "id": "...",
      "facility_id": "..."
    }
  ]
}
```
---

#### Form/Action: Delete Facility
- **Endpoint**: `DELETE /facilities/{facility_id}`
---

#### Form/Action: List Networks
- **Endpoint**: `GET /facilities/networks/all`
**Response Body:**
```json
[
  {
    "name": "string",
    "code": "string",
    "description": "string",
    "id": 0,
    "head_office_facility_id": 0
  }
]
```
---

#### Form/Action: Create Network
- **Endpoint**: `POST /facilities/networks/create`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "head_office_facility_id": 0
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "id": 0,
  "head_office_facility_id": 0
}
```
---

#### Form/Action: Update Network
- **Endpoint**: `PUT /facilities/networks/{network_id}`
**Request Payload:**
```json
{
  "name": "string",
  "description": "string",
  "head_office_facility_id": 0
}
```
**Response Body:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string",
  "id": 0,
  "head_office_facility_id": 0
}
```
---

#### Form/Action: Delete Network
- **Endpoint**: `DELETE /facilities/networks/{network_id}`
---

#### Form/Action: List Service Areas
- **Endpoint**: `GET /facilities/service-areas/all`
**Response Body:**
```json
[
  {
    "area_name": "string",
    "region_code": "string",
    "notes": "string",
    "id": 0,
    "facility_id": 0
  }
]
```
---

#### Form/Action: Create Service Area
- **Endpoint**: `POST /facilities/service-areas/create`
**Request Payload:**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string",
  "facility_id": 0
}
```
**Response Body:**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string",
  "id": 0,
  "facility_id": 0
}
```
---

#### Form/Action: Update Service Area
- **Endpoint**: `PUT /facilities/service-areas/{area_id}`
**Request Payload:**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "area_name": "string",
  "region_code": "string",
  "notes": "string",
  "id": 0,
  "facility_id": 0
}
```
---

#### Form/Action: Delete Service Area
- **Endpoint**: `DELETE /facilities/service-areas/{area_id}`
---


### 📦 Module: WARD (File: ward_routes.py)
#### Form/Action: Create Ward
- **Endpoint**: `POST /wards/`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string",
  "Args": "string",
  "Returns": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: List Wards
- **Endpoint**: `GET /wards/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Ward
- **Endpoint**: `GET /wards/{ward_id}`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Get Detailed Ward
- **Endpoint**: `GET /wards/{ward_id}/summary`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "total_beds": 0,
  "available_beds": 0,
  "occupied_beds": 0,
  "total_admissions": 0,
  "active_admissions": 0
}
```
---

#### Form/Action: Update Ward
- **Endpoint**: `PUT /wards/{ward_id}`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "ward_type": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Delete Ward
- **Endpoint**: `DELETE /wards/{ward_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---


### 📦 Module: BED (File: bed_routes.py)
#### Form/Action: Create Bed
- **Endpoint**: `POST /beds/`
**Request Payload:**
```json
{
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: List Beds
- **Endpoint**: `GET /beds/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Bed
- **Endpoint**: `GET /beds/{bed_id}`
**Response Body:**
```json
{
  "id": 0,
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Get Detailed Bed
- **Endpoint**: `GET /beds/{bed_id}/summary`
**Response Body:**
```json
{
  "id": 0,
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "ward": {
    "id": 0,
    "name": "string",
    "code": "string",
    "ward_type": "string",
    "description": "string"
  },
  "admission_count": 0,
  "has_active_admission": false
}
```
---

#### Form/Action: Update Bed
- **Endpoint**: `PUT /beds/{bed_id}`
**Request Payload:**
```json
{
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "ward_id": 0,
  "bed_no": "string",
  "bed_status": "string",
  "bed_type": "string",
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Delete Bed
- **Endpoint**: `DELETE /beds/{bed_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---


### 📦 Module: PATIENT (File: patient_routes.py)
#### Form/Action: Create Patient
- **Endpoint**: `POST /patients/`
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string",
  "hospital_number": "string",
  "registration_notes": "string",
  "previous_identifiers": "string",
  "insurance_enrollment": {
    "insurance_provider_id": 0,
    "policy_number": "string",
    "member_id": "string",
    "plan_name": "string",
    "coverage_details": "string",
    "status": "string",
    "valid_from": "2026-05-09T00:00:00Z",
    "valid_to": "2026-05-09T00:00:00Z",
    "note": "string"
  },
  "loyalty_enrollment": {
    "loyalty_program_id": 0,
    "membership_no": "string",
    "points_balance": 0.0,
    "joined_date": "2026-05-09T00:00:00Z",
    "note": "string"
  }
}
```
**Response Body:**
```json
{
  "success": false,
  "patient_id": 0,
  "hospital_number": "string",
  "registration_id": 0,
  "insurance_record_id": 0,
  "loyalty_membership_id": 0,
  "message": "string"
}
```
---

#### Form/Action: Check For Possible Duplicates
- **Endpoint**: `POST /patients/duplicate-check`
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "phone_number": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "national_identifier": "string",
  "previous_record_identifiers": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "possible_duplicate_found": false,
  "candidates": "2026-05-09T00:00:00Z",
  "message": "string"
}
```
---

#### Form/Action: Resolve Duplicate Review
- **Endpoint**: `POST /patients/duplicate-review/resolve`
**Request Payload:**
```json
{
  "decision": "string",
  "existing_patient_id": 0,
  "review_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "decision": "string",
  "patient_id": 0,
  "message": "string"
}
```
---

#### Form/Action: Get Link Existing Result
- **Endpoint**: `POST /patients/{patient_id}/link-existing-result`
**Response Body:**
```json
{
  "success": false,
  "patient_id": 0,
  "hospital_number": "string",
  "message": "string"
}
```
---

#### Form/Action: Attach Patient Insurance Later
- **Endpoint**: `POST /patients/{patient_id}/attach-insurance-later`
**Request Payload:**
```json
{
  "insurance_enrollment": {
    "insurance_provider_id": 0,
    "policy_number": "string",
    "member_id": "string",
    "plan_name": "string",
    "coverage_details": "string",
    "status": "string",
    "valid_from": "2026-05-09T00:00:00Z",
    "valid_to": "2026-05-09T00:00:00Z",
    "note": "string"
  }
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "insurance_provider_id": 0,
  "policy_number": "string",
  "member_id": "string",
  "plan_name": "string",
  "coverage_details": "string",
  "status": "string",
  "valid_from": "2026-05-09T00:00:00Z",
  "valid_to": "2026-05-09T00:00:00Z",
  "note": "string",
  "insurance_provider": {
    "id": 0,
    "name": "string",
    "code": "string",
    "phone_number": "string",
    "email": "string"
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: List Patients
- **Endpoint**: `GET /patients/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Search Patients
- **Endpoint**: `GET /patients/search`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Patient By Hospital Number
- **Endpoint**: `GET /patients/by-hospital-number/{hospital_number}`
**Response Body:**
```json
{
  "id": 0,
  "global_patient_id": "string",
  "hospital_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "preferred_payer": {
    "id": 0,
    "name": "string",
    "code": "string",
    "payer_type": "string",
    "phone_number": "string",
    "email": "string"
  },
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string",
  "photo": {
    "file_name": "string",
    "file_key": "string",
    "file_url": "string"
  },
  "registrations": "string",
  "identifiers": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Get Patient
- **Endpoint**: `GET /patients/{patient_id}`
**Response Body:**
```json
{
  "id": 0,
  "global_patient_id": "string",
  "hospital_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "preferred_payer": {
    "id": 0,
    "name": "string",
    "code": "string",
    "payer_type": "string",
    "phone_number": "string",
    "email": "string"
  },
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string",
  "photo": {
    "file_name": "string",
    "file_key": "string",
    "file_url": "string"
  },
  "registrations": "string",
  "identifiers": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Get Detailed Patient
- **Endpoint**: `GET /patients/{patient_id}/detailed`
**Response Body:**
```json
{
  "id": 0,
  "global_patient_id": "string",
  "hospital_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "preferred_payer": {
    "id": 0,
    "name": "string",
    "code": "string",
    "payer_type": "string",
    "phone_number": "string",
    "email": "string"
  },
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string",
  "photo": {
    "file_name": "string",
    "file_key": "string",
    "file_url": "string"
  },
  "registrations": "string",
  "identifiers": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "insurance_records": "string",
  "loyalty_memberships": "string",
  "document_attachments": "string",
  "consent_records": "string",
  "scanned_forms": "string",
  "demographic_audits": "string"
}
```
---

#### Form/Action: Update Patient
- **Endpoint**: `PUT /patients/{patient_id}`
**Request Payload:**
```json
{
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "global_patient_id": "string",
  "hospital_number": "string",
  "first_name": "string",
  "last_name": "string",
  "middle_name": "string",
  "date_of_birth": "2026-05-09T00:00:00Z",
  "gender": "string",
  "marital_status": "string",
  "phone_number": "string",
  "alternate_phone_number": "string",
  "email": "string",
  "address": "string",
  "city": "string",
  "state": "string",
  "country": "string",
  "blood_group": "string",
  "genotype": "string",
  "allergies": "string",
  "emergency_contact_name": "string",
  "emergency_contact_phone": "string",
  "emergency_contact_relationship": "string",
  "next_of_kin_name": "string",
  "next_of_kin_phone": "string",
  "next_of_kin_relationship": "string",
  "next_of_kin_address": "string",
  "patient_type": "string",
  "preferred_payer_id": 0,
  "payer_type": "string",
  "preferred_payer": {
    "id": 0,
    "name": "string",
    "code": "string",
    "payer_type": "string",
    "phone_number": "string",
    "email": "string"
  },
  "national_identifier": "string",
  "national_identifier_type": "string",
  "identification_details": "string",
  "photo": {
    "file_name": "string",
    "file_key": "string",
    "file_url": "string"
  },
  "registrations": "string",
  "identifiers": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "insurance_records": "string",
  "loyalty_memberships": "string",
  "document_attachments": "string",
  "consent_records": "string",
  "scanned_forms": "string",
  "demographic_audits": "string"
}
```
---

#### Form/Action: Add Patient Identifier
- **Endpoint**: `POST /patients/{patient_id}/identifiers`
**Request Payload:**
```json
{
  "identifier_type": "string",
  "identifier_value": "string",
  "issuing_authority": "string",
  "is_primary": false,
  "is_active": false,
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "identifier_type": "string",
  "identifier_value": "string",
  "issuing_authority": "string",
  "is_primary": false,
  "is_active": false,
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Create Patient Consent Record
- **Endpoint**: `POST /patients/{patient_id}/photo`
**Request Payload:**
```json
{
  "consent_type": "string",
  "consent_status": "string",
  "consent_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "document_file_name": "string",
  "document_file_key": "string",
  "document_file_url": "string",
  "note": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "uploaded_by_id": 0,
  "attachment_type": "string",
  "title": "string",
  "file_name": "string",
  "file_key": "string",
  "file_url": "string",
  "content_type": "string",
  "checksum": "string",
  "is_primary": false,
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Delete Patient
- **Endpoint**: `DELETE /patients/{patient_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---


### 📦 Module: PATIENT_REGISTRATION (File: patient_registration_routes.py)
#### Form/Action: Initiate Visit
- **Endpoint**: `POST /patient-registration/initiate-visit`
**Request Payload:**
```json
{
  "existing_patient": {
    "hospital_number": "string",
    "national_identifier": "string",
    "phone_number": "string",
    "email": "string"
  },
  "new_patient": {
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "date_of_birth": "2026-05-09T00:00:00Z",
    "gender": "string",
    "marital_status": "string",
    "phone_number": "string",
    "alternate_phone_number": "string",
    "email": "string",
    "address": "string",
    "city": "string",
    "state": "string",
    "country": "string",
    "blood_group": "string",
    "genotype": "string",
    "allergies": "string",
    "emergency_contact_name": "string",
    "emergency_contact_phone": "string",
    "emergency_contact_relationship": "string",
    "next_of_kin_name": "string",
    "next_of_kin_phone": "string",
    "next_of_kin_relationship": "string",
    "next_of_kin_address": "string",
    "patient_type": "string",
    "preferred_payer_id": 0,
    "payer_type": "string",
    "national_identifier": "string",
    "national_identifier_type": "string",
    "identification_details": "string",
    "hospital_number": "string",
    "registration_notes": "string",
    "previous_identifiers": "string",
    "insurance_enrollment": {
      "insurance_provider_id": "...",
      "policy_number": "...",
      "member_id": "...",
      "plan_name": "...",
      "coverage_details": "...",
      "status": "...",
      "valid_from": "...",
      "valid_to": "...",
      "note": "..."
    },
    "loyalty_enrollment": {
      "loyalty_program_id": "...",
      "membership_no": "...",
      "points_balance": "...",
      "joined_date": "...",
      "note": "..."
    }
  },
  "options": {
    "appointment_id": 0,
    "visit_flow_template_id": 0,
    "visit_flow_template_code": "string",
    "first_service_delivery_point_id": 0,
    "use_appointment_service_point": false,
    "fast_track": false,
    "priority": "string",
    "visit_reason": "string",
    "visit_date": "2026-05-09T00:00:00Z",
    "referred_from": "string"
  },
  "admission": {
    "ward_id": 0,
    "bed_id": 0,
    "admitting_staff_id": 0,
    "admission_reason": "string",
    "expected_discharge_at": "2026-05-09T00:00:00Z",
    "admitted_at": "2026-05-09T00:00:00Z",
    "capture_first_bed_day_charge": false
  }
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "is_returning_patient": false,
  "patient_id": 0,
  "patient_hospital_number": "string",
  "visit_id": 0,
  "visit_code": "string",
  "queue_ticket_id": 0,
  "queue_number": "string",
  "queue_position": 0,
  "first_service_delivery_point_id": 0,
  "visit_flow_template_id": 0,
  "admission_id": 0,
  "admission_no": "string",
  "admission_status": "string",
  "ward_id": 0,
  "bed_id": 0,
  "bed_day_charges_captured": 0
}
```
---


### 📦 Module: VISIT (File: visit_routes.py)
#### Form/Action: Initiate Visit
- **Endpoint**: `POST /visits/initiate`
**Request Payload:**
```json
{
  "patient_id": 0,
  "appointment_id": 0,
  "visit_reason": "string",
  "referred_from": "string",
  "priority": "string",
  "status": "string",
  "first_service_delivery_point_id": 0,
  "use_appointment_service_point": false,
  "visit_flow_template_id": 0,
  "visit_date": "2026-05-09T00:00:00Z",
  "check_in_time": "2026-05-09T00:00:00Z",
  "Supports": 0,
  "create_first_flow_step": false,
  "create_queue_ticket": false,
  "first_step_status": "string",
  "first_queue_status": "string",
  "mark_visit_waiting": false,
  "fast_track": false,
  "queue_position": 0,
  "flow_step_notes": "string",
  "queue_notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "visit": {
    "id": 0,
    "patient_id": 0,
    "appointment_id": 0,
    "visit_code": "string",
    "visit_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "priority": "string",
    "first_service_delivery_point_id": 0,
    "current_service_delivery_point_id": 0,
    "referred_from": "string",
    "visit_reason": "string",
    "check_in_time": "2026-05-09T00:00:00Z",
    "check_out_time": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "Includes": "string",
    "patient": {
      "id": "...",
      "hospital_number": "...",
      "first_name": "...",
      "last_name": "...",
      "middle_name": "...",
      "gender": "...",
      "phone_number": "..."
    },
    "appointment": {
      "id": "...",
      "appointment_code": "...",
      "scheduled_start_at": "...",
      "scheduled_end_at": "...",
      "reason": "...",
      "status": "...",
      "patient_id": "...",
      "service_delivery_point_id": "...",
      "staff_profile_id": "..."
    },
    "first_service_delivery_point": {
      "id": "...",
      "name": "...",
      "code": "...",
      "service_point_type": "...",
      "department_id": "...",
      "location_description": "...",
      "queue_prefix": "...",
      "supports_appointments": "...",
      "supports_walk_in": "...",
      "is_active": "..."
    },
    "current_service_delivery_point": {
      "id": "...",
      "name": "...",
      "code": "...",
      "service_point_type": "...",
      "department_id": "...",
      "location_description": "...",
      "queue_prefix": "...",
      "supports_appointments": "...",
      "supports_walk_in": "...",
      "is_active": "..."
    },
    "flow_steps": "string",
    "queue_tickets": "string"
  },
  "first_flow_step": {
    "id": 0,
    "visit_id": 0,
    "service_delivery_point_id": 0,
    "step_order": 0,
    "status": "string",
    "is_current": false,
    "is_required": false,
    "is_skipped": false,
    "routed_by_id": 0,
    "started_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "notes": "string",
    "service_delivery_point": {
      "id": "...",
      "name": "...",
      "code": "...",
      "service_point_type": "...",
      "department_id": "...",
      "location_description": "...",
      "queue_prefix": "...",
      "supports_appointments": "...",
      "supports_walk_in": "..."
    },
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "first_queue_ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "applied_template": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "inherited_from_appointment": false,
  "fast_tracked": false
}
```
---

#### Form/Action: Reroute Visit
- **Endpoint**: `POST /visits/{visit_id}/reroute`
**Request Payload:**
```json
{
  "service_delivery_point_id": 0,
  "routed_by_id": 0,
  "reason": "string",
  "create_queue_ticket": false,
  "queue_status": "string",
  "queue_position": 0,
  "mark_as_current": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "visit": {
    "id": 0,
    "patient_id": 0,
    "appointment_id": 0,
    "visit_code": "string",
    "visit_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "priority": "string",
    "first_service_delivery_point_id": 0,
    "current_service_delivery_point_id": 0,
    "referred_from": "string",
    "visit_reason": "string",
    "check_in_time": "2026-05-09T00:00:00Z",
    "check_out_time": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z",
    "Includes": "string",
    "patient": {
      "id": "...",
      "hospital_number": "...",
      "first_name": "...",
      "last_name": "...",
      "middle_name": "...",
      "gender": "...",
      "phone_number": "..."
    },
    "appointment": {
      "id": "...",
      "appointment_code": "...",
      "scheduled_start_at": "...",
      "scheduled_end_at": "...",
      "reason": "...",
      "status": "...",
      "patient_id": "...",
      "service_delivery_point_id": "...",
      "staff_profile_id": "..."
    },
    "first_service_delivery_point": {
      "id": "...",
      "name": "...",
      "code": "...",
      "service_point_type": "...",
      "department_id": "...",
      "location_description": "...",
      "queue_prefix": "...",
      "supports_appointments": "...",
      "supports_walk_in": "...",
      "is_active": "..."
    },
    "current_service_delivery_point": {
      "id": "...",
      "name": "...",
      "code": "...",
      "service_point_type": "...",
      "department_id": "...",
      "location_description": "...",
      "queue_prefix": "...",
      "supports_appointments": "...",
      "supports_walk_in": "...",
      "is_active": "..."
    },
    "flow_steps": "string",
    "queue_tickets": "string"
  },
  "new_flow_step": {
    "id": 0,
    "visit_id": 0,
    "service_delivery_point_id": 0,
    "step_order": 0,
    "status": "string",
    "is_current": false,
    "is_required": false,
    "is_skipped": false,
    "routed_by_id": 0,
    "started_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "notes": "string",
    "service_delivery_point": {
      "id": "...",
      "name": "...",
      "code": "...",
      "service_point_type": "...",
      "department_id": "...",
      "location_description": "...",
      "queue_prefix": "...",
      "supports_appointments": "...",
      "supports_walk_in": "..."
    },
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "new_queue_ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: List Visits
- **Endpoint**: `GET /visits/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Visit
- **Endpoint**: `GET /visits/{visit_id}`
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "appointment_id": 0,
  "visit_code": "string",
  "visit_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "priority": "string",
  "first_service_delivery_point_id": 0,
  "current_service_delivery_point_id": 0,
  "referred_from": "string",
  "visit_reason": "string",
  "check_in_time": "2026-05-09T00:00:00Z",
  "check_out_time": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Get Detailed Visit
- **Endpoint**: `GET /visits/{visit_id}/detailed`
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "appointment_id": 0,
  "visit_code": "string",
  "visit_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "priority": "string",
  "first_service_delivery_point_id": 0,
  "current_service_delivery_point_id": 0,
  "referred_from": "string",
  "visit_reason": "string",
  "check_in_time": "2026-05-09T00:00:00Z",
  "check_out_time": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "Includes": "string",
  "patient": {
    "id": 0,
    "hospital_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "gender": "string",
    "phone_number": "string"
  },
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0
  },
  "first_service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "current_service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "flow_steps": "string",
  "queue_tickets": "string"
}
```
---

#### Form/Action: Update Visit
- **Endpoint**: `PUT /visits/{visit_id}`
**Request Payload:**
```json
{
  "appointment_id": 0,
  "visit_reason": "string",
  "referred_from": "string",
  "priority": "string",
  "status": "string",
  "first_service_delivery_point_id": 0,
  "current_service_delivery_point_id": 0,
  "check_in_time": "2026-05-09T00:00:00Z",
  "check_out_time": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "appointment_id": 0,
  "visit_code": "string",
  "visit_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "priority": "string",
  "first_service_delivery_point_id": 0,
  "current_service_delivery_point_id": 0,
  "referred_from": "string",
  "visit_reason": "string",
  "check_in_time": "2026-05-09T00:00:00Z",
  "check_out_time": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z",
  "Includes": "string",
  "patient": {
    "id": 0,
    "hospital_number": "string",
    "first_name": "string",
    "last_name": "string",
    "middle_name": "string",
    "gender": "string",
    "phone_number": "string"
  },
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0
  },
  "first_service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "current_service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false,
    "is_active": false
  },
  "flow_steps": "string",
  "queue_tickets": "string"
}
```
---

#### Form/Action: Delete Visit Placeholder
- **Endpoint**: `DELETE /visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---


### 📦 Module: VISIT_FLOW (File: visit_flow_routes.py)
#### Form/Action: Create Template
- **Endpoint**: `POST /visit-flows/templates`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "steps": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: List Templates
- **Endpoint**: `GET /visit-flows/templates`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Template
- **Endpoint**: `GET /visit-flows/templates/{template_id}`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "steps": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Template
- **Endpoint**: `PUT /visit-flows/templates/{template_id}`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "description": "string",
  "steps": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Delete Template
- **Endpoint**: `DELETE /visit-flows/templates/{template_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---

#### Form/Action: Create Template Step
- **Endpoint**: `POST /visit-flows/template-steps`
**Request Payload:**
```json
{
  "service_delivery_point_id": 0,
  "step_order": 0,
  "is_required": false,
  "notes": "string",
  "template_id": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "template_id": 0,
  "service_delivery_point_id": 0,
  "step_order": 0,
  "is_required": false,
  "notes": "string",
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Template Step
- **Endpoint**: `PUT /visit-flows/template-steps/{template_step_id}`
**Request Payload:**
```json
{
  "service_delivery_point_id": 0,
  "step_order": 0,
  "is_required": false,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "template_id": 0,
  "service_delivery_point_id": 0,
  "step_order": 0,
  "is_required": false,
  "notes": "string",
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Delete Template Step
- **Endpoint**: `DELETE /visit-flows/template-steps/{template_step_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---

#### Form/Action: Create Visit Step
- **Endpoint**: `POST /visit-flows/visit-steps`
**Request Payload:**
```json
{
  "Supports": "string",
  "service_delivery_point_id": 0,
  "step_order": 0,
  "status": "string",
  "is_current": false,
  "is_required": false,
  "is_skipped": false,
  "routed_by_id": 0,
  "started_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "notes": "string",
  "visit_id": 0
}
```
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "service_delivery_point_id": 0,
  "step_order": 0,
  "status": "string",
  "is_current": false,
  "is_required": false,
  "is_skipped": false,
  "routed_by_id": 0,
  "started_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "notes": "string",
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: List Visit Steps
- **Endpoint**: `GET /visit-flows/visit-steps`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Visit Step
- **Endpoint**: `GET /visit-flows/visit-steps/{visit_step_id}`
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "service_delivery_point_id": 0,
  "step_order": 0,
  "status": "string",
  "is_current": false,
  "is_required": false,
  "is_skipped": false,
  "routed_by_id": 0,
  "started_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "notes": "string",
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Visit Step
- **Endpoint**: `PUT /visit-flows/visit-steps/{visit_step_id}`
**Request Payload:**
```json
{
  "service_delivery_point_id": 0,
  "step_order": 0,
  "status": "string",
  "is_current": false,
  "is_required": false,
  "is_skipped": false,
  "routed_by_id": 0,
  "started_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "service_delivery_point_id": 0,
  "step_order": 0,
  "status": "string",
  "is_current": false,
  "is_required": false,
  "is_skipped": false,
  "routed_by_id": 0,
  "started_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "notes": "string",
  "service_delivery_point": {
    "id": 0,
    "name": "string",
    "code": "string",
    "service_point_type": "string",
    "department_id": 0,
    "location_description": "string",
    "queue_prefix": "string",
    "supports_appointments": false,
    "supports_walk_in": false
  },
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Delete Visit Step
- **Endpoint**: `DELETE /visit-flows/visit-steps/{visit_step_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string"
}
```
---

#### Form/Action: Create Combined Flow Records
- **Endpoint**: `POST /visit-flows/combined-create`
**Request Payload:**
```json
{
  "template": {
    "name": "string",
    "code": "string",
    "description": "string"
  },
  "template_steps": "string",
  "visit_id": 0,
  "visit_steps": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "template": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "steps": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "created_template_steps": "string",
  "created_visit_steps": "string"
}
```
---


### 📦 Module: QUEUE (File: queue_routes.py)
#### Form/Action: Get My Worklist
- **Endpoint**: `GET /queue/my-worklist`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "service_delivery_point_id": 0,
  "service_delivery_point_name": "string",
  "waiting": "string",
  "serving": "string",
  "served_today": 0,
  "cancelled_today": 0
}
```
---

#### Form/Action: Get Worklist
- **Endpoint**: `GET /queue/service-points/{service_delivery_point_id}/worklist`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "service_delivery_point_id": 0,
  "service_delivery_point_name": "string",
  "waiting": "string",
  "serving": "string",
  "served_today": 0,
  "cancelled_today": 0
}
```
---

#### Form/Action: List Service Point Tickets
- **Endpoint**: `GET /queue/service-points/{service_delivery_point_id}/tickets`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List Visit Tickets
- **Endpoint**: `GET /queue/visits/{visit_id}/tickets`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Ticket
- **Endpoint**: `GET /queue/tickets/{ticket_id}`
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "visit_flow_step_id": 0,
  "patient_id": 0,
  "service_delivery_point_id": 0,
  "queue_number": "string",
  "queue_position": 0,
  "status": "string",
  "called_at": "2026-05-09T00:00:00Z",
  "service_started_at": "2026-05-09T00:00:00Z",
  "service_ended_at": "2026-05-09T00:00:00Z",
  "transferred_from_ticket_id": 0,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Call Ticket
- **Endpoint**: `POST /queue/tickets/{ticket_id}/call`
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Start Serving Ticket
- **Endpoint**: `POST /queue/tickets/{ticket_id}/serve`
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Complete Ticket
- **Endpoint**: `POST /queue/tickets/{ticket_id}/complete`
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Complete And Route Ticket
- **Endpoint**: `POST /queue/tickets/{ticket_id}/complete-and-route`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Complete And End Visit Ticket
- **Endpoint**: `POST /queue/tickets/{ticket_id}/complete-and-end-visit`
**Request Payload:**
```json
"string"
```
---

#### Form/Action: Miss Ticket
- **Endpoint**: `POST /queue/tickets/{ticket_id}/miss`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Ticket
- **Endpoint**: `POST /queue/tickets/{ticket_id}/cancel`
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Transfer Ticket
- **Endpoint**: `POST /queue/tickets/{ticket_id}/transfer`
**Request Payload:**
```json
{
  "target_service_delivery_point_id": 0,
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ticket": {
    "id": 0,
    "visit_id": 0,
    "visit_flow_step_id": 0,
    "patient_id": 0,
    "service_delivery_point_id": 0,
    "queue_number": "string",
    "queue_position": 0,
    "status": "string",
    "called_at": "2026-05-09T00:00:00Z",
    "service_started_at": "2026-05-09T00:00:00Z",
    "service_ended_at": "2026-05-09T00:00:00Z",
    "transferred_from_ticket_id": 0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: MEMBERSHIP_CARD (File: membership_card_routes.py)
#### Form/Action: Create Membership Card
- **Endpoint**: `POST /membership-cards/`
**Request Payload:**
```json
{
  "card_number": "string",
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "patient_id": 0,
  "issuing_facility_id": 0,
  "initial_balance": 0.0
}
```
**Response Body:**
```json
{
  "card_number": "string",
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "id": 0,
  "patient_id": 0,
  "balance": 0.0,
  "issuing_facility_id": 0,
  "issued_by_id": 0,
  "date_issued": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Get Membership Card
- **Endpoint**: `GET /membership-cards/{card_id}`
**Response Body:**
```json
{
  "card_number": "string",
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "id": 0,
  "patient_id": 0,
  "balance": 0.0,
  "issuing_facility_id": 0,
  "issued_by_id": 0,
  "date_issued": "2026-05-09T00:00:00Z",
  "transactions": "string"
}
```
---

#### Form/Action: Get Membership Card By Number
- **Endpoint**: `GET /membership-cards/by-number/{card_number}`
**Response Body:**
```json
{
  "card_number": "string",
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "id": 0,
  "patient_id": 0,
  "balance": 0.0,
  "issuing_facility_id": 0,
  "issued_by_id": 0,
  "date_issued": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: List Patient Membership Cards
- **Endpoint**: `GET /membership-cards/patient/{patient_id}`
**Response Body:**
```json
[
  {
    "card_number": "string",
    "status": "string",
    "expiry_date": "2026-05-09T00:00:00Z",
    "id": 0,
    "patient_id": 0,
    "balance": 0.0,
    "issuing_facility_id": 0,
    "issued_by_id": 0,
    "date_issued": "2026-05-09T00:00:00Z"
  }
]
```
---

#### Form/Action: Update Membership Card
- **Endpoint**: `PATCH /membership-cards/{card_id}`
**Request Payload:**
```json
{
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "card_number": "string",
  "status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "id": 0,
  "patient_id": 0,
  "balance": 0.0,
  "issuing_facility_id": 0,
  "issued_by_id": 0,
  "date_issued": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Fund Membership Card
- **Endpoint**: `POST /membership-cards/{card_id}/fund`
**Request Payload:**
```json
{
  "amount": 0.0,
  "payment_source": "string",
  "payment_reference": "string",
  "narration": "string"
}
```
**Response Body:**
```json
{
  "amount": 0.0,
  "transaction_type": "string",
  "payment_source": "string",
  "payment_reference": "string",
  "narration": "string",
  "id": 0,
  "membership_card_id": 0,
  "patient_id": 0,
  "balance_before": 0.0,
  "balance_after": 0.0,
  "facility_id": 0,
  "processed_by_id": 0,
  "transaction_date": "2026-05-09T00:00:00Z",
  "invoice_id": 0,
  "visit_id": 0,
  "payment_id": 0
}
```
---

#### Form/Action: Debit Membership Card
- **Endpoint**: `POST /membership-cards/{card_id}/debit`
**Request Payload:**
```json
{
  "amount": 0.0,
  "invoice_id": 0,
  "visit_id": 0,
  "narration": "string"
}
```
**Response Body:**
```json
{
  "amount": 0.0,
  "transaction_type": "string",
  "payment_source": "string",
  "payment_reference": "string",
  "narration": "string",
  "id": 0,
  "membership_card_id": 0,
  "patient_id": 0,
  "balance_before": 0.0,
  "balance_after": 0.0,
  "facility_id": 0,
  "processed_by_id": 0,
  "transaction_date": "2026-05-09T00:00:00Z",
  "invoice_id": 0,
  "visit_id": 0,
  "payment_id": 0
}
```
---

#### Form/Action: List Membership Card Transactions
- **Endpoint**: `GET /membership-cards/{card_id}/transactions`
**Response Body:**
```json
[
  {
    "amount": 0.0,
    "transaction_type": "string",
    "payment_source": "string",
    "payment_reference": "string",
    "narration": "string",
    "id": 0,
    "membership_card_id": 0,
    "patient_id": 0,
    "balance_before": 0.0,
    "balance_after": 0.0,
    "facility_id": 0,
    "processed_by_id": 0,
    "transaction_date": "2026-05-09T00:00:00Z",
    "invoice_id": 0,
    "visit_id": 0,
    "payment_id": 0
  }
]
```
---


### 📦 Module: PATIENT_PORTAL (File: patient_portal_routes.py)

### 📦 Module: PAYSTACK_WEBHOOK (File: paystack_webhook_routes.py)

### 📦 Module: CLINICIAN (File: clinician_routes.py)
#### Form/Action: List Clinicians
- **Endpoint**: `GET /clinicians/`
---


### 📦 Module: TRIAGE (File: triage_routes.py)
#### Form/Action: List For Visit
- **Endpoint**: `GET /triage/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Triage
- **Endpoint**: `POST /triage/`
**Request Payload:**
```json
{
  "visit_id": 0,
  "chief_complaint": "string",
  "triage_note": "string",
  "priority": "string",
  "assessed_by_staff_id": 0,
  "update_visit_priority": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "triage": {
    "id": 0,
    "visit_id": 0,
    "assessed_by_staff_id": 0,
    "chief_complaint": "string",
    "triage_note": "string",
    "priority": "string",
    "assessed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Triage
- **Endpoint**: `GET /triage/{triage_id}`
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "assessed_by_staff_id": 0,
  "chief_complaint": "string",
  "triage_note": "string",
  "priority": "string",
  "assessed_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Triage
- **Endpoint**: `PUT /triage/{triage_id}`
**Request Payload:**
```json
{
  "chief_complaint": "string",
  "triage_note": "string",
  "priority": "string",
  "update_visit_priority": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "triage": {
    "id": 0,
    "visit_id": 0,
    "assessed_by_staff_id": 0,
    "chief_complaint": "string",
    "triage_note": "string",
    "priority": "string",
    "assessed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: VITAL_SIGN (File: vital_sign_routes.py)
#### Form/Action: List For Visit
- **Endpoint**: `GET /vital-signs/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Latest For Visit
- **Endpoint**: `GET /vital-signs/visits/{visit_id}/latest`
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "recorded_by_staff_id": 0,
  "temperature_celsius": 0.0,
  "pulse_rate": 0,
  "respiratory_rate": 0,
  "systolic_bp": 0,
  "diastolic_bp": 0,
  "oxygen_saturation": 0.0,
  "weight_kg": 0.0,
  "height_cm": 0.0,
  "bmi": 0.0,
  "pain_score": 0,
  "recorded_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Create Vitals
- **Endpoint**: `POST /vital-signs/`
**Request Payload:**
```json
{
  "visit_id": 0,
  "recorded_by_staff_id": 0,
  "temperature_celsius": 0.0,
  "pulse_rate": 0,
  "respiratory_rate": 0,
  "systolic_bp": 0,
  "diastolic_bp": 0,
  "oxygen_saturation": 0.0,
  "weight_kg": 0.0,
  "height_cm": 0.0,
  "bmi": 0.0,
  "pain_score": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "vital_sign": {
    "id": 0,
    "visit_id": 0,
    "recorded_by_staff_id": 0,
    "temperature_celsius": 0.0,
    "pulse_rate": 0,
    "respiratory_rate": 0,
    "systolic_bp": 0,
    "diastolic_bp": 0,
    "oxygen_saturation": 0.0,
    "weight_kg": 0.0,
    "height_cm": 0.0,
    "bmi": 0.0,
    "pain_score": 0,
    "recorded_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: CONSULTATION (File: consultation_routes.py)
#### Form/Action: List For Visit
- **Endpoint**: `GET /consultations/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Consultation
- **Endpoint**: `POST /consultations/`
**Request Payload:**
```json
{
  "visit_id": 0,
  "clinician_staff_id": 0,
  "subjective_note": "string",
  "objective_note": "string",
  "assessment_note": "string",
  "plan_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "consultation": {
    "id": 0,
    "visit_id": 0,
    "clinician_staff_id": 0,
    "status": "string",
    "subjective_note": "string",
    "objective_note": "string",
    "assessment_note": "string",
    "plan_note": "string",
    "consultation_started_at": "2026-05-09T00:00:00Z",
    "consultation_ended_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Consultation
- **Endpoint**: `GET /consultations/{consultation_id}`
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "clinician_staff_id": 0,
  "status": "string",
  "subjective_note": "string",
  "objective_note": "string",
  "assessment_note": "string",
  "plan_note": "string",
  "consultation_started_at": "2026-05-09T00:00:00Z",
  "consultation_ended_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Consultation
- **Endpoint**: `PUT /consultations/{consultation_id}`
**Request Payload:**
```json
{
  "subjective_note": "string",
  "objective_note": "string",
  "assessment_note": "string",
  "plan_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "consultation": {
    "id": 0,
    "visit_id": 0,
    "clinician_staff_id": 0,
    "status": "string",
    "subjective_note": "string",
    "objective_note": "string",
    "assessment_note": "string",
    "plan_note": "string",
    "consultation_started_at": "2026-05-09T00:00:00Z",
    "consultation_ended_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Finalize Consultation
- **Endpoint**: `POST /consultations/{consultation_id}/finalize`
**Request Payload:**
```json
{
  "next_service_delivery_point_id": 0,
  "end_visit": false,
  "closing_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "consultation": {
    "id": 0,
    "visit_id": 0,
    "clinician_staff_id": 0,
    "status": "string",
    "subjective_note": "string",
    "objective_note": "string",
    "assessment_note": "string",
    "plan_note": "string",
    "consultation_started_at": "2026-05-09T00:00:00Z",
    "consultation_ended_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Consultation
- **Endpoint**: `POST /consultations/{consultation_id}/cancel`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "consultation": {
    "id": 0,
    "visit_id": 0,
    "clinician_staff_id": 0,
    "status": "string",
    "subjective_note": "string",
    "objective_note": "string",
    "assessment_note": "string",
    "plan_note": "string",
    "consultation_started_at": "2026-05-09T00:00:00Z",
    "consultation_ended_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: DIAGNOSIS (File: diagnosis_routes.py)
#### Form/Action: List For Visit
- **Endpoint**: `GET /diagnoses/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Diagnosis
- **Endpoint**: `POST /diagnoses/`
**Request Payload:**
```json
{
  "visit_id": 0,
  "consultation_id": 0,
  "diagnosis_name": "string",
  "diagnosis_code": "string",
  "diagnosis_type": "string",
  "diagnosis_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "diagnosis": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "diagnosis_code": "string",
    "diagnosis_name": "string",
    "diagnosis_type": "string",
    "diagnosis_note": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Diagnosis
- **Endpoint**: `GET /diagnoses/{diagnosis_id}`
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "consultation_id": 0,
  "diagnosis_code": "string",
  "diagnosis_name": "string",
  "diagnosis_type": "string",
  "diagnosis_note": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Diagnosis
- **Endpoint**: `PUT /diagnoses/{diagnosis_id}`
**Request Payload:**
```json
{
  "diagnosis_name": "string",
  "diagnosis_code": "string",
  "diagnosis_type": "string",
  "diagnosis_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "diagnosis": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "diagnosis_code": "string",
    "diagnosis_name": "string",
    "diagnosis_type": "string",
    "diagnosis_note": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: REFERRAL (File: referral_routes.py)
#### Form/Action: List Referrals
- **Endpoint**: `GET /referrals/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0
}
```
---

#### Form/Action: Get Referral
- **Endpoint**: `GET /referrals/{referral_id}`
**Response Body:**
```json
{
  "id": 0,
  "referral_no": "string",
  "patient_id": 0,
  "visit_id": 0,
  "referring_staff_id": 0,
  "destination_facility": "string",
  "reason_for_referral": "string",
  "clinical_summary": "string",
  "referral_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "priority": "string",
  "date_created": "2026-05-09T00:00:00Z",
  "date_updated": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Create Referral
- **Endpoint**: `POST /referrals/`
**Request Payload:**
```json
{
  "patient_id": 0,
  "visit_id": 0,
  "destination_facility": "string",
  "reason_for_referral": "string",
  "clinical_summary": "string",
  "referral_date": "2026-05-09T00:00:00Z",
  "priority": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "referral": {
    "id": 0,
    "referral_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "referring_staff_id": 0,
    "destination_facility": "string",
    "reason_for_referral": "string",
    "clinical_summary": "string",
    "referral_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "priority": "string",
    "date_created": "2026-05-09T00:00:00Z",
    "date_updated": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Update Referral
- **Endpoint**: `PATCH /referrals/{referral_id}`
**Request Payload:**
```json
{
  "destination_facility": "string",
  "reason_for_referral": "string",
  "clinical_summary": "string",
  "status": "string",
  "priority": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "referral": {
    "id": 0,
    "referral_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "referring_staff_id": 0,
    "destination_facility": "string",
    "reason_for_referral": "string",
    "clinical_summary": "string",
    "referral_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "priority": "string",
    "date_created": "2026-05-09T00:00:00Z",
    "date_updated": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Referral
- **Endpoint**: `POST /referrals/{referral_id}/cancel`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "referral": {
    "id": 0,
    "referral_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "referring_staff_id": 0,
    "destination_facility": "string",
    "reason_for_referral": "string",
    "clinical_summary": "string",
    "referral_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "priority": "string",
    "date_created": "2026-05-09T00:00:00Z",
    "date_updated": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Create Inter Facility Referral
- **Endpoint**: `POST /referrals/inter-facility`
**Request Payload:**
```json
{
  "target_tenant_id": 0,
  "target_facility_id": 0,
  "patient_global_id": "string",
  "reason_for_referral": "string",
  "clinical_summary": "string",
  "referral_date": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "referral": {
    "id": 0,
    "referral_no": "string",
    "source_tenant_id": 0,
    "source_facility_id": 0,
    "target_tenant_id": 0,
    "target_facility_id": 0,
    "patient_global_id": "string",
    "reason_for_referral": "string",
    "clinical_summary": "string",
    "status": "string",
    "acceptance_note": "string",
    "declined_reason": "string",
    "referral_date": "2026-05-09T00:00:00Z",
    "responded_at": "2026-05-09T00:00:00Z",
    "is_history_access_granted": false,
    "access_expires_at": "2026-05-09T00:00:00Z",
    "date_created": "2026-05-09T00:00:00Z",
    "date_updated": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: List Incoming Referrals
- **Endpoint**: `GET /referrals/inter-facility/incoming`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0
}
```
---

#### Form/Action: Respond To Inter Facility Referral
- **Endpoint**: `POST /referrals/inter-facility/{referral_id}/respond`
**Request Payload:**
```json
{
  "status": "string",
  "note": "string",
  "access_expiry_days": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "referral": {
    "id": 0,
    "referral_no": "string",
    "source_tenant_id": 0,
    "source_facility_id": 0,
    "target_tenant_id": 0,
    "target_facility_id": 0,
    "patient_global_id": "string",
    "reason_for_referral": "string",
    "clinical_summary": "string",
    "status": "string",
    "acceptance_note": "string",
    "declined_reason": "string",
    "referral_date": "2026-05-09T00:00:00Z",
    "responded_at": "2026-05-09T00:00:00Z",
    "is_history_access_granted": false,
    "access_expires_at": "2026-05-09T00:00:00Z",
    "date_created": "2026-05-09T00:00:00Z",
    "date_updated": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: LAB (File: lab_routes.py)
#### Form/Action: List Tests
- **Endpoint**: `GET /lab/tests/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Test
- **Endpoint**: `POST /lab/tests/`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "sample_type": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_test": {
    "id": 0,
    "code": "string",
    "name": "string",
    "sample_type": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "default_price": 0.0,
    "description": "string",
    "is_active": false,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Test
- **Endpoint**: `GET /lab/tests/{test_id}`
**Response Body:**
```json
{
  "id": 0,
  "code": "string",
  "name": "string",
  "sample_type": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "default_price": 0.0,
  "description": "string",
  "is_active": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Test
- **Endpoint**: `PUT /lab/tests/{test_id}`
**Request Payload:**
```json
{
  "name": "string",
  "sample_type": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_test": {
    "id": 0,
    "code": "string",
    "name": "string",
    "sample_type": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "default_price": 0.0,
    "description": "string",
    "is_active": false,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Delete Test
- **Endpoint**: `DELETE /lab/tests/{test_id}`
---


### 📦 Module: LAB_ORDER (File: lab_order_routes.py)
#### Form/Action: List For Visit
- **Endpoint**: `GET /lab/orders/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List Worklist
- **Endpoint**: `GET /lab/orders/worklist`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Order
- **Endpoint**: `POST /lab/orders/`
**Request Payload:**
```json
{
  "visit_id": 0,
  "consultation_id": 0,
  "ordered_by_staff_id": 0,
  "clinical_note": "string",
  "items": "string",
  "auto_capture_charge": false,
  "route_to_lab_service_delivery_point_id": 0,
  "route_to_cashier_service_delivery_point_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "clinical_note": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Order
- **Endpoint**: `GET /lab/orders/{order_id}`
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "consultation_id": 0,
  "ordered_by_staff_id": 0,
  "order_no": "string",
  "status": "string",
  "clinical_note": "string",
  "ordered_at": "2026-05-09T00:00:00Z",
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Collect Specimen
- **Endpoint**: `POST /lab/orders/items/{item_id}/collect-specimen`
**Request Payload:**
```json
{
  "specimen_id": "string",
  "collected_by_staff_id": 0,
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "clinical_note": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Start Processing
- **Endpoint**: `POST /lab/orders/items/{item_id}/start-processing`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "clinical_note": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Item
- **Endpoint**: `POST /lab/orders/items/{item_id}/cancel`
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "clinical_note": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Order
- **Endpoint**: `POST /lab/orders/{order_id}/cancel`
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "lab_order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "clinical_note": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: LAB_RESULT (File: lab_result_routes.py)
#### Form/Action: Enter Result
- **Endpoint**: `POST /lab/results/`
**Request Payload:**
```json
{
  "lab_order_item_id": 0,
  "entered_by_staff_id": 0,
  "result_value": "string",
  "result_text": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "interpretation": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "result": {
    "id": 0,
    "lab_order_item_id": 0,
    "entered_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "result_status": "string",
    "result_value": "string",
    "result_text": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "interpretation": "string",
    "entered_at": "2026-05-09T00:00:00Z",
    "verified_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Update Result
- **Endpoint**: `PUT /lab/results/{result_id}`
**Request Payload:**
```json
{
  "result_value": "string",
  "result_text": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "interpretation": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "result": {
    "id": 0,
    "lab_order_item_id": 0,
    "entered_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "result_status": "string",
    "result_value": "string",
    "result_text": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "interpretation": "string",
    "entered_at": "2026-05-09T00:00:00Z",
    "verified_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Verify Result
- **Endpoint**: `POST /lab/results/{result_id}/verify`
**Request Payload:**
```json
{
  "verified_by_staff_id": 0,
  "verification_note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "result": {
    "id": 0,
    "lab_order_item_id": 0,
    "entered_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "result_status": "string",
    "result_value": "string",
    "result_text": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "interpretation": "string",
    "entered_at": "2026-05-09T00:00:00Z",
    "verified_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Release Result
- **Endpoint**: `POST /lab/results/{result_id}/release`
**Request Payload:**
```json
{
  "release_note": "string",
  "notify_clinician": false,
  "route_to_service_delivery_point_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "result": {
    "id": 0,
    "lab_order_item_id": 0,
    "entered_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "result_status": "string",
    "result_value": "string",
    "result_text": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "interpretation": "string",
    "entered_at": "2026-05-09T00:00:00Z",
    "verified_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Result
- **Endpoint**: `POST /lab/results/{result_id}/cancel`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "result": {
    "id": 0,
    "lab_order_item_id": 0,
    "entered_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "result_status": "string",
    "result_value": "string",
    "result_text": "string",
    "unit_of_measure": "string",
    "reference_range": "string",
    "interpretation": "string",
    "entered_at": "2026-05-09T00:00:00Z",
    "verified_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Result
- **Endpoint**: `GET /lab/results/{result_id}`
**Response Body:**
```json
{
  "id": 0,
  "lab_order_item_id": 0,
  "entered_by_staff_id": 0,
  "verified_by_staff_id": 0,
  "result_status": "string",
  "result_value": "string",
  "result_text": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "interpretation": "string",
  "entered_at": "2026-05-09T00:00:00Z",
  "verified_at": "2026-05-09T00:00:00Z",
  "released_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Get By Item
- **Endpoint**: `GET /lab/results/by-item/{item_id}`
**Response Body:**
```json
{
  "id": 0,
  "lab_order_item_id": 0,
  "entered_by_staff_id": 0,
  "verified_by_staff_id": 0,
  "result_status": "string",
  "result_value": "string",
  "result_text": "string",
  "unit_of_measure": "string",
  "reference_range": "string",
  "interpretation": "string",
  "entered_at": "2026-05-09T00:00:00Z",
  "verified_at": "2026-05-09T00:00:00Z",
  "released_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: DRUG (File: drug_routes.py)
#### Form/Action: List Categories
- **Endpoint**: `GET /drugs/categories`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Category
- **Endpoint**: `POST /drugs/categories`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "category": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Update Category
- **Endpoint**: `PUT /drugs/categories/{cat_id}`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "category": {
    "id": 0,
    "name": "string",
    "code": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Delete Category
- **Endpoint**: `DELETE /drugs/categories/{cat_id}`
---

#### Form/Action: List Drugs
- **Endpoint**: `GET /drugs/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Drug
- **Endpoint**: `POST /drugs/`
**Request Payload:**
```json
{
  "name": "string",
  "generic_name": "string",
  "brand_name": "string",
  "strength": "string",
  "dosage_form": "string",
  "pack_size": "string",
  "sku": "string",
  "drug_category_id": 0,
  "unit_price": 0.0,
  "reorder_level": 0.0,
  "is_controlled": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "drug": {
    "id": 0,
    "name": "string",
    "generic_name": "string",
    "brand_name": "string",
    "strength": "string",
    "dosage_form": "string",
    "pack_size": "string",
    "sku": "string",
    "drug_category_id": 0,
    "unit_price": 0.0,
    "reorder_level": 0.0,
    "is_controlled": false,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Drug
- **Endpoint**: `GET /drugs/{drug_id}`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "generic_name": "string",
  "brand_name": "string",
  "strength": "string",
  "dosage_form": "string",
  "pack_size": "string",
  "sku": "string",
  "drug_category_id": 0,
  "unit_price": 0.0,
  "reorder_level": 0.0,
  "is_controlled": false,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Drug
- **Endpoint**: `PUT /drugs/{drug_id}`
**Request Payload:**
```json
{
  "name": "string",
  "generic_name": "string",
  "brand_name": "string",
  "strength": "string",
  "dosage_form": "string",
  "pack_size": "string",
  "sku": "string",
  "drug_category_id": 0,
  "unit_price": 0.0,
  "reorder_level": 0.0,
  "is_controlled": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "drug": {
    "id": 0,
    "name": "string",
    "generic_name": "string",
    "brand_name": "string",
    "strength": "string",
    "dosage_form": "string",
    "pack_size": "string",
    "sku": "string",
    "drug_category_id": 0,
    "unit_price": 0.0,
    "reorder_level": 0.0,
    "is_controlled": false,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Delete Drug
- **Endpoint**: `DELETE /drugs/{drug_id}`
---


### 📦 Module: INVENTORY (File: inventory_routes.py)
#### Form/Action: List Stores
- **Endpoint**: `GET /inventory/stores`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Store
- **Endpoint**: `POST /inventory/stores`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "location_description": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "store": {
    "id": 0,
    "name": "string",
    "code": "string",
    "location_description": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Store
- **Endpoint**: `GET /inventory/stores/{store_id}`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "location_description": "string",
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Store
- **Endpoint**: `PUT /inventory/stores/{store_id}`
**Request Payload:**
```json
{
  "name": "string",
  "location_description": "string",
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "store": {
    "id": 0,
    "name": "string",
    "code": "string",
    "location_description": "string",
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Delete Store
- **Endpoint**: `DELETE /inventory/stores/{store_id}`
---

#### Form/Action: List Items
- **Endpoint**: `GET /inventory/items`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Item
- **Endpoint**: `POST /inventory/items`
**Request Payload:**
```json
{
  "store_id": 0,
  "drug_id": 0,
  "item_type": "string",
  "item_name": "string",
  "sku": "string",
  "unit_of_measure": "string",
  "quantity_on_hand": 0.0,
  "reorder_level": 0.0,
  "unit_cost": 0.0,
  "expiry_date": "2026-05-09T00:00:00Z",
  "batch_no": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "stock_item": {
    "id": 0,
    "store_id": 0,
    "drug_id": 0,
    "item_type": "string",
    "item_name": "string",
    "sku": "string",
    "unit_of_measure": "string",
    "quantity_on_hand": 0.0,
    "reorder_level": 0.0,
    "unit_cost": 0.0,
    "expiry_date": "2026-05-09T00:00:00Z",
    "batch_no": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Item
- **Endpoint**: `GET /inventory/items/{item_id}`
**Response Body:**
```json
{
  "id": 0,
  "store_id": 0,
  "drug_id": 0,
  "item_type": "string",
  "item_name": "string",
  "sku": "string",
  "unit_of_measure": "string",
  "quantity_on_hand": 0.0,
  "reorder_level": 0.0,
  "unit_cost": 0.0,
  "expiry_date": "2026-05-09T00:00:00Z",
  "batch_no": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Item
- **Endpoint**: `PUT /inventory/items/{item_id}`
**Request Payload:**
```json
{
  "item_name": "string",
  "sku": "string",
  "unit_of_measure": "string",
  "reorder_level": 0.0,
  "unit_cost": 0.0,
  "expiry_date": "2026-05-09T00:00:00Z",
  "batch_no": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "stock_item": {
    "id": 0,
    "store_id": 0,
    "drug_id": 0,
    "item_type": "string",
    "item_name": "string",
    "sku": "string",
    "unit_of_measure": "string",
    "quantity_on_hand": 0.0,
    "reorder_level": 0.0,
    "unit_cost": 0.0,
    "expiry_date": "2026-05-09T00:00:00Z",
    "batch_no": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Delete Item
- **Endpoint**: `DELETE /inventory/items/{item_id}`
---

#### Form/Action: List Movements
- **Endpoint**: `GET /inventory/movements`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Record Movement
- **Endpoint**: `POST /inventory/movements`
**Request Payload:**
```json
{
  "store_id": 0,
  "stock_item_id": 0,
  "movement_type": "string",
  "quantity": 0.0,
  "reference_no": "string",
  "note": "string",
  "performed_by_staff_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "movement": {
    "id": 0,
    "store_id": 0,
    "stock_item_id": 0,
    "performed_by_staff_id": 0,
    "movement_type": "string",
    "reference_no": "string",
    "quantity": 0.0,
    "balance_after": 0.0,
    "movement_date": "2026-05-09T00:00:00Z",
    "note": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Movement
- **Endpoint**: `GET /inventory/movements/{movement_id}`
**Response Body:**
```json
{
  "id": 0,
  "store_id": 0,
  "stock_item_id": 0,
  "performed_by_staff_id": 0,
  "movement_type": "string",
  "reference_no": "string",
  "quantity": 0.0,
  "balance_after": 0.0,
  "movement_date": "2026-05-09T00:00:00Z",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: STOCK_MOVEMENT (File: stock_movement_routes.py)
#### Form/Action: List Movements
- **Endpoint**: `GET /stock-movements/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Post Movement
- **Endpoint**: `POST /stock-movements/`
**Request Payload:**
```json
{
  "store_id": 0,
  "stock_item_id": 0,
  "movement_type": "string",
  "quantity": 0.0,
  "reference_no": "string",
  "note": "string",
  "performed_by_staff_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "movement": {
    "id": 0,
    "store_id": 0,
    "stock_item_id": 0,
    "performed_by_staff_id": 0,
    "movement_type": "string",
    "reference_no": "string",
    "quantity": 0.0,
    "balance_after": 0.0,
    "movement_date": "2026-05-09T00:00:00Z",
    "note": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Transfer Stock
- **Endpoint**: `POST /stock-movements/transfer`
**Request Payload:**
```json
{
  "from_stock_item_id": 0,
  "to_store_id": 0,
  "quantity": 0.0,
  "note": "string",
  "performed_by_staff_id": 0
}
```
---

#### Form/Action: Get Movement
- **Endpoint**: `GET /stock-movements/{movement_id}`
**Response Body:**
```json
{
  "id": 0,
  "store_id": 0,
  "stock_item_id": 0,
  "performed_by_staff_id": 0,
  "movement_type": "string",
  "reference_no": "string",
  "quantity": 0.0,
  "balance_after": 0.0,
  "movement_date": "2026-05-09T00:00:00Z",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: PRESCRIPTION (File: prescription_routes.py)
#### Form/Action: List For Visit
- **Endpoint**: `GET /prescriptions/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Prescription
- **Endpoint**: `POST /prescriptions/`
**Request Payload:**
```json
{
  "visit_id": 0,
  "consultation_id": 0,
  "prescribed_by_staff_id": 0,
  "note": "string",
  "items": "string",
  "auto_capture_charge": false,
  "route_to_pharmacy_service_delivery_point_id": 0,
  "route_to_cashier_service_delivery_point_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "prescription": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "prescribed_by_staff_id": 0,
    "prescription_no": "string",
    "status": "string",
    "note": "string",
    "prescribed_at": "2026-05-09T00:00:00Z",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Prescription
- **Endpoint**: `GET /prescriptions/{prescription_id}`
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "consultation_id": 0,
  "prescribed_by_staff_id": 0,
  "prescription_no": "string",
  "status": "string",
  "note": "string",
  "prescribed_at": "2026-05-09T00:00:00Z",
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Cancel Prescription
- **Endpoint**: `POST /prescriptions/{prescription_id}/cancel`
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "prescription": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "prescribed_by_staff_id": 0,
    "prescription_no": "string",
    "status": "string",
    "note": "string",
    "prescribed_at": "2026-05-09T00:00:00Z",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: DISPENSE (File: dispense_routes.py)
#### Form/Action: Create Dispense
- **Endpoint**: `POST /dispenses/`
**Request Payload:**
```json
{
  "prescription_id": 0,
  "dispensed_by_staff_id": 0,
  "note": "string",
  "items": "string",
  "store_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "dispense": {
    "id": 0,
    "prescription_id": 0,
    "dispensed_by_staff_id": 0,
    "dispense_no": "string",
    "status": "string",
    "dispensed_at": "2026-05-09T00:00:00Z",
    "note": "string",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: List For Visit
- **Endpoint**: `GET /dispenses/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List For Prescription
- **Endpoint**: `GET /dispenses/prescriptions/{prescription_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Dispense
- **Endpoint**: `GET /dispenses/{dispense_id}`
**Response Body:**
```json
{
  "id": 0,
  "prescription_id": 0,
  "dispensed_by_staff_id": 0,
  "dispense_no": "string",
  "status": "string",
  "dispensed_at": "2026-05-09T00:00:00Z",
  "note": "string",
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: PHARMACY (File: pharmacy_routes.py)
#### Form/Action: Get Worklist
- **Endpoint**: `GET /pharmacy/worklist`
---

#### Form/Action: Get Stock Alerts
- **Endpoint**: `GET /pharmacy/stock-alerts`
---


### 📦 Module: ADMISSION (File: admission_routes.py)
#### Form/Action: List Admissions
- **Endpoint**: `GET /admissions/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List Active For Ward
- **Endpoint**: `GET /admissions/wards/{ward_id}/active`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Admission
- **Endpoint**: `GET /admissions/{admission_id}`
**Response Body:**
```json
{
  "id": 0,
  "admission_no": "string",
  "patient_id": 0,
  "visit_id": 0,
  "ward_id": 0,
  "bed_id": 0,
  "admitted_by_staff_id": 0,
  "admission_status": "string",
  "admission_reason": "string",
  "admitted_at": "2026-05-09T00:00:00Z",
  "expected_discharge_at": "2026-05-09T00:00:00Z",
  "actual_discharge_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Admit Patient
- **Endpoint**: `POST /admissions/`
**Request Payload:**
```json
{
  "patient_id": 0,
  "visit_id": 0,
  "ward_id": 0,
  "bed_id": 0,
  "admitting_staff_id": 0,
  "admission_reason": "string",
  "admitted_at": "2026-05-09T00:00:00Z",
  "expected_discharge_at": "2026-05-09T00:00:00Z",
  "capture_first_bed_day_charge": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "admission": {
    "id": 0,
    "admission_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "ward_id": 0,
    "bed_id": 0,
    "admitted_by_staff_id": 0,
    "admission_status": "string",
    "admission_reason": "string",
    "admitted_at": "2026-05-09T00:00:00Z",
    "expected_discharge_at": "2026-05-09T00:00:00Z",
    "actual_discharge_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Convert Visit To Admission
- **Endpoint**: `POST /admissions/from-visit`
**Request Payload:**
```json
{
  "visit_id": 0,
  "ward_id": 0,
  "bed_id": 0,
  "admitting_staff_id": 0,
  "admission_reason": "string",
  "expected_discharge_at": "2026-05-09T00:00:00Z",
  "capture_first_bed_day_charge": false,
  "route_to_service_delivery_point_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "admission": {
    "id": 0,
    "admission_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "ward_id": 0,
    "bed_id": 0,
    "admitted_by_staff_id": 0,
    "admission_status": "string",
    "admission_reason": "string",
    "admitted_at": "2026-05-09T00:00:00Z",
    "expected_discharge_at": "2026-05-09T00:00:00Z",
    "actual_discharge_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Transfer Bed
- **Endpoint**: `POST /admissions/{admission_id}/transfer`
**Request Payload:**
```json
{
  "new_bed_id": 0,
  "new_ward_id": 0,
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "admission": {
    "id": 0,
    "admission_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "ward_id": 0,
    "bed_id": 0,
    "admitted_by_staff_id": 0,
    "admission_status": "string",
    "admission_reason": "string",
    "admitted_at": "2026-05-09T00:00:00Z",
    "expected_discharge_at": "2026-05-09T00:00:00Z",
    "actual_discharge_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Update Status
- **Endpoint**: `POST /admissions/{admission_id}/status`
**Request Payload:**
```json
{
  "new_status": "string",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "admission": {
    "id": 0,
    "admission_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "ward_id": 0,
    "bed_id": 0,
    "admitted_by_staff_id": 0,
    "admission_status": "string",
    "admission_reason": "string",
    "admitted_at": "2026-05-09T00:00:00Z",
    "expected_discharge_at": "2026-05-09T00:00:00Z",
    "actual_discharge_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Capture Bed Day Charges
- **Endpoint**: `POST /admissions/{admission_id}/bed-days`
**Request Payload:**
```json
{
  "through_date": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "admission_id": 0,
  "charges_captured": 0,
  "total_amount_captured": 0.0,
  "captured_through": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: DISCHARGE (File: discharge_routes.py)
#### Form/Action: Discharge
- **Endpoint**: `POST /discharges/`
**Request Payload:**
```json
{
  "admission_id": 0,
  "discharged_by_staff_id": 0,
  "discharge_date": "2026-05-09T00:00:00Z",
  "discharge_condition": "string",
  "discharge_summary": "string",
  "follow_up_instruction": "string",
  "capture_final_bed_day_charges": false,
  "end_visit_if_only_open_event": false,
  "force": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "discharge": {
    "id": 0,
    "admission_id": 0,
    "discharged_by_staff_id": 0,
    "discharge_date": "2026-05-09T00:00:00Z",
    "discharge_condition": "string",
    "discharge_summary": "string",
    "follow_up_instruction": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "admission_id": 0,
  "bed_day_charges_captured": 0,
  "visit_completed": false
}
```
---

#### Form/Action: Check Discharge Readiness
- **Endpoint**: `GET /discharges/admissions/{admission_id}/readiness`
---

#### Form/Action: Get Discharge
- **Endpoint**: `GET /discharges/{discharge_id}`
**Response Body:**
```json
{
  "id": 0,
  "admission_id": 0,
  "discharged_by_staff_id": 0,
  "discharge_date": "2026-05-09T00:00:00Z",
  "discharge_condition": "string",
  "discharge_summary": "string",
  "follow_up_instruction": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Get Discharge For Admission
- **Endpoint**: `GET /discharges/admissions/{admission_id}`
**Response Body:**
```json
{
  "id": 0,
  "admission_id": 0,
  "discharged_by_staff_id": 0,
  "discharge_date": "2026-05-09T00:00:00Z",
  "discharge_condition": "string",
  "discharge_summary": "string",
  "follow_up_instruction": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: BILLING (File: billing_routes.py)
#### Form/Action: List Services
- **Endpoint**: `GET /billing/services`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Billable Service
- **Endpoint**: `POST /billing/services`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "category": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "service": {
    "id": 0,
    "code": "string",
    "name": "string",
    "category": "string",
    "default_price": 0.0,
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Update Billable Service
- **Endpoint**: `PUT /billing/services/{sid}`
**Request Payload:**
```json
{
  "name": "string",
  "category": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "service": {
    "id": 0,
    "code": "string",
    "name": "string",
    "category": "string",
    "default_price": 0.0,
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Delete Billable Service
- **Endpoint**: `DELETE /billing/services/{sid}`
---

#### Form/Action: List Billings
- **Endpoint**: `GET /billing/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List For Visit
- **Endpoint**: `GET /billing/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Billing
- **Endpoint**: `POST /billing/`
**Request Payload:**
```json
{
  "patient_id": 0,
  "visit_id": 0,
  "patient_insurance_id": 0,
  "notes": "string",
  "items": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "billing": {
    "id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "patient_insurance_id": 0,
    "billing_no": "string",
    "billing_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "gross_amount": 0.0,
    "discount_amount": 0.0,
    "net_amount": 0.0,
    "notes": "string",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Billing
- **Endpoint**: `GET /billing/{billing_id}`
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "patient_insurance_id": 0,
  "billing_no": "string",
  "billing_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "gross_amount": 0.0,
  "discount_amount": 0.0,
  "net_amount": 0.0,
  "notes": "string",
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Add Item
- **Endpoint**: `POST /billing/{billing_id}/items`
**Request Payload:**
```json
{
  "service_name": "string",
  "service_code": "string",
  "quantity": 0.0,
  "unit_price": 0.0,
  "discount_amount": 0.0,
  "billable_service_id": 0,
  "source_reference": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "billing": {
    "id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "patient_insurance_id": 0,
    "billing_no": "string",
    "billing_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "gross_amount": 0.0,
    "discount_amount": 0.0,
    "net_amount": 0.0,
    "notes": "string",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Billing
- **Endpoint**: `POST /billing/{billing_id}/cancel`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "billing": {
    "id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "patient_insurance_id": 0,
    "billing_no": "string",
    "billing_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "gross_amount": 0.0,
    "discount_amount": 0.0,
    "net_amount": 0.0,
    "notes": "string",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: INVOICE (File: invoice_routes.py)
#### Form/Action: List Invoices
- **Endpoint**: `GET /invoices/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List For Visit
- **Endpoint**: `GET /invoices/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Issue From Billing
- **Endpoint**: `POST /invoices/issue-from-billing`
**Request Payload:**
```json
{
  "billing_id": 0,
  "payer_id": 0,
  "due_date": "2026-05-09T00:00:00Z",
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "invoice": {
    "id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "billing_id": 0,
    "payer_id": 0,
    "invoice_no": "string",
    "status": "string",
    "invoice_date": "2026-05-09T00:00:00Z",
    "due_date": "2026-05-09T00:00:00Z",
    "subtotal_amount": 0.0,
    "discount_amount": 0.0,
    "tax_amount": 0.0,
    "total_amount": 0.0,
    "amount_paid": 0.0,
    "balance_due": 0.0,
    "note": "string",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Invoice
- **Endpoint**: `GET /invoices/{invoice_id}`
**Response Body:**
```json
{
  "id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "billing_id": 0,
  "payer_id": 0,
  "invoice_no": "string",
  "status": "string",
  "invoice_date": "2026-05-09T00:00:00Z",
  "due_date": "2026-05-09T00:00:00Z",
  "subtotal_amount": 0.0,
  "discount_amount": 0.0,
  "tax_amount": 0.0,
  "total_amount": 0.0,
  "amount_paid": 0.0,
  "balance_due": 0.0,
  "note": "string",
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Void Invoice
- **Endpoint**: `POST /invoices/{invoice_id}/void`
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "invoice": {
    "id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "billing_id": 0,
    "payer_id": 0,
    "invoice_no": "string",
    "status": "string",
    "invoice_date": "2026-05-09T00:00:00Z",
    "due_date": "2026-05-09T00:00:00Z",
    "subtotal_amount": 0.0,
    "discount_amount": 0.0,
    "tax_amount": 0.0,
    "total_amount": 0.0,
    "amount_paid": 0.0,
    "balance_due": 0.0,
    "note": "string",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: PAYMENT (File: payment_routes.py)
#### Form/Action: List Payments
- **Endpoint**: `GET /payments/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List For Invoice
- **Endpoint**: `GET /payments/invoices/{invoice_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Receive Payment
- **Endpoint**: `POST /payments/`
**Request Payload:**
```json
{
  "invoice_id": 0,
  "amount": 0.0,
  "currency": "string",
  "payment_method": "string",
  "membership_card_id": 0,
  "received_by_staff_id": 0,
  "transaction_metadata": "string",
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "payment": {
    "id": 0,
    "invoice_id": 0,
    "received_by_staff_id": 0,
    "payment_reference": "string",
    "payment_method": "string",
    "payment_status": "string",
    "amount": 0.0,
    "currency": "string",
    "paid_at": "2026-05-09T00:00:00Z",
    "transaction_metadata": "string",
    "note": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Refund Payment
- **Endpoint**: `POST /payments/refund`
**Request Payload:**
```json
{
  "payment_id": 0,
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "payment": {
    "id": 0,
    "invoice_id": 0,
    "received_by_staff_id": 0,
    "payment_reference": "string",
    "payment_method": "string",
    "payment_status": "string",
    "amount": 0.0,
    "currency": "string",
    "paid_at": "2026-05-09T00:00:00Z",
    "transaction_metadata": "string",
    "note": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Payment
- **Endpoint**: `GET /payments/{payment_id}`
**Response Body:**
```json
{
  "id": 0,
  "invoice_id": 0,
  "received_by_staff_id": 0,
  "payment_reference": "string",
  "payment_method": "string",
  "payment_status": "string",
  "amount": 0.0,
  "currency": "string",
  "paid_at": "2026-05-09T00:00:00Z",
  "transaction_metadata": "string",
  "note": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: APPOINTMENT (File: appointment_routes.py)
#### Form/Action: List Appointments
- **Endpoint**: `GET /appointments/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Arrival Board
- **Endpoint**: `GET /appointments/arrival-board`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Check Availability
- **Endpoint**: `GET /appointments/availability`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "available": false,
  "conflicts": 0
}
```
---

#### Form/Action: Get Appointment
- **Endpoint**: `GET /appointments/{appointment_id}`
**Response Body:**
```json
{
  "id": 0,
  "appointment_code": "string",
  "patient_id": 0,
  "facility_id": 0,
  "service_delivery_point_id": 0,
  "staff_profile_id": 0,
  "scheduled_start_at": "2026-05-09T00:00:00Z",
  "scheduled_end_at": "2026-05-09T00:00:00Z",
  "reason": "string",
  "status": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Book Appointment
- **Endpoint**: `POST /appointments/`
**Request Payload:**
```json
{
  "patient_id": 0,
  "facility_id": 0,
  "service_delivery_point_id": 0,
  "staff_profile_id": 0,
  "scheduled_start_at": "2026-05-09T00:00:00Z",
  "scheduled_end_at": "2026-05-09T00:00:00Z",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "patient_id": 0,
    "facility_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0,
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Reschedule Appointment
- **Endpoint**: `POST /appointments/{appointment_id}/reschedule`
**Request Payload:**
```json
{
  "new_scheduled_start_at": "2026-05-09T00:00:00Z",
  "new_scheduled_end_at": "2026-05-09T00:00:00Z",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "patient_id": 0,
    "facility_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0,
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Appointment
- **Endpoint**: `POST /appointments/{appointment_id}/cancel`
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "patient_id": 0,
    "facility_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0,
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Mark No Show
- **Endpoint**: `POST /appointments/{appointment_id}/no-show`
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "patient_id": 0,
    "facility_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0,
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Check In Appointment
- **Endpoint**: `POST /appointments/{appointment_id}/check-in`
**Request Payload:**
```json
{
  "initiate_visit": false,
  "visit_flow_template_id": 0,
  "create_first_flow_step": false,
  "create_queue_ticket": false,
  "fast_track": false,
  "use_appointment_service_point": false,
  "visit_reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appointment": {
    "id": 0,
    "appointment_code": "string",
    "patient_id": 0,
    "facility_id": 0,
    "service_delivery_point_id": 0,
    "staff_profile_id": 0,
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "reason": "string",
    "status": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  },
  "visit_id": 0,
  "visit_code": "string",
  "queue_ticket_id": 0,
  "queue_number": "string",
  "queue_position": 0,
  "first_service_delivery_point_id": 0
}
```
---


### 📦 Module: AMBULANCE (File: ambulance_routes.py)
#### Form/Action: List Ambulances
- **Endpoint**: `GET /ambulances/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Ambulance
- **Endpoint**: `POST /ambulances/`
**Request Payload:**
```json
{
  "code": "string",
  "plate_number": "string",
  "model": "string",
  "manufacturer": "string",
  "year_of_manufacture": 0,
  "color": "string",
  "current_mileage": 0.0,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ambulance": {
    "id": 0,
    "code": "string",
    "plate_number": "string",
    "model": "string",
    "manufacturer": "string",
    "year_of_manufacture": 0,
    "color": "string",
    "status": "string",
    "current_mileage": 0.0,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Ambulance
- **Endpoint**: `GET /ambulances/{ambulance_id}`
**Response Body:**
```json
{
  "id": 0,
  "code": "string",
  "plate_number": "string",
  "model": "string",
  "manufacturer": "string",
  "year_of_manufacture": 0,
  "color": "string",
  "status": "string",
  "current_mileage": 0.0,
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Ambulance
- **Endpoint**: `PUT /ambulances/{ambulance_id}`
**Request Payload:**
```json
{
  "model": "string",
  "manufacturer": "string",
  "year_of_manufacture": 0,
  "color": "string",
  "current_mileage": 0.0,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ambulance": {
    "id": 0,
    "code": "string",
    "plate_number": "string",
    "model": "string",
    "manufacturer": "string",
    "year_of_manufacture": 0,
    "color": "string",
    "status": "string",
    "current_mileage": 0.0,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Update Ambulance Status
- **Endpoint**: `POST /ambulances/{ambulance_id}/status`
**Request Payload:**
```json
{
  "new_status": "string",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ambulance": {
    "id": 0,
    "code": "string",
    "plate_number": "string",
    "model": "string",
    "manufacturer": "string",
    "year_of_manufacture": 0,
    "color": "string",
    "status": "string",
    "current_mileage": 0.0,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Soft Delete Ambulance
- **Endpoint**: `DELETE /ambulances/{ambulance_id}`
---

#### Form/Action: Compute Readiness
- **Endpoint**: `GET /ambulances/{ambulance_id}/readiness`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "ambulance_id": 0,
  "ready": false,
  "reasons": "string",
  "primary_driver_id": 0,
  "expired_equipment_ids": 0,
  "open_maintenance_ids": 0
}
```
---

#### Form/Action: List Drivers
- **Endpoint**: `GET /ambulances/drivers/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Driver
- **Endpoint**: `POST /ambulances/drivers/`
**Request Payload:**
```json
{
  "staff_profile_id": 0,
  "ambulance_id": 0,
  "driver_license_no": "string",
  "license_expiry_date": "2026-05-09T00:00:00Z",
  "is_primary_driver": false,
  "emergency_response_certified": false,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "driver": {
    "id": 0,
    "staff_profile_id": 0,
    "ambulance_id": 0,
    "driver_license_no": "string",
    "license_expiry_date": "2026-05-09T00:00:00Z",
    "is_primary_driver": false,
    "emergency_response_certified": false,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Update Driver
- **Endpoint**: `PUT /ambulances/drivers/{driver_id}`
**Request Payload:**
```json
{
  "license_expiry_date": "2026-05-09T00:00:00Z",
  "is_primary_driver": false,
  "emergency_response_certified": false,
  "ambulance_id": 0,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "driver": {
    "id": 0,
    "staff_profile_id": 0,
    "ambulance_id": 0,
    "driver_license_no": "string",
    "license_expiry_date": "2026-05-09T00:00:00Z",
    "is_primary_driver": false,
    "emergency_response_certified": false,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Soft Delete Driver
- **Endpoint**: `DELETE /ambulances/drivers/{driver_id}`
---

#### Form/Action: List Equipment
- **Endpoint**: `GET /ambulances/{ambulance_id}/equipment`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Add Equipment
- **Endpoint**: `POST /ambulances/{ambulance_id}/equipment`
**Request Payload:**
```json
{
  "ambulance_id": 0,
  "equipment_name": "string",
  "equipment_code": "string",
  "quantity": 0.0,
  "condition_status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "equipment": {
    "id": 0,
    "ambulance_id": 0,
    "equipment_name": "string",
    "equipment_code": "string",
    "quantity": 0.0,
    "condition_status": "string",
    "expiry_date": "2026-05-09T00:00:00Z",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Update Equipment
- **Endpoint**: `PUT /ambulances/equipment/{equipment_id}`
**Request Payload:**
```json
{
  "equipment_name": "string",
  "quantity": 0.0,
  "condition_status": "string",
  "expiry_date": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "equipment": {
    "id": 0,
    "ambulance_id": 0,
    "equipment_name": "string",
    "equipment_code": "string",
    "quantity": 0.0,
    "condition_status": "string",
    "expiry_date": "2026-05-09T00:00:00Z",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Soft Delete Equipment
- **Endpoint**: `DELETE /ambulances/equipment/{equipment_id}`
---

#### Form/Action: List Maintenance
- **Endpoint**: `GET /ambulances/{ambulance_id}/maintenance`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": 0,
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Schedule Maintenance
- **Endpoint**: `POST /ambulances/{ambulance_id}/maintenance`
**Request Payload:**
```json
{
  "ambulance_id": 0,
  "maintenance_type": "string",
  "issue_description": "string",
  "service_provider": "string",
  "maintenance_date": "2026-05-09T00:00:00Z",
  "cost": 0.0,
  "mileage_at_service": 0.0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "maintenance": {
    "id": 0,
    "ambulance_id": 0,
    "maintenance_status": "string",
    "maintenance_type": "string",
    "issue_description": "string",
    "service_provider": "string",
    "maintenance_date": "2026-05-09T00:00:00Z",
    "completed_date": "2026-05-09T00:00:00Z",
    "cost": 0.0,
    "mileage_at_service": 0.0
  }
}
```
---

#### Form/Action: Update Maintenance
- **Endpoint**: `PUT /ambulances/maintenance/{maintenance_id}`
**Request Payload:**
```json
{
  "maintenance_status": "string",
  "completed_date": "2026-05-09T00:00:00Z",
  "issue_description": "string",
  "service_provider": "string",
  "cost": 0.0,
  "mileage_at_service": 0.0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "maintenance": {
    "id": 0,
    "ambulance_id": 0,
    "maintenance_status": "string",
    "maintenance_type": "string",
    "issue_description": "string",
    "service_provider": "string",
    "maintenance_date": "2026-05-09T00:00:00Z",
    "completed_date": "2026-05-09T00:00:00Z",
    "cost": 0.0,
    "mileage_at_service": 0.0
  }
}
```
---


### 📦 Module: AMBULANCE_DISPATCH (File: ambulance_routes.py)
#### Form/Action: List Dispatches
- **Endpoint**: `GET /ambulance-dispatches/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Dispatch
- **Endpoint**: `POST /ambulance-dispatches/`
**Request Payload:**
```json
{
  "ambulance_id": 0,
  "driver_id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "pickup_location": "string",
  "destination_location": "string",
  "incident_description": "string",
  "requested_at": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "dispatch": {
    "id": 0,
    "dispatch_no": "string",
    "ambulance_id": 0,
    "driver_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "dispatch_status": "string",
    "pickup_location": "string",
    "destination_location": "string",
    "incident_description": "string",
    "requested_at": "2026-05-09T00:00:00Z",
    "assigned_at": "2026-05-09T00:00:00Z",
    "departed_at": "2026-05-09T00:00:00Z",
    "arrived_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Dispatch
- **Endpoint**: `GET /ambulance-dispatches/{dispatch_id}`
**Response Body:**
```json
{
  "id": 0,
  "dispatch_no": "string",
  "ambulance_id": 0,
  "driver_id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "dispatch_status": "string",
  "pickup_location": "string",
  "destination_location": "string",
  "incident_description": "string",
  "requested_at": "2026-05-09T00:00:00Z",
  "assigned_at": "2026-05-09T00:00:00Z",
  "departed_at": "2026-05-09T00:00:00Z",
  "arrived_at": "2026-05-09T00:00:00Z",
  "completed_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Assign Dispatch
- **Endpoint**: `POST /ambulance-dispatches/{dispatch_id}/assign`
**Request Payload:**
```json
{
  "ambulance_id": 0,
  "driver_id": 0,
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "dispatch": {
    "id": 0,
    "dispatch_no": "string",
    "ambulance_id": 0,
    "driver_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "dispatch_status": "string",
    "pickup_location": "string",
    "destination_location": "string",
    "incident_description": "string",
    "requested_at": "2026-05-09T00:00:00Z",
    "assigned_at": "2026-05-09T00:00:00Z",
    "departed_at": "2026-05-09T00:00:00Z",
    "arrived_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Depart Dispatch
- **Endpoint**: `POST /ambulance-dispatches/{dispatch_id}/depart`
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "dispatch": {
    "id": 0,
    "dispatch_no": "string",
    "ambulance_id": 0,
    "driver_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "dispatch_status": "string",
    "pickup_location": "string",
    "destination_location": "string",
    "incident_description": "string",
    "requested_at": "2026-05-09T00:00:00Z",
    "assigned_at": "2026-05-09T00:00:00Z",
    "departed_at": "2026-05-09T00:00:00Z",
    "arrived_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Arrive Dispatch
- **Endpoint**: `POST /ambulance-dispatches/{dispatch_id}/arrive`
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "dispatch": {
    "id": 0,
    "dispatch_no": "string",
    "ambulance_id": 0,
    "driver_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "dispatch_status": "string",
    "pickup_location": "string",
    "destination_location": "string",
    "incident_description": "string",
    "requested_at": "2026-05-09T00:00:00Z",
    "assigned_at": "2026-05-09T00:00:00Z",
    "departed_at": "2026-05-09T00:00:00Z",
    "arrived_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Patient Picked Dispatch
- **Endpoint**: `POST /ambulance-dispatches/{dispatch_id}/patient-picked`
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "dispatch": {
    "id": 0,
    "dispatch_no": "string",
    "ambulance_id": 0,
    "driver_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "dispatch_status": "string",
    "pickup_location": "string",
    "destination_location": "string",
    "incident_description": "string",
    "requested_at": "2026-05-09T00:00:00Z",
    "assigned_at": "2026-05-09T00:00:00Z",
    "departed_at": "2026-05-09T00:00:00Z",
    "arrived_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Complete Dispatch
- **Endpoint**: `POST /ambulance-dispatches/{dispatch_id}/complete`
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "dispatch": {
    "id": 0,
    "dispatch_no": "string",
    "ambulance_id": 0,
    "driver_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "dispatch_status": "string",
    "pickup_location": "string",
    "destination_location": "string",
    "incident_description": "string",
    "requested_at": "2026-05-09T00:00:00Z",
    "assigned_at": "2026-05-09T00:00:00Z",
    "departed_at": "2026-05-09T00:00:00Z",
    "arrived_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Dispatch
- **Endpoint**: `POST /ambulance-dispatches/{dispatch_id}/cancel`
**Request Payload:**
```json
{
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "dispatch": {
    "id": 0,
    "dispatch_no": "string",
    "ambulance_id": 0,
    "driver_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "dispatch_status": "string",
    "pickup_location": "string",
    "destination_location": "string",
    "incident_description": "string",
    "requested_at": "2026-05-09T00:00:00Z",
    "assigned_at": "2026-05-09T00:00:00Z",
    "departed_at": "2026-05-09T00:00:00Z",
    "arrived_at": "2026-05-09T00:00:00Z",
    "completed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: List Incidents
- **Endpoint**: `GET /ambulance-dispatches/{dispatch_id}/incidents`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: File Incident
- **Endpoint**: `POST /ambulance-dispatches/{dispatch_id}/incidents`
**Request Payload:**
```json
{
  "dispatch_id": 0,
  "reported_by_staff_id": 0,
  "severity": "string",
  "incident_date": "2026-05-09T00:00:00Z",
  "summary": "string",
  "action_taken": "string",
  "follow_up_required": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "incident": {
    "id": 0,
    "dispatch_id": 0,
    "reported_by_staff_id": 0,
    "severity": "string",
    "incident_date": "2026-05-09T00:00:00Z",
    "summary": "string",
    "action_taken": "string",
    "follow_up_required": false,
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: NOTIFICATION (File: notification_routes.py)
#### Form/Action: List Templates
- **Endpoint**: `GET /notifications/templates`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Template
- **Endpoint**: `POST /notifications/templates`
**Request Payload:**
```json
{
  "name": "string",
  "code": "string",
  "channel": "string",
  "subject_template": "string",
  "body_template": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "template": {
    "id": 0,
    "name": "string",
    "code": "string",
    "channel": "string",
    "subject_template": "string",
    "body_template": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Template
- **Endpoint**: `GET /notifications/templates/{template_id}`
**Response Body:**
```json
{
  "id": 0,
  "name": "string",
  "code": "string",
  "channel": "string",
  "subject_template": "string",
  "body_template": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Template
- **Endpoint**: `PUT /notifications/templates/{template_id}`
**Request Payload:**
```json
{
  "name": "string",
  "subject_template": "string",
  "body_template": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "template": {
    "id": 0,
    "name": "string",
    "code": "string",
    "channel": "string",
    "subject_template": "string",
    "body_template": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Soft Delete Template
- **Endpoint**: `DELETE /notifications/templates/{template_id}`
---

#### Form/Action: List Notifications
- **Endpoint**: `GET /notifications/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Get Notification
- **Endpoint**: `GET /notifications/{notification_id}`
**Response Body:**
```json
{
  "id": 0,
  "user_id": 0,
  "patient_id": 0,
  "template_id": 0,
  "channel": "string",
  "status": "string",
  "recipient_address": "string",
  "subject": "string",
  "body": "string",
  "payload_metadata": "string",
  "scheduled_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Dispatch From Template
- **Endpoint**: `POST /notifications/dispatch`
**Request Payload:**
```json
{
  "template_code": "string",
  "template_id": 0,
  "user_id": 0,
  "patient_id": 0,
  "recipient_address": "string",
  "context": "string",
  "scheduled_at": "2026-05-09T00:00:00Z",
  "channel_override": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "notification": {
    "id": 0,
    "user_id": 0,
    "patient_id": 0,
    "template_id": 0,
    "channel": "string",
    "status": "string",
    "recipient_address": "string",
    "subject": "string",
    "body": "string",
    "payload_metadata": "string",
    "scheduled_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Dispatch Ad Hoc
- **Endpoint**: `POST /notifications/dispatch-ad-hoc`
**Request Payload:**
```json
{
  "channel": "string",
  "subject": "string",
  "body": "string",
  "user_id": 0,
  "patient_id": 0,
  "recipient_address": "string",
  "scheduled_at": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "notification": {
    "id": 0,
    "user_id": 0,
    "patient_id": 0,
    "template_id": 0,
    "channel": "string",
    "status": "string",
    "recipient_address": "string",
    "subject": "string",
    "body": "string",
    "payload_metadata": "string",
    "scheduled_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Retry Failed
- **Endpoint**: `POST /notifications/retry-failed`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "retried": 0,
  "failed": 0,
  "sent": 0
}
```
---

#### Form/Action: Mark Read
- **Endpoint**: `POST /notifications/{notification_id}/mark-read`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "notification": {
    "id": 0,
    "user_id": 0,
    "patient_id": 0,
    "template_id": 0,
    "channel": "string",
    "status": "string",
    "recipient_address": "string",
    "subject": "string",
    "body": "string",
    "payload_metadata": "string",
    "scheduled_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Message Inbox
- **Endpoint**: `GET /notifications/messages/inbox`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Message Sent
- **Endpoint**: `GET /notifications/messages/sent`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Send Message
- **Endpoint**: `POST /notifications/messages`
**Request Payload:**
```json
{
  "recipient_user_id": 0,
  "subject": "string",
  "body": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "direct_message": {
    "id": 0,
    "sender_user_id": 0,
    "recipient_user_id": 0,
    "subject": "string",
    "body": "string",
    "status": "string",
    "sent_at": "2026-05-09T00:00:00Z",
    "read_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Mark Message Read
- **Endpoint**: `POST /notifications/messages/{message_id}/read`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "direct_message": {
    "id": 0,
    "sender_user_id": 0,
    "recipient_user_id": 0,
    "subject": "string",
    "body": "string",
    "status": "string",
    "sent_at": "2026-05-09T00:00:00Z",
    "read_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Message
- **Endpoint**: `GET /notifications/messages/{message_id}`
**Response Body:**
```json
{
  "id": 0,
  "sender_user_id": 0,
  "recipient_user_id": 0,
  "subject": "string",
  "body": "string",
  "status": "string",
  "sent_at": "2026-05-09T00:00:00Z",
  "read_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: PUSH_DEVICE (File: push_device_routes.py)
#### Form/Action: Register Device
- **Endpoint**: `POST /push-devices`
**Request Payload:**
```json
"string"
```
**Response Body:**
```json
"string"
```
---

#### Form/Action: List Devices
- **Endpoint**: `GET /push-devices`
**Response Body:**
```json
"string"
```
---

#### Form/Action: Remove Device
- **Endpoint**: `DELETE /push-devices/{device_id}`
---


### 📦 Module: COMPLIANCE (File: compliance_routes.py)
#### Form/Action: List Compliance Records
- **Endpoint**: `GET /compliance/records`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Compliance Record
- **Endpoint**: `POST /compliance/records`
**Request Payload:**
```json
{
  "title": "string",
  "department_id": 0,
  "owner_staff_id": 0,
  "compliance_area": "string",
  "reference_code": "string",
  "due_date": "2026-05-09T00:00:00Z",
  "review_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "findings": "string",
  "action_plan": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "record": {
    "id": 0,
    "department_id": 0,
    "owner_staff_id": 0,
    "title": "string",
    "compliance_area": "string",
    "reference_code": "string",
    "due_date": "2026-05-09T00:00:00Z",
    "review_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "findings": "string",
    "action_plan": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Compliance Record
- **Endpoint**: `GET /compliance/records/{record_id}`
**Response Body:**
```json
{
  "id": 0,
  "department_id": 0,
  "owner_staff_id": 0,
  "title": "string",
  "compliance_area": "string",
  "reference_code": "string",
  "due_date": "2026-05-09T00:00:00Z",
  "review_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "findings": "string",
  "action_plan": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Compliance Record
- **Endpoint**: `PUT /compliance/records/{record_id}`
**Request Payload:**
```json
{
  "title": "string",
  "owner_staff_id": 0,
  "compliance_area": "string",
  "reference_code": "string",
  "due_date": "2026-05-09T00:00:00Z",
  "review_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "findings": "string",
  "action_plan": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "record": {
    "id": 0,
    "department_id": 0,
    "owner_staff_id": 0,
    "title": "string",
    "compliance_area": "string",
    "reference_code": "string",
    "due_date": "2026-05-09T00:00:00Z",
    "review_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "findings": "string",
    "action_plan": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Soft Delete Compliance Record
- **Endpoint**: `DELETE /compliance/records/{record_id}`
---

#### Form/Action: List Accreditations
- **Endpoint**: `GET /compliance/accreditations`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Accreditation
- **Endpoint**: `POST /compliance/accreditations`
**Request Payload:**
```json
{
  "accreditation_body": "string",
  "accreditation_name": "string",
  "department_id": 0,
  "certificate_no": "string",
  "issue_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "accreditation": {
    "id": 0,
    "department_id": 0,
    "accreditation_body": "string",
    "accreditation_name": "string",
    "certificate_no": "string",
    "issue_date": "2026-05-09T00:00:00Z",
    "expiry_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Accreditation
- **Endpoint**: `GET /compliance/accreditations/{accreditation_id}`
**Response Body:**
```json
{
  "id": 0,
  "department_id": 0,
  "accreditation_body": "string",
  "accreditation_name": "string",
  "certificate_no": "string",
  "issue_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "notes": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Accreditation
- **Endpoint**: `PUT /compliance/accreditations/{accreditation_id}`
**Request Payload:**
```json
{
  "certificate_no": "string",
  "issue_date": "2026-05-09T00:00:00Z",
  "expiry_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "accreditation": {
    "id": 0,
    "department_id": 0,
    "accreditation_body": "string",
    "accreditation_name": "string",
    "certificate_no": "string",
    "issue_date": "2026-05-09T00:00:00Z",
    "expiry_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Soft Delete Accreditation
- **Endpoint**: `DELETE /compliance/accreditations/{accreditation_id}`
---

#### Form/Action: List Incidents
- **Endpoint**: `GET /compliance/incidents`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: File Incident
- **Endpoint**: `POST /compliance/incidents`
**Request Payload:**
```json
{
  "summary": "string",
  "incident_date": "2026-05-09T00:00:00Z",
  "severity": "string",
  "category": "string",
  "department_id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "reported_by_staff_id": 0,
  "immediate_action_taken": "string",
  "follow_up_required": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "incident": {
    "id": 0,
    "incident_no": "string",
    "incident_date": "2026-05-09T00:00:00Z",
    "severity": "string",
    "category": "string",
    "summary": "string",
    "immediate_action_taken": "string",
    "follow_up_required": false,
    "department_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "reported_by_staff_id": 0,
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Incident
- **Endpoint**: `GET /compliance/incidents/{incident_id}`
**Response Body:**
```json
{
  "id": 0,
  "incident_no": "string",
  "incident_date": "2026-05-09T00:00:00Z",
  "severity": "string",
  "category": "string",
  "summary": "string",
  "immediate_action_taken": "string",
  "follow_up_required": false,
  "department_id": 0,
  "patient_id": 0,
  "visit_id": 0,
  "reported_by_staff_id": 0,
  "created_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Incident
- **Endpoint**: `PUT /compliance/incidents/{incident_id}`
**Request Payload:**
```json
{
  "severity": "string",
  "category": "string",
  "immediate_action_taken": "string",
  "follow_up_required": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "incident": {
    "id": 0,
    "incident_no": "string",
    "incident_date": "2026-05-09T00:00:00Z",
    "severity": "string",
    "category": "string",
    "summary": "string",
    "immediate_action_taken": "string",
    "follow_up_required": false,
    "department_id": 0,
    "patient_id": 0,
    "visit_id": 0,
    "reported_by_staff_id": 0,
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: List Infection Logs
- **Endpoint**: `GET /compliance/infection-logs`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Infection Log
- **Endpoint**: `POST /compliance/infection-logs`
**Request Payload:**
```json
{
  "log_date": "2026-05-09T00:00:00Z",
  "details": "string",
  "department_id": 0,
  "recorded_by_staff_id": 0,
  "infection_type": "string",
  "affected_area": "string",
  "action_taken": "string",
  "outcome": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "log": {
    "id": 0,
    "department_id": 0,
    "recorded_by_staff_id": 0,
    "log_date": "2026-05-09T00:00:00Z",
    "infection_type": "string",
    "affected_area": "string",
    "details": "string",
    "action_taken": "string",
    "outcome": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Infection Log
- **Endpoint**: `GET /compliance/infection-logs/{log_id}`
**Response Body:**
```json
{
  "id": 0,
  "department_id": 0,
  "recorded_by_staff_id": 0,
  "log_date": "2026-05-09T00:00:00Z",
  "infection_type": "string",
  "affected_area": "string",
  "details": "string",
  "action_taken": "string",
  "outcome": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: List Quality Projects
- **Endpoint**: `GET /compliance/quality-projects`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Quality Project
- **Endpoint**: `POST /compliance/quality-projects`
**Request Payload:**
```json
{
  "title": "string",
  "department_id": 0,
  "project_lead_staff_id": 0,
  "objective": "string",
  "problem_statement": "string",
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "outcome_summary": "string",
  "recommendations": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "project": {
    "id": 0,
    "department_id": 0,
    "project_lead_staff_id": 0,
    "title": "string",
    "objective": "string",
    "problem_statement": "string",
    "start_date": "2026-05-09T00:00:00Z",
    "end_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "outcome_summary": "string",
    "recommendations": "string"
  }
}
```
---

#### Form/Action: Get Quality Project
- **Endpoint**: `GET /compliance/quality-projects/{project_id}`
**Response Body:**
```json
{
  "id": 0,
  "department_id": 0,
  "project_lead_staff_id": 0,
  "title": "string",
  "objective": "string",
  "problem_statement": "string",
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "outcome_summary": "string",
  "recommendations": "string"
}
```
---

#### Form/Action: Update Quality Project
- **Endpoint**: `PUT /compliance/quality-projects/{project_id}`
**Request Payload:**
```json
{
  "objective": "string",
  "problem_statement": "string",
  "start_date": "2026-05-09T00:00:00Z",
  "end_date": "2026-05-09T00:00:00Z",
  "status": "string",
  "outcome_summary": "string",
  "recommendations": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "project": {
    "id": 0,
    "department_id": 0,
    "project_lead_staff_id": 0,
    "title": "string",
    "objective": "string",
    "problem_statement": "string",
    "start_date": "2026-05-09T00:00:00Z",
    "end_date": "2026-05-09T00:00:00Z",
    "status": "string",
    "outcome_summary": "string",
    "recommendations": "string"
  }
}
```
---

#### Form/Action: Get Dashboard
- **Endpoint**: `GET /compliance/dashboard`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "compliance_due_soon": 0,
  "compliance_overdue": 0,
  "accreditations_expiring_soon": 0,
  "accreditations_expired": 0,
  "incidents_open_critical": 0,
  "incidents_open_high": 0,
  "quality_projects_active": 0
}
```
---


### 📦 Module: PROCEDURE_CATALOG (File: procedure_routes.py)
#### Form/Action: List Procedures
- **Endpoint**: `GET /procedures/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Procedure
- **Endpoint**: `POST /procedures/`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "description": "string",
  "default_price": 0.0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "procedure": {
    "id": 0,
    "code": "string",
    "name": "string",
    "description": "string",
    "default_price": 0.0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Procedure
- **Endpoint**: `GET /procedures/{procedure_id}`
**Response Body:**
```json
{
  "id": 0,
  "code": "string",
  "name": "string",
  "description": "string",
  "default_price": 0.0,
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Procedure
- **Endpoint**: `PUT /procedures/{procedure_id}`
**Request Payload:**
```json
{
  "name": "string",
  "description": "string",
  "default_price": 0.0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "procedure": {
    "id": 0,
    "code": "string",
    "name": "string",
    "description": "string",
    "default_price": 0.0,
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Soft Delete Procedure
- **Endpoint**: `DELETE /procedures/{procedure_id}`
---


### 📦 Module: PROCEDURE_ORDER (File: procedure_routes.py)
#### Form/Action: List For Visit
- **Endpoint**: `GET /procedure-orders/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List Worklist
- **Endpoint**: `GET /procedure-orders/worklist`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Order Procedure
- **Endpoint**: `POST /procedure-orders/`
**Request Payload:**
```json
{
  "visit_id": 0,
  "procedure_catalog_id": 0,
  "consultation_id": 0,
  "ordered_by_staff_id": 0,
  "notes": "string",
  "auto_capture_charge": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "procedure_catalog_id": 0,
    "ordered_by_staff_id": 0,
    "performed_by_staff_id": 0,
    "status": "string",
    "findings": "string",
    "notes": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "performed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Order
- **Endpoint**: `GET /procedure-orders/{order_id}`
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "consultation_id": 0,
  "procedure_catalog_id": 0,
  "ordered_by_staff_id": 0,
  "performed_by_staff_id": 0,
  "status": "string",
  "findings": "string",
  "notes": "string",
  "ordered_at": "2026-05-09T00:00:00Z",
  "performed_at": "2026-05-09T00:00:00Z",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Start Procedure
- **Endpoint**: `POST /procedure-orders/{order_id}/start`
**Request Payload:**
```json
{
  "performed_by_staff_id": 0,
  "findings": "string",
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "procedure_catalog_id": 0,
    "ordered_by_staff_id": 0,
    "performed_by_staff_id": 0,
    "status": "string",
    "findings": "string",
    "notes": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "performed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Complete Procedure
- **Endpoint**: `POST /procedure-orders/{order_id}/complete`
**Request Payload:**
```json
{
  "performed_by_staff_id": 0,
  "findings": "string",
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "procedure_catalog_id": 0,
    "ordered_by_staff_id": 0,
    "performed_by_staff_id": 0,
    "status": "string",
    "findings": "string",
    "notes": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "performed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Cancel Procedure
- **Endpoint**: `POST /procedure-orders/{order_id}/cancel`
**Request Payload:**
```json
{
  "performed_by_staff_id": 0,
  "findings": "string",
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "procedure_catalog_id": 0,
    "ordered_by_staff_id": 0,
    "performed_by_staff_id": 0,
    "status": "string",
    "findings": "string",
    "notes": "string",
    "ordered_at": "2026-05-09T00:00:00Z",
    "performed_at": "2026-05-09T00:00:00Z",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: RADIOLOGY_CATALOG (File: radiology_routes.py)
#### Form/Action: List Procedures
- **Endpoint**: `GET /radiology/procedures/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Procedure
- **Endpoint**: `POST /radiology/procedures/`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "modality": "string",
  "body_part": "string",
  "cpt_code": "string",
  "typical_duration_minutes": 0,
  "contrast_required": false,
  "radiation_dose_msv": 0.0,
  "preparation_instructions": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "procedure": {
    "id": 0,
    "code": "string",
    "name": "string",
    "modality": "string",
    "body_part": "string",
    "cpt_code": "string",
    "typical_duration_minutes": 0,
    "contrast_required": false,
    "radiation_dose_msv": 0.0,
    "preparation_instructions": "string",
    "default_price": 0.0,
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Procedure
- **Endpoint**: `GET /radiology/procedures/{procedure_id}`
**Response Body:**
```json
{
  "id": 0,
  "code": "string",
  "name": "string",
  "modality": "string",
  "body_part": "string",
  "cpt_code": "string",
  "typical_duration_minutes": 0,
  "contrast_required": false,
  "radiation_dose_msv": 0.0,
  "preparation_instructions": "string",
  "default_price": 0.0,
  "description": "string",
  "created_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Update Procedure
- **Endpoint**: `PUT /radiology/procedures/{procedure_id}`
**Request Payload:**
```json
{
  "name": "string",
  "body_part": "string",
  "cpt_code": "string",
  "typical_duration_minutes": 0,
  "contrast_required": false,
  "radiation_dose_msv": 0.0,
  "preparation_instructions": "string",
  "default_price": 0.0,
  "description": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "procedure": {
    "id": 0,
    "code": "string",
    "name": "string",
    "modality": "string",
    "body_part": "string",
    "cpt_code": "string",
    "typical_duration_minutes": 0,
    "contrast_required": false,
    "radiation_dose_msv": 0.0,
    "preparation_instructions": "string",
    "default_price": 0.0,
    "description": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Soft Delete Procedure
- **Endpoint**: `DELETE /radiology/procedures/{procedure_id}`
---


### 📦 Module: RADIOLOGY_ORDER (File: radiology_routes.py)
#### Form/Action: List For Visit
- **Endpoint**: `GET /radiology/orders/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: List Worklist
- **Endpoint**: `GET /radiology/orders/worklist`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Order
- **Endpoint**: `POST /radiology/orders/`
**Request Payload:**
```json
{
  "visit_id": 0,
  "consultation_id": 0,
  "ordered_by_staff_id": 0,
  "facility_id": 0,
  "priority": "string",
  "clinical_indication": "string",
  "pregnancy_screening": false,
  "creatinine_value": 0.0,
  "items": "string",
  "auto_capture_charge": false,
  "route_to_radiology_service_delivery_point_id": 0,
  "route_to_cashier_service_delivery_point_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "facility_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "priority": "string",
    "clinical_indication": "string",
    "pregnancy_screening": false,
    "creatinine_value": 0.0,
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Order
- **Endpoint**: `GET /radiology/orders/{order_id}`
**Response Body:**
```json
{
  "id": 0,
  "visit_id": 0,
  "consultation_id": 0,
  "facility_id": 0,
  "ordered_by_staff_id": 0,
  "order_no": "string",
  "status": "string",
  "priority": "string",
  "clinical_indication": "string",
  "pregnancy_screening": false,
  "creatinine_value": 0.0,
  "ordered_at": "2026-05-09T00:00:00Z",
  "items": "string",
  "created_at": "2026-05-09T00:00:00Z",
  "updated_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Cancel Order
- **Endpoint**: `POST /radiology/orders/{order_id}/cancel`
**Request Payload:**
```json
{
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "order": {
    "id": 0,
    "visit_id": 0,
    "consultation_id": 0,
    "facility_id": 0,
    "ordered_by_staff_id": 0,
    "order_no": "string",
    "status": "string",
    "priority": "string",
    "clinical_indication": "string",
    "pregnancy_screening": false,
    "creatinine_value": 0.0,
    "ordered_at": "2026-05-09T00:00:00Z",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z",
    "updated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: RADIOLOGY_EXAM (File: radiology_routes.py)
#### Form/Action: Schedule Exam
- **Endpoint**: `POST /radiology/exams/schedule`
**Request Payload:**
```json
{
  "order_item_id": 0,
  "facility_id": 0,
  "scheduled_at": "2026-05-09T00:00:00Z",
  "machine_identifier": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "exam": {
    "id": 0,
    "order_item_id": 0,
    "facility_id": 0,
    "performed_by_staff_id": 0,
    "machine_identifier": "string",
    "accession_number": "string",
    "status": "string",
    "scheduled_at": "2026-05-09T00:00:00Z",
    "started_at": "2026-05-09T00:00:00Z",
    "ended_at": "2026-05-09T00:00:00Z",
    "contrast_administered": false,
    "technical_notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Start Exam
- **Endpoint**: `POST /radiology/exams/{exam_id}/start`
**Request Payload:**
```json
{
  "performed_by_staff_id": 0,
  "machine_identifier": "string",
  "contrast_administered": false,
  "technical_notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "exam": {
    "id": 0,
    "order_item_id": 0,
    "facility_id": 0,
    "performed_by_staff_id": 0,
    "machine_identifier": "string",
    "accession_number": "string",
    "status": "string",
    "scheduled_at": "2026-05-09T00:00:00Z",
    "started_at": "2026-05-09T00:00:00Z",
    "ended_at": "2026-05-09T00:00:00Z",
    "contrast_administered": false,
    "technical_notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Complete Exam
- **Endpoint**: `POST /radiology/exams/{exam_id}/complete`
**Request Payload:**
```json
{
  "technical_notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "exam": {
    "id": 0,
    "order_item_id": 0,
    "facility_id": 0,
    "performed_by_staff_id": 0,
    "machine_identifier": "string",
    "accession_number": "string",
    "status": "string",
    "scheduled_at": "2026-05-09T00:00:00Z",
    "started_at": "2026-05-09T00:00:00Z",
    "ended_at": "2026-05-09T00:00:00Z",
    "contrast_administered": false,
    "technical_notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Attach Image
- **Endpoint**: `POST /radiology/exams/{exam_id}/images`
**Request Payload:**
```json
{
  "exam_id": 0,
  "sop_instance_uid": "string",
  "series_instance_uid": "string",
  "study_instance_uid": "string",
  "image_url": "string",
  "pacs_archive_id": "string",
  "image_count": 0,
  "captured_at": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "image": {
    "id": 0,
    "exam_id": 0,
    "sop_instance_uid": "string",
    "series_instance_uid": "string",
    "study_instance_uid": "string",
    "image_url": "string",
    "pacs_archive_id": "string",
    "image_count": 0,
    "captured_at": "2026-05-09T00:00:00Z",
    "notes": "string"
  }
}
```
---

#### Form/Action: List Images
- **Endpoint**: `GET /radiology/exams/{exam_id}/images`
---


### 📦 Module: RADIOLOGY_REPORT (File: radiology_routes.py)
#### Form/Action: Draft Report
- **Endpoint**: `POST /radiology/reports/draft`
**Request Payload:**
```json
{
  "exam_id": 0,
  "reported_by_staff_id": 0,
  "findings": "string",
  "impression": "string",
  "recommendations": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "report": {
    "id": 0,
    "exam_id": 0,
    "reported_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "status": "string",
    "findings": "string",
    "impression": "string",
    "recommendations": "string",
    "drafted_at": "2026-05-09T00:00:00Z",
    "finalized_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Finalize Report
- **Endpoint**: `POST /radiology/reports/{report_id}/finalize`
**Request Payload:**
```json
{
  "verified_by_staff_id": 0,
  "findings": "string",
  "impression": "string",
  "recommendations": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "report": {
    "id": 0,
    "exam_id": 0,
    "reported_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "status": "string",
    "findings": "string",
    "impression": "string",
    "recommendations": "string",
    "drafted_at": "2026-05-09T00:00:00Z",
    "finalized_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Release Report
- **Endpoint**: `POST /radiology/reports/{report_id}/release`
**Request Payload:**
```json
{
  "notify_clinician": false,
  "note": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "report": {
    "id": 0,
    "exam_id": 0,
    "reported_by_staff_id": 0,
    "verified_by_staff_id": 0,
    "status": "string",
    "findings": "string",
    "impression": "string",
    "recommendations": "string",
    "drafted_at": "2026-05-09T00:00:00Z",
    "finalized_at": "2026-05-09T00:00:00Z",
    "released_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Report
- **Endpoint**: `GET /radiology/reports/{report_id}`
**Response Body:**
```json
{
  "id": 0,
  "exam_id": 0,
  "reported_by_staff_id": 0,
  "verified_by_staff_id": 0,
  "status": "string",
  "findings": "string",
  "impression": "string",
  "recommendations": "string",
  "drafted_at": "2026-05-09T00:00:00Z",
  "finalized_at": "2026-05-09T00:00:00Z",
  "released_at": "2026-05-09T00:00:00Z"
}
```
---

#### Form/Action: Get Report For Exam
- **Endpoint**: `GET /radiology/reports/exams/{exam_id}`
**Response Body:**
```json
{
  "id": 0,
  "exam_id": 0,
  "reported_by_staff_id": 0,
  "verified_by_staff_id": 0,
  "status": "string",
  "findings": "string",
  "impression": "string",
  "recommendations": "string",
  "drafted_at": "2026-05-09T00:00:00Z",
  "finalized_at": "2026-05-09T00:00:00Z",
  "released_at": "2026-05-09T00:00:00Z"
}
```
---


### 📦 Module: SURGICAL_THEATRE (File: surgical_routes.py)
#### Form/Action: List Theatres
- **Endpoint**: `GET /theatres/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Theatre
- **Endpoint**: `POST /theatres/`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "facility_id": 0,
  "location_description": "string",
  "is_emergency_capable": false,
  "capabilities": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "theatre": {
    "id": 0,
    "code": "string",
    "name": "string",
    "facility_id": 0,
    "location_description": "string",
    "status": "string",
    "is_emergency_capable": false,
    "capabilities": "string",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Theatre
- **Endpoint**: `GET /theatres/{theatre_id}`
---

#### Form/Action: Update Theatre
- **Endpoint**: `PUT /theatres/{theatre_id}`
**Request Payload:**
```json
{
  "name": "string",
  "location_description": "string",
  "is_emergency_capable": false,
  "capabilities": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "theatre": {
    "id": 0,
    "code": "string",
    "name": "string",
    "facility_id": 0,
    "location_description": "string",
    "status": "string",
    "is_emergency_capable": false,
    "capabilities": "string",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Change Theatre Status
- **Endpoint**: `POST /theatres/{theatre_id}/status`
**Request Payload:**
```json
{
  "new_status": "string",
  "reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "theatre": {
    "id": 0,
    "code": "string",
    "name": "string",
    "facility_id": 0,
    "location_description": "string",
    "status": "string",
    "is_emergency_capable": false,
    "capabilities": "string",
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Soft Delete Theatre
- **Endpoint**: `DELETE /theatres/{theatre_id}`
---


### 📦 Module: SURGICAL_CATALOG (File: surgical_routes.py)
#### Form/Action: List Procedures
- **Endpoint**: `GET /surgical/procedures/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Procedure
- **Endpoint**: `POST /surgical/procedures/`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "cpt_code": "string",
  "typical_duration_minutes": 0,
  "requires_blood_products": false,
  "average_blood_loss_ml": 0,
  "default_price": 0.0,
  "description": "string",
  "pre_op_instructions": "string",
  "post_op_instructions": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "procedure": {
    "id": 0,
    "code": "string",
    "name": "string",
    "cpt_code": "string",
    "typical_duration_minutes": 0,
    "requires_blood_products": false,
    "average_blood_loss_ml": 0,
    "default_price": 0.0,
    "description": "string",
    "pre_op_instructions": "string",
    "post_op_instructions": "string"
  }
}
```
---

#### Form/Action: Get Procedure
- **Endpoint**: `GET /surgical/procedures/{procedure_id}`
---

#### Form/Action: Soft Delete Procedure
- **Endpoint**: `DELETE /surgical/procedures/{procedure_id}`
---


### 📦 Module: SURGICAL_CASE (File: surgical_routes.py)
#### Form/Action: List Cases For Visit
- **Endpoint**: `GET /surgical/cases/visits/{visit_id}`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Case Worklist
- **Endpoint**: `GET /surgical/cases/worklist`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Book Case
- **Endpoint**: `POST /surgical/cases/`
**Request Payload:**
```json
{
  "patient_id": 0,
  "procedure_catalog_id": 0,
  "visit_id": 0,
  "facility_id": 0,
  "operating_theatre_id": 0,
  "is_emergency": false,
  "asa_class": "string",
  "anaesthesia_type": "string",
  "scheduled_start_at": "2026-05-09T00:00:00Z",
  "scheduled_end_at": "2026-05-09T00:00:00Z",
  "diagnosis_text": "string",
  "auto_capture_charge": false
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "case": {
    "id": 0,
    "case_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "facility_id": 0,
    "procedure_catalog_id": 0,
    "operating_theatre_id": 0,
    "status": "string",
    "is_emergency": false,
    "asa_class": "string",
    "anaesthesia_type": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "pre_op_started_at": "2026-05-09T00:00:00Z",
    "incision_at": "2026-05-09T00:00:00Z",
    "closure_at": "2026-05-09T00:00:00Z",
    "out_of_theatre_at": "2026-05-09T00:00:00Z",
    "diagnosis_text": "string",
    "findings_text": "string",
    "cancellation_reason": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Case
- **Endpoint**: `GET /surgical/cases/{case_id}`
---

#### Form/Action: Confirm Case
- **Endpoint**: `POST /surgical/cases/{case_id}/confirm`
**Request Payload:**
```json
{
  "note": "string",
  "findings": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "case": {
    "id": 0,
    "case_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "facility_id": 0,
    "procedure_catalog_id": 0,
    "operating_theatre_id": 0,
    "status": "string",
    "is_emergency": false,
    "asa_class": "string",
    "anaesthesia_type": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "pre_op_started_at": "2026-05-09T00:00:00Z",
    "incision_at": "2026-05-09T00:00:00Z",
    "closure_at": "2026-05-09T00:00:00Z",
    "out_of_theatre_at": "2026-05-09T00:00:00Z",
    "diagnosis_text": "string",
    "findings_text": "string",
    "cancellation_reason": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Start Pre Op
- **Endpoint**: `POST /surgical/cases/{case_id}/start-pre-op`
**Request Payload:**
```json
{
  "note": "string",
  "findings": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "case": {
    "id": 0,
    "case_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "facility_id": 0,
    "procedure_catalog_id": 0,
    "operating_theatre_id": 0,
    "status": "string",
    "is_emergency": false,
    "asa_class": "string",
    "anaesthesia_type": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "pre_op_started_at": "2026-05-09T00:00:00Z",
    "incision_at": "2026-05-09T00:00:00Z",
    "closure_at": "2026-05-09T00:00:00Z",
    "out_of_theatre_at": "2026-05-09T00:00:00Z",
    "diagnosis_text": "string",
    "findings_text": "string",
    "cancellation_reason": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Into Theatre
- **Endpoint**: `POST /surgical/cases/{case_id}/into-theatre`
**Request Payload:**
```json
{
  "note": "string",
  "findings": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "case": {
    "id": 0,
    "case_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "facility_id": 0,
    "procedure_catalog_id": 0,
    "operating_theatre_id": 0,
    "status": "string",
    "is_emergency": false,
    "asa_class": "string",
    "anaesthesia_type": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "pre_op_started_at": "2026-05-09T00:00:00Z",
    "incision_at": "2026-05-09T00:00:00Z",
    "closure_at": "2026-05-09T00:00:00Z",
    "out_of_theatre_at": "2026-05-09T00:00:00Z",
    "diagnosis_text": "string",
    "findings_text": "string",
    "cancellation_reason": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Case Incision
- **Endpoint**: `POST /surgical/cases/{case_id}/incision`
**Request Payload:**
```json
{
  "note": "string",
  "findings": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "case": {
    "id": 0,
    "case_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "facility_id": 0,
    "procedure_catalog_id": 0,
    "operating_theatre_id": 0,
    "status": "string",
    "is_emergency": false,
    "asa_class": "string",
    "anaesthesia_type": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "pre_op_started_at": "2026-05-09T00:00:00Z",
    "incision_at": "2026-05-09T00:00:00Z",
    "closure_at": "2026-05-09T00:00:00Z",
    "out_of_theatre_at": "2026-05-09T00:00:00Z",
    "diagnosis_text": "string",
    "findings_text": "string",
    "cancellation_reason": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Case Closure
- **Endpoint**: `POST /surgical/cases/{case_id}/closure`
**Request Payload:**
```json
{
  "note": "string",
  "findings": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "case": {
    "id": 0,
    "case_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "facility_id": 0,
    "procedure_catalog_id": 0,
    "operating_theatre_id": 0,
    "status": "string",
    "is_emergency": false,
    "asa_class": "string",
    "anaesthesia_type": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "pre_op_started_at": "2026-05-09T00:00:00Z",
    "incision_at": "2026-05-09T00:00:00Z",
    "closure_at": "2026-05-09T00:00:00Z",
    "out_of_theatre_at": "2026-05-09T00:00:00Z",
    "diagnosis_text": "string",
    "findings_text": "string",
    "cancellation_reason": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Case Post Op
- **Endpoint**: `POST /surgical/cases/{case_id}/post-op`
**Request Payload:**
```json
{
  "note": "string",
  "findings": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "case": {
    "id": 0,
    "case_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "facility_id": 0,
    "procedure_catalog_id": 0,
    "operating_theatre_id": 0,
    "status": "string",
    "is_emergency": false,
    "asa_class": "string",
    "anaesthesia_type": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "pre_op_started_at": "2026-05-09T00:00:00Z",
    "incision_at": "2026-05-09T00:00:00Z",
    "closure_at": "2026-05-09T00:00:00Z",
    "out_of_theatre_at": "2026-05-09T00:00:00Z",
    "diagnosis_text": "string",
    "findings_text": "string",
    "cancellation_reason": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Case Complete
- **Endpoint**: `POST /surgical/cases/{case_id}/complete`
**Request Payload:**
```json
{
  "note": "string",
  "findings": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "case": {
    "id": 0,
    "case_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "facility_id": 0,
    "procedure_catalog_id": 0,
    "operating_theatre_id": 0,
    "status": "string",
    "is_emergency": false,
    "asa_class": "string",
    "anaesthesia_type": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "pre_op_started_at": "2026-05-09T00:00:00Z",
    "incision_at": "2026-05-09T00:00:00Z",
    "closure_at": "2026-05-09T00:00:00Z",
    "out_of_theatre_at": "2026-05-09T00:00:00Z",
    "diagnosis_text": "string",
    "findings_text": "string",
    "cancellation_reason": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Case Cancel
- **Endpoint**: `POST /surgical/cases/{case_id}/cancel`
**Request Payload:**
```json
{
  "note": "string",
  "findings": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "case": {
    "id": 0,
    "case_no": "string",
    "patient_id": 0,
    "visit_id": 0,
    "facility_id": 0,
    "procedure_catalog_id": 0,
    "operating_theatre_id": 0,
    "status": "string",
    "is_emergency": false,
    "asa_class": "string",
    "anaesthesia_type": "string",
    "scheduled_start_at": "2026-05-09T00:00:00Z",
    "scheduled_end_at": "2026-05-09T00:00:00Z",
    "pre_op_started_at": "2026-05-09T00:00:00Z",
    "incision_at": "2026-05-09T00:00:00Z",
    "closure_at": "2026-05-09T00:00:00Z",
    "out_of_theatre_at": "2026-05-09T00:00:00Z",
    "diagnosis_text": "string",
    "findings_text": "string",
    "cancellation_reason": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: SURGICAL_TEAM (File: surgical_routes.py)
#### Form/Action: List Team
- **Endpoint**: `GET /surgical/team/cases/{case_id}`
---

#### Form/Action: Add Team Member
- **Endpoint**: `POST /surgical/team/`
**Request Payload:**
```json
{
  "surgical_case_id": 0,
  "staff_profile_id": 0,
  "role": "string",
  "is_lead": false,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "member": {
    "id": 0,
    "surgical_case_id": 0,
    "staff_profile_id": 0,
    "role": "string",
    "is_lead": false,
    "notes": "string"
  }
}
```
---

#### Form/Action: Remove Team Member
- **Endpoint**: `DELETE /surgical/team/{member_id}`
---


### 📦 Module: SURGICAL_CONSENT (File: surgical_routes.py)
#### Form/Action: List Consents
- **Endpoint**: `GET /surgical/consents/cases/{case_id}`
---

#### Form/Action: Record Consent
- **Endpoint**: `POST /surgical/consents/`
**Request Payload:**
```json
{
  "surgical_case_id": 0,
  "consent_text": "string",
  "consent_signed_by": "string",
  "relationship_to_patient": "string",
  "witnessed_by_staff_id": 0,
  "signed_at": "2026-05-09T00:00:00Z",
  "signature_image_url": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "consent": {
    "id": 0,
    "surgical_case_id": 0,
    "consent_text": "string",
    "consent_signed_by": "string",
    "relationship_to_patient": "string",
    "witnessed_by_staff_id": 0,
    "signed_at": "2026-05-09T00:00:00Z",
    "signature_image_url": "string"
  }
}
```
---


### 📦 Module: SURGICAL_CHECKLIST (File: surgical_routes.py)
#### Form/Action: List Checklists
- **Endpoint**: `GET /surgical/checklists/cases/{case_id}`
---

#### Form/Action: Record Checklist
- **Endpoint**: `POST /surgical/checklists/`
**Request Payload:**
```json
{
  "surgical_case_id": 0,
  "phase": "string",
  "items": "string",
  "completed_by_staff_id": 0,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "checklist": {
    "id": 0,
    "surgical_case_id": 0,
    "phase": "string",
    "completed_at": "2026-05-09T00:00:00Z",
    "completed_by_staff_id": 0,
    "items": "string",
    "notes": "string"
  }
}
```
---


### 📦 Module: SURGICAL_ANAESTHESIA (File: surgical_routes.py)
#### Form/Action: List Anaesthesia
- **Endpoint**: `GET /surgical/anaesthesia/cases/{case_id}`
---

#### Form/Action: Record Anaesthesia
- **Endpoint**: `POST /surgical/anaesthesia/`
**Request Payload:**
```json
{
  "surgical_case_id": 0,
  "anaesthetist_staff_id": 0,
  "anaesthesia_type": "string",
  "induction_time": "2026-05-09T00:00:00Z",
  "emergence_time": "2026-05-09T00:00:00Z",
  "agents": "string",
  "monitoring_intervals": "string",
  "complications": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "record": {
    "id": 0,
    "surgical_case_id": 0,
    "anaesthetist_staff_id": 0,
    "anaesthesia_type": "string",
    "induction_time": "2026-05-09T00:00:00Z",
    "emergence_time": "2026-05-09T00:00:00Z",
    "agents": "string",
    "monitoring_intervals": "string",
    "complications": "string",
    "notes": "string"
  }
}
```
---


### 📦 Module: SURGICAL_NOTE (File: surgical_routes.py)
#### Form/Action: List Notes
- **Endpoint**: `GET /surgical/notes/cases/{case_id}`
---

#### Form/Action: Add Note
- **Endpoint**: `POST /surgical/notes/`
**Request Payload:**
```json
{
  "surgical_case_id": 0,
  "note": "string",
  "note_type": "string",
  "author_staff_id": 0,
  "captured_at": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "theatre_note": {
    "id": 0,
    "surgical_case_id": 0,
    "author_staff_id": 0,
    "note_type": "string",
    "note": "string",
    "captured_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: SURGICAL_INSTRUMENT (File: surgical_routes.py)
#### Form/Action: List Instrument Sets
- **Endpoint**: `GET /surgical/instrument-sets/`
---

#### Form/Action: Create Instrument Set
- **Endpoint**: `POST /surgical/instrument-sets/`
**Request Payload:**
```json
{
  "code": "string",
  "name": "string",
  "facility_id": 0,
  "contents": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "instrument_set": {
    "id": 0,
    "code": "string",
    "name": "string",
    "facility_id": 0,
    "surgical_case_id": 0,
    "sterilization_status": "string",
    "last_autoclaved_at": "2026-05-09T00:00:00Z",
    "next_required_sterilization_at": "2026-05-09T00:00:00Z",
    "contents": "string",
    "notes": "string"
  }
}
```
---

#### Form/Action: Get Instrument Set
- **Endpoint**: `GET /surgical/instrument-sets/{set_id}`
---

#### Form/Action: Assign Instrument Set
- **Endpoint**: `POST /surgical/instrument-sets/{set_id}/assign`
**Request Payload:**
```json
{
  "surgical_case_id": 0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "instrument_set": {
    "id": 0,
    "code": "string",
    "name": "string",
    "facility_id": 0,
    "surgical_case_id": 0,
    "sterilization_status": "string",
    "last_autoclaved_at": "2026-05-09T00:00:00Z",
    "next_required_sterilization_at": "2026-05-09T00:00:00Z",
    "contents": "string",
    "notes": "string"
  }
}
```
---

#### Form/Action: Log Sterilization
- **Endpoint**: `POST /surgical/instrument-sets/{set_id}/sterilization`
**Request Payload:**
```json
{
  "instrument_set_id": 0,
  "performed_by_staff_id": 0,
  "cycle_started_at": "2026-05-09T00:00:00Z",
  "cycle_ended_at": "2026-05-09T00:00:00Z",
  "method": "string",
  "machine_identifier": "string",
  "indicator_passed": false,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "log": {
    "id": 0,
    "instrument_set_id": 0,
    "performed_by_staff_id": 0,
    "cycle_started_at": "2026-05-09T00:00:00Z",
    "cycle_ended_at": "2026-05-09T00:00:00Z",
    "method": "string",
    "machine_identifier": "string",
    "indicator_passed": false,
    "notes": "string"
  }
}
```
---


### 📦 Module: INSURANCE_BATCH (File: insurance_claim_routes.py)
#### Form/Action: List Batches
- **Endpoint**: `GET /insurance/batches/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Batch
- **Endpoint**: `POST /insurance/batches/`
**Request Payload:**
```json
{
  "insurance_provider_id": 0,
  "facility_id": 0,
  "period_start": "2026-05-09T00:00:00Z",
  "period_end": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "batch": {
    "id": 0,
    "batch_no": "string",
    "insurance_provider_id": 0,
    "facility_id": 0,
    "submitted_by_staff_id": 0,
    "status": "string",
    "period_start": "2026-05-09T00:00:00Z",
    "period_end": "2026-05-09T00:00:00Z",
    "submitted_at": "2026-05-09T00:00:00Z",
    "acknowledged_at": "2026-05-09T00:00:00Z",
    "total_claims": 0,
    "total_billed_amount": 0.0,
    "total_approved_amount": 0.0,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Batch
- **Endpoint**: `GET /insurance/batches/{batch_id}`
---

#### Form/Action: Submit Batch
- **Endpoint**: `POST /insurance/batches/{batch_id}/submit`
**Request Payload:**
```json
{
  "submitted_by_staff_id": 0,
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "batch": {
    "id": 0,
    "batch_no": "string",
    "insurance_provider_id": 0,
    "facility_id": 0,
    "submitted_by_staff_id": 0,
    "status": "string",
    "period_start": "2026-05-09T00:00:00Z",
    "period_end": "2026-05-09T00:00:00Z",
    "submitted_at": "2026-05-09T00:00:00Z",
    "acknowledged_at": "2026-05-09T00:00:00Z",
    "total_claims": 0,
    "total_billed_amount": 0.0,
    "total_approved_amount": 0.0,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Acknowledge Batch
- **Endpoint**: `POST /insurance/batches/{batch_id}/acknowledge`
**Request Payload:**
```json
{
  "acknowledged_at": "2026-05-09T00:00:00Z",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "batch": {
    "id": 0,
    "batch_no": "string",
    "insurance_provider_id": 0,
    "facility_id": 0,
    "submitted_by_staff_id": 0,
    "status": "string",
    "period_start": "2026-05-09T00:00:00Z",
    "period_end": "2026-05-09T00:00:00Z",
    "submitted_at": "2026-05-09T00:00:00Z",
    "acknowledged_at": "2026-05-09T00:00:00Z",
    "total_claims": 0,
    "total_billed_amount": 0.0,
    "total_approved_amount": 0.0,
    "notes": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: INSURANCE_CLAIM (File: insurance_claim_routes.py)
#### Form/Action: List Claims
- **Endpoint**: `GET /insurance/claims/`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "items": "string",
  "count": 0,
  "meta": "string"
}
```
---

#### Form/Action: Create Claim
- **Endpoint**: `POST /insurance/claims/`
**Request Payload:**
```json
{
  "patient_id": 0,
  "patient_insurance_id": 0,
  "insurance_provider_id": 0,
  "visit_id": 0,
  "invoice_id": 0,
  "facility_id": 0,
  "batch_id": 0,
  "service_date": "2026-05-09T00:00:00Z",
  "diagnosis_codes": "string",
  "primary_diagnosis_text": "string",
  "notes": "string",
  "items": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "claim": {
    "id": 0,
    "claim_no": "string",
    "batch_id": 0,
    "patient_id": 0,
    "patient_insurance_id": 0,
    "insurance_provider_id": 0,
    "visit_id": 0,
    "invoice_id": 0,
    "facility_id": 0,
    "status": "string",
    "service_date": "2026-05-09T00:00:00Z",
    "diagnosis_codes": "string",
    "primary_diagnosis_text": "string",
    "billed_amount": 0.0,
    "approved_amount": 0.0,
    "rejected_amount": 0.0,
    "patient_responsibility_amount": 0.0,
    "paid_amount": 0.0,
    "submitted_at": "2026-05-09T00:00:00Z",
    "notes": "string",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Get Claim
- **Endpoint**: `GET /insurance/claims/{claim_id}`
---

#### Form/Action: Submit Claim
- **Endpoint**: `POST /insurance/claims/{claim_id}/submit`
**Request Payload:**
```json
{
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "claim": {
    "id": 0,
    "claim_no": "string",
    "batch_id": 0,
    "patient_id": 0,
    "patient_insurance_id": 0,
    "insurance_provider_id": 0,
    "visit_id": 0,
    "invoice_id": 0,
    "facility_id": 0,
    "status": "string",
    "service_date": "2026-05-09T00:00:00Z",
    "diagnosis_codes": "string",
    "primary_diagnosis_text": "string",
    "billed_amount": 0.0,
    "approved_amount": 0.0,
    "rejected_amount": 0.0,
    "patient_responsibility_amount": 0.0,
    "paid_amount": 0.0,
    "submitted_at": "2026-05-09T00:00:00Z",
    "notes": "string",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---

#### Form/Action: Withdraw Claim
- **Endpoint**: `POST /insurance/claims/{claim_id}/withdraw`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "claim": {
    "id": 0,
    "claim_no": "string",
    "batch_id": 0,
    "patient_id": 0,
    "patient_insurance_id": 0,
    "insurance_provider_id": 0,
    "visit_id": 0,
    "invoice_id": 0,
    "facility_id": 0,
    "status": "string",
    "service_date": "2026-05-09T00:00:00Z",
    "diagnosis_codes": "string",
    "primary_diagnosis_text": "string",
    "billed_amount": 0.0,
    "approved_amount": 0.0,
    "rejected_amount": 0.0,
    "patient_responsibility_amount": 0.0,
    "paid_amount": 0.0,
    "submitted_at": "2026-05-09T00:00:00Z",
    "notes": "string",
    "items": "string",
    "created_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: INSURANCE_AUTH (File: insurance_claim_routes.py)
#### Form/Action: List Authorizations
- **Endpoint**: `GET /insurance/authorizations/claims/{claim_id}`
---

#### Form/Action: Request Authorization
- **Endpoint**: `POST /insurance/authorizations/`
**Request Payload:**
```json
{
  "patient_insurance_id": 0,
  "requested_service": "string",
  "requested_amount": 0.0,
  "claim_id": 0,
  "requested_at": "2026-05-09T00:00:00Z",
  "decision_reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "authorization": {
    "id": 0,
    "claim_id": 0,
    "patient_insurance_id": 0,
    "authorization_no": "string",
    "requested_service": "string",
    "requested_amount": 0.0,
    "approved_amount": 0.0,
    "status": "string",
    "requested_at": "2026-05-09T00:00:00Z",
    "decided_at": "2026-05-09T00:00:00Z",
    "valid_from": "2026-05-09T00:00:00Z",
    "valid_until": "2026-05-09T00:00:00Z",
    "decision_reason": "string"
  }
}
```
---

#### Form/Action: Decide Authorization
- **Endpoint**: `POST /insurance/authorizations/{auth_id}/decide`
**Request Payload:**
```json
{
  "decision": "string",
  "authorization_no": "string",
  "approved_amount": 0.0,
  "valid_from": "2026-05-09T00:00:00Z",
  "valid_until": "2026-05-09T00:00:00Z",
  "decision_reason": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "authorization": {
    "id": 0,
    "claim_id": 0,
    "patient_insurance_id": 0,
    "authorization_no": "string",
    "requested_service": "string",
    "requested_amount": 0.0,
    "approved_amount": 0.0,
    "status": "string",
    "requested_at": "2026-05-09T00:00:00Z",
    "decided_at": "2026-05-09T00:00:00Z",
    "valid_from": "2026-05-09T00:00:00Z",
    "valid_until": "2026-05-09T00:00:00Z",
    "decision_reason": "string"
  }
}
```
---


### 📦 Module: INSURANCE_ADJUDICATION (File: insurance_claim_routes.py)
#### Form/Action: List Adjudications
- **Endpoint**: `GET /insurance/adjudications/claims/{claim_id}`
---

#### Form/Action: Record Adjudication
- **Endpoint**: `POST /insurance/adjudications/`
**Request Payload:**
```json
{
  "claim_id": 0,
  "outcome": "string",
  "approved_amount": 0.0,
  "rejected_amount": 0.0,
  "adjudication_no": "string",
  "rejection_codes": "string",
  "explanation_of_benefit": "string",
  "adjudicated_at": "2026-05-09T00:00:00Z"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "adjudication": {
    "id": 0,
    "claim_id": 0,
    "adjudication_no": "string",
    "outcome": "string",
    "approved_amount": 0.0,
    "rejected_amount": 0.0,
    "rejection_codes": "string",
    "explanation_of_benefit": "string",
    "adjudicated_at": "2026-05-09T00:00:00Z"
  }
}
```
---


### 📦 Module: INSURANCE_PAYMENT (File: insurance_claim_routes.py)
#### Form/Action: List Payments
- **Endpoint**: `GET /insurance/payments/claims/{claim_id}`
---

#### Form/Action: Record Payment
- **Endpoint**: `POST /insurance/payments/`
**Request Payload:**
```json
{
  "claim_id": 0,
  "payment_reference": "string",
  "amount": 0.0,
  "currency": "string",
  "paid_at": "2026-05-09T00:00:00Z",
  "payment_method": "string",
  "notes": "string"
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "payment": {
    "id": 0,
    "claim_id": 0,
    "payment_reference": "string",
    "amount": 0.0,
    "currency": "string",
    "paid_at": "2026-05-09T00:00:00Z",
    "payment_method": "string",
    "notes": "string"
  }
}
```
---


### 📦 Module: INSURANCE_APPEAL (File: insurance_claim_routes.py)
#### Form/Action: List Appeals
- **Endpoint**: `GET /insurance/appeals/claims/{claim_id}`
---

#### Form/Action: Submit Appeal
- **Endpoint**: `POST /insurance/appeals/`
**Request Payload:**
```json
{
  "claim_id": 0,
  "appeal_text": "string",
  "submitted_by_staff_id": 0,
  "additional_evidence_url": "string",
  "additional_amount_requested": 0.0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appeal": {
    "id": 0,
    "claim_id": 0,
    "appeal_no": "string",
    "status": "string",
    "submitted_by_staff_id": 0,
    "submitted_at": "2026-05-09T00:00:00Z",
    "decided_at": "2026-05-09T00:00:00Z",
    "decision_text": "string",
    "appeal_text": "string",
    "additional_evidence_url": "string",
    "additional_amount_requested": 0.0,
    "additional_amount_approved": 0.0
  }
}
```
---

#### Form/Action: Decide Appeal
- **Endpoint**: `POST /insurance/appeals/{appeal_id}/decide`
**Request Payload:**
```json
{
  "decision": "string",
  "decision_text": "string",
  "additional_amount_approved": 0.0
}
```
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "appeal": {
    "id": 0,
    "claim_id": 0,
    "appeal_no": "string",
    "status": "string",
    "submitted_by_staff_id": 0,
    "submitted_at": "2026-05-09T00:00:00Z",
    "decided_at": "2026-05-09T00:00:00Z",
    "decision_text": "string",
    "appeal_text": "string",
    "additional_evidence_url": "string",
    "additional_amount_requested": 0.0,
    "additional_amount_approved": 0.0
  }
}
```
---


### 📦 Module: MEDICAL_HISTORY (File: medical_history_routes.py)
#### Form/Action: Get Patient Medical History
- **Endpoint**: `GET /patients/{patient_id}/medical-history`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "history": {
    "patient": {
      "id": "...",
      "hospital_number": "...",
      "first_name": "...",
      "last_name": "...",
      "middle_name": "...",
      "date_of_birth": "...",
      "age_years": "...",
      "gender": "...",
      "blood_group": "...",
      "genotype": "...",
      "allergies": "...",
      "patient_type": "...",
      "phone_number": "...",
      "email": "...",
      "chronic_conditions": "..."
    },
    "summary": "string",
    "allergies": "string",
    "visits": "string",
    "consultations": "string",
    "diagnoses": "string",
    "lab_orders": "string",
    "radiology_orders": "string",
    "prescriptions": "string",
    "procedure_orders": "string",
    "surgical_cases": "string",
    "admissions": "string",
    "triage_assessments": "string",
    "vital_signs": "string"
  }
}
```
---

#### Form/Action: Get History For Visit
- **Endpoint**: `GET /visits/{visit_id}/medical-history`
**Response Body:**
```json
{
  "success": false,
  "message": "string",
  "history": {
    "patient": {
      "id": "...",
      "hospital_number": "...",
      "first_name": "...",
      "last_name": "...",
      "middle_name": "...",
      "date_of_birth": "...",
      "age_years": "...",
      "gender": "...",
      "blood_group": "...",
      "genotype": "...",
      "allergies": "...",
      "patient_type": "...",
      "phone_number": "...",
      "email": "...",
      "chronic_conditions": "..."
    },
    "summary": "string",
    "allergies": "string",
    "visits": "string",
    "consultations": "string",
    "diagnoses": "string",
    "lab_orders": "string",
    "radiology_orders": "string",
    "prescriptions": "string",
    "procedure_orders": "string",
    "surgical_cases": "string",
    "admissions": "string",
    "triage_assessments": "string",
    "vital_signs": "string"
  }
}
```
---


### 📦 Module: REPORT (File: report_routes.py)

