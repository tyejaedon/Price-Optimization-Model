"""#70 synthetic preload and benchmark regressions; never requires Firebase keys."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.artifact_contract import MANIFEST_NAME, file_sha256, write_manifest
from src.protected_pricing_benchmark import benchmark_protected_pricing
from src.serve import InferenceRuntime, create_app
from tests.test_container_gateway import FakeFirestore, PAYLOAD
from tests.test_serve import ServeApiTests


class ProtectedPreloadTests(unittest.TestCase):
    @staticmethod
    def _app(artifacts, tariff, pin, repository):
        return create_app(
            artifact_dir=artifacts, tariff_csv_path=tariff,
            trusted_manifest_sha256=pin, repository=repository,
            token_verifier=lambda token: {"uid": "fixture-user"} if token == "valid" else {},
            readiness_probe=repository.probe_readiness,
        )

    def test_single_startup_load_and_no_per_request_joblib_or_artifact_hashing(self):
        with tempfile.TemporaryDirectory() as temp:
            artifacts, _, tariff = ServeApiTests()._build_artifacts(temp)
            repo = FakeFirestore()
            app = self._app(artifacts, tariff, file_sha256(os.path.join(artifacts, MANIFEST_NAME)), repo)
            real_load = InferenceRuntime.load
            with patch.object(InferenceRuntime, "load", autospec=True, side_effect=real_load) as load:
                with TestClient(app) as client:
                    self.assertEqual(load.call_count, 1)
                    self.assertEqual(client.get("/ready").status_code, 200)
                    with patch("joblib.load", side_effect=AssertionError("per-request joblib load")), \
                            patch("src.serve.verify_manifest", side_effect=AssertionError("per-request manifest verification")):
                        for _ in range(4):
                            response = client.post("/api/v1/optimize-price", json=PAYLOAD,
                                                   headers={"Authorization": "Bearer valid"})
                            self.assertEqual(response.status_code, 200, response.text)
                            self.assertEqual(client.get("/ready").status_code, 200)
                    self.assertEqual(load.call_count, 1)
            self.assertEqual(len(repo.list_transactions()), 4)

    def test_protected_unready_missing_and_incompatible_bundles_never_run_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            artifacts, _, tariff = ServeApiTests()._build_artifacts(temp)
            valid_pin = file_sha256(os.path.join(artifacts, MANIFEST_NAME))
            headers = {"Authorization": "Bearer valid"}
            for artifact_dir, pin, expected in (
                (artifacts, None, "Untrusted artifacts"),
                (os.path.join(temp, "missing"), valid_pin, "missing artifact file"),
            ):
                with self.subTest(expected=expected):
                    repository = FakeFirestore()
                    with patch.dict(os.environ, {"PRICING_ARTIFACT_MANIFEST_SHA256": ""}), \
                            patch("joblib.load", side_effect=AssertionError("untrusted pickle loaded")):
                        app = self._app(artifact_dir, tariff, pin, repository)
                        with TestClient(app) as client:
                            self.assertEqual(client.get("/health").json()["status"], "DEGRADED")
                            ready = client.get("/ready")
                            self.assertEqual(ready.status_code, 503)
                            self.assertIn(expected, ready.json()["readiness_reason"])
                            self.assertEqual(client.post("/api/v1/optimize-price", json=PAYLOAD,
                                                         headers=headers).status_code, 503)
                    self.assertEqual(repository.list_transactions(), [])

            config_path = os.path.join(artifacts, "inference_config.json")
            with open(config_path, encoding="utf-8") as handle:
                config = json.load(handle)
            config["version"] = 999
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(config, handle)
            pin = write_manifest(artifacts, config, dataset_version="synthetic-fixture-v1",
                                 source_type="synthetic proxy fixture", split_policy="synthetic fixed fixture")
            repository = FakeFirestore()
            app = self._app(artifacts, tariff, pin, repository)
            with patch("joblib.load", side_effect=AssertionError("incompatible pickle loaded")):
                with TestClient(app) as client:
                    ready = client.get("/ready")
                    self.assertEqual(ready.status_code, 503)
                    self.assertIn("feature schema", ready.json()["readiness_reason"])
                    self.assertEqual(client.post("/api/v1/optimize-price", json=PAYLOAD,
                                                 headers=headers).status_code, 503)
            self.assertEqual(repository.list_transactions(), [])

    def test_reproducible_profile_counts_warmed_auth_and_repository_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            artifacts, _, tariff = ServeApiTests()._build_artifacts(temp)
            digest = file_sha256(os.path.join(artifacts, MANIFEST_NAME))
            report = benchmark_protected_pricing(artifacts, tariff, digest, samples=5, warmup=2)
            self.assertEqual(report["samples_per_fixture"], 5)
            self.assertEqual(report["warmup_per_fixture_per_path"], 2)
            self.assertEqual(report["artifact"]["validation_status"], "exploratory_not_empirically_approved")
            self.assertEqual(report["environment"]["auth"], "local fixture verifier (NOT Firebase Admin)")
            self.assertGreaterEqual(report["lifespan_start_ms"], 0)
            self.assertEqual(len(report["fixtures"]), 2)
            self.assertEqual(report["skipped_untrained_fixtures"], ["cross_border_data_ai", "domestic_mobile"])
            for fixture in report["fixtures"].values():
                for operation in fixture.values():
                    self.assertEqual(operation["successful_requests"], 5)
                    self.assertEqual(operation["failed_requests"], 0)
                    self.assertGreaterEqual(operation["p95_ms"], 0)
            with self.assertRaisesRegex(ValueError, "samples must be positive"):
                benchmark_protected_pricing(artifacts, tariff, digest, samples=0)
            with self.assertRaisesRegex(RuntimeError, "pricing not ready"):
                benchmark_protected_pricing(artifacts, tariff, "0" * 64, samples=1, warmup=0)


if __name__ == "__main__":
    unittest.main()
