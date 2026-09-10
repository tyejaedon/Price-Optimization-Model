import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

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
        return artifact_dir, macro_lookup_path, tariff_csv_path

    def test_health_reports_ready_when_artifacts_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir, macro_path, tariff_path = self._build_artifacts(tmp_dir)
            app = create_app(artifact_dir, macro_path, tariff_path)

            with TestClient(app) as client:
                response = client.get("/health")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "HEALTHY")
            self.assertTrue(response.json()["models_loaded"])
            self.assertEqual(response.json()["database"], "unconfigured")

    def test_optimize_price_returns_complete_prediction_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir, macro_path, tariff_path = self._build_artifacts(tmp_dir)
            app = create_app(artifact_dir, macro_path, tariff_path)
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

    def test_invalid_optimize_request_returns_422(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact_dir, macro_path, tariff_path = self._build_artifacts(tmp_dir)
            app = create_app(artifact_dir, macro_path, tariff_path)

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


if __name__ == "__main__":
    unittest.main()

