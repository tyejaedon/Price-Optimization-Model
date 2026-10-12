"""Browser demo CORS is restricted to explicit trusted origins."""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.config import DeploymentConfig, parse_cors_allowed_origins
from src.serve import create_app


class BrowserDemoCorsTests(unittest.TestCase):
    def test_origin_parser_accepts_exact_https_and_loopback_origins(self):
        self.assertEqual(
            parse_cors_allowed_origins("https://demo.example.com,http://127.0.0.1:4173,https://demo.example.com"),
            ("https://demo.example.com", "http://127.0.0.1:4173"),
        )
        self.assertEqual(parse_cors_allowed_origins(""), ())

    def test_origin_parser_rejects_wildcards_paths_credentials_and_remote_http(self):
        for origin in (
            "*",
            "https://*.example.com",
            "https://demo.example.com/path",
            "https://user:password@demo.example.com",
            "http://demo.example.com",
            "https://demo.example.com?debug=true",
            "https://demo.example.com:invalid",
        ):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                parse_cors_allowed_origins(origin)

    def test_deployment_config_reads_the_scoped_cors_allow_list(self):
        with patch.dict(
            os.environ,
            {
                "FIREBASE_PROJECT_ID": "demo-pricing",
                "PRICING_TARIFF_SHA256": "a" * 64,
                "PRICING_CORS_ALLOWED_ORIGINS": "https://demo.example.com",
            },
            clear=True,
        ):
            self.assertEqual(
                DeploymentConfig.from_env().cors_allowed_origins,
                ("https://demo.example.com",),
            )

    def test_preflight_is_origin_scoped_and_pricing_still_requires_auth(self):
        origin = "http://127.0.0.1:4173"
        app = create_app(
            inference=lambda query: {},
            token_verifier=lambda token: {"uid": "test-user"},
            cors_allowed_origins=(origin,),
        )
        payload = {
            "mentorId": "test-user",
            "rawText": "Experienced mobile engineer building Android applications.",
            "industry": "mobile",
            "mentorCountry": "KE",
            "clientCountry": "US",
        }
        with TestClient(app) as client:
            preflight = client.options(
                "/api/v1/optimize-price",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )
            self.assertEqual(preflight.status_code, 200)
            self.assertEqual(preflight.headers["access-control-allow-origin"], origin)
            self.assertNotEqual(preflight.headers.get("access-control-allow-credentials"), "true")
            self.assertIn("POST", preflight.headers["access-control-allow-methods"])

            missing_token = client.post(
                "/api/v1/optimize-price",
                json=payload,
                headers={"Origin": origin},
            )
            self.assertEqual(missing_token.status_code, 401)
            self.assertEqual(missing_token.headers["access-control-allow-origin"], origin)

            rejected_origin = client.post(
                "/api/v1/optimize-price",
                json=payload,
                headers={"Origin": "https://untrusted.example"},
            )
            self.assertEqual(rejected_origin.status_code, 401)
            self.assertNotIn("access-control-allow-origin", rejected_origin.headers)

    def test_cors_is_disabled_when_no_origins_are_configured(self):
        with TestClient(create_app(inference=lambda query: {})) as client:
            response = client.get("/health", headers={"Origin": "https://demo.example.com"})
        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
