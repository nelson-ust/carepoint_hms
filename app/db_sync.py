"""
app.db_sync

Lightweight, idempotent schema migrator for PostgreSQL.

Why this exists
---------------
``MasterBase.metadata.create_all()`` only creates tables that don't yet
exist; it does **not** add columns to tables that already do. After
adding new fields to existing models (e.g. ``SubscriptionPlan.trial_days``,
``Tenant.billing_email``) you would otherwise need a real migration tool
to bring an existing database forward.

This module adds the two operations needed in practice:

* ``sync_schema(metadata, engine, ...)`` — for every table in
  ``metadata`` that already exists in the database, add any model columns
  that are missing using ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS``.
  New tables and new enum types are created via ``metadata.create_all``.

* ``extend_enum(engine, name, values)`` — append values to an
  already-installed PostgreSQL ``ENUM`` type.

Both functions are PostgreSQL-specific (the project standardises on
PostgreSQL) and safe to run multiple times. They are intentionally
conservative: when SQLAlchemy declares a NOT NULL column without a
server-side default, the helper falls back to NULLABLE so the ALTER
succeeds against tables that already contain rows. Operators can later
back-fill values and tighten the constraint with Alembic.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from sqlalchemy import MetaData, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn
from sqlalchemy.sql.sqltypes import Enum as SAEnum


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ENUM helpers
# ---------------------------------------------------------------------------


def _existing_enum_values(engine: Engine, type_name: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT e.enumlabel
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = :n
                """
            ),
            {"n": type_name},
        ).fetchall()
    return {r[0] for r in rows}


def _enum_type_exists(engine: Engine, type_name: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM pg_type WHERE typname = :n"),
            {"n": type_name},
        ).first()
    return row is not None


def extend_enum(engine: Engine, type_name: str, values: Iterable[str]) -> list[str]:
    """
    Add ``values`` to an installed PostgreSQL ``ENUM`` type. Existing
    values are skipped so the call is idempotent.

    ``ALTER TYPE ... ADD VALUE`` cannot run inside a transaction in old
    PostgreSQL versions, so we open an AUTOCOMMIT-style connection.

    Returns the list of values actually added (useful for logging).
    """
    if not _enum_type_exists(engine, type_name):
        # Nothing to do — the type will be created when the new column or
        # table that needs it is created via metadata.create_all().
        return []

    have = _existing_enum_values(engine, type_name)
    to_add = [v for v in values if v not in have]
    if not to_add:
        return []

    raw = engine.execution_options(isolation_level="AUTOCOMMIT")
    with raw.connect() as conn:
        for v in to_add:
            safe = v.replace("'", "''")
            conn.execute(text(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{safe}'"))
    logger.info("Schema sync: extended enum %s with %s", type_name, to_add)
    return to_add


# ---------------------------------------------------------------------------
# Column helpers
# ---------------------------------------------------------------------------


def _render_default(column) -> Optional[str]:
    """
    Return a ``DEFAULT <literal>`` clause string for ``column``, or
    ``None`` when no server-side default can be reliably emitted.

    ``column.default`` is a Python-side default in SQLAlchemy by default
    (it runs in the session, not in PG). We translate the most common
    literal shapes to a real ``DEFAULT`` so adding a NOT NULL column to a
    populated table doesn't fail.
    """
    if column.server_default is not None:
        # CreateColumn already includes server-side defaults; skip ours.
        return None
    if column.default is None:
        return None
    arg = getattr(column.default, "arg", None)
    if arg is None or callable(arg):
        return None
    if isinstance(arg, bool):
        return f"DEFAULT {'true' if arg else 'false'}"
    if isinstance(arg, (int, float)):
        return f"DEFAULT {arg}"
    if hasattr(arg, "value") and isinstance(getattr(arg, "value"), str):
        # Enum instance: use its string value.
        safe = arg.value.replace("'", "''")
        return f"DEFAULT '{safe}'"
    if isinstance(arg, str):
        safe = arg.replace("'", "''")
        return f"DEFAULT '{safe}'"
    return None


def _ensure_enum_type_for_column(engine: Engine, column) -> None:
    """
    Make sure the PostgreSQL ENUM type behind ``column.type`` exists.

    Needed when we ALTER an existing table to add a column whose type is
    a brand-new SQLAlchemy ``Enum``. Without this, the ``ADD COLUMN``
    statement would reference a type that's not yet installed.
    """
    col_type = column.type
    if not isinstance(col_type, SAEnum):
        return
    try:
        col_type.create(bind=engine, checkfirst=True)
    except Exception as exc:
        logger.warning(
            "Could not pre-create enum type for column %s.%s: %s",
            column.table.name if column.table is not None else "?",
            column.name,
            exc,
        )


def _add_missing_columns_for_table(
    engine: Engine,
    table,
    *,
    existing_cols: Optional[set[str]] = None,
    conn=None,
) -> list[str]:
    """
    Compare the table's model columns to what's actually in the DB and
    issue ``ALTER TABLE ADD COLUMN IF NOT EXISTS`` for any that are
    missing. Returns the list of columns that were added.

    Performance
    -----------
    The caller may pass a pre-fetched ``existing_cols`` set to avoid an
    inspector round trip per table (the inspector translates to a
    ``pg_catalog`` query, which is expensive over high-latency links —
    230+ tenant tables × ~150ms = a 30-second stall otherwise). The
    caller may also pass an open ``conn`` so the ALTER TABLE statements
    reuse the same connection.
    """
    if existing_cols is None:
        inspector = inspect(engine)
        if not inspector.has_table(table.name):
            return []
        existing_cols = {col["name"] for col in inspector.get_columns(table.name)}

    added: list[str] = []

    for column in table.columns:
        if column.name in existing_cols:
            continue

        _ensure_enum_type_for_column(engine, column)

        # Render the column DDL using SQLAlchemy's compiler so types
        # (Numeric, JSON, Enum, etc.) come out exactly as the model
        # declares them. CreateColumn emits ``name TYPE [NULL|NOT NULL]
        # [DEFAULT ...]`` without ``ALTER TABLE`` wrapping.
        col_ddl = str(CreateColumn(column).compile(dialect=engine.dialect)).strip()

        # If the column is NOT NULL and has no server_default, fall back
        # to a synthesised DEFAULT (when we can derive one) — otherwise
        # add the column as NULLABLE so the ALTER works against a
        # populated table. The model still enforces NOT NULL at write
        # time via the Python-side default.
        default_clause = _render_default(column)

        if not column.nullable and column.server_default is None:
            if default_clause:
                # Inject the DEFAULT into the DDL after the type spec.
                if "DEFAULT" not in col_ddl.upper():
                    # Strip the trailing ``NOT NULL`` so we can put DEFAULT
                    # before it (PostgreSQL accepts either order, but this
                    # keeps the SQL readable).
                    col_ddl = col_ddl.replace("NOT NULL", "").rstrip()
                    col_ddl = f"{col_ddl} {default_clause} NOT NULL"
            else:
                # Drop the NOT NULL qualifier so the ALTER works.
                col_ddl = col_ddl.replace("NOT NULL", "").rstrip()
                logger.warning(
                    "Schema sync: %s.%s declared NOT NULL without a server "
                    "default; adding as NULLABLE so existing rows are "
                    "preserved. Back-fill and tighten the constraint via "
                    "Alembic if required.",
                    table.name,
                    column.name,
                )

        sql = f'ALTER TABLE "{table.name}" ADD COLUMN IF NOT EXISTS {col_ddl}'
        logger.info("Schema sync: %s", sql)
        if conn is not None:
            conn.execute(text(sql))
        else:
            with engine.begin() as own_conn:
                own_conn.execute(text(sql))
        added.append(column.name)

    return added


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def sync_schema(
    metadata: MetaData,
    engine: Engine,
    *,
    enum_extensions: Optional[dict[str, Iterable[str]]] = None,
) -> dict[str, list[str]]:
    """
    Bring an existing PostgreSQL database in line with ``metadata``.

    Steps:
      1. Extend any pre-existing ENUM types listed in ``enum_extensions``
         with new values.
      2. Run ``metadata.create_all(...)`` so brand-new tables and
         brand-new enum types are installed.
      3. For every *pre-existing* table, add any model column that is
         missing.

    Performance notes
    -----------------
    The earlier implementation made one inspector call per table and
    one autocommit transaction per ALTER. With ~90 tenant tables and a
    ~150ms RTT to a remote managed Postgres, that translated into 30+
    seconds of pure round trips on top of the ~80 CREATE TABLE calls
    issued by ``create_all``. We now:

    * read ``pg_tables`` once to learn which tables already exist;
    * skip the entire column-back-fill loop when the database is
      brand-new (fresh tenant DB → ``create_all`` already produced
      every column at the right shape);
    * read ``information_schema.columns`` once for the surviving
      tables instead of issuing one inspector call per table;
    * pass ``checkfirst=False`` to ``metadata.create_all`` when we
      detected the DB is fresh, which halves the round trips that
      ``create_all`` itself emits.

    These changes shave the tenant-provisioning step from
    multiple minutes down to a few seconds even over a high-latency
    link.

    Returns a per-table dict of the columns that were added so callers
    can log a single tidy summary.
    """
    summary: dict[str, list[str]] = {}

    # 1. Extend existing enums.
    for name, values in (enum_extensions or {}).items():
        added_values = extend_enum(engine, name, values)
        if added_values:
            summary[f"enum:{name}"] = added_values

    # 2. Pre-create new enum types using idempotent DO blocks.
    # This prevents UniqueViolation if SQLAlchemy's checkfirst=True fails.
    from sqlalchemy.sql.sqltypes import Enum as SAEnum
    found_enums: set = set()
    for table in metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, SAEnum) and column.type.native_enum:
                found_enums.add(column.type)

    # 3. Single connection for the rest of the sync — keeps DDL on the
    # same backend and amortises the network round trips.
    with engine.connect() as conn:
        # 3a. Detect schema "freshness" up front. This is one round trip
        # instead of one per table.
        schema_clause = (
            "current_schema()" if not _has_search_path_override(engine) else "ANY (current_schemas(false))"
        )
        try:
            existing_tables = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        f"WHERE schemaname = {schema_clause}"
                    )
                )
            }
        except Exception:
            # Fall back to the inspector (also one trip, but more compatible).
            existing_tables = set(inspect(engine).get_table_names())

        is_fresh_db = len(existing_tables) == 0

        # 3b. On a non-fresh DB we may have leftover enum types from a
        # previous incarnation of this schema (a partial migration, a
        # dropped-but-not-clean rebuild, etc.). Pre-create them with
        # idempotent DO blocks so the upcoming ``create_all`` doesn't
        # trip on "type already exists" (SQLAlchemy's checkfirst probe
        # for an enum is "is there a pg_type row" — it can be True
        # while the table that referenced it has been dropped).
        #
        # We deliberately *skip* this step on a fresh DB: SQLAlchemy
        # will own enum creation during ``create_all`` and pre-creating
        # here would just add a redundant round trip per enum.
        if not is_fresh_db:
            for enum_type in found_enums:
                vals = ", ".join("'" + v.replace("'", "''") + "'" for v in enum_type.enums)
                sql = (
                    "DO $$ BEGIN "
                    f"CREATE TYPE {enum_type.name} AS ENUM ({vals}); "
                    "EXCEPTION WHEN duplicate_object THEN null; END $$;"
                )
                conn.execute(text(sql))
            conn.commit()

    # 3c. Create all tables. We always pass ``checkfirst=True`` because:
    #   * non-fresh DB: existing types/tables must be skipped;
    #   * fresh DB: a single metadata can register the *same* PG enum
    #     under multiple columns/tables. With ``checkfirst=False``
    #     SQLAlchemy attempts CREATE TYPE for each occurrence and
    #     trips on the second one with ``DuplicateObject``.
    # ``checkfirst=True`` issues one ``pg_class`` lookup per table —
    # one round trip apiece — which is still much cheaper than the
    # per-table column inspection we eliminate below.
    metadata.create_all(bind=engine, checkfirst=True)

    # 3d. Skip the column-add loop entirely when the DB was fresh —
    # ``create_all`` just produced every column at the right shape.
    if is_fresh_db:
        return summary

    # 3e. For pre-existing tables, fetch all columns in one go from
    # information_schema instead of one inspector call per table.
    columns_by_table: dict[str, set[str]] = {}
    try:
        with engine.connect() as conn:
            schema_clause = (
                "current_schema()"
                if not _has_search_path_override(engine)
                else "ANY (current_schemas(false))"
            )
            rows = conn.execute(
                text(
                    "SELECT table_name, column_name "
                    "FROM information_schema.columns "
                    f"WHERE table_schema = {schema_clause}"
                )
            )
            for tbl, col in rows:
                columns_by_table.setdefault(tbl, set()).add(col)
    except Exception as exc:
        logger.warning(
            "Schema sync: bulk column-fetch failed (%s); falling back to "
            "per-table inspection.",
            exc,
        )

    # 3f. Issue ALTER TABLE for every missing column on a single
    # autocommit connection.
    with engine.begin() as alter_conn:
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # newly created by step 3c — already complete
            existing_cols = columns_by_table.get(table.name)
            added = _add_missing_columns_for_table(
                engine,
                table,
                existing_cols=existing_cols,
                conn=alter_conn,
            )
            if added:
                summary[table.name] = added

    return summary


def _has_search_path_override(engine: Engine) -> bool:
    """
    Detect whether the engine URL includes a custom ``search_path`` (the
    schema-per-tenant fallback used on managed Postgres). When it does,
    table existence checks must look across all visible schemas — not
    just ``current_schema()``.
    """
    try:
        opts = engine.url.query.get("options") or ""
    except Exception:
        return False
    return "search_path" in str(opts)


def sync_master_schema(engine: Engine | None = None) -> dict[str, list[str]]:
    """
    Convenience wrapper that targets the Master metadata.
    """
    from app.core.database import MASTER_DATABASE_URL, get_master_engine
    from app.models.base import MasterBase

    if engine is None:
        if not MASTER_DATABASE_URL:
            logger.warning("MASTER_DATABASE_URL not set; sync_master_schema skipped.")
            return {}
        engine = get_master_engine()

    enum_extensions = _master_enum_extensions()
    
    # Check for pollution (tenant tables in master DB)
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        master_tables = set(MasterBase.metadata.tables.keys())
        unexpected = existing_tables - master_tables
        if unexpected:
            logger.warning(
                "POLLUTION DETECTED in Master Database! Found %d unexpected tables "
                "(e.g. %s). These likely leaked from a misconfigured tenant sync. "
                "Run `python -m app.init_db` for a destructive reset to clean this up.",
                len(unexpected), list(unexpected)[:5]
            )
    except Exception as exc:
        logger.warning("Could not audit master database for pollution: %s", exc)

    return sync_schema(MasterBase.metadata, engine, enum_extensions=enum_extensions)


def sync_tenant_schema(db_url: str) -> dict[str, list[str]]:
    """
    Convenience wrapper that targets the Tenant metadata for ``db_url``.

    Use this to forward-migrate one tenant database. The companion helper
    :func:`app.services.tenant_service.TenantService.run_migrations_all_tenants`
    iterates every active tenant and calls this for each.

    The engine here uses a short ``connect_timeout`` so a managed-Postgres
    handshake that quietly stalls fails fast instead of locking the API
    request for the full TCP timeout (~75s on Linux).
    """
    from sqlalchemy import create_engine

    from app.models.base import TenantBase

    engine = create_engine(
        db_url,
        future=True,
        pool_pre_ping=False,
        connect_args={"connect_timeout": 10},
    )
    try:
        enum_extensions = _tenant_enum_extensions()
        return sync_schema(TenantBase.metadata, engine, enum_extensions=enum_extensions)
    finally:
        engine.dispose()


def _is_missing_db_error(exc: BaseException) -> bool:
    """
    Detect the PostgreSQL "database does not exist" error.

    psycopg2 raises ``OperationalError`` with a message that mentions
    ``does not exist`` and the SQLSTATE class ``3D000``. Either signal
    is enough for us to treat the tenant as "needs (re-)provisioning"
    rather than crash the rest of the sync run.

    The check walks the exception chain (``__cause__`` + ``__context__``)
    so wrapped errors are caught even when SQLAlchemy reformats the
    ``str()`` representation.
    """
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        msg = str(cur) or ""
        # Match a wide net of phrasings ("database X does not exist",
        # "FATAL: database ... does not exist", etc.).
        lowered = msg.lower()
        if "does not exist" in lowered and ("database" in lowered or "fatal" in lowered):
            return True
        pgcode = getattr(getattr(cur, "orig", None), "pgcode", None) or getattr(cur, "pgcode", None)
        if pgcode == "3D000":  # invalid_catalog_name
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def _tenant_db_reachable(url: str) -> tuple[bool, str | None]:
    """
    Lightweight pre-flight probe that opens a single connection and runs
    ``SELECT 1``. Returns ``(reachable, reason)``. ``reason`` is
    ``"missing"`` when the physical database does not exist, or a short
    error string for any other failure (network, auth, …).
    """
    from sqlalchemy import create_engine, text

    engine = create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        if _is_missing_db_error(exc):
            return False, "missing"
        return False, str(exc)[:200]
    finally:
        try:
            engine.dispose()
        except Exception:
            pass


def _demote_stale_tenant(master_db, tenant, reason: str) -> None:
    """
    Mark a tenant whose DB has gone missing as un-provisioned so it is
    excluded from subsequent sync ticks until an admin re-provisions
    via ``POST /api/v1/tenants/{tenant_id}/approve``.
    """
    try:
        from app.core.enums import UserStatus

        tenant.is_provisioned = False
        tenant.status = UserStatus.PENDING
        master_db.commit()
        logger.warning(
            "Tenant %s demoted to PENDING / unprovisioned (DB missing: %s). "
            "Re-approve via POST /api/v1/tenants/%s/approve to recreate it.",
            tenant.code,
            reason,
            tenant.id,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not demote stale tenant %s: %s", tenant.code, exc)


def sync_tenant_schemas_all() -> dict[str, dict[str, list[str]] | str]:
    """
    Walk every active, provisioned tenant in master and forward-migrate
    each tenant's database in turn.

    Returns a mapping ``{tenant_code: summary | error_message}`` so the
    caller can log a single tidy line per process boot. Failures for one
    tenant never abort the rest.

    Stale tenants (master row says ``is_provisioned=True`` but the
    physical PostgreSQL database has gone missing) are demoted to
    ``is_provisioned=False`` + ``status=PENDING`` so subsequent runs
    skip them cleanly until a SaaS admin re-approves the tenant.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.core.cryptography import decrypt_string
    from app.core.database import MASTER_DATABASE_URL
    from app.models.all_models import Tenant
    from app.services.tenant_job_runner import reset_table_presence_cache

    if not MASTER_DATABASE_URL:
        logger.warning("MASTER_DATABASE_URL not set; sync_tenant_schemas_all skipped.")
        return {}

    out: dict[str, dict[str, list[str]] | str] = {}
    master_engine = create_engine(MASTER_DATABASE_URL, future=True)
    try:
        tenant_targets = []
        with Session(master_engine) as master_db:
            tenants = (
                master_db.query(Tenant)
                .filter(
                    Tenant.is_active.is_(True),
                    Tenant.is_provisioned.is_(True),
                    Tenant.is_deleted.is_(False),
                )
                .all()
            )
            for tenant in tenants:
                if not tenant.db_connection_string:
                    out[tenant.code] = "skipped: no db_connection_string"
                    continue
                try:
                    url = decrypt_string(tenant.db_connection_string)
                except Exception:
                    url = tenant.db_connection_string
                tenant_targets.append((tenant.id, tenant.code, url))

        for tenant_id, tenant_code, url in tenant_targets:
            # Pre-flight probe: confirm the tenant database is
            # reachable BEFORE we try to migrate it.
            reachable, reason = _tenant_db_reachable(url)
            if not reachable:
                if reason == "missing":
                    out[tenant_code] = (
                        "skipped: tenant database is missing — "
                        "re-approve to recreate (POST /api/v1/tenants/{id}/approve)"
                    )
                    with Session(master_engine) as master_db:
                        tenant = master_db.query(Tenant).get(tenant_id)
                        if tenant:
                            _demote_stale_tenant(
                                master_db,
                                tenant,
                                reason="physical PostgreSQL database missing",
                            )
                else:
                    logger.warning(
                        "Tenant %s sync skipped: database unreachable (%s)",
                        tenant_code,
                        reason,
                    )
                    out[tenant_code] = f"skipped: database unreachable ({reason})"
                continue

            try:
                summary = sync_tenant_schema(url)
                out[tenant_code] = summary or {}
            except Exception as exc:
                # Defensive second pass
                if _is_missing_db_error(exc):
                    out[tenant_code] = (
                        "skipped: tenant database is missing — re-approve to recreate"
                    )
                    with Session(master_engine) as master_db:
                        tenant = master_db.query(Tenant).get(tenant_id)
                        if tenant:
                            _demote_stale_tenant(
                                master_db,
                                tenant,
                                reason="physical PostgreSQL database missing",
                            )
                    continue
                logger.exception("Schema sync failed for tenant %s: %s", tenant_code, exc)
                out[tenant_code] = f"error: {exc}"
    finally:
        master_engine.dispose()

    # Newly-migrated tables become visible immediately to the tenant-job
    # dispatcher.
    try:
        reset_table_presence_cache()
    except Exception:
        pass
    return out


def heal_stale_tenants() -> dict[str, str]:
    """
    Walk every ``is_provisioned=True`` tenant, probe its physical
    database with a one-off connection, and demote any whose database
    has gone missing.

    Returns ``{tenant_code: outcome}`` so CLI callers can render a
    summary. Outcomes:

    * ``"ok"``       — DB exists and is reachable.
    * ``"demoted"``  — DB missing; row demoted to PENDING.
    * ``"unreachable: ..."`` — connection failed for some other reason
      (network, auth, etc.); the row is NOT demoted.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from app.core.cryptography import decrypt_string
    from app.core.database import MASTER_DATABASE_URL
    from app.models.all_models import Tenant

    if not MASTER_DATABASE_URL:
        return {}

    out: dict[str, str] = {}
    master_engine = create_engine(MASTER_DATABASE_URL, future=True)
    try:
        with Session(master_engine) as master_db:
            tenants = (
                master_db.query(Tenant)
                .filter(
                    Tenant.is_provisioned.is_(True),
                    Tenant.is_deleted.is_(False),
                )
                .all()
            )
            for tenant in tenants:
                if not tenant.db_connection_string:
                    out[tenant.code] = "skipped: no db_connection_string"
                    continue
                try:
                    url = decrypt_string(tenant.db_connection_string)
                except Exception:
                    url = tenant.db_connection_string

                probe = create_engine(url, future=True)
                try:
                    with probe.connect() as conn:
                        conn.execute(text("SELECT 1"))
                    out[tenant.code] = "ok"
                except Exception as exc:
                    if _is_missing_db_error(exc):
                        _demote_stale_tenant(
                            master_db,
                            tenant,
                            reason="physical PostgreSQL database missing",
                        )
                        out[tenant.code] = "demoted"
                    else:
                        out[tenant.code] = f"unreachable: {str(exc)[:140]}"
                finally:
                    probe.dispose()
    finally:
        master_engine.dispose()
    return out


# ---------------------------------------------------------------------------
# Known enum extensions
# ---------------------------------------------------------------------------


def _master_enum_extensions() -> dict[str, list[str]]:
    """
    Enum value additions known to apply to the master database.

    Add new entries here as the model evolves.
    """
    return {
        # No master-only enum has gained new values in this release.
    }


def _tenant_enum_extensions() -> dict[str, list[str]]:
    """
    Enum value additions known to apply to every tenant database.
    """
    return {
        # PaymentMethod gained FLUTTERWAVE + STRIPE.
        # PostgreSQL stores enum types in lower-case unless quoted;
        # SQLAlchemy's default naming is the lower-cased class name.
        "paymentmethod": ["FLUTTERWAVE", "STRIPE"],
    }
