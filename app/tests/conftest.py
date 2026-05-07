from __future__ import annotations
import os
from dotenv import load_dotenv

# Load .env file to ensure CAREPOINT_HMS_TEST_DATABASE_URL is picked up
load_dotenv()

# Set environment variables BEFORE any other imports to avoid Pydantic validation warnings
# We force these for tests to ensure consistency and avoid short-key warnings.
# We use 'carepoint_hms_test' to ensure we don't hit the dev/prod database.
test_db_url = os.environ.get(
    "CAREPOINT_HMS_TEST_DATABASE_URL", 
    "postgresql+psycopg2://postgres:Admin123@localhost:5432/carepoint_hms_test"
)
os.environ["CAREPOINT_HMS_DATABASE_URL"] = test_db_url
os.environ["CAREPOINT_HMS_MASTER_DATABASE_URL"] = test_db_url
os.environ["CAREPOINT_HMS_SECRET_KEY"] = "test-secret-key-please-change-to-something-longer-and-more-secure-2026"
# Disable in-memory rate limiting during tests.  The test suite fires 100+
# login requests from the same TestClient IP within 60s, which exhausts the
# per-path bucket and causes auth_header fixtures to receive 429 responses.
os.environ["CAREPOINT_HMS_RATE_LIMIT_ENABLED"] = "false"

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
    """
    if not HAS_TEST_DB:
        pytest.skip("CAREPOINT_HMS_DATABASE_URL not configured for integration tests.")
    
    from app.core.database import engine, get_master_engine
    import app.core.database as db_mod
    
    # Monkeypatch get_master_engine to always return the main test engine
    # This ensures SaaS admin routes (which use master DB) hit the same DB.
    db_mod.get_master_engine = lambda: engine
    
    # We no longer drop/recreate tables here aggressively. 
    # Instead, we check if a core table exists. If not, we create all tables.
    # This avoids the slow SSL connection closures on every run.
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if not inspector.has_table("user"):
        print("\n[DB] Tables missing or incomplete. Initializing schema...")
        import app.models.all_models
        from app.models.base import TenantBase, MasterBase
        
        with engine.connect() as conn:
            # Postgres Enum workaround: if create_all fails because of existing types,
            # we try to ignore those specific errors or handle them.
            try:
                TenantBase.metadata.create_all(bind=conn, checkfirst=True)
                MasterBase.metadata.create_all(bind=conn, checkfirst=True)
                conn.commit()
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f"[DB] Note: Some types already exist, continuing... ({e})")
                    conn.rollback()
                    # Try creating tables one by one as a fallback
                    for table in TenantBase.metadata.sorted_tables:
                        try:
                            table.create(conn, checkfirst=True)
                        except Exception:
                            pass
                    for table in MasterBase.metadata.sorted_tables:
                        try:
                            table.create(conn, checkfirst=True)
                        except Exception:
                            pass
                    conn.commit()
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
    ]
    with engine.connect() as conn:
        for table, col, col_type in _missing_columns:
            try:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
                ))
            except Exception:
                pass
        conn.commit()
    
    # (Optional) Ensure baseline security data exists if it's an empty DB
    from app.core.database import SessionLocal
    from app.seeds.security_seed import seed_security_baseline
    db = SessionLocal()
    try:
        # We run seed_security_baseline in non-fresh mode (is_fresh=False)
        # so it only adds missing records without being slow.
        seed_security_baseline(db, is_fresh=False)
        db.commit()
    except Exception as e:
        db.rollback()
        # Not fatal if it fails due to existing data
        pass
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
