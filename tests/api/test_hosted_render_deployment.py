"""Tests for M13.4: Hosted pricing service deployment on Render with PLATFORM_PRICE_KEY."""

import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.api.hosted import create_hosted_app

TEST_PLATFORM_KEY = "render-hosted-platform-key-xyz"


class HostedRenderDeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.render_yaml_path = self.repo_root / "render.yaml"

    def test_render_yaml_validity_and_specifications(self) -> None:
        self.assertTrue(self.render_yaml_path.is_file(), "render.yaml must exist at repo root")
        content = self.render_yaml_path.read_text(encoding="utf-8")

        self.assertIn("type: web", content)
        self.assertIn("name: price-optimization-service", content)
        self.assertIn("healthCheckPath: /health", content)
        self.assertIn("src.api.hosted:app", content)
        self.assertIn("$PORT", content)
        self.assertIn("PLATFORM_PRICE_KEY", content)
        self.assertIn("SEED_PLATFORM_MENTORS", content)
        self.assertIn("PRICING_TARIFF_SHA256", content)
        self.assertIn("PRICING_ARTIFACT_MANIFEST_SHA256", content)

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
