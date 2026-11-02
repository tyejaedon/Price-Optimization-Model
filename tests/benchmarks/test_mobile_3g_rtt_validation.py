"""Unit and benchmark tests for M14.2: Mobile 3G RTT Validation (#86)."""

import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from src.benchmarks.mobile_3g_rtt_validation import (
    GOOD_3G,
    MOBILE_3G_RTT_TARGET_MS,
    REGULAR_3G,
    SLOW_3G,
    MobilePricing3GBenchmarkRunner,
    NetworkProfile,
    Simulated3GNetworkConditioner,
    build_default_test_app,
)


class Mobile3GRTTValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app, self.payload, self.headers = build_default_test_app()

    def test_network_profile_specifications(self) -> None:
        """Verify standard 3G cellular network profiles meet 3GPP/ITU-T specifications."""
        for profile in (REGULAR_3G, GOOD_3G, SLOW_3G):
            self.assertGreater(profile.download_kbps, 0.0)
            self.assertGreater(profile.upload_kbps, 0.0)
            self.assertGreaterEqual(profile.download_kbps, profile.upload_kbps)
            self.assertGreater(profile.one_way_latency_ms, 0.0)
            self.assertGreater(profile.jitter_ms, 0.0)
            self.assertGreaterEqual(profile.packet_loss_rate, 0.0)
            self.assertLess(profile.packet_loss_rate, 0.05)

    def test_conditioner_transfer_time_calculation(self) -> None:
        """Verify upload and download bandwidth transfer time calculations."""
        conditioner = Simulated3GNetworkConditioner(REGULAR_3G, seed=123)

        # 1000 bytes at 250 kbps (31.25 kB/s) upload -> 1000 / 31250 * 1000 = 32.0 ms
        t_up = conditioner.calculate_transfer_time_ms(1000, uplink=True)
        self.assertAlmostEqual(t_up, 32.0, places=1)

        # 1500 bytes at 750 kbps (93.75 kB/s) download -> 1500 / 93750 * 1000 = 16.0 ms
        t_down = conditioner.calculate_transfer_time_ms(1500, uplink=False)
        self.assertAlmostEqual(t_down, 16.0, places=1)

    def test_conditioner_connection_and_token_overhead(self) -> None:
        """Verify cold TCP/TLS and token refresh overheads vs warmed connection."""
        conditioner = Simulated3GNetworkConditioner(REGULAR_3G, seed=123)

        # Warmed connection has zero handshake overhead
        self.assertEqual(conditioner.simulate_connection_setup_ms(is_cold=False), 0.0)

        # Cold connection: 4 * 100 ms = 400 ms (2 round-trips for TCP 3-way handshake + TLS 1.3)
        self.assertEqual(conditioner.simulate_connection_setup_ms(is_cold=True), 400.0)

        # Token acquisition: warmed is cached (< 1 ms), cold requires network round-trip (> 200 ms)
        t_token_warm = conditioner.simulate_token_acquisition_ms(is_cold=False)
        self.assertLess(t_token_warm, 1.0)

        t_token_cold = conditioner.simulate_token_acquisition_ms(is_cold=True)
        self.assertGreaterEqual(t_token_cold, 200.0)

    def test_warmed_authenticated_pricing_meets_target(self) -> None:
        """Validate authenticated mobile pricing round-trip latency satisfies RTT < 3.0s under Regular 3G."""
        runner = MobilePricing3GBenchmarkRunner(self.app, profile=REGULAR_3G, seed=42)
        summary = runner.run_benchmark(
            payload=self.payload,
            headers=self.headers,
            sample_count=30,
            warmup_count=3,
        )

        self.assertTrue(summary.target_met)
        self.assertLess(summary.p95_rtt_ms, MOBILE_3G_RTT_TARGET_MS)
        self.assertEqual(summary.failure_rate, 0.0)
        self.assertEqual(summary.timeout_rate, 0.0)

        # Verify percentiles are monotonically increasing: P50 <= P90 <= P95 <= P99
        self.assertLessEqual(summary.p50_rtt_ms, summary.p90_rtt_ms)
        self.assertLessEqual(summary.p90_rtt_ms, summary.p95_rtt_ms)
        self.assertLessEqual(summary.p95_rtt_ms, summary.p99_rtt_ms)

        # Verify backend server processing is isolated and measured
        self.assertGreater(summary.server_p95_ms, 0.0)
        self.assertLess(summary.server_p95_ms, summary.p95_rtt_ms)

    def test_slow_3g_profile_meets_target(self) -> None:
        """Validate that even under high latency Slow 3G (400ms RTT), P95 remains < 3.0s."""
        runner = MobilePricing3GBenchmarkRunner(self.app, profile=SLOW_3G, seed=42)
        summary = runner.run_benchmark(
            payload=self.payload,
            headers=self.headers,
            sample_count=20,
            warmup_count=2,
        )

        self.assertTrue(summary.target_met)
        self.assertLess(summary.p95_rtt_ms, MOBILE_3G_RTT_TARGET_MS)
        self.assertEqual(summary.failure_rate, 0.0)

    def test_cold_flow_end_to_end_timing(self) -> None:
        """Verify cold flow with TLS connection and token refresh remains well below 3.0s."""
        runner = MobilePricing3GBenchmarkRunner(self.app, profile=REGULAR_3G, seed=42)
        from fastapi.testclient import TestClient

        with TestClient(self.app) as client:
            sample = runner.execute_single_request(
                client,
                "/api/v1/optimize-price",
                self.payload,
                self.headers,
                is_cold=True,
            )

        self.assertTrue(sample.success)
        self.assertEqual(sample.status_code, 200)
        # Cold connection should be ~600-1100ms, strictly below 3000ms
        self.assertGreater(sample.timing.connection_handshake_ms, 300.0)
        self.assertGreater(sample.timing.token_acquisition_ms, 200.0)
        self.assertLess(sample.timing.total_rtt_ms, MOBILE_3G_RTT_TARGET_MS)

    def test_secure_error_paths_under_simulated_3g(self) -> None:
        """Verify error paths (401, 403, 422, timeout) are observable and properly mapped."""
        runner = MobilePricing3GBenchmarkRunner(self.app, profile=REGULAR_3G, seed=42)
        summary = runner.run_benchmark(
            payload=self.payload,
            headers=self.headers,
            sample_count=10,
            warmup_count=1,
        )

        paths = summary.error_paths_verified
        self.assertTrue(paths.get("401_unauthorized"), "401 Unauthorized path must return 401")
        self.assertTrue(paths.get("403_forbidden"), "403 Forbidden path must return 403")
        self.assertTrue(paths.get("422_validation"), "422 Validation error must return 422")
        self.assertTrue(paths.get("timeout_observable"), "Timeout must be observable")

    def test_cli_json_emission(self) -> None:
        """Verify CLI runner emits valid JSON with complete statistics."""
        cmd = [
            sys.executable,
            "-m",
            "src.benchmarks.mobile_3g_rtt_validation",
            "--samples",
            "10",
            "--json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Find JSON block in output
        json_start = result.stdout.find("{")
        self.assertGreaterEqual(json_start, 0)
        data = json.loads(result.stdout[json_start:])

        self.assertIn("p50_rtt_ms", data)
        self.assertIn("p95_rtt_ms", data)
        self.assertIn("target_met", data)
        self.assertTrue(data["target_met"])
        self.assertLess(data["p95_rtt_ms"], 3000.0)


if __name__ == "__main__":
    unittest.main()
