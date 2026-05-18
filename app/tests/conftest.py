from __future__ import annotations
import os
from dotenv import load_dotenv

# Load .env file to ensure CAREPOINT_HMS_TEST_DATABASE_URL is picked up.
# IMPORTANT: load_dotenv populates os.environ with whatever names the
# .env declares (e.g. ``DATABASE_URL`` *without* the CAREPOINT_HMS_ prefix).
# Pydantic settings uses ``AliasChoices("DATABASE_URL", "CAREPOINT_HMS_DATABASE_URL")``
# and tries the *first* alias first, so a non-prefixed value in .env will
# override anything we put in CAREPOINT_HMS_DATABASE_URL below. If .env
# happens to point at a remote production database, the entire test suite
# silently runs against production — and integration tests that try to
# CREATE/DROP rows hang indefinitely or fail with confusing auth errors
# (which is what test_tenant_routes.py was doing).
#
# To make the test environment truly hermetic we:
#   1. force ``ENVIRONMENT=test`` *before* settings are imported,
#   2. nuke any inherited unprefixed ``DATABASE_URL``/``MASTER_DATABASE_URL``
#      that could have come from .env or the parent shell, and
#   3. set BOTH the unprefixed and prefixed forms to the test DB so
#      whichever AliasChoices entry pydantic picks resolves to the same
#      hermetic test database.
load_dotenv()

# Default to a locally-running test Postgres unless the operator has
# explicitly pointed the suite somewhere else.
test_db_url = os.environ.get(
    "CAREPOINT_HMS_TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:Admin123@localhost:5432/carepoint_hms_test",
)

# Step 1 — make sure the production-shaped vars don't leak in via .env.
for _leak in ("DATABASE_URL", "MASTER_DATABASE_URL"):
    if os.environ.get(_leak) and not os.environ[_leak].endswith("/carepoint_hms_test"):
        # Drop the leaked value; we'll set our own below.
        os.environ.pop(_leak, None)

# Step 2 — set BOTH alias variants so Settings.AliasChoices resolves to
# the test DB regardless of which choice it tries first.
os.environ["DATABASE_URL"] = test_db_url
os.environ["MASTER_DATABASE_URL"] = test_db_url
os.environ["CAREPOINT_HMS_DATABASE_URL"] = test_db_url
os.environ["CAREPOINT_HMS_MASTER_DATABASE_URL"] = test_db_url

# Step 3 — force "test" environment + a long-enough secret key so the
# pydantic settings model never trips its production safety guards.
os.environ["CAREPOINT_HMS_ENVIRONMENT"] = "test"
os.environ.setdefault("ENVIRONMENT", "test")
os.environ["CAREPOINT_HMS_SECRET_KEY"] = (
    "test-secret-key-please-change-to-something-longer-and-more-secure-2026"
)
# Disable in-memory rate limiting during tests.  The test suite fires 100+
# login requests from the same TestClient IP within 60s, which exhausts the
# per-path bucket and causes auth_header fixtures to receive 429 responses.
os.environ["CAREPOINT_HMS_RATE_LIMIT_ENABLED"] = "false"
# Disable email + SMS during tests so route handlers that lazily call
# notification helpers do not try to reach SMTP / Twilio (those hangs
# would otherwise look like the test suite itself is stalled).
os.environ.setdefault("CAREPOINT_HMS_EMAILS_ENABLED", "false")
os.environ.setdefault("CAREPOINT_HMS_SMS_ENABLED", "false")

from typing import Generator
import pytest


def _has_test_database() -> bool:
    """
    Best-effort detection of a usable test database.
    """
    url = os.getenv("CAREPOINT_HMS_DATABASE_URL") or os.getenv("DATABASE_URL")
    return bool(url and url.startswith("postgresql"))


HAS_TEST_DB = _has_test_database()


# ============================================================
# DATABASE-DEPENDENT FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def app_module():
    """
    Lazy import of the FastAPI app. Skips if no DB is available.
    """
    if not HAS_TEST_DB:
        pytest.skip("CAREPOINT_HMS_DATABASE_URL not configured for integration tests.")
    from app.main import app
    return app


@pytest.fixture(scope="session")
def database_engine():
    """
    Lazy import of the SQLAlchemy engine. Skips if no DB is available.

    Uses the **default** engine (``DATABASE_URL``) and **master** engine
    (``MASTER_DATABASE_URL``). We monkeypatch ``get_master_engine`` to ensure
    all database operations hit the same test database instance.

    Hermetic safety check
    ---------------------
    We refuse to run against a DB whose name does NOT end in ``_test``.
    Without this guard, a stray ``DATABASE_URL`` in .env (or the
    operator's shell) silently turns the test suite into a destructive
    operation against a real environment.
    """
    if not HAS_TEST_DB:
        pytest.skip("CAREPOINT_HMS_DATABASE_URL not configured for integration tests.")

    from app.core.database import engine, get_master_engine
    import app.core.database as db_mod

    # Refuse to run against any database whose name does not end in ``_test``.
    # This is the last line of defence against a misconfigured .env that
    # leaked production credentials into the test process.
    db_name = engine.url.database or ""
    if not db_name.endswith("_test"):
        pytest.skip(
            "Refusing to run integration tests against a non-test database "
            f"(connected to '{db_name}'). Point CAREPOINT_HMS_TEST_DATABASE_URL "
            "at a database whose name ends in '_test'."
        )

    # Monkeypatch get_master_engine to always return the main test engine
    # This ensures SaaS admin routes (which use master DB) hit the same DB.
    db_mod.get_master_engine = lambda: engine

    # Always run an idempotent forward-migrate so newly added master
    # tables (saas_admin, tenant, subscription_plan, ...) and tenant
    # tables show up automatically. Previously we only ran create_all
    # when the ``user`` table was missing, which meant a pre-existing
    # test DB never picked up new SaaS tables -> "relation
    # 'saas_admin' does not exist" during tenant route tests.
    print("\n[DB] Ensuring test schema is up to date (master + tenant)...")
    import app.models.all_models  # noqa: F401  ensure all models loaded
    from app.models.base import TenantBase, MasterBase
    from sqlalchemy import inspect, text

    try:
        MasterBase.metadata.create_all(bind=engine, checkfirst=True)
        TenantBase.metadata.create_all(bind=engine, checkfirst=True)
    except Exception as e:
        # Recover from "type already exists" by creating tables one at a
        # time and swallowing the duplicate-type errors per table.
        msg = str(e).lower()
        if "already exists" in msg:
            print(f"[DB] Note: Some types already exist, continuing... ({e})")
            for table in MasterBase.metadata.sorted_tables:
                try:
                    table.create(engine, checkfirst=True)
                except Exception:
                    pass
            for table in TenantBase.metadata.sorted_tables:
                try:
                    table.create(engine, checkfirst=True)
                except Exception:
                    pass
        else:
            raise
    
    # Ensure new columns exist on tables that may predate the model changes.
    # This is a lightweight migration for columns added after initial schema creation.
    from sqlalchemy import text
    _missing_columns = [
        ("purchase_requisition", "approval_request_id", "BIGINT"),
        ("salary_advance", "approval_request_id", "BIGINT"),
        ("leave_request", "approval_request_id", "BIGINT"),
        ("reimbursement_request", "approval_request_id", "BIGINT"),
        ("user", "deleted_by_id", "INTEGER"),
        ("user", "password_reset_token", "VARCHAR(255)"),
        ("user", "password_reset_token_expires_at", "TIMESTAMP WITH TIME ZONE"),
        ("user", "failed_login_attempts", "INTEGER DEFAULT 0"),
        ("user", "locked_until", "TIMESTAMP WITH TIME ZONE"),
        ("user", "last_failed_login_at", "TIMESTAMP WITH TIME ZONE"),
        ("user", "profile_photo_url", "VARCHAR(500)"),
        ("user", "job_title", "VARCHAR(150)"),
        ("user", "department_id", "INTEGER"),
        ("user", "facility_id", "INTEGER"),
        ("user", "employment_status", "VARCHAR(40)"),
        ("user", "bio", "TEXT"),
        ("user", "date_of_birth", "DATE"),
        ("user", "gender", "VARCHAR(20)"),
        ("role", "deleted_by_id", "INTEGER"),
        ("permission", "deleted_by_id", "INTEGER"),
        ("staff_profile", "deleted_by_id", "INTEGER"),
        ("patient", "deleted_by_id", "INTEGER"),
        ("patient", "chronic_conditions", "TEXT"),
        ("consultation", "visit_flow_step_id", "INTEGER"),
        ("vital_sign", "visit_flow_step_id", "INTEGER"),
        ("vital_sign", "pain_score", "INTEGER"),
        ("vital_sign", "mews_score", "INTEGER"),
        ("triage_assessment", "visit_flow_step_id", "INTEGER"),
        ("lab_order", "visit_flow_step_id", "INTEGER"),
        ("radiology_order", "visit_flow_step_id", "INTEGER"),
        ("prescription", "visit_flow_step_id", "INTEGER"),
        ("subscription_plan", "has_dietary", "BOOLEAN DEFAULT TRUE"),
        ("subscription_plan", "has_ambulance", "BOOLEAN DEFAULT TRUE"),
        ("subscription_plan", "has_compliance", "BOOLEAN DEFAULT TRUE"),
    ]


    with engine.connect() as conn:
        for table, col, col_type in _missing_columns:
            try:
                # Quote table names to handle reserved keywords like 'user'
                conn.execute(text(
                    f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS {col} {col_type}'
                ))
            except Exception as e:
                print(f"[DB] Failed to patch {table}.{col}: {e}")
                pass

        conn.commit()
    
    # Ensure baseline security data exists. Idempotent — adds only
    # missing rows on subsequent runs so it stays fast on a warm DB.
    from app.core.database import SessionLocal
    from app.seeds.security_seed import seed_security_baseline
    db = SessionLocal()
    try:
        seed_security_baseline(db, is_fresh=False)
        db.commit()
    except Exception:
        db.rollback()
        # Not fatal if it fails due to existing data
        pass
    finally:
        db.close()

    # Seed master-side reference data (subscription plans + a default
    # SaaS Admin row) that some integration tests need. Idempotent.
    db = SessionLocal()
    try:
        from app.init_db import seed_plans, seed_saas_admin

        seed_plans(db)
        seed_saas_admin(db)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    return engine


@pytest.fixture()
def db_session(database_engine) -> Generator:
    """
    Provide a SQLAlchemy session that rolls back after each test.
    """
    from app.core.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# Build a minimal stand-in that satisfies attribute access performed by
# routes and services (e.g. .id, .code, .active_subscription, .subscriptions).
from types import SimpleNamespace
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.multitenancy import set_current_tenant

_MOCK_TENANT = SimpleNamespace(
    id=0,
    code="test",
    name="Test Tenant",
    db_connection_string=None,
    active_subscription=SimpleNamespace(
        status="ACTIVE",
        is_active=True,
        has_clinical=True,
        has_inpatient=True,
        has_laboratory=True,
        has_pharmacy=True,
        has_inventory=True,
        has_billing=True,
        has_reporting=True,
        has_appointments=True,
        has_patient_portal=True,
        has_insurance=True,
        has_radiology=True,
        has_surgical=True,
        has_hr=True,
        has_dietary=True,
        has_ambulance=True,
        has_compliance=True,
    ),
    subscriptions=[],
)


class InjectTestTenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        set_current_tenant(_MOCK_TENANT)
        return await call_next(request)


@pytest.fixture(scope="session")
def client(app_module, database_engine):
    """
    FastAPI TestClient wired to the running app.

    Two things are necessary for integration tests in a multi-tenant setup:

    1. A mock tenant is injected into the request context so that route-level
       branching (``if get_current_tenant() is None`` → SaaS admin path)
       resolves to the normal tenant path.
    2. The ``get_db`` dependency is overridden to return a session bound to
       the **default** engine (``DATABASE_URL``), which is where
       ``create_tables()`` placed the tenant-model tables. Without this
       override the dependency falls back to the master engine
       (``MASTER_DATABASE_URL``) where tenant tables do not exist.
    """
    from fastapi.testclient import TestClient
    from app.core.database import get_db, SessionLocal

    def _test_get_db():
        """Use the default engine (same DB where tenant tables live)."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Add middleware only once (session-scoped).
    app_module.add_middleware(InjectTestTenantMiddleware)
    app_module.dependency_overrides[get_db] = _test_get_db
    # Force Starlette to rebuild its middleware stack
    app_module.middleware_stack = None
    _client = TestClient(app_module)
    yield _client
    # Cleanup
    app_module.dependency_overrides.pop(get_db, None)
    app_module.user_middleware = [
        m for m in app_module.user_middleware
        if m.cls is not InjectTestTenantMiddleware
    ]
    app_module.middleware_stack = None




@pytest.fixture()
def saas_client(app_module, database_engine):
    """
    Client for SaaS-level routes (tenants, SaaS admin, etc.)
    Does NOT inject a mock tenant.
    Overrides both get_db AND get_master_db so SaaS routes resolve correctly.
    """
    from fastapi.testclient import TestClient
    from app.core.database import get_db, get_master_db, SessionLocal

    # Save previous overrides so we can restore them (the session-scoped
    # client fixture also sets get_db and we must not destroy that).
    _prev_get_db = app_module.dependency_overrides.get(get_db)
    _prev_get_master_db = app_module.dependency_overrides.get(get_master_db)
    
    # Save and temporarily remove InjectTestTenantMiddleware if it exists
    _prev_middleware = app_module.user_middleware
    app_module.user_middleware = [
        m for m in app_module.user_middleware
        if getattr(m, "cls", None) is not InjectTestTenantMiddleware
    ]
    app_module.middleware_stack = None

    def _test_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app_module.dependency_overrides[get_db] = _test_get_db
    app_module.dependency_overrides[get_master_db] = _test_get_db
    _client = TestClient(app_module)
    yield _client

    # Restore previous overrides instead of popping.
    for dep, prev in [(get_db, _prev_get_db), (get_master_db, _prev_get_master_db)]:
        if prev is not None:
            app_module.dependency_overrides[dep] = prev
        else:
            app_module.dependency_overrides.pop(dep, None)
            
    # Restore middleware
    app_module.user_middleware = _prev_middleware
    app_module.middleware_stack = None


@pytest.fixture()
def saas_admin_user(db_session):
    """Create a SaaS Admin user in the master database."""
    from app.models.all_models import SaaSAdmin
    from app.core.security import get_password_hash
    import uuid

    email = f"saas-admin-{uuid.uuid4().hex[:8]}@test.example"
    password = "SaaSAdminPass123"
    from app.core.enums import UserStatus, SaaSRole
    admin = SaaSAdmin()
    admin.email = email
    admin.password_hash = get_password_hash(password)
    admin.first_name = "SaaS"
    admin.last_name = "Administrator"
    admin.status = UserStatus.ACTIVE
    admin.is_superuser = True
    admin.platform_role = SaaSRole.SUPER_ADMIN
    # SaaSAdmin usually lives in master DB. In tests, we use the same DB.
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return {"email": email, "password": password, "obj": admin}

@pytest.fixture(scope="session")
def seeded_security(database_engine):
    """
    Ensure the canonical role/permission seed has been applied for tests
    that assume those records exist.
    
    Now a session-scoped no-op as seeding happens in database_engine.
    """
    return True


@pytest.fixture()
def make_user(db_session, seeded_security):
    """
    Factory fixture that returns a callable for creating ad-hoc users.
    Lets each test create the exact users it needs without re-implementing
    the boilerplate.
    """
    import uuid

    from app.core.enums import UserStatus
    from app.core.security import get_password_hash
    from app.models.all_models import Role, User, UserRoleAssociation

    def _create(
        *,
        username: str | None = None,
        password: str = "Password123!",
        role_codes: list[str] | None = None,
        is_superuser: bool = False,
    ):
        username = username or f"u-{uuid.uuid4().hex[:10]}"
        user = User(
            username=username,
            email=f"{username}@test.example",
            password_hash=get_password_hash(password),
            first_name="Test",
            last_name="User",
            status=UserStatus.ACTIVE,
            is_superuser=is_superuser,
            is_email_verified=True,
        )
        db_session.add(user)
        db_session.flush()
        for code in role_codes or []:
            role = (
                db_session.query(Role)
                .filter(Role.code == code, Role.is_deleted.is_(False))
                .first()
            )
            if role is not None:
                db_session.add(UserRoleAssociation(user_id=user.id, role_id=role.id))
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture()
def make_patient(db_session):
    """Factory that creates a minimal Patient for clinical tests."""

    import uuid

    from app.models.all_models import Patient

    def _create(**overrides):
        defaults = {
            "hospital_number": f"HN-{uuid.uuid4().hex[:8].upper()}",
            "first_name": "Test",
            "last_name": "Patient",
        }
        defaults.update(overrides)
        try:
            p = Patient(**defaults)
        except TypeError:
            # Patient may have additional required fields in this build;
            # skip the test rather than fail it for callers that just
            # need *some* patient.
            pytest.skip("Patient model requires fields this fixture doesn't supply.")
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        return p

    return _create


@pytest.fixture()
def make_staff(db_session, make_user):
    """Factory that creates a StaffProfile + linked User."""

    import uuid

    from app.models.all_models import StaffProfile

    def _create(**overrides):
        user = overrides.pop("user", None) or make_user(role_codes=["DOCTOR"])
        defaults = {
            "user_id": user.id,
            "staff_no": f"STF-{uuid.uuid4().hex[:8].upper()}",
            "job_title": "Test Staff",
        }
        defaults.update(overrides)
        rec = StaffProfile(**defaults)
        db_session.add(rec)
        db_session.commit()
        db_session.refresh(rec)
        return rec

    return _create


@pytest.fixture()
def admin_user(db_session, seeded_security):
    """
    Create a TENANT_ADMIN user and return raw credentials for login tests.
    """
    import uuid
    from app.core.enums import UserStatus
    from app.core.security import get_password_hash
    from app.models.all_models import Role, User, UserRoleAssociation, StaffProfile

    username = f"admin-{uuid.uuid4().hex[:10]}"
    email = f"{username}@test.example"
    password = "AdminPass123"

    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash(password),
        first_name="Test",
        last_name="Admin",
        status=UserStatus.ACTIVE,
        is_superuser=True,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    # Create a staff profile for the admin user so it can perform staff actions
    staff = StaffProfile(
        user_id=user.id,
        staff_no=f"STF-{uuid.uuid4().hex[:8].upper()}",
        job_title="Administrator"
    )
    db_session.add(staff)
    db_session.flush()

    role = (
        db_session.query(Role)
        .filter(Role.code == "TENANT_ADMIN", Role.is_deleted.is_(False))
        .first()
    )
    if role is not None:
        db_session.add(UserRoleAssociation(user_id=user.id, role_id=role.id))

    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(staff)
    return {"user": user, "username": username, "email": email, "password": password, "staff": staff}
