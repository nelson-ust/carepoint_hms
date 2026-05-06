# carepoint_hms/app/core/enums.py
from __future__ import annotations

"""
carepoint_hms.app.core.enums

Centralized application enums for the Carepoint Hospital Management System.

Purpose
-------
This module stores the shared Python enumeration classes used across models,
schemas, services, and business logic.

Why this exists
---------------
Keeping enums in one place helps to:
- avoid duplicate enum definitions
- improve consistency across the application
- simplify imports in models, schemas, and services
- make future changes easier and safer

Usage
-----
Example:

    from sqlalchemy import Enum
    from app.core.enums import UserStatus

    status = mapped_column(Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE)
"""

from enum import Enum


class StringEnum(str, Enum):
    """
    Base enum class for string-backed enums.

    Benefits
    --------
    - Stores values as strings
    - Serializes more cleanly in APIs
    - Works well with SQLAlchemy Enum columns and Pydantic models
    """

    def __str__(self) -> str:
        return str(self.value)


# ============================================================
# USER / AUTH / SECURITY
# ============================================================


class UserStatus(StringEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    LOCKED = "LOCKED"
    SUSPENDED = "SUSPENDED"
    INVITED = "INVITED"


class SaaSRole(StringEnum):
    """
    Platform-level (SaaS) administrator roles.

    A platform admin's authority is governed by this role. Tenant data
    remains opaque to platform admins unless a SupportAccessGrant explicitly
    permits it for a bounded window.
    """

    SUPER_ADMIN = "SUPER_ADMIN"
    SUPPORT_ADMIN = "SUPPORT_ADMIN"
    BILLING_ADMIN = "BILLING_ADMIN"
    SYSTEM_AUDITOR = "SYSTEM_AUDITOR"


class InvitationStatus(StringEnum):
    """Lifecycle states for a tenant user invitation."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class SupportAccessStatus(StringEnum):
    """
    Lifecycle of a controlled support-access grant from a tenant to a SaaS
    admin. Grants must be explicitly approved by the tenant before they
    become usable, and they revert to EXPIRED once the window closes.
    """

    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    USED = "USED"


class SubscriptionInvoiceStatus(StringEnum):
    """
    Lifecycle of a SaaS-level subscription invoice.
    """

    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class SubscriptionPaymentStatus(StringEnum):
    """
    Lifecycle of a payment recorded against a subscription invoice.
    """

    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentGatePolicy(StringEnum):
    """
    Hospital-wide policy that controls when patients must settle charges.

    PRE_PAID: lab and pharmacy services require payment (or insurance/loyalty
        cover) before they execute. The cashier service point is inserted in
        the visit flow ahead of those steps.
    POST_PAID: charges accumulate during the visit and are settled at a
        single invoice on discharge from OPD.
    HYBRID: pre-paid for lab and pharmacy; post-paid for everything else.
    """

    PRE_PAID = "PRE_PAID"
    POST_PAID = "POST_PAID"
    HYBRID = "HYBRID"


class PaymentMethod(StringEnum):
    CASH = "CASH"
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    MOBILE_MONEY = "MOBILE_MONEY"
    INSURANCE = "INSURANCE"
    LOYALTY = "LOYALTY"
    WAIVER = "WAIVER"
    MEMBERSHIP_CARD = "MEMBERSHIP_CARD"
    PAYSTACK = "PAYSTACK"
    FLUTTERWAVE = "FLUTTERWAVE"
    STRIPE = "STRIPE"
    OTHER = "OTHER"


class PaymentChannel(StringEnum):
    """
    Logical payment channel selected by a patient (or by the cashier on
    their behalf). The patient-payment dispatcher routes the payment to a
    different backend based on this value:

      * CASHIER     → manual receipt at a cashier point (cash, card, POS)
      * MEMBERSHIP_CARD → debit the patient's membership-card balance
      * LOYALTY     → redeem loyalty points against the invoice
      * GATEWAY     → initiate an online charge via the tenant's
                      configured online gateway (Paystack/Flutterwave/Stripe…)
      * BANK_TRANSFER → manual reconciliation of an offline transfer
      * INSURANCE   → claim against an insurer; settled out of band
    """

    CASHIER = "CASHIER"
    MEMBERSHIP_CARD = "MEMBERSHIP_CARD"
    LOYALTY = "LOYALTY"
    GATEWAY = "GATEWAY"
    BANK_TRANSFER = "BANK_TRANSFER"
    INSURANCE = "INSURANCE"


class PaymentProvider(StringEnum):
    """
    External payment provider for online gateway transactions.

    ``MANUAL`` is used when the channel is cashier / cash / bank-transfer
    and no third-party API is involved.
    """

    PAYSTACK = "PAYSTACK"
    FLUTTERWAVE = "FLUTTERWAVE"
    STRIPE = "STRIPE"
    MONNIFY = "MONNIFY"
    REMITA = "REMITA"
    MANUAL = "MANUAL"


class EmailProvider(StringEnum):
    """
    Outbound-email provider for tenant-configured email systems.

    Each tenant points the platform at *their own* email infrastructure
    so that messages to their patients/users come from a sender they
    control (their own ``no-reply@hospital.com`` address, branded footer,
    custom signing domain, etc.). The platform's global SMTP remains for
    SaaS-level communication only (subscription invoices, registration
    acknowledgements).
    """

    SMTP = "SMTP"
    SENDGRID = "SENDGRID"
    SES = "SES"
    MAILGUN = "MAILGUN"
    POSTMARK = "POSTMARK"
    RESEND = "RESEND"


class BillingStatus(StringEnum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    INVOICED = "INVOICED"
    SETTLED = "SETTLED"
    CANCELLED = "CANCELLED"


class TwoFactorType(StringEnum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    AUTHENTICATOR = "AUTHENTICATOR"


# ============================================================
# SAAS / SUBSCRIPTION
# ============================================================


class SubscriptionStatus(StringEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    TRIALING = "TRIALING"
    SUSPENDED = "SUSPENDED"


class SubscriptionInterval(StringEnum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class TwoFactorPurpose(StringEnum):
    LOGIN = "LOGIN"
    PASSWORD_RESET = "PASSWORD_RESET"
    EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
    PHONE_VERIFICATION = "PHONE_VERIFICATION"
    HIGH_RISK_ACTION = "HIGH_RISK_ACTION"
    PATIENT_PORTAL_LOGIN = "PATIENT_PORTAL_LOGIN"


class NotificationChannel(StringEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    PUSH = "PUSH"


class NotificationStatus(StringEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    READ = "READ"


class NotificationEvent(StringEnum):
    """
    Canonical event codes used by :class:`TenantSetting.notification_channels`
    and the unified :class:`NotificationDispatcher`.
    """

    # Identity / users
    USER_INVITED = "user.invited"
    USER_PASSWORD_RESET = "user.password_reset"
    USER_LOCKED = "user.locked"

    # Appointments
    APPOINTMENT_CREATED = "appointment.created"
    APPOINTMENT_REMINDER = "appointment.reminder"
    APPOINTMENT_CANCELLED = "appointment.cancelled"

    # Billing & payments
    INVOICE_CREATED = "invoice.created"
    PAYMENT_RECEIVED = "payment.received"

    # SaaS subscription lifecycle
    SUBSCRIPTION_RENEWED = "subscription.renewed"
    SUBSCRIPTION_EXPIRING = "subscription.expiring"
    SUBSCRIPTION_SUSPENDED = "subscription.suspended"

    # SaaS subscription billing
    SUBSCRIPTION_INVOICE_ISSUED = "subscription.invoice.issued"
    SUBSCRIPTION_INVOICE_OVERDUE = "subscription.invoice.overdue"
    SUBSCRIPTION_PAYMENT_RECEIPT = "subscription.payment.receipt"
    SUBSCRIPTION_DUE_REMINDER = "subscription.due.reminder"

    # Approvals
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"

    # System / ops
    SYSTEM_ALERT = "system.alert"
    BACKUP_COMPLETED = "backup.completed"
    BACKUP_FAILED = "backup.failed"


class IntegrationProviderType(StringEnum):
    PAYMENT_GATEWAY = "PAYMENT_GATEWAY"
    SMS_PROVIDER = "SMS_PROVIDER"
    EMAIL_PROVIDER = "EMAIL_PROVIDER"
    ACCOUNTING_SOFTWARE = "ACCOUNTING_SOFTWARE"
    EXTERNAL_API = "EXTERNAL_API"


class DocumentTemplateType(StringEnum):
    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    LAB_REPORT = "LAB_REPORT"
    PRESCRIPTION = "PRESCRIPTION"
    ADMISSION_FORM = "ADMISSION_FORM"
 
 
class PaystackTransactionStatus(StringEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class MembershipCardStatus(StringEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    LOST = "LOST"
    EXPIRED = "EXPIRED"
 
 
class MembershipCardTransactionType(StringEnum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"


# ============================================================
# PATIENT / DEMOGRAPHICS
# ============================================================


class Gender(StringEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    UNDISCLOSED = "UNDISCLOSED"


class MaritalStatus(StringEnum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"
    SEPARATED = "SEPARATED"


class BloodGroup(StringEnum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"


class Genotype(StringEnum):
    AA = "AA"
    AS = "AS"
    AC = "AC"
    SS = "SS"
    SC = "SC"
    CC = "CC"
    UNKNOWN = "UNKNOWN"


class PatientType(StringEnum):
    OUTPATIENT = "OUTPATIENT"
    INPATIENT = "INPATIENT"
    EMERGENCY = "EMERGENCY"
    ANC = "ANC"
    PEDIATRIC = "PEDIATRIC"
    SPECIALTY = "SPECIALTY"


# ============================================================
# APPOINTMENT / VISIT / QUEUE / FLOW
# ============================================================


class AppointmentStatus(StringEnum):
    SCHEDULED = "SCHEDULED"
    ARRIVED = "ARRIVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"


class ServicePointType(StringEnum):
    REGISTRATION = "REGISTRATION"
    INSURANCE_CONFIRMATION = "INSURANCE_CONFIRMATION"
    TRIAGE = "TRIAGE"
    CLINIC = "CLINIC"
    LABORATORY = "LABORATORY"
    PHARMACY = "PHARMACY"
    CASHIER = "CASHIER"
    RADIOLOGY = "RADIOLOGY"
    WARD = "WARD"
    THEATRE = "THEATRE"
    EMERGENCY = "EMERGENCY"
    PROCEDURE_ROOM = "PROCEDURE_ROOM"
    OTHER = "OTHER"


class VisitStatus(StringEnum):
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ON_HOLD = "ON_HOLD"


class VisitPriority(StringEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"
    EMERGENCY = "EMERGENCY"


class VisitFlowStepStatus(StringEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    CALLED = "CALLED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class QueueStatus(StringEnum):
    WAITING = "WAITING"
    CALLED = "CALLED"
    SERVING = "SERVING"
    SERVED = "SERVED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"
    TRANSFERRED = "TRANSFERRED"


class EncounterStatus(StringEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    AMENDED = "AMENDED"
    CANCELLED = "CANCELLED"


# ============================================================
# ORDERS / CLINICAL / LAB / PHARMACY
# ============================================================


class OrderStatus(StringEnum):
    DRAFT = "DRAFT"
    ORDERED = "ORDERED"
    SAMPLE_COLLECTED = "SAMPLE_COLLECTED"
    IN_PROGRESS = "IN_PROGRESS"
    RESULT_READY = "RESULT_READY"
    DISPENSED = "DISPENSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class LabResultStatus(StringEnum):
    PENDING = "PENDING"
    ENTERED = "ENTERED"
    VERIFIED = "VERIFIED"
    RELEASED = "RELEASED"
    CANCELLED = "CANCELLED"


class PrescriptionStatus(StringEnum):
    DRAFT = "DRAFT"
    PRESCRIBED = "PRESCRIBED"
    PARTIALLY_DISPENSED = "PARTIALLY_DISPENSED"
    DISPENSED = "DISPENSED"
    CANCELLED = "CANCELLED"


class DispenseStatus(StringEnum):
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    DISPENSED = "DISPENSED"
    CANCELLED = "CANCELLED"


# ============================================================
# REFERRALS
# ============================================================


class ReferralStatus(StringEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReferralPriority(StringEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"
    EMERGENCY = "EMERGENCY"


# ============================================================


class InvoiceStatus(StringEnum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    WAIVED = "WAIVED"
    VOIDED = "VOIDED"
    CANCELLED = "CANCELLED"


class PaymentStatus(StringEnum):
    PENDING = "PENDING"
    SUCCESSFUL = "SUCCESSFUL"
    FAILED = "FAILED"
    REVERSED = "REVERSED"
    CANCELLED = "CANCELLED"


# ============================================================
# ADMISSION / BED MANAGEMENT
# ============================================================


class AdmissionStatus(StringEnum):
    PENDING = "PENDING"
    ADMITTED = "ADMITTED"
    TRANSFERRED = "TRANSFERRED"
    DISCHARGED = "DISCHARGED"
    CANCELLED = "CANCELLED"
    DECEASED = "DECEASED"


class BedStatus(StringEnum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    OCCUPIED = "OCCUPIED"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


# ============================================================
# INVENTORY
# ============================================================


class InventoryItemType(StringEnum):
    DRUG = "DRUG"
    CONSUMABLE = "CONSUMABLE"
    EQUIPMENT = "EQUIPMENT"
    SUPPLY = "SUPPLY"
    OTHER = "OTHER"


class StockMovementType(StringEnum):
    OPENING_BALANCE = "OPENING_BALANCE"
    PURCHASE = "PURCHASE"
    ISSUE = "ISSUE"
    DISPENSE = "DISPENSE"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"
    RETURN_IN = "RETURN_IN"
    RETURN_OUT = "RETURN_OUT"
    WRITE_OFF = "WRITE_OFF"



class AmbulanceStatus(StringEnum):
    AVAILABLE = "AVAILABLE"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    UNDER_MAINTENANCE = "UNDER_MAINTENANCE"


class AmbulanceDispatchStatus(StringEnum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    PATIENT_PICKED = "PATIENT_PICKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class MaintenanceStatus(StringEnum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class InsurancePolicyStatus(StringEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(StringEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


# ============================================================
# APPROVAL ENGINE
# ============================================================
#
# These enums power the tenant-managed approval engine. Each tenant
# defines `ApprovalFlow` rows (e.g. LEAVE_REQUEST flow, REIMBURSEMENT
# flow) with ordered `ApprovalFlowStep` rows. Steps can target multiple
# approver kinds and use a per-step decision rule.

class ApprovalSubjectType(StringEnum):
    """Domain object an approval flow is wired to."""
    LEAVE_REQUEST = "LEAVE_REQUEST"
    TIMESHEET = "TIMESHEET"
    REIMBURSEMENT = "REIMBURSEMENT"
    STAFF_REQUEST = "STAFF_REQUEST"
    OVERTIME = "OVERTIME"
    SALARY_ADVANCE = "SALARY_ADVANCE"
    PROCUREMENT = "PROCUREMENT"
    GENERIC = "GENERIC"


class ApprovalApproverKind(StringEnum):
    """How a step's approvers are resolved."""
    USER = "USER"               # specific User row
    ROLE = "ROLE"               # any user holding the named Role
    DEPARTMENT = "DEPARTMENT"   # any user assigned to the Department
    DYNAMIC = "DYNAMIC"         # resolver token (see ApprovalDynamicApprover)


class ApprovalDynamicApprover(StringEnum):
    """Tokens used when ApprovalApproverKind is DYNAMIC."""
    REQUESTER_MANAGER = "REQUESTER_MANAGER"
    DEPARTMENT_HEAD = "DEPARTMENT_HEAD"
    FACILITY_HEAD = "FACILITY_HEAD"
    HR_HEAD = "HR_HEAD"
    FINANCE_HEAD = "FINANCE_HEAD"


class ApprovalStepDecisionRule(StringEnum):
    """How a step decides 'this step is approved'."""
    ANY_OF = "ANY_OF"     # any single eligible approver advances the step
    ALL_OF = "ALL_OF"     # every named approver must approve
    N_OF_M = "N_OF_M"     # at least `required_approvals` of the eligible approvers


class ApprovalRequestStatus(StringEnum):
    """Lifecycle of an ApprovalRequest."""
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ApprovalRequestStepStatus(StringEnum):
    """Lifecycle of one step inside an in-flight ApprovalRequest."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"


class ApprovalDecisionAction(StringEnum):
    """Action recorded on an ApprovalDecision row."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    DELEGATE = "DELEGATE"
    COMMENT = "COMMENT"


class LoyaltyTransactionType(StringEnum):
    EARN = "EARN"
    REDEEM = "REDEEM"
    ADJUSTMENT = "ADJUSTMENT"
    REVERSAL = "REVERSAL"


class EmployeeScheduleStatus(StringEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class ShiftStatus(StringEnum):
    SCHEDULED = "SCHEDULED"
    ON_DUTY = "ON_DUTY"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"


class LeaveStatus(StringEnum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ReimbursementStatus(StringEnum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    PAID = "PAID"


class PerformanceStatus(StringEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEWED = "REVIEWED"
    CLOSED = "CLOSED"


class DisciplinaryActionStatus(StringEnum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class MessageStatus(StringEnum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"


class IncidentSeverity(StringEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ComplianceStatus(StringEnum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    IN_PROGRESS = "IN_PROGRESS"
    EXPIRED = "EXPIRED"


class AccreditationStatus(StringEnum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class QualityProjectStatus(StringEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# ============================================================
# FACILITY / MULTI-BRANCH
# ============================================================


class FacilityType(StringEnum):
    HEAD_OFFICE = "HEAD_OFFICE"
    MAIN_HOSPITAL = "MAIN_HOSPITAL"
    BRANCH_HOSPITAL = "BRANCH_HOSPITAL"
    CLINIC = "CLINIC"
    DIAGNOSTIC_CENTER = "DIAGNOSTIC_CENTER"
    PHARMACY_OUTLET = "PHARMACY_OUTLET"
    WAREHOUSE = "WAREHOUSE"
    OTHER = "OTHER"


class FacilityStatus(StringEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UNDER_CONSTRUCTION = "UNDER_CONSTRUCTION"
    DECOMMISSIONED = "DECOMMISSIONED"


# ============================================================
# RADIOLOGY / RIS
# ============================================================


class RadiologyModality(StringEnum):
    X_RAY = "X_RAY"
    CT = "CT"
    MRI = "MRI"
    ULTRASOUND = "ULTRASOUND"
    MAMMOGRAPHY = "MAMMOGRAPHY"
    FLUOROSCOPY = "FLUOROSCOPY"
    NUCLEAR_MEDICINE = "NUCLEAR_MEDICINE"
    PET = "PET"
    DEXA = "DEXA"
    ANGIOGRAPHY = "ANGIOGRAPHY"
    INTERVENTIONAL = "INTERVENTIONAL"
    OTHER = "OTHER"


class RadiologyOrderStatus(StringEnum):
    DRAFT = "DRAFT"
    ORDERED = "ORDERED"
    SCHEDULED = "SCHEDULED"
    CHECKED_IN = "CHECKED_IN"
    IN_PROGRESS = "IN_PROGRESS"
    PERFORMED = "PERFORMED"
    REPORTED = "REPORTED"
    RELEASED = "RELEASED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RadiologyExamStatus(StringEnum):
    SCHEDULED = "SCHEDULED"
    PATIENT_PREP = "PATIENT_PREP"
    IN_PROGRESS = "IN_PROGRESS"
    PERFORMED = "PERFORMED"
    INCOMPLETE = "INCOMPLETE"
    CANCELLED = "CANCELLED"


class RadiologyReportStatus(StringEnum):
    DRAFT = "DRAFT"
    PRELIMINARY = "PRELIMINARY"
    FINAL = "FINAL"
    AMENDED = "AMENDED"
    CANCELLED = "CANCELLED"


# ============================================================
# THEATRE & SURGICAL
# ============================================================


class TheatreStatus(StringEnum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    CLEANING = "CLEANING"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    UNDER_MAINTENANCE = "UNDER_MAINTENANCE"


class SurgicalCaseStatus(StringEnum):
    BOOKED = "BOOKED"
    CONFIRMED = "CONFIRMED"
    PRE_OP = "PRE_OP"
    IN_THEATRE = "IN_THEATRE"
    PROCEDURE_STARTED = "PROCEDURE_STARTED"
    PROCEDURE_ENDED = "PROCEDURE_ENDED"
    POST_OP = "POST_OP"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    POSTPONED = "POSTPONED"


class SurgicalRole(StringEnum):
    PRIMARY_SURGEON = "PRIMARY_SURGEON"
    ASSISTANT_SURGEON = "ASSISTANT_SURGEON"
    ANAESTHETIST = "ANAESTHETIST"
    SCRUB_NURSE = "SCRUB_NURSE"
    CIRCULATING_NURSE = "CIRCULATING_NURSE"
    PERFUSIONIST = "PERFUSIONIST"
    OBSERVER = "OBSERVER"
    OTHER = "OTHER"


class AnaesthesiaType(StringEnum):
    GENERAL = "GENERAL"
    SPINAL = "SPINAL"
    EPIDURAL = "EPIDURAL"
    REGIONAL = "REGIONAL"
    LOCAL = "LOCAL"
    SEDATION = "SEDATION"
    NONE = "NONE"


class ASAClass(StringEnum):
    """ASA Physical Status Classification."""

    ASA_I = "ASA_I"
    ASA_II = "ASA_II"
    ASA_III = "ASA_III"
    ASA_IV = "ASA_IV"
    ASA_V = "ASA_V"
    ASA_VI = "ASA_VI"


class SurgicalChecklistPhase(StringEnum):
    SIGN_IN = "SIGN_IN"
    TIME_OUT = "TIME_OUT"
    SIGN_OUT = "SIGN_OUT"


class SterilizationStatus(StringEnum):
    DIRTY = "DIRTY"
    PRE_CLEAN = "PRE_CLEAN"
    AUTOCLAVE = "AUTOCLAVE"
    READY = "READY"
    IN_USE = "IN_USE"
    QUARANTINED = "QUARANTINED"


# ============================================================
# PROCUREMENT
# ============================================================


class ProcurementRequisitionStatus(StringEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    DEPARTMENT_APPROVED = "DEPARTMENT_APPROVED"
    FINANCE_APPROVED = "FINANCE_APPROVED"
    REJECTED = "REJECTED"
    CONVERTED_TO_RFQ = "CONVERTED_TO_RFQ"
    CONVERTED_TO_PO = "CONVERTED_TO_PO"
    CANCELLED = "CANCELLED"


class RFQStatus(StringEnum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    RESPONSES_OPEN = "RESPONSES_OPEN"
    AWARDED = "AWARDED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class QuotationStatus(StringEnum):
    RECEIVED = "RECEIVED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SHORTLISTED = "SHORTLISTED"
    AWARDED = "AWARDED"
    REJECTED = "REJECTED"


class PurchaseOrderStatus(StringEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SENT_TO_SUPPLIER = "SENT_TO_SUPPLIER"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    INVOICED = "INVOICED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class GoodsReceiptStatus(StringEnum):
    DRAFT = "DRAFT"
    RECEIVED = "RECEIVED"
    QUALITY_CHECK = "QUALITY_CHECK"
    REJECTED = "REJECTED"
    POSTED_TO_INVENTORY = "POSTED_TO_INVENTORY"


class SupplierInvoiceStatus(StringEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    MATCHED = "MATCHED"
    APPROVED = "APPROVED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    DISPUTED = "DISPUTED"
    CANCELLED = "CANCELLED"


class SupplierContractStatus(StringEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"


# ============================================================
# INSURANCE CLAIMS
# ============================================================


class ClaimBatchStatus(StringEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_ADJUDICATED = "PARTIALLY_ADJUDICATED"
    ADJUDICATED = "ADJUDICATED"
    PAID = "PAID"
    REJECTED = "REJECTED"


class InsuranceClaimStatus(StringEnum):
    DRAFT = "DRAFT"
    PENDING_AUTH = "PENDING_AUTH"
    AUTHORIZED = "AUTHORIZED"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"
    APPEALED = "APPEALED"
    CLOSED = "CLOSED"


class AuthorizationStatus(StringEnum):
    REQUESTED = "REQUESTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class AdjudicationOutcome(StringEnum):
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    DENIED = "DENIED"
    PENDING = "PENDING"


class ClaimAppealStatus(StringEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    UPHELD = "UPHELD"
    OVERTURNED = "OVERTURNED"
    PARTIALLY_OVERTURNED = "PARTIALLY_OVERTURNED"
    WITHDRAWN = "WITHDRAWN"


# ============================================================
# PATIENT PORTAL
# ============================================================


class PortalAccountStatus(StringEnum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class PortalMessageStatus(StringEnum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    REPLIED = "REPLIED"
    ARCHIVED = "ARCHIVED"


class PortalMessageDirection(StringEnum):
    PATIENT_TO_PROVIDER = "PATIENT_TO_PROVIDER"
    PROVIDER_TO_PATIENT = "PROVIDER_TO_PATIENT"
    SYSTEM = "SYSTEM"


class PortalAppointmentRequestStatus(StringEnum):
    REQUESTED = "REQUESTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SCHEDULED = "SCHEDULED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"


class PortalConsentScope(StringEnum):
    DATA_SHARING = "DATA_SHARING"
    TELEHEALTH = "TELEHEALTH"
    RESEARCH = "RESEARCH"
    MARKETING = "MARKETING"
    THIRD_PARTY = "THIRD_PARTY"


# ============================================================
# INTEROPERABILITY / FHIR
# ============================================================


class IntegrationDirection(StringEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class IntegrationProtocol(StringEnum):
    FHIR_R4 = "FHIR_R4"
    FHIR_R5 = "FHIR_R5"
    HL7_V2 = "HL7_V2"
    HL7_V3 = "HL7_V3"
    DICOM = "DICOM"
    REST_JSON = "REST_JSON"
    SOAP_XML = "SOAP_XML"
    CSV_BATCH = "CSV_BATCH"
    SFTP = "SFTP"
    OTHER = "OTHER"


class IntegrationMessageStatus(StringEnum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    DELIVERED = "DELIVERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"
    DEAD_LETTERED = "DEAD_LETTERED"
    SUPERSEDED = "SUPERSEDED"


class FHIRResourceType(StringEnum):
    PATIENT = "PATIENT"
    PRACTITIONER = "PRACTITIONER"
    ENCOUNTER = "ENCOUNTER"
    OBSERVATION = "OBSERVATION"
    CONDITION = "CONDITION"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"
    SERVICE_REQUEST = "SERVICE_REQUEST"
    MEDICATION_REQUEST = "MEDICATION_REQUEST"
    MEDICATION_DISPENSE = "MEDICATION_DISPENSE"
    PROCEDURE = "PROCEDURE"
    APPOINTMENT = "APPOINTMENT"
    ALLERGY_INTOLERANCE = "ALLERGY_INTOLERANCE"
    IMMUNIZATION = "IMMUNIZATION"
    INVOICE = "INVOICE"
    COVERAGE = "COVERAGE"
    CLAIM = "CLAIM"
    EXPLANATION_OF_BENEFIT = "EXPLANATION_OF_BENEFIT"
    DOCUMENT_REFERENCE = "DOCUMENT_REFERENCE"
    OTHER = "OTHER"


class TerminologySystem(StringEnum):
    ICD_10 = "ICD_10"
    ICD_11 = "ICD_11"
    LOINC = "LOINC"
    SNOMED_CT = "SNOMED_CT"
    RX_NORM = "RX_NORM"
    NDC = "NDC"
    CPT = "CPT"
    HCPCS = "HCPCS"
    LOCAL = "LOCAL"
    OTHER = "OTHER"


# ============================================================
# DOWNTIME / OFFLINE OPERATIONS
# ============================================================


class DowntimeEventType(StringEnum):
    PLANNED = "PLANNED"
    UNPLANNED = "UNPLANNED"
    NETWORK_OUTAGE = "NETWORK_OUTAGE"
    SYSTEM_UPGRADE = "SYSTEM_UPGRADE"
    POWER_OUTAGE = "POWER_OUTAGE"
    DR_DRILL = "DR_DRILL"


class DowntimeStatus(StringEnum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    POST_RECONCILIATION = "POST_RECONCILIATION"
    CLOSED = "CLOSED"


class OfflineDeviceStatus(StringEnum):
    REGISTERED = "REGISTERED"
    SYNCED = "SYNCED"
    OUT_OF_SYNC = "OUT_OF_SYNC"
    LOCKED = "LOCKED"
    DECOMMISSIONED = "DECOMMISSIONED"


class OfflineSubmissionStatus(StringEnum):
    CAPTURED = "CAPTURED"
    PENDING_SYNC = "PENDING_SYNC"
    SYNCED = "SYNCED"
    REJECTED = "REJECTED"
    RECONCILED = "RECONCILED"
    DUPLICATE = "DUPLICATE"


class EdgeNodeStatus(StringEnum):
    """
    Lifecycle of a hospital-side on-prem edge node.

    PROVISIONED:  registered in master, waiting for first handshake.
    ACTIVE:       reachable on the public internet and syncing on schedule.
    OFFLINE:      missed its heartbeat window; serving traffic locally.
    DEGRADED:     reachable but the last sync had failures.
    DECOMMISSIONED: retired; no longer accepted for sync.
    """

    PROVISIONED = "PROVISIONED"
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    DECOMMISSIONED = "DECOMMISSIONED"


class SyncJournalOp(StringEnum):
    """The operation a SyncJournal row represents."""

    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EVENT = "EVENT"  # append-only clinical events (vitals, dispense, payment, ...)


class SyncJournalStatus(StringEnum):
    PENDING = "PENDING"
    PUSHED = "PUSHED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    CONFLICTED = "CONFLICTED"


class SyncDirection(StringEnum):
    """Which way a sync batch flowed."""

    PULL = "PULL"   # cloud → edge
    PUSH = "PUSH"   # edge → cloud


# ============================================================
# MEDICATION ADHERENCE
# ============================================================


class MedicationFrequency(StringEnum):
    """Canonical frequency codes used by MedicationSchedule."""

    DAILY = "DAILY"
    TWICE_DAILY = "TWICE_DAILY"
    THREE_TIMES_DAILY = "THREE_TIMES_DAILY"
    FOUR_TIMES_DAILY = "FOUR_TIMES_DAILY"
    EVERY_4_HOURS = "EVERY_4_HOURS"
    EVERY_6_HOURS = "EVERY_6_HOURS"
    EVERY_8_HOURS = "EVERY_8_HOURS"
    EVERY_12_HOURS = "EVERY_12_HOURS"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"
    AS_NEEDED = "AS_NEEDED"
    CUSTOM = "CUSTOM"


class MedicationScheduleStatus(StringEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    DISCONTINUED = "DISCONTINUED"


class MedicationDoseStatus(StringEnum):
    SCHEDULED = "SCHEDULED"
    TAKEN = "TAKEN"
    MISSED = "MISSED"
    SKIPPED = "SKIPPED"
    DELAYED = "DELAYED"
    STOPPED = "STOPPED"


class AdherenceLevel(StringEnum):
    """Bucketed adherence rating, used in alerts and reports."""

    EXCELLENT = "EXCELLENT"   # >= 95 %
    GOOD = "GOOD"             # 80-94 %
    FAIR = "FAIR"             # 60-79 %
    POOR = "POOR"             # < 60 %
    UNKNOWN = "UNKNOWN"


class AdherenceAlertSeverity(StringEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class FollowUpTaskStatus(StringEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class RefillStatus(StringEnum):
    DUE_SOON = "DUE_SOON"
    DUE = "DUE"
    OVERDUE = "OVERDUE"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


# ============================================================
# SCHEDULING & DOCTOR CALENDAR
# ============================================================


class AppointmentReminderRule(StringEnum):
    """Pre-defined reminder offsets relative to scheduled_start_at."""

    H24_BEFORE = "H24_BEFORE"
    H2_BEFORE = "H2_BEFORE"
    H1_BEFORE = "H1_BEFORE"
    M30_BEFORE = "M30_BEFORE"
    M15_BEFORE = "M15_BEFORE"
    CUSTOM = "CUSTOM"


class AppointmentRecurrence(StringEnum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"


class DoctorAvailabilityType(StringEnum):
    REGULAR = "REGULAR"      # repeating weekly schedule
    OVERRIDE = "OVERRIDE"    # one-off available block
    BLOCKED = "BLOCKED"      # one-off unavailable block (leave/holiday)


class AppointmentSlotStatus(StringEnum):
    OPEN = "OPEN"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"
    EXPIRED = "EXPIRED"


# ============================================================
# TAX MANAGEMENT
# ============================================================


class TaxKind(StringEnum):
    """Top-level tax taxonomy."""

    VAT = "VAT"
    WHT = "WHT"                  # Withholding tax
    SERVICE_TAX = "SERVICE_TAX"
    SALES_TAX = "SALES_TAX"
    CONSUMPTION_TAX = "CONSUMPTION_TAX"
    OTHER = "OTHER"


class TaxScope(StringEnum):
    """Whether a tax rule is tenant-wide or restricted to a branch."""

    TENANT = "TENANT"
    FACILITY = "FACILITY"


class TaxApplicability(StringEnum):
    """Predicate dimensions that pick which line-items a tax applies to."""

    ALL = "ALL"
    SERVICE_TYPE = "SERVICE_TYPE"
    ITEM_CATEGORY = "ITEM_CATEGORY"
    PAYER_TYPE = "PAYER_TYPE"
    PATIENT_TYPE = "PATIENT_TYPE"


class TaxPricingMode(StringEnum):
    EXCLUSIVE = "EXCLUSIVE"   # tax added on top
    INCLUSIVE = "INCLUSIVE"   # tax already in price


class WithholdingTaxStatus(StringEnum):
    PENDING = "PENDING"
    DEDUCTED = "DEDUCTED"
    REMITTED = "REMITTED"
    CERTIFICATE_ISSUED = "CERTIFICATE_ISSUED"
    REFUNDED = "REFUNDED"


class TaxExemptionScope(StringEnum):
    SERVICE = "SERVICE"
    PRODUCT = "PRODUCT"
    PATIENT = "PATIENT"
    ORGANIZATION = "ORGANIZATION"
    PAYER = "PAYER"


# ============================================================
# STAFF / HR
# ============================================================


class EmploymentType(StringEnum):
    PERMANENT = "PERMANENT"
    CONTRACT = "CONTRACT"
    LOCUM = "LOCUM"
    CONSULTANT = "CONSULTANT"
    INTERN = "INTERN"
    VOLUNTEER = "VOLUNTEER"


class EmploymentStatus(StringEnum):
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"
    PROBATION = "PROBATION"
    SUSPENDED = "SUSPENDED"
    RESIGNED = "RESIGNED"
    TERMINATED = "TERMINATED"
    RETIRED = "RETIRED"
    TRANSFERRED = "TRANSFERRED"


class StaffShiftType(StringEnum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    NIGHT = "NIGHT"
    WEEKEND = "WEEKEND"
    EMERGENCY = "EMERGENCY"
    ON_CALL = "ON_CALL"
    OFF_DUTY = "OFF_DUTY"


class LeaveTypeKind(StringEnum):
    ANNUAL = "ANNUAL"
    SICK = "SICK"
    MATERNITY = "MATERNITY"
    PATERNITY = "PATERNITY"
    STUDY = "STUDY"
    COMPASSIONATE = "COMPASSIONATE"
    UNPAID = "UNPAID"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    OTHER = "OTHER"


class LeaveStatus(StringEnum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class AttendanceMethod(StringEnum):
    MANUAL = "MANUAL"
    BIOMETRIC = "BIOMETRIC"
    QR_CODE = "QR_CODE"
    MOBILE = "MOBILE"
    DEVICE = "DEVICE"


class TimesheetStatus(StringEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    LOCKED = "LOCKED"


class PayrollRunStatus(StringEnum):
    DRAFT = "DRAFT"
    CALCULATED = "CALCULATED"
    APPROVED = "APPROVED"
    PAID = "PAID"
    LOCKED = "LOCKED"
    CANCELLED = "CANCELLED"


class PayrollLineStatus(StringEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAID = "PAID"
    ERROR = "ERROR"


class OvertimeStatus(StringEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"


class StaffLoanStatus(StringEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    DISBURSED = "DISBURSED"
    REPAYING = "REPAYING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class SalaryAdvanceStatus(StringEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class AppraisalStatus(StringEnum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    MODERATED = "MODERATED"
    FINAL = "FINAL"
    CANCELLED = "CANCELLED"


class StaffDocumentCategory(StringEnum):
    CV = "CV"
    CERTIFICATE = "CERTIFICATE"
    LICENSE = "LICENSE"
    CONTRACT = "CONTRACT"
    ID = "ID"
    PASSPORT_PHOTO = "PASSPORT_PHOTO"
    APPRAISAL = "APPRAISAL"
    DISCIPLINARY = "DISCIPLINARY"
    TRAINING = "TRAINING"
    PAYROLL = "PAYROLL"
    MEDICAL_CLEARANCE = "MEDICAL_CLEARANCE"
    OTHER = "OTHER"


class LicenseStatus(StringEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    PENDING_RENEWAL = "PENDING_RENEWAL"


class StaffIncidentSeverity(StringEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DisciplinaryActionKind(StringEnum):
    VERBAL_WARNING = "VERBAL_WARNING"
    WRITTEN_WARNING = "WRITTEN_WARNING"
    SUSPENSION = "SUSPENSION"
    DEMOTION = "DEMOTION"
    TERMINATION = "TERMINATION"
    OTHER = "OTHER"


class StaffRequestType(StringEnum):
    LEAVE = "LEAVE"
    OVERTIME = "OVERTIME"
    SHIFT_SWAP = "SHIFT_SWAP"
    SALARY_ADVANCE = "SALARY_ADVANCE"
    TRAINING = "TRAINING"
    REIMBURSEMENT = "REIMBURSEMENT"
    TRAVEL = "TRAVEL"
    ASSET = "ASSET"
    DOCUMENT = "DOCUMENT"
    OTHER = "OTHER"


class StaffRequestStatus(StringEnum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    FULFILLED = "FULFILLED"


class StaffTaskStatus(StringEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class StaffTaskPriority(StringEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class HolidayScope(StringEnum):
    NATIONAL = "NATIONAL"
    STATE = "STATE"
    TENANT = "TENANT"
    FACILITY = "FACILITY"


class TrainingStatus(StringEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ============================================================
# DATA WAREHOUSE
# ============================================================

class WarehouseExportType(StringEnum):
    SNAPSHOT = "SNAPSHOT"
    INCREMENTAL = "INCREMENTAL"
    EVENT_STREAM = "EVENT_STREAM"
    ON_DEMAND = "ON_DEMAND"


class WarehouseJobStatus(StringEnum):
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIALLY_FAILED = "PARTIALLY_FAILED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WarehouseRefreshStrategy(StringEnum):
    FULL_REFRESH = "FULL_REFRESH"
    INCREMENTAL = "INCREMENTAL"
    CDC = "CDC"
    APPEND_ONLY = "APPEND_ONLY"


class DataExtractionPurpose(StringEnum):
    BI_REPORTING = "BI_REPORTING"
    REGULATORY = "REGULATORY"
    RESEARCH = "RESEARCH"
    AUDIT = "AUDIT"
    BACKUP = "BACKUP"
    OTHER = "OTHER"


# ============================================================
# STAFF ONBOARDING
# ============================================================


class OnboardingInvitationStatus(StringEnum):
    """
    Lifecycle states for a staff onboarding invitation.

    DRAFT      – HR has created the record but not yet sent the link.
    PENDING    – The link has been dispatched; the candidate has not yet acted.
    IN_PROGRESS – The candidate clicked the link and started filling in their
                  details (optional intermediate state used by the front-end).
    COMPLETED  – The candidate submitted all required information.
    EXPIRED    – The link passed its expiry timestamp without being used.
    CANCELLED  – HR explicitly revoked the invitation before it was used.
    RESENT     – The link was regenerated and re-dispatched; the old token is
                 now invalid but the record is preserved for audit purposes.
    """

    DRAFT = "DRAFT"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    RESENT = "RESENT"


class OnboardingDocumentType(StringEnum):
    """
    Expected document types that a candidate must upload during onboarding.

    These are used to drive the document-upload checklist embedded in the
    onboarding invitation flow.
    """

    CV = "CV"
    GOVERNMENT_ID = "GOVERNMENT_ID"
    PASSPORT_PHOTO = "PASSPORT_PHOTO"
    ACADEMIC_CERTIFICATE = "ACADEMIC_CERTIFICATE"
    PROFESSIONAL_CERTIFICATE = "PROFESSIONAL_CERTIFICATE"
    MEDICAL_CLEARANCE = "MEDICAL_CLEARANCE"
    POLICE_CLEARANCE = "POLICE_CLEARANCE"
    OFFER_LETTER_SIGNED = "OFFER_LETTER_SIGNED"
    NDA_SIGNED = "NDA_SIGNED"
    OTHER = "OTHER"

