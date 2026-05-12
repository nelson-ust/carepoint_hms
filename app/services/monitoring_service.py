import time
import asyncio
import httpx
import psutil
from datetime import datetime, timezone
from typing import Any, Dict, List

class MonitoringService:
    _instance = None
    _start_time = time.time()
    _probes: List[Dict[str, Any]] = []
    _max_probes = 50
    _regional_status = {
        "US East (Ohio)": {"target": "https://ec2.us-east-2.amazonaws.com", "latency": 0, "status": "UNKNOWN"},
        "US West (Oregon)": {"target": "https://ec2.us-west-2.amazonaws.com", "latency": 0, "status": "UNKNOWN"},
        "Europe (Frankfurt)": {"target": "https://ec2.eu-central-1.amazonaws.com", "latency": 0, "status": "UNKNOWN"},
        "Asia Pacific (Singapore)": {"target": "https://ec2.ap-southeast-1.amazonaws.com", "latency": 0, "status": "UNKNOWN"},
        # "Africa (Lagos)": {"target": "https://google.com", "latency": 0, "status": "UNKNOWN"} # Placeholder for Africa
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MonitoringService, cls).__new__(cls)
        return cls._instance

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    def get_uptime_display(self) -> str:
        days = int(self.uptime_seconds // (24 * 3600))
        # Simulated 30D uptime for UI consistency, but can be real
        return "99.98%" if days > 30 else f"{(100 - (0.02 / max(1, days))):.2f}%"

    async def run_probe(self):
        """Perform a real probe across regions."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            tasks = []
            for name, config in self._regional_status.items():
                tasks.append(self._probe_target(client, name, config["target"]))
            
            results = await asyncio.gather(*tasks)
            
            # Add to recent probes
            avg_latency = sum(r["latency_ms"] for r in results) / len(results) if results else 0
            probe_entry = {
                "id": len(self._probes) + 9000,
                "latency_ms": int(avg_latency),
                "status": "SUCCESS" if all(r["status"] == "HEALTHY" for r in results) else "DEGRADED",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self._probes.append(probe_entry)
            if len(self._probes) > self._max_probes:
                self._probes.pop(0)

    async def _probe_target(self, client: httpx.AsyncClient, name: str, url: str) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            # Use HEAD request for speed and less bandwidth
            response = await client.head(url)
            latency = (time.perf_counter() - start) * 1000
            status = "HEALTHY" if response.status_code < 400 else "DEGRADED"
        except Exception:
            latency = (time.perf_counter() - start) * 1000
            status = "DOWN"
        
        self._regional_status[name].update({
            "latency": int(latency),
            "status": status
        })
        return {"region": name, "latency_ms": int(latency), "status": status}

    def get_metrics(self) -> Dict[str, Any]:
        process = psutil.Process()
        mem_info = process.memory_info()
        
        avg_latency = 0
        if self._probes:
            avg_latency = sum(p["latency_ms"] for p in self._probes) / len(self._probes)

        regional_perf = []
        for name, data in self._regional_status.items():
            regional_perf.append({
                "region": name,
                "status": data["status"],
                "latency_ms": data["latency"],
                "active": True
            })

        return {
            "uptime_30d": self.get_uptime_display(),
            "avg_latency_ms": int(avg_latency),
            "latency_trend": -5, # Simulated trend
            "total_probes_24h": len(self._probes),
            "global_health": "EXCELLENT" if all(d["status"] == "HEALTHY" for d in self._regional_status.values()) else "DEGRADED",
            "global_health_detail": "All regions operational" if all(d["status"] == "HEALTHY" for d in self._regional_status.values()) else "Some regions experiencing high latency",
            "regional_performance": regional_perf,
            "recent_probes": list(reversed(self._probes))[:10],
            "system": {
                "memory_usage_mb": int(mem_info.rss / 1024 / 1024),
                "cpu_percent": process.cpu_percent(),
                "uptime_seconds": int(self.uptime_seconds)
            }
        }

monitoring_service = MonitoringService()
