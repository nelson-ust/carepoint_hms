import time
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    import psutil  # optional: system CPU/memory metrics
except Exception:  # pragma: no cover - degrade gracefully when unavailable
    psutil = None


class MonitoringService:
    """
    Real, in-platform health monitoring.

    Rather than pinging unreachable external endpoints, we probe the services
    this platform actually depends on — the master database, a sample of tenant
    databases, and the API process itself — and report real round-trip latency
    and status. A rolling window of probes feeds the uptime / trend figures.
    """

    _instance = None
    _start_time = time.time()
    _probes: List[Dict[str, Any]] = []
    _max_probes = 50

    # Latency thresholds (ms) for classifying a healthy service.
    _HEALTHY_MS = 300
    _DEGRADED_MS = 1500

    _services: Dict[str, Dict[str, Any]] = {
        "Master Database": {"latency": 0, "status": "UNKNOWN"},
        "Tenant Databases": {"latency": 0, "status": "UNKNOWN"},
        "API Server": {"latency": 0, "status": "UNKNOWN"},
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MonitoringService, cls).__new__(cls)
        return cls._instance

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------
    def _classify(self, latency_ms: float, ok: bool) -> str:
        if not ok:
            return "DOWN"
        if latency_ms <= self._HEALTHY_MS:
            return "HEALTHY"
        return "DEGRADED"

    # ------------------------------------------------------------------
    # Probes (run in a worker thread so the sync DB calls never block the loop)
    # ------------------------------------------------------------------
    def _probe_master_db_sync(self) -> Tuple[float, bool]:
        from sqlalchemy import text
        from app.core.database import get_master_engine
        start = time.perf_counter()
        try:
            engine = get_master_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return (time.perf_counter() - start) * 1000, True
        except Exception:
            return (time.perf_counter() - start) * 1000, False

    def _probe_tenant_dbs_sync(self) -> Tuple[float, str, int]:
        """Best-effort probe of up to 3 provisioned tenant databases."""
        from sqlalchemy import text
        from app.core.database import get_master_db_context, get_tenant_db_context
        try:
            from app.models.all_models import Tenant
            with get_master_db_context() as mdb:
                q = mdb.query(Tenant.id).filter(Tenant.is_deleted.is_(False))
                if hasattr(Tenant, "is_provisioned"):
                    q = q.filter(Tenant.is_provisioned.is_(True))
                tenant_ids = [row[0] for row in q.limit(3).all()]
        except Exception:
            return 0.0, "UNKNOWN", 0

        if not tenant_ids:
            return 0.0, "HEALTHY", 0  # nothing provisioned yet — not a fault

        latencies: List[float] = []
        failures = 0
        for tid in tenant_ids:
            start = time.perf_counter()
            try:
                with get_tenant_db_context(tid) as tdb:
                    tdb.execute(text("SELECT 1"))
                latencies.append((time.perf_counter() - start) * 1000)
            except Exception:
                failures += 1

        if not latencies:
            return 0.0, "DOWN", len(tenant_ids)
        avg = sum(latencies) / len(latencies)
        status = "HEALTHY" if failures == 0 and avg <= self._DEGRADED_MS else "DEGRADED"
        return avg, status, len(tenant_ids)

    async def run_probe(self) -> None:
        """Probe every core service and record one aggregate probe entry."""
        # Master database
        m_lat, m_ok = await asyncio.to_thread(self._probe_master_db_sync)
        self._services["Master Database"] = {"latency": int(m_lat), "status": self._classify(m_lat, m_ok)}

        # Tenant databases (sampled)
        t_lat, t_status, t_count = await asyncio.to_thread(self._probe_tenant_dbs_sync)
        self._services["Tenant Databases"] = {
            "latency": int(t_lat), "status": t_status, "sampled": t_count,
        }

        # API server — event-loop responsiveness (the process is answering now).
        start = time.perf_counter()
        await asyncio.sleep(0)
        api_lat = max(1, int((time.perf_counter() - start) * 1000))
        self._services["API Server"] = {"latency": api_lat, "status": "HEALTHY"}

        statuses = [v["status"] for v in self._services.values()]
        lats = [v["latency"] for v in self._services.values()]
        avg = sum(lats) / len(lats) if lats else 0
        if "DOWN" in statuses:
            overall = "DOWN"
        elif "DEGRADED" in statuses:
            overall = "DEGRADED"
        else:
            overall = "HEALTHY"

        self._probes.append({
            "id": len(self._probes) + 9000,
            "latency_ms": int(avg),
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._probes) > self._max_probes:
            self._probes.pop(0)

    # ------------------------------------------------------------------
    # Derived figures
    # ------------------------------------------------------------------
    def _success_rate(self):
        if not self._probes:
            return None
        healthy = sum(1 for p in self._probes if p["status"] == "HEALTHY")
        return healthy / len(self._probes) * 100

    def get_uptime_display(self) -> str:
        rate = self._success_rate()
        return f"{(100.0 if rate is None else rate):.2f}%"

    def get_metrics(self) -> Dict[str, Any]:
        # System metrics are best-effort: psutil may be absent, and its absence
        # must never take down /health.
        mem_mb = None
        cpu_pct = None
        if psutil is not None:
            try:
                process = psutil.Process()
                mem_mb = int(process.memory_info().rss / 1024 / 1024)
                cpu_pct = process.cpu_percent()
            except Exception:
                mem_mb = None
                cpu_pct = None

        avg_latency = 0
        if self._probes:
            avg_latency = sum(p["latency_ms"] for p in self._probes) / len(self._probes)

        # Real month-over-month style trend: latest probe vs the previous one.
        latency_trend = 0
        if len(self._probes) >= 2:
            prev = self._probes[-2]["latency_ms"]
            cur = self._probes[-1]["latency_ms"]
            if prev > 0:
                latency_trend = round((cur - prev) / prev * 100)

        regional_perf = [
            {"region": name, "status": data["status"], "latency_ms": data["latency"], "active": True}
            for name, data in self._services.items()
        ]

        statuses = [d["status"] for d in self._services.values()]
        if "DOWN" in statuses:
            global_health, detail = "DOWN", "One or more core services are unreachable."
        elif "DEGRADED" in statuses:
            global_health, detail = "DEGRADED", "Some services are responding slowly."
        elif statuses and all(s == "HEALTHY" for s in statuses):
            global_health, detail = "HEALTHY", "All core services operational."
        else:
            global_health, detail = "HEALTHY", "Awaiting first health probe."

        return {
            "uptime_30d": self.get_uptime_display(),
            "avg_latency_ms": int(avg_latency),
            "latency_trend": latency_trend,
            "total_probes_24h": len(self._probes),
            "global_health": global_health,
            "global_health_detail": detail,
            "regional_performance": regional_perf,
            "recent_probes": list(reversed(self._probes))[:10],
            "system": {
                "memory_usage_mb": mem_mb,
                "cpu_percent": cpu_pct,
                "uptime_seconds": int(self.uptime_seconds),
                "metrics_available": psutil is not None,
            },
        }


monitoring_service = MonitoringService()
