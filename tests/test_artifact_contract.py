"""#95 synthetic engineering parity only; these are not mentor-rate validation tests."""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from src.api_contracts import PricingQueryDTO
from src.artifact_contract import MANIFEST_NAME, file_sha256, write_manifest
from src.macro_arbitrage import ContinuousMetadataNormalizer, fuse_coordinates
from src.nlp_pipeline import TextFeatureReducer, ensure_text_dimensions
from src.serve import create_app
from src.spatial_engine import DomainPartitionedKDTreeIndexer
from src.train_pipeline import evaluate_and_serialize_training
from tests.test_train_pipeline import TrainPipelineTests
from tests.test_serve import ServeApiTests

TARIFF = str(Path(__file__).resolve().parent / "fixtures" / "raw" / "Mpesa_Tarrifs" / "tarrifs_full_schedule.csv")


class ArtifactContractTests(unittest.TestCase):
    def test_export_reload_api_matches_offline_coordinates_rate_and_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            macro, parquet = TrainPipelineTests()._write_input_artifacts(tmp)
            frame = pd.read_parquet(parquet)
            frame.loc[0:5, "industry_partition"] = "mobile"
            frame.loc[6:25, "industry_partition"] = "general_tech"
            frame.to_parquet(parquet, index=False)
            artifacts = os.path.join(tmp, "model")
            evaluate_and_serialize_training(parquet, macro, artifact_dir=artifacts,
                                            k_neighbors=2, minimum_partition_size=5,
                                            enforce_quality_gate=False, dataset_version="synthetic-v1")
            digest = file_sha256(os.path.join(artifacts, MANIFEST_NAME))
            with open(os.path.join(artifacts, MANIFEST_NAME), encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["provenance"]["dataset_sha256"], file_sha256(parquet))
            self.assertEqual(manifest["preprocessing"]["text"]["n_components_requested"], 50)
            with open(os.path.join(artifacts, "inference_config.json"), encoding="utf-8") as handle:
                config = json.load(handle)
            query = PricingQueryDTO(raw_description=str(frame.iloc[0].raw_description), selected_industry="mobile",
                                    mentor_country="KE", client_country="KE", market_saturation_score=0.5)
            bundled = os.path.join(artifacts, "macro_lookup_table.json")
            reducer = TextFeatureReducer.load_artifacts(artifacts)
            scaler = ContinuousMetadataNormalizer.load_artifacts(artifacts, macro_lookup_path=bundled)
            text = ensure_text_dimensions(reducer.transform([query.raw_description]))
            metadata = scaler.transform_live_metadata("KE", "KE", 0.5, config["partition_density"]["mobile"])
            coordinates = fuse_coordinates(text * config["text_weight"], metadata * config["metadata_weight"])
            offline = DomainPartitionedKDTreeIndexer.load_artifacts(artifacts).predict_base_rate(
                coordinates, "mobile", k=2, epsilon=config["idw_epsilon"], allow_fallback=True,
            )
            self.assertEqual(offline["routed_partition"], "general_tech")
            app = create_app(artifacts, macro, TARIFF, trusted_manifest_sha256=digest)
            with TestClient(app) as client:
                health = client.get("/health").json()
                self.assertEqual(health["status"], "HEALTHY")
                self.assertEqual(health["artifact_version"], "v1:" + digest[:12])
                self.assertEqual(health["dataset_version"], "synthetic-v1")
                self.assertIn("proxy", health["source_type"])
                self.assertEqual(health["validation_status"], "exploratory_not_empirically_approved")
                runtime = app.state.inference_runtime
                self.assertIsNotNone(runtime.spatial_indexer)
                with patch.object(runtime.spatial_indexer, "predict_base_rate",
                                  wraps=runtime.spatial_indexer.predict_base_rate) as prediction:
                    for _ in range(2):  # Warmed handoff for #70; no wall-clock performance gate.
                        response = client.post("/api/v1/optimize-price", json=query.model_dump())
                        self.assertEqual(response.status_code, 200, response.text)
                    start = time.perf_counter()
                    response = client.post("/api/v1/optimize-price", json=query.model_dump())
                    warmed_ms = (time.perf_counter() - start) * 1000
                    self.assertGreaterEqual(warmed_ms, 0)
                    actual_vector = prediction.call_args.args[0]
                    np.testing.assert_allclose(actual_vector, coordinates, rtol=1e-9, atol=1e-9)
                    self.assertEqual(prediction.call_args.kwargs["requested_partition"], "mobile")
                    self.assertEqual(prediction.call_args.kwargs["k"], 2)
                    self.assertEqual(prediction.call_args.kwargs["epsilon"], config["idw_epsilon"])
                self.assertEqual(response.json()["base_predicted_rate"], offline["base_predicted_rate"])
                self.assertEqual(len(response.json()["nearest_neighbors"]), offline["k_neighbors_used"])
                self.assertEqual([peer["peer_index"] for peer in response.json()["nearest_neighbors"]],
                                 [peer["peer_index"] for peer in offline["nearest_neighbors"]])

    def test_untrusted_corrupt_and_incompatible_artifacts_are_unready_without_joblib(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts, macro, tariff = ServeApiTests()._build_artifacts(tmp)
            digest = file_sha256(os.path.join(artifacts, MANIFEST_NAME))
            def status(pin):
                app = create_app(artifacts, macro, tariff, trusted_manifest_sha256=pin)
                with patch("src.nlp_pipeline.joblib.load", side_effect=AssertionError("untrusted pickle loaded")):
                    with TestClient(app) as client:
                        self.assertEqual(client.get("/ready").status_code, 503)
                        return client.get("/ready").json()["readiness_reason"]
            self.assertIn("Untrusted", status(None))
            self.assertIn("mismatch", status("0" * 64))
            with open(os.path.join(artifacts, "industry_kdtrees.joblib"), "ab") as handle:
                handle.write(b"corrupted")
            self.assertIn("Corrupted artifact", status(digest))

            # Recreate a valid set, then pin a structurally incompatible schema.
            artifacts, macro, tariff = ServeApiTests()._build_artifacts(tmp)
            manifest_path = os.path.join(artifacts, MANIFEST_NAME)
            with open(manifest_path, encoding="utf-8") as handle:
                manifest = json.load(handle)
            manifest["query_policy"]["k_neighbors"] = 2  # Config still says 5.
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(manifest, handle)
            self.assertIn("query or partition policy", status(file_sha256(manifest_path)))
            manifest["query_policy"]["k_neighbors"] = 5
            manifest["provenance"]["empirically_approved"] = True
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(manifest, handle)
            self.assertIn("Incompatible artifact provenance fields", status(file_sha256(manifest_path)))

            artifacts, macro, tariff = ServeApiTests()._build_artifacts(tmp)
            config_path = os.path.join(artifacts, "inference_config.json")
            with open(config_path, encoding="utf-8") as handle:
                config = json.load(handle)
            config["version"] = 999
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(config, handle)
            digest = write_manifest(artifacts, config, dataset_version="synthetic-fixture-v1",
                                    source_type="synthetic proxy fixture", split_policy="synthetic fixed fixture")
            app = create_app(artifacts, macro, tariff, trusted_manifest_sha256=digest)
            with TestClient(app) as client:
                self.assertEqual(client.get("/ready").status_code, 503)
                self.assertIn("feature schema", client.get("/ready").json()["readiness_reason"])

            artifacts, macro, tariff = ServeApiTests()._build_artifacts(tmp)
            with open(os.path.join(artifacts, "svd_reducer.joblib"), "wb") as handle:
                handle.write(b"not a pickle")
            with open(os.path.join(artifacts, "inference_config.json"), encoding="utf-8") as handle:
                config = json.load(handle)
            digest = write_manifest(artifacts, config, dataset_version="synthetic-fixture-v1",
                                    source_type="synthetic proxy fixture", split_policy="synthetic fixed fixture")
            with TestClient(create_app(artifacts, macro, tariff, trusted_manifest_sha256=digest)) as client:
                self.assertEqual(client.get("/ready").status_code, 503)
                self.assertEqual(client.get("/ready").json()["readiness_reason"], "invalid or corrupted artifact set")


if __name__ == "__main__":
    unittest.main()
