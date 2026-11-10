"""Tests for M13.4: Hosted pricing service deployment on Render with PLATFORM_PRICE_KEY."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

from src.api.hosted import create_hosted_app
from src.core.artifact_contract import MANIFEST_NAME, file_sha256, write_manifest
from src.data.ingest_multisource import SUPPORTED_INDUSTRY_PARTITIONS, build_macro_lookup
from src.engine.macro_arbitrage import ContinuousMetadataNormalizer, HYBRID_VECTOR_DIMENSIONS
from src.engine.spatial_engine import DomainPartitionedKDTreeIndexer
from src.nlp.nlp_pipeline import TextFeatureReducer

TEST_PLATFORM_KEY = "render-hosted-platform-key-xyz"


class HostedRenderDeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        cls.render_yaml_path = cls.repo_root / "render.yaml"
        cls.dockerfile_path = cls.repo_root / "Dockerfile"

        cls.tmp_dir = tempfile.mkdtemp()
        cls.artifact_dir = os.path.join(cls.tmp_dir, "artifacts")
        os.makedirs(cls.artifact_dir, exist_ok=True)

        cls.raw_fixture_dir = str(cls.repo_root / "tests" / "fixtures" / "raw")
        cls.tariff_csv_path = str(
            cls.repo_root
            / "tests"
            / "fixtures"
            / "raw"
            / "Mpesa_Tarrifs"
            / "tarrifs_full_schedule.csv"
        )
        cls.macro_lookup_path = os.path.join(cls.tmp_dir, "macro_lookup_table.json")
        build_macro_lookup(cls.raw_fixture_dir, cls.macro_lookup_path)

        texts = [f"mentor profile engineering python backend cloud devops {i}" for i in range(90)]
        reducer = TextFeatureReducer(n_components=50, max_features=8000)
        reducer.fit_transform(texts)
        reducer.save_artifacts(cls.artifact_dir)

        normalizer = ContinuousMetadataNormalizer(macro_lookup_path=cls.macro_lookup_path)
        records = [
            {
                "bilateral_arbitrage_factor": 1.0,
                "market_saturation_score": 0.2,
                "industry_relative_density": 0.3,
            }
        ]
        normalizer.fit(records)
        normalizer.save_artifacts(cls.artifact_dir)

        partitions = []
        for p in SUPPORTED_INDUSTRY_PARTITIONS:
            partitions.extend([p] * 5)
        n = len(partitions)
        vectors = np.zeros((n, HYBRID_VECTOR_DIMENSIONS), dtype=float)
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=1)
        indexer.fit(
            vectors,
            partitions,
            record_indices=list(range(n)),
            verified_rates=[3500.0] * n,
        )
        indexer.save_artifacts(cls.artifact_dir)
        shutil.copyfile(cls.macro_lookup_path, os.path.join(cls.artifact_dir, "macro_lookup_table.json"))

        config = {
            "version": 1,
            "text_dimensions": 50,
            "metadata_features": [
                "bilateral_arbitrage_factor",
                "market_saturation_score",
                "industry_relative_density",
            ],
            "k_neighbors": 5,
            "idw_epsilon": 1e-6,
            "text_weight": 1.0,
            "metadata_weight": 1.0,
            "minimum_partition_size": 1,
            "fallback_partition": "general_tech",
            "allow_fallback": True,
            "partition_density": {p: 0.5 for p in SUPPORTED_INDUSTRY_PARTITIONS},
        }
        with open(os.path.join(cls.artifact_dir, "inference_config.json"), "w", encoding="utf-8") as handle:
            json.dump(config, handle)
        write_manifest(
            cls.artifact_dir,
            config,
            dataset_version="synthetic-fixture-v1",
            source_type="synthetic proxy fixture",
            split_policy="synthetic fixed fixture",
        )

        cls.manifest_sha256 = file_sha256(os.path.join(cls.artifact_dir, MANIFEST_NAME))
        cls.tariff_sha256 = file_sha256(cls.tariff_csv_path)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def setUp(self) -> None:
        self.env_patcher = patch.dict(
            os.environ,
            {
                "PRICING_ARTIFACT_DIR": self.artifact_dir,
                "PRICING_TARIFF_CSV": self.tariff_csv_path,
                "PRICING_ARTIFACT_MANIFEST_SHA256": self.manifest_sha256,
                "PRICING_TARIFF_SHA256": self.tariff_sha256,
            },
        )
        self.env_patcher.start()

    def tearDown(self) -> None:
        self.env_patcher.stop()

    def test_render_yaml_validity_and_specifications(self) -> None:
        self.assertTrue(self.render_yaml_path.is_file(), "render.yaml must exist at repo root")
        content = self.render_yaml_path.read_text(encoding="utf-8")

        self.assertIn("type: web", content)
        self.assertIn("name: price-optimization-service", content)
        self.assertIn("env: docker", content)
        self.assertIn("dockerfilePath: ./Dockerfile", content)
        self.assertIn("healthCheckPath: /health", content)
        self.assertIn("src.api.hosted:app", content)
        self.assertIn("$PORT", content)
        self.assertIn("PLATFORM_PRICE_KEY", content)
        self.assertIn("SEED_PLATFORM_MENTORS", content)
        self.assertIn("PRICING_TARIFF_SHA256", content)
        self.assertIn("PRICING_ARTIFACT_MANIFEST_SHA256", content)

    def test_dockerfile_render_specifications(self) -> None:
        self.assertTrue(self.dockerfile_path.is_file(), "Dockerfile must exist at repo root")
        content = self.dockerfile_path.read_text(encoding="utf-8")

        # Render requirement: must bind to host 0.0.0.0
        self.assertIn("--host", content)
        self.assertIn("0.0.0.0", content)
        # Render requirement: dynamic port binding via PORT variable (default 10000)
        self.assertIn("PORT", content)
        self.assertIn("10000", content)
        self.assertIn("EXPOSE 10000", content)
        # Non-root user execution
        self.assertIn("USER pricing", content)
        # Dynamic module dispatch supporting hosted on Render and deployment in CI
        self.assertIn("APP_MODULE", content)
        self.assertIn("src.api.hosted:app", content)
        self.assertIn("src.api.deployment:app", content)

    def test_hosted_service_health_and_ready(self) -> None:
        app = create_hosted_app()
        with TestClient(app) as client:
            health_resp = client.get("/health")
            self.assertEqual(health_resp.status_code, 200)
            health_body = health_resp.json()
            self.assertIn("database", health_body)

            ready_resp = client.get("/ready")
            self.assertEqual(ready_resp.status_code, 200)
            self.assertEqual(ready_resp.json().get("status"), "HEALTHY")

    def test_platform_pricing_disabled_when_key_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PLATFORM_PRICE_KEY", None)
            app = create_hosted_app()
            with TestClient(app) as client:
                resp = client.post("/price", json={"mentorId": "p1"}, headers={"X-Platform-Key": "any"})
                self.assertEqual(resp.status_code, 503)
                self.assertIn("PLATFORM_PRICE_KEY", resp.json()["detail"])

    def test_platform_pricing_unauthorized_with_bad_key(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": TEST_PLATFORM_KEY}):
            app = create_hosted_app()
            with TestClient(app) as client:
                missing = client.post("/price", json={"mentorId": "p1"})
                wrong = client.post(
                    "/price", json={"mentorId": "p1"}, headers={"X-Platform-Key": "wrong-key"}
                )
                self.assertEqual(missing.status_code, 401)
                self.assertEqual(wrong.status_code, 401)

    def test_platform_pricing_authorized_resolves_seeded_mentors(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": TEST_PLATFORM_KEY}):
            app = create_hosted_app()
            with TestClient(app) as client:
                # Career Mentor OS contract sends only { "mentorId": "p1" }
                resp = client.post(
                    "/price",
                    json={"mentorId": "p1"},
                    headers={"X-Platform-Key": TEST_PLATFORM_KEY},
                )
                self.assertEqual(resp.status_code, 200, resp.text)
                body = resp.json()
                self.assertEqual(set(body.keys()), {"min", "max", "comparables", "reason"})
                self.assertGreater(body["min"], 0.0)
                self.assertGreaterEqual(body["max"], body["min"])
                self.assertIsInstance(body["comparables"], list)
                self.assertIn("KES", body["reason"])

                # Also resolves by user ID alias (u1)
                resp_user = client.post(
                    "/price",
                    json={"mentorId": "u1"},
                    headers={"X-Platform-Key": TEST_PLATFORM_KEY},
                )
                self.assertEqual(resp_user.status_code, 200, resp_user.text)


if __name__ == "__main__":
    unittest.main()
