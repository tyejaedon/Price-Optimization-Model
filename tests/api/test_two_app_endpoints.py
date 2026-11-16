import unittest

from fastapi.testclient import TestClient

from src.api.serve import create_app
from tests.api.test_container_gateway import FakeFirestore


class TwoAppEndpointsTests(unittest.TestCase):
    def _setup_app(self):
        repository = FakeFirestore()
        repository.upsert_profile(
            "mentor-u1",
            {
                "profile_id": "mentor-u1",
                "auth_uid": "uid-1",
                "full_name": "Alice Mentor",
                "email": "alice@example.test",
                "country_code": "KE",
                "account_status": "active",
            },
        )
        repository.upsert_profile(
            "mentor-u2",
            {
                "profile_id": "mentor-u2",
                "auth_uid": "uid-2",
                "full_name": "Bob Mentor",
                "email": "bob@example.test",
                "country_code": "KE",
                "account_status": "active",
            },
        )

        def verifier(token: str):
            if token == "token-u1":
                return {"uid": "uid-1"}
            if token == "token-u2":
                return {"uid": "uid-2"}
            raise ValueError("invalid token")

        def inference(_query):
            return {
                "base_predicted_rate": 2500.0,
                "mpesa_tariff_surcharge": 57.0,
                "final_quoted_rate": 2557.0,
                "min_quoted_rate": 2125.0,
                "max_quoted_rate": 3375.0,
                "bilateral_arbitrage_factor": 0.51,
                "mentor_country_iso2": "KE",
                "nearest_neighbors": [
                    {
                        "peer_index": 0,
                        "listing_id": "list-1",
                        "job_title": "Backend Engineer",
                        "verified_rate": 2500.0,
                        "similarity_score": 0.9,
                        "distance": 0.2,
                    }
                ],
            }

        app = create_app(
            repository=repository,
            inference=inference,
            token_verifier=verifier,
            admin_token="admin-secret",
        )
        return app, repository

    def test_shared_metadata_endpoint(self):
        app, _ = self._setup_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/metadata")
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertEqual(body["unit"], "KES/hour")
            self.assertIn("mobile", body["industries"])
            self.assertIn("web_backend", body["industries"])

    def test_mentor_listings_history_and_feedback_scoped_to_uid(self):
        app, repository = self._setup_app()
        u1_headers = {"Authorization": "Bearer token-u1"}
        u2_headers = {"Authorization": "Bearer token-u2"}
        admin_headers = {"X-Admin-Token": "admin-secret"}

        with TestClient(app) as client:
            # 1. Create and list mentor listings
            put_res = client.put(
                "/api/v1/me/listings/listing-u1",
                json={
                    "title": "Mobile Architecture Coaching",
                    "industryId": "mobile",
                    "rawText": "Senior Kotlin and Jetpack Compose architecture mentoring for teams.",
                    "verifiedRate": 2800.0,
                },
                headers=u1_headers,
            )
            self.assertEqual(put_res.status_code, 200, put_res.text)
            self.assertEqual(put_res.json()["mentorId"], "mentor-u1")

            list_res = client.get("/api/v1/me/listings", headers=u1_headers)
            self.assertEqual(list_res.status_code, 200)
            self.assertEqual(len(list_res.json()), 1)
            self.assertEqual(list_res.json()[0]["listingId"], "listing-u1")

            # Other user sees no listings for u1
            self.assertEqual(client.get("/api/v1/me/listings", headers=u2_headers).json(), [])

            # 2. Issue a quote for u1 so an audit transaction exists
            quote_res = client.post(
                "/api/v1/optimize-price",
                json={
                    "mentorId": "mentor-u1",
                    "listingId": "listing-u1",
                    "clientCountry": "US",
                },
                headers=u1_headers,
            )
            self.assertEqual(quote_res.status_code, 200, quote_res.text)

            # 3. u1 sees their history; u2 does not
            u1_hist = client.get("/api/v1/me/history", headers=u1_headers)
            self.assertEqual(u1_hist.status_code, 200)
            self.assertEqual(len(u1_hist.json()), 1)
            tx_id = u1_hist.json()[0]["transaction_id"]

            u2_hist = client.get("/api/v1/me/history", headers=u2_headers)
            self.assertEqual(u2_hist.status_code, 200)
            self.assertEqual(u2_hist.json(), [])

            # 4. Feedback ownership enforcement
            fb_forbidden = client.post(
                f"/api/v1/quotes/{tx_id}/feedback",
                json={"outcome": "accepted"},
                headers=u2_headers,
            )
            self.assertEqual(fb_forbidden.status_code, 403)

            fb_ok = client.post(
                f"/api/v1/quotes/{tx_id}/feedback",
                json={"outcome": "booked", "actualRate": 2600.0, "notes": "Client accepted"},
                headers=u1_headers,
            )
            self.assertEqual(fb_ok.status_code, 200, fb_ok.text)
            self.assertEqual(fb_ok.json()["outcome"], "booked")

            # 5. Admin / MLOps endpoints require admin token
            self.assertEqual(client.get("/api/v1/admin/drift", headers=u1_headers).status_code, 403)
            self.assertEqual(client.get("/api/v1/admin/feedback", headers=u1_headers).status_code, 403)
            self.assertEqual(client.get("/api/v1/admin/artifacts", headers=u1_headers).status_code, 403)

            drift_res = client.get("/api/v1/admin/drift", headers=admin_headers)
            self.assertEqual(drift_res.status_code, 200)
            self.assertEqual(drift_res.json()["totalTransactions"], 1)
            self.assertEqual(drift_res.json()["byIndustry"]["mobile"], 1)
            self.assertEqual(drift_res.json()["byCorridor"]["KE->US"], 1)

            fb_admin = client.get("/api/v1/admin/feedback", headers=admin_headers)
            self.assertEqual(fb_admin.status_code, 200)
            self.assertEqual(len(fb_admin.json()), 1)

            art_admin = client.get("/api/v1/admin/artifacts", headers=admin_headers)
            self.assertEqual(art_admin.status_code, 200)
            self.assertIn("modelsLoaded", art_admin.json())


if __name__ == "__main__":
    unittest.main()
