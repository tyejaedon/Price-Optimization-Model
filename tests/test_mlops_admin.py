import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api_contracts import GridSearchConfigDTO
from src.mlops_service import GridSearchStore, MLOpsService
from src.observability import MetricsRegistry
from src.repository import InMemoryRepository
from src.serve import create_app


class MlOpsAdminTests(unittest.TestCase):
    def _build_app(self, tmp_dir: str, runner=None):
        repository = InMemoryRepository()
        service = MLOpsService(
            artifact_dir=os.path.join(tmp_dir, "artifacts"),
            grid_store=GridSearchStore(os.path.join(tmp_dir, "grid.json")),
            retrain_runner=runner,
        )

        def inference(query):
            return {
                "base_predicted_rate": 4500.0,
                "mpesa_tariff_surcharge": 55.0 if query.mentor_country == "KE" else 0.0,
                "final_quoted_rate": 4555.0 if query.mentor_country == "KE" else 4500.0,
                "currency": "KES",
                "mentor_country_iso2": query.mentor_country,
            }

        app = create_app(
            repository=repository,
            mlops=service,
            metrics=MetricsRegistry(),
            inference=inference,
            admin_token="test-admin-token",
        )
        return app, service

    def test_health_inference_and_admin_repository_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            app, _ = self._build_app(tmp_dir)
            client = TestClient(app)

            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "HEALTHY")
            self.assertEqual(health.json()["database"], "memory")

            prediction = client.post(
                "/api/v1/optimize-price",
                json={
                    "raw_description": "Senior Python mentor",
                    "selected_industry": "data_ai",
                    "mentor_country": "ke",
                    "client_country": "us",
                },
            )
            self.assertEqual(prediction.status_code, 200)
            self.assertEqual(prediction.json()["final_quoted_rate"], 4555.0)

            unauthorized = client.get("/api/v1/admin/profiles")
            self.assertEqual(unauthorized.status_code, 403)

            profile = {
                "profile_id": "mentor-1",
                "full_name": "Test Mentor",
                "email": "mentor@example.com",
                "country_code": "KE",
            }
            saved = client.put("/api/v1/admin/profiles/mentor-1", json=profile, headers={"X-Admin-Token": "test-admin-token"})
            self.assertEqual(saved.status_code, 200)
            profiles = client.get("/api/v1/admin/profiles", headers={"X-Admin-Token": "test-admin-token"})
            self.assertEqual(len(profiles.json()), 1)
            history = client.get("/api/v1/admin/history", headers={"X-Admin-Token": "test-admin-token"})
            self.assertEqual(len(history.json()), 1)

    def test_grid_search_is_validated_persisted_and_applied_to_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            app, service = self._build_app(tmp_dir)
            client = TestClient(app)
            response = client.put(
                "/api/v1/admin/grid-search",
                headers={"X-Admin-Token": "test-admin-token"},
                json={
                    "k_neighbors": [3, 10, 20],
                    "text_weight": 1.5,
                    "metadata_weight": 0.5,
                    "idw_epsilon": 0.000001,
                    "minimum_partition_size": 3,
                    "allow_fallback": False,
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["k_neighbors"], [3, 10, 20])
            self.assertEqual(service.get_tuning().text_weight, 1.5)
            weighted = service.weighted_hybrid_coordinates([1.0] * 50, [2.0] * 3)
            self.assertEqual(weighted[0], 1.5)
            self.assertEqual(weighted[-1], 1.0)

            invalid = client.put(
                "/api/v1/admin/grid-search",
                headers={"X-Admin-Token": "test-admin-token"},
                json={"k_neighbors": [0]},
            )
            self.assertEqual(invalid.status_code, 422)

    def test_manual_retrain_publishes_version_manifest(self) -> None:
        def runner(version_dir, config):
            Path(version_dir, "tfidf_vectorizer.joblib").write_text("vectorizer", encoding="utf-8")
            Path(version_dir, "industry_kdtrees.joblib").write_text("tree", encoding="utf-8")
            return {"k_neighbors": list(config.k_neighbors)}

        with tempfile.TemporaryDirectory() as tmp_dir:
            app, _ = self._build_app(tmp_dir, runner=runner)
            client = TestClient(app)
            response = client.post("/api/v1/admin/retrain", headers={"X-Admin-Token": "test-admin-token"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "succeeded")
            active_manifest = Path(tmp_dir, "artifacts", "active_model.json")
            self.assertTrue(active_manifest.exists())
            self.assertEqual(json.loads(active_manifest.read_text(encoding="utf-8"))["result"]["k_neighbors"], [1, 3, 5, 7, 10])

    def test_retraining_lock_returns_busy(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def runner(version_dir, config):
            started.set()
            release.wait(timeout=2.0)
            return {"ok": True}

        with tempfile.TemporaryDirectory() as tmp_dir:
            _, service = self._build_app(tmp_dir, runner=runner)
            first_result = {}
            thread = threading.Thread(target=lambda: first_result.update(service.trigger_retrain()))
            thread.start()
            self.assertTrue(started.wait(timeout=1.0))
            busy = service.trigger_retrain()
            self.assertEqual(busy["status"], "busy")
            release.set()
            thread.join(timeout=2.0)
            self.assertEqual(first_result["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()

