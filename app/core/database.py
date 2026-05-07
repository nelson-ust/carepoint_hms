# carepoint_hms/app/core/database.py
from __future__ import annotations

"""
carepoint_hms.app.core.database

Centralized database configuration and session management for Carepoint HMS.

Purpose
-------
This module provides:
- SQLAlchemy engine creation for PostgreSQL
- session factory configuration
- FastAPI request-scoped database dependency
- helper utilities for connectivity checks
- optional schema create/drop helpers for local development

Design goals
------------
- PostgreSQL-first setup
- SQLAlchemy 2.x style
- stable connection pooling
- safe session lifecycle management
- clean integration with FastAPI and Alembic

Expected configuration
----------------------
This module expects `app.core.config.settings` to expose values such as:

- DATABASE_URL
    Example:
    postgresql+psycopg2://postgres:password@localhost:5432/carepoint_hms

Optional settings:
- SQLALCHEMY_ECHO
- DB_POOL_SIZE
- DB_MAX_OVERFLOW
- DB_POOL_TIMEOUT
- DB_POOL_RECYCLE
- DB_POOL_PRE_PING
- DB_ISOLATION_LEVEL

Notes
-----
- PostgreSQL is the primary supported database for this application.
- In production, database schema changes should be managed with Alembic.
- `create_tables()` is mainly useful for local development and tests.
"""

from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import MasterBase, TenantBase

from app.core.multitenancy import get_current_tenant_db_url

try:
    from app.core.config import settings
except Exception:
    settings = None


def _get_required_database_url() -> str:
    """
    Resolve the PostgreSQL database URL from application settings.

    Raises
    ------
    RuntimeError
        If DATABASE_URL is missing.
    """
    database_url = getattr(settings, "DATABASE_URL", None) if settings is not None else None

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured. Please set a PostgreSQL connection string "
            "in app.core.config.settings."
        )

    return database_url


DATABASE_URL: str = _get_required_database_url()
MASTER_DATABASE_URL: Optional[str] = getattr(settings, "MASTER_DATABASE_URL", None) if settings else None

if not DATABASE_URL.startswith("postgresql"):
    raise RuntimeError(
        "Invalid DATABASE_URL for Carepoint HMS. "
        "This project is configured to use PostgreSQL."
    )


SQLALCHEMY_ECHO: bool = bool(getattr(settings, "SQLALCHEMY_ECHO", False)) if settings else False
DB_POOL_SIZE: int = int(getattr(settings, "DB_POOL_SIZE", 10)) if settings else 10
DB_MAX_OVERFLOW: int = int(getattr(settings, "DB_MAX_OVERFLOW", 20)) if settings else 20
DB_POOL_TIMEOUT: int = int(getattr(settings, "DB_POOL_TIMEOUT", 30)) if settings else 30
DB_POOL_RECYCLE: int = int(getattr(settings, "DB_POOL_RECYCLE", 1800)) if settings else 1800
DB_POOL_PRE_PING: bool = bool(getattr(settings, "DB_POOL_PRE_PING", True)) if settings else True
DB_ISOLATION_LEVEL: Optional[str] = getattr(settings, "DB_ISOLATION_LEVEL", None) if settings else None


_engine_kwargs: dict = {
    "echo": SQLALCHEMY_ECHO,
    "future": True,
    "pool_pre_ping": DB_POOL_PRE_PING,
    "pool_size": DB_POOL_SIZE,
    "max_overflow": DB_MAX_OVERFLOW,
    "pool_timeout": DB_POOL_TIMEOUT,
    "pool_recycle": DB_POOL_RECYCLE,
}

if DB_ISOLATION_LEVEL:
    _engine_kwargs["isolation_level"] = DB_ISOLATION_LEVEL


# Default engine and SessionLocal for script-level operations (non-tenant context)
engine: Engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# Cache for tenant engines
_tenant_engines: dict[str, Engine] = {}

def get_engine_for_url(url: str) -> Engine:
    """Return a cached engine for a given database URL."""
    if url not in _tenant_engines:
        _tenant_engines[url] = create_engine(url, **_engine_kwargs)
    return _tenant_engines[url]

def get_master_engine() -> Engine:
    """Return the master database engine."""
    master_url = settings.MASTER_DATABASE_URL or DATABASE_URL
    return get_engine_for_url(master_url)

from contextlib import contextmanager

@contextmanager
def get_master_db_context() -> Generator[Session, None, None]:
    """Provide a session for the master database."""
    engine = get_master_engine()
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()

def get_master_db() -> Generator[Session, None, None]:
    """FastAPI dependency providing a session to the master database."""
    engine = get_master_engine()
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.
    This session is bound to the current tenant's database.
    """
    tenant_db_url = get_current_tenant_db_url()
    
    if not tenant_db_url:
        # Fallback to master/default database if no tenant is set
        # (e.g. for registration or system routes)
        from app.core.logger import get_logger
        logger = get_logger(__name__)
        logger.warning("No tenant context found. Falling back to Master Database engine.")
        engine = get_master_engine()
    else:
        engine = get_engine_for_url(tenant_db_url)
        
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = session_factory()
    
    try:
        yield db
    except SQLAlchemyError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_session() -> Session:
    """
    Return a plain SQLAlchemy session instance for the current tenant.
    """
    tenant_db_url = get_current_tenant_db_url()
    if not tenant_db_url:
        engine = get_master_engine()
    else:
        engine = get_engine_for_url(tenant_db_url)
    
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return session_factory()


def get_engine() -> Engine:
    """
    Return the engine for the current tenant.
    """
    tenant_db_url = get_current_tenant_db_url()
    if not tenant_db_url:
        return get_master_engine()
    return get_engine_for_url(tenant_db_url)


def create_tables(bind_engine: Optional[Engine] = None, is_master: bool = False) -> None:
    """
    Create ORM tables registered in metadata.
    """
    # Ensure all models are imported so they register with metadata
    import app.models.all_models  # noqa: F401
    target_engine = bind_engine or engine
    if is_master:
        MasterBase.metadata.create_all(bind=target_engine)
    else:
        TenantBase.metadata.create_all(bind=target_engine)


def drop_tables(bind_engine: Optional[Engine] = None, is_master: bool = False) -> None:
    """
    Drop all ORM tables registered in metadata.
    """
    target_engine = bind_engine or engine
    from sqlalchemy import text
    with target_engine.connect() as conn:
        # Set a short lock timeout so we don't hang forever if there are zombie connections
        conn.execute(text("SET lock_timeout = '10s';"))
        
        # Attempt to kill other connections to this database to release locks.
        # This may fail if the user is not a superuser/owner, but we try anyway.
        try:
            conn.execute(text("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid();
            """))
            conn.commit()
        except Exception:
            conn.rollback() # Ignore failures here
            
        try:
            conn.execute(text("DROP SCHEMA public CASCADE;"))
            conn.execute(text("CREATE SCHEMA public;"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public;"))
            conn.commit()
        except Exception as e:
            conn.rollback()
            # Fallback: drop tables and types one by one, ignoring errors per item
            conn.execute(text("""
                DO $$ DECLARE
                    r RECORD;
                    v_schema TEXT := current_schema();
                BEGIN
                    -- Drop all tables
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = v_schema) LOOP
                        BEGIN
                            EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                        EXCEPTION WHEN OTHERS THEN
                            RAISE NOTICE 'Could not drop table %: %', r.tablename, SQLERRM;
                        END;
                    END LOOP;
                    
                    -- Drop all custom types (enums)
                    FOR r IN (
                        SELECT t.typname 
                        FROM pg_type t 
                        JOIN pg_namespace n ON n.oid = t.typnamespace 
                        WHERE n.nspname = v_schema 
                        AND t.typtype = 'e'
                    ) LOOP
                        BEGIN
                            EXECUTE 'DROP TYPE ' || quote_ident(r.typname) || ' CASCADE';
                        EXCEPTION WHEN OTHERS THEN
                            -- Ignore if it was already dropped by a previous CASCADE
                            NULL;
                        END;
                    END LOOP;
                END $$;
            """))
            conn.commit()


def check_database_connection() -> bool:
    """
    Check whether the application can connect to PostgreSQL.

    Returns
    -------
    bool
        True if the connection is healthy, otherwise False.
    """
    try:
        master_engine = get_master_engine()
        with master_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def check_database_connection_or_raise() -> None:
    """
    Validate the database connection and raise an explicit error if it fails.

    Raises
    ------
    RuntimeError
        If the application cannot connect to PostgreSQL.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError(f"Unable to connect to PostgreSQL database: {exc}") from exc



def dispose_engine() -> None:
    """
    Dispose the SQLAlchemy engine and its pool.

    Useful during graceful shutdown or certain test scenarios.
    """
    engine.dispose()