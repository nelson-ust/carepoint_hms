import os
import sys

# Add the root project directory to the sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.config import settings
from app.models.base import MasterBase, TenantBase
import app.models.all_models  # Ensure all models are loaded

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# ---------------------------------------------------------------------------
# Target selection (master by default; tenant-aware via -x arguments).
#
# Alembic historically pointed at the master database. Tenant tables (the vast
# majority of the schema — billing, HR, clinical, etc.) live in per-tenant
# databases, so to run a migration against a tenant you pass its URL:
#
#     alembic -x db_url="postgresql://…/tenant_db" upgrade head
#
# Combine with app.db_sync.iter_tenant_targets() in a shell loop to migrate the
# whole fleet with per-tenant isolation. When no -x db_url is given the
# behaviour is unchanged (master database, master metadata).
# ---------------------------------------------------------------------------
_x_args = context.get_x_argument(as_dictionary=True)
_override_url = _x_args.get("db_url")

db_url = _override_url or settings.MASTER_DATABASE_URL or settings.DATABASE_URL
# Escape % signs (e.g. in an encoded password) for ConfigParser.
config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))

# Metadata: tenant DBs carry TenantBase tables; the master DB carries
# MasterBase tables. Default to tenant metadata whenever a tenant URL is
# supplied, unless the caller overrides with -x metadata=master|tenant.
_meta_choice = _x_args.get("metadata")
if _meta_choice == "tenant":
    target_metadata = TenantBase.metadata
elif _meta_choice == "master":
    target_metadata = MasterBase.metadata
elif _override_url:
    target_metadata = TenantBase.metadata
else:
    target_metadata = MasterBase.metadata

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no DBAPI needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against the resolved database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
