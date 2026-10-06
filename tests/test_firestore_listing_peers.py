"""Issue #71: real root listing provenance and mentor UID ownership; no cloud needed."""

import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api_contracts import ServiceListingDTO
from src.artifact_contract import MANIFEST_NAME, file_sha256
from src.nlp_pipeline import TextFeatureReducer, ensure_text_dimensions
from src.repository import FirestoreRepository, InMemoryRepository, RepositoryError
from src.serve import create_app
from src.spatial_engine import DomainPartitionedKDTreeIndexer
from src.train_pipeline import (
    _verified_listing_provenance, build_stratified_splits,
    evaluate_and_serialize_training, load_harmonized_parquet,
)
from tests.test_pricing_audit import FakeFirestoreClient
from tests.test_train_pipeline import TrainPipelineTests


MENTOR = {"auth_uid": "firebase-owner", "full_name": "Test Mentor", "email": "mentor@example.com",
          "country_code": "KE"}
LISTING = {"mentor_id": "mentor-123", "industry_id": "web_backend", "title": "Backend mentor",
           "raw_description": "Experienced backend developer mentoring teams in Python APIs.",
           "latent_svd_vector": [0.0] * 50, "verified_rate": 3800.0, "is_active": True}


class RootListingRepositoryTests(unittest.TestCase):
    def test_memory_and_fake_firestore_use_root_paths_and_enforce_identity(self):
        for repository in (InMemoryRepository(), FirestoreRepository(client=FakeFirestoreClient())):
            with self.subTest(adapter=type(repository).__name__):
                self.assertIsNone(repository.get_mentor("mentor-123", "firebase-owner"))
                self.assertIsNone(repository.get_listing("listing-abc"))
                repository.upsert_profile("mentor-123", MENTOR)
                self.assertEqual(repository.get_mentor("mentor-123", "firebase-owner")["country_code"], "KE")
                with self.assertRaises(RepositoryError):
                    repository.get_mentor("mentor-123", "other-owner")
                with self.assertRaises(RepositoryError):
                    repository.upsert_profile("mentor-123", {**MENTOR, "auth_uid": "other-owner"})
                with self.assertRaises(ValidationError):
                    repository.upsert_profile("bad-country", {**MENTOR, "country_code": "КE"})
                stored = repository.upsert_listing("listing-abc", LISTING)
                self.assertEqual(stored["listing_id"], "listing-abc")
                self.assertEqual(len(stored["latent_svd_vector"]), 50)
                stored["latent_svd_vector"][0] = 99.0
                self.assertEqual(repository.get_listing("listing-abc")["latent_svd_vector"][0], 0.0)
                repository.upsert_profile("another-mentor", {**MENTOR, "auth_uid": "another-owner"})
                with self.assertRaises(RepositoryError):
                    repository.upsert_listing("listing-abc", {**LISTING, "mentor_id": "another-mentor"})
                with self.assertRaises(RepositoryError):
                    repository.upsert_listing("missing-parent", {**LISTING, "mentor_id": "unknown"})
                with self.assertRaises(RepositoryError):
                    repository.upsert_listing("nested/id", LISTING)
                with self.assertRaises(RepositoryError):
                    repository.upsert_listing("listing-abc", {**LISTING, "listing_id": "other"})
                if isinstance(repository, FirestoreRepository):
                    fake = repository._client
                    self.assertIn("mentor-123", fake.collection("mentors").documents)
                    self.assertEqual(set(fake.collection("service_listings").documents), {"listing-abc"})
                    self.assertNotIn("service_listings", fake.collection("mentors").documents["mentor-123"])
                    self.assertNotIn("auth_uid", fake.collection("service_listings").documents["listing-abc"])

    def test_listing_schema_rejects_unverified_or_malformed_peer_fields(self):
        for change in ({"latent_svd_vector": [0.0] * 49},
                       {"latent_svd_vector": [0.0] * 49 + [float("nan")]},
                       {"latent_svd_vector": [0.0] * 49 + [1]},
                       {"latent_svd_vector": [0.0] * 49 + [True]},
                       {"latent_svd_vector": "[0.0]"},
                       {"verified_rate": float("inf")}, {"verified_rate": 0},
                       {"industry_id": "not_a_partition"}, {"raw_description": "short"},
                       {"auth_uid": "secret-user-data"}):
            with self.subTest(change=str(change)[:80]), self.assertRaises(ValidationError):
                ServiceListingDTO.model_validate({**LISTING, "listing_id": "listing-abc", **change})

    def test_protected_pricing_uses_stored_owner_not_body_id_and_rejects_missing_or_inactive(self):
        repository = FirestoreRepository(client=FakeFirestoreClient())
        repository.upsert_profile("mentor-123", MENTOR)
        repository.upsert_listing("listing-abc", LISTING)
        calls = []

        def inference(query):
            calls.append(query)
            return {"base_predicted_rate": 3800.0, "mpesa_tariff_surcharge": 0.0,
                    "final_quoted_rate": 3800.0, "min_quoted_rate": 3700.0, "max_quoted_rate": 4000.0,
                    "bilateral_arbitrage_factor": 1.0,
                    "nearest_neighbors": [{"peer_index": 0, "distance": 0.0,
                                           "similarity_score": 1.0, "verified_rate": 3800.0,
                                           "listing_id": "listing-abc", "job_title": "Backend mentor"}]}

        app = create_app(repository=repository, inference=inference,
                         token_verifier=lambda token: {"uid": "firebase-owner"} if token == "valid" else {})
        query = {"mentorId": "mentor-123", "rawText": LISTING["raw_description"],
                 "industry": "web_backend", "mentorCountry": "KE", "clientCountry": "KE"}
        headers = {"Authorization": "Bearer valid"}
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/v1/optimize-price", json=query).status_code, 401)
            self.assertEqual(client.post("/api/v1/optimize-price", json={**query, "mentorId": "other"},
                                         headers=headers).status_code, 403)
            self.assertEqual(client.post("/api/v1/optimize-price", json={**query, "mentorCountry": "US"},
                                         headers=headers).status_code, 422)
            self.assertEqual(calls, [])
            self.assertEqual(repository.list_transactions(), [])
            response = client.post("/api/v1/optimize-price", json=query, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["comparables"][0]["listingId"], "listing-abc")
            self.assertEqual(response.json()["comparables"][0]["jobTitle"], "Backend mentor")
            self.assertEqual(repository.list_transactions()[0]["mentor_id"], "mentor-123")
            self.assertEqual(repository.list_transactions()[0]["auth_uid"], "firebase-owner")
            repository.upsert_profile("mentor-123", {**MENTOR, "account_status": "inactive"})
            self.assertEqual(client.post("/api/v1/optimize-price", json=query, headers=headers).status_code, 403)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(repository.list_transactions()), 1)


class TrainingListingPeerTests(unittest.TestCase):
    def test_training_requires_real_matching_active_listing_documents(self):
        repository = InMemoryRepository()
        repository.upsert_profile("mentor-123", MENTOR)
        frame = pd.DataFrame([{"listing_id": "listing-abc", "raw_description": LISTING["raw_description"],
                               "industry_partition": "web_backend", "job_title": "Backend mentor"},
                              {"listing_id": None, "raw_description": "Unlisted proxy peer",
                               "industry_partition": "web_backend", "job_title": "Proxy"}])
        repository.upsert_listing("listing-abc", LISTING)
        rates = np.array([3800.0, 1000.0])
        self.assertEqual(_verified_listing_provenance(frame, rates, repository),
                         (["listing-abc", None], ["Backend mentor", None]))
        reducer = TextFeatureReducer(n_components=50)
        reducer.fit_transform([str(LISTING["raw_description"]), "Unlisted proxy peer", "Another backend peer"])
        with self.assertRaisesRegex(ValueError, "SVD vector"):
            _verified_listing_provenance(frame, rates, repository, reducer)
        with self.assertRaisesRegex(ValueError, "repository is required"):
            _verified_listing_provenance(frame, rates, None)
        for changed in ({"raw_description": "A different description from the published listing."},
                        {"industry_partition": "mobile"}, {"job_title": "Other title"}):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "does not match"):
                _verified_listing_provenance(frame.assign(**changed), rates, repository)
        with self.assertRaisesRegex(ValueError, "does not match"):
            _verified_listing_provenance(frame, np.array([3900.0, 1000.0]), repository)
        repository.upsert_listing("listing-abc", {**LISTING, "is_active": False})
        with self.assertRaisesRegex(ValueError, "inactive"):
            _verified_listing_provenance(frame, rates, repository)

    def test_exported_kdtree_preserves_only_root_backed_training_peers(self):
        with tempfile.TemporaryDirectory() as tmp:
            macro, parquet = TrainPipelineTests()._write_input_artifacts(tmp)
            frame = pd.read_parquet(parquet)
            frame["listing_id"] = pd.Series([f"stored-{i}" if i < 12 else None for i in range(len(frame))])
            frame["job_title"] = ["Technical mentor" if i < 12 else None for i in range(len(frame))]
            frame.to_parquet(parquet, index=False)
            repository = InMemoryRepository()
            repository.upsert_profile("mentor-123", MENTOR)
            train = build_stratified_splits(load_harmonized_parquet(parquet)).train
            reducer = TextFeatureReducer(n_components=50, max_features=12000)
            text_vectors = ensure_text_dimensions(reducer.fit_transform(train["raw_description"].tolist()))
            by_record_id = dict(zip(train["record_id"], text_vectors.tolist()))
            for i, row in frame.head(12).iterrows():
                repository.upsert_listing(f"stored-{i}", {
                    "mentor_id": "mentor-123", "industry_id": row["industry_partition"],
                    "title": row["job_title"], "raw_description": row["raw_description"],
                    "latent_svd_vector": by_record_id.get(i, [0.0] * 50),
                    "verified_rate": float(row["harmonized_hourly_rate"]),
                })
            with self.assertRaisesRegex(ValueError, "repository is required"):
                evaluate_and_serialize_training(parquet, macro, artifact_dir=os.path.join(tmp, "no-repository"),
                                                enforce_quality_gate=False)
            artifacts = os.path.join(tmp, "verified")
            evaluate_and_serialize_training(parquet, macro, artifact_dir=artifacts,
                                            enforce_quality_gate=False, listing_repository=repository)
            expected = set(train["listing_id"].dropna())
            self.assertTrue(expected)
            indexer = DomainPartitionedKDTreeIndexer.load_artifacts(artifacts)
            actual = {listing_id for ids in indexer.partition_listing_ids.values()
                      for listing_id in ids if listing_id is not None}
            self.assertEqual(actual, expected)
            for partition, ids in indexer.partition_listing_ids.items():
                positions = [i for i, listing_id in enumerate(ids) if listing_id is not None]
                for i in positions:
                    listing_id = ids[i]
                    assert listing_id is not None
                    peer = repository.get_listing(listing_id)
                    self.assertEqual(indexer.partition_verified_rates[partition][i], peer["verified_rate"])
                    self.assertEqual(indexer.partition_job_titles[partition][i], peer["title"])
            self.assertLess(len(actual), len(train))  # proxy rows never acquire fabricated listing IDs

            tariff = str(Path(__file__).parent / "fixtures" / "raw" / "Mpesa_Tarrifs" / "tarrifs_full_schedule.csv")
            app = create_app(artifacts, macro, tariff, repository=repository,
                             trusted_manifest_sha256=file_sha256(os.path.join(artifacts, MANIFEST_NAME)))
            sample = train.loc[train["listing_id"].notna()].iloc[0]
            with TestClient(app) as client:
                self.assertTrue(client.get("/health").json()["models_loaded"])
                result = client.post("/api/v1/optimize-price", json={
                    "mentorId": "mentor-123", "rawText": sample["raw_description"],
                    "industry": sample["industry_partition"], "mentorCountry": "KE", "clientCountry": "KE",
                })
                self.assertEqual(result.status_code, 200, result.text)
                comparables = result.json()["comparables"]
                self.assertTrue(comparables)
                self.assertEqual(comparables[0]["listingId"], sample["listing_id"])
                for comparable in comparables:
                    self.assertIn(comparable["listingId"], expected)
                    stored = repository.get_listing(comparable["listingId"])
                    self.assertEqual(comparable["verifiedRate"], stored["verified_rate"])
                    self.assertEqual(comparable["jobTitle"], stored["title"])


if __name__ == "__main__":
    unittest.main()
