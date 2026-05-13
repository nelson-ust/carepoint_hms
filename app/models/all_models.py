#carepoint_hms/app/models/all_models
from __future__ import annotations

"""
carepoint_hms.app.models.all_models

Comprehensive SQLAlchemy ORM models for Carepoint HMS.

This module centralizes the database models for:
- authentication and RBAC
- patient registration and records
- appointments, visits, queue, and flexible visit flow
- clinical documentation
- laboratory
- pharmacy
- billing, payments, insurance, and loyalty
- admission, wards, beds, discharge
- inventory and stock
- ambulance and dispatch operations
- employee HR and workforce records
- messaging and notifications
- compliance, accreditation, incidents, infection control, and quality improvement

Design Notes
------------
1. All major business tables inherit from BaseTable.
2. Enums are imported from app.core.enums.
3. The visit flow remains dynamic at runtime.
4. Each service delivery point can maintain its own queue/workspace.
5. Relationships are designed to support gradual expansion of repositories/services.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy, AssociationProxy

from app.models.base import MasterTable, TenantTable, utc_now
from app.core.enums import (
    AccreditationStatus,
    AdjudicationOutcome,
    AdmissionStatus,
    AmbulanceDispatchStatus,
    AmbulanceStatus,
    AnaesthesiaType,
    AppointmentStatus,
    ApprovalApproverKind,
    ApprovalDecisionAction,
    ApprovalDynamicApprover,
    ApprovalRequestStatus,
    ApprovalRequestStepStatus,
    ApprovalStatus,
    ApprovalStepDecisionRule,
    ApprovalSubjectType,
    ASAClass,
    AuthorizationStatus,
    BedStatus,
    BloodGroup,
    ClaimAppealStatus,
    ClaimBatchStatus,
    ComplianceStatus,
    DataExtractionPurpose,
    DisciplinaryActionStatus,
    DispenseStatus,
    DowntimeEventType,
    DowntimeStatus,
    EmployeeScheduleStatus,
    EncounterStatus,
    FacilityStatus,
    FacilityType,
    FHIRResourceType,
    Gender,
    Genotype,
    GoodsReceiptStatus,
    IncidentSeverity,
    InsuranceClaimStatus,
    InsurancePolicyStatus,
    IntegrationDirection,
    IntegrationMessageStatus,
    IntegrationProtocol,
    IntegrationProviderType,
    DocumentTemplateType,
    InventoryItemType,
    InvoiceStatus,
    LabResultStatus,
    LeaveStatus,
    LoyaltyTransactionType,
    MaintenanceStatus,
    MaritalStatus,
    MessageStatus,
    MembershipCardStatus,
    MembershipCardTransactionType,
    NotificationChannel,
    NotificationStatus,
    OfflineDeviceStatus,
    OfflineSubmissionStatus,
    OrderStatus,
    PatientType,
    PaymentStatus,
    PaystackTransactionStatus,
    PerformanceStatus,
    PortalAccountStatus,
    PortalAppointmentRequestStatus,
    PortalConsentScope,
    PortalMessageDirection,
    PortalMessageStatus,
    PrescriptionStatus,
    ProcurementRequisitionStatus,
    PurchaseOrderStatus,
    QualityProjectStatus,
    QueueStatus,
    QuotationStatus,
    RadiologyExamStatus,
    RadiologyModality,
    ReimbursementStatus,
    RadiologyOrderStatus,
    RadiologyReportStatus,
    ReferralPriority,
    ReferralStatus,
    RFQStatus,
    ServicePointType,
    ShiftStatus,
    SterilizationStatus,
    StockMovementType,
    SupplierContractStatus,
    SupplierInvoiceStatus,
    SurgicalCaseStatus,
    SurgicalChecklistPhase,
    SurgicalRole,
    TerminologySystem,
    TheatreStatus,
    TwoFactorPurpose,
    TwoFactorType,
    UserStatus,
    SaaSRole,
    InvitationStatus,
    SupportAccessStatus,
    VisitFlowStepStatus,
    VisitPriority,
    VisitStatus,
    WarehouseExportType,
    WarehouseJobStatus,
    WarehouseRefreshStrategy,
    SubscriptionStatus,
    SubscriptionInterval,
    SubscriptionInvoiceStatus,
    SubscriptionPaymentStatus,
    PaymentChannel,
    PaymentProvider,
    EmailProvider,
    EdgeNodeStatus,
    SyncJournalOp,
    SyncJournalStatus,
    SyncDirection,
    MedicationFrequency,
    MedicationScheduleStatus,
    MedicationDoseStatus,
    AdherenceLevel,
    AdherenceAlertSeverity,
    FollowUpTaskStatus,
    RefillStatus,
    AppointmentReminderRule,
    AppointmentRecurrence,
    DoctorAvailabilityType,
    AppointmentSlotStatus,
    TaxKind,
    TaxScope,
    TaxApplicability,
    TaxPricingMode,
    WithholdingTaxStatus,
    TaxExemptionScope,
    EmploymentType,
    EmploymentStatus,
    StaffShiftType,
    LeaveTypeKind,
    LeaveStatus,
    AttendanceMethod,
    TimesheetStatus,
    PayrollRunStatus,
    PayrollLineStatus,
    OvertimeStatus,
    StaffLoanStatus,
    SalaryAdvanceStatus,
    AppraisalStatus,
    StaffDocumentCategory,
    LicenseStatus,
    StaffIncidentSeverity,
    DisciplinaryActionKind,
    StaffRequestType,
    StaffRequestStatus,
    StaffTaskStatus,
    StaffTaskPriority,
    HolidayScope,
    AllergySeverity,
    CdssAlertType,
    AiScribeJobStatus,
    TrainingStatus,
    OnboardingInvitationStatus,
    OnboardingDocumentType,
)


# ============================================================
# SECURITY / AUTH / RBAC / 2FA
# ============================================================


class Role(TenantTable):
    """
    System role for access control.

    The ``is_system`` flag protects built-in roles such as TENANT_ADMIN,
    ADMIN, DOCTOR, NURSE, BILLING_OFFICER, etc. from accidental deletion,
    renaming, or reassignment by ordinary administrative workflows.
    Enforcement should be handled in the role repository/service layer.
    """

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Marks built-in/system roles that should be treated as immutable.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user_roles: Mapped[list["UserRoleAssociation"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )
    role_permissions: Mapped[list["RolePermissionAssociation"]] = relationship(
        back_populates="role",
        cascade="all, delete-orphan",
    )


class Permission(TenantTable):
    """
    Fine-grained permission record.

    Permissions represent atomic actions such as PATIENT_CREATE,
    PATIENT_VIEW, BILLING_APPROVE, ROLE_ASSIGN, etc. The ``is_system`` flag
    protects built-in permissions from accidental modification or deletion.
    """

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    module: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Marks built-in permissions that should be treated as immutable.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permission_roles: Mapped[list["RolePermissionAssociation"]] = relationship(
        back_populates="permission",
        cascade="all, delete-orphan",
    )


class User(TenantTable):
    """Application user."""

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus),
        default=UserStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Brute-force and credential-stuffing protection fields.
    # These are updated by the auth service when login attempts succeed/fail.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failed_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ----- Profile fields ----------------------------------------------
    # These mirror common StaffProfile fields at the user level so they're
    # available even for users without a staff profile (e.g. patient users).
    profile_photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"), nullable=True, index=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True
    )
    employment_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    @property
    def profile_completion(self) -> int:
        """
        Return profile completion as an integer percentage (0-100).

        Required fields contribute equally; only filled, non-blank values
        count. Useful for guided onboarding ("Your profile is 60% complete").
        """
        required = (
            self.first_name,
            self.last_name,
            self.email,
            self.phone_number,
            self.profile_photo_url,
            self.job_title,
            self.department_id,
            self.facility_id,
        )
        filled = sum(1 for v in required if v not in (None, "", 0))
        return int(round(100 * filled / len(required)))

    staff_profile: Mapped[Optional["StaffProfile"]] = relationship(
        back_populates="user",
        uselist=False,
    )
    patient: Mapped[Optional["Patient"]] = relationship(
        back_populates="user",
        uselist=False,
    )
    user_roles: Mapped[list["UserRoleAssociation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    two_factor_challenges: Mapped[list["TwoFactorChallenge"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_histories: Mapped[list["PasswordHistory"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="PasswordHistory.changed_at.desc()",
    )
    security_events: Mapped[list["SecurityEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserRoleAssociation(TenantTable):
    """Join table between users and roles."""

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("role.id"), nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship(back_populates="user_roles")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role_association"),
        Index("ix_user_role_active_lookup", "user_id", "role_id", "is_active", "is_deleted"),
    )


class RolePermissionAssociation(TenantTable):
    """Join table between roles and permissions."""

    role_id: Mapped[int] = mapped_column(ForeignKey("role.id"), nullable=False, index=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permission.id"), nullable=False, index=True)

    role: Mapped["Role"] = relationship(back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship(back_populates="permission_roles")

    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission_association"),
        Index("ix_role_permission_active_lookup", "role_id", "permission_id", "is_active", "is_deleted"),
    )


class UserSession(TenantTable):
    """Tracks authenticated sessions."""

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    session_token_jti: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    refresh_token_jti: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)

    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optional device/browser fingerprint used for suspicious-session detection.
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")

    __table_args__ = (
        # Optimizes cleanup and validation queries for active user sessions.
        Index("ix_user_session_user_current", "user_id", "is_current", "is_deleted"),
        Index("ix_user_session_user_expires", "user_id", "expires_at"),
    )


class PasswordHistory(TenantTable):
    """
    Previous password hash record for password reuse prevention.

    The auth service should insert the current password hash here before a
    password change/reset is finalized, then compare new passwords against the
    most recent N rows for the user.
    """

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="password_histories")

    __table_args__ = (
        Index("ix_password_history_user_changed", "user_id", "changed_at"),
    )


class SecurityEvent(TenantTable):
    """
    Structured security audit trail for authentication and authorization events.

    This model is intentionally separate from the generic ``AuditLog`` table so
    that security-sensitive events can be filtered, alerted on, and retained
    according to stricter security policies.
    """

    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Examples: LOGIN_SUCCESS, LOGIN_FAILURE, ACCOUNT_LOCKED, ROLE_ASSIGNED.",
    )
    event_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Attribute is named event_metadata to avoid colliding with SQLAlchemy's
    # reserved DeclarativeBase.metadata attribute, while the DB column remains
    # named `metadata` for reporting/readability.
    event_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="INFO",
        index=True,
        doc="Recommended values: INFO, WARNING, CRITICAL.",
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="security_events")

    __table_args__ = (
        Index("ix_security_event_user_type", "user_id", "event_type"),
        Index("ix_security_event_type_severity", "event_type", "severity"),
    )


class TwoFactorChallenge(TenantTable):
    """Stores OTP/challenge records for login and verification flows."""

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    challenge_type: Mapped[TwoFactorType] = mapped_column(Enum(TwoFactorType), nullable=False, index=True)
    purpose: Mapped[TwoFactorPurpose] = mapped_column(Enum(TwoFactorPurpose), nullable=False, index=True)

    destination: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship(back_populates="two_factor_challenges")

    __table_args__ = (
        Index("ix_two_factor_user_purpose_verified", "user_id", "purpose", "is_verified"),
    )


# ============================================================
# ORGANIZATION / DEPARTMENTS / STAFF / SERVICE POINTS
# ============================================================


class Department(TenantTable):
    """Hospital department."""

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    service_delivery_points: Mapped[list["ServiceDeliveryPoint"]] = relationship(
        back_populates="department"
    )
    staff_profiles: Mapped[list["StaffProfile"]] = relationship(
        back_populates="department"
    )
    employee_schedules: Mapped[list["EmployeeSchedule"]] = relationship(
        back_populates="department"
    )


class ServiceDeliveryPoint(TenantTable):
    """
    Physical or logical care point where service is delivered and queue is managed.

    Each service delivery point can maintain its own queue and workflow interface.
    """

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    service_point_type: Mapped[ServicePointType] = mapped_column(
        Enum(ServicePointType),
        nullable=False,
        index=True,
    )

    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"),
        nullable=True,
        index=True,
    )
    location_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    queue_prefix: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    supports_appointments: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_walk_in: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    department: Mapped[Optional["Department"]] = relationship(back_populates="service_delivery_points")
    staff_assignments: Mapped[list["StaffServiceDeliveryPointAssociation"]] = relationship(
        back_populates="service_delivery_point",
        cascade="all, delete-orphan",
    )
    assigned_staff: AssociationProxy[list["StaffProfile"]] = association_proxy(
        "staff_assignments", "staff_profile", creator=lambda v: StaffServiceDeliveryPointAssociation(staff_profile=v)
    )
    queue_tickets: Mapped[list["QueueTicket"]] = relationship(back_populates="service_delivery_point")
    visit_flow_steps: Mapped[list["VisitFlowStep"]] = relationship(back_populates="service_delivery_point")
    employee_shifts: Mapped[list["EmployeeShift"]] = relationship(back_populates="service_delivery_point")


class StaffProfile(TenantTable):
    """Staff profile linked to a system user.

    Rich HR record covering personal/employment/contract details. New
    fields here are nullable to keep historical data compatible after
    schema-sync runs against existing tenant DBs.
    """

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, unique=True, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("department.id"), nullable=True, index=True)

    staff_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    designation: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    professional_license_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    specialty: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    # ----- Employment ---------------------------------------------------
    employment_type: Mapped[Optional[EmploymentType]] = mapped_column(
        Enum(EmploymentType), nullable=True, index=True
    )
    employment_status: Mapped[Optional[EmploymentStatus]] = mapped_column(
        Enum(EmploymentStatus), default=EmploymentStatus.ACTIVE, nullable=True, index=True
    )
    hire_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    confirmation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    probation_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    exit_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ----- Reporting line ----------------------------------------------
    supervisor_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True, index=True
    )

    # ----- Salary scaffolding (full structure lives in StaffSalary) ----
    salary_grade: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    salary_step: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    base_salary_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    salary_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    # ----- Personal / contact ------------------------------------------
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    marital_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    address_line_1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state_region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    personal_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    personal_phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    # ----- Next of kin / emergency contact -----------------------------
    next_of_kin_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    next_of_kin_relationship: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    next_of_kin_phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    # ----- Statutory / tax IDs -----------------------------------------
    tax_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    pension_pin: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    nhf_no: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    bank_account_no: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    bank_account_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ----- Onboarding bookkeeping --------------------------------------
    onboarded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    user: Mapped["User"] = relationship(back_populates="staff_profile")
    department: Mapped[Optional["Department"]] = relationship(back_populates="staff_profiles")
    service_delivery_points: Mapped[list["StaffServiceDeliveryPointAssociation"]] = relationship(
        back_populates="staff_profile",
        cascade="all, delete-orphan",
    )
    assigned_sdps: AssociationProxy[list["ServiceDeliveryPoint"]] = association_proxy(
        "service_delivery_points", "service_delivery_point", creator=lambda v: StaffServiceDeliveryPointAssociation(service_delivery_point=v)
    )

    @property
    def assigned_sdp_ids(self) -> list[int]:
        return [link.service_delivery_point_id for link in self.service_delivery_points]


class StaffServiceDeliveryPointAssociation(TenantTable):
    """Join table between staff profiles and service delivery points."""

    staff_profile_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False, index=True)
    service_delivery_point_id: Mapped[int] = mapped_column(ForeignKey("service_delivery_point.id"), nullable=False, index=True)

    staff_profile: Mapped["StaffProfile"] = relationship(back_populates="service_delivery_points")
    service_delivery_point: Mapped["ServiceDeliveryPoint"] = relationship(back_populates="staff_assignments")

    __table_args__ = (
        UniqueConstraint("staff_profile_id", "service_delivery_point_id", name="uq_staff_sdp_association"),
    )

# # ============================================================
# # PATIENTS / REGISTRATION
# # ============================================================


# class Patient(TenantTable):
#     """Master patient record."""

#     hospital_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

#     first_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
#     last_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
#     middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

#     date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
#     gender: Mapped[Optional[Gender]] = mapped_column(Enum(Gender), nullable=True, index=True)
#     marital_status: Mapped[Optional[MaritalStatus]] = mapped_column(Enum(MaritalStatus), nullable=True)

#     phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
#     alternate_phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
#     email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

#     address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
#     city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
#     state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
#     country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

#     blood_group: Mapped[Optional[BloodGroup]] = mapped_column(Enum(BloodGroup), nullable=True)
#     genotype: Mapped[Optional[Genotype]] = mapped_column(Enum(Genotype), nullable=True)
#     allergies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

#     emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
#     emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
#     emergency_contact_relationship: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

#     patient_type: Mapped[PatientType] = mapped_column(
#         Enum(PatientType),
#         default=PatientType.OUTPATIENT,
#         nullable=False,
#         index=True,
#     )

#     registrations: Mapped[list["PatientRegistration"]] = relationship(back_populates="patient")
#     appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient")
#     visits: Mapped[list["Visit"]] = relationship(back_populates="patient")
#     admissions: Mapped[list["Admission"]] = relationship(back_populates="patient")
#     billings: Mapped[list["Billing"]] = relationship(back_populates="patient")
#     invoices: Mapped[list["Invoice"]] = relationship(back_populates="patient")
#     notifications: Mapped[list["Notification"]] = relationship(back_populates="patient")
#     insurance_records: Mapped[list["PatientInsurance"]] = relationship(back_populates="patient")
#     loyalty_memberships: Mapped[list["PatientLoyalty"]] = relationship(back_populates="patient")


# class PatientRegistration(TenantTable):
#     """Logs patient registration events."""

#     patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
#     registered_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)

#     registration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
#     notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

#     patient: Mapped["Patient"] = relationship(back_populates="registrations")
#     registered_by: Mapped[Optional["User"]] = relationship()


# ============================================================
# PATIENTS / REGISTRATION / MPI / IDENTIFIERS / CONSENTS
# ============================================================


class Patient(TenantTable):
    """Master patient record."""

    global_patient_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
        doc="Unique identifier across the entire SaaS platform (global patient ID)."
    )
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)

    # Core MRN / MPI
    hospital_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    # Names / demographics
    first_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    gender: Mapped[Optional[Gender]] = mapped_column(Enum(Gender), nullable=True, index=True)
    marital_status: Mapped[Optional[MaritalStatus]] = mapped_column(Enum(MaritalStatus), nullable=True)

    # Contact details
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    alternate_phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Clinical profile
    blood_group: Mapped[Optional[BloodGroup]] = mapped_column(Enum(BloodGroup), nullable=True)
    genotype: Mapped[Optional[Genotype]] = mapped_column(Enum(Genotype), nullable=True)
    allergies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Existing emergency contact (keep)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    emergency_contact_relationship: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Explicit next-of-kin fields (new)
    next_of_kin_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    next_of_kin_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    next_of_kin_relationship: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    next_of_kin_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Patient classification
    patient_type: Mapped[PatientType] = mapped_column(
        Enum(PatientType),
        default=PatientType.OUTPATIENT,
        nullable=False,
        index=True,
    )

    # Billing / payer preference
    preferred_payer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payer.id"),
        nullable=True,
        index=True,
    )
    payer_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Optional quick payer-type snapshot, e.g. SELF_PAY, HMO, SPONSOR.",
    )

    # Generic identity summary
    national_identifier: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )
    national_identifier_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        doc="Examples: NIN, PASSPORT, DRIVER_LICENSE, VOTER_CARD.",
    )
    identification_details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        doc="Flexible JSON for additional identification details if needed.",
    )

    # Patient photo convenience fields
    photo_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    photo_file_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    photo_file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    registrations: Mapped[list["PatientRegistration"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    identifiers: Mapped[list["PatientIdentifier"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    attachments: Mapped[list["PatientAttachment"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    consent_records: Mapped[list["PatientConsent"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    scanned_forms: Mapped[list["PatientScannedForm"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    demographic_audits: Mapped[list["PatientDemographicAudit"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="PatientDemographicAudit.changed_at.desc()",
    )

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient")
    visits: Mapped[list["Visit"]] = relationship(back_populates="patient")
    admissions: Mapped[list["Admission"]] = relationship(back_populates="patient")
    billings: Mapped[list["Billing"]] = relationship(back_populates="patient")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="patient")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="patient")
    insurance_records: Mapped[list["PatientInsurance"]] = relationship(back_populates="patient")
    loyalty_memberships: Mapped[list["PatientLoyalty"]] = relationship(back_populates="patient")
    membership_cards: Mapped[list["MembershipCard"]] = relationship(back_populates="patient")
    paystack_transactions: Mapped[list["PaystackTransaction"]] = relationship(back_populates="patient")
    referrals: Mapped[list["Referral"]] = relationship(back_populates="patient")

    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, unique=True, index=True)
    user: Mapped[Optional["User"]] = relationship(back_populates="patient")

    preferred_payer: Mapped[Optional["Payer"]] = relationship(
        foreign_keys=[preferred_payer_id]
    )

    __table_args__ = (
        Index("ix_patient_name_dob", "last_name", "first_name", "date_of_birth"),
        Index("ix_patient_phone_dob", "phone_number", "date_of_birth"),
    )


class PatientRegistration(TenantTable):
    """Logs patient registration events."""

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    registered_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)

    registration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="registrations")
    registered_by: Mapped[Optional["User"]] = relationship()


class PatientIdentifier(TenantTable):
    """
    Flexible patient identifier record.

    Supports:
    - national identifiers
    - previous hospital numbers
    - payer/member IDs
    - external/reference identifiers
    """

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)

    identifier_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Examples: NATIONAL_ID, PREVIOUS_RECORD_ID, PASSPORT, INSURANCE_MEMBER_ID, EXTERNAL_MRN.",
    )
    identifier_value: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    issuing_authority: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="identifiers")

    __table_args__ = (
        UniqueConstraint(
            "identifier_type",
            "identifier_value",
            name="uq_patient_identifier_type_value",
        ),
        Index("ix_patient_identifier_patient_type", "patient_id", "identifier_type"),
    )


class PatientAttachment(TenantTable):
    """
    Document/photo attachment linked to a patient.

    Covers:
    - registration documents
    - ID cards
    - referrals
    - photographs
    - scanned paperwork
    """

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)

    attachment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Examples: PHOTO, ID_DOCUMENT, REFERRAL, REGISTRATION_FORM, CLINICAL_FORM, OTHER.",
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="attachments")
    uploaded_by: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        Index("ix_patient_attachment_patient_type", "patient_id", "attachment_type"),
    )


class PatientConsent(TenantTable):
    """
    Patient consent record.

    Covers:
    - treatment consent
    - privacy/data use consent
    - photo consent
    - billing/payment consent
    """

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    recorded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)

    consent_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    consent_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Examples: GRANTED, DECLINED, WITHDRAWN, EXPIRED.",
    )
    consent_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    document_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_file_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    document_file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="consent_records")
    recorded_by: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        Index("ix_patient_consent_patient_type_status", "patient_id", "consent_type", "consent_status"),
    )


class PatientScannedForm(TenantTable):
    """
    Scanned form or externally sourced clinical/registration form.
    """

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)

    form_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Examples: REGISTRATION_FORM, CLINICAL_FORM, CONSENT_FORM, REFERRAL_FORM.",
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="scanned_forms")
    uploaded_by: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        Index("ix_patient_scanned_form_patient_type", "patient_id", "form_type"),
    )


class PatientDemographicAudit(TenantTable):
    """
    Audit log for demographic changes on the patient master record.
    """

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)

    change_source: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Examples: REGISTRATION_DESK, MPI_UPDATE, MERGE, API, BULK_IMPORT.",
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    before_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    changed_fields: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="demographic_audits")
    changed_by: Mapped[Optional["User"]] = relationship()

    __table_args__ = (
        Index("ix_patient_demographic_audit_patient_changed_at", "patient_id", "changed_at"),
    )


# ============================================================
# APPOINTMENTS / VISITS / DYNAMIC VISIT FLOW / QUEUES
# ============================================================


class Appointment(TenantTable):
    """Patient appointment."""

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    service_delivery_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_delivery_point.id"),
        nullable=True,
        index=True,
    )
    staff_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"),
        nullable=True,
        index=True,
    )

    appointment_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    scheduled_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    scheduled_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus),
        default=AppointmentStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    patient: Mapped["Patient"] = relationship(back_populates="appointments")
    service_delivery_point: Mapped[Optional["ServiceDeliveryPoint"]] = relationship()
    staff_profile: Mapped[Optional["StaffProfile"]] = relationship()


class Visit(TenantTable):
    """
    Patient visit record.

    New patient flow:
        registration -> visit initiation -> visit code -> queue

    Existing patient flow:
        visit initiation -> queue

    The actual visit flow is dynamic and can be changed at runtime depending on
    patient condition.
    """

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    appointment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("appointment.id"), nullable=True, index=True)

    visit_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    visit_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    status: Mapped[VisitStatus] = mapped_column(
        Enum(VisitStatus),
        default=VisitStatus.INITIATED,
        nullable=False,
        index=True,
    )
    priority: Mapped[VisitPriority] = mapped_column(
        Enum(VisitPriority),
        default=VisitPriority.NORMAL,
        nullable=False,
        index=True,
    )

    first_service_delivery_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_delivery_point.id"),
        nullable=True,
        index=True,
    )
    current_service_delivery_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_delivery_point.id"),
        nullable=True,
        index=True,
    )

    referred_from: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    visit_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    check_in_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="visits")
    appointment: Mapped[Optional["Appointment"]] = relationship()
    first_service_delivery_point: Mapped[Optional["ServiceDeliveryPoint"]] = relationship(
        foreign_keys=[first_service_delivery_point_id]
    )
    current_service_delivery_point: Mapped[Optional["ServiceDeliveryPoint"]] = relationship(
        foreign_keys=[current_service_delivery_point_id]
    )

    flow_steps: Mapped[list["VisitFlowStep"]] = relationship(
        back_populates="visit",
        cascade="all, delete-orphan",
        order_by="VisitFlowStep.step_order",
    )
    queue_tickets: Mapped[list["QueueTicket"]] = relationship(
        back_populates="visit",
        cascade="all, delete-orphan",
    )
    triage_assessments: Mapped[list["TriageAssessment"]] = relationship(back_populates="visit")
    vital_signs: Mapped[list["VitalSign"]] = relationship(back_populates="visit")
    consultations: Mapped[list["Consultation"]] = relationship(back_populates="visit")
    diagnoses: Mapped[list["Diagnosis"]] = relationship(back_populates="visit")
    procedure_orders: Mapped[list["ProcedureOrder"]] = relationship(back_populates="visit")
    lab_orders: Mapped[list["LabOrder"]] = relationship(back_populates="visit")
    prescriptions: Mapped[list["Prescription"]] = relationship(back_populates="visit")
    billings: Mapped[list["Billing"]] = relationship(back_populates="visit")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="visit")
    admissions: Mapped[list["Admission"]] = relationship(back_populates="visit")
    referrals: Mapped[list["Referral"]] = relationship(back_populates="visit")


class VisitFlowTemplate(TenantTable):
    """Reusable visit flow template."""

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    steps: Mapped[list["VisitFlowTemplateStep"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="VisitFlowTemplateStep.step_order",
    )


class VisitFlowTemplateStep(TenantTable):
    """Step definition inside a reusable visit flow template."""

    template_id: Mapped[int] = mapped_column(ForeignKey("visit_flow_template.id"), nullable=False, index=True)
    service_delivery_point_id: Mapped[int] = mapped_column(
        ForeignKey("service_delivery_point.id"),
        nullable=False,
        index=True,
    )

    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    template: Mapped["VisitFlowTemplate"] = relationship(back_populates="steps")
    service_delivery_point: Mapped["ServiceDeliveryPoint"] = relationship()

    __table_args__ = (
        UniqueConstraint("template_id", "step_order", name="uq_visit_flow_template_step_order"),
    )


class VisitFlowStep(TenantTable):
    """
    Runtime visit flow step for a specific visit.

    Supports insertion, repetition, skipping, and rerouting.
    """

    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), nullable=False, index=True)
    service_delivery_point_id: Mapped[int] = mapped_column(
        ForeignKey("service_delivery_point.id"),
        nullable=False,
        index=True,
    )

    step_order: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[VisitFlowStepStatus] = mapped_column(
        Enum(VisitFlowStepStatus),
        default=VisitFlowStepStatus.PENDING,
        nullable=False,
        index=True,
    )

    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    routed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    visit: Mapped["Visit"] = relationship(back_populates="flow_steps")
    service_delivery_point: Mapped["ServiceDeliveryPoint"] = relationship(back_populates="visit_flow_steps")
    routed_by: Mapped[Optional["User"]] = relationship()
    queue_ticket: Mapped[Optional["QueueTicket"]] = relationship(
        back_populates="visit_flow_step",
        uselist=False,
    )

    __table_args__ = (
        UniqueConstraint("visit_id", "step_order", name="uq_visit_flow_step_visit_order"),
        Index("ix_visit_flow_visit_current", "visit_id", "is_current"),
    )


class QueueTicket(TenantTable):
    """
    Queue record for a visit at a specific service delivery point.

    Every service delivery point can maintain its own queue.
    """

    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), nullable=False, index=True)
    visit_flow_step_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("visit_flow_step.id"),
        nullable=True,
        unique=True,
        index=True,
    )
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    service_delivery_point_id: Mapped[int] = mapped_column(
        ForeignKey("service_delivery_point.id"),
        nullable=False,
        index=True,
    )

    queue_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    queue_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[QueueStatus] = mapped_column(
        Enum(QueueStatus),
        default=QueueStatus.WAITING,
        nullable=False,
        index=True,
    )

    called_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    service_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    service_ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    transferred_from_ticket_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("queue_ticket.id"),
        nullable=True,
    )

    visit: Mapped["Visit"] = relationship(back_populates="queue_tickets")
    visit_flow_step: Mapped[Optional["VisitFlowStep"]] = relationship(back_populates="queue_ticket")
    patient: Mapped["Patient"] = relationship()
    service_delivery_point: Mapped["ServiceDeliveryPoint"] = relationship(back_populates="queue_tickets")
    transferred_from_ticket: Mapped[Optional["QueueTicket"]] = relationship(remote_side="QueueTicket.id")

    __table_args__ = (
        Index("ix_queue_sdp_status_position", "service_delivery_point_id", "status", "queue_position"),
    )


# ============================================================
# CLINICAL DOMAIN
# ============================================================


class TriageAssessment(TenantTable):
    """Triage record for a visit."""

    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), nullable=False, index=True)
    assessed_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    chief_complaint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triage_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    priority: Mapped[VisitPriority] = mapped_column(
        Enum(VisitPriority),
        default=VisitPriority.NORMAL,
        nullable=False,
    )

    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    visit: Mapped["Visit"] = relationship(back_populates="triage_assessments")
    assessed_by_staff: Mapped[Optional["StaffProfile"]] = relationship()


class VitalSign(TenantTable):
    """Vital signs captured during a visit."""

    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), nullable=False, index=True)
    visit_flow_step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit_flow_step.id"), nullable=True, index=True)
    recorded_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    temperature_celsius: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    pulse_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    respiratory_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    systolic_bp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    diastolic_bp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    oxygen_saturation: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    height_cm: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    bmi: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    pain_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mews_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Modified Early Warning Score")

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    visit: Mapped["Visit"] = relationship(back_populates="vital_signs")
    visit_flow_step: Mapped[Optional["VisitFlowStep"]] = relationship()
    recorded_by_staff: Mapped[Optional["StaffProfile"]] = relationship()


class Consultation(TenantTable):
    """Clinical consultation note for a visit."""

    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), nullable=False, index=True)
    visit_flow_step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit_flow_step.id"), nullable=True, index=True)
    clinician_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True, index=True)

    status: Mapped[EncounterStatus] = mapped_column(
        Enum(EncounterStatus),
        default=EncounterStatus.OPEN,
        nullable=False,
    )

    subjective_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objective_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assessment_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    consultation_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consultation_ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    visit: Mapped["Visit"] = relationship(back_populates="consultations")
    visit_flow_step: Mapped[Optional["VisitFlowStep"]] = relationship()
    clinician_staff: Mapped[Optional["StaffProfile"]] = relationship()


class Diagnosis(TenantTable):
    """Diagnosis attached to a visit."""

    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), nullable=False, index=True)
    consultation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("consultation.id"), nullable=True, index=True)

    diagnosis_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    diagnosis_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    diagnosis_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    diagnosis_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    visit: Mapped["Visit"] = relationship(back_populates="diagnoses")
    consultation: Mapped[Optional["Consultation"]] = relationship()


class Referral(TenantTable):
    """Tracks referrals to external facilities."""

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True, index=True)
    referring_staff_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False)

    referral_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    destination_facility: Mapped[str] = mapped_column(String(255), nullable=False)
    reason_for_referral: Mapped[str] = mapped_column(Text, nullable=False)
    clinical_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    referral_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus),
        default=ReferralStatus.PENDING,
        nullable=False,
        index=True,
    )
    priority: Mapped[ReferralPriority] = mapped_column(
        Enum(ReferralPriority),
        default=ReferralPriority.NORMAL,
        nullable=False,
    )

    patient: Mapped["Patient"] = relationship(back_populates="referrals")
    visit: Mapped[Optional["Visit"]] = relationship(back_populates="referrals")
    referring_staff: Mapped["StaffProfile"] = relationship()


class InterFacilityReferral(MasterTable):
    """
    Manages referrals between different tenants/facilities in the SaaS platform.
    Grants medical history access upon acceptance.
    """

    referral_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    
    source_tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    source_facility_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    target_tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    target_facility_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Linked by global ID to allow cross-tenant lookup
    patient_global_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    reason_for_referral: Mapped[str] = mapped_column(Text, nullable=False)
    clinical_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    status: Mapped[ReferralStatus] = mapped_column(
        Enum(ReferralStatus), default=ReferralStatus.PENDING, index=True
    )
    
    acceptance_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    declined_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timing
    referral_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Permission metadata
    is_history_access_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    access_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class InterFacilityAccessGrant(MasterTable):
    """
    Explicit authorization record granting a tenant access to a patient's
    records from another tenant, typically following an accepted referral.
    """

    referral_id: Mapped[Optional[int]] = mapped_column(ForeignKey("inter_facility_referral.id"), nullable=True)
    patient_global_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    source_tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    target_tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PatientRecordTransferRequest(MasterTable):
    """
    Tracks requests to permanently transfer a patient's medical record
    from one facility/tenant to another.
    """

    patient_global_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    target_tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False)
    
    request_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ApprovalStatus] = mapped_column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)
    
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcedureCatalog(TenantTable):
    """Master list of procedures offered by the hospital."""

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)


class ProcedureOrder(TenantTable):
    """Ordered procedure for a visit."""

    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), nullable=False, index=True)
    consultation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("consultation.id"), nullable=True, index=True)
    procedure_catalog_id: Mapped[int] = mapped_column(ForeignKey("procedure_catalog.id"), nullable=False, index=True)

    ordered_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)
    performed_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        default=OrderStatus.ORDERED,
        nullable=False,
    )

    findings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    performed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    visit: Mapped["Visit"] = relationship(back_populates="procedure_orders")
    consultation: Mapped[Optional["Consultation"]] = relationship()
    procedure_catalog: Mapped["ProcedureCatalog"] = relationship()
    ordered_by_staff: Mapped[Optional["StaffProfile"]] = relationship(foreign_keys=[ordered_by_staff_id])
    performed_by_staff: Mapped[Optional["StaffProfile"]] = relationship(foreign_keys=[performed_by_staff_id])


# ============================================================
# LABORATORY
# ============================================================


class LabTestCatalog(TenantTable):
    """Master list of laboratory tests."""

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    sample_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_range: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class LabOrder(TenantTable):
    """Laboratory order header for a visit."""

    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), nullable=False, index=True)
    visit_flow_step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit_flow_step.id"), nullable=True, index=True)
    consultation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("consultation.id"), nullable=True, index=True)
    ordered_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    order_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        default=OrderStatus.ORDERED,
        nullable=False,
        index=True,
    )

    clinical_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    visit: Mapped["Visit"] = relationship(back_populates="lab_orders")
    visit_flow_step: Mapped[Optional["VisitFlowStep"]] = relationship()
    consultation: Mapped[Optional["Consultation"]] = relationship()
    ordered_by_staff: Mapped[Optional["StaffProfile"]] = relationship()

    items: Mapped[list["LabOrderItem"]] = relationship(
        back_populates="lab_order",
        cascade="all, delete-orphan",
    )


class LabOrderItem(TenantTable):
    """Individual test item within a lab order."""

    lab_order_id: Mapped[int] = mapped_column(ForeignKey("lab_order.id"), nullable=False, index=True)
    visit_flow_step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit_flow_step.id"), nullable=True, index=True)
    lab_test_catalog_id: Mapped[int] = mapped_column(ForeignKey("lab_test_catalog.id"), nullable=False, index=True)

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus),
        default=OrderStatus.ORDERED,
        nullable=False,
    )

    specimen_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    sample_collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    lab_order: Mapped["LabOrder"] = relationship(back_populates="items")
    visit_flow_step: Mapped[Optional["VisitFlowStep"]] = relationship()
    lab_test_catalog: Mapped["LabTestCatalog"] = relationship()
    collected_by_staff: Mapped[Optional["StaffProfile"]] = relationship()

    result: Mapped[Optional["LabResult"]] = relationship(
        back_populates="lab_order_item",
        uselist=False,
        cascade="all, delete-orphan",
    )


class LabResult(TenantTable):
    """Result for a lab order item."""

    lab_order_item_id: Mapped[int] = mapped_column(
        ForeignKey("lab_order_item.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    visit_flow_step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit_flow_step.id"), nullable=True, index=True)
    entered_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)
    verified_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    result_status: Mapped[LabResultStatus] = mapped_column(
        Enum(LabResultStatus),
        default=LabResultStatus.PENDING,
        nullable=False,
        index=True,
    )

    result_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    result_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_range: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    interpretation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    entered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    lab_order_item: Mapped["LabOrderItem"] = relationship(back_populates="result")
    visit_flow_step: Mapped[Optional["VisitFlowStep"]] = relationship()
    entered_by_staff: Mapped[Optional["StaffProfile"]] = relationship(foreign_keys=[entered_by_staff_id])
    verified_by_staff: Mapped[Optional["StaffProfile"]] = relationship(foreign_keys=[verified_by_staff_id])


# ============================================================
# PHARMACY
# ============================================================


class DrugCategory(TenantTable):
    """Drug grouping/category."""

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    drugs: Mapped[list["Drug"]] = relationship(back_populates="category")


class Drug(TenantTable):
    """Drug master."""

    drug_category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drug_category.id"), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    generic_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    brand_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    strength: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dosage_form: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pack_size: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, index=True)

    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    reorder_level: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    is_controlled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    category: Mapped[Optional["DrugCategory"]] = relationship(back_populates="drugs")
    prescription_items: Mapped[list["PrescriptionItem"]] = relationship(back_populates="drug")
    stock_items: Mapped[list["InventoryStockItem"]] = relationship(back_populates="drug")


class Prescription(TenantTable):
    """Prescription header for a visit."""

    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), nullable=False, index=True)
    visit_flow_step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit_flow_step.id"), nullable=True, index=True)
    consultation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("consultation.id"), nullable=True, index=True)
    prescribed_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    prescription_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    status: Mapped[PrescriptionStatus] = mapped_column(
        Enum(PrescriptionStatus),
        default=PrescriptionStatus.PRESCRIBED,
        nullable=False,
    )

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prescribed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    visit: Mapped["Visit"] = relationship(back_populates="prescriptions")
    visit_flow_step: Mapped[Optional["VisitFlowStep"]] = relationship()
    consultation: Mapped[Optional["Consultation"]] = relationship()
    prescribed_by_staff: Mapped[Optional["StaffProfile"]] = relationship()

    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription",
        cascade="all, delete-orphan",
    )
    dispenses: Mapped[list["Dispense"]] = relationship(back_populates="prescription")


class PrescriptionItem(TenantTable):
    """Drug line inside a prescription."""

    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescription.id"), nullable=False, index=True)
    drug_id: Mapped[int] = mapped_column(ForeignKey("drug.id"), nullable=False, index=True)

    dosage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    frequency: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    route: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    quantity_prescribed: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    quantity_dispensed: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    prescription: Mapped["Prescription"] = relationship(back_populates="items")
    drug: Mapped["Drug"] = relationship(back_populates="prescription_items")


class Dispense(TenantTable):
    """Pharmacy dispense transaction."""

    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescription.id"), nullable=False, index=True)
    visit_flow_step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit_flow_step.id"), nullable=True, index=True)
    dispensed_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    dispense_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    status: Mapped[DispenseStatus] = mapped_column(
        Enum(DispenseStatus),
        default=DispenseStatus.PENDING,
        nullable=False,
    )

    dispensed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    prescription: Mapped["Prescription"] = relationship(back_populates="dispenses")
    visit_flow_step: Mapped[Optional["VisitFlowStep"]] = relationship()
    dispensed_by_staff: Mapped[Optional["StaffProfile"]] = relationship()

    items: Mapped[list["DispenseItem"]] = relationship(
        back_populates="dispense",
        cascade="all, delete-orphan",
    )


class DispenseItem(TenantTable):
    """Dispensed item line."""

    dispense_id: Mapped[int] = mapped_column(ForeignKey("dispense.id"), nullable=False, index=True)
    prescription_item_id: Mapped[int] = mapped_column(ForeignKey("prescription_item.id"), nullable=False, index=True)

    quantity_dispensed: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    dispense: Mapped["Dispense"] = relationship(back_populates="items")
    prescription_item: Mapped["PrescriptionItem"] = relationship()


# ============================================================
# BILLING / INVOICES / PAYMENTS / INSURANCE / LOYALTY
# ============================================================


class InsuranceProvider(TenantTable):
    """Insurance or HMO provider."""

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient_insurance_records: Mapped[list["PatientInsurance"]] = relationship(
        back_populates="insurance_provider"
    )


class PatientInsurance(TenantTable):
    """Insurance enrollment record for a patient."""

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    insurance_provider_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_provider.id"),
        nullable=False,
        index=True,
    )

    policy_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    member_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    plan_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    # Alignment with schema and repository
    coverage_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    coverage_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    coverage_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    policy_status: Mapped[InsurancePolicyStatus] = mapped_column(
        Enum(InsurancePolicyStatus),
        default=InsurancePolicyStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="insurance_records")
    insurance_provider: Mapped["InsuranceProvider"] = relationship(back_populates="patient_insurance_records")


class Payer(TenantTable):
    """Payer or sponsor."""

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    payer_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class BillableService(TenantTable):
    """Master catalog of billable services."""

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    default_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Billing(TenantTable):
    """
    Billing header/workflow record.

    This can be used before invoice issuance or as the billing workbench record
    that later results in one or more invoices.
    """

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True, index=True)
    patient_insurance_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patient_insurance.id"), nullable=True, index=True)

    billing_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    billing_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="billings")
    visit: Mapped[Optional["Visit"]] = relationship(back_populates="billings")
    patient_insurance: Mapped[Optional["PatientInsurance"]] = relationship()

    items: Mapped[list["BillingItem"]] = relationship(
        back_populates="billing",
        cascade="all, delete-orphan",
    )
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="billing")


class BillingItem(TenantTable):
    """Individual charge line on a billing record."""

    billing_id: Mapped[int] = mapped_column(ForeignKey("billing.id"), nullable=False, index=True)
    billable_service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("billable_service.id"), nullable=True, index=True)

    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    source_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    billing: Mapped["Billing"] = relationship(back_populates="items")
    billable_service: Mapped[Optional["BillableService"]] = relationship()


class Invoice(TenantTable):
    """Billing invoice for a patient and/or visit."""

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True, index=True)
    billing_id: Mapped[Optional[int]] = mapped_column(ForeignKey("billing.id"), nullable=True, index=True)
    payer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("payer.id"), nullable=True, index=True)

    invoice_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus),
        default=InvoiceStatus.DRAFT,
        nullable=False,
        index=True,
    )

    invoice_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    balance_due: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="invoices")
    visit: Mapped[Optional["Visit"]] = relationship(back_populates="invoices")
    billing: Mapped[Optional["Billing"]] = relationship(back_populates="invoices")
    payer: Mapped[Optional["Payer"]] = relationship()

    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice")
    loyalty_transactions: Mapped[list["LoyaltyTransaction"]] = relationship(back_populates="invoice")


class InvoiceItem(TenantTable):
    """Individual charge line on an invoice."""

    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"), nullable=False, index=True)
    billable_service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("billable_service.id"), nullable=True, index=True)

    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    source_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="items")
    billable_service: Mapped[Optional["BillableService"]] = relationship()


class Payment(TenantTable):
    """Payment transaction against an invoice."""

    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"), nullable=False, index=True)
    visit_flow_step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit_flow_step.id"), nullable=True, index=True)
    received_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    payment_reference: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="NGN")
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    transaction_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")
    visit_flow_step: Mapped[Optional["VisitFlowStep"]] = relationship()
    received_by_staff: Mapped[Optional["StaffProfile"]] = relationship()
    membership_card_transaction: Mapped[Optional["MembershipCardTransaction"]] = relationship(back_populates="payment")


class LoyaltyProgram(TenantTable):
    """Hospital loyalty program definition."""

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    points_per_currency_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    minimum_redemption_points: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    is_auto_enroll: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    patient_loyalties: Mapped[list["PatientLoyalty"]] = relationship(back_populates="loyalty_program")


class PatientLoyalty(TenantTable):
    """Patient membership in a loyalty program."""

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    loyalty_program_id: Mapped[int] = mapped_column(ForeignKey("loyalty_program.id"), nullable=False, index=True)

    membership_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    points_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    joined_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="loyalty_memberships")
    loyalty_program: Mapped["LoyaltyProgram"] = relationship(back_populates="patient_loyalties")

    transactions: Mapped[list["LoyaltyTransaction"]] = relationship(
        back_populates="patient_loyalty",
        cascade="all, delete-orphan",
    )


class LoyaltyTransaction(TenantTable):
    """Points earning, redemption, or adjustment transaction."""

    patient_loyalty_id: Mapped[int] = mapped_column(ForeignKey("patient_loyalty.id"), nullable=False, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoice.id"), nullable=True, index=True)

    transaction_type: Mapped[LoyaltyTransactionType] = mapped_column(
        Enum(LoyaltyTransactionType),
        nullable=False,
        index=True,
    )

    points: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    patient_loyalty: Mapped["PatientLoyalty"] = relationship(back_populates="transactions")
    invoice: Mapped[Optional["Invoice"]] = relationship(back_populates="loyalty_transactions")

    redemption_approval: Mapped[Optional["LoyaltyRedemptionApproval"]] = relationship(
        back_populates="loyalty_transaction",
        uselist=False,
        cascade="all, delete-orphan",
    )


class LoyaltyRedemptionApproval(TenantTable):
    """Approval record for loyalty redemption requiring authorization."""

    loyalty_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("loyalty_transaction.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    requested_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus),
        default=ApprovalStatus.PENDING,
        nullable=False,
        index=True,
    )

    request_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    loyalty_transaction: Mapped["LoyaltyTransaction"] = relationship(back_populates="redemption_approval")
    requested_by: Mapped[Optional["User"]] = relationship(foreign_keys=[requested_by_id])
    approved_by: Mapped[Optional["User"]] = relationship(foreign_keys=[approved_by_id])


class MembershipCard(TenantTable):
    """
    Facility-issued card linked to a patient wallet.
    
    Can be credited through online payments or cashier deposits and debited
    for billable services.
    """
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    card_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    status: Mapped[MembershipCardStatus] = mapped_column(
        Enum(MembershipCardStatus), default=MembershipCardStatus.ACTIVE, nullable=False
    )
    issuing_facility_id: Mapped[int] = mapped_column(ForeignKey("facility.id"), nullable=False)
    issued_by_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    date_issued: Mapped[date] = mapped_column(Date, nullable=False, default=lambda: datetime.utcnow().date())
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="membership_cards")
    issuing_facility: Mapped["Facility"] = relationship()
    issued_by: Mapped["User"] = relationship()
    transactions: Mapped[list["MembershipCardTransaction"]] = relationship(back_populates="membership_card")


class MembershipCardTransaction(TenantTable):
    """Tracks funding (credit) and payment (debit) events for a membership card."""
    membership_card_id: Mapped[int] = mapped_column(ForeignKey("membership_card.id"), nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    transaction_type: Mapped[MembershipCardTransactionType] = mapped_column(
        Enum(MembershipCardTransactionType), nullable=False
    )
    payment_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    balance_before: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facility.id"), nullable=False)
    processed_by_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    narration: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoice.id"), nullable=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True)
    payment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("payment.id"), nullable=True)

    membership_card: Mapped["MembershipCard"] = relationship(back_populates="transactions")
    patient: Mapped["Patient"] = relationship()
    facility: Mapped["Facility"] = relationship()
    processed_by: Mapped["User"] = relationship()
    invoice: Mapped[Optional["Invoice"]] = relationship()
    visit: Mapped[Optional["Visit"]] = relationship()
    payment: Mapped[Optional["Payment"]] = relationship(back_populates="membership_card_transaction")


class PaystackTransaction(TenantTable):
    """Tracks individual Paystack payment sessions for auditing and wallet funding."""

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    membership_card_id: Mapped[int] = mapped_column(ForeignKey("membership_card.id"), nullable=False, index=True)

    reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    access_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    authorization_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="NGN", nullable=False)

    status: Mapped[PaystackTransactionStatus] = mapped_column(
        Enum(PaystackTransactionStatus),
        default=PaystackTransactionStatus.PENDING,
        nullable=False,
        index=True,
    )

    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="paystack_transactions")
    membership_card: Mapped["MembershipCard"] = relationship()


# ============================================================
# ADMISSION / WARDS / BEDS / DISCHARGE
# ============================================================


class Ward(TenantTable):
    """
    Inpatient ward.

    Pricing
    -------
    ``daily_rate`` is the default per-night charge applied when a patient is
    admitted to a bed in this ward. The charge-capture helper looks up
    ``Bed.daily_rate_override`` first; if absent, it falls back to the
    ward's ``daily_rate``. ``billable_service_id`` is an optional pointer to
    the canonical entry in :class:`BillableService` so finance teams can keep
    pricing centralised in the catalog.
    """

    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    ward_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Bed-day pricing fields. ``daily_rate`` is per night per bed in this ward.
    daily_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    billable_service_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("billable_service.id"),
        nullable=True,
        index=True,
        doc="Optional pointer to the canonical billable-service catalog row.",
    )

    beds: Mapped[list["Bed"]] = relationship(back_populates="ward")
    admissions: Mapped[list["Admission"]] = relationship(back_populates="ward")


class Bed(TenantTable):
    """
    Bed inside a ward.

    Pricing
    -------
    ``daily_rate_override`` lets premium beds (e.g., a deluxe suite inside
    a general ward) charge a different per-night rate than the ward default.
    When unset, the parent ward's ``daily_rate`` is used.
    """

    ward_id: Mapped[int] = mapped_column(ForeignKey("ward.id"), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)

    bed_no: Mapped[str] = mapped_column(String(100), nullable=False)
    bed_status: Mapped[BedStatus] = mapped_column(
        Enum(BedStatus),
        default=BedStatus.AVAILABLE,
        nullable=False,
        index=True,
    )
    bed_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optional per-bed price override. NULL means "use ward.daily_rate".
    daily_rate_override: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    ward: Mapped["Ward"] = relationship(back_populates="beds")
    admissions: Mapped[list["Admission"]] = relationship(back_populates="bed")

    __table_args__ = (
        UniqueConstraint("ward_id", "bed_no", name="uq_ward_bed_no"),
    )


class Admission(TenantTable):
    """Admission record for inpatient management."""

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True, index=True)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ward.id"), nullable=True, index=True)
    bed_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bed.id"), nullable=True, index=True)
    admitted_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    admission_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    admission_status: Mapped[AdmissionStatus] = mapped_column(
        Enum(AdmissionStatus),
        default=AdmissionStatus.PENDING,
        nullable=False,
        index=True,
    )

    admission_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_discharge_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_discharge_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="admissions")
    visit: Mapped[Optional["Visit"]] = relationship(back_populates="admissions")
    ward: Mapped[Optional["Ward"]] = relationship(back_populates="admissions")
    bed: Mapped[Optional["Bed"]] = relationship(back_populates="admissions")
    admitted_by_staff: Mapped[Optional["StaffProfile"]] = relationship()

    discharge: Mapped[Optional["Discharge"]] = relationship(
        back_populates="admission",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Discharge(TenantTable):
    """Discharge summary/event for an admission."""

    admission_id: Mapped[int] = mapped_column(
        ForeignKey("admission.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    discharged_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    discharge_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    discharge_condition: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    discharge_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_instruction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    admission: Mapped["Admission"] = relationship(back_populates="discharge")
    discharged_by_staff: Mapped[Optional["StaffProfile"]] = relationship()


# ============================================================
# INVENTORY / STOCK
# ============================================================


class InventoryStore(TenantTable):
    """Physical or logical inventory store."""

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    location_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    stock_items: Mapped[list["InventoryStockItem"]] = relationship(back_populates="store")
    stock_movements: Mapped[list["StockMovement"]] = relationship(back_populates="store")


class InventoryStockItem(TenantTable):
    """Inventory item record for stock-tracked items."""

    store_id: Mapped[int] = mapped_column(ForeignKey("inventory_store.id"), nullable=False, index=True)
    drug_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drug.id"), nullable=True, index=True)

    item_type: Mapped[InventoryItemType] = mapped_column(
        Enum(InventoryItemType),
        nullable=False,
        index=True,
    )

    item_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    reorder_level: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    batch_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    store: Mapped["InventoryStore"] = relationship(back_populates="stock_items")
    drug: Mapped[Optional["Drug"]] = relationship(back_populates="stock_items")
    stock_movements: Mapped[list["StockMovement"]] = relationship(back_populates="stock_item")


class StockMovement(TenantTable):
    """Tracks stock inflow/outflow events."""

    store_id: Mapped[int] = mapped_column(ForeignKey("inventory_store.id"), nullable=False, index=True)
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_stock_item.id"), nullable=False, index=True)
    performed_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    movement_type: Mapped[StockMovementType] = mapped_column(
        Enum(StockMovementType),
        nullable=False,
        index=True,
    )

    reference_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    balance_after: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    movement_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    store: Mapped["InventoryStore"] = relationship(back_populates="stock_movements")
    stock_item: Mapped["InventoryStockItem"] = relationship(back_populates="stock_movements")
    performed_by_staff: Mapped[Optional["StaffProfile"]] = relationship()


# ============================================================
# AMBULANCE / EMERGENCY TRANSPORT
# ============================================================


class Ambulance(TenantTable):
    """Ambulance master record."""

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    plate_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    model: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    year_of_manufacture: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    status: Mapped[AmbulanceStatus] = mapped_column(
        Enum(AmbulanceStatus),
        default=AmbulanceStatus.AVAILABLE,
        nullable=False,
        index=True,
    )

    current_mileage: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    dispatches: Mapped[list["AmbulanceDispatch"]] = relationship(back_populates="ambulance")
    maintenance_records: Mapped[list["AmbulanceMaintenance"]] = relationship(back_populates="ambulance")
    equipment_items: Mapped[list["AmbulanceEquipment"]] = relationship(back_populates="ambulance")
    drivers: Mapped[list["AmbulanceDriver"]] = relationship(back_populates="ambulance")


class AmbulanceDriver(TenantTable):
    """Driver assignment and qualification record for ambulance operations."""

    staff_profile_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False, index=True)
    ambulance_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ambulance.id"), nullable=True, index=True)

    driver_license_no: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    license_expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_primary_driver: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    emergency_response_certified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    staff_profile: Mapped["StaffProfile"] = relationship()
    ambulance: Mapped[Optional["Ambulance"]] = relationship(back_populates="drivers")
    dispatches: Mapped[list["AmbulanceDispatch"]] = relationship(back_populates="driver")


class AmbulanceDispatch(TenantTable):
    """Dispatch event for an ambulance call."""

    ambulance_id: Mapped[int] = mapped_column(ForeignKey("ambulance.id"), nullable=False, index=True)
    driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ambulance_driver.id"), nullable=True, index=True)
    patient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patient.id"), nullable=True, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True, index=True)

    dispatch_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    dispatch_status: Mapped[AmbulanceDispatchStatus] = mapped_column(
        Enum(AmbulanceDispatchStatus),
        default=AmbulanceDispatchStatus.PENDING,
        nullable=False,
        index=True,
    )

    pickup_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    destination_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    incident_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    departed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    ambulance: Mapped["Ambulance"] = relationship(back_populates="dispatches")
    driver: Mapped[Optional["AmbulanceDriver"]] = relationship(back_populates="dispatches")
    patient: Mapped[Optional["Patient"]] = relationship()
    visit: Mapped[Optional["Visit"]] = relationship()

    incident_reports: Mapped[list["AmbulanceIncidentReport"]] = relationship(
        back_populates="dispatch",
        cascade="all, delete-orphan",
    )


class AmbulanceMaintenance(TenantTable):
    """Maintenance log for ambulances."""

    ambulance_id: Mapped[int] = mapped_column(ForeignKey("ambulance.id"), nullable=False, index=True)

    maintenance_status: Mapped[MaintenanceStatus] = mapped_column(
        Enum(MaintenanceStatus),
        default=MaintenanceStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    maintenance_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issue_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    service_provider: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    maintenance_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    mileage_at_service: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    ambulance: Mapped["Ambulance"] = relationship(back_populates="maintenance_records")


class AmbulanceEquipment(TenantTable):
    """Equipment assigned to an ambulance."""

    ambulance_id: Mapped[int] = mapped_column(ForeignKey("ambulance.id"), nullable=False, index=True)

    equipment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=1)
    condition_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ambulance: Mapped["Ambulance"] = relationship(back_populates="equipment_items")


class AmbulanceIncidentReport(TenantTable):
    """Incident report generated during or after an ambulance dispatch."""

    dispatch_id: Mapped[int] = mapped_column(ForeignKey("ambulance_dispatch.id"), nullable=False, index=True)
    reported_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity),
        default=IncidentSeverity.MEDIUM,
        nullable=False,
        index=True,
    )

    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    dispatch: Mapped["AmbulanceDispatch"] = relationship(back_populates="incident_reports")
    reported_by_staff: Mapped[Optional["StaffProfile"]] = relationship()


# ============================================================
# EMPLOYEE HR / DEVELOPMENT / PERFORMANCE
# ============================================================


class EmployeeCertification(TenantTable):
    """Professional certification held by a staff member."""

    staff_profile_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False, index=True)

    certification_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuing_body: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    certificate_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    staff_profile: Mapped["StaffProfile"] = relationship()


class EmployeeTraining(TenantTable):
    """Training attended or assigned to a staff member."""

    staff_profile_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False, index=True)

    training_title: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    certificate_received: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    staff_profile: Mapped["StaffProfile"] = relationship()


class EmployeeSchedule(TenantTable):
    """Published schedule period for employee duty planning."""

    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("department.id"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[EmployeeScheduleStatus] = mapped_column(
        Enum(EmployeeScheduleStatus),
        default=EmployeeScheduleStatus.DRAFT,
        nullable=False,
        index=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    department: Mapped[Optional["Department"]] = relationship(back_populates="employee_schedules")
    shifts: Mapped[list["EmployeeShift"]] = relationship(
        back_populates="employee_schedule",
        cascade="all, delete-orphan",
    )


class EmployeeShift(TenantTable):
    """Individual employee shift inside a schedule."""

    employee_schedule_id: Mapped[int] = mapped_column(ForeignKey("employee_schedule.id"), nullable=False, index=True)
    staff_profile_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False, index=True)
    service_delivery_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_delivery_point.id"),
        nullable=True,
        index=True,
    )

    shift_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    shift_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shift_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus),
        default=ShiftStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    employee_schedule: Mapped["EmployeeSchedule"] = relationship(back_populates="shifts")
    staff_profile: Mapped["StaffProfile"] = relationship()
    service_delivery_point: Mapped[Optional["ServiceDeliveryPoint"]] = relationship(back_populates="employee_shifts")


class EmployeeLeave(TenantTable):
    """Employee leave application and tracking."""

    staff_profile_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False, index=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    leave_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[LeaveStatus] = mapped_column(
        Enum(LeaveStatus),
        default=LeaveStatus.PENDING,
        nullable=False,
        index=True,
    )

    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    staff_profile: Mapped["StaffProfile"] = relationship()
    approved_by: Mapped[Optional["User"]] = relationship()


class EmployeePerformance(TenantTable):
    """Performance review record for a staff member."""

    staff_profile_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False, index=True)
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    review_period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    review_period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    performance_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    strengths: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    improvement_areas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[PerformanceStatus] = mapped_column(
        Enum(PerformanceStatus),
        default=PerformanceStatus.DRAFT,
        nullable=False,
        index=True,
    )

    staff_profile: Mapped["StaffProfile"] = relationship()
    reviewer: Mapped[Optional["User"]] = relationship()


class EmployeeDisciplinaryAction(TenantTable):
    """Disciplinary action record for an employee."""

    staff_profile_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False, index=True)
    reported_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    action_type: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[DisciplinaryActionStatus] = mapped_column(
        Enum(DisciplinaryActionStatus),
        default=DisciplinaryActionStatus.OPEN,
        nullable=False,
        index=True,
    )

    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    staff_profile: Mapped["StaffProfile"] = relationship()
    reported_by: Mapped[Optional["User"]] = relationship()


# ============================================================
# MESSAGING / NOTIFICATIONS / AUDIT
# ============================================================


class Message(TenantTable):
    """Direct or system-generated message record."""

    sender_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)
    recipient_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)

    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[MessageStatus] = mapped_column(
        Enum(MessageStatus),
        default=MessageStatus.DRAFT,
        nullable=False,
        index=True,
    )

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    sender_user: Mapped[Optional["User"]] = relationship(foreign_keys=[sender_user_id])
    recipient_user: Mapped[Optional["User"]] = relationship(foreign_keys=[recipient_user_id])


class NotificationTemplate(TenantTable):
    """Reusable notification template."""

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel),
        nullable=False,
        index=True,
    )

    subject_template: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)


class DocumentTemplate(TenantTable):
    """Reusable HTML document templates (Invoices, Receipts, etc.)"""

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    template_type: Mapped[DocumentTemplateType] = mapped_column(
        Enum(DocumentTemplateType), nullable=False, index=True
    )
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)



class Notification(TenantTable):
    """Notification record for in-app, email, SMS, WhatsApp, or push."""

    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)
    patient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patient.id"), nullable=True, index=True)
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("notification_template.id"), nullable=True)

    # Canonical event code (matches NotificationEvent enum). Optional for
    # backward compatibility — older rows may not have one.
    event_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)

    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel),
        nullable=False,
        index=True,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus),
        default=NotificationStatus.PENDING,
        nullable=False,
        index=True,
    )

    recipient_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    payload_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[Optional["User"]] = relationship()
    patient: Mapped[Optional["Patient"]] = relationship(back_populates="notifications")
    template: Mapped[Optional["NotificationTemplate"]] = relationship()


class UserInvitation(TenantTable):
    """
    Tenant-side user invitation.

    A tenant admin invites a new user by email or phone number. We persist
    a unique, securely-generated token (hashed at rest) with an expiry,
    optional pre-assigned roles, and current lifecycle status. The plain
    token is delivered via the platform notification dispatcher and is
    only ever returned in the response to ``invite_user`` so callers can
    embed it in an emailed link.
    """

    __tablename__ = "user_invitation"

    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(InvitationStatus),
        default=InvitationStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Roles to assign when the invitation is accepted.
    role_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Lifecycle bookkeeping.
    invited_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    accepted_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resend_count: Mapped[int] = mapped_column(Integer, default=0)


class TenantScheduledJob(TenantTable):
    """
    Per-tenant scheduled job definition.

    Each tenant may register their own recurring tasks (reminders, custom
    reports, backups beyond the platform default) without changing the
    global scheduler. The tenant-aware dispatcher (see
    ``app/services/tenant_job_runner.py``) walks active rows on every tick,
    sets the request-scoped tenant context, and invokes the matching
    handler.

    Lifecycle: ``last_run_at`` is updated on every run; ``last_status`` and
    ``last_error`` capture the outcome. Operators can pause a job by
    flipping ``is_enabled`` without losing history.
    """

    __tablename__ = "tenant_scheduled_job"

    job_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    handler: Mapped[str] = mapped_column(String(120), nullable=False)
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    schedule_interval_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0)


class PushDeviceToken(TenantTable):
    """
    Mobile/web push device token for a user (FCM/APNs/WebPush).

    A single user can have multiple devices; we store one row per
    (user_id, device_token) and prune stale entries when delivery fails.
    """

    __tablename__ = "push_device_token"

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    device_token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), default="WEB")  # WEB, IOS, ANDROID
    label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()

    __table_args__ = (
        Index(
            "uq_push_device_user_token",
            "user_id",
            "device_token",
            unique=True,
        ),
    )


class AuditLog(TenantTable):
    """Generic audit trail for sensitive actions."""

    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)

    action: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    before_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    actor_user: Mapped[Optional["User"]] = relationship()


# ============================================================
# COMPLIANCE / ACCREDITATION / INCIDENTS / QUALITY
# ============================================================


class ComplianceRecord(TenantTable):
    """Compliance obligation or review record."""

    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("department.id"), nullable=True, index=True)
    owner_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    compliance_area: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    reference_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus),
        default=ComplianceStatus.IN_PROGRESS,
        nullable=False,
        index=True,
    )

    findings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    department: Mapped[Optional["Department"]] = relationship()
    owner_staff: Mapped[Optional["StaffProfile"]] = relationship()


class Accreditation(TenantTable):
    """Hospital or departmental accreditation record."""

    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("department.id"), nullable=True, index=True)

    accreditation_body: Mapped[str] = mapped_column(String(255), nullable=False)
    accreditation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    certificate_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    status: Mapped[AccreditationStatus] = mapped_column(
        Enum(AccreditationStatus),
        default=AccreditationStatus.PENDING,
        nullable=False,
        index=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    department: Mapped[Optional["Department"]] = relationship()


class IncidentReport(TenantTable):
    """General operational or patient safety incident report."""

    reported_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)
    patient_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patient.id"), nullable=True, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("department.id"), nullable=True, index=True)

    incident_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity),
        default=IncidentSeverity.MEDIUM,
        nullable=False,
        index=True,
    )

    category: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    immediate_action_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    reported_by_staff: Mapped[Optional["StaffProfile"]] = relationship()
    patient: Mapped[Optional["Patient"]] = relationship()
    visit: Mapped[Optional["Visit"]] = relationship()
    department: Mapped[Optional["Department"]] = relationship()


class InfectionControlLog(TenantTable):
    """Infection control surveillance and response log."""

    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("department.id"), nullable=True, index=True)
    recorded_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    log_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    infection_type: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    affected_area: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    details: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    department: Mapped[Optional["Department"]] = relationship()
    recorded_by_staff: Mapped[Optional["StaffProfile"]] = relationship()


class QualityImprovementProject(TenantTable):
    """Quality improvement initiative or project."""

    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("department.id"), nullable=True, index=True)
    project_lead_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    problem_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    status: Mapped[QualityProjectStatus] = mapped_column(
        Enum(QualityProjectStatus),
        default=QualityProjectStatus.PLANNED,
        nullable=False,
        index=True,
    )

    outcome_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    department: Mapped[Optional["Department"]] = relationship()
    project_lead_staff: Mapped[Optional["StaffProfile"]] = relationship()

# ============================================================
# FACILITY / MULTI-BRANCH SCOPING
# ============================================================


class FacilityNetwork(TenantTable):
    """
    Hospital network / chain that owns one or more facilities.
    """

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    head_office_facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey(
            "facility.id", name="fk_facility_network_head_office", use_alter=True
        ),
        nullable=True,
    )

    facilities: Mapped[list["Facility"]] = relationship(
        back_populates="network",
        foreign_keys="Facility.network_id",
    )





class SubscriptionPlan(MasterTable):
    """
    Defines available subscription plans and their feature sets.

    Plans drive both *limits* (users / branches / storage) and *modular
    feature access* (clinical, inpatient, laboratory, pharmacy, inventory,
    billing, reporting). Per-tenant overrides are stored in
    :class:`TenantModuleAccess`.
    """

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.00)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    interval: Mapped[SubscriptionInterval] = mapped_column(
        Enum(SubscriptionInterval), default=SubscriptionInterval.MONTHLY
    )

    # Trial duration (in days). 0 means the plan does not offer a free trial.
    trial_days: Mapped[int] = mapped_column(Integer, default=0)

    # Tier-based limits.
    max_facilities: Mapped[int] = mapped_column(Integer, default=1)
    # Alias for "branches" terminology used by some clients.
    max_branches: Mapped[int] = mapped_column(Integer, default=1)
    max_users: Mapped[int] = mapped_column(Integer, default=10)
    max_patients: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = unlimited
    # Storage cap. None = unlimited.
    storage_limit_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Feature gating (also exposed via TenantModuleAccess for overrides).
    has_clinical: Mapped[bool] = mapped_column(Boolean, default=True)
    has_inpatient: Mapped[bool] = mapped_column(Boolean, default=False)
    has_laboratory: Mapped[bool] = mapped_column(Boolean, default=False)
    has_pharmacy: Mapped[bool] = mapped_column(Boolean, default=False)
    has_inventory: Mapped[bool] = mapped_column(Boolean, default=False)
    has_billing: Mapped[bool] = mapped_column(Boolean, default=True)
    has_reporting: Mapped[bool] = mapped_column(Boolean, default=False)
    has_appointments: Mapped[bool] = mapped_column(Boolean, default=True)
    has_patient_portal: Mapped[bool] = mapped_column(Boolean, default=False)
    has_insurance: Mapped[bool] = mapped_column(Boolean, default=False)
    has_radiology: Mapped[bool] = mapped_column(Boolean, default=False)
    has_surgical: Mapped[bool] = mapped_column(Boolean, default=False)
    has_hr: Mapped[bool] = mapped_column(Boolean, default=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class SaaSAdmin(MasterTable):
    """
    Platform administrator (SaaS-level operator).

    Platform admins manage tenants, subscriptions, plans, custom domains,
    billing, and system-wide settings. They are intentionally **walled off**
    from tenant data; access to a specific tenant database requires a
    :class:`SupportAccessGrant` approved by that tenant.

    Authority is governed by :class:`SaaSRole`. ``is_superuser`` is kept for
    legacy compatibility — it is true only for SUPER_ADMIN.
    """

    __tablename__ = "saas_admin"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=True)

    # Platform-level RBAC. Defaults to SUPPORT_ADMIN — the safest grant
    # for newly-provisioned admins.
    platform_role: Mapped[SaaSRole] = mapped_column(
        Enum(SaaSRole),
        default=SaaSRole.SUPPORT_ADMIN,
        nullable=False,
        index=True,
    )

    # Lockout / failed login tracking, mirroring User for parity.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SupportAccessGrant(MasterTable):
    """
    Audited support-access grant.

    A tenant admin (or SUPER_ADMIN as a fallback) approves a SaaS admin
    to access a specific tenant for a bounded window. Every login and
    every API call against the tenant scoped to this grant is logged
    against the grant ID so support actions can be replayed and audited.

    A grant is *required* before any platform admin can read tenant data
    or impersonate a tenant user, regardless of the admin's platform role.
    """

    __tablename__ = "support_access_grant"

    saas_admin_id: Mapped[int] = mapped_column(
        ForeignKey("saas_admin.id"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id"), nullable=False, index=True
    )

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SupportAccessStatus] = mapped_column(
        Enum(SupportAccessStatus),
        default=SupportAccessStatus.REQUESTED,
        nullable=False,
        index=True,
    )

    # Bounded window during which this grant is valid.
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Lifecycle bookkeeping.
    requested_by_admin_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("saas_admin.id"), nullable=True
    )
    approved_by_tenant_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Limits the actions the grant authorises (e.g. ["read", "impersonate"]).
    permissions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    saas_admin: Mapped["SaaSAdmin"] = relationship(foreign_keys=[saas_admin_id])
    tenant: Mapped["Tenant"] = relationship()


class SaaSAdminSession(MasterTable):
    """
    Session tracking for SaaS Admins.
    """
    __tablename__ = "saas_admin_session"

    saas_admin_id: Mapped[int] = mapped_column(ForeignKey("saas_admin.id"), nullable=False, index=True)
    access_jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    refresh_jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    saas_admin: Mapped["SaaSAdmin"] = relationship()


class SaaSAdminTwoFactorChallenge(MasterTable):
    """
    Two-factor authentication challenges for SaaS Administrators.
    Stored in the Master Database.
    """
    __tablename__ = "saas_admin_two_factor_challenge"

    saas_admin_id: Mapped[int] = mapped_column(ForeignKey("saas_admin.id"), nullable=False, index=True)
    challenge_type: Mapped[TwoFactorType] = mapped_column(Enum(TwoFactorType), nullable=False)
    purpose: Mapped[TwoFactorPurpose] = mapped_column(Enum(TwoFactorPurpose), nullable=False)
    destination: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    saas_admin: Mapped["SaaSAdmin"] = relationship()


class SaaSNotification(MasterTable):
    """
    In-App notifications specifically for SaaS Administrators.
    """
    __tablename__ = "saas_notification"

    saas_admin_id: Mapped[int] = mapped_column(ForeignKey("saas_admin.id"), nullable=False, index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus),
        default=NotificationStatus.PENDING,
    )
    
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    saas_admin: Mapped["SaaSAdmin"] = relationship()


class TenantSubscription(MasterTable):
    """
    Tracks the subscription history and current plan for a tenant.

    The pair (``current_period_start``, ``current_period_end``) drives the
    invoicing cycle: the billing service issues the next invoice when
    ``current_period_end`` is within the configured pre-issue window, and
    rolls the period forward when payment is received.
    """

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("subscription_plan.id"), nullable=False, index=True)

    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.TRIALING
    )

    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Current billing window. Updated when an invoice is paid.
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    next_invoice_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    auto_renew: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="subscriptions")
    plan: Mapped["SubscriptionPlan"] = relationship()


class SubscriptionInvoice(MasterTable):
    """
    SaaS-level invoice issued to a tenant for a single billing period.

    Invoices are generated automatically when the active subscription is
    nearing the end of its current period. Each invoice carries the plan
    snapshot (so historical line-items remain stable even when the plan
    is updated later), the billing period it covers, and the email it
    was sent to.

    Lifecycle:

        DRAFT → ISSUED → PARTIALLY_PAID? → PAID
                          \\__ OVERDUE
                          \\__ CANCELLED
                          \\__ REFUNDED
    """

    __tablename__ = "subscription_invoice"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("tenant_subscription.id"), nullable=False, index=True
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_plan.id"), nullable=False, index=True
    )

    invoice_number: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=False, index=True
    )

    # Plan snapshot (immutable) so historical invoices remain accurate.
    plan_code_snapshot: Mapped[str] = mapped_column(String(60), nullable=False)
    plan_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_interval_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)

    # Money
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    amount_due: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Period the invoice covers.
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[SubscriptionInvoiceStatus] = mapped_column(
        Enum(SubscriptionInvoiceStatus),
        default=SubscriptionInvoiceStatus.DRAFT,
        nullable=False,
        index=True,
    )

    # Free-form line-items so add-ons / proration / discounts can be itemised.
    line_items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Dispatch bookkeeping.
    sent_to_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reminder_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)

    tenant: Mapped["Tenant"] = relationship()
    subscription: Mapped["TenantSubscription"] = relationship()
    plan: Mapped["SubscriptionPlan"] = relationship()
    payments: Mapped[list["SubscriptionPayment"]] = relationship(back_populates="invoice")


class SubscriptionPayment(MasterTable):
    """
    Payment recorded against a :class:`SubscriptionInvoice`.

    A successful payment triggers receipt issuance via the notification
    dispatcher and rolls the parent subscription's billing window
    forward.
    """

    __tablename__ = "subscription_payment"

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_invoice.id"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN", nullable=False)

    payment_method: Mapped[str] = mapped_column(String(40), default="MANUAL")  # MANUAL, CARD, BANK_TRANSFER, ETC.
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(120), unique=True, nullable=True, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)  # PAYSTACK, FLUTTERWAVE, STRIPE, MANUAL

    status: Mapped[SubscriptionPaymentStatus] = mapped_column(
        Enum(SubscriptionPaymentStatus),
        default=SubscriptionPaymentStatus.SUCCEEDED,
        nullable=False,
        index=True,
    )

    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Receipt issued for this payment.
    receipt_number: Mapped[Optional[str]] = mapped_column(String(60), unique=True, nullable=True, index=True)
    receipt_sent_to_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    receipt_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    invoice: Mapped["SubscriptionInvoice"] = relationship(back_populates="payments")
    tenant: Mapped["Tenant"] = relationship()


class Tenant(MasterTable):
    """
    SaaS Tenant (Hospital Group / Single Facility Entity).
    Each tenant operates in its own isolated database instance.

    A tenant carries TWO contact points:

    * **billing_email / billing_phone / billing_contact_name** — captured
      during onboarding and used for SaaS-level financial communication
      (invoice issuance, payment receipts, renewal reminders, dunning).
      This may be different from the tenant admin's personal email
      (e.g. ``billing@stnicholas.com`` vs ``admin@stnicholas.com``).
    * **the tenant admin user** in the tenant DB — used for application-
      level notifications inside the tenant's own environment.

    Subscription invoices are *additionally* CC'd to the tenant admin so
    the operator and the finance contact both have visibility.
    """

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Custom URL / Domain support
    domain_url: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    custom_domain: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)

    # Database isolation metadata
    db_name: Mapped[str] = mapped_column(String(255), nullable=False)
    db_connection_string: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # AWS S3 Integration
    aws_s3_bucket_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ----- SaaS-level billing/communication contact ---------------------
    # The dedicated email used for invoices, receipts, and renewal alerts.
    # If the operator does not specify one at onboarding, the registration
    # service falls back to the admin email.
    billing_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    billing_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    billing_contact_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    billing_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tax_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE)
    is_provisioned: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    subscriptions: Mapped[list["TenantSubscription"]] = relationship(back_populates="tenant")

    @property
    def active_subscription(self) -> Optional["TenantSubscription"]:
        """
        Return the currently active subscription for this tenant.
        """
        for sub in self.subscriptions:
            if sub.status == SubscriptionStatus.ACTIVE and sub.is_active:
                return sub
        return None

class TenantUsage(MasterTable):
    """
    Tracks usage metrics per tenant in the master database.
    Used for billing, analytics, and SaaS-level monitoring.
    """
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), unique=True, nullable=False, index=True)
    
    user_count: Mapped[int] = mapped_column(Integer, default=0)
    storage_usage_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    api_call_count: Mapped[int] = mapped_column(BigInteger, default=0)
    transaction_count: Mapped[int] = mapped_column(BigInteger, default=0)
    sms_count: Mapped[int] = mapped_column(BigInteger, default=0)
    email_count: Mapped[int] = mapped_column(BigInteger, default=0)
    login_count: Mapped[int] = mapped_column(BigInteger, default=0)
    
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    tenant: Mapped["Tenant"] = relationship()



class EdgeNode(MasterTable):
    """
    On-premises edge node deployed at a tenant facility.

    The hospital runs a small server (often called a "boundary box" or
    "site server") that holds a local replica of the tenant database and
    exposes the API on the LAN. When the public internet drops, clinical
    staff continue to use the edge node — patient registration, vitals,
    prescriptions, dispenses, and cashier payments all keep working
    against the local DB. As soon as connectivity returns the
    :class:`EdgeSyncService` exchanges journals with the cloud and brings
    both copies back into agreement.

    Each node holds a hashed bearer token that authenticates its sync
    requests. The plain token is delivered once at registration time and
    never re-issued — lost tokens are rotated by re-provisioning the node.
    """

    __tablename__ = "edge_node"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # SHA-256 hash of the bearer token. The plaintext is shown to the
    # operator exactly once (at registration / rotation time) and never
    # stored.
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)

    public_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    app_version: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    schema_version: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    status: Mapped[EdgeNodeStatus] = mapped_column(
        Enum(EdgeNodeStatus),
        default=EdgeNodeStatus.PROVISIONED,
        nullable=False,
        index=True,
    )

    # Heartbeat / sync bookkeeping.
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_pulled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_pull_cursor: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    last_push_cursor: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    last_failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Heartbeat tolerance. Nodes that miss this window are flipped to
    # OFFLINE and surface in dashboards.
    heartbeat_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    heartbeat_grace_seconds: Mapped[int] = mapped_column(Integer, default=900)

    tenant: Mapped["Tenant"] = relationship()


class TenantDomain(MasterTable):
    """
    Custom domain attached to a tenant.

    A tenant always has a primary subdomain on the platform's base domain
    (``acme.carepointhms.com``). Tenants can additionally register their
    own custom domain (``portal.acmeclinic.com``) which must be verified
    via DNS before traffic is accepted.
    """

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    domain_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    # ----- DNS / verification -----
    verification_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ----- SSL / certificate state -----
    # Lifecycle: PENDING -> ISSUING -> ACTIVE | FAILED | EXPIRED
    ssl_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    ssl_issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ssl_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ssl_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    tenant: Mapped["Tenant"] = relationship()


class TenantModuleAccess(MasterTable):
    """
    Per-tenant override of which modules are enabled.

    Effective access is computed as::

        plan_default AND (override.is_enabled if override exists else True)

    See :func:`app.services.tenant_module_service.is_module_enabled`.
    """

    __tablename__ = "tenant_module_access"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    module_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship()

    __table_args__ = (
        Index(
            "uq_tenant_module_access_tenant_module",
            "tenant_id",
            "module_code",
            unique=True,
        ),
    )


class Facility(TenantTable):
    """
    A hospital facility / branch / clinic / outlet.
    """

    network_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility_network.id", name="fk_facility_network_id"),
        nullable=True,
        index=True,
    )
    parent_facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True
    )

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    facility_type: Mapped[FacilityType] = mapped_column(
        Enum(FacilityType),
        default=FacilityType.MAIN_HOSPITAL,
        nullable=False,
        index=True,
    )
    status: Mapped[FacilityStatus] = mapped_column(
        Enum(FacilityStatus),
        default=FacilityStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    address_line_1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    geo_latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(11, 7), nullable=True)
    geo_longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(11, 7), nullable=True)

    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    timezone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    license_number: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    tax_identification_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bed_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    facility_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    network: Mapped[Optional["FacilityNetwork"]] = relationship(
        back_populates="facilities",
        foreign_keys=[network_id],
    )
    parent_facility: Mapped[Optional["Facility"]] = relationship(
        remote_side="Facility.id",
        foreign_keys=[parent_facility_id],
    )
    service_areas: Mapped[list["FacilityServiceArea"]] = relationship(
        back_populates="facility",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_facility_network_status", "network_id", "status"),
    )


class FacilityServiceArea(TenantTable):
    """
    Catchment / service-area description for a facility.

    Useful for multi-branch routing decisions and reports such as
    "patients seen by region".
    """

    facility_id: Mapped[int] = mapped_column(ForeignKey("facility.id"), nullable=False, index=True)

    area_name: Mapped[str] = mapped_column(String(200), nullable=False)
    region_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    facility: Mapped["Facility"] = relationship(back_populates="service_areas")


# ============================================================
# RADIOLOGY / RIS
# ============================================================


class RadiologyProcedureCatalog(TenantTable):
    """Master list of radiology procedures (e.g. Chest X-Ray AP, CT Brain WC)."""

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    modality: Mapped[RadiologyModality] = mapped_column(
        Enum(RadiologyModality), nullable=False, index=True
    )
    body_part: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    cpt_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    typical_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    contrast_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    radiation_dose_msv: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    preparation_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RadiologyOrder(TenantTable):
    """Radiology order header for a visit."""

    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"), nullable=False, index=True)
    consultation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("consultation.id"), nullable=True, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    ordered_by_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("staff_profile.id"), nullable=True)

    order_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[RadiologyOrderStatus] = mapped_column(
        Enum(RadiologyOrderStatus),
        default=RadiologyOrderStatus.ORDERED,
        nullable=False,
        index=True,
    )
    priority: Mapped[VisitPriority] = mapped_column(
        Enum(VisitPriority), default=VisitPriority.NORMAL, nullable=False, index=True
    )
    clinical_indication: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pregnancy_screening: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    creatinine_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    items: Mapped[list["RadiologyOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_radiology_order_visit_status", "visit_id", "status"),
    )


class RadiologyOrderItem(TenantTable):
    """Individual procedure within a radiology order."""

    radiology_order_id: Mapped[int] = mapped_column(
        ForeignKey("radiology_order.id"), nullable=False, index=True
    )
    procedure_catalog_id: Mapped[int] = mapped_column(
        ForeignKey("radiology_procedure_catalog.id"), nullable=False, index=True
    )

    status: Mapped[RadiologyOrderStatus] = mapped_column(
        Enum(RadiologyOrderStatus),
        default=RadiologyOrderStatus.ORDERED,
        nullable=False,
        index=True,
    )
    laterality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped["RadiologyOrder"] = relationship(back_populates="items")
    procedure_catalog: Mapped["RadiologyProcedureCatalog"] = relationship()
    exam: Mapped[Optional["RadiologyExam"]] = relationship(
        back_populates="order_item",
        uselist=False,
        cascade="all, delete-orphan",
    )


class RadiologyExam(TenantTable):
    """Execution record of a radiology procedure."""

    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("radiology_order_item.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    performed_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    machine_identifier: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    accession_number: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, index=True
    )
    status: Mapped[RadiologyExamStatus] = mapped_column(
        Enum(RadiologyExamStatus),
        default=RadiologyExamStatus.SCHEDULED,
        nullable=False,
        index=True,
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    contrast_administered: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    technical_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order_item: Mapped["RadiologyOrderItem"] = relationship(back_populates="exam")
    images: Mapped[list["RadiologyImage"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan"
    )
    report: Mapped[Optional["RadiologyReport"]] = relationship(
        back_populates="exam", uselist=False, cascade="all, delete-orphan"
    )


class RadiologyImage(TenantTable):
    """PACS/DICOM image reference linked to an exam."""

    exam_id: Mapped[int] = mapped_column(ForeignKey("radiology_exam.id"), nullable=False, index=True)

    sop_instance_uid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    series_instance_uid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    study_instance_uid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pacs_archive_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    exam: Mapped["RadiologyExam"] = relationship(back_populates="images")


class RadiologyReport(TenantTable):
    """Radiologist reading of an exam."""

    exam_id: Mapped[int] = mapped_column(
        ForeignKey("radiology_exam.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    reported_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    verified_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )

    status: Mapped[RadiologyReportStatus] = mapped_column(
        Enum(RadiologyReportStatus),
        default=RadiologyReportStatus.DRAFT,
        nullable=False,
        index=True,
    )

    findings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    impression: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    drafted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    exam: Mapped["RadiologyExam"] = relationship(back_populates="report")


# ============================================================
# THEATRE & SURGICAL MANAGEMENT
# ============================================================


class OperatingTheatre(TenantTable):
    """A physical operating theatre/room."""

    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    location_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[TheatreStatus] = mapped_column(
        Enum(TheatreStatus),
        default=TheatreStatus.AVAILABLE,
        nullable=False,
        index=True,
    )
    is_emergency_capable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    capabilities: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SurgicalProcedureCatalog(TenantTable):
    """Master catalog of surgical procedures."""

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    cpt_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    typical_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requires_blood_products: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    average_blood_loss_ml: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    default_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pre_op_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    post_op_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SurgicalCase(TenantTable):
    """A booked / scheduled / performed surgical case."""

    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    procedure_catalog_id: Mapped[int] = mapped_column(
        ForeignKey("surgical_procedure_catalog.id"), nullable=False, index=True
    )
    operating_theatre_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("operating_theatre.id"), nullable=True, index=True
    )

    case_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[SurgicalCaseStatus] = mapped_column(
        Enum(SurgicalCaseStatus),
        default=SurgicalCaseStatus.BOOKED,
        nullable=False,
        index=True,
    )
    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    asa_class: Mapped[Optional[ASAClass]] = mapped_column(Enum(ASAClass), nullable=True)
    anaesthesia_type: Mapped[Optional[AnaesthesiaType]] = mapped_column(
        Enum(AnaesthesiaType), nullable=True
    )

    scheduled_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pre_op_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    incision_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    out_of_theatre_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    diagnosis_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    findings_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    team_members: Mapped[list["SurgicalTeamMember"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    consents: Mapped[list["SurgicalConsent"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    checklists: Mapped[list["SurgicalSafetyChecklist"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    anaesthesia_records: Mapped[list["AnaesthesiaRecord"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    theatre_notes: Mapped[list["TheatreNote"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    instrument_sets_used: Mapped[list["SurgicalInstrumentSet"]] = relationship(
        back_populates="case",
    )

    __table_args__ = (
        Index("ix_surgical_case_status_scheduled", "status", "scheduled_start_at"),
    )


class SurgicalTeamMember(TenantTable):
    """A staff member's role on a surgical case."""

    surgical_case_id: Mapped[int] = mapped_column(
        ForeignKey("surgical_case.id"), nullable=False, index=True
    )
    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    role: Mapped[SurgicalRole] = mapped_column(Enum(SurgicalRole), nullable=False, index=True)
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    case: Mapped["SurgicalCase"] = relationship(back_populates="team_members")
    staff_profile: Mapped["StaffProfile"] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "surgical_case_id", "staff_profile_id", "role",
            name="uq_surgical_team_member_role",
        ),
    )


class SurgicalConsent(TenantTable):
    """Patient consent for a surgical case."""

    surgical_case_id: Mapped[int] = mapped_column(
        ForeignKey("surgical_case.id"), nullable=False, index=True
    )
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)
    consent_signed_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    relationship_to_patient: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    witnessed_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signature_image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    case: Mapped["SurgicalCase"] = relationship(back_populates="consents")
    witnessed_by_staff: Mapped[Optional["StaffProfile"]] = relationship()


class SurgicalSafetyChecklist(TenantTable):
    """WHO surgical safety checklist phase record."""

    surgical_case_id: Mapped[int] = mapped_column(
        ForeignKey("surgical_case.id"), nullable=False, index=True
    )
    phase: Mapped[SurgicalChecklistPhase] = mapped_column(
        Enum(SurgicalChecklistPhase), nullable=False, index=True
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    items: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    case: Mapped["SurgicalCase"] = relationship(back_populates="checklists")
    completed_by_staff: Mapped[Optional["StaffProfile"]] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "surgical_case_id", "phase",
            name="uq_surgical_checklist_phase",
        ),
    )


class AnaesthesiaRecord(TenantTable):
    """Anaesthesia administration and monitoring record."""

    surgical_case_id: Mapped[int] = mapped_column(
        ForeignKey("surgical_case.id"), nullable=False, index=True
    )
    anaesthetist_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )

    anaesthesia_type: Mapped[AnaesthesiaType] = mapped_column(
        Enum(AnaesthesiaType), nullable=False, index=True
    )
    induction_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    emergence_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    agents: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    monitoring_intervals: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    complications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    case: Mapped["SurgicalCase"] = relationship(back_populates="anaesthesia_records")
    anaesthetist_staff: Mapped[Optional["StaffProfile"]] = relationship()


class TheatreNote(TenantTable):
    """Free-text intra-operative note."""

    surgical_case_id: Mapped[int] = mapped_column(
        ForeignKey("surgical_case.id"), nullable=False, index=True
    )
    author_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    note_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    case: Mapped["SurgicalCase"] = relationship(back_populates="theatre_notes")
    author_staff: Mapped[Optional["StaffProfile"]] = relationship()


class SurgicalInstrumentSet(TenantTable):
    """A reusable instrument tray that goes through sterilization cycles."""

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)

    surgical_case_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("surgical_case.id"), nullable=True, index=True
    )
    sterilization_status: Mapped[SterilizationStatus] = mapped_column(
        Enum(SterilizationStatus),
        default=SterilizationStatus.READY,
        nullable=False,
        index=True,
    )
    last_autoclaved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_required_sterilization_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    contents: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    case: Mapped[Optional["SurgicalCase"]] = relationship(back_populates="instrument_sets_used")
    sterilization_logs: Mapped[list["InstrumentSterilizationLog"]] = relationship(
        back_populates="instrument_set", cascade="all, delete-orphan"
    )


class InstrumentSterilizationLog(TenantTable):
    """Per-cycle sterilization audit log."""

    instrument_set_id: Mapped[int] = mapped_column(
        ForeignKey("surgical_instrument_set.id"), nullable=False, index=True
    )
    performed_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    cycle_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cycle_ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    machine_identifier: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    indicator_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    instrument_set: Mapped["SurgicalInstrumentSet"] = relationship(back_populates="sterilization_logs")
    performed_by_staff: Mapped[Optional["StaffProfile"]] = relationship()


# ============================================================
# PROCUREMENT & SUPPLIERS
# ============================================================


class Supplier(TenantTable):
    """Vendor / supplier master record."""

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    legal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tax_identification_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    registration_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    primary_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    primary_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    address_line_1: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    payment_terms: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    contacts: Mapped[list["SupplierContact"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )
    contracts: Mapped[list["SupplierContract"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")
    invoices: Mapped[list["SupplierInvoice"]] = relationship(back_populates="supplier")


class SupplierContact(TenantTable):
    """Named contact at a supplier."""

    supplier_id: Mapped[int] = mapped_column(ForeignKey("supplier.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    supplier: Mapped["Supplier"] = relationship(back_populates="contacts")


class SupplierContract(TenantTable):
    """Framework / pricing contract with a supplier."""

    supplier_id: Mapped[int] = mapped_column(ForeignKey("supplier.id"), nullable=False, index=True)
    contract_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[SupplierContractStatus] = mapped_column(
        Enum(SupplierContractStatus),
        default=SupplierContractStatus.DRAFT,
        nullable=False,
        index=True,
    )
    contract_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    pricing_terms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    supplier: Mapped["Supplier"] = relationship(back_populates="contracts")


class PurchaseRequisition(TenantTable):
    """Internal request to procure goods or services."""

    requisition_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("department.id"), nullable=True, index=True)
    requested_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    department_approved_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    finance_approved_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )

    status: Mapped[ProcurementRequisitionStatus] = mapped_column(
        Enum(ProcurementRequisitionStatus),
        default=ProcurementRequisitionStatus.DRAFT,
        nullable=False,
        index=True,
    )
    needed_by: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Link to approval engine
    approval_request_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    items: Mapped[list["PurchaseRequisitionItem"]] = relationship(
        back_populates="requisition", cascade="all, delete-orphan"
    )


class PurchaseRequisitionItem(TenantTable):
    """Line item on a purchase requisition."""

    requisition_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_requisition.id"), nullable=False, index=True
    )
    drug_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drug.id"), nullable=True, index=True)
    inventory_stock_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("inventory_stock_item.id"), nullable=True, index=True
    )

    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    item_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity_requested: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    estimated_unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    estimated_line_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)

    requisition: Mapped["PurchaseRequisition"] = relationship(back_populates="items")
    drug: Mapped[Optional["Drug"]] = relationship()
    inventory_stock_item: Mapped[Optional["InventoryStockItem"]] = relationship()


class RequestForQuotation(TenantTable):
    """An RFQ sent to suppliers in response to a requisition."""

    rfq_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    requisition_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("purchase_requisition.id"), nullable=True, index=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    issued_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    status: Mapped[RFQStatus] = mapped_column(
        Enum(RFQStatus), default=RFQStatus.DRAFT, nullable=False, index=True
    )
    response_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_supplier_ids: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    quotations: Mapped[list["Quotation"]] = relationship(back_populates="rfq")
    items: Mapped[list["RequestForQuotationItem"]] = relationship(back_populates="rfq", cascade="all, delete-orphan")
    vendors: Mapped[list["RequestForQuotationVendor"]] = relationship(back_populates="rfq", cascade="all, delete-orphan")


class RequestForQuotationItem(TenantTable):
    """Specific items requested in an RFQ."""

    rfq_id: Mapped[int] = mapped_column(ForeignKey("request_for_quotation.id"), nullable=False, index=True)
    requisition_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_requisition_item.id"), nullable=True, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    
    rfq: Mapped["RequestForQuotation"] = relationship(back_populates="items")
    requisition_item: Mapped[Optional["PurchaseRequisitionItem"]] = relationship()


class RequestForQuotationVendor(TenantTable):
    """Vendors invited to bid on an RFQ."""

    rfq_id: Mapped[int] = mapped_column(ForeignKey("request_for_quotation.id"), nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("supplier.id"), nullable=False, index=True)
    
    rfq: Mapped["RequestForQuotation"] = relationship(back_populates="vendors")
    vendor: Mapped["Supplier"] = relationship()


class Quotation(TenantTable):
    """A supplier's quotation in response to an RFQ."""

    rfq_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("request_for_quotation.id"), nullable=True, index=True
    )
    supplier_id: Mapped[int] = mapped_column(ForeignKey("supplier.id"), nullable=False, index=True)
    quotation_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[QuotationStatus] = mapped_column(
        Enum(QuotationStatus),
        default=QuotationStatus.RECEIVED,
        nullable=False,
        index=True,
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rfq: Mapped[Optional["RequestForQuotation"]] = relationship(back_populates="quotations")
    supplier: Mapped["Supplier"] = relationship()
    lines: Mapped[list["QuotationLine"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan"
    )


class QuotationLine(TenantTable):
    """Line item on a supplier quotation."""

    quotation_id: Mapped[int] = mapped_column(ForeignKey("quotation.id"), nullable=False, index=True)
    requisition_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("purchase_requisition_item.id"), nullable=True, index=True
    )

    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_quoted: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    delivery_lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    quotation: Mapped["Quotation"] = relationship(back_populates="lines")
    requisition_item: Mapped[Optional["PurchaseRequisitionItem"]] = relationship()


class PurchaseOrder(TenantTable):
    """A confirmed purchase order issued to a supplier."""

    po_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("supplier.id"), nullable=False, index=True)
    requisition_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("purchase_requisition.id"), nullable=True, index=True
    )
    quotation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("quotation.id"), nullable=True, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    issued_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )

    status: Mapped[PurchaseOrderStatus] = mapped_column(
        Enum(PurchaseOrderStatus),
        default=PurchaseOrderStatus.DRAFT,
        nullable=False,
        index=True,
    )
    expected_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    subtotal_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    tax_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    discount_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    supplier: Mapped["Supplier"] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )
    goods_receipts: Mapped[list["GoodsReceiptNote"]] = relationship(back_populates="purchase_order")


class PurchaseOrderItem(TenantTable):
    """Line item on a purchase order."""

    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order.id"), nullable=False, index=True
    )
    drug_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drug.id"), nullable=True, index=True)
    inventory_stock_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("inventory_stock_item.id"), nullable=True, index=True
    )

    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
    drug: Mapped[Optional["Drug"]] = relationship()
    inventory_stock_item: Mapped[Optional["InventoryStockItem"]] = relationship()


class GoodsReceiptNote(TenantTable):
    """Receipt note for goods delivered against a purchase order."""

    grn_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order.id"), nullable=False, index=True
    )
    received_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    target_store_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("inventory_store.id"), nullable=True, index=True
    )

    status: Mapped[GoodsReceiptStatus] = mapped_column(
        Enum(GoodsReceiptStatus),
        default=GoodsReceiptStatus.DRAFT,
        nullable=False,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivery_note_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    inspector_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="goods_receipts")
    items: Mapped[list["GoodsReceiptItem"]] = relationship(
        back_populates="grn", cascade="all, delete-orphan"
    )


class GoodsReceiptItem(TenantTable):
    """Per-line receipt detail."""

    grn_id: Mapped[int] = mapped_column(
        ForeignKey("goods_receipt_note.id"), nullable=False, index=True
    )
    purchase_order_item_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order_item.id"), nullable=False, index=True
    )
    inventory_stock_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("inventory_stock_item.id"), nullable=True, index=True
    )
    stock_movement_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("stock_movement.id"), nullable=True, index=True
    )

    quantity_received: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity_rejected: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    batch_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    unit_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    grn: Mapped["GoodsReceiptNote"] = relationship(back_populates="items")
    purchase_order_item: Mapped["PurchaseOrderItem"] = relationship()
    inventory_stock_item: Mapped[Optional["InventoryStockItem"]] = relationship()


class SupplierInvoice(TenantTable):
    """Accounts-payable invoice from a supplier."""

    invoice_no: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("supplier.id"), nullable=False, index=True)
    purchase_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("purchase_order.id"), nullable=True, index=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)

    status: Mapped[SupplierInvoiceStatus] = mapped_column(
        Enum(SupplierInvoiceStatus),
        default=SupplierInvoiceStatus.DRAFT,
        nullable=False,
        index=True,
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    balance_due: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    supplier: Mapped["Supplier"] = relationship(back_populates="invoices")
    payments: Mapped[list["SupplierPayment"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("supplier_id", "invoice_no", name="uq_supplier_invoice_per_supplier"),
        Index("ix_supplier_invoice_status_due", "status", "due_date"),
    )


class SupplierPayment(TenantTable):
    """Payment against a supplier invoice."""

    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_invoice.id"), nullable=False, index=True
    )
    payment_reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    paid_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    payment_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bank_reference: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    invoice: Mapped["SupplierInvoice"] = relationship(back_populates="payments")


# ============================================================
# INSURANCE CLAIMS
# ============================================================


class ClaimBatch(TenantTable):
    """Batch of insurance claims submitted to an insurer."""

    batch_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    insurance_provider_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_provider.id"), nullable=False, index=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    submitted_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )

    status: Mapped[ClaimBatchStatus] = mapped_column(
        Enum(ClaimBatchStatus),
        default=ClaimBatchStatus.DRAFT,
        nullable=False,
        index=True,
    )
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_claims: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_billed_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    total_approved_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    insurance_provider: Mapped["InsuranceProvider"] = relationship()
    claims: Mapped[list["InsuranceClaim"]] = relationship(back_populates="batch")


class InsuranceClaim(TenantTable):
    """A single insurance claim, typically per visit or per invoice."""

    claim_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("claim_batch.id"), nullable=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    patient_insurance_id: Mapped[int] = mapped_column(
        ForeignKey("patient_insurance.id"), nullable=False, index=True
    )
    insurance_provider_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_provider.id"), nullable=False, index=True
    )
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("invoice.id"), nullable=True, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)

    status: Mapped[InsuranceClaimStatus] = mapped_column(
        Enum(InsuranceClaimStatus),
        default=InsuranceClaimStatus.DRAFT,
        nullable=False,
        index=True,
    )

    service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    diagnosis_codes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    primary_diagnosis_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    billed_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    approved_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    rejected_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    patient_responsibility_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)

    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    batch: Mapped[Optional["ClaimBatch"]] = relationship(back_populates="claims")
    patient: Mapped["Patient"] = relationship()
    patient_insurance: Mapped["PatientInsurance"] = relationship()
    insurance_provider: Mapped["InsuranceProvider"] = relationship()
    visit: Mapped[Optional["Visit"]] = relationship()
    invoice: Mapped[Optional["Invoice"]] = relationship()

    items: Mapped[list["InsuranceClaimItem"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    authorizations: Mapped[list["ClaimAuthorization"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    adjudications: Mapped[list["ClaimAdjudication"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    claim_payments: Mapped[list["ClaimPayment"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    appeals: Mapped[list["ClaimAppeal"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )


class InsuranceClaimItem(TenantTable):
    """Line-level detail on an insurance claim."""

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_claim.id"), nullable=False, index=True
    )
    invoice_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoice_item.id"), nullable=True, index=True
    )
    billable_service_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("billable_service.id"), nullable=True, index=True
    )

    service_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    procedure_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    diagnosis_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    billed_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    approved_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    rejected_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)

    claim: Mapped["InsuranceClaim"] = relationship(back_populates="items")
    invoice_item: Mapped[Optional["InvoiceItem"]] = relationship()
    billable_service: Mapped[Optional["BillableService"]] = relationship()


class ClaimAuthorization(TenantTable):
    """Pre-authorization request and decision for a claim."""

    claim_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("insurance_claim.id"), nullable=True, index=True
    )
    patient_insurance_id: Mapped[int] = mapped_column(
        ForeignKey("patient_insurance.id"), nullable=False, index=True
    )
    authorization_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    requested_service: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    approved_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    status: Mapped[AuthorizationStatus] = mapped_column(
        Enum(AuthorizationStatus),
        default=AuthorizationStatus.REQUESTED,
        nullable=False,
        index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    claim: Mapped[Optional["InsuranceClaim"]] = relationship(back_populates="authorizations")
    patient_insurance: Mapped["PatientInsurance"] = relationship()


class ClaimAdjudication(TenantTable):
    """Insurer's adjudication record for a claim."""

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_claim.id"), nullable=False, index=True
    )
    adjudication_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    outcome: Mapped[AdjudicationOutcome] = mapped_column(
        Enum(AdjudicationOutcome), nullable=False, index=True
    )
    approved_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    rejected_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    rejection_codes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    explanation_of_benefit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    adjudicated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    claim: Mapped["InsuranceClaim"] = relationship(back_populates="adjudications")


class ClaimPayment(TenantTable):
    """Payment received from an insurer against a claim."""

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_claim.id"), nullable=False, index=True
    )
    payment_reference: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    claim: Mapped["InsuranceClaim"] = relationship(back_populates="claim_payments")


class ClaimAppeal(TenantTable):
    """An appeal against a (partially) rejected claim."""

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("insurance_claim.id"), nullable=False, index=True
    )
    appeal_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[ClaimAppealStatus] = mapped_column(
        Enum(ClaimAppealStatus),
        default=ClaimAppealStatus.DRAFT,
        nullable=False,
        index=True,
    )
    submitted_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    appeal_text: Mapped[str] = mapped_column(Text, nullable=False)
    additional_evidence_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    additional_amount_requested: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    additional_amount_approved: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)

    claim: Mapped["InsuranceClaim"] = relationship(back_populates="appeals")


# ============================================================
# PATIENT PORTAL
# ============================================================


class PortalAccount(TenantTable):
    """Self-service portal account for a patient (separate from staff Users)."""

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient.id"), unique=True, nullable=False, index=True
    )
    portal_username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True, index=True)

    status: Mapped[PortalAccountStatus] = mapped_column(
        Enum(PortalAccountStatus),
        default=PortalAccountStatus.PENDING_VERIFICATION,
        nullable=False,
        index=True,
    )
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["Patient"] = relationship()
    sessions: Mapped[list["PortalSession"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    challenges: Mapped[list["PortalAuthChallenge"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )
    preferences: Mapped[Optional["PortalPreferences"]] = relationship(
        back_populates="account", uselist=False, cascade="all, delete-orphan"
    )
    appointment_requests: Mapped[list["PortalAppointmentRequest"]] = relationship(
        back_populates="account"
    )
    messages: Mapped[list["PortalMessage"]] = relationship(back_populates="account")
    document_shares: Mapped[list["PortalDocumentShare"]] = relationship(back_populates="account")
    consent_logs: Mapped[list["PortalConsentLog"]] = relationship(back_populates="account")


class PortalSession(TenantTable):
    """Active session on the patient portal."""

    account_id: Mapped[int] = mapped_column(
        ForeignKey("portal_account.id"), nullable=False, index=True
    )
    session_token_jti: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    refresh_token_jti: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    account: Mapped["PortalAccount"] = relationship(back_populates="sessions")


class PortalAuthChallenge(TenantTable):
    """OTP / 2FA challenge issued to a portal account."""

    account_id: Mapped[int] = mapped_column(
        ForeignKey("portal_account.id"), nullable=False, index=True
    )
    challenge_type: Mapped[TwoFactorType] = mapped_column(Enum(TwoFactorType), nullable=False, index=True)
    purpose: Mapped[TwoFactorPurpose] = mapped_column(Enum(TwoFactorPurpose), nullable=False, index=True)
    destination: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    account: Mapped["PortalAccount"] = relationship(back_populates="challenges")


class PortalPreferences(TenantTable):
    """Communication and visibility preferences."""

    account_id: Mapped[int] = mapped_column(
        ForeignKey("portal_account.id"), unique=True, nullable=False, index=True
    )
    preferred_language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    preferred_timezone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    accepts_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    accepts_sms: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    accepts_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepts_push_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    accessibility_settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    account: Mapped["PortalAccount"] = relationship(back_populates="preferences")


class PortalAppointmentRequest(TenantTable):
    """Patient-initiated appointment request via the portal."""

    account_id: Mapped[int] = mapped_column(
        ForeignKey("portal_account.id"), nullable=False, index=True
    )
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("department.id"), nullable=True, index=True)
    service_delivery_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_delivery_point.id"), nullable=True, index=True
    )

    requested_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[PortalAppointmentRequestStatus] = mapped_column(
        Enum(PortalAppointmentRequestStatus),
        default=PortalAppointmentRequestStatus.REQUESTED,
        nullable=False,
        index=True,
    )
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    converted_appointment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("appointment.id"), nullable=True, index=True
    )
    reviewed_by_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )

    account: Mapped["PortalAccount"] = relationship(back_populates="appointment_requests")
    patient: Mapped["Patient"] = relationship()
    converted_appointment: Mapped[Optional["Appointment"]] = relationship()


class PortalMessage(TenantTable):
    """Secure message exchanged between patient and care team."""

    account_id: Mapped[int] = mapped_column(
        ForeignKey("portal_account.id"), nullable=False, index=True
    )
    counterpart_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True, index=True
    )
    direction: Mapped[PortalMessageDirection] = mapped_column(
        Enum(PortalMessageDirection), nullable=False, index=True
    )
    status: Mapped[PortalMessageStatus] = mapped_column(
        Enum(PortalMessageStatus),
        default=PortalMessageStatus.SENT,
        nullable=False,
        index=True,
    )
    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    parent_message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("portal_message.id"), nullable=True
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["PortalAccount"] = relationship(back_populates="messages")
    counterpart_staff: Mapped[Optional["StaffProfile"]] = relationship()


class PortalDocumentShare(TenantTable):
    """Documents uploaded by the patient or shared with the patient."""

    account_id: Mapped[int] = mapped_column(
        ForeignKey("portal_account.id"), nullable=False, index=True
    )
    direction: Mapped[PortalMessageDirection] = mapped_column(
        Enum(PortalMessageDirection), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["PortalAccount"] = relationship(back_populates="document_shares")


class PortalConsentLog(TenantTable):
    """Patient consent (data sharing, telehealth, etc.) captured via the portal."""

    account_id: Mapped[int] = mapped_column(
        ForeignKey("portal_account.id"), nullable=False, index=True
    )
    scope: Mapped[PortalConsentScope] = mapped_column(
        Enum(PortalConsentScope), nullable=False, index=True
    )
    granted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    granted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_text_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    consent_text_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    account: Mapped["PortalAccount"] = relationship(back_populates="consent_logs")


# ============================================================
# INTEROPERABILITY / FHIR
# ============================================================


class IntegrationEndpoint(TenantTable):
    """An external system endpoint we exchange data with."""

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    protocol: Mapped[IntegrationProtocol] = mapped_column(
        Enum(IntegrationProtocol), nullable=False, index=True
    )
    provider_type: Mapped[IntegrationProviderType] = mapped_column(
        Enum(IntegrationProviderType), nullable=False, index=True
    )

    direction: Mapped[IntegrationDirection] = mapped_column(
        Enum(IntegrationDirection), default=IntegrationDirection.OUTBOUND, nullable=False, index=True
    )
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    credentials: Mapped[list["IntegrationCredential"]] = relationship(
        back_populates="endpoint", cascade="all, delete-orphan"
    )


class IntegrationCredential(TenantTable):
    """Reference to credentials/secrets for an integration endpoint.

    Secrets are not stored in plaintext — `secret_reference` points to a key
    in the secrets manager (e.g. AWS Secrets Manager / Vault).
    """

    endpoint_id: Mapped[int] = mapped_column(
        ForeignKey("integration_endpoint.id"), nullable=False, index=True
    )
    credential_type: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    secret_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    endpoint: Mapped["IntegrationEndpoint"] = relationship(back_populates="credentials")


class FHIRResourceMapping(TenantTable):
    """
    Maps an internal record to an external FHIR resource id.

    For example, a Patient with id=42 might map to the FHIR Patient resource
    `urn:my-hie:Patient/12345` on a regional health information exchange.
    """

    fhir_resource_type: Mapped[FHIRResourceType] = mapped_column(
        Enum(FHIRResourceType), nullable=False, index=True
    )
    internal_table: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    internal_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    endpoint_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("integration_endpoint.id"), nullable=True, index=True
    )
    external_system_code: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    external_resource_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    external_version_id: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    endpoint: Mapped[Optional["IntegrationEndpoint"]] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "fhir_resource_type", "internal_table", "internal_id",
            "endpoint_id", "external_resource_id",
            name="uq_fhir_mapping_per_endpoint",
        ),
        Index(
            "ix_fhir_mapping_lookup",
            "fhir_resource_type", "external_system_code", "external_resource_id",
        ),
    )


class FHIRResourceVersion(TenantTable):
    """Stored FHIR resource versions for audit / replay."""

    mapping_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("fhir_resource_mapping.id"), nullable=True, index=True
    )
    fhir_resource_type: Mapped[FHIRResourceType] = mapped_column(
        Enum(FHIRResourceType), nullable=False, index=True
    )
    version_id: Mapped[str] = mapped_column(String(150), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    mapping: Mapped[Optional["FHIRResourceMapping"]] = relationship()


class OutboundIntegrationMessage(TenantTable):
    """Queue of messages to be sent to an external system."""

    endpoint_id: Mapped[int] = mapped_column(
        ForeignKey("integration_endpoint.id"), nullable=False, index=True
    )
    fhir_resource_type: Mapped[Optional[FHIRResourceType]] = mapped_column(
        Enum(FHIRResourceType), nullable=True, index=True
    )
    operation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    internal_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    status: Mapped[IntegrationMessageStatus] = mapped_column(
        Enum(IntegrationMessageStatus),
        default=IntegrationMessageStatus.QUEUED,
        nullable=False,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    endpoint: Mapped["IntegrationEndpoint"] = relationship()

    __table_args__ = (
        Index("ix_outbound_msg_status_next_retry", "status", "next_retry_at"),
    )


class InboundIntegrationMessage(TenantTable):
    """Queue of messages received from an external system."""

    endpoint_id: Mapped[int] = mapped_column(
        ForeignKey("integration_endpoint.id"), nullable=False, index=True
    )
    fhir_resource_type: Mapped[Optional[FHIRResourceType]] = mapped_column(
        Enum(FHIRResourceType), nullable=True, index=True
    )
    operation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_status: Mapped[IntegrationMessageStatus] = mapped_column(
        Enum(IntegrationMessageStatus),
        default=IntegrationMessageStatus.QUEUED,
        nullable=False,
        index=True,
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    endpoint: Mapped["IntegrationEndpoint"] = relationship()


class IntegrationAuditLog(TenantTable):
    """Per-attempt request/response audit for integrations."""

    endpoint_id: Mapped[int] = mapped_column(
        ForeignKey("integration_endpoint.id"), nullable=False, index=True
    )
    outbound_message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("outbound_integration_message.id"), nullable=True, index=True
    )
    inbound_message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("inbound_integration_message.id"), nullable=True, index=True
    )

    direction: Mapped[IntegrationDirection] = mapped_column(
        Enum(IntegrationDirection), nullable=False, index=True
    )
    request_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    request_headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    request_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    response_headers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    endpoint: Mapped["IntegrationEndpoint"] = relationship()


class TerminologyCodeMap(TenantTable):
    """Maps internal codes to standard terminologies (ICD/LOINC/SNOMED/etc.)."""

    domain: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    internal_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    internal_display: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_system: Mapped[TerminologySystem] = mapped_column(
        Enum(TerminologySystem), nullable=False, index=True
    )
    target_code: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    target_display: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mapping_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "domain", "internal_code", "target_system", "target_code",
            name="uq_terminology_mapping",
        ),
    )


# ============================================================
# DOWNTIME & OFFLINE OPERATIONS
# ============================================================


class DowntimeEvent(TenantTable):
    """Tracks planned or unplanned periods when the system is unavailable."""

    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    declared_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    resolved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[DowntimeEventType] = mapped_column(
        Enum(DowntimeEventType), nullable=False, index=True
    )
    status: Mapped[DowntimeStatus] = mapped_column(
        Enum(DowntimeStatus),
        default=DowntimeStatus.SCHEDULED,
        nullable=False,
        index=True,
    )
    severity: Mapped[Optional[IncidentSeverity]] = mapped_column(
        Enum(IncidentSeverity), nullable=True, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    affected_modules: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reconciliation_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    registration_logs: Mapped[list["DowntimeRegistrationLog"]] = relationship(
        back_populates="downtime_event", cascade="all, delete-orphan"
    )
    order_logs: Mapped[list["DowntimeOrderLog"]] = relationship(
        back_populates="downtime_event", cascade="all, delete-orphan"
    )


class SyncJournal(TenantTable):
    """
    Append-only change ledger for cloud↔edge replication.

    Every business write that needs to survive an internet outage is
    captured in this table at commit time. Sync runs read forward from
    the last acknowledged cursor and ship the batch to the other side.

    Conflict policy:

      * **Append-only events** — vitals, dispenses, payments, audit
        rows, lab results. Both sides keep all rows; duplicates are
        de-duplicated by ``client_uuid``.
      * **Mutable records** — patients, invoices, users. The newer
        ``occurred_at`` wins (last-writer-wins), with the loser archived
        in ``conflicted_payload`` for manual review.
    """

    __tablename__ = "sync_journal"

    # Monotonic cursor per-tenant so subscribers can resume without a
    # timestamp comparison.
    seq: Mapped[int] = mapped_column(BigInteger, autoincrement=True, unique=True, index=True)

    entity_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    client_uuid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    op: Mapped[SyncJournalOp] = mapped_column(
        Enum(SyncJournalOp),
        nullable=False,
        index=True,
    )
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    conflicted_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )

    # Origin labels: 'cloud' for cloud-authored rows, 'edge:<code>' for
    # edge-node-authored rows. We use this to skip echoes during sync.
    origin: Mapped[str] = mapped_column(String(120), default="cloud", nullable=False, index=True)
    origin_node_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[SyncJournalStatus] = mapped_column(
        Enum(SyncJournalStatus),
        default=SyncJournalStatus.PENDING,
        nullable=False,
        index=True,
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_sync_journal_status_seq", "status", "seq"),
        Index("ix_sync_journal_entity", "entity_type", "entity_id"),
    )


class SyncBatch(TenantTable):
    """
    Audit row for one cloud↔edge exchange.

    A batch records direction (PULL/PUSH), the cursor range, and counts.
    Useful for reconciling "we sent 1,200 rows and only 1,198 were
    applied — what happened?" investigations.
    """

    __tablename__ = "sync_batch"

    direction: Mapped[SyncDirection] = mapped_column(
        Enum(SyncDirection), nullable=False, index=True
    )
    edge_node_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    cursor_from: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    cursor_to: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    applied_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class OfflineDevice(TenantTable):
    """A device (kiosk / tablet / mobile app) that captures data offline."""

    code: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    device_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    os_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    app_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    public_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[OfflineDeviceStatus] = mapped_column(
        Enum(OfflineDeviceStatus),
        default=OfflineDeviceStatus.REGISTERED,
        nullable=False,
        index=True,
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class OfflineSyncBatch(TenantTable):
    """A batch of offline submissions ingested during a sync."""

    batch_no: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    device_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("offline_device.id"), nullable=True, index=True
    )
    initiated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submission_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class OfflineFormSubmission(TenantTable):
    """Generic submission captured offline awaiting reconciliation."""

    device_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("offline_device.id"), nullable=True, index=True
    )
    sync_batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("offline_sync_batch.id"), nullable=True, index=True
    )
    submitted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    client_uuid: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    form_code: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    target_table: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[OfflineSubmissionStatus] = mapped_column(
        Enum(OfflineSubmissionStatus),
        default=OfflineSubmissionStatus.PENDING_SYNC,
        nullable=False,
        index=True,
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciled_record_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DowntimeRegistrationLog(TenantTable):
    """Patient registration captured on paper during downtime."""

    downtime_event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("downtime_event.id"), nullable=True, index=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    captured_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    paper_form_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    patient_full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    status: Mapped[OfflineSubmissionStatus] = mapped_column(
        Enum(OfflineSubmissionStatus),
        default=OfflineSubmissionStatus.CAPTURED,
        nullable=False,
        index=True,
    )
    reconciled_patient_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("patient.id"), nullable=True, index=True
    )
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciliation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    downtime_event: Mapped[Optional["DowntimeEvent"]] = relationship(back_populates="registration_logs")


class DowntimeOrderLog(TenantTable):
    """Clinical orders / prescriptions / lab requests captured during downtime."""

    downtime_event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("downtime_event.id"), nullable=True, index=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    captured_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    paper_form_no: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    order_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_table: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    related_patient_identifier: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    status: Mapped[OfflineSubmissionStatus] = mapped_column(
        Enum(OfflineSubmissionStatus),
        default=OfflineSubmissionStatus.CAPTURED,
        nullable=False,
        index=True,
    )
    reconciled_record_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reconciliation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    downtime_event: Mapped[Optional["DowntimeEvent"]] = relationship(back_populates="order_logs")


# ============================================================
# DATA WAREHOUSE
# ============================================================


class WarehouseExportJob(TenantTable):
    """Scheduled job that exports operational data to the data warehouse."""

    code: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)
    target_dataset: Mapped[str] = mapped_column(String(255), nullable=False)

    export_type: Mapped[WarehouseExportType] = mapped_column(
        Enum(WarehouseExportType), nullable=False, index=True
    )
    refresh_strategy: Mapped[WarehouseRefreshStrategy] = mapped_column(
        Enum(WarehouseRefreshStrategy),
        default=WarehouseRefreshStrategy.INCREMENTAL,
        nullable=False,
        index=True,
    )
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transform_definition: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notification_emails: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    runs: Mapped[list["WarehouseExportRun"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class WarehouseExportRun(TenantTable):
    """An execution of a warehouse export job."""

    job_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse_export_job.id"), nullable=False, index=True
    )
    triggered_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)

    status: Mapped[WarehouseJobStatus] = mapped_column(
        Enum(WarehouseJobStatus),
        default=WarehouseJobStatus.SCHEDULED,
        nullable=False,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    rows_extracted: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rows_loaded: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bytes_written: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    high_watermark_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    run_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    job: Mapped["WarehouseExportJob"] = relationship(back_populates="runs")


class WarehouseTableSnapshot(TenantTable):
    """Point-in-time snapshot record produced by an export run."""

    run_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse_export_run.id"), nullable=False, index=True
    )
    source_table: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    target_table: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    column_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class WarehouseDimensionDefinition(TenantTable):
    """Star-schema dimension definition (BI metadata)."""

    dimension_code: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    surrogate_key_column: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    natural_key_column: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    scd_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    columns_definition: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class WarehouseFactDefinition(TenantTable):
    """Star-schema fact-table definition (BI metadata)."""

    fact_code: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    measures_definition: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dimension_keys: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class WarehouseMaterializedView(TenantTable):
    """Refreshable view living in the warehouse."""

    view_code: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    target_dataset: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sql_definition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_schedule_cron: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refresh_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DataExtractionAudit(TenantTable):
    """Audit row for any human-initiated extract/export action."""

    requested_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facility.id"), nullable=True, index=True)

    purpose: Mapped[DataExtractionPurpose] = mapped_column(
        Enum(DataExtractionPurpose), nullable=False, index=True
    )
    target_dataset: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_sensitive_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_basis: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ============================================================
# PATIENT PORTAL OTP LOGIN
# ============================================================


class PatientPortalOtp(TenantTable):
    """
    One-time-password challenges for the patient portal.

    Differs from :class:`TwoFactorChallenge` in two important ways:
    - it is keyed on ``patient_id`` (not ``user_id``), so a patient can
      authenticate before they have a system :class:`User` row;
    - it always carries a ``channel`` (EMAIL / SMS) and the resolved
      ``destination`` so the OTP can be re-sent to the same address on
      ``resend``.

    Storage rules:
    - the OTP plaintext is **never** stored — only ``code_hash`` (sha256).
    - ``expires_at`` enforces short-lived validity (typical: 10 minutes).
    - ``attempt_count`` / ``max_attempts`` short-circuits brute-force.
    - ``is_consumed`` is flipped to True on successful verification so the
      same OTP can't be reused.
    """

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient.id"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    resend_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    requested_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    patient: Mapped["Patient"] = relationship()

    __table_args__ = (
        Index(
            "ix_patient_portal_otp_patient_active",
            "patient_id",
            "is_consumed",
            "expires_at",
        ),
    )


class TenantSetting(TenantTable):
    """
    Tenant-specific configuration and UI settings.

    Holds branding (logo, colors), regional preferences (currency, timezone,
    date/time format), document numbering, configurable approval workflows,
    and notification preferences (which channels receive which event types).
    """

    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    theme_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Branding
    primary_color: Mapped[str] = mapped_column(String(20), default="#007bff")
    secondary_color: Mapped[str] = mapped_column(String(20), default="#6c757d")

    # Regional
    default_currency: Mapped[str] = mapped_column(String(10), default="NGN")
    timezone: Mapped[str] = mapped_column(String(50), default="Africa/Lagos")
    date_format: Mapped[str] = mapped_column(String(50), default="YYYY-MM-DD")
    time_format: Mapped[str] = mapped_column(String(50), default="HH:mm")

    # Document Numbering
    invoice_prefix: Mapped[str] = mapped_column(String(20), default="INV")
    invoice_next_number: Mapped[int] = mapped_column(Integer, default=1)
    invoice_number_format: Mapped[str] = mapped_column(
        String(80), default="{prefix}-{year}-{seq:06d}"
    )
    receipt_prefix: Mapped[str] = mapped_column(String(20), default="RCT")
    receipt_next_number: Mapped[int] = mapped_column(Integer, default=1)
    receipt_number_format: Mapped[str] = mapped_column(
        String(80), default="{prefix}-{year}-{seq:06d}"
    )
    appointment_prefix: Mapped[str] = mapped_column(String(20), default="APT")
    appointment_next_number: Mapped[int] = mapped_column(Integer, default=1)

    # ----- Approval workflows ------------------------------------------------
    # Free-form JSON describing approval requirements per business action.
    # Example:
    #   {
    #     "invoice.discount": {"required": true, "min_amount": 5000, "approver_role": "TENANT_ADMIN"},
    #     "lab.result.publish": {"required": true, "approver_role": "LAB_SCIENTIST"}
    #   }
    approval_workflows: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # ----- Notification preferences -----------------------------------------
    # Channels that should be enabled by default for the tenant.
    notify_in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_push_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Per-event channel routing. Keys are NotificationEvent codes (e.g.
    # "invoice.created", "appointment.reminder"); values are arrays of
    # channel codes ("in_app", "email", "sms", "whatsapp", "push").
    notification_channels: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Quiet-hours window (e.g. {"start": "22:00", "end": "07:00", "tz": "Africa/Lagos"}).
    quiet_hours: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Tenant-level "From" address for email and SMS sender ID.
    notification_from_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notification_from_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    notification_sms_sender_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

class TenantEmailConfig(TenantTable):
    """
    Per-tenant outbound-email configuration.

    Each tenant owns their own SMTP/relay so messages to their patients
    and users come from a sender they control (e.g. ``no-reply@stnicholas
    .com``). The platform falls back to its global SMTP only when no
    tenant configuration is active. Credentials (SMTP password, API key)
    are encrypted at rest using the platform encryption key — only the
    email-send adapter ever decrypts them in-memory at the moment of use.

    Two flavours of provider are supported:

    * ``SMTP`` — host / port / TLS / username / password, sent through
      ``smtplib``.
    * **API providers** (``SENDGRID``, ``SES``, ``MAILGUN``, ``POSTMARK``,
      ``RESEND``) — invoked via the provider's HTTP API using
      ``api_key`` and any provider-specific knobs (region, domain).

    Multiple rows may exist per tenant; ``is_default=True`` selects which
    one the dispatcher uses. ``is_active=False`` disables a row without
    deleting its history.
    """

    __tablename__ = "tenant_email_config"

    provider: Mapped[EmailProvider] = mapped_column(
        Enum(EmailProvider),
        default=EmailProvider.SMTP,
        nullable=False,
        index=True,
    )

    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ----- SMTP fields -------------------------------------------------
    smtp_host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # NONE | TLS | SSL
    smtp_security: Mapped[str] = mapped_column(String(10), default="TLS", nullable=False)
    smtp_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    smtp_password_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ----- API-provider fields ----------------------------------------
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    api_region: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    api_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ----- Sender identity / branding ---------------------------------
    from_email: Mapped[str] = mapped_column(String(255), nullable=False)
    from_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    reply_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    footer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    footer_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ----- Toggles -----------------------------------------------------
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    sandbox_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    # ----- Health bookkeeping -----------------------------------------
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_test_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_count: Mapped[int] = mapped_column(BigInteger, default=0)


class TenantPaymentMethodConfig(TenantTable):
    """
    Per-tenant payment-method configuration.

    Each tenant decides which payment channels they accept and how each
    online gateway is wired up. Provider credentials (secret keys, public
    keys, webhook secrets) are stored encrypted at rest using the
    platform-wide ``DATABASE_ENCRYPTION_KEY`` so even an operator with
    SQL access cannot read them in plaintext.

    The same ``channel`` may have multiple rows (for example a tenant with
    a primary Paystack gateway and a secondary Flutterwave gateway); the
    ``is_default`` flag controls which one gets selected when the patient
    chooses ``GATEWAY`` without naming a provider.

    Lifecycle: ``is_active`` toggles the configuration without deleting
    its history. Soft-delete via :meth:`BaseTable.soft_delete` removes a
    row entirely from the active set.
    """

    __tablename__ = "tenant_payment_method_config"

    # ----- Channel identification --------------------------------------
    channel: Mapped[PaymentChannel] = mapped_column(
        Enum(PaymentChannel),
        nullable=False,
        index=True,
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        Enum(PaymentProvider),
        default=PaymentProvider.MANUAL,
        nullable=False,
        index=True,
    )

    # Human-readable label (e.g. "Main Paystack Account").
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ----- Toggles ------------------------------------------------------
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    accepts_patient_payments: Mapped[bool] = mapped_column(Boolean, default=True)
    accepts_subscription_payments: Mapped[bool] = mapped_column(Boolean, default=False)

    # ----- Currency & limits -------------------------------------------
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    minimum_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    maximum_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    # ----- Fees ---------------------------------------------------------
    fee_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    fee_flat: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    fee_borne_by_patient: Mapped[bool] = mapped_column(Boolean, default=False)

    # ----- Encrypted credentials ---------------------------------------
    # Strings stored here are Fernet-encrypted by the service layer using
    # ``app.core.cryptography.encrypt_string``. Never write plaintext to
    # these columns directly — always go through TenantPaymentMethodService.
    secret_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    public_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    webhook_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    api_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    merchant_id_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ----- Provider-specific knobs --------------------------------------
    api_base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    callback_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    sandbox_mode: Mapped[bool] = mapped_column(Boolean, default=False)

    # ----- Health bookkeeping ------------------------------------------
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    last_test_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_tenant_payment_method_channel_provider",
            "channel",
            "provider",
        ),
    )


class DatabaseBackup(TenantTable):
    """
    Database backup record for the tenant.

    Each backup carries enough metadata to support retention policy
    enforcement, integrity verification, and selective restore (including
    point-in-time-recovery when WAL archiving is configured).
    """

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    s3_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    s3_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING")  # PENDING, COMPLETED, FAILED, EXPIRED
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Encryption / integrity
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    encryption_algo: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Backup taxonomy / PITR support
    backup_type: Mapped[str] = mapped_column(String(20), default="FULL")  # FULL, INCREMENTAL, WAL
    pg_dump_format: Mapped[str] = mapped_column(String(20), default="custom")  # custom, plain, tar
    backup_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    backup_finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pitr_lsn: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pitr_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Retention
    retention_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    triggered_by: Mapped[str] = mapped_column(String(20), default="MANUAL")  # MANUAL, SCHEDULED, ON_RESTORE

class TenantLog(TenantTable):
    """
    Metadata for daily application logs archived to S3.
    """
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    log_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED") # PENDING, COMPLETED, FAILED



# ============================================================
# MEDICATION ADHERENCE
# ============================================================


class MedicationProfile(TenantTable):
    """
    Aggregate view of every active and past medication for a patient.

    Each entry links back to the prescription it came from so the
    clinical history (diagnosis → consultation → prescription → dispense)
    remains queryable from the profile view.
    """

    __tablename__ = "medication_profile"

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    drug_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drug.id"), nullable=True, index=True)
    drug_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)

    # Source linkage — at least one of these is set so we can navigate
    # back to the originating clinical event.
    prescription_id: Mapped[Optional[int]] = mapped_column(ForeignKey("prescription.id"), nullable=True, index=True)
    prescription_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("prescription_item.id"), nullable=True, index=True
    )
    consultation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("consultation.id"), nullable=True, index=True
    )
    diagnosis_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("diagnosis.id"), nullable=True, index=True
    )
    prescribing_doctor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True, index=True
    )

    # Clinical instructions copied from the prescription.
    dosage: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    frequency_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    route: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ended_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    discontinued_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MedicationSchedule(TenantTable):
    """
    Time-based plan that spawns individual MedicationDose rows.

    A schedule belongs to one MedicationProfile and is what the reminder
    engine works against. ``frequency`` and ``custom_times`` together
    describe when doses occur — e.g. ``THREE_TIMES_DAILY`` with default
    08:00 / 14:00 / 20:00 OR ``CUSTOM`` with an explicit list of HH:MM.
    """

    __tablename__ = "medication_schedule"

    medication_profile_id: Mapped[int] = mapped_column(
        ForeignKey("medication_profile.id"), nullable=False, index=True
    )
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)

    frequency: Mapped[MedicationFrequency] = mapped_column(
        Enum(MedicationFrequency),
        default=MedicationFrequency.DAILY,
        nullable=False,
    )
    # Custom HH:MM times when frequency == CUSTOM.
    custom_times: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    interval_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    refill_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    review_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    status: Mapped[MedicationScheduleStatus] = mapped_column(
        Enum(MedicationScheduleStatus),
        default=MedicationScheduleStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    last_generated_through: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MedicationDose(TenantTable):
    """
    A single dose event scheduled to be (or that has been) taken.

    Append-only by convention: doses transition through statuses but the
    row itself isn't deleted. ``confirmed_by`` lets caregivers confirm on
    behalf of a patient.
    """

    __tablename__ = "medication_dose"

    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("medication_schedule.id"), nullable=False, index=True
    )
    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)

    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    window_minutes: Mapped[int] = mapped_column(Integer, default=30)

    status: Mapped[MedicationDoseStatus] = mapped_column(
        Enum(MedicationDoseStatus),
        default=MedicationDoseStatus.SCHEDULED,
        nullable=False,
        index=True,
    )

    taken_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    confirmation_source: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True
    )  # PATIENT_PORTAL, CAREGIVER, NURSE, AUTO
    miss_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_medication_dose_pat_due", "patient_id", "scheduled_for"),
    )


class MedicationReminderPreference(TenantTable):
    """
    Per-patient channel preferences for medication reminders.

    Falls back to the tenant-level NotificationDispatcher routing when
    nothing is configured here.
    """

    __tablename__ = "medication_reminder_preference"

    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patient.id"), unique=True, nullable=False, index=True
    )

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    channel_in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    channel_email: Mapped[bool] = mapped_column(Boolean, default=False)
    channel_sms: Mapped[bool] = mapped_column(Boolean, default=True)
    channel_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)
    channel_push: Mapped[bool] = mapped_column(Boolean, default=False)

    advance_minutes: Mapped[int] = mapped_column(Integer, default=15)
    quiet_hours_start: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # HH:MM
    quiet_hours_end: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)


class AdherenceSnapshot(TenantTable):
    """
    Periodic computed adherence rollup per (patient, schedule, period).

    Snapshots are produced by the daily adherence job so dashboards
    don't have to recompute from raw doses every page load.
    """

    __tablename__ = "adherence_snapshot"

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    schedule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medication_schedule.id"), nullable=True, index=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    doses_scheduled: Mapped[int] = mapped_column(Integer, default=0)
    doses_taken: Mapped[int] = mapped_column(Integer, default=0)
    doses_missed: Mapped[int] = mapped_column(Integer, default=0)
    doses_skipped: Mapped[int] = mapped_column(Integer, default=0)
    doses_delayed: Mapped[int] = mapped_column(Integer, default=0)

    adherence_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    level: Mapped[AdherenceLevel] = mapped_column(
        Enum(AdherenceLevel),
        default=AdherenceLevel.UNKNOWN,
        nullable=False,
        index=True,
    )


class AdherenceAlert(TenantTable):
    """
    Clinician-facing alert when a patient repeatedly misses doses,
    misses a refill, or fails to start a high-risk medication.
    """

    __tablename__ = "adherence_alert"

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    schedule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medication_schedule.id"), nullable=True, index=True
    )
    severity: Mapped[AdherenceAlertSeverity] = mapped_column(
        Enum(AdherenceAlertSeverity),
        default=AdherenceAlertSeverity.WARNING,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    acknowledged_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)


class RefillRecord(TenantTable):
    """
    Refill due-date tracker that notifies patients and pharmacy when
    medication needs to be refilled, and links to the dispense once
    it's actually filled.
    """

    __tablename__ = "refill_record"

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    schedule_id: Mapped[int] = mapped_column(
        ForeignKey("medication_schedule.id"), nullable=False, index=True
    )
    prescription_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("prescription_item.id"), nullable=True, index=True
    )

    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    last_reminded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[RefillStatus] = mapped_column(
        Enum(RefillStatus),
        default=RefillStatus.DUE_SOON,
        nullable=False,
        index=True,
    )
    fulfilled_dispense_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("dispense.id"), nullable=True, index=True
    )
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class FollowUpTask(TenantTable):
    """
    Adherence-driven follow-up assigned to a clinician, nurse,
    pharmacist, or case manager.
    """

    __tablename__ = "follow_up_task"

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    schedule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medication_schedule.id"), nullable=True, index=True
    )
    alert_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("adherence_alert.id"), nullable=True, index=True
    )

    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)
    assigned_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[FollowUpTaskStatus] = mapped_column(
        Enum(FollowUpTaskStatus),
        default=FollowUpTaskStatus.OPEN,
        nullable=False,
        index=True,
    )
    outcome_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


# ============================================================
# DOCTOR CALENDAR & APPOINTMENT EXTENSIONS
# ============================================================


class DoctorAvailabilityTemplate(TenantTable):
    """
    Repeating weekly availability for a single doctor.

    Each row represents one weekday slot definition (e.g. "Mondays
    08:00–13:00, 30-minute slots, max 1 patient per slot"). The
    DoctorCalendarService materialises concrete AppointmentSlot rows
    from these templates on a rolling basis.
    """

    __tablename__ = "doctor_availability_template"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True
    )
    service_delivery_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_delivery_point.id"), nullable=True
    )

    # 0 = Monday … 6 = Sunday
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    max_patients_per_slot: Mapped[int] = mapped_column(Integer, default=1)

    appointment_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DoctorTimeOff(TenantTable):
    """
    Block of time when a doctor is unavailable (leave, holiday,
    conference). Generated AppointmentSlot rows in this window are
    flipped to BLOCKED so they cannot be booked.
    """

    __tablename__ = "doctor_time_off"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    availability_type: Mapped[DoctorAvailabilityType] = mapped_column(
        Enum(DoctorAvailabilityType),
        default=DoctorAvailabilityType.BLOCKED,
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)


class AppointmentSlot(TenantTable):
    """
    Materialised time slot a patient can book.

    Slots are generated forward from DoctorAvailabilityTemplate by the
    DoctorCalendarService. They reference the appointment that booked
    them (when one exists) so reschedules and cancellations stay
    consistent.
    """

    __tablename__ = "appointment_slot"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True
    )
    service_delivery_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_delivery_point.id"), nullable=True
    )
    appointment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("appointment.id"), nullable=True, index=True
    )

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    booked_count: Mapped[int] = mapped_column(Integer, default=0)

    appointment_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status: Mapped[AppointmentSlotStatus] = mapped_column(
        Enum(AppointmentSlotStatus),
        default=AppointmentSlotStatus.OPEN,
        nullable=False,
        index=True,
    )
    block_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_appointment_slot_doctor_start", "staff_profile_id", "starts_at"),
    )


class AppointmentReminderJob(TenantTable):
    """
    A scheduled reminder for one appointment.

    Materialised by the AppointmentService at booking time so the
    scheduler can dispatch reminders without recomputing offsets.
    """

    __tablename__ = "appointment_reminder_job"

    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointment.id"), nullable=False, index=True
    )
    rule: Mapped[AppointmentReminderRule] = mapped_column(
        Enum(AppointmentReminderRule),
        default=AppointmentReminderRule.H24_BEFORE,
        nullable=False,
    )
    fire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    fired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    channels: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AppointmentCancellationLog(TenantTable):
    """Immutable record of every cancellation/reschedule action."""

    __tablename__ = "appointment_cancellation_log"

    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointment.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # CANCELLED, RESCHEDULED, NO_SHOW
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    previous_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    new_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AppointmentRecurrenceRule(TenantTable):
    """
    Defines a recurring appointment series.

    Concrete child Appointment rows reference the parent's
    ``parent_appointment_id`` (a JSON metadata field on Appointment is
    used for that linkage to avoid an Appointment-table migration).
    """

    __tablename__ = "appointment_recurrence_rule"

    parent_appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointment.id"), nullable=False, index=True
    )
    recurrence: Mapped[AppointmentRecurrence] = mapped_column(
        Enum(AppointmentRecurrence),
        default=AppointmentRecurrence.WEEKLY,
        nullable=False,
    )
    interval_count: Mapped[int] = mapped_column(Integer, default=1)
    occurrences: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    until_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    weekdays: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


# ============================================================
# TAX MANAGEMENT
# ============================================================


class TaxType(TenantTable):
    """
    A tax kind enabled for the tenant (VAT, WHT, Service Tax, etc).

    Each TaxType groups one or more TaxRate entries (with effective
    dates) and TaxRule entries (deciding when the type applies).
    """

    __tablename__ = "tax_type"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[TaxKind] = mapped_column(
        Enum(TaxKind),
        default=TaxKind.OTHER,
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    is_withholding: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class TaxRate(TenantTable):
    """
    Effective-dated tax rate for a TaxType.

    The active rate at a given date is the row whose
    ``[effective_from, effective_to]`` window covers that date. This
    lets us preserve historical invoice taxes when a rate changes
    later.
    """

    __tablename__ = "tax_rate"

    tax_type_id: Mapped[int] = mapped_column(ForeignKey("tax_type.id"), nullable=False, index=True)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TaxRule(TenantTable):
    """
    Predicate that selects which line-items a TaxType applies to.

    Rules are evaluated by the TaxService at invoice issuance time. A
    line that matches *any* applicable rule receives the corresponding
    rate. ``priority`` lets exemption rules trump default ones.
    """

    __tablename__ = "tax_rule"

    tax_type_id: Mapped[int] = mapped_column(ForeignKey("tax_type.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    scope: Mapped[TaxScope] = mapped_column(
        Enum(TaxScope),
        default=TaxScope.TENANT,
        nullable=False,
    )
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True
    )
    applicability: Mapped[TaxApplicability] = mapped_column(
        Enum(TaxApplicability),
        default=TaxApplicability.ALL,
        nullable=False,
    )
    match_values: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    pricing_mode: Mapped[TaxPricingMode] = mapped_column(
        Enum(TaxPricingMode),
        default=TaxPricingMode.EXCLUSIVE,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class TaxExemption(TenantTable):
    """
    Mark specific entities (services, products, patients, payers,
    organisations) as tax-exempt for a given TaxType.
    """

    __tablename__ = "tax_exemption"

    tax_type_id: Mapped[int] = mapped_column(ForeignKey("tax_type.id"), nullable=False, index=True)
    scope: Mapped[TaxExemptionScope] = mapped_column(
        Enum(TaxExemptionScope),
        nullable=False,
        index=True,
    )
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_document_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    starts_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ends_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class InvoiceTaxLine(TenantTable):
    """
    Immutable per-invoice tax snapshot.

    Captures the tax type, rate, and amount applied to one invoice line
    at issuance time. Because rate changes after issuance must NOT alter
    historical totals, the rate is stored here directly rather than
    looked up via foreign key at read time.
    """

    __tablename__ = "invoice_tax_line"

    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"), nullable=False, index=True)
    invoice_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoice_item.id"), nullable=True, index=True
    )

    tax_type_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tax_type.id"), nullable=True, index=True
    )
    tax_type_code_snapshot: Mapped[str] = mapped_column(String(40), nullable=False)
    tax_type_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    rate_percent_snapshot: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)

    taxable_base: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    pricing_mode: Mapped[TaxPricingMode] = mapped_column(
        Enum(TaxPricingMode),
        default=TaxPricingMode.EXCLUSIVE,
        nullable=False,
    )
    is_exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    exemption_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class WithholdingTaxRecord(TenantTable):
    """
    Withholding tax deducted on a payment to a vendor / contractor /
    other applicable beneficiary.
    """

    __tablename__ = "withholding_tax_record"

    tax_type_id: Mapped[int] = mapped_column(ForeignKey("tax_type.id"), nullable=False, index=True)
    payee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payee_tax_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    payee_kind: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    related_invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoice.id"), nullable=True, index=True
    )
    related_payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment.id"), nullable=True, index=True
    )

    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    rate_percent_snapshot: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    wht_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    status: Mapped[WithholdingTaxStatus] = mapped_column(
        Enum(WithholdingTaxStatus),
        default=WithholdingTaxStatus.PENDING,
        nullable=False,
        index=True,
    )
    deducted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    remitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    certificate_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    certificate_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TaxAuditLog(TenantTable):
    """
    Append-only history of tax-configuration changes.

    Captures who changed what and when so finance and auditors can
    reconstruct the rules in force at any past point in time.
    """

    __tablename__ = "tax_audit_log"

    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)
    entity: Mapped[str] = mapped_column(String(60), nullable=False, index=True)  # tax_type, tax_rate, tax_rule, tax_exemption
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # CREATE, UPDATE, DEACTIVATE
    before_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


# ============================================================
# HR — STAFF DOCUMENTS, CONTRACTS, LICENSES, ONBOARDING
# ============================================================


class StaffDocument(TenantTable):
    """Uploaded HR document attached to a staff record."""

    __tablename__ = "staff_document"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    category: Mapped[StaffDocumentCategory] = mapped_column(
        Enum(StaffDocumentCategory),
        default=StaffDocumentCategory.OTHER,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    s3_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    issued_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expires_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)


class StaffEmploymentContract(TenantTable):
    """Employment-contract record. A staff profile may have many over time."""

    __tablename__ = "staff_employment_contract"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType), default=EmploymentType.PERMANENT, nullable=False, index=True
    )
    job_title: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"), nullable=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True
    )
    salary_grade: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    salary_step: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    base_salary_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    probation_period_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confirmation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_renewal: Mapped[bool] = mapped_column(Boolean, default=False)
    renewed_from_contract_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_employment_contract.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_document.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StaffLicense(TenantTable):
    """Professional license / credential held by a staff member."""

    __tablename__ = "staff_license"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    license_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    license_number: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    issuing_body: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus), default=LicenseStatus.ACTIVE, nullable=False, index=True
    )
    document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_document.id"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StaffEmergencyContact(TenantTable):
    """Emergency contact information for a staff member."""

    __tablename__ = "staff_emergency_contact"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class StaffStatusHistory(TenantTable):
    """Audit row for every employment-status transition."""

    __tablename__ = "staff_status_history"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    from_status: Mapped[Optional[EmploymentStatus]] = mapped_column(
        Enum(EmploymentStatus), nullable=True
    )
    to_status: Mapped[EmploymentStatus] = mapped_column(
        Enum(EmploymentStatus), nullable=False, index=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StaffOnboardingChecklistItem(TenantTable):
    """One step on a staff member's onboarding checklist."""

    __tablename__ = "staff_onboarding_checklist_item"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)


class StaffOffboardingChecklistItem(TenantTable):
    """One step on a staff member's offboarding checklist."""

    __tablename__ = "staff_offboarding_checklist_item"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)


# ============================================================
# HR — DUTY ROSTER / SHIFTS / ATTENDANCE / TIMESHEETS
# ============================================================


class ShiftTemplate(TenantTable):
    """Reusable shift definition (e.g. MORNING 08:00-16:00)."""

    __tablename__ = "shift_template"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    shift_type: Mapped[StaffShiftType] = mapped_column(
        Enum(StaffShiftType), default=StaffShiftType.MORNING, nullable=False, index=True
    )
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    grace_minutes: Mapped[int] = mapped_column(Integer, default=10)
    crosses_midnight: Mapped[bool] = mapped_column(Boolean, default=False)
    overtime_after_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"), nullable=True, index=True
    )
    is_clinical: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DutyRoster(TenantTable):
    """A roster window for a department/facility/role over a date range."""

    __tablename__ = "duty_roster"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"), nullable=True, index=True
    )
    service_delivery_point_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("service_delivery_point.id"), nullable=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DutyAssignment(TenantTable):
    """One staff-to-shift mapping inside a roster."""

    __tablename__ = "duty_assignment"

    roster_id: Mapped[int] = mapped_column(
        ForeignKey("duty_roster.id"), nullable=False, index=True
    )
    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    shift_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("shift_template.id"), nullable=True
    )
    shift_type: Mapped[StaffShiftType] = mapped_column(
        Enum(StaffShiftType), default=StaffShiftType.MORNING, nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_on_call: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    swapped_with_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    swap_approved_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_duty_assignment_staff_start", "staff_profile_id", "starts_at"),
    )


class AttendanceRecord(TenantTable):
    """Single clock-in/out event for a staff member."""

    __tablename__ = "attendance_record"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    duty_assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("duty_assignment.id"), nullable=True, index=True
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    clock_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    clock_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    method: Mapped[AttendanceMethod] = mapped_column(
        Enum(AttendanceMethod), default=AttendanceMethod.MANUAL, nullable=False
    )
    device_identifier: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    is_absent: Mapped[bool] = mapped_column(Boolean, default=False)
    minutes_late: Mapped[int] = mapped_column(Integer, default=0)
    minutes_overtime: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Timesheet(TenantTable):
    """Per-staff timesheet for a payroll period."""

    __tablename__ = "timesheet"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_regular_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    total_overtime_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    total_night_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    total_weekend_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    total_holiday_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    absence_days: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[TimesheetStatus] = mapped_column(
        Enum(TimesheetStatus), default=TimesheetStatus.DRAFT, nullable=False, index=True
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entries: Mapped[list["TimesheetEntry"]] = relationship(back_populates="timesheet", cascade="all, delete-orphan")



class TimesheetEntry(TenantTable):
    """Per-day breakdown inside a Timesheet."""

    __tablename__ = "timesheet_entry"

    timesheet_id: Mapped[int] = mapped_column(
        ForeignKey("timesheet.id"), nullable=False, index=True
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    regular_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    night_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    weekend_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    holiday_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    is_absent: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timesheet: Mapped["Timesheet"] = relationship(back_populates="entries")



# ============================================================
# HR — LEAVE & PUBLIC HOLIDAYS
# ============================================================


class LeaveType(TenantTable):
    """Tenant-configurable leave type with default entitlement."""

    __tablename__ = "leave_type"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[LeaveTypeKind] = mapped_column(
        Enum(LeaveTypeKind), default=LeaveTypeKind.OTHER, nullable=False, index=True
    )
    default_annual_days: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class LeaveBalance(TenantTable):
    """Per-staff balance per leave-type per year."""

    __tablename__ = "leave_balance"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    leave_type_id: Mapped[int] = mapped_column(
        ForeignKey("leave_type.id"), nullable=False, index=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entitled_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    taken_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    pending_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    carry_over_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)

    __table_args__ = (
        Index("uq_leave_balance_staff_type_year", "staff_profile_id", "leave_type_id", "year", unique=True),
    )


class LeaveRequest(TenantTable):
    """Leave application / approval workflow row."""

    __tablename__ = "leave_request"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    leave_type_id: Mapped[int] = mapped_column(
        ForeignKey("leave_type.id"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    days_requested: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[LeaveStatus] = mapped_column(
        Enum(LeaveStatus), default=LeaveStatus.DRAFT, nullable=False, index=True
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Link to approval engine
    approval_request_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    handover_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )


class ReimbursementRequest(TenantTable):
    """Reimbursement request workflow row."""

    __tablename__ = "reimbursement_request"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[ReimbursementStatus] = mapped_column(
        Enum(ReimbursementStatus), default=ReimbursementStatus.DRAFT, nullable=False, index=True
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Link to approval engine
    approval_request_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PublicHoliday(TenantTable):
    """Configured public holiday."""

    __tablename__ = "public_holiday"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scope: Mapped[HolidayScope] = mapped_column(
        Enum(HolidayScope), default=HolidayScope.NATIONAL, nullable=False, index=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True
    )
    affects_clinical: Mapped[bool] = mapped_column(Boolean, default=True)
    affects_admin: Mapped[bool] = mapped_column(Boolean, default=True)
    pay_multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("1.00"))
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ============================================================
# HR — PAYROLL / SALARY / OVERTIME / LOANS
# ============================================================


class SalaryGrade(TenantTable):
    """Salary band / pay scale."""

    __tablename__ = "salary_grade"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SalaryStep(TenantTable):
    """One step inside a SalaryGrade."""

    __tablename__ = "salary_step"

    grade_id: Mapped[int] = mapped_column(ForeignKey("salary_grade.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AllowanceType(TenantTable):
    """Allowance template (housing, transport, hazard, call duty, …)."""

    __tablename__ = "allowance_type"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=True)
    default_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    default_percent_of_base: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class DeductionType(TenantTable):
    """Deduction template (PAYE, pension, NHF, union dues, ...)."""

    __tablename__ = "deduction_type"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_statutory: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    default_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    default_percent_of_base: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class StaffSalary(TenantTable):
    """Staff-level salary configuration (allowances/deductions in JSON)."""

    __tablename__ = "staff_salary"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    grade_id: Mapped[Optional[int]] = mapped_column(ForeignKey("salary_grade.id"), nullable=True)
    step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("salary_step.id"), nullable=True)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    allowances: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # [{type_code, amount}]
    deductions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class PayrollRun(TenantTable):
    """Payroll batch over a period."""

    __tablename__ = "payroll_run"

    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"), nullable=True, index=True
    )
    status: Mapped[PayrollRunStatus] = mapped_column(
        Enum(PayrollRunStatus), default=PayrollRunStatus.DRAFT, nullable=False, index=True
    )
    total_gross: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    total_net: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    calculated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PayrollLine(TenantTable):
    """One staff member's payslip line in a PayrollRun."""

    __tablename__ = "payroll_line"

    payroll_run_id: Mapped[int] = mapped_column(
        ForeignKey("payroll_run.id"), nullable=False, index=True
    )
    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    timesheet_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("timesheet.id"), nullable=True
    )
    base_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_allowances: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    overtime_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    bonus_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gross_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    paye_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    pension_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    nhf_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    health_insurance_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    loan_repayment_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    other_deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    net_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    breakdown_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[PayrollLineStatus] = mapped_column(
        Enum(PayrollLineStatus), default=PayrollLineStatus.PENDING, nullable=False, index=True
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class OvertimeRecord(TenantTable):
    """Overtime claim / record."""

    __tablename__ = "overtime_record"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    duty_assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("duty_assignment.id"), nullable=True
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("1.00"))
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[OvertimeStatus] = mapped_column(
        Enum(OvertimeStatus), default=OvertimeStatus.PENDING, nullable=False, index=True
    )
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_in_payroll_line_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payroll_line.id"), nullable=True
    )


class StaffLoan(TenantTable):
    """Staff loan / advance."""

    __tablename__ = "staff_loan"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    interest_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    repayment_count: Mapped[int] = mapped_column(Integer, default=1)
    monthly_repayment_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    outstanding_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    requested_on: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    approved_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    starts_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expected_end_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[StaffLoanStatus] = mapped_column(
        Enum(StaffLoanStatus), default=StaffLoanStatus.REQUESTED, nullable=False, index=True
    )
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StaffLoanRepayment(TenantTable):
    """Repayment ledger entry against a StaffLoan."""

    __tablename__ = "staff_loan_repayment"

    loan_id: Mapped[int] = mapped_column(ForeignKey("staff_loan.id"), nullable=False, index=True)
    payroll_line_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payroll_line.id"), nullable=True
    )
    repayment_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SalaryAdvance(TenantTable):
    """Staff request for an early payout of their earned salary."""

    __tablename__ = "salary_advance"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repayment_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[SalaryAdvanceStatus] = mapped_column(
        Enum(SalaryAdvanceStatus), default=SalaryAdvanceStatus.DRAFT, nullable=False, index=True
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    staff_profile: Mapped["StaffProfile"] = relationship()
    
    # Link to approval engine (optional but helpful back-reference)
    approval_request_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)



class StatutoryDeductionConfig(TenantTable):
    """Tenant-specific statutory deduction config (PAYE bands, pension %, etc.)."""

    __tablename__ = "statutory_deduction_config"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rate_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    bands_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    employer_rate_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 3), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ============================================================
# HR — APPRAISAL / TRAINING / TASKS / INCIDENTS / REQUESTS
# ============================================================


class AppraisalCycle(TenantTable):
    """A performance-appraisal cycle (e.g. Q1 2026)."""

    __tablename__ = "appraisal_cycle"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    self_assessment_due_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    supervisor_review_due_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    moderation_due_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[AppraisalStatus] = mapped_column(
        Enum(AppraisalStatus), default=AppraisalStatus.DRAFT, nullable=False, index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AppraisalKPI(TenantTable):
    """KPI / competency template used by appraisals in a cycle."""

    __tablename__ = "appraisal_kpi"

    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("appraisal_cycle.id"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weight_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    max_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("5.00"))
    is_competency: Mapped[bool] = mapped_column(Boolean, default=False)


class StaffAppraisal(TenantTable):
    """Per-staff appraisal record for a cycle."""

    __tablename__ = "staff_appraisal"

    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("appraisal_cycle.id"), nullable=False, index=True
    )
    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    supervisor_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True
    )
    self_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    supervisor_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    moderated_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    final_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    self_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supervisor_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    moderation_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scoring_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[AppraisalStatus] = mapped_column(
        Enum(AppraisalStatus), default=AppraisalStatus.DRAFT, nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class TrainingSession(TenantTable):
    """A scheduled training event (mandatory or optional)."""

    __tablename__ = "training_session"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    venue: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)
    is_clinical: Mapped[bool] = mapped_column(Boolean, default=False)
    cme_credits: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[TrainingStatus] = mapped_column(
        Enum(TrainingStatus), default=TrainingStatus.PLANNED, nullable=False, index=True
    )


class TrainingRecord(TenantTable):
    """Per-staff training-attendance / certification record."""

    __tablename__ = "training_record"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_session.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    completed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    expires_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    certificate_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    issuing_body: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_document.id"), nullable=True
    )
    status: Mapped[TrainingStatus] = mapped_column(
        Enum(TrainingStatus), default=TrainingStatus.COMPLETED, nullable=False, index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StaffTask(TenantTable):
    """Task assigned to a staff member."""

    __tablename__ = "staff_task"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to_staff_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True, index=True
    )
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    related_patient_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("patient.id"), nullable=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"), nullable=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True
    )
    priority: Mapped[StaffTaskPriority] = mapped_column(
        Enum(StaffTaskPriority), default=StaffTaskPriority.MEDIUM, nullable=False
    )
    status: Mapped[StaffTaskStatus] = mapped_column(
        Enum(StaffTaskStatus), default=StaffTaskStatus.TODO, nullable=False, index=True
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StaffAnnouncement(TenantTable):
    """Internal-comms announcement to a slice of staff."""

    __tablename__ = "staff_announcement"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)  # ALL, BRANCH, DEPT, ROLE, CUSTOM
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"), nullable=True
    )
    role_codes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    channels: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)


class StaffIncident(TenantTable):
    """Disciplinary or workplace incident record."""

    __tablename__ = "staff_incident"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    severity: Mapped[StaffIncidentSeverity] = mapped_column(
        Enum(StaffIncidentSeverity), default=StaffIncidentSeverity.LOW, nullable=False, index=True
    )
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reported_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    confidential_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DisciplinaryActionRecord(TenantTable):
    """Action taken on a StaffIncident."""

    __tablename__ = "disciplinary_action_record"

    incident_id: Mapped[int] = mapped_column(
        ForeignKey("staff_incident.id"), nullable=False, index=True
    )
    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    kind: Mapped[DisciplinaryActionKind] = mapped_column(
        Enum(DisciplinaryActionKind), default=DisciplinaryActionKind.WRITTEN_WARNING, nullable=False, index=True
    )
    issued_on: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    issued_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StaffRequest(TenantTable):
    """Generic staff-initiated request (leave/overtime/swap/advance/...)."""

    __tablename__ = "staff_request"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    request_type: Mapped[StaffRequestType] = mapped_column(
        Enum(StaffRequestType), default=StaffRequestType.OTHER, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[StaffRequestStatus] = mapped_column(
        Enum(StaffRequestStatus), default=StaffRequestStatus.DRAFT, nullable=False, index=True
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True)
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class StaffAuditLog(TenantTable):
    """Generic audit row for sensitive changes to HR records."""

    __tablename__ = "staff_audit_log"

    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("user.id"), nullable=True, index=True)
    entity: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    before_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)


# ============================================================
# APPROVAL ENGINE
# ============================================================
#
# Tenant-managed approval workflows for internal staff requests.
# Each tenant defines its own ApprovalFlow rows (one per subject_type
# per use case, e.g. "STANDARD_LEAVE", "MANAGER_REIMBURSEMENT") and
# assembles them from ordered ApprovalFlowStep + ApprovalFlowStepApprover
# rows. ApprovalRequest is the runtime instance; ApprovalRequestStep is
# the per-request snapshot of each definition step; ApprovalDecision is
# the audit row of every approve/reject/delegate action.


class ApprovalFlow(TenantTable):
    """
    Tenant-defined approval flow definition.

    A flow is keyed by ``subject_type`` (e.g. LEAVE_REQUEST, REIMBURSEMENT)
    plus a tenant-unique ``code``. Multiple flows may exist for the same
    subject type (e.g. SHORT_LEAVE vs ANNUAL_LEAVE) — set ``is_default``
    on the one to use when no specific flow is requested.
    """

    __tablename__ = "approval_flow"

    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subject_type: Mapped[ApprovalSubjectType] = mapped_column(
        Enum(ApprovalSubjectType),
        default=ApprovalSubjectType.GENERIC,
        nullable=False,
        index=True,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Operational guards
    sla_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    auto_cancel_after_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notify_on_submit: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_decision: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("subject_type", "code", name="uq_approval_flow_subject_code"),
        Index("ix_approval_flow_subject_default", "subject_type", "is_default"),
    )

    steps: Mapped[list["ApprovalFlowStep"]] = relationship(
        back_populates="flow", cascade="all, delete-orphan", order_by="ApprovalFlowStep.step_order"
    )
    requests: Mapped[list["ApprovalRequest"]] = relationship(back_populates="flow")


class ApprovalFlowStep(TenantTable):
    """
    One ordered step inside an ``ApprovalFlow``.

    The step's ``decision_rule`` controls when the step passes. ``ANY_OF``
    advances on the first approve; ``ALL_OF`` requires every required
    approver; ``N_OF_M`` uses ``required_approvals``. Rejection at any
    step rejects the whole request (handled by the service).
    """

    __tablename__ = "approval_flow_step"

    flow_id: Mapped[int] = mapped_column(
        ForeignKey("approval_flow.id"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_rule: Mapped[ApprovalStepDecisionRule] = mapped_column(
        Enum(ApprovalStepDecisionRule),
        default=ApprovalStepDecisionRule.ANY_OF,
        nullable=False,
    )
    required_approvals: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    allow_self_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sla_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Optional condition expression evaluated against the request payload
    # at submit time. If the condition is False the step is auto-SKIPPED
    # for that request. Format: {"field": "amount", "op": "gt",
    # "value": 1000} or composite {"all": [...]} / {"any": [...]} /
    # {"not": {...}}. See app.utils.approval_utils.evaluate_condition.
    condition: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Steps sharing the same parallel_group activate simultaneously; the
    # group is treated as a single advancement boundary (the engine only
    # advances past the group when every member is APPROVED or SKIPPED).
    # NULL means "sequential, no group".
    parallel_group: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("flow_id", "step_order", name="uq_approval_step_order"),
    )

    flow: Mapped["ApprovalFlow"] = relationship(back_populates="steps")
    approvers: Mapped[list["ApprovalFlowStepApprover"]] = relationship(
        back_populates="step", cascade="all, delete-orphan"
    )


class ApprovalFlowStepApprover(TenantTable):
    """
    A target approver attached to an ``ApprovalFlowStep``.

    A step can have many of these. Each row identifies *who* can act:
    a specific user, anyone with a role, anyone in a department, or a
    dynamic resolver token (e.g. requester's manager).
    """

    __tablename__ = "approval_flow_step_approver"

    step_id: Mapped[int] = mapped_column(
        ForeignKey("approval_flow_step.id"), nullable=False, index=True
    )
    approver_kind: Mapped[ApprovalApproverKind] = mapped_column(
        Enum(ApprovalApproverKind), nullable=False, index=True
    )

    # Set exactly one of the following based on approver_kind.
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True, index=True
    )
    role_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("role.id"), nullable=True, index=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"), nullable=True, index=True
    )
    dynamic_token: Mapped[Optional[ApprovalDynamicApprover]] = mapped_column(
        Enum(ApprovalDynamicApprover), nullable=True
    )

    # For ALL_OF / N_OF_M semantics: rows where is_required=True must approve.
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    step: Mapped["ApprovalFlowStep"] = relationship(back_populates="approvers")


class ApprovalRequest(TenantTable):
    """
    Runtime instance of an approval flow tied to a subject record.

    ``subject_type`` + ``subject_id`` link back to the underlying domain
    row (e.g. a LeaveRequest). ``payload`` stores a JSON snapshot of the
    request data so historical audits don't break if the source row is
    edited later.
    """

    __tablename__ = "approval_request"

    flow_id: Mapped[int] = mapped_column(
        ForeignKey("approval_flow.id"), nullable=False, index=True
    )
    subject_type: Mapped[ApprovalSubjectType] = mapped_column(
        Enum(ApprovalSubjectType), nullable=False, index=True
    )
    subject_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    requester_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, index=True
    )
    requester_staff_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=True, index=True
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("department.id"), nullable=True, index=True
    )
    facility_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("facility.id"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    status: Mapped[ApprovalRequestStatus] = mapped_column(
        Enum(ApprovalRequestStatus),
        default=ApprovalRequestStatus.DRAFT,
        nullable=False,
        index=True,
    )

    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    current_step_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("approval_request_step.id", use_alter=True),
        nullable=True,
    )
    decision_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_approval_request_subject",
            "subject_type",
            "subject_id",
        ),
        Index(
            "ix_approval_request_status_requester",
            "status",
            "requester_user_id",
        ),
    )

    flow: Mapped["ApprovalFlow"] = relationship(back_populates="requests")
    steps: Mapped[list["ApprovalRequestStep"]] = relationship(
        back_populates="request", 
        cascade="all, delete-orphan", 
        order_by="ApprovalRequestStep.step_order",
        foreign_keys="[ApprovalRequestStep.request_id]"
    )
    comments: Mapped[list["ApprovalComment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    
    current_step: Mapped[Optional["ApprovalRequestStep"]] = relationship(
        foreign_keys=[current_step_id], post_update=True
    )


class ApprovalRequestStep(TenantTable):
    """
    Per-request snapshot of a flow step.

    Created when an ``ApprovalRequest`` is submitted so the step
    definition can change later without rewriting history. Tracks
    counters used by the engine to evaluate the decision rule.
    """

    __tablename__ = "approval_request_step"

    request_id: Mapped[int] = mapped_column(
        ForeignKey("approval_request.id"), nullable=False, index=True
    )
    flow_step_id: Mapped[int] = mapped_column(
        ForeignKey("approval_flow_step.id"), nullable=False, index=True
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    decision_rule: Mapped[ApprovalStepDecisionRule] = mapped_column(
        Enum(ApprovalStepDecisionRule),
        default=ApprovalStepDecisionRule.ANY_OF,
        nullable=False,
    )
    required_approvals: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Snapshotted from ApprovalFlowStep at submit time so editing the
    # flow definition later doesn't change live request behaviour.
    parallel_group: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    condition_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Snapshot of the eligible approver user ids resolved at step start.
    eligible_user_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Snapshot of approver entries (kind/user/role/department/token, is_required).
    approver_specs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    status: Mapped[ApprovalRequestStepStatus] = mapped_column(
        Enum(ApprovalRequestStepStatus),
        default=ApprovalRequestStepStatus.PENDING,
        nullable=False,
        index=True,
    )

    approvals_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejections_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "request_id", "step_order", name="uq_approval_request_step_order"
        ),
    )

    request: Mapped["ApprovalRequest"] = relationship(
        back_populates="steps",
        foreign_keys=[request_id]
    )
    flow_step: Mapped["ApprovalFlowStep"] = relationship()
    decisions: Mapped[list["ApprovalDecision"]] = relationship(
        back_populates="request_step", cascade="all, delete-orphan"
    )


class ApprovalDecision(TenantTable):
    """One approve/reject/delegate action recorded against a request step."""

    __tablename__ = "approval_decision"

    request_id: Mapped[int] = mapped_column(
        ForeignKey("approval_request.id"), nullable=False, index=True
    )
    request_step_id: Mapped[int] = mapped_column(
        ForeignKey("approval_request_step.id"), nullable=False, index=True
    )
    decided_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, index=True
    )
    action: Mapped[ApprovalDecisionAction] = mapped_column(
        Enum(ApprovalDecisionAction), nullable=False, index=True
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delegated_to_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    request: Mapped["ApprovalRequest"] = relationship()
    request_step: Mapped["ApprovalRequestStep"] = relationship(back_populates="decisions")


class ApprovalComment(TenantTable):
    """Free-form comment thread attached to an approval request."""

    __tablename__ = "approval_comment"

    request_id: Mapped[int] = mapped_column(
        ForeignKey("approval_request.id"), nullable=False, index=True
    )
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    request: Mapped["ApprovalRequest"] = relationship(back_populates="comments")


# =============================================================================
# Staff Shift Management
# =============================================================================

class ShiftDefinition(TenantTable):
    """
    Reusable shift template owned by a department.

    Each department head creates definitions (e.g. "Morning Shift 07:00–15:00")
    that are then assigned to staff members.
    """

    __tablename__ = "shift_definition"

    department_id: Mapped[int] = mapped_column(
        ForeignKey("department.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    shift_type: Mapped[StaffShiftType] = mapped_column(
        Enum(StaffShiftType), nullable=False, index=True
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    color_hex: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # relationships
    department: Mapped["Department"] = relationship()


class StaffShiftAssignment(TenantTable):
    """
    Assigns a staff member to a specific shift definition on a specific date.
    """

    __tablename__ = "staff_shift_assignment"

    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    shift_definition_id: Mapped[int] = mapped_column(
        ForeignKey("shift_definition.id"), nullable=False, index=True
    )
    shift_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus), default=ShiftStatus.SCHEDULED, nullable=False, index=True
    )
    check_in_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    check_out_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )

    # relationships
    staff_profile: Mapped["StaffProfile"] = relationship()
    shift_definition: Mapped["ShiftDefinition"] = relationship()


class ShiftSwapRequest(TenantTable):
    """
    A request from one staff member to swap a shift assignment with another.
    """

    __tablename__ = "shift_swap_request"

    requester_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("staff_shift_assignment.id"), nullable=False, index=True
    )
    target_assignment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_shift_assignment.id"), nullable=True, index=True
    )
    target_staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", nullable=False, index=True
    )
    decided_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # relationships
    requester_assignment: Mapped["StaffShiftAssignment"] = relationship(
        foreign_keys=[requester_assignment_id]
    )
    target_staff: Mapped["StaffProfile"] = relationship()


# ============================================================
# STAFF ONBOARDING INVITATIONS
# ============================================================


class StaffOnboardingInvitation(TenantTable):
    """
    HR-issued onboarding invitation for a post-interview candidate.

    Lifecycle
    ---------
    1. HR creates the record in DRAFT status with the candidate's personal
       email, phone number, and basic demographic data.
    2. HR clicks "Send Link" → the status moves to PENDING and a unique,
       time-limited token is generated and emailed to the candidate.
    3. The candidate clicks the link in the email → status can transition
       to IN_PROGRESS while they complete the form (optional front-end step).
    4. The candidate submits all required data and uploads their documents
       → status moves to COMPLETED and the linked StaffProfile.onboarding_completed
       flag is set to True.
    5. HR can CANCEL a PENDING/DRAFT invitation at any time (e.g., candidate
       withdrew).  If a PENDING token passes its expiry, a background sweep
       marks it EXPIRED.
    6. HR can RESENT a PENDING or EXPIRED invitation; a new token is issued and
       the old one is invalidated.

    Security
    --------
    The raw token is never persisted — only its SHA-256 hash is stored
    (``token_hash``).  The plain token is returned exactly once (at issue or
    re-issue time) so the caller can embed it in the invitation email URL.

    Relationships
    -------------
    * A ``StaffOnboardingInvitation`` is linked to a ``StaffProfile`` (created
      by HR at the time the invitation is drafted) so that the candidate's
      record exists before they complete onboarding.
    * Uploaded documents are linked via ``StaffOnboardingDocument``.
    """

    __tablename__ = "staff_onboarding_invitation"

    # ── Core identity ────────────────────────────────────────────────────
    staff_profile_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), nullable=False, unique=True, index=True,
        comment="The pre-created staff profile this invitation is for.",
    )

    # ── Candidate contact (pre-populated by HR) ──────────────────────────
    candidate_email: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
        comment="Personal email address where the invitation link is sent.",
    )
    candidate_phone: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True,
        comment="Mobile number for SMS fallback delivery.",
    )

    # ── Token management ─────────────────────────────────────────────────
    token_hash: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True, unique=True,
        comment="SHA-256 hash of the raw invitation token. NULL when status=DRAFT.",
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="UTC timestamp after which the token is invalid.",
    )

    # ── Lifecycle ────────────────────────────────────────────────────────
    status: Mapped[OnboardingInvitationStatus] = mapped_column(
        Enum(OnboardingInvitationStatus),
        default=OnboardingInvitationStatus.DRAFT,
        nullable=False,
        index=True,
        comment="Current state in the onboarding invitation lifecycle.",
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp when the invitation email was last dispatched.",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp when the candidate marked their profile as complete.",
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    resend_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Number of times the invitation link has been re-dispatched.",
    )

    # ── Authorship / audit ────────────────────────────────────────────────
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True,
        comment="HR user who created this invitation.",
    )
    cancelled_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True,
        comment="HR user who cancelled this invitation.",
    )

    # ── Extra metadata ────────────────────────────────────────────────────
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Internal HR notes (not visible to the candidate).",
    )
    expiry_days: Mapped[int] = mapped_column(
        Integer, default=7, nullable=False,
        comment="Number of days the token remains valid after dispatch.",
    )

    # ── Salary presets (HR-defined) ───────────────────────────────────────
    salary_grade_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("salary_grade.id"), nullable=True,
    )
    salary_step_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("salary_step.id"), nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    staff_profile: Mapped["StaffProfile"] = relationship()
    documents: Mapped[list["StaffOnboardingDocument"]] = relationship(
        back_populates="invitation",
        cascade="all, delete-orphan",
    )


class StaffOnboardingDocument(TenantTable):
    """
    Document uploaded by a candidate during the onboarding flow.

    Each row represents one file the candidate submitted via the
    self-service onboarding portal.  The actual file bytes are stored
    on AWS S3; only the bucket key and a publicly-accessible URL are
    persisted here.

    The ``document_type`` is drawn from :class:`OnboardingDocumentType`
    and drives the checklist displayed to the candidate.

    After onboarding is complete, HR can promote any of these documents
    to the permanent ``StaffDocument`` table via a separate operation.
    """

    __tablename__ = "staff_onboarding_document"

    invitation_id: Mapped[int] = mapped_column(
        ForeignKey("staff_onboarding_invitation.id"),
        nullable=False,
        index=True,
        comment="Parent invitation this document belongs to.",
    )
    document_type: Mapped[OnboardingDocumentType] = mapped_column(
        Enum(OnboardingDocumentType),
        nullable=False,
        index=True,
        comment="Document category from the onboarding checklist.",
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Human-readable label for the document.",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Optional description provided by the candidate.",
    )

    # ── S3 storage metadata ──────────────────────────────────────────────
    s3_key: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="S3 object key used to retrieve/delete the file.",
    )
    file_url: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True,
        comment="Direct or pre-signed URL to access the stored file.",
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True,
        comment="MIME type of the uploaded file (e.g. application/pdf).",
    )
    size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True,
        comment="File size in bytes recorded at upload time.",
    )

    # ── Relationships ────────────────────────────────────────────────────
    invitation: Mapped["StaffOnboardingInvitation"] = relationship(
        back_populates="documents",
    )


class ClinicalMacro(TenantTable):
    """Personalized clinical macros / shortcuts for clinicians."""

    __tablename__ = "clinical_macro"

    clinician_staff_id: Mapped[int] = mapped_column(
        ForeignKey("staff_profile.id"), 
        nullable=False, 
        index=True,
        comment="The clinician who owns this macro."
    )
    shortcut_code: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        index=True,
        comment="The shortcode that triggers the macro (e.g. .exam)."
    )
    expanded_text: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="The expanded text content of the macro."
    )

    __table_args__ = (
        UniqueConstraint("clinician_staff_id", "shortcut_code", name="uq_clinician_shortcut"),
    )

    clinician_staff: Mapped["StaffProfile"] = relationship()


# ============================================================
# AI & CLINICAL DECISION SUPPORT
# ============================================================

class PatientAllergy(TenantTable):
    """Tracks patient allergies to drugs, food, or environment for CDSS."""

    __tablename__ = "patient_allergy"

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    allergen_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    severity: Mapped[AllergySeverity] = mapped_column(Enum(AllergySeverity), default=AllergySeverity.UNKNOWN)
    reaction_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    patient: Mapped["Patient"] = relationship()


class CdssAlert(TenantTable):
    """Audit log of CDSS alerts triggered during prescribing/clinical workflows."""

    __tablename__ = "cdss_alert"

    patient_id: Mapped[int] = mapped_column(ForeignKey("patient.id"), nullable=False, index=True)
    clinician_staff_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("visit.id"), nullable=True)
    
    alert_type: Mapped[CdssAlertType] = mapped_column(Enum(CdssAlertType), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    was_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship()
    clinician_staff: Mapped["StaffProfile"] = relationship()
    visit: Mapped[Optional["Visit"]] = relationship()


class AiScribeJob(TenantTable):
    """Tracks the status and output of Ambient AI Medical Scribe transcription jobs."""

    __tablename__ = "ai_scribe_job"

    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultation.id"), nullable=False, index=True, unique=True)
    clinician_staff_id: Mapped[int] = mapped_column(ForeignKey("staff_profile.id"), nullable=False, index=True)
    
    status: Mapped[AiScribeJobStatus] = mapped_column(Enum(AiScribeJobStatus), default=AiScribeJobStatus.PENDING)
    audio_s3_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    transcription_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_soap_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_icd10_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="JSON array of codes")
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    consultation: Mapped["Consultation"] = relationship()
    clinician_staff: Mapped["StaffProfile"] = relationship()

