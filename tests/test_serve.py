import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from src.artifact_contract import MANIFEST_NAME, file_sha256, write_manifest
from src.ingest_multisource import build_macro_lookup
from src.macro_arbitrage import ContinuousMetadataNormalizer, HYBRID_VECTOR_DIMENSIONS
from src.nlp_pipeline import TextFeatureReducer
from src.serve import create_app
from src.spatial_engine import DomainPartitionedKDTreeIndexer


class ServeApiTests(unittest.TestCase):
    @staticmethod
    def _alpha_token(index: int) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        chars = []
        value = index
        while True:
            chars.append(alphabet[value % len(alphabet)])
            value //= len(alphabet)
            if value == 0:
                return "tok" + "".join(chars)

    def _build_artifacts(self, tmp_dir: str) -> tuple[str, str, str]:
        repo_root = Path(__file__).resolve().parent.parent
        raw_fixture_dir = str(repo_root / "tests" / "fixtures" / "raw")
        macro_lookup_path = os.path.join(tmp_dir, "macro_lookup_table.json")
        tariff_csv_path = str(repo_root / "tests" / "fixtures" / "raw" / "Mpesa_Tarrifs" / "tarrifs_full_schedule.csv")
        artifact_dir = os.path.join(tmp_dir, "artifacts")
        os.makedirs(artifact_dir, exist_ok=True)
        build_macro_lookup(raw_fixture_dir, macro_lookup_path)

        texts = [
            f"web backend python api engineering {self._alpha_token(index)}"
            for index in range(90)
        ]
        reducer = TextFeatureReducer(n_components=50, max_features=8000)
        reducer.fit_transform(texts)
        reducer.save_artifacts(artifact_dir)

        normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path)
        records = [
            {
                "bilateral_arbitrage_factor": 1.0 + index * 0.1,
                "market_saturation_score": 0.2 + index * 0.05,
                "industry_relative_density": 0.3 + index * 0.04,
            }
            for index in range(5)
        ]
        normalizer.fit(records)
        normalizer.save_artifacts(artifact_dir)

        vectors = np.zeros((5, HYBRID_VECTOR_DIMENSIONS), dtype=float)
        vectors[:, 0] = np.arange(5, dtype=float) * 0.1
        vectors[:, -3:] = np.asarray(
            [[1.0 + index * 0.1, 0.2 + index * 0.05, 0.3 + index * 0.04] for index in range(5)],
            dtype=float,
        )
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=1)
        indexer.fit(
            vectors,
            ["web_backend"] * 5,
            record_indices=list(range(5)),
            verified_rates=[3000.0, 3200.0, 3400.0, 3600.0, 3800.0],
        )
        indexer.save_artifacts(artifact_dir)
        shutil.copyfile(macro_lookup_path, os.path.join(artifact_dir, "macro_lookup_table.json"))
        config = {
                "version": 1,
                "text_dimensions": 50,
                "metadata_features": ["bilateral_arbitrage_factor", "market_saturation_score", "industry_relative_density"],
                "k_neighbors": 5,
                "idw_epsilon": 1e-6,
                "text_weight": 1.0,
                "metadata_weight": 1.0,
                "minimum_partition_size": 1,
                "fallback_partition": "general_tech",
                "allow_fallback": True,
                "partition_density": {"web_backend": 0.5},
        }
        with open(os.path.join(artifact_dir, "inference_config.json"), "w", encoding="utf-8") as handle:
            json.dump(config, handle)
        write_manifest(artifact_dir, config, dataset_version="synthetic-fixture-v1",
                       source_type="synthetic proxy fixture", split_policy="synthetic fixed fixture")
        return artifact_dir, macro_lookup_path, tariff_csv_path

    @staticmethod
    def _app(artifact_dir: str, macro_path: str, tariff_path: str):
        return create_app(artifact_dir, macro_path, tariff_path,
                          trusted_manifest_sha256=file_sha256(os.path.join(artifact_dir, MANIFEST_NAME)))

    def test_health_reports_ready_when_artifacts_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir, macro_path, tariff_path = self._build_artifacts(tmp_dir)
            app = self._app(artifact_dir, macro_path, tariff_path)

            with TestClient(app) as client:
                response = client.get("/health")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "HEALTHY")
            self.assertTrue(response.json()["models_loaded"])
            self.assertEqual(response.json()["database"], "unconfigured")
            self.assertTrue(response.json()["artifact_version"].startswith("v1:"))
            self.assertEqual(response.json()["dataset_version"], "synthetic-fixture-v1")
            self.assertEqual(response.json()["validation_status"], "exploratory_not_empirically_approved")

    def test_optimize_price_returns_complete_prediction_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir, macro_path, tariff_path = self._build_artifacts(tmp_dir)
            app = self._app(artifact_dir, macro_path, tariff_path)
            payload = {
                "raw_description": "Senior web backend engineer building Python APIs and cloud services.",
                "selected_industry": "web_backend",
                "mentor_country": "ke",
                "client_country": "us",
                "competitiveness_score": 0.6,
                "market_saturation_score": 0.3,
            }

            with TestClient(app) as client:
                response = client.post("/api/v1/optimize-price", json=payload)

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["currency"], "KES")
            self.assertGreaterEqual(body["final_quoted_rate"], body["base_predicted_rate"])
            self.assertGreaterEqual(len(body["nearest_neighbors"]), 1)

    def test_live_corridor_floor_and_fee_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir, macro_path, tariff_path = self._build_artifacts(tmp_dir)
            app = self._app(artifact_dir, macro_path, tariff_path)
            payload = {
                "raw_description": "Senior web backend engineer building Python APIs and cloud services.",
                "selected_industry": "web_backend", "mentor_country": "KE", "client_country": "KE",
            }
            with TestClient(app) as client:
                response = client.post("/api/v1/optimize-price", json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual(body["bilateral_arbitrage_factor"], 1.0)
                self.assertEqual(len(body["nearest_neighbors"]), 5)
                self.assertLessEqual(body["min_quoted_rate"], body["max_quoted_rate"])
                self.assertEqual(body["final_quoted_rate"],
                                 round(body["base_predicted_rate"] + body["mpesa_tariff_surcharge"], 2))
                sigma = app.state.inference_runtime.spatial_indexer.predict_base_rate(
                    self._query_coordinates(app, payload), "web_backend", k=5, epsilon=1e-6,
                )["peer_stddev"]
                self.assertAlmostEqual(body["min_quoted_rate"], max(0.5 * body["base_predicted_rate"],
                                                                    body["base_predicted_rate"] - 0.75 * sigma))
                self.assertAlmostEqual(body["max_quoted_rate"], body["base_predicted_rate"] + 1.25 * sigma)

                requested_floor = (body["base_predicted_rate"] + body["max_quoted_rate"]) / 2
                raised = client.post("/api/v1/optimize-price", json={**payload, "base_rate_floor": requested_floor})
                self.assertEqual(raised.status_code, 200, raised.text)
                self.assertAlmostEqual(raised.json()["min_quoted_rate"], requested_floor)
                self.assertEqual(raised.json()["final_quoted_rate"], body["final_quoted_rate"])

                before = len(app.state.dependencies.repository.list_transactions())
                impossible = client.post("/api/v1/optimize-price", json={**payload, "base_rate_floor": body["max_quoted_rate"] + 1})
                self.assertEqual(impossible.status_code, 422)
                self.assertIn("exceeds", impossible.json()["detail"])
                self.assertEqual(len(app.state.dependencies.repository.list_transactions()), before)
                for value in (-1, "NaN", "Infinity"):
                    self.assertEqual(client.post("/api/v1/optimize-price", json={**payload, "base_rate_floor": value}).status_code, 422)

    @staticmethod
    def _query_coordinates(app, payload):
        from src.macro_arbitrage import fuse_coordinates
        from src.nlp_pipeline import ensure_text_dimensions

        runtime = app.state.inference_runtime
        config = runtime.inference_config
        text = ensure_text_dimensions(runtime.reducer.transform([payload["raw_description"]]))
        metadata = runtime.metadata_normalizer.transform_live_metadata(
            payload["mentor_country"], payload["client_country"], 0.5,
            config["partition_density"][payload["selected_industry"]],
        )
        return fuse_coordinates(text * config["text_weight"], metadata * config["metadata_weight"])

    def test_invalid_optimize_request_returns_422(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir, macro_path, tariff_path = self._build_artifacts(tmp_dir)
            app = self._app(artifact_dir, macro_path, tariff_path)

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/optimize-price",
                    json={"raw_description": "too short"},
                )

            self.assertEqual(response.status_code, 422)

    def test_health_reports_degraded_when_artifacts_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(__file__).resolve().parent.parent
            macro_path = str(repo_root / "tests" / "fixtures" / "raw" / "Mpesa_Tarrifs" / "tarrifs_full_schedule.csv")
            app = create_app(os.path.join(tmp_dir, "missing"), macro_path, macro_path)

            with TestClient(app) as client:
                response = client.get("/health")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "DEGRADED")
            self.assertFalse(response.json()["models_loaded"])
            self.assertIn("Untrusted artifacts", response.json()["readiness_reason"])

    def test_incompatible_feature_manifest_is_unready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir, macro_path, tariff_path = self._build_artifacts(tmp_dir)
            config_path = os.path.join(artifact_dir, "inference_config.json")
            with open(config_path, encoding="utf-8") as handle:
                config = json.load(handle)
            config["metadata_features"][1] = "competitiveness_score"
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(config, handle)
            with TestClient(self._app(artifact_dir, macro_path, tariff_path)) as client:
                self.assertFalse(client.get("/health").json()["models_loaded"])
                self.assertIn("SHA-256 mismatch", client.get("/ready").json()["readiness_reason"])
                self.assertEqual(client.post("/api/v1/optimize-price", json={
                    "raw_description": "Senior web backend engineer",
                    "selected_industry": "web_backend", "mentor_country": "KE", "client_country": "US",
                }).status_code, 503)

    def test_short_vocabulary_still_produces_53d_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir, macro_path, tariff_path = self._build_artifacts(tmp_dir)
            reducer = TextFeatureReducer(n_components=50)
            reducer.fit_transform(["python api engineering", "python backend", "api backend"])
            reducer.save_artifacts(artifact_dir)
            with open(os.path.join(artifact_dir, "inference_config.json"), encoding="utf-8") as handle:
                config = json.load(handle)
            write_manifest(artifact_dir, config, dataset_version="synthetic-fixture-v1",
                           source_type="synthetic proxy fixture", split_policy="synthetic fixed fixture")
            app = self._app(artifact_dir, macro_path, tariff_path)
            with TestClient(app) as client:
                self.assertTrue(client.get("/health").json()["models_loaded"])
                result = client.post("/api/v1/optimize-price", json={
                    "raw_description": "Python backend engineering",
                    "selected_industry": "web_backend", "mentor_country": "KE", "client_country": "US",
                })
                self.assertEqual(result.status_code, 200)


if __name__ == "__main__":
    unittest.main()
