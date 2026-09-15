import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.performance_profiling import (
    build_demo_inference_components,
    profile_callable_latency,
    profile_http_endpoint,
    profile_inference_components,
    profile_memory_stability,
    write_profile_report,
)


class PerformanceProfilingTests(unittest.TestCase):
    def test_callable_profile_counts_failures_without_polluting_latency_stats(self) -> None:
        calls = 0

        def operation() -> None:
            nonlocal calls
            calls += 1
            if calls == 3:
                raise ValueError("synthetic failure")

        summary = profile_callable_latency(operation, name="synthetic", iterations=5, warmup_iterations=0)

        self.assertEqual(calls, 5)
        self.assertEqual(summary.iterations, 5)
        self.assertEqual(summary.successful_requests, 4)
        self.assertEqual(summary.failed_requests, 1)
        self.assertEqual(summary.error_types, {"ValueError": 1})
        self.assertGreaterEqual(summary.p95_ms, 0.0)

    def test_memory_profile_reports_bounded_short_lived_allocations(self) -> None:
        summary = profile_memory_stability(
            lambda: [value * 2 for value in range(25)],
            iterations=20,
            batch_size=5,
            warmup_iterations=1,
            max_allowed_growth_bytes=10_000_000,
        )

        self.assertEqual(summary.iterations, 20)
        self.assertEqual(summary.failed_requests, 0)
        self.assertEqual(len(summary.batch_current_bytes), 4)
        self.assertFalse(summary.leak_suspected)

    def test_callable_profile_reports_when_every_request_fails(self) -> None:
        def operation() -> None:
            raise ConnectionError("synthetic outage")

        summary = profile_callable_latency(operation, name="outage", iterations=3, warmup_iterations=0)

        self.assertEqual(summary.successful_requests, 0)
        self.assertEqual(summary.failed_requests, 3)
        self.assertEqual(summary.error_types, {"ConnectionError": 3})
        self.assertFalse(summary.within_p95_target(250.0))

    def test_http_profile_measures_loopback_json_post(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
                content_length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(content_length)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            summary = profile_http_endpoint(
                f"http://127.0.0.1:{server.server_port}/predict",
                {"raw_description": "demo"},
                iterations=3,
                warmup_iterations=0,
                timeout_seconds=2.0,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2.0)

        self.assertEqual(summary.name, "http_inference")
        self.assertEqual(summary.successful_requests, 3)
        self.assertEqual(summary.failed_requests, 0)

    def test_demo_inference_profile_writes_latency_and_stability_reports(self) -> None:
        components = build_demo_inference_components()
        profile = profile_inference_components(
            components,
            iterations=3,
            memory_iterations=10,
            warmup_iterations=1,
            target_p95_ms=5_000.0,
            max_memory_growth_bytes=10_000_000,
        )

        self.assertEqual(profile.execution_mode, "in_process")
        self.assertEqual(profile.inference.failed_requests, 0)
        self.assertEqual(profile.memory_stability.iterations, 10)
        self.assertIn("tracemalloc", " ".join(profile.notes))

        with tempfile.TemporaryDirectory() as output_dir:
            paths = write_profile_report(profile, output_dir)
            self.assertTrue(os.path.exists(paths["json"]))
            self.assertTrue(os.path.exists(paths["markdown"]))
            with open(paths["markdown"], encoding="utf-8") as handle:
                report = handle.read()
            self.assertIn("M8.2 Inference Latency", report)
            self.assertIn("Operational checks", report)

    def test_invalid_iteration_counts_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 1"):
            profile_callable_latency(lambda: None, name="invalid", iterations=0)
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            profile_memory_stability(lambda: None, iterations=1, warmup_iterations=-1)


if __name__ == "__main__":
    unittest.main()

