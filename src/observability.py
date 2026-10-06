"""Thread-safe, process-local latency and exception counters, not durable telemetry.

Serving code records named request timers (``api.<method>.<path>``), inference
(``inference.optimize_price``), instrumented database calls, and audit persistence.
``database.append_transaction`` counts each attempt; ``audit.persist`` records
the overall background task, so a successful retry can coexist with a failed
database attempt. Timers count exceptions escaping their scope, not HTTP status
codes: a handled error response does not necessarily increment API failures.

Snapshots keep cumulative counts but latency statistics cover only the latest
10000 samples per name. Names themselves are not bounded, snapshots reset with
the process, and there is no cross-worker aggregation, durable queue, request
trace or payment verification. A successful request/metric cannot prove an audit
was persisted or an empirically verified payment occurred.

See ../docs/README.md (glossary) and ../docs/M11.2_Pricing_Audit.md
(audit events, retries and durability limits).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List


class MetricsRegistry:
    """Lock-protected counters and bounded per-operation latency sample windows."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latencies: Dict[str, List[float]] = defaultdict(list)
        self._requests: Dict[str, int] = defaultdict(int)
        self._failures: Dict[str, int] = defaultdict(int)

    def record(self, name: str, latency_ms: float, failed: bool = False) -> None:
        """Record milliseconds to six decimals and optionally increment failures.

        Counts span this registry's lifetime; only the latest 10000 latencies
        per operation are retained. Callers choose names and failure semantics.
        """
        with self._lock:
            values = self._latencies[name]
            values.append(round(float(latency_ms), 6))
            if len(values) > 10_000:
                del values[: len(values) - 10_000]
            self._requests[name] += 1
            if failed:
                self._failures[name] += 1

    def snapshot(self) -> Dict[str, Any]:
        """Return a UTC-stamped copy of counts and current-window mean/p95/max.

        P95 selects the rounded 95%-position in sorted retained samples; it is
        not an interpolated percentile or an end-to-end mobile latency measure.
        """
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
        """Create a context timer for one named operation; entering starts timing."""
        return MetricTimer(self, name)


class MetricTimer:
    """Measure elapsed perf_counter time and record escaping exceptions as failures."""

    def __init__(self, registry: MetricsRegistry, name: str) -> None:
        self.registry = registry
        self.name = name
        self.started = 0.0

    def __enter__(self) -> "MetricTimer":
        """Start the monotonic timer and return this context."""
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        """Record elapsed milliseconds even on failure, without suppressing exceptions."""
        self.registry.record(
            self.name,
            (time.perf_counter() - self.started) * 1000.0,
            failed=exc_type is not None,
        )
        return False
