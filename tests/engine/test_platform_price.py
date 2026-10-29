"""``POST /price`` — the Career Mentor OS platform contract (#99).

Runs without model artifacts: ``create_app(inference=...)`` skips artifact
loading and defaults to the in-memory repository, so these tests exercise the
route, the gate, the profile fallback and the response mapping in isolation.
"""

import os
import unittest
from typing import Any, Dict
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api.api_contracts import PricingQueryDTO
from src.api.repository import InMemoryRepository
from src.api.serve import create_app

KEY = "test-platform-key"


def fake_inference(query: PricingQueryDTO) -> Dict[str, Any]:
    """A deterministic stand-in for the KD-tree engine."""
    assert isinstance(query, PricingQueryDTO)
    return {
        "base_predicted_rate": 4700.0,
        "mpesa_tariff_surcharge": 57.0 if query.mentor_country == "KE" else 0.0,
        "final_quoted_rate": 4757.0 if query.mentor_country == "KE" else 4700.0,
        "currency": "KES",
        "mentor_country_iso2": query.mentor_country,
        "nearest_neighbors": [
            {"peer_index": 3, "distance": 0.10, "verified_rate": 4200.0, "similarity_score": 0.91, "idw_weight": 0.5},
            {"peer_index": 7, "distance": 0.25, "verified_rate": 5100.0, "similarity_score": 0.80, "idw_weight": 0.3},
            {"peer_index": 9, "distance": 0.40, "verified_rate": 4800.0, "similarity_score": 0.71, "idw_weight": 0.2},
        ],
    }


INLINE = {
    "mentorId": "mentor-123",
    "raw_description": "Experienced Android developer mentoring mobile teams in Kotlin and Compose.",
    "selected_industry": "mobile",
    "mentor_country": "KE",
    "client_country": "US",
}


class PlatformPriceTests(unittest.TestCase):
    def _client(self, repository: InMemoryRepository = None) -> TestClient:
        app = create_app(inference=fake_inference, repository=repository)
        return TestClient(app)

    def test_disabled_by_default_returns_503(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PLATFORM_PRICE_KEY", None)
            with self._client() as client:
                response = client.post("/price", json=INLINE, headers={"X-Platform-Key": "anything"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("PLATFORM_PRICE_KEY", response.json()["detail"])

    def test_wrong_or_missing_key_is_401(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": KEY}):
            with self._client() as client:
                missing = client.post("/price", json=INLINE)
                wrong = client.post("/price", json=INLINE, headers={"X-Platform-Key": "nope"})
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)

    def test_inline_inputs_return_platform_shape(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": KEY}):
            with self._client() as client:
                response = client.post("/price", json=INLINE, headers={"X-Platform-Key": KEY})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(set(body), {"min", "max", "comparables", "reason"})
        # min/max are the peer spread, widened to contain the quote itself
        self.assertEqual(body["min"], 4200.0)
        self.assertEqual(body["max"], 5100.0)
        self.assertEqual([c["peer_index"] for c in body["comparables"]], [3, 7, 9])
        self.assertIn("4757.00 KES", body["reason"])
        self.assertIn("M-Pesa surcharge", body["reason"])

    def test_profile_fallback_supplies_missing_inputs(self) -> None:
        repo = InMemoryRepository()
        repo.upsert_profile(
            "mentor-123",
            {
                "full_name": "Test Mentor",
                "email": "mentor@example.com",
                "country_code": "KE",
                "metadata": {
                    "raw_description": "Backend engineer mentoring on Python APIs and data pipelines.",
                    "selected_industry": "web_backend",
                },
            },
        )
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": KEY}):
            with self._client(repo) as client:
                # Exactly what the platform sends: the id and nothing else.
                response = client.post("/price", json={"mentorId": "mentor-123"}, headers={"X-Platform-Key": KEY})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["min"], 4200.0)

    def test_unknown_mentor_with_no_inputs_is_422_naming_fields(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": KEY}):
            with self._client() as client:
                response = client.post("/price", json={"mentorId": "nobody"}, headers={"X-Platform-Key": KEY})
        self.assertEqual(response.status_code, 422)
        detail = response.json()["detail"]
        self.assertEqual(detail["mentorId"], "nobody")
        self.assertEqual(detail["missing"], ["mentor_country", "raw_description", "selected_industry"])

    def test_existing_optimize_price_route_is_untouched(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": KEY}):
            with self._client() as client:
                response = client.post(
                    "/api/v1/optimize-price",
                    json={
                        "raw_description": INLINE["raw_description"],
                        "selected_industry": "mobile",
                        "mentor_country": "KE",
                        "client_country": "US",
                    },
                )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["final_quoted_rate"], 4757.0)

    def test_seeded_platform_mentor_resolves_and_quotes(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": KEY}):
            with self._client() as client:
                # Query an in-scope platform mentor by platform_mentor_user_id
                response = client.post(
                    "/price",
                    json={"mentorId": "c61a767b-f0a2-4367-a278-7aa41cda8edc"},
                    headers={"X-Platform-Key": KEY},
                )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(set(body), {"min", "max", "comparables", "reason"})
        self.assertGreater(body["min"], 0.0)
        self.assertGreater(body["max"], 0.0)
        self.assertGreater(len(body["comparables"]), 0)
        self.assertIn("KES", body["reason"])

    def test_seeded_vocational_mentor_returns_outside_scope(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": KEY}):
            with self._client() as client:
                # Query a vocational mentor (Nelson Juma, Electrical & Electronics)
                response = client.post(
                    "/price",
                    json={"mentorId": "b1e66e3b-d3c9-45bf-b788-0c2d9beb0d65"},
                    headers={"X-Platform-Key": KEY},
                )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(set(body), {"min", "max", "comparables", "reason"})
        self.assertEqual(body["min"], 0.0)
        self.assertEqual(body["max"], 0.0)
        self.assertEqual(body["comparables"], [])
        self.assertIn("Outside scope", body["reason"])

    def test_unsupported_partition_returns_outside_scope(self) -> None:
        def failing_inference(query):
            raise ValueError("No trained density for partition 'Culinary & Hospitality'.")

        app = create_app(inference=failing_inference, repository=InMemoryRepository(), seed_platform_profiles=False)
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": KEY}):
            with TestClient(app) as client:
                response = client.post(
                    "/price",
                    json={
                        "mentorId": "any-id",
                        "raw_description": "Experienced culinary chef mentoring cooking staff.",
                        "selected_industry": "Culinary & Hospitality",
                        "mentor_country": "KE",
                    },
                    headers={"X-Platform-Key": KEY},
                )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["min"], 0.0)
        self.assertEqual(body["max"], 0.0)
        self.assertIn("Outside scope", body["reason"])

    def test_root_index_endpoint_returns_online_status(self) -> None:
        with self._client() as client:
            response = client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("POST /price", data["endpoints"]["platform_pricing"])

    def test_mentor_id_whitespace_and_profile_id_lookup(self) -> None:
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": KEY}):
            with self._client() as client:
                # Query with leading/trailing whitespace
                resp_whitespace = client.post(
                    "/price",
                    json={"mentorId": "  c61a767b-f0a2-4367-a278-7aa41cda8edc  "},
                    headers={"X-Platform-Key": KEY},
                )
                self.assertEqual(resp_whitespace.status_code, 200, resp_whitespace.text)
                self.assertGreater(resp_whitespace.json()["min"], 0.0)

                # Query using platform_mentor_profile_id alias (cc2800f6...)
                resp_profile_id = client.post(
                    "/price",
                    json={"mentorId": "cc2800f6-2bda-4075-b61d-201bfab2762b"},
                    headers={"X-Platform-Key": KEY},
                )
                self.assertEqual(resp_profile_id.status_code, 200, resp_profile_id.text)
                self.assertGreater(resp_profile_id.json()["min"], 0.0)

    def test_inline_vocational_category_intercepted_as_outside_scope(self) -> None:
        # Even if inference would return a valid quote, an explicit vocational category must return outside scope
        app = create_app(inference=fake_inference, repository=InMemoryRepository(), seed_platform_profiles=False)
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": KEY}):
            with TestClient(app) as client:
                response = client.post(
                    "/price",
                    json={
                        "mentorId": "unseeded-chef-999",
                        "raw_description": "Master executive chef teaching culinary arts and restaurant management.",
                        "selected_industry": "Culinary & Hospitality",
                        "mentor_country": "KE",
                    },
                    headers={"X-Platform-Key": KEY},
                )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["min"], 0.0)
        self.assertEqual(body["max"], 0.0)
        self.assertEqual(body["comparables"], [])
        self.assertIn("Outside scope", body["reason"])
        self.assertIn("Culinary & Hospitality", body["reason"])


if __name__ == "__main__":
    unittest.main()
