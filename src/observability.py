"""Thread-safe latency/error metrics for API, inference, and repository operations."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        self._requests: Dict[str, int] = defaultdict(int)
        self._failures: Dict[str, int] = defaultdict(int)

    def record(self, name: str, latency_ms: float, failed: bool = False) -> None:
        with self._lock:
            values = self._latencies[name]
            values.append(round(float(latency_ms), 6))
            if len(values) > 10_000:
                del values[: len(values) - 10_000]
            self._requests[name] += 1
            if failed:
                self._failures[name] += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            result: Dict[str, Any] = {}
            for name, values in self._latencies.items():
                ordered = sorted(values)
                p95_index = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
                result[name] = {
                    "count": self._requests[name],
                    "failures": self._failures[name],
                    "mean_ms": round(sum(values) / len(values), 6) if values else 0.0,
                    "p95_ms": ordered[p95_index] if ordered else 0.0,
                    "max_ms": max(values) if values else 0.0,
                }
            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "operations": result,
            }

    def timer(self, name: str) -> "MetricTimer":
        return MetricTimer(self, name)


class MetricTimer:
    def __init__(self, registry: MetricsRegistry, name: str) -> None:
        self.registry = registry
        self.name = name
        self.started = 0.0

    def __enter__(self) -> "MetricTimer":
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        self.registry.record(
            self.name,
            (time.perf_counter() - self.started) * 1000.0,
            failed=exc_type is not None,
        )
        return False

