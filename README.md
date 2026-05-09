# Carepoint HMS (Hospital Management System)

Carepoint HMS is a comprehensive, multi-tenant SaaS healthcare platform designed to streamline hospital operations, enhance clinical workflows, and manage patient care efficiently. Built with modern, secure architecture, it supports everything from single clinics to multi-branch hospital networks.

## 🚀 Core Features & Capabilities

### 🏢 Multi-Tenant SaaS Platform Core
* **Tenant Isolation:** Secure data isolation using schema/database-per-tenant architecture.
* **Subscription & Billing:** Automated lifecycle management, tier-based access limits, usage tracking, and SaaS-level invoicing.
* **Custom Domains:** Support for custom tenant URLs (e.g., `portal.acmeclinic.com`) with DNS verification and SSL tracking.
* **Module Access Toggling:** Dynamically activate or deactivate clinical and administrative modules per tenant based on subscription tier.
* **Automated Database Backups:** Scheduled tenant-level and master database backups with retention policies.
* **Tenant Usage Tracking:** Granular monitoring of storage, users, and API/communication consumption.
* **Tenant Dashboard:** High-level metrics and system overviews for tenant administrators.
* **Tenant Settings & Payment Methods:** Custom branding, localized timezone/currency configurations, and payment method options per tenant.

### 🔐 Security & Access Control
* **Role-Based Access Control (RBAC):** Fine-grained, customizable permission hierarchies for different hospital staff.
* **Two-Factor Authentication (2FA):** Enhanced account security using OTPs via email/SMS.
* **SaaS Support Access Grants:** Auditable, time-bounded access approvals allowing platform administrators to securely assist tenants.
* **User Invitations:** Secure email-based staff invitation and onboarding flows.
* **Comprehensive Audit Logs & Compliance:** System-wide logging of all sensitive actions, data modifications, and PHI access.

### 🧑‍⚕️ Patient & Outpatient (OPD) Management
* **Patient Registration & Identity:** Streamlined demographic capture, unique hospital numbers, and identity verification.
* **Patient Portals:** Secure self-service access for patients to view records, book appointments, and pay bills.
* **Queue & Triage:** Dynamic patient flow management, queue routing, and upfront vitals tracking.
* **Visit Flows & Service Points:** Customizable clinical pathways mapping a patient's journey across different Service Delivery Points.
* **Medical History & Vitals:** Longitudinal electronic health records (EHR), clinical notes, and vital sign flowsheets.
* **Referral Management:** Tracking of internal department transfers and external specialist referrals.
* **Patient Loyalty & Membership:** Programs to manage patient loyalty tiers, membership cards, and discount structures.

### 🛏️ Inpatient (IPD), Wards & Surgical Care
* **Ward & Bed Management:** Real-time dashboards for bed occupancy, ward transfers, and capacity planning.
* **Admissions & Discharges:** End-to-end IPD workflow tracking from admission requests to discharge summaries.
* **Surgical & Procedure Management:** Comprehensive scheduling and resource management for operating theatres, surgical teams, and pre/post-op care.
* **Ambulance Management:** Fleet tracking, dispatch, and emergency response coordination.

### 🩺 Clinical Workflows & Consultations
* **Doctor Calendars & Appointments:** Advanced scheduling with recurring appointments, availability templates, and extensions.
* **Consultations & Diagnoses:** Clinician dashboards for recording symptoms, ICD-10 diagnoses, and treatment plans.
* **E-Prescriptions & Adherence:** Electronic prescription generation with medication adherence tracking and refill alerts.
* **Clinical Templates:** Customizable templates for clinical notes and standard operating procedures.

### 🧪 Laboratory & Radiology (LIS / RIS)
* **Laboratory Order Management:** End-to-end processing of diagnostic requests, sample collections, and result publications.
* **Radiology Information System (RIS):** Management of radiology exams, imaging modalities, and radiologist reports.

### 💊 Pharmacy, Procurement & Inventory
* **Inventory Control:** Centralized tracking of drugs, consumables, and multi-store stock movements.
* **Pharmacy Dispensing:** Verification and fulfillment of clinical prescriptions at the counter.
* **Procurement:** Requisitions, purchase orders, supplier management, and goods receipt tracking.

### 💳 Billing, Payments, Insurance & Financials
* **Automated Invoicing:** Consolidated billing for consultations, procedures, lab tests, and medications.
* **Payment Processing:** Integrated cashier desk for cash/card payments and online integrations (Paystack).
* **Insurance Claims Processing:** End-to-end management of HMO claims, coverage verification, and remittances.
* **Tax Management:** Rule-based calculation of VAT, Withholding Tax, and customized tax exemptions.
* **Patient Payments & Reimbursements:** Management of patient wallets, overpayments, and refund/reimbursement workflows.

### 👥 Human Resources (HR) & Payroll
* **Staff Profiles & Onboarding:** Complete employee lifecycle management, document storage, and digital contracts.
* **Leave Requests:** Configurable request and approval workflows for annual leave, sick days, and holidays.
* **Shift & Roster Management:** Planning and publishing of clinical duty rosters and shift schedules.
* **Timesheets & Attendance:** Tracking of clock-ins, clock-outs, and overtime.
* **Payroll & Salary Advances:** Generation of payslips, deduction tracking, and management of employee salary advance requests.
* **Approvals Workflow:** Centralized multi-tier approval system for HR, financial, and administrative requests.

### 🔔 Communications, Reporting & Integrations
* **Omnichannel Notifications:** Event-driven Emails, SMS, and In-App notifications.
* **Push Devices:** Registration and management of mobile/browser push notification tokens.
* **Edge Node Syncing:** Offline-first "boundary box" architecture allowing remote clinics to operate during internet outages and sync via journals.
* **Background Scheduled Jobs:** Automated tasks (cron) for appointment reminders, database backups, and report aggregation.
* **Advanced Reporting:** Generation of tabular and graphical reports for clinical, operational, and financial metrics.
* **Third-Party Integrations:** Connectors for external accounting, EMR, and government compliance APIs.

## 🧩 Available Modules
Carepoint HMS is highly modular. Tenants can enable or disable these modules based on their subscription tier and operational needs:

* **Core Administration:** User roles, facility management, and tenant settings.
* **Outpatient Department (OPD):** Visit management, doctor consultations, and queues.
* **Inpatient Department (IPD):** Ward/bed management, admissions, and discharges.
* **Pharmacy & Inventory:** Stock management, dispensing, and procurement.
* **Laboratory (LIS):** Lab test catalogues, sample collection, and result entry.
* **Radiology (RIS):** Imaging requests, modality scheduling, and reporting.
* **Billing & Finance:** Invoices, payments, taxes, and HMO/Insurance claims.
* **Human Resources (HR):** Staff profiles, shifts, leave requests, and payroll.
* **Operating Theatre (Surgery):** Surgical scheduling and pre/post-op tracking.
* **Ambulance Services:** Fleet management and emergency dispatch tracking.
* **Patient Portal:** Self-service web access for patients.

## 🔄 Typical Clinic Flow (Patient Journey)
Carepoint HMS supports highly customizable visit flows. A standard Outpatient (OPD) flow looks like this:

1. **Registration & Check-In:** The patient arrives at the front desk, gets registered (or verified), and a new visit is initiated.
2. **Billing (Upfront - Optional):** For fee-for-service models, the patient pays for the consultation at the cashier desk.
3. **Triage & Vitals:** The patient is routed to the nursing station where vital signs (BP, Temperature, Weight, etc.) and brief triage notes are recorded.
4. **Consultation:** The patient appears on the doctor's queue. The doctor reviews vitals, records symptoms, makes diagnoses (ICD-10), and raises requests for labs, radiology, or prescriptions.
5. **Investigations (Labs/Radiology):** If tests are ordered, the patient goes to the respective department. Samples are collected/scans are done, and results are published directly to the doctor's dashboard.
6. **Pharmacy:** The patient proceeds to the pharmacy where the pharmacist reviews the electronic prescription and dispenses the medication.
7. **Final Billing & Discharge:** Any outstanding balances (e.g., for drugs or tests) are cleared, and the visit is officially closed.

## 🛠️ Tech Stack
* **Backend:** Python, FastAPI, SQLAlchemy 2.0
* **Database:** PostgreSQL (with Schema/Database per Tenant isolation)
* **Authentication:** JWT, Fernet encryption
* **Integrations:** AWS S3, Twilio (SMS), Paystack (Payments)

## 📚 API Documentation
For detailed information on integrating with the Carepoint HMS API:
* **[API Usage Guide](file:///Users/nelsonattah/Projects/carepoint_hms/API_USAGE_GUIDE.md)**: A comprehensive guide covering the application flow, request payloads, and response structures.
* **[Postman Collection](file:///Users/nelsonattah/Projects/carepoint_hms/carepoint_hms_postman_collection.json)**: The complete API collection for local testing and environment setup.
