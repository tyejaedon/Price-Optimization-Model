"""Profile a pinned artifact bundle through warmed inference and protected pricing.

This is an in-process engineering benchmark: Firebase verification and Firestore
are timed local stubs, not a real cloud service or network RTT measurement.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import fastapi
import numpy
import sklearn
from fastapi.testclient import TestClient

from src.api_contracts import PricingQueryDTO
from src.performance_profiling import profile_callable_latency, summarize_latency_samples
from src.repository import InMemoryRepository
from src.serve import create_app


FIXTURES = {
    "domestic_web_backend": {
        "mentorId": "benchmark-mentor",
        "raw_description": "Senior Python backend engineer mentoring cloud API development and database architecture.",
        "selected_industry": "web_backend",
        "mentor_country": "KE",
        "client_country": "KE",
        "market_saturation_score": 0.3,
    },
    "cross_border_web_backend": {
        "mentorId": "benchmark-mentor",
        "raw_description": "Experienced web services developer teaching distributed systems and scalable APIs.",
        "selected_industry": "web_backend",
        "mentor_country": "KE",
        "client_country": "US",
        "market_saturation_score": 0.7,
    },
    "cross_border_data_ai": {
        "mentorId": "benchmark-mentor",
        "raw_description": "Senior data scientist mentoring machine learning, Python analytics and AI deployment.",
        "selected_industry": "data_ai",
        "mentor_country": "KE",
        "client_country": "US",
        "market_saturation_score": 0.5,
    },
    "domestic_mobile": {
        "mentorId": "benchmark-mentor",
        "raw_description": "Android Kotlin mobile application developer teaching architecture and app delivery.",
        "selected_industry": "mobile",
        "mentor_country": "KE",
        "client_country": "KE",
        "market_saturation_score": 0.5,
    },
}


class TimedFirestoreStub(InMemoryRepository):
    """No credentials, network or persistent writes; time the repository interface."""

    def __init__(self) -> None:
        super().__init__()
        self.upsert_profile("benchmark-mentor", {
            "auth_uid": "benchmark-mentor", "full_name": "Synthetic Mentor",
            "email": "mentor@example.com", "country_code": "KE",
        })
        self.health_ms: list[float] = []
        self.audit_ms: list[float] = []

    def health(self) -> str:
        started = time.perf_counter()
        result = "firestore"
        self.health_ms.append((time.perf_counter() - started) * 1000)
        return result

    def probe_readiness(self) -> bool:
        return True

    def append_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        result = super().append_transaction(payload)
        self.audit_ms.append((time.perf_counter() - started) * 1000)
        return result


def benchmark_protected_pricing(
    artifact_dir: str,
    tariff_csv_path: str,
    trusted_manifest_sha256: str,
    *,
    samples: int = 100,
    warmup: int = 10,
) -> dict[str, Any]:
    """Return distributions per fixture, failing rather than reporting unready or failed calls."""
    if samples < 1 or warmup < 0:
        raise ValueError("samples must be positive and warmup non-negative")

    repository = TimedFirestoreStub()
    verifier_ms: list[float] = []

    def verify_fixture_token(token: str) -> dict[str, str]:
        started = time.perf_counter()
        if token != "fixture-id-token":
            raise ValueError("invalid fixture token")
        verifier_ms.append((time.perf_counter() - started) * 1000)
        return {"uid": "benchmark-mentor"}

    app = create_app(
        artifact_dir=artifact_dir,
        tariff_csv_path=tariff_csv_path,
        repository=repository,
        token_verifier=verify_fixture_token,
        readiness_probe=repository.probe_readiness,
        trusted_manifest_sha256=trusted_manifest_sha256,
    )
    started = time.perf_counter()
    with TestClient(app) as client:
        lifespan_start_ms = (time.perf_counter() - started) * 1000
        ready = client.get("/ready")
        if ready.status_code != 200:
            raise RuntimeError(f"pricing not ready: {ready.json().get('readiness_reason') or 'unavailable'}")

        runtime = app.state.inference_runtime
        fixtures: dict[str, Any] = {}
        skipped: list[str] = []
        for name, payload in FIXTURES.items():
            query = PricingQueryDTO.model_validate(payload)
            if query.selected_industry not in runtime.spatial_indexer.active_partitions():
                skipped.append(name)
                continue

            inference = profile_callable_latency(
                lambda: runtime.predict(query), name="warmed_inference",
                iterations=samples, warmup_iterations=warmup,
            )
            if not inference.all_requests_succeeded:
                raise RuntimeError(f"warmed inference failed for fixture: {name}")

            def protected_request() -> None:
                response = client.post(
                    "/api/v1/optimize-price", json=payload,
                    headers={"Authorization": "Bearer fixture-id-token"},
                )
                if response.status_code != 200:
                    raise RuntimeError(f"protected pricing returned HTTP {response.status_code}")
                quote = response.json()
                if not quote["nearest_neighbors"] or quote["min_quoted_rate"] > quote["max_quoted_rate"]:
                    raise RuntimeError("invalid pricing response")

            for _ in range(warmup):
                protected_request()
            verifier_ms.clear()
            repository.health_ms.clear()
            repository.audit_ms.clear()
            protected_http = profile_callable_latency(
                protected_request, name="authenticated_testclient_http",
                iterations=samples, warmup_iterations=0,
            )
            if not protected_http.all_requests_succeeded:
                raise RuntimeError(f"protected pricing failed for fixture: {name}")
            if not (len(verifier_ms) == len(repository.health_ms) == len(repository.audit_ms) == samples):
                raise RuntimeError("missing authentication or repository timing samples")

            fixtures[name] = {
                "warmed_inference": asdict(inference),
                "authenticated_testclient_http": asdict(protected_http),
                "firebase_verifier_stub": asdict(summarize_latency_samples("firebase_verifier_stub", verifier_ms)),
                "firestore_health_stub": asdict(summarize_latency_samples("firestore_health_stub", repository.health_ms)),
                "firestore_audit_stub": asdict(summarize_latency_samples("firestore_audit_stub", repository.audit_ms)),
            }

        if not fixtures:
            raise RuntimeError("No benchmark fixtures have a trained partition")
        manifest = runtime.manifest
        return {
            "environment": {
                "python": platform.python_version(), "os": platform.platform(),
                "machine": platform.machine(), "logical_cpus": os.cpu_count(),
                "numpy": numpy.__version__, "scikit_learn": sklearn.__version__,
                "fastapi": fastapi.__version__, "http_client": "FastAPI TestClient (in-process)",
                "auth": "local fixture verifier (NOT Firebase Admin)",
                "repository": "in-memory Firestore interface stub (NOT cloud Firestore)",
            },
            "artifact": {
                "version": ready.json()["artifact_version"],
                "dataset_version": manifest["provenance"]["dataset_version"],
                "source_type": manifest["provenance"]["source_type"],
                "validation_status": manifest["provenance"]["validation_status"],
                "partition_counts": runtime.spatial_indexer.partition_counts,
            },
            "samples_per_fixture": samples,
            "warmup_per_fixture_per_path": warmup,
            "lifespan_start_ms": round(lifespan_start_ms, 6),
            "percentile_method": "numpy.percentile linear interpolation over successful calls",
            "fixtures": fixtures,
            "skipped_untrained_fixtures": skipped,
            "limitations": "No real token verification, Firestore network, TCP/TLS, container or 3G RTT; no HTTP SLA gate.",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark a preloaded protected pricing bundle locally (#70).")
    parser.add_argument("--artifact-dir", required=True, help="Trusted, reviewed local artifact export")
    parser.add_argument("--manifest-sha256", required=True, help="Independently trusted manifest digest")
    parser.add_argument("--tariff-csv", required=True, help="Local approved tariff file (fixture for tests only)")
    parser.add_argument("--output", default="reports/m10_protected_pricing/latency.json")
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    args = parser.parse_args()
    report = benchmark_protected_pricing(
        args.artifact_dir, args.tariff_csv, args.manifest_sha256,
        samples=args.samples, warmup=args.warmup,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
