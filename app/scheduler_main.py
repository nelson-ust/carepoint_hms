# app/scheduler_main.py
from __future__ import annotations

"""
Standalone scheduler process.

Run the background scheduler in its own process instead of inside the web
workers::

    python -m app.scheduler_main

Recommended deployment (e.g. Render)
------------------------------------
* Web service:      ``ENABLE_SCHEDULER=false`` — serve HTTP only, any number
                    of workers/replicas.
* Scheduler worker: a single instance running ``python -m app.scheduler_main``.

This process starts the scheduler unconditionally (it does not consult
``ENABLE_SCHEDULER`` — running it *is* the opt-in) and keeps running until it
receives SIGINT/SIGTERM, at which point it shuts the scheduler down cleanly.

Even if a web worker is accidentally left with ``ENABLE_SCHEDULER=true``, the
per-job PostgreSQL advisory locks (see ``app/scheduler.py`` /
``app/core/pg_lock.py``) guarantee each job still runs on only one instance —
so this process is safe to add without having to perfectly coordinate flags.
"""

import signal
import threading

from app.core.logger import get_logger

logger = get_logger(__name__)


def _sync_schemas_best_effort() -> None:
    """
    Forward-migrate master + tenant schemas before ticking, mirroring the API
    lifespan. This makes the scheduler process self-sufficient: new columns
    (e.g. the scheduling metadata on ``tenant_scheduled_job``) are present even
    if this process happens to start before the web service has synced.
    """
    try:
        from app.db_sync import sync_master_schema

        summary = sync_master_schema()
        if summary:
            logger.info("[scheduler_main] Master schema sync applied: %s", summary)
    except Exception as exc:  # pragma: no cover - best effort
        logger.exception("[scheduler_main] sync_master_schema failed: %s", exc)

    try:
        from app.db_sync import sync_tenant_schemas_all

        results = sync_tenant_schemas_all()
        ok = sum(1 for v in results.values() if isinstance(v, dict))
        failed = sum(
            1 for v in results.values() if isinstance(v, str) and v.startswith("error")
        )
        logger.info(
            "[scheduler_main] Tenant schema sync complete: ok=%s failed=%s total=%s",
            ok,
            failed,
            len(results),
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.exception("[scheduler_main] sync_tenant_schemas_all failed: %s", exc)


def main() -> None:
    from app.scheduler import shutdown_scheduler, start_scheduler

    stop = threading.Event()

    def _handle(signum, _frame):
        logger.info("[scheduler_main] Received signal %s; shutting down.", signum)
        stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    _sync_schemas_best_effort()

    logger.info("[scheduler_main] Starting standalone scheduler process.")
    start_scheduler()
    try:
        # BackgroundScheduler runs its jobs on worker threads; keep the main
        # thread parked until a shutdown signal arrives.
        stop.wait()
    finally:
        shutdown_scheduler()
        logger.info("[scheduler_main] Scheduler process stopped.")


if __name__ == "__main__":
    main()
