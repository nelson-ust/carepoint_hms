# app/services/tenant_service.py
"""
Service layer for tenant lifecycle.

Responsibilities
----------------
* Register new tenants in the master database (idempotent).
* Provision the per-tenant operational database, run migrations, seed
  default roles + permissions, and create the tenant admin user.
* Auto-bootstrap ``TenantSetting`` (branding/regional defaults).
* Manage tenant status transitions (suspend, reactivate, reject).
* Run tenant DB migrations across the fleet.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_master_db_context
from app.core.cryptography import encrypt_string, decrypt_string
from app.core.enums import (
    NotificationStatus,
    SubscriptionStatus,
    UserStatus,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.logger import get_logger
from app.core.security import get_password_hash
from app.init_db import create_new_database, run_tenant_initialization
from app.models.all_models import (
    Role,
    SaaSAdmin,
    SaaSNotification,
    SubscriptionPlan,
    Tenant,
    TenantDomain,
    TenantSetting,
    TenantSubscription,
    User,
)
from app.schemas.tenant_schemas import TenantRegistrationSchema
from app.services.aws_s3_service import S3Service

try:
    from app.utils.email_utils import send_email
except ImportError:
    send_email = None

try:
    from app.utils.sms_util import send_sms
except ImportError:
    send_sms = None


logger = get_logger(__name__)


def _period_end_for_plan(plan, period_start: datetime) -> datetime:
    """
    Compute the end of a single billing period for ``plan``.

    Falls back to a 30-day month when the plan does not declare an
    interval. This helper is used by both registration and the billing
    service so renewal arithmetic stays consistent.
    """
    interval = getattr(plan, "interval", None)
    interval_value = str(getattr(interval, "value", interval) or "MONTHLY").upper()
    if interval_value == "YEARLY" or interval_value == "ANNUAL":
        return period_start + timedelta(days=365)
    if interval_value == "QUARTERLY":
        return period_start + timedelta(days=91)
    if interval_value == "WEEKLY":
        return period_start + timedelta(days=7)
    if interval_value == "DAILY":
        return period_start + timedelta(days=1)
    return period_start + timedelta(days=30)

class TenantService:
    def __init__(self, db: Session) -> None:
        """
        Note: The 'db' here should ideally be a Master DB session 
        for tenant creation operations.
        """
        self.db = db

    def register_tenant(self, payload: TenantRegistrationSchema) -> Tenant:
        """
        Capture a new tenant onboarding application.

        This method ONLY persists the application in the master database.
        Specifically it:

          * creates the :class:`Tenant` row with ``status=PENDING`` and
            ``is_provisioned=False``,
          * stores the prospective admin's credentials inside
            ``onboarding_data`` (hashed) so they can be promoted to a
            real ``User`` later,
          * attaches the primary :class:`TenantDomain`,
          * creates a :class:`TenantSubscription` (TRIALING when the plan
            offers a trial, otherwise PENDING),
          * dispatches an acknowledgement email to the applicant
            (``admin_email`` and ``billing_email`` if different),
          * notifies all active SaaS administrators that an approval is
            required.

        This method DOES NOT:

          * create the tenant database — that happens only in
            :meth:`provision_tenant`, which the SaaS admin triggers via
            ``POST /api/v1/tenants/{tenant_id}/approve``,
          * run any migrations or seed any data,
          * make the tenant accessible.

        The applicant therefore knows their request was received but
        cannot log in until a SaaS admin approves the registration.
        """
        # 1. Validate plan
        from sqlalchemy import func
        plan = self.db.query(SubscriptionPlan).filter(
            func.upper(SubscriptionPlan.code) == payload.plan_code.upper(),
            SubscriptionPlan.is_active == True
        ).first()
        if not plan:
            raise NotFoundError(message="Selected subscription plan not found.")

        # 2. Check if tenant code exists (Idempotency)
        existing = self.db.query(Tenant).filter(Tenant.code == payload.tenant_code.lower()).first()
        if existing:
            return existing

        # 3. Create Tenant in Master DB
        db_name = f"hms_tenant_{payload.tenant_code.lower()}"
        master_url = settings.MASTER_DATABASE_URL
        if not master_url:
            raise BadRequestError(message="MASTER_DATABASE_URL is not configured.")
        
        from sqlalchemy.engine import make_url
        url_obj = make_url(master_url)
        tenant_db_url = str(url_obj.set(database=db_name))

        # Store admin info for later provisioning
        onboarding_data = {
            "admin_email": payload.admin_email,
            "admin_username": payload.admin_username,
            "admin_password_hash": get_password_hash(payload.admin_password),
            "admin_first_name": payload.admin_first_name,
            "admin_last_name": payload.admin_last_name
        }

        # Always store *some* deliverable billing email — fall back to the
        # admin email if the operator did not supply a dedicated one.
        billing_email = (
            (payload.billing_email or payload.admin_email).strip().lower()
        )

        tenant = Tenant(
            name=payload.tenant_name,
            code=payload.tenant_code.lower(),
            domain_url=payload.domain_url,
            db_name=db_name,
            db_connection_string=encrypt_string(tenant_db_url),
            status=UserStatus.PENDING,
            is_provisioned=False,
            onboarding_data=onboarding_data,
            billing_email=billing_email,
            billing_phone=payload.billing_phone,
            billing_contact_name=payload.billing_contact_name,
            billing_address=payload.billing_address,
            tax_id=payload.tax_id,
        )
        self.db.add(tenant)
        self.db.flush()

        # 4. Add Primary Domain
        domain = TenantDomain(
            tenant_id=tenant.id,
            domain_name=payload.domain_url,
            is_primary=True
        )
        self.db.add(domain)

        # 5. Create Subscription. If the plan offers a trial, start in TRIALING
        # state so the tenant can use the platform during the trial window.
        now = datetime.now(timezone.utc)
        trial_days = int(getattr(plan, "trial_days", 0) or 0)
        if trial_days > 0:
            sub_status = SubscriptionStatus.TRIALING
            trial_end = now + timedelta(days=trial_days)
            period_start = now
            period_end = trial_end
            next_invoice = trial_end
        else:
            sub_status = SubscriptionStatus.PENDING
            trial_end = None
            # Establish the first billing window from the plan interval so
            # the billing service knows when to issue the first invoice.
            period_start = now
            period_end = _period_end_for_plan(plan, period_start)
            next_invoice = now  # invoice immediately for paid plans on activation

        subscription = TenantSubscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status=sub_status,
            start_date=now,
            trial_end_date=trial_end,
            current_period_start=period_start,
            current_period_end=period_end,
            next_invoice_at=next_invoice,
            auto_renew=True,
        )
        self.db.add(subscription)
        self.db.commit()

        # 6. Notify SaaS Administrators that approval is required.
        self._notify_saas_admins_of_registration(tenant)

        # 7. Acknowledge the applicant. Best-effort: a missing SMTP
        # configuration must not abort the registration.
        try:
            self._notify_applicant_received(tenant, payload)
        except Exception as exc:
            logger.warning(
                "Could not send registration acknowledgement to applicant for "
                "tenant %s: %s",
                tenant.code,
                exc,
            )

        return tenant

    # ------------------------------------------------------------------
    # Applicant-facing notifications
    # ------------------------------------------------------------------

    def _resolve_applicant_recipients(
        self,
        tenant: Tenant,
        payload: Optional[TenantRegistrationSchema] = None,
    ) -> list[str]:
        """
        Return the de-duplicated list of email addresses that should
        receive applicant-facing communication for ``tenant``.

        Always includes the tenant admin email, plus the billing email
        when it is different.
        """
        candidates: list[str] = []

        # Admin email — primary communication channel for the operator.
        admin_email: Optional[str] = None
        if payload is not None:
            admin_email = (payload.admin_email or "").strip()
        if not admin_email and tenant.onboarding_data:
            admin_email = (tenant.onboarding_data or {}).get("admin_email")
        if admin_email:
            candidates.append(admin_email.strip().lower())

        # Billing email — only when present AND different from the admin
        # email (to avoid CCing the same person twice).
        if tenant.billing_email:
            billing = tenant.billing_email.strip().lower()
            if billing and billing not in candidates:
                candidates.append(billing)

        return candidates

    def _notify_applicant_received(
        self,
        tenant: Tenant,
        payload: TenantRegistrationSchema,
    ) -> None:
        """
        Send the "we've received your application" acknowledgement.

        Reaches the prospective tenant admin (and the billing contact
        when distinct) and explains the next step is approval by a SaaS
        administrator.
        """
        recipients = self._resolve_applicant_recipients(tenant, payload)
        if not recipients:
            logger.info(
                "Skipping applicant acknowledgement for tenant %s: no recipients.",
                tenant.code,
            )
            return

        subject = (
            f"We've received your CarePoint HMS registration — {tenant.name}"
        )
        applicant_name = (
            f"{payload.admin_first_name} {payload.admin_last_name}".strip()
            or tenant.billing_contact_name
            or tenant.name
        )
        body = (
            f"Hello {applicant_name},\n\n"
            f"Thank you for registering {tenant.name} with CarePoint HMS.\n\n"
            f"Your application has been received and is currently being "
            f"reviewed by our SaaS administration team. The information "
            f"you submitted is summarised below for your records:\n\n"
            f"  Tenant name:     {tenant.name}\n"
            f"  Tenant code:     {tenant.code}\n"
            f"  Primary domain:  {tenant.domain_url}\n"
            f"  Subscription:    {payload.plan_code}\n"
            f"  Admin email:     {payload.admin_email}\n"
            f"\n"
            f"You will receive a follow-up email as soon as your "
            f"registration is approved and your tenant environment is "
            f"provisioned. At that point you'll be able to sign in at "
            f"https://{tenant.domain_url} with the username "
            f"'{payload.admin_username}' and the password you supplied "
            f"during registration.\n\n"
            f"If you did not initiate this registration, or you need to "
            f"make changes before approval, please reply to this email.\n\n"
            f"— The CarePoint HMS Team"
        )

        if send_email is None:
            logger.warning(
                "send_email helper unavailable; applicant acknowledgement for "
                "tenant %s was not delivered.",
                tenant.code,
            )
            return

        for recipient in recipients:
            try:
                send_email(
                    subject=subject,
                    recipients=[recipient],
                    body_text=body,
                )
                logger.info(
                    "Registration acknowledgement sent to %s for tenant %s.",
                    recipient,
                    tenant.code,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to send registration acknowledgement to %s: %s",
                    recipient,
                    exc,
                )

        # Best-effort SMS to the billing phone (if provided) so the
        # applicant gets a confirmation even when their email bounces.
        if send_sms is not None and tenant.billing_phone:
            try:
                send_sms(
                    to=tenant.billing_phone,
                    body=(
                        f"CarePoint HMS: We've received your registration for "
                        f"{tenant.name}. You will be notified once it is approved."
                    ),
                )
            except Exception as exc:
                logger.warning(
                    "Failed to send registration acknowledgement SMS to %s: %s",
                    tenant.billing_phone,
                    exc,
                )

    def _notify_applicant_approved(self, tenant: Tenant) -> None:
        """
        Send the "your tenant has been approved" notification once the
        SaaS admin has run :meth:`provision_tenant` successfully.
        """
        recipients = self._resolve_applicant_recipients(tenant)
        if not recipients:
            logger.info(
                "Skipping approval notification for tenant %s: no recipients.",
                tenant.code,
            )
            return

        # Resolve the admin username from onboarding_data before it was
        # cleared. provision_tenant calls this BEFORE setting
        # onboarding_data=None so username is still available.
        admin_username = "(see onboarding email)"
        admin_first_name = tenant.billing_contact_name or tenant.name
        if tenant.onboarding_data:
            admin_username = tenant.onboarding_data.get("admin_username", admin_username)
            admin_first_name = (
                tenant.onboarding_data.get("admin_first_name") or admin_first_name
            )

        subject = f"Your CarePoint HMS tenant is now active — {tenant.name}"
        body = (
            f"Hello {admin_first_name},\n\n"
            f"Great news — your CarePoint HMS registration for "
            f"{tenant.name} has been approved and your tenant environment "
            f"is now live.\n\n"
            f"  Sign-in URL:   https://{tenant.domain_url}\n"
            f"  Tenant code:   {tenant.code}\n"
            f"  Admin user:    {admin_username}\n"
            f"\n"
            f"Use the password you supplied during registration to sign "
            f"in. We strongly recommend updating it on first use, and "
            f"enabling two-factor authentication from your profile.\n\n"
            f"Invoices, payment receipts, and renewal reminders will be "
            f"sent to your billing contact"
            f"{(' at ' + tenant.billing_email) if tenant.billing_email else ''}.\n\n"
            f"Welcome aboard.\n\n"
            f"— The CarePoint HMS Team"
        )

        if send_email is None:
            logger.warning(
                "send_email helper unavailable; approval notification for "
                "tenant %s was not delivered.",
                tenant.code,
            )
            return

        for recipient in recipients:
            try:
                send_email(
                    subject=subject,
                    recipients=[recipient],
                    body_text=body,
                )
                logger.info(
                    "Approval notification sent to %s for tenant %s.",
                    recipient,
                    tenant.code,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to send approval notification to %s: %s",
                    recipient,
                    exc,
                )

    def _notify_saas_admins_of_registration(self, tenant: Tenant) -> None:
        """
        Dispatch Email, SMS, and In-App notifications to all active SaaS Admins.
        """
        saas_admins = self.db.query(SaaSAdmin).filter(SaaSAdmin.status == UserStatus.ACTIVE).all()
        
        subject = f"New Tenancy Onboarding Request: {tenant.name}"
        body = (
            f"A new tenant ({tenant.name} - Code: {tenant.code}) has registered "
            f"and is awaiting approval and provisioning."
        )

        for admin in saas_admins:
            # 1. In-App Notification (Master DB)
            notification = SaaSNotification(
                saas_admin_id=admin.id,
                subject=subject,
                body=body,
                status=NotificationStatus.PENDING,
                is_read=False
            )
            self.db.add(notification)
            
            # 2. Email Notification
            if send_email and admin.email:
                try:
                    send_email(
                        subject=subject,
                        recipients=[admin.email],
                        body_text=body
                    )
                except Exception as e:
                    # Log but do not interrupt the registration flow
                    print(f"Failed to send email to {admin.email}: {e}")
                    
            # 3. SMS Notification
            # Note: Assuming SaaSAdmin model has a phone_number in the future,
            # or if it exists now, we use it. Currently SaaSAdmin model only has email.
            phone_number = getattr(admin, "phone_number", None)
            if send_sms and phone_number:
                try:
                    send_sms(to=phone_number, body=body)
                except Exception as e:
                    print(f"Failed to send SMS to {phone_number}: {e}")

        self.db.commit()

    def provision_tenant(
        self,
        tenant_id: int,
        admin_payload: Optional[TenantRegistrationSchema] = None,
    ) -> Tenant:
        """
        Approve a pending registration and physically provision the tenant.

        This is the **only** entry point that creates the tenant
        database. It must therefore be called by an authenticated SaaS
        Superuser (route: ``POST /api/v1/tenants/{tenant_id}/approve``).

        Steps performed (in order):

          1. Create the physical PostgreSQL database for the tenant.
          2. Run schema creation + seeds (roles, permissions, etc.).
          3. Materialise the tenant admin user from the captured
             ``onboarding_data``.
          4. Bootstrap default :class:`TenantSetting`.
          5. Mark the tenant ``ACTIVE`` and ``is_provisioned=True``.
          6. Activate the subscription (PENDING → ACTIVE; TRIALING is
             preserved).
          7. Provision the tenant's S3 bucket (best-effort).
          8. Email the applicant that their tenant is now live.

        Idempotent: if the tenant is already provisioned the method is a
        no-op and returns the existing record unchanged.
        """
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError(message="Tenant not found.")

        if tenant.is_provisioned:
            return tenant

        # 1. Physically create the database
        try:
            create_new_database(tenant.db_name)
        except Exception as e:
            raise BadRequestError(message=f"Failed to create tenant database: {str(e)}")

        # 2. Initialize Tenant Database (Tables + Seeds)
        db_url = decrypt_string(tenant.db_connection_string)
        try:
            run_tenant_initialization(db_url, create_default_admin=False)
        except Exception as e:
            raise BadRequestError(message=f"Failed to initialize tenant database: {str(e)}")

        # 3. Create Admin User in the new Tenant Database
        if admin_payload:
            self._create_tenant_admin(db_url, admin_payload=admin_payload)
        elif tenant.onboarding_data:
            self._create_tenant_admin(db_url, onboarding_data=tenant.onboarding_data)
        else:
            raise BadRequestError(message="No admin user details found for provisioning.")

        # 4. Bootstrap TenantSetting (branding/regional defaults) in the tenant DB.
        try:
            self._bootstrap_tenant_settings(db_url)
        except Exception as exc:
            logger.warning(f"Failed to bootstrap TenantSetting for {tenant.code}: {exc}")

        # 5. Update Status in Master DB
        tenant.status = UserStatus.ACTIVE
        tenant.is_provisioned = True

        # 6. Update subscription status. Preserve TRIALING state so the trial
        # window keeps running; only PENDING subscriptions become ACTIVE.
        subscription = self.db.query(TenantSubscription).filter(
            TenantSubscription.tenant_id == tenant.id
        ).first()
        if subscription and subscription.status == SubscriptionStatus.PENDING:
            subscription.status = SubscriptionStatus.ACTIVE

        # 7. Provision AWS S3 Bucket (best-effort).
        try:
            s3_service = S3Service()
            bucket_name = s3_service.create_tenant_bucket(tenant.code)
            if bucket_name:
                tenant.aws_s3_bucket_name = bucket_name
        except Exception as exc:
            logger.warning(f"S3 bucket provisioning skipped for {tenant.code}: {exc}")

        # 8. Notify the applicant. We do this BEFORE clearing
        # ``onboarding_data`` because the approval email re-uses the
        # admin username/first name we captured at registration.
        try:
            self._notify_applicant_approved(tenant)
        except Exception as exc:
            logger.warning(
                "Could not send approval notification for tenant %s: %s",
                tenant.code,
                exc,
            )

        # Clear onboarding data only after the email is dispatched.
        tenant.onboarding_data = None

        self.db.commit()
        return tenant

    # ------------------------------------------------------------------
    # Tenant Settings bootstrap
    # ------------------------------------------------------------------

    def _bootstrap_tenant_settings(self, db_url: str) -> None:
        """
        Create a default :class:`TenantSetting` row inside the new tenant DB
        if one does not already exist. The TenantSetting model defines column
        defaults for branding/regional configuration so an empty insert is
        sufficient.
        """
        engine = create_engine(db_url, future=True)
        try:
            with Session(engine) as tenant_db:
                existing = tenant_db.query(TenantSetting).first()
                if existing is not None:
                    return
                tenant_db.add(TenantSetting())
                tenant_db.commit()
        finally:
            engine.dispose()

    def _create_tenant_admin(
        self, 
        db_url: str, 
        admin_payload: Optional[TenantRegistrationSchema] = None,
        onboarding_data: Optional[dict] = None
    ):
        """
        Connect directly to the newly created tenant DB to insert the first admin.
        """
        engine = create_engine(db_url, future=True)
        with Session(engine) as tenant_db:
            # Resolve the ADMIN role (which was seeded by run_tenant_initialization)
            admin_role = tenant_db.query(Role).filter(Role.code == "TENANT_ADMIN").first()
            if not admin_role:
                 admin_role = Role(name="Tenant Admin", code="TENANT_ADMIN")
                 tenant_db.add(admin_role)
                 tenant_db.flush()

            if admin_payload:
                admin_user_data = {
                    "first_name": admin_payload.admin_first_name,
                    "last_name": admin_payload.admin_last_name,
                    "email": admin_payload.admin_email.strip().lower(),
                    "username": admin_payload.admin_username.strip().lower(),
                    "password_hash": get_password_hash(admin_payload.admin_password),
                }
            elif onboarding_data:
                admin_user_data = {
                    "first_name": onboarding_data["admin_first_name"],
                    "last_name": onboarding_data["admin_last_name"],
                    "email": onboarding_data["admin_email"].strip().lower(),
                    "username": onboarding_data["admin_username"].strip().lower(),
                    "password_hash": onboarding_data["admin_password_hash"],
                }
            else:
                return

            # Check if user already exists to make this idempotent
            existing_user = tenant_db.query(User).filter(User.email == admin_user_data["email"]).first()
            if existing_user:
                # If the user exists, we check if they have the role, otherwise we're done
                from app.models.all_models import UserRoleAssociation
                role_link = tenant_db.query(UserRoleAssociation).filter(
                    UserRoleAssociation.user_id == existing_user.id,
                    UserRoleAssociation.role_id == admin_role.id
                ).first()
                if not role_link:
                    tenant_db.add(UserRoleAssociation(user_id=existing_user.id, role_id=admin_role.id))
                    tenant_db.commit()
                return

            admin_user = User(
                first_name=admin_user_data["first_name"],
                last_name=admin_user_data["last_name"],
                email=admin_user_data["email"],
                username=admin_user_data["username"],
                password_hash=admin_user_data["password_hash"],
                status=UserStatus.ACTIVE,
                is_superuser=True,
                is_email_verified=True
            )
            tenant_db.add(admin_user)
            tenant_db.flush()

            from app.models.all_models import UserRoleAssociation
            tenant_db.add(UserRoleAssociation(user_id=admin_user.id, role_id=admin_role.id))
            tenant_db.commit()

    def get_tenants(self, page: int = 1, page_size: int = 20, status: Optional[str] = None):
        query = self.db.query(Tenant)
        if status:
            query = query.filter(Tenant.status == status)
        
        total_count = query.count()
        tenants = query.order_by(Tenant.date_created.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return {
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "tenants": tenants
        }

    def get_tenant(self, tenant_id: int) -> Tenant:
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundError(message="Tenant not found.")
        return tenant

    def update_tenant_status(self, tenant_id: int, new_status: str) -> Tenant:
        tenant = self.get_tenant(tenant_id)
        
        try:
            status_enum = UserStatus[new_status.upper()]
        except KeyError:
            raise BadRequestError(message=f"Invalid status: {new_status}")
            
        tenant.status = status_enum
        
        # If suspended, suspend the subscription as well
        if status_enum == UserStatus.SUSPENDED:
            sub = self.db.query(TenantSubscription).filter(TenantSubscription.tenant_id == tenant.id).first()
            if sub:
                sub.status = SubscriptionStatus.SUSPENDED
        
        self.db.commit()
        return tenant

    def run_migrations_all_tenants(self) -> dict:
        """
        Run database initialization/migrations for every active, provisioned
        tenant. Failures are isolated per-tenant — one bad tenant does not
        abort the rest.
        """
        tenants = self.db.query(Tenant).filter(
            Tenant.is_active.is_(True),
            Tenant.is_provisioned.is_(True),
        ).all()

        results = {"total": len(tenants), "success": 0, "failed": 0, "errors": []}

        for tenant in tenants:
            try:
                db_url = decrypt_string(tenant.db_connection_string)
                run_tenant_initialization(db_url, create_default_admin=False)
                results["success"] += 1
                logger.info(f"Successfully ran migrations for tenant: {tenant.code}")
            except Exception as e:
                results["failed"] += 1
                error_msg = f"Failed to migrate tenant {tenant.code}: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(error_msg)

        return results

    def get_system_health(self) -> dict:
        """
        Check the health of core infrastructure components.
        """
        health = {
            "master_db": "HEALTHY",
            "s3_storage": "HEALTHY",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # 1. Check Master DB
        try:
            self.db.execute(text("SELECT 1"))
        except Exception as e:
            health["master_db"] = f"UNHEALTHY: {str(e)}"
            
        # 2. Check S3
        s3_service = S3Service()
        if s3_service.is_enabled:
            try:
                s3_service.s3_client.list_buckets()
            except Exception as e:
                health["s3_storage"] = f"UNHEALTHY: {str(e)}"
        else:
            health["s3_storage"] = "DISABLED"
            
        return health
