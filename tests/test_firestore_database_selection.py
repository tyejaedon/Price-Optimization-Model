"""Issue #113: database selection must not read credentials or contact Firestore in tests."""

import os
import unittest
from unittest.mock import MagicMock, patch

from src.config import DeploymentConfig
from src.repository import FirestoreRepository


class FirestoreDatabaseSelectionTests(unittest.TestCase):
    def test_default_database_when_unset(self):
        with patch.dict(os.environ, {"FIREBASE_PROJECT_ID": "demo-pricing"}, clear=True):
            self.assertEqual(DeploymentConfig.from_env().firestore_database_id, "(default)")
            with patch("firebase_admin._apps", {"test": object()}), \
                    patch("firebase_admin.firestore.client", return_value=MagicMock()) as client_factory:
                repository = FirestoreRepository()
                self.assertTrue(repository.probe_readiness())
                client_factory.assert_called_once_with(database_id="(default)")

    def test_named_database_is_used_by_repository_and_readiness(self):
        client = MagicMock()
        with patch.dict(os.environ, {"FIREBASE_PROJECT_ID": "demo-pricing",
                                     "FIRESTORE_DATABASE_ID": "priceoptimizationmodel"}, clear=True):
            self.assertEqual(DeploymentConfig.from_env().firestore_database_id, "priceoptimizationmodel")
            with patch("firebase_admin._apps", {"test": object()}), \
                    patch("firebase_admin.firestore.client", return_value=client) as client_factory:
                repository = FirestoreRepository()
                self.assertTrue(repository.probe_readiness())
                client_factory.assert_called_once_with(database_id="priceoptimizationmodel")
                client.collection.assert_called_once_with("mentors")
                client.collection.return_value.limit.assert_called_once_with(1)
                client.collection.return_value.limit.return_value.get.assert_called_once_with(timeout=3)

    def test_readiness_propagates_named_database_read_failure(self):
        client = MagicMock()
        client.collection.return_value.limit.return_value.get.side_effect = PermissionError("read denied")
        with patch.dict(os.environ, {"FIRESTORE_DATABASE_ID": "priceoptimizationmodel"}, clear=True), \
                patch("firebase_admin._apps", {"test": object()}), \
                patch("firebase_admin.firestore.client", return_value=client) as client_factory:
            repository = FirestoreRepository()
            with self.assertRaises(PermissionError):
                repository.probe_readiness()
            client_factory.assert_called_once_with(database_id="priceoptimizationmodel")

    def test_explicit_database_id_overrides_environment(self):
        with patch.dict(os.environ, {"FIRESTORE_DATABASE_ID": "some-other-db"}, clear=True), \
                patch("firebase_admin._apps", {"test": object()}), \
                patch("firebase_admin.firestore.client", return_value=MagicMock()) as client_factory:
            FirestoreRepository(database_id="priceoptimizationmodel")
            client_factory.assert_called_once_with(database_id="priceoptimizationmodel")

    def test_injected_client_does_not_initialize_firebase(self):
        fake = object()
        with patch.dict(os.environ, {"FIRESTORE_DATABASE_ID": "invalid/id"}, clear=True), \
                patch("firebase_admin.firestore.client") as client_factory:
            self.assertIs(FirestoreRepository(client=fake)._client, fake)
            with self.assertRaisesRegex(ValueError, "FIRESTORE_DATABASE_ID"):
                FirestoreRepository(client=fake, database_id="invalid/id")
            client_factory.assert_not_called()

    def test_valid_database_id_boundaries(self):
        for database_id in ("(default)", "abcd", "a" + "b" * 61 + "c", "priceoptimizationmodel"):
            with self.subTest(database_id=database_id), \
                    patch.dict(os.environ, {"FIREBASE_PROJECT_ID": "demo-pricing",
                                         "FIRESTORE_DATABASE_ID": database_id}, clear=True):
                self.assertEqual(DeploymentConfig.from_env().firestore_database_id, database_id)

    def test_invalid_database_id_fails_closed_before_client_creation(self):
        for database_id in ("", " ", "(default) ", "BadID", "ab", "abc", "bad/name", "-bad-name",
                            "bad-name-", "a" * 64):
            with self.subTest(database_id=database_id), \
                    patch.dict(os.environ, {"FIREBASE_PROJECT_ID": "demo-pricing",
                                         "FIRESTORE_DATABASE_ID": database_id}, clear=True), \
                    patch("firebase_admin.firestore.client") as client_factory:
                with self.assertRaisesRegex(ValueError, "FIRESTORE_DATABASE_ID"):
                    DeploymentConfig.from_env()
                with self.assertRaisesRegex(ValueError, "FIRESTORE_DATABASE_ID"):
                    FirestoreRepository()
                client_factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
