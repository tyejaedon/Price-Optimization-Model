"""M10.5: canonical/legacy wire migration on the protected versioned route."""

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api_contracts import (
    CanonicalPeerMatchDTO,
    CanonicalPredictionResultDTO,
    CanonicalPricingQueryDTO,
    PredictionResultDTO,
)
from src.artifact_contract import MANIFEST_NAME, file_sha256
from src.serve import create_app
from tests.test_container_gateway import FakeFirestore
from tests.test_serve import ServeApiTests


CANONICAL = {
    "mentorId": "fixture-user",
    "rawText": "Senior web backend engineer building Python APIs and cloud services.",
    "industry": "web_backend",
    "mentorCountry": "ke",
    "clientCountry": "us",
    "competitivenessScore": 0.3,
}


class CanonicalContractTests(unittest.TestCase):
    def test_request_defaults_aliases_and_fitted_feature_translation(self):
        query = CanonicalPricingQueryDTO.model_validate({
            **CANONICAL, "baseRateFloor": 0.0, "costOfLivingIndex": 1.25,
        })
        self.assertEqual(query.mentor_country, "KE")
        self.assertEqual(query.client_country, "US")
        self.assertEqual(query.model_dump(by_alias=True)["rawText"], CANONICAL["rawText"])
        inference = query.to_inference_query()
        self.assertEqual(inference.market_saturation_score, 0.3)
        self.assertEqual(inference.cost_of_living_index, 1.25)
        self.assertEqual(inference.base_rate_floor, 0.0)
        self.assertEqual(CanonicalPricingQueryDTO.model_validate({
            key: value for key, value in CANONICAL.items() if key != "competitivenessScore"
        }).competitiveness_score, 0.5)

    def test_strict_canonical_validation_and_missing_text_policy(self):
        for change in (
            {"mentorId": ""}, {"rawText": "short"}, {"rawText": "x" * 2001},
            {"mentorCountry": "USA"}, {"clientCountry": "КE"},
            {"competitivenessScore": 1.01}, {"competitivenessScore": float("nan")},
            {"costOfLivingIndex": 0}, {"costOfLivingIndex": 0.001},
            {"costOfLivingIndex": 1001}, {"costOfLivingIndex": float("inf")},
            {"baseRateFloor": -1}, {"baseRateFloor": float("inf")},
            {"raw_description": CANONICAL["rawText"]},
        ):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                CanonicalPricingQueryDTO.model_validate({**CANONICAL, **change})
        without_text = CanonicalPricingQueryDTO.model_validate({
            key: value for key, value in CANONICAL.items() if key != "rawText"
        })
        with self.assertRaisesRegex(ValueError, "rawText is required"):
            without_text.to_inference_query()

    def test_response_rejects_fabrication_and_invalid_rates(self):
        peer = {"listingId": "listing-real", "verifiedRate": 4900, "similarityScore": 0.8,
                "euclideanDistance": 0.25}
        self.assertEqual(CanonicalPeerMatchDTO.model_validate(peer).listing_id, "listing-real")
        for change in ({"listingId": ""}, {"similarityScore": 1.1},
                       {"euclideanDistance": float("nan")}, {"peer_index": 1}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                CanonicalPeerMatchDTO.model_validate({**peer, **change})

        legacy = PredictionResultDTO.model_validate({
            "base_predicted_rate": 100, "mpesa_tariff_surcharge": 7,
            "final_quoted_rate": 107, "min_quoted_rate": 90, "max_quoted_rate": 120,
            "bilateral_arbitrage_factor": 0.8,
            "nearest_neighbors": [
                {"peer_index": 3, "distance": 0.25, "verified_rate": 110,
                 "similarity_score": 0.8, "listing_id": "listing-real", "job_title": "Engineer"},
                {"peer_index": 4, "distance": 0.5, "verified_rate": 90, "similarity_score": 0.67},
            ],
        })
        result = CanonicalPredictionResultDTO.from_legacy(legacy)
        self.assertEqual(result.k_neighbors_used, 2)
        self.assertEqual(len(result.comparables), 1)
        self.assertEqual(result.comparables[0].listing_id, "listing-real")
        self.assertEqual(result.comparables[0].job_title, "Engineer")
        self.assertEqual(result.confidence_score, 0.0)
        self.assertIn("unavailable", result.reason)
        self.assertIsNotNone(result.timestamp.tzinfo)
        with self.assertRaises(ValidationError):
            CanonicalPredictionResultDTO.model_validate({
                **result.model_dump(by_alias=True), "minQuotedRate": 125,
            })
        with self.assertRaises(ValidationError):
            CanonicalPredictionResultDTO.model_validate({
                **result.model_dump(by_alias=True), "finalQuotedRate": 108,
            })


class CanonicalApiTests(unittest.TestCase):
    def test_canonical_quote_legacy_compatibility_health_and_openapi(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir, macro, tariff = ServeApiTests()._build_artifacts(tmp)
            app = create_app(artifact_dir, macro, tariff, trusted_manifest_sha256=file_sha256(
                os.path.join(artifact_dir, MANIFEST_NAME)))
            with TestClient(app) as client:
                health = client.get("/health").json()
                self.assertEqual(health["service"], "pricing-engine")
                self.assertEqual(health["unit"], "KES/hour")
                self.assertEqual(health["version"], "1.0.0")
                self.assertEqual(health["modelsLoaded"], health["models_loaded"])
                operation = client.get("/openapi.json").json()["paths"]["/api/v1/optimize-price"]["post"]
                request_schema = str(operation["requestBody"]["content"]["application/json"]["schema"])
                response_schema = str(operation["responses"]["200"]["content"]["application/json"]["schema"])
                self.assertIn("CanonicalPricingQueryDTO", request_schema)
                self.assertIn("PricingQueryDTO", request_schema)
                self.assertIn("CanonicalPredictionResultDTO", response_schema)
                self.assertIn("PredictionResultDTO", response_schema)
                self.assertIn("deprecated", operation["description"])

                canonical = client.post("/api/v1/optimize-price", json=CANONICAL)
                self.assertEqual(canonical.status_code, 200, canonical.text)
                body = canonical.json()
                self.assertEqual(set(body), {"basePredictedRate", "mpesaTariffSurcharge", "finalQuotedRate",
                                             "minQuotedRate", "maxQuotedRate", "kNeighborsUsed", "bilateralArbitrageFactor",
                                             "confidenceScore", "comparables", "reason", "timestamp"})
                self.assertEqual(body["kNeighborsUsed"], 5)
                self.assertEqual(body["comparables"], [])  # row indices are NOT listing IDs
                self.assertEqual(body["confidenceScore"], 0.0)  # not empirically calibrated
                self.assertLessEqual(body["minQuotedRate"], body["maxQuotedRate"])
                self.assertEqual(body["finalQuotedRate"],
                                 round(body["basePredictedRate"] + body["mpesaTariffSurcharge"], 2))
                self.assertIn("Kenyan M-Pesa fee", body["reason"])
                self.assertIn("unavailable", body["reason"])
                legacy = client.post("/api/v1/optimize-price", json={
                    "mentorId": "fixture-user", "raw_description": CANONICAL["rawText"],
                    "selected_industry": "web_backend", "mentor_country": "ke", "client_country": "us",
                    "market_saturation_score": 0.3,
                })
                self.assertEqual(legacy.status_code, 200, legacy.text)
                self.assertEqual(legacy.headers["Deprecation"], "true")
                self.assertEqual(legacy.json()["base_predicted_rate"], body["basePredictedRate"])
                self.assertEqual(legacy.json()["min_quoted_rate"], body["minQuotedRate"])
                self.assertEqual(len(legacy.json()["nearest_neighbors"]), 5)
                self.assertEqual(len(app.state.dependencies.repository.list_transactions()), 2)

                override = client.post("/api/v1/optimize-price", json={**CANONICAL, "costOfLivingIndex": 1.25})
                self.assertEqual(override.status_code, 200, override.text)
                self.assertNotEqual(override.json()["bilateralArbitrageFactor"], body["bilateralArbitrageFactor"])
                self.assertEqual(app.state.inference_runtime.metadata_normalizer.feature_names,
                                 ("bilateral_arbitrage_factor", "market_saturation_score", "industry_relative_density"))

                count = len(app.state.dependencies.repository.list_transactions())
                for payload in (
                    {**CANONICAL, "baseRateFloor": body["maxQuotedRate"] + 1e6},
                    {key: value for key, value in CANONICAL.items() if key != "rawText"},
                    {**CANONICAL, "mentorCountry": "123"},
                    {**CANONICAL, "raw_description": CANONICAL["rawText"]},
                ):
                    with self.subTest(payload=payload):
                        self.assertEqual(client.post("/api/v1/optimize-price", json=payload).status_code, 422)
                self.assertEqual(len(app.state.dependencies.repository.list_transactions()), count)

    def test_missing_artifacts_and_missing_canonical_corridor_return_503(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(artifact_dir=os.path.join(tmp, "missing"))
            with TestClient(app) as client:
                self.assertFalse(client.get("/health").json()["modelsLoaded"])
                response = client.post("/api/v1/optimize-price", json=CANONICAL)
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["detail"], client.get("/health").json()["readiness_reason"])

        app = create_app(inference=lambda query: {
            "base_predicted_rate": 100, "mpesa_tariff_surcharge": 0, "final_quoted_rate": 100,
        })
        with TestClient(app) as client:
            self.assertEqual(client.post("/api/v1/optimize-price", json=CANONICAL).status_code, 503)
            self.assertEqual(app.state.dependencies.repository.list_transactions(), [])

    def test_canonical_auth_binding_and_audit(self):
        repository = FakeFirestore()
        with tempfile.TemporaryDirectory() as tmp:
            artifacts, macro, tariff = ServeApiTests()._build_artifacts(tmp)
            app = create_app(artifacts, macro, tariff, repository=repository,
                             trusted_manifest_sha256=file_sha256(os.path.join(artifacts, MANIFEST_NAME)),
                             token_verifier=lambda token: {"uid": "fixture-user"} if token == "valid" else {})
            with TestClient(app) as client:
                headers = {"Authorization": "Bearer valid"}
                self.assertEqual(client.post("/api/v1/optimize-price", json=CANONICAL).status_code, 401)
                self.assertEqual(client.post("/api/v1/optimize-price", json=CANONICAL,
                                             headers={"Authorization": "Bearer bad"}).status_code, 401)
                self.assertEqual(client.post("/api/v1/optimize-price", json={**CANONICAL, "mentorId": "other"},
                                             headers=headers).status_code, 403)
                self.assertEqual(repository.list_transactions(), [])
                self.assertEqual(client.post("/api/v1/optimize-price", json=CANONICAL,
                                             headers=headers).status_code, 200)
                self.assertEqual(repository.list_transactions()[0]["mentor_id"], "fixture-user")

    def test_verified_kenyan_tariff_boundaries_and_non_kenyan_bypass(self):
        repository = FakeFirestore()
        repository.upsert_profile("foreign-mentor", {"auth_uid": "foreign-owner", "full_name": "US Mentor",
                                                     "email": "foreign@example.com", "country_code": "US"})
        with tempfile.TemporaryDirectory() as tmp:
            artifacts, macro, tariff = ServeApiTests()._build_artifacts(tmp)
            app = create_app(artifacts, macro, tariff, repository=repository,
                             trusted_manifest_sha256=file_sha256(os.path.join(artifacts, MANIFEST_NAME)),
                             trusted_tariff_sha256=file_sha256(tariff),
                             token_verifier=lambda token: {"uid": "fixture-user" if token == "kenyan" else "foreign-owner"}
                             if token in ("kenyan", "foreign") else {})
            with TestClient(app) as client:
                def quote(base, *, foreign=False, floor=None):
                    payload = ({**CANONICAL, "mentorId": "foreign-mentor", "mentorCountry": "US", "clientCountry": "US"}
                               if foreign else {**CANONICAL, "clientCountry": "KE"})
                    if floor is not None:
                        payload["baseRateFloor"] = floor
                    with patch("src.spatial_engine.DomainPartitionedKDTreeIndexer.predict_base_rate", return_value={
                        "base_predicted_rate": base, "peer_stddev": 0.0,
                        "nearest_neighbors": [{"peer_index": 0, "distance": 0, "verified_rate": base,
                                               "similarity_score": 1}],
                    }):
                        return client.post("/api/v1/optimize-price", json=payload,
                                           headers={"Authorization": "Bearer foreign" if foreign else "Bearer kenyan"})

                tiers = (
                    (1, 49, 0), (50, 100, 0), (101, 500, 7), (501, 1000, 13),
                    (1001, 1500, 23), (1501, 2500, 33), (2501, 3500, 53),
                    (3501, 5000, 57), (5001, 7500, 78), (7501, 10000, 90),
                    (10001, 15000, 100), (15001, 20000, 105),
                    (20001, 35000, 108), (35001, 50000, 108), (50001, 250000, 108),
                )
                for minimum, maximum, fee in tiers:
                    for base in (minimum, maximum):
                        with self.subTest(base=base):
                            response = quote(base)
                            self.assertEqual(response.status_code, 200, response.text)
                            body = response.json()
                            self.assertEqual(body["basePredictedRate"], base)
                            self.assertEqual(body["mpesaTariffSurcharge"], fee)
                            self.assertEqual(body["finalQuotedRate"], round(base + fee, 2))
                            self.assertEqual(body["minQuotedRate"], base)  # corridor and floor are fee-free
                            self.assertEqual(body["maxQuotedRate"], base)
                            audit = repository.list_transactions()[-1]
                            self.assertEqual(audit["base_predicted_rate"], base)
                            self.assertEqual(audit["mpesa_tariff_surcharge"], fee)
                            self.assertEqual(audit["final_quoted_rate"], body["finalQuotedRate"])
                            self.assertEqual(audit["tariff_schedule_sha256"], file_sha256(tariff))
                for base, fee in ((49.01, 0), (100.01, 7), (20000.01, 108), (50000.01, 108)):
                    with self.subTest(base=base):
                        response = quote(base)
                        self.assertEqual(response.status_code, 200, response.text)
                        body = response.json()
                        self.assertEqual(body["basePredictedRate"], base)
                        self.assertEqual(body["mpesaTariffSurcharge"], fee)
                        self.assertEqual(body["finalQuotedRate"], round(base + fee, 2))
                        self.assertEqual(body["minQuotedRate"], base)  # corridor and floor are fee-free
                        self.assertEqual(body["maxQuotedRate"], base)

                before = len(repository.list_transactions())
                self.assertEqual(quote(250000.01).status_code, 503)
                self.assertEqual(quote(5000, floor=5001).status_code, 422)
                self.assertEqual(len(repository.list_transactions()), before)
                foreign = quote(5000, foreign=True)
                self.assertEqual(foreign.status_code, 200, foreign.text)
                self.assertEqual(foreign.json()["mpesaTariffSurcharge"], 0)
                self.assertEqual(foreign.json()["finalQuotedRate"], 5000)
                self.assertIn("No Kenyan M-Pesa fee", foreign.json()["reason"])
                self.assertEqual(client.post("/api/v1/optimize-price", json=CANONICAL,
                                             headers={"Authorization": "Bearer foreign"}).status_code, 403)

    def test_missing_or_untrusted_tariff_fails_ready_and_never_audits(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts, macro, tariff = ServeApiTests()._build_artifacts(tmp)
            for path, pin, expected_reason in (
                (os.path.join(tmp, "missing.csv"), None, "missing tariff schedule"),
                (tariff, "0" * 64, "invalid or untrusted tariff schedule"),
            ):
                with self.subTest(path=path, pin=pin):
                    repository = FakeFirestore()
                    app = create_app(artifacts, macro, path, repository=repository,
                                     trusted_manifest_sha256=file_sha256(os.path.join(artifacts, MANIFEST_NAME)),
                                     trusted_tariff_sha256=pin, token_verifier=lambda token: {"uid": "fixture-user"})
                    with TestClient(app) as client:
                        self.assertEqual(client.get("/ready").status_code, 503)
                        self.assertEqual(client.get("/ready").json()["readiness_reason"], expected_reason)
                        result = client.post("/api/v1/optimize-price", json=CANONICAL,
                                             headers={"Authorization": "Bearer valid"})
                        self.assertEqual(result.status_code, 503, result.text)
                        self.assertEqual(repository.list_transactions(), [])


if __name__ == "__main__":
    unittest.main()
