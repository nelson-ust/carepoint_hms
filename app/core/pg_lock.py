# app/core/pg_lock.py
from __future__ import annotations

"""
app.core.pg_lock

PostgreSQL advisory-lock helpers used to make background work
single-instance across a horizontally-scaled deployment.

Problem
-------
The scheduler (``app/scheduler.py``) is started inside the FastAPI lifespan.
When the API runs with more than one worker/replica (e.g. gunicorn/uvicorn
``--workers N`` or several Render instances), **every** worker starts its own
``BackgroundScheduler`` and therefore fires the same jobs at the same time.
That means duplicate backups, duplicate invoices, duplicate reminders.

Solution
--------
PostgreSQL *session-level advisory locks* give us a cheap, infrastructure-free
mutex that every worker can agree on through the shared master database.
``pg_try_advisory_lock(key)`` returns immediately: ``true`` if this connection
grabbed the lock, ``false`` if another connection already holds it. The lock is
held for as long as the owning connection keeps it (we release it explicitly,
and closing the connection releases it as a backstop).

A distinct lock key per job means different jobs still run concurrently across
workers — only the *same* job is serialised to a single runner at a time.

These helpers are PostgreSQL-specific (the project standardises on Postgres).
"""

import hashlib
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def advisory_key(name: str) -> int:
    """
    Derive a stable signed 64-bit integer key from an arbitrary name.

    ``pg_advisory_lock`` takes a ``bigint``; we hash the name to 8 bytes and
    interpret them as a signed integer so the same name always maps to the
    same key across workers and restarts.
    """
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


@contextmanager
def try_advisory_lock(engine: Engine, name: str) -> Generator[bool, None, None]:
    """
    Non-blocking advisory lock scoped to a single checked-out connection.

    Usage::

        with try_advisory_lock(get_master_engine(), "carepoint:scheduler:daily_backup") as locked:
            if not locked:
                return  # another worker is already running this job
            do_the_work()

    The context manager always yields a bool (``True`` iff this process now
    owns the lock) and guarantees the lock is released on exit. It never
    raises purely because the lock could not be acquired.
    """
    key = advisory_key(name)
    conn = engine.connect()
    acquired = False
    try:
        try:
            acquired = bool(
                conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}).scalar()
            )
        except Exception as exc:  # pragma: no cover - defensive
            # If the lock probe itself fails (e.g. master DB briefly
            # unavailable) we conservatively report "not acquired" so the
            # caller skips rather than risking a duplicate run.
            logger.warning("Advisory lock probe failed for %s: %s", name, exc)
            acquired = False
        yield acquired
    finally:
        if acquired:
            try:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
                conn.commit()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Advisory unlock failed for %s: %s", name, exc)
        try:
            conn.close()
        except Exception:  # pragma: no cover
            pass


def run_single_instance(engine: Engine, name: str, fn) -> bool:
    """
    Run ``fn()`` only if this process can grab the advisory lock ``name``.

    Returns ``True`` if the function ran, ``False`` if it was skipped because
    another instance held the lock. Exceptions raised by ``fn`` propagate to
    the caller (the scheduler wraps each job in its own ``_safe_*`` guard).
    """
    with try_advisory_lock(engine, name) as locked:
        if not locked:
            logger.debug("Job %s skipped — another instance holds the lock.", name)
            return False
        fn()
        return True
