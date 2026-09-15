"""Latency and operational-stability profiling for the pricing inference path.

The module deliberately does not initialize Firestore or read credential files. It
profiles the available in-process model components and can optionally probe an
already-running HTTP endpoint through the standard library.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import statistics
import time
import tracemalloc
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np

from src.macro_arbitrage import fuse_coordinates
from src.nlp_pipeline import TextFeatureReducer
from src.spatial_engine import DomainPartitionedKDTreeIndexer, _build_demo_training_data
from src.tariff_evaluator import MpesaTariffEvaluator

DEFAULT_OUTPUT_DIR = os.path.join("reports", "inference_latency")
DEFAULT_ITERATIONS = 100
DEFAULT_MEMORY_ITERATIONS = 1000
DEFAULT_WARMUP_ITERATIONS = 10
DEFAULT_TARGET_P95_MS = 250.0
DEFAULT_MAX_MEMORY_GROWTH_BYTES = 1_000_000


@dataclass(frozen=True)
class LatencySummary:
    """Distribution and reliability statistics for repeated calls."""

    name: str
    iterations: int
    successful_requests: int
    failed_requests: int
    mean_ms: float
    min_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    throughput_requests_per_second: float
    error_types: Dict[str, int] = field(default_factory=dict)

    @property
    def all_requests_succeeded(self) -> bool:
        return self.failed_requests == 0

    def within_p95_target(self, target_ms: float) -> bool:
        return self.p95_ms <= float(target_ms) and self.all_requests_succeeded


@dataclass(frozen=True)
class MemoryStabilitySummary:
    """Approximate Python allocation growth during sequential inference calls."""

    iterations: int
    initial_current_bytes: int
    final_current_bytes: int
    peak_bytes: int
    growth_bytes: int
    growth_percent: float
    batch_current_bytes: List[int]
    failed_requests: int
    max_allowed_growth_bytes: int
    leak_suspected: bool


@dataclass(frozen=True)
class OperationalChecks:
    """Explicit M8.2 readiness checks derived from measured results."""

    latency_target_ms: float
    max_memory_growth_bytes: int
    nlp_p95_within_target: bool
    spatial_p95_within_target: bool
    inference_p95_within_target: bool
    no_inference_errors: bool
    memory_growth_within_limit: bool
    passed: bool


@dataclass(frozen=True)
class InferenceProfile:
    """Serializable M8.2 profile report."""

    execution_mode: str
    nlp_transform: LatencySummary
    spatial_prediction: LatencySummary
    inference: LatencySummary
    memory_stability: MemoryStabilitySummary
    operational_checks: OperationalChecks
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _validate_iterations(iterations: int, name: str = "iterations") -> int:
    resolved = int(iterations)
    if resolved < 1:
        raise ValueError(f"{name} must be at least 1.")
    return resolved


def _validate_warmup(warmup_iterations: int) -> int:
    resolved = int(warmup_iterations)
    if resolved < 0:
        raise ValueError("warmup_iterations cannot be negative.")
    return resolved


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    return float(np.percentile(np.asarray(values, dtype=float), percentile))


def _latency_summary(
    name: str,
    durations_ms: Sequence[float],
    requested_iterations: int,
    failures: Sequence[BaseException],
) -> LatencySummary:
    durations = [float(value) for value in durations_ms]
    elapsed_seconds = sum(durations) / 1000.0
    error_types: Dict[str, int] = {}
    for failure in failures:
        error_name = type(failure).__name__
        error_types[error_name] = error_types.get(error_name, 0) + 1

    return LatencySummary(
        name=name,
        iterations=int(requested_iterations),
        successful_requests=len(durations),
        failed_requests=len(failures),
        mean_ms=round(statistics.fmean(durations), 6) if durations else 0.0,
        min_ms=round(min(durations), 6) if durations else 0.0,
        p50_ms=round(_percentile(durations, 50), 6),
        p95_ms=round(_percentile(durations, 95), 6),
        p99_ms=round(_percentile(durations, 99), 6),
        max_ms=round(max(durations), 6) if durations else 0.0,
        throughput_requests_per_second=round(
            len(durations) / elapsed_seconds if elapsed_seconds > 0.0 else 0.0,
            6,
        ),
        error_types=error_types,
    )


def profile_callable_latency(
    operation: Callable[[], Any],
    *,
    name: str,
    iterations: int = DEFAULT_ITERATIONS,
    warmup_iterations: int = DEFAULT_WARMUP_ITERATIONS,
) -> LatencySummary:
    """Measure repeated callable latency without masking operation failures."""
    resolved_iterations = _validate_iterations(iterations)
    resolved_warmup = _validate_warmup(warmup_iterations)

    for _ in range(resolved_warmup):
        operation()

    durations_ms: List[float] = []
    failures: List[Exception] = []
    for _ in range(resolved_iterations):
        started = time.perf_counter()
        try:
            operation()
        except Exception as exc:  # pragma: no cover - exercised through failure tests
            failures.append(exc)
        else:
            durations_ms.append((time.perf_counter() - started) * 1000.0)

    return _latency_summary(name, durations_ms, resolved_iterations, failures)


def profile_memory_stability(
    operation: Callable[[], Any],
    *,
    iterations: int = DEFAULT_MEMORY_ITERATIONS,
    batch_size: int = 100,
    warmup_iterations: int = DEFAULT_WARMUP_ITERATIONS,
    max_allowed_growth_bytes: int = DEFAULT_MAX_MEMORY_GROWTH_BYTES,
) -> MemoryStabilitySummary:
    """Profile allocation growth over sequential calls using ``tracemalloc``.

    This detects obvious Python-level growth. It is not an OS RSS measurement and
    should be complemented by container/process metrics in production.
    """
    resolved_iterations = _validate_iterations(iterations)
    resolved_batch_size = _validate_iterations(batch_size, "batch_size")
    resolved_warmup = _validate_warmup(warmup_iterations)
    max_growth = max(0, int(max_allowed_growth_bytes))

    tracemalloc.start()
    try:
        for _ in range(resolved_warmup):
            operation()

        gc.collect()
        initial_current, _ = tracemalloc.get_traced_memory()
        batch_current_bytes: List[int] = []
        failures = 0
        for index in range(resolved_iterations):
            try:
                operation()
            except Exception:
                failures += 1
            if (index + 1) % resolved_batch_size == 0 or index + 1 == resolved_iterations:
                current, _ = tracemalloc.get_traced_memory()
                batch_current_bytes.append(int(current))
        final_current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    growth = int(final_current - initial_current)
    growth_percent = (growth / initial_current * 100.0) if initial_current else 0.0
    return MemoryStabilitySummary(
        iterations=resolved_iterations,
        initial_current_bytes=int(initial_current),
        final_current_bytes=int(final_current),
        peak_bytes=int(peak),
        growth_bytes=growth,
        growth_percent=round(growth_percent, 6),
        batch_current_bytes=batch_current_bytes,
        failed_requests=failures,
        max_allowed_growth_bytes=max_growth,
        leak_suspected=failures > 0 or growth > max_growth,
    )


def profile_http_endpoint(
    endpoint_url: str,
    payload: Mapping[str, Any],
    *,
    iterations: int = DEFAULT_ITERATIONS,
    warmup_iterations: int = DEFAULT_WARMUP_ITERATIONS,
    timeout_seconds: float = 10.0,
) -> LatencySummary:
    """Profile a JSON POST endpoint without importing or initializing the API service."""
    if not endpoint_url.strip():
        raise ValueError("endpoint_url cannot be empty.")
    if float(timeout_seconds) <= 0.0:
        raise ValueError("timeout_seconds must be positive.")

    body = json.dumps(dict(payload)).encode("utf-8")

    def request() -> None:
        request_object = urllib.request.Request(
            endpoint_url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request_object, timeout=float(timeout_seconds)) as response:
                response.read()
                if int(response.status) >= 400:
                    raise RuntimeError(f"HTTP endpoint returned status {response.status}.")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"HTTP endpoint returned status {exc.code}.") from exc

    return profile_callable_latency(
        request,
        name="http_inference",
        iterations=iterations,
        warmup_iterations=warmup_iterations,
    )


def _alpha_token(index: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    chars: List[str] = []
    value = int(index)
    while True:
        chars.append(alphabet[value % len(alphabet)])
        value //= len(alphabet)
        if value == 0:
            break
    return "tok" + "".join(chars)


def build_demo_inference_components() -> Dict[str, Any]:
    """Build deterministic local components for profiling and tests."""
    texts = [
        f"senior data scientist machine learning python analytics {_alpha_token(index)} {_alpha_token(index + 200)}"
        for index in range(90)
    ]
    reducer = TextFeatureReducer(n_components=50, max_features=12000)
    reducer.fit_transform(texts)

    matrix, partitions, verified_rates, query_vector = _build_demo_training_data()
    indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)
    indexer.fit(matrix, partitions, verified_rates=verified_rates)
    tariff_evaluator = MpesaTariffEvaluator.from_csv()
    metadata_vector = np.asarray([0.5, 0.3, 0.4], dtype=float)
    query_text = texts[-1]

    def infer() -> Dict[str, Any]:
        text_vector = reducer.transform([query_text])[0]
        fused_vector = fuse_coordinates(text_vector, metadata_vector)
        prediction = indexer.predict_base_rate(
            fused_vector,
            requested_partition="data_ai",
            k=3,
            allow_fallback=True,
        )
        return tariff_evaluator.evaluate_quote(
            base_predicted_rate=prediction["base_predicted_rate"],
            mentor_country="KE",
        )

    return {
        "reducer": reducer,
        "indexer": indexer,
        "infer": infer,
        "query_text": query_text,
        "query_vector": query_vector,
    }


def profile_inference_components(
    components: Mapping[str, Any],
    *,
    iterations: int = DEFAULT_ITERATIONS,
    memory_iterations: int = DEFAULT_MEMORY_ITERATIONS,
    warmup_iterations: int = DEFAULT_WARMUP_ITERATIONS,
    target_p95_ms: float = DEFAULT_TARGET_P95_MS,
    max_memory_growth_bytes: int = DEFAULT_MAX_MEMORY_GROWTH_BYTES,
) -> InferenceProfile:
    """Profile NLP, spatial, and end-to-end in-process inference components."""
    reducer = components["reducer"]
    indexer = components["indexer"]
    infer = components["infer"]
    query_text = str(components["query_text"])
    query_vector = components["query_vector"]

    nlp_profile = profile_callable_latency(
        lambda: reducer.transform([query_text]),
        name="nlp_transform",
        iterations=iterations,
        warmup_iterations=warmup_iterations,
    )
    spatial_profile = profile_callable_latency(
        lambda: indexer.predict_base_rate(
            query_vector,
            requested_partition="data_ai",
            k=3,
            allow_fallback=True,
        ),
        name="spatial_idw_prediction",
        iterations=iterations,
        warmup_iterations=warmup_iterations,
    )
    inference_profile = profile_callable_latency(
        infer,
        name="in_process_inference",
        iterations=iterations,
        warmup_iterations=warmup_iterations,
    )
    memory_profile = profile_memory_stability(
        infer,
        iterations=memory_iterations,
        warmup_iterations=warmup_iterations,
        max_allowed_growth_bytes=max_memory_growth_bytes,
    )

    checks = OperationalChecks(
        latency_target_ms=float(target_p95_ms),
        max_memory_growth_bytes=int(max_memory_growth_bytes),
        nlp_p95_within_target=nlp_profile.within_p95_target(target_p95_ms),
        spatial_p95_within_target=spatial_profile.within_p95_target(target_p95_ms),
        inference_p95_within_target=inference_profile.within_p95_target(target_p95_ms),
        no_inference_errors=(inference_profile.failed_requests == 0 and memory_profile.failed_requests == 0),
        memory_growth_within_limit=not memory_profile.leak_suspected,
        passed=(
            nlp_profile.within_p95_target(target_p95_ms)
            and spatial_profile.within_p95_target(target_p95_ms)
            and inference_profile.within_p95_target(target_p95_ms)
            and inference_profile.failed_requests == 0
            and memory_profile.failed_requests == 0
            and not memory_profile.leak_suspected
        ),
    )
    return InferenceProfile(
        execution_mode="in_process",
        nlp_transform=nlp_profile,
        spatial_prediction=spatial_profile,
        inference=inference_profile,
        memory_stability=memory_profile,
        operational_checks=checks,
        notes=[
            "Memory stability uses Python tracemalloc, not OS RSS.",
            "HTTP endpoint profiling is available through profile_http_endpoint().",
            "No Firestore or credential file is accessed by this profiler.",
        ],
    )


def write_profile_report(profile: InferenceProfile, output_dir: str) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, "inference_latency_profile.json")
    markdown_path = os.path.join(output_dir, "inference_latency_profile.md")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(profile.to_dict(), handle, indent=2, sort_keys=True)

    rows = [profile.nlp_transform, profile.spatial_prediction, profile.inference]
    markdown_lines = [
        "# M8.2 Inference Latency and Operational Stability",
        "",
        f"Execution mode: `{profile.execution_mode}`",
        "",
        "## Latency profile",
        "",
        "| Operation | Requests | Failures | Mean ms | P50 ms | P95 ms | P99 ms | Max ms | Throughput/s |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        markdown_lines.append(
            f"| {row.name} | {row.iterations} | {row.failed_requests} | {row.mean_ms:.3f} | "
            f"{row.p50_ms:.3f} | {row.p95_ms:.3f} | {row.p99_ms:.3f} | {row.max_ms:.3f} | "
            f"{row.throughput_requests_per_second:.2f} |"
        )
    memory = profile.memory_stability
    checks = profile.operational_checks
    markdown_lines.extend(
        [
            "",
            "## Memory stability",
            "",
            f"- Sequential requests: `{memory.iterations}`",
            f"- Current allocation growth: `{memory.growth_bytes}` bytes",
            f"- Peak traced allocation: `{memory.peak_bytes}` bytes",
            f"- Failed requests: `{memory.failed_requests}`",
            f"- Leak suspected: `{memory.leak_suspected}`",
            "",
            "## Operational checks",
            "",
            f"- P95 target: `{checks.latency_target_ms}` ms",
            f"- Maximum allocation growth: `{checks.max_memory_growth_bytes}` bytes",
            f"- NLP target passed: `{checks.nlp_p95_within_target}`",
            f"- Spatial target passed: `{checks.spatial_p95_within_target}`",
            f"- End-to-end target passed: `{checks.inference_p95_within_target}`",
            f"- No inference errors: `{checks.no_inference_errors}`",
            f"- Memory-growth limit passed: `{checks.memory_growth_within_limit}`",
            f"- **Overall passed: `{checks.passed}`**",
            "",
            "## Notes",
            "",
        ]
    )
    markdown_lines.extend(f"- {note}" for note in profile.notes)
    with open(markdown_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(markdown_lines) + "\n")
    return {"json": json_path, "markdown": markdown_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile inference latency and operational stability for M8.2.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--memory-iterations", type=int, default=DEFAULT_MEMORY_ITERATIONS)
    parser.add_argument("--warmup-iterations", type=int, default=DEFAULT_WARMUP_ITERATIONS)
    parser.add_argument("--target-p95-ms", type=float, default=DEFAULT_TARGET_P95_MS)
    parser.add_argument("--max-memory-growth-bytes", type=int, default=DEFAULT_MAX_MEMORY_GROWTH_BYTES)
    parser.add_argument("--endpoint-url", default="", help="Optional M7.2 HTTP endpoint URL to profile instead of local inference.")
    parser.add_argument("--http-timeout", type=float, default=10.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    components = build_demo_inference_components()
    profile = profile_inference_components(
        components,
        iterations=args.iterations,
        memory_iterations=args.memory_iterations,
        warmup_iterations=args.warmup_iterations,
        target_p95_ms=args.target_p95_ms,
        max_memory_growth_bytes=args.max_memory_growth_bytes,
    )

    if args.endpoint_url:
        payload = {
            "raw_description": components["query_text"],
            "selected_industry": "data_ai",
            "mentor_country": "KE",
            "client_country": "US",
            "competitiveness_score": 0.65,
            "market_saturation_score": 0.45,
        }
        http_profile = profile_http_endpoint(
            args.endpoint_url,
            payload,
            iterations=args.iterations,
            warmup_iterations=args.warmup_iterations,
            timeout_seconds=args.http_timeout,
        )
        profile = InferenceProfile(
            execution_mode="http",
            nlp_transform=profile.nlp_transform,
            spatial_prediction=profile.spatial_prediction,
            inference=http_profile,
            memory_stability=profile.memory_stability,
            operational_checks=OperationalChecks(
                latency_target_ms=args.target_p95_ms,
                max_memory_growth_bytes=args.max_memory_growth_bytes,
                nlp_p95_within_target=profile.nlp_transform.within_p95_target(args.target_p95_ms),
                spatial_p95_within_target=profile.spatial_prediction.within_p95_target(args.target_p95_ms),
                inference_p95_within_target=http_profile.within_p95_target(args.target_p95_ms),
                no_inference_errors=(http_profile.failed_requests == 0),
                memory_growth_within_limit=not profile.memory_stability.leak_suspected,
                passed=(
                    profile.nlp_transform.within_p95_target(args.target_p95_ms)
                    and profile.spatial_prediction.within_p95_target(args.target_p95_ms)
                    and http_profile.within_p95_target(args.target_p95_ms)
                    and not profile.memory_stability.leak_suspected
                ),
            ),
            notes=profile.notes + [f"HTTP endpoint profiled: {args.endpoint_url}"],
        )

    paths = write_profile_report(profile, args.output_dir)
    print(json.dumps({"profile": profile.to_dict(), "report_paths": paths}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
