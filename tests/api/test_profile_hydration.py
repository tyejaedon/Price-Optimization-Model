"""Issue #84 / M11.4: Hydrate missing pricing profile fields from verified Firestore mentor.

Tests cover:
- Resolving /mentors/{mentor_id} through repository boundary requiring verified UID
- Hydrating missing rawText and country from verified Firestore mentor and root service listings
- Deterministic listing selection when multiple active listings exist
- Targeted listingId hydration and industry/active checks
- Explicit request overrides taking precedence over Firestore attributes
- Cost of living index bounds validation and hydration
- Failing explicitly on missing, inactive or inconsistent mentor/listing data
- Preventing identity crossover (listing belonging to another mentor)
- Service unavailable behavior when repository fails
- Verifying audits are scheduled ONLY on verified success, never on hydration/validation errors
"""

import math
import tempfile
import unittest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api.api_contracts import CanonicalPricingQueryDTO, PricingQueryDTO
from src.api.repository import FirestoreRepository, InMemoryRepository, RepositoryError
from src.api.serve import create_app
from tests.api.test_pricing_audit import FakeFirestoreClient
from tests.api.test_serve import ServeApiTests


MENTOR_DATA = {
    "auth_uid": "firebase-uid-alice",
    "full_name": "Alice Mentor",
    "email": "alice@example.com",
    "country_code": "KE",
    "account_status": "active",
    "cost_of_living_index": 42.1,
}

LISTING_DATA = {
    "mentor_id": "mentor-alice",
    "industry_id": "web_backend",
    "title": "Backend Engineering Mentor",
    "raw_description": "Experienced backend developer mentoring teams in Python APIs and microservices.",
    "latent_svd_vector": [0.0] * 50,
    "verified_rate": 3500.0,
    "is_active": True,
}


class ProfileHydrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.artifact_dir, cls.macro_path, cls.tariff_path = ServeApiTests()._build_artifacts(cls._tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _create_app(self, repository, verifier=None, inference=None):
        token_verifier = verifier or (lambda t: {"uid": "firebase-uid-alice"} if t == "valid-token" else {})
        inf = inference or (lambda q: {
            "base_predicted_rate": 3500.0,
            "mpesa_tariff_surcharge": 55.0,
            "final_quoted_rate": 3555.0,
            "min_quoted_rate": 3200.0,
            "max_quoted_rate": 4000.0,
            "bilateral_arbitrage_factor": 1.0,
            "nearest_neighbors": [{
                "peer_index": 0, "distance": 0.1, "verified_rate": 3500.0, "similarity_score": 0.9,
            }],
        })
        return create_app(
            artifact_dir=self.artifact_dir,
            macro_lookup_path=self.macro_path,
            tariff_csv_path=self.tariff_path,
            repository=repository,
            token_verifier=token_verifier,
            inference=inf,
        )

    def test_repository_list_listings_for_mentor(self):
        for repo in (InMemoryRepository(), FirestoreRepository(client=FakeFirestoreClient())):
            with self.subTest(adapter=type(repo).__name__):
                repo.upsert_profile("mentor-alice", MENTOR_DATA)
                repo.upsert_profile("mentor-bob", {**MENTOR_DATA, "auth_uid": "uid-bob"})
                self.assertEqual(repo.list_listings_for_mentor("mentor-alice"), [])

                repo.upsert_listing("listing-1", {**LISTING_DATA, "mentor_id": "mentor-alice"})
                repo.upsert_listing("listing-2", {**LISTING_DATA, "mentor_id": "mentor-alice", "industry_id": "data_ai"})
                repo.upsert_listing("listing-3", {**LISTING_DATA, "mentor_id": "mentor-bob"})

                alice_listings = repo.list_listings_for_mentor("mentor-alice")
                self.assertEqual({l["listing_id"] for l in alice_listings}, {"listing-1", "listing-2"})
                bob_listings = repo.list_listings_for_mentor("mentor-bob")
                self.assertEqual({l["listing_id"] for l in bob_listings}, {"listing-3"})

                with self.assertRaises(RepositoryError):
                    repo.list_listings_for_mentor("")
                with self.assertRaises(RepositoryError):
                    repo.list_listings_for_mentor("invalid/id")

    def test_hydrate_missing_raw_text_and_country_from_service_listing(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", MENTOR_DATA)
        repo.upsert_listing("listing-1", LISTING_DATA)

        app = self._create_app(repo)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        # Request omits rawText and mentorCountry
        query = {
            "mentorId": "mentor-alice",
            "industry": "web_backend",
            "clientCountry": "US",
        }
        response = client.post("/api/v1/optimize-price", json=query, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["finalQuotedRate"], 3555.0)

        # Audit must be recorded with verified mentor_id, auth_uid and hydrated listing_id
        txs = repo.list_transactions()
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]["mentor_id"], "mentor-alice")
        self.assertEqual(txs[0]["auth_uid"], "firebase-uid-alice")
        self.assertEqual(txs[0]["listing_id"], "listing-1")
        self.assertEqual(txs[0]["mentor_country_code"], "KE")

    def test_deterministic_listing_selection_multiple_listings(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", MENTOR_DATA)
        # 3 listings in web_backend, out of alphabetical order
        repo.upsert_listing("listing-z", {**LISTING_DATA, "raw_description": "Z" * 30})
        repo.upsert_listing("listing-a", {**LISTING_DATA, "raw_description": "A" * 30})
        repo.upsert_listing("listing-m", {**LISTING_DATA, "raw_description": "M" * 30})

        captured = []
        def inf(q):
            captured.append(q)
            return {
                "base_predicted_rate": 3500.0, "mpesa_tariff_surcharge": 55.0,
                "final_quoted_rate": 3555.0, "min_quoted_rate": 3200.0, "max_quoted_rate": 4000.0,
                "bilateral_arbitrage_factor": 1.0,
                "nearest_neighbors": [{"peer_index": 0, "distance": 0.1, "verified_rate": 3500.0, "similarity_score": 0.9}],
            }

        app = self._create_app(repo, inference=inf)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        query = {"mentorId": "mentor-alice", "industry": "web_backend", "clientCountry": "US"}
        response = client.post("/api/v1/optimize-price", json=query, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        # Alphabetical first is listing-a
        self.assertEqual(captured[0].raw_description, "A" * 30)
        self.assertEqual(repo.list_transactions()[0]["listing_id"], "listing-a")

        # Inactive listing-a should be skipped, picking listing-m next
        repo.upsert_listing("listing-a", {**LISTING_DATA, "raw_description": "A" * 30, "is_active": False})
        response2 = client.post("/api/v1/optimize-price", json=query, headers=headers)
        self.assertEqual(response2.status_code, 200, response2.text)
        self.assertEqual(captured[1].raw_description, "M" * 30)
        self.assertEqual(repo.list_transactions()[1]["listing_id"], "listing-m")

    def test_targeted_listing_id_hydration(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", MENTOR_DATA)
        repo.upsert_listing("listing-target", {
            **LISTING_DATA,
            "raw_description": "Targeted listing description for specific mentoring offering.",
            "market_competitiveness": 0.85,
            "base_rate_floor": 2800.0,
        })

        captured = []
        def inf(q):
            captured.append(q)
            return {
                "base_predicted_rate": 3500.0, "mpesa_tariff_surcharge": 55.0,
                "final_quoted_rate": 3555.0, "min_quoted_rate": 3200.0, "max_quoted_rate": 4000.0,
                "bilateral_arbitrage_factor": 1.0,
                "nearest_neighbors": [{"peer_index": 0, "distance": 0.1, "verified_rate": 3500.0, "similarity_score": 0.9}],
            }

        app = self._create_app(repo, inference=inf)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        query = {
            "mentorId": "mentor-alice",
            "listingId": "listing-target",
            "clientCountry": "US",
        }
        response = client.post("/api/v1/optimize-price", json=query, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        # Verified hydrated fields from targeted listing
        self.assertEqual(captured[0].raw_description, "Targeted listing description for specific mentoring offering.")
        self.assertEqual(captured[0].selected_industry, "web_backend")
        self.assertEqual(captured[0].market_saturation_score, 0.85)
        self.assertEqual(captured[0].base_rate_floor, 2800.0)
        self.assertEqual(repo.list_transactions()[0]["listing_id"], "listing-target")

    def test_explicit_request_overrides_firestore_attributes(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", {**MENTOR_DATA, "cost_of_living_index": 42.1})
        repo.upsert_listing("listing-1", {
            **LISTING_DATA,
            "raw_description": "Default listing description stored in Firestore.",
            "market_competitiveness": 0.2,
            "base_rate_floor": 2000.0,
        })

        captured = []
        def inf(q):
            captured.append(q)
            return {
                "base_predicted_rate": 3500.0, "mpesa_tariff_surcharge": 55.0,
                "final_quoted_rate": 3555.0, "min_quoted_rate": 3200.0, "max_quoted_rate": 4000.0,
                "bilateral_arbitrage_factor": 1.0,
                "nearest_neighbors": [{"peer_index": 0, "distance": 0.1, "verified_rate": 3500.0, "similarity_score": 0.9}],
            }

        app = self._create_app(repo, inference=inf)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        query = {
            "mentorId": "mentor-alice",
            "listingId": "listing-1",
            "rawText": "Custom override description provided in the request body.",
            "costOfLivingIndex": 88.5,
            "competitivenessScore": 0.95,
            "baseRateFloor": 3100.0,
            "clientCountry": "US",
        }
        response = client.post("/api/v1/optimize-price", json=query, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        # All explicit request overrides must be respected over stored values
        self.assertEqual(captured[0].raw_description, "Custom override description provided in the request body.")
        self.assertEqual(captured[0].cost_of_living_index, 88.5)
        self.assertEqual(captured[0].market_saturation_score, 0.95)
        self.assertEqual(captured[0].base_rate_floor, 3100.0)

    def test_cost_of_living_hydration_from_mentor_profile(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", {**MENTOR_DATA, "cost_of_living_index": 52.3})
        repo.upsert_listing("listing-1", LISTING_DATA)

        captured = []
        def inf(q):
            captured.append(q)
            return {
                "base_predicted_rate": 3500.0, "mpesa_tariff_surcharge": 55.0,
                "final_quoted_rate": 3555.0, "min_quoted_rate": 3200.0, "max_quoted_rate": 4000.0,
                "bilateral_arbitrage_factor": 1.0,
                "nearest_neighbors": [{"peer_index": 0, "distance": 0.1, "verified_rate": 3500.0, "similarity_score": 0.9}],
            }

        app = self._create_app(repo, inference=inf)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        query = {"mentorId": "mentor-alice", "industry": "web_backend", "clientCountry": "US"}
        response = client.post("/api/v1/optimize-price", json=query, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(captured[0].cost_of_living_index, 52.3)

    def test_hydrate_raw_text_from_mentor_profile_when_no_listings(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", {
            **MENTOR_DATA,
            "raw_description": "Senior backend architect with ten years of API mentoring experience.",
        })
        # No listings in repository
        captured = []
        def inf(q):
            captured.append(q)
            return {
                "base_predicted_rate": 3500.0, "mpesa_tariff_surcharge": 55.0,
                "final_quoted_rate": 3555.0, "min_quoted_rate": 3200.0, "max_quoted_rate": 4000.0,
                "bilateral_arbitrage_factor": 1.0,
                "nearest_neighbors": [{"peer_index": 0, "distance": 0.1, "verified_rate": 3500.0, "similarity_score": 0.9}],
            }

        app = self._create_app(repo, inference=inf)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        query = {"mentorId": "mentor-alice", "industry": "web_backend", "clientCountry": "US"}
        response = client.post("/api/v1/optimize-price", json=query, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(captured[0].raw_description, "Senior backend architect with ten years of API mentoring experience.")

    def test_fail_explicitly_identity_crossover_prevented(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", MENTOR_DATA)
        repo.upsert_profile("mentor-bob", {**MENTOR_DATA, "auth_uid": "uid-bob"})
        repo.upsert_listing("listing-bob", {**LISTING_DATA, "mentor_id": "mentor-bob"})

        app = self._create_app(repo)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        # Alice attempts to quote against Bob's listing
        query = {
            "mentorId": "mentor-alice",
            "listingId": "listing-bob",
            "clientCountry": "US",
        }
        response = client.post("/api/v1/optimize-price", json=query, headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertIn("listing does not belong to authorized mentor", response.json()["detail"])
        # No success audit should be scheduled
        self.assertEqual(repo.list_transactions(), [])

    def test_fail_explicitly_on_inactive_or_missing_listing(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", MENTOR_DATA)
        repo.upsert_listing("listing-inactive", {**LISTING_DATA, "is_active": False})

        app = self._create_app(repo)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        # Inactive listing
        response = client.post("/api/v1/optimize-price",
                               json={"mentorId": "mentor-alice", "listingId": "listing-inactive", "clientCountry": "US"},
                               headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertIn("listing is inactive", response.json()["detail"])

        # Missing listing
        response = client.post("/api/v1/optimize-price",
                               json={"mentorId": "mentor-alice", "listingId": "listing-missing", "clientCountry": "US"},
                               headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertIn("listing 'listing-missing' not found", response.json()["detail"])
        self.assertEqual(repo.list_transactions(), [])

    def test_fail_explicitly_on_listing_industry_mismatch(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", MENTOR_DATA)
        repo.upsert_listing("listing-mobile", {**LISTING_DATA, "industry_id": "mobile"})

        app = self._create_app(repo)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        response = client.post("/api/v1/optimize-price",
                               json={"mentorId": "mentor-alice", "listingId": "listing-mobile",
                                     "industry": "web_backend", "clientCountry": "US"},
                               headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertIn("listing industry does not match requested industry", response.json()["detail"])
        self.assertEqual(repo.list_transactions(), [])

    def test_fail_explicitly_when_required_profile_data_missing(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", MENTOR_DATA)
        # No listings and no description on mentor profile

        app = self._create_app(repo)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        # Missing rawText with no listings to hydrate from
        response = client.post("/api/v1/optimize-price",
                               json={"mentorId": "mentor-alice", "industry": "web_backend", "clientCountry": "US"},
                               headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertIn("rawText is required and could not be hydrated", response.json()["detail"])

        # Missing industry with no listings to hydrate from
        response = client.post("/api/v1/optimize-price",
                               json={"mentorId": "mentor-alice", "clientCountry": "US"},
                               headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertIn("rawText is required", response.json()["detail"])
        self.assertEqual(repo.list_transactions(), [])

    def test_fail_explicitly_on_out_of_bounds_hydrated_data(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", MENTOR_DATA)
        app = self._create_app(repo)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        # Stored listing description too short (< 20 chars)
        fake_client = repo._client
        fake_client.collection("service_listings").documents["listing-short"] = {
            "listing_id": "listing-short", "mentor_id": "mentor-alice", "industry_id": "web_backend",
            "title": "Title", "raw_description": "too short", "latent_svd_vector": [0.0] * 50,
            "verified_rate": 3000.0, "is_active": True,
        }
        response = client.post("/api/v1/optimize-price",
                               json={"mentorId": "mentor-alice", "listingId": "listing-short", "clientCountry": "US"},
                               headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertIn("20 characters", response.json()["detail"])

        # Invalid cost_of_living_index on mentor profile
        for bad_col in (-1.0, 0.0, 1001.0, float("nan"), float("inf")):
            fake_client.collection("mentors").documents["mentor-alice"]["cost_of_living_index"] = bad_col
            resp = client.post("/api/v1/optimize-price",
                               json={"mentorId": "mentor-alice", "rawText": "A" * 30,
                                     "industry": "web_backend", "clientCountry": "US"},
                               headers=headers)
            self.assertEqual(resp.status_code, 422)
            self.assertIn("invalid cost_of_living_index on mentor profile", resp.json()["detail"])

        # Invalid country code on mentor profile
        fake_client.collection("mentors").documents["mentor-alice"]["cost_of_living_index"] = 42.1
        for bad_country in ("K", "12", "KENYA", ""):
            fake_client.collection("mentors").documents["mentor-alice"]["country_code"] = bad_country
            resp = client.post("/api/v1/optimize-price",
                               json={"mentorId": "mentor-alice", "rawText": "A" * 30,
                                     "industry": "web_backend", "clientCountry": "US"},
                               headers=headers)
            self.assertEqual(resp.status_code, 422)
            self.assertIn("missing or invalid verified mentor country code", resp.json()["detail"])
        self.assertEqual(repo.list_transactions(), [])

    def test_fail_explicitly_unauthorized_reads_and_unverified_uid(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", MENTOR_DATA)
        repo.upsert_listing("listing-1", LISTING_DATA)

        app = self._create_app(repo)
        client = TestClient(app)

        query = {"mentorId": "mentor-alice", "industry": "web_backend", "clientCountry": "US"}

        # Missing token
        self.assertEqual(client.post("/api/v1/optimize-price", json=query).status_code, 401)
        # Invalid token
        self.assertEqual(client.post("/api/v1/optimize-price", json=query,
                                     headers={"Authorization": "Bearer bad-token"}).status_code, 401)
        # Wrong mentorId (not owned by token UID)
        self.assertEqual(client.post("/api/v1/optimize-price", json={**query, "mentorId": "mentor-other"},
                                     headers={"Authorization": "Bearer valid-token"}).status_code, 403)
        # Inactive mentor account
        repo.upsert_profile("mentor-alice", {**MENTOR_DATA, "account_status": "inactive"})
        self.assertEqual(client.post("/api/v1/optimize-price", json=query,
                                     headers={"Authorization": "Bearer valid-token"}).status_code, 403)
        self.assertEqual(repo.list_transactions(), [])

    def test_service_unavailable_when_repository_fails(self):
        class FailingListingRepo(InMemoryRepository):
            def health(self) -> str:
                return "firestore"

            def list_listings_for_mentor(self, mentor_id: str):
                raise RuntimeError("Firestore connection timed out")

            def get_listing(self, listing_id: str):
                raise RuntimeError("Firestore connection timed out")

        repo = FailingListingRepo()
        repo.upsert_profile("mentor-alice", MENTOR_DATA)

        app = self._create_app(repo)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        query = {"mentorId": "mentor-alice", "industry": "web_backend", "clientCountry": "US"}
        response = client.post("/api/v1/optimize-price", json=query, headers=headers)
        self.assertEqual(response.status_code, 503)
        self.assertIn("pricing repository unavailable", response.json()["detail"])
        self.assertEqual(repo.list_transactions(), [])

    def test_legacy_snake_case_hydration(self):
        repo = FirestoreRepository(client=FakeFirestoreClient())
        repo.upsert_profile("mentor-alice", MENTOR_DATA)
        repo.upsert_listing("listing-1", LISTING_DATA)

        app = self._create_app(repo)
        client = TestClient(app)
        headers = {"Authorization": "Bearer valid-token"}

        # Legacy query with mentorId, omitting raw_description and mentor_country
        legacy_query = {
            "mentorId": "mentor-alice",
            "selected_industry": "web_backend",
            "client_country": "US",
        }
        response = client.post("/api/v1/optimize-price", json=legacy_query, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["Deprecation"], "true")
        data = response.json()
        self.assertEqual(data["final_quoted_rate"], 3555.0)
        self.assertEqual(len(repo.list_transactions()), 1)


if __name__ == "__main__":
    unittest.main()
