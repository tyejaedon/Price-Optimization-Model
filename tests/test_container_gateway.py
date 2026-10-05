"""Deployment boundary tests; Firebase/Firestore fakes never use production keys."""

import os
import importlib
import tempfile
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.config import DeploymentConfig
from src.artifact_contract import MANIFEST_NAME, file_sha256
from src.repository import InMemoryRepository
from src.serve import create_app
from tests import test_serve


class FakeFirestore(InMemoryRepository):
    def health(self) -> str:
        return "firestore"

    def probe_readiness(self) -> bool:
        return True


class FailingFirestore(FakeFirestore):
    def append_transaction(self, payload):
        raise RuntimeError("Firestore unavailable")


class UnavailableFirestore(FakeFirestore):
    def health(self) -> str:
        raise RuntimeError("Firestore unavailable")


PAYLOAD = {
    "mentorId": "fixture-user",
    "raw_description": "Senior web backend engineer building Python APIs and cloud services.",
    "selected_industry": "web_backend",
    "mentor_country": "KE",
    "client_country": "US",
    "market_saturation_score": 0.3,
}


class ContainerGatewayTests(unittest.TestCase):
    def test_missing_firebase_project_fails_closed(self):
        with patch.dict(os.environ, {"FIREBASE_PROJECT_ID": ""}):
            with self.assertRaisesRegex(ValueError, "FIREBASE_PROJECT_ID"):
                DeploymentConfig.from_env()

    def test_deployment_rejects_firebase_emulator_configuration(self):
        for name in ("FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST"):
            with self.subTest(name=name), patch.dict(os.environ, {"FIREBASE_PROJECT_ID": "demo-pricing", name: "localhost:9099"}, clear=True):
                with self.assertRaisesRegex(ValueError, "emulators are not allowed"):
                    DeploymentConfig.from_env()

    def test_pricing_requires_token_and_own_mentor_before_inference_or_audit(self):
        repository = FakeFirestore()
        calls = []

        def inference(query):
            calls.append(query)
            return {"base_predicted_rate": 100.0, "mpesa_tariff_surcharge": 0.0,
                    "final_quoted_rate": 100.0}

        def verifier(token):
            if token != "valid-id-token":
                raise ValueError("invalid or expired token")
            return {"uid": "fixture-user"}

        app = create_app(repository=repository, inference=inference, token_verifier=verifier,
                         admin_token="admin-secret")
        with TestClient(app) as client:
            for headers in ({}, {"Authorization": "Bearer expired-id-token"},
                            {"Authorization": "Basic valid-id-token"},
                            {"Authorization": "Bearer valid-id-token extra"},
                            {"Authorization": "Bearer  valid-id-token"},
                            {"X-Admin-Token": "admin-secret"}):
                with self.subTest(headers=headers):
                    response = client.post("/api/v1/optimize-price", json=PAYLOAD, headers=headers)
                    self.assertEqual(response.status_code, 401, response.text)

            headers = {"Authorization": "Bearer valid-id-token"}
            for payload in ({key: value for key, value in PAYLOAD.items() if key != "mentorId"},
                            {**PAYLOAD, "mentorId": "other-user"}):
                with self.subTest(payload=payload):
                    response = client.post("/api/v1/optimize-price", json=payload, headers=headers)
                    self.assertEqual(response.status_code, 403, response.text)

            self.assertEqual(calls, [])
            self.assertEqual(repository.list_transactions(), [])
            self.assertEqual(client.get("/api/v1/admin/profiles", headers=headers).status_code, 403)
            self.assertEqual(client.get("/api/v1/admin/profiles", headers={"X-Admin-Token": "admin-secret"}).status_code, 200)

            response = client.post("/api/v1/optimize-price", json=PAYLOAD, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(len(calls), 1)
            self.assertEqual(repository.list_transactions()[0]["mentor_id"], "fixture-user")

    def test_pricing_rejects_missing_or_malformed_verified_uid(self):
        repository = FakeFirestore()
        calls = []

        def forbidden_inference(query):
            calls.append(query)
            return {}

        for claims in (None, {}, {"uid": None}, {"uid": ""}, {"uid": " "}, {"uid": 123}):
            with self.subTest(claims=claims):
                def verifier(token: str) -> Any:
                    return claims

                app = create_app(repository=repository, inference=forbidden_inference,
                                 token_verifier=verifier)
                with TestClient(app) as client:
                    response = client.post("/api/v1/optimize-price", json=PAYLOAD,
                                           headers={"Authorization": "Bearer token"})
                    self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(calls, [])
        self.assertEqual(repository.list_transactions(), [])

    def test_protected_pricing_never_falls_back_to_memory(self):
        repository = InMemoryRepository()
        called = []
        def forbidden_inference(query):
            called.append(query)
            return {}

        app = create_app(repository=repository, inference=forbidden_inference,
                         token_verifier=lambda token: {"uid": "fixture-user"})
        with TestClient(app) as client:
            self.assertEqual(client.get("/ready").status_code, 503)
            response = client.post("/api/v1/optimize-price", json=PAYLOAD,
                                   headers={"Authorization": "Bearer fixture-id-token"})
            self.assertEqual(response.status_code, 503)
        self.assertEqual(called, [])
        self.assertEqual(repository.list_transactions(), [])

    def test_repository_health_exception_marks_protected_app_unready(self):
        app = create_app(repository=UnavailableFirestore(), inference=lambda query: {},
                         token_verifier=lambda token: {"uid": "fixture-user"})
        with TestClient(app) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/ready").status_code, 503)
            self.assertEqual(client.post("/api/v1/optimize-price", json=PAYLOAD,
                                         headers={"Authorization": "Bearer fixture-id-token"}).status_code, 503)

    def test_protected_quote_and_audit_and_unready_state(self):
        with tempfile.TemporaryDirectory() as temp:
            artifact_dir, macro_path, tariff_path = test_serve.ServeApiTests()._build_artifacts(temp)
            digest = file_sha256(os.path.join(artifact_dir, MANIFEST_NAME))
            repository = FakeFirestore()
            probe = lambda: True

            def verifier(token):
                if token != "fixture-id-token":
                    raise ValueError("invalid ID token")
                return {"uid": "fixture-user"}

            app = create_app(artifact_dir, macro_path, tariff_path, repository=repository,
                             token_verifier=verifier, readiness_probe=probe, trusted_manifest_sha256=digest)
            with TestClient(app) as client:
                self.assertEqual(client.get("/ready").status_code, 200)
                for headers in ({}, {"Authorization": "Bearer invalid"}, {"Authorization": "Basic fixture-id-token"},
                                {"Authorization": "Bearer fixture-id-token extra"}):
                    self.assertEqual(client.post("/api/v1/optimize-price", json=PAYLOAD, headers=headers).status_code, 401)
                self.assertEqual(repository.list_transactions(), [])
                headers = {"Authorization": "Bearer fixture-id-token"}
                self.assertEqual(client.post("/api/v1/optimize-price", json={"bad": "payload"}, headers=headers).status_code, 422)
                response = client.post("/api/v1/optimize-price", json=PAYLOAD, headers=headers)
                self.assertEqual(response.status_code, 200, response.text)
                quote = response.json()
                self.assertGreaterEqual(quote["final_quoted_rate"], quote["base_predicted_rate"] + quote["mpesa_tariff_surcharge"])
                self.assertTrue(quote["nearest_neighbors"])
                self.assertEqual(len(repository.list_transactions()), 1)
                self.assertEqual(repository.list_transactions()[0]["final_quoted_rate"], quote["final_quoted_rate"])
                self.assertEqual(repository.list_transactions()[0]["mentor_id"], "fixture-user")


            unavailable = create_app(artifact_dir, macro_path, tariff_path, repository=FakeFirestore(),
                                     token_verifier=verifier, readiness_probe=lambda: False, trusted_manifest_sha256=digest)
            with TestClient(unavailable) as client:
                self.assertEqual(client.get("/ready").status_code, 503)

            missing = create_app(os.path.join(temp, "missing"), macro_path, tariff_path,
                                 repository=FakeFirestore(), token_verifier=verifier)
            with TestClient(missing) as client:
                self.assertEqual(client.get("/ready").status_code, 503)
                self.assertEqual(client.post("/api/v1/optimize-price", json=PAYLOAD,
                                            headers={"Authorization": "Bearer fixture-id-token"}).status_code, 503)

            failing = create_app(artifact_dir, macro_path, tariff_path, repository=FailingFirestore(),
                                 token_verifier=verifier, readiness_probe=lambda: True, trusted_manifest_sha256=digest)
            with TestClient(failing) as client:
                self.assertEqual(client.post("/api/v1/optimize-price", json=PAYLOAD,
                                             headers={"Authorization": "Bearer fixture-id-token"}).status_code, 200)
                self.assertEqual(failing.state.dependencies.repository.list_transactions(), [])
                self.assertEqual(failing.state.dependencies.metrics.snapshot()["operations"]["audit.persist"]["failures"], 1)

    def test_deployment_entrypoint_binds_firebase_and_firestore(self):
        with tempfile.TemporaryDirectory() as temp:
            artifact_dir, _, tariff_path = test_serve.ServeApiTests()._build_artifacts(temp)
            repository = FakeFirestore()
            env = {"FIREBASE_PROJECT_ID": "demo-pricing", "PRICING_ARTIFACT_DIR": artifact_dir,
                   "PRICING_TARIFF_CSV": tariff_path,
                   "PRICING_ARTIFACT_MANIFEST_SHA256": file_sha256(os.path.join(artifact_dir, MANIFEST_NAME))}
            with patch.dict(os.environ, env), patch("firebase_admin.get_app", return_value=SimpleNamespace(project_id="demo-pricing")), \
                    patch("src.repository.FirestoreRepository", return_value=repository), \
                    patch("firebase_admin.auth.verify_id_token", return_value={"uid": "fixture-user"}) as verify:
                deployment = importlib.import_module("src.deployment")
                with TestClient(deployment.create_deployment_app()) as client:
                    self.assertEqual(client.get("/ready").status_code, 200)
                    self.assertEqual(client.post("/api/v1/optimize-price", json=PAYLOAD).status_code, 401)
                    result = client.post("/api/v1/optimize-price", json=PAYLOAD,
                                         headers={"Authorization": "Bearer fixture-id-token"})
                    self.assertEqual(result.status_code, 200, result.text)
                    verify.assert_called_with("fixture-id-token", app=deployment.firebase_admin.get_app())
                    self.assertEqual(len(repository.list_transactions()), 1)


if __name__ == "__main__":
    unittest.main()
