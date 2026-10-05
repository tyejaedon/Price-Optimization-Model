"""#72 append-only pricing audit regressions; no cloud credentials needed."""

import asyncio
import json
import threading
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.interval_synthesizer import FloorExceedsCeilingError
from src.observability import MetricsRegistry
from src.repository import FirestoreRepository, InMemoryRepository, RepositoryError
from src.serve import create_app


QUERY = {
    "mentorId": "mentor-verified",
    "raw_description": "Sensitive private mentor description",
    "selected_industry": "web_backend",
    "mentor_country": "ke",
    "client_country": "us",
}
HEADERS = {"Authorization": "Bearer private-id-token"}
QUOTE = {"base_predicted_rate": 200.0, "mpesa_tariff_surcharge": 20.0, "final_quoted_rate": 220.0}


class FakeDocument:
    def __init__(self, collection, document_id):
        self.collection = collection
        self.id = document_id

    def create(self, payload):
        if self.id in self.collection.documents:
            raise RepositoryError("document already exists")
        self.collection.documents[self.id] = deepcopy(payload)


class FakeCollection:
    def __init__(self):
        self.documents = {}
        self.limit_count = 100

    def document(self, document_id):
        return FakeDocument(self, document_id)

    def limit(self, count):
        self.limit_count = count
        return self

    def stream(self):
        return [SimpleNamespace(id=key, to_dict=lambda record=value: deepcopy(record))
                for key, value in list(self.documents.items())[:self.limit_count]]


class FakeFirestoreClient:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, FakeCollection())


class FirestoreLikeMemory(InMemoryRepository):
    def health(self):
        return "firestore"


class FlakyFirestore(FirestoreLikeMemory):
    def __init__(self, failures):
        super().__init__()
        self.failures = failures
        self.attempts = []

    def append_transaction(self, payload):
        self.attempts.append(payload["transaction_id"])
        if len(self.attempts) <= self.failures:
            raise RuntimeError("private-id-token Sensitive private mentor description")
        return super().append_transaction(payload)


class BlockingMemory(InMemoryRepository):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def append_transaction(self, payload):
        self.started.set()
        if not self.release.wait(timeout=5):
            raise RuntimeError("write timed out")
        return super().append_transaction(payload)


class PricingAuditTests(unittest.TestCase):
    @staticmethod
    def app(repository, *, inference=None, metrics=None):
        return create_app(repository=repository, inference=inference or (lambda query: QUOTE), metrics=metrics,
                          token_verifier=lambda token: {"uid": "mentor-verified"} if token == "private-id-token" else {},
                          admin_token="admin-only")

    def test_firestore_create_only_records_are_inspectable_and_match_quotes(self):
        fake = FakeFirestoreClient()
        repository = FirestoreRepository(client=fake)
        app = self.app(repository)
        with TestClient(app) as client:
            for _ in range(2):
                response = client.post("/api/v1/optimize-price", json=QUERY, headers=HEADERS)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["final_quoted_rate"], QUOTE["final_quoted_rate"])
            history = client.get("/api/v1/admin/history", headers={"X-Admin-Token": "admin-only"})
            self.assertEqual(history.status_code, 200)
            self.assertEqual(len(history.json()), 2)
            self.assertEqual(client.get("/api/v1/admin/history").status_code, 403)
            audit_metrics = client.get("/api/v1/admin/metrics", headers={"X-Admin-Token": "admin-only"}).json()
            self.assertEqual(audit_metrics["metrics"]["operations"]["audit.persist"]["count"], 2)
            self.assertEqual(audit_metrics["metrics"]["operations"]["audit.persist"]["failures"], 0)

        records = history.json()
        ids = {row["transaction_id"] for row in records}
        self.assertEqual(len(ids), 2)
        self.assertEqual(set(fake.collection("historical_transactions").documents), ids)
        for record in records:
            self.assertEqual(record["mentor_id"], "mentor-verified")
            self.assertEqual(record["schema_version"], 1)
            self.assertEqual(record["selected_industry"], QUERY["selected_industry"])
            self.assertEqual(record["mentor_country_code"], "KE")
            self.assertEqual(record["client_country_code"], "US")
            self.assertEqual(record["final_quoted_rate"], QUOTE["final_quoted_rate"])
            self.assertEqual(datetime.fromisoformat(record["executed_at"]).tzinfo, timezone.utc)
            self.assertNotIn("raw_description", record)
            self.assertNotIn("listing_id", record)  # #71 owns durable listing identity.
            self.assertNotIn("private-id-token", str(record))
            with self.assertRaises(RepositoryError):
                repository.append_transaction({**record, "final_quoted_rate": 999.0})
            self.assertEqual(fake.collection("historical_transactions").documents[record["transaction_id"]], record)

    def test_memory_append_is_create_only_and_copies_records(self):
        repository = InMemoryRepository()
        audit = {"transaction_id": "once", "context": {"country": "KE"}}
        repository.append_transaction(audit)
        audit["context"]["country"] = "US"
        with self.assertRaises(RepositoryError):
            repository.append_transaction({"transaction_id": "once", "context": {"country": "US"}})
        listed = repository.list_transactions()
        listed[0]["context"]["country"] = "GB"
        self.assertEqual(repository.list_transactions(), [{"transaction_id": "once", "context": {"country": "KE"}}])

    def test_invalid_ids_cannot_be_appended_to_either_repository(self):
        for repository in (InMemoryRepository(), FirestoreRepository(client=FakeFirestoreClient())):
            for transaction_id in (None, "", 123, "nested/document"):
                with self.subTest(repository=type(repository).__name__, transaction_id=transaction_id):
                    with self.assertRaises(RepositoryError):
                        repository.append_transaction({"transaction_id": transaction_id})
            self.assertEqual(repository.list_transactions(), [])

    def test_rejected_requests_and_inference_failures_never_schedule_success_audits(self):
        repository = FirestoreLikeMemory()
        calls = []

        def inference(query):
            calls.append(query)
            if query.base_rate_floor == 999:
                raise FloorExceedsCeilingError("floor exceeds ceiling")
            if query.base_rate_floor == 888:
                raise RuntimeError("inference unavailable")
            return QUOTE

        app = self.app(repository, inference=inference)
        with TestClient(app) as client:
            cases = [({**QUERY}, {}, 401), ({**QUERY, "mentorId": "someone-else"}, HEADERS, 403),
                     ({"mentorId": "mentor-verified"}, HEADERS, 422),
                     ({**QUERY, "base_rate_floor": 999}, HEADERS, 422),
                     ({**QUERY, "base_rate_floor": 888}, HEADERS, 500)]
            for payload, headers, expected in cases:
                with self.subTest(expected=expected):
                    self.assertEqual(client.post("/api/v1/optimize-price", json=payload,
                                                 headers=headers).status_code, expected)
            self.assertEqual(len(calls), 2)
            self.assertEqual(repository.list_transactions(), [])
            self.assertNotIn("audit.persist", app.state.dependencies.metrics.snapshot()["operations"])

    def test_transient_failure_retries_same_id_and_reports_recovery(self):
        repository = FlakyFirestore(failures=1)
        metrics = MetricsRegistry()
        with TestClient(self.app(repository, metrics=metrics)) as client:
            self.assertEqual(client.post("/api/v1/optimize-price", json=QUERY, headers=HEADERS).status_code, 200)
        self.assertEqual(len(set(repository.attempts)), 1)
        self.assertEqual(len(repository.attempts), 2)
        self.assertEqual(len(repository.list_transactions()), 1)
        snapshot = metrics.snapshot()["operations"]
        self.assertEqual(snapshot["database.append_transaction"]["failures"], 1)
        self.assertEqual(snapshot["audit.persist"]["failures"], 0)

    def test_exhausted_failure_is_metricized_and_logged_without_secrets(self):
        repository = FlakyFirestore(failures=2)
        metrics = MetricsRegistry()
        with self.assertLogs("src.serve", level="ERROR") as logs:
            with TestClient(self.app(repository, metrics=metrics)) as client:
                response = client.post("/api/v1/optimize-price", json=QUERY, headers=HEADERS)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(client.get("/api/v1/admin/history", headers={"X-Admin-Token": "admin-only"}).json(), [])
        self.assertEqual(len(repository.attempts), 2)
        self.assertEqual(len(set(repository.attempts)), 1)
        snapshot = metrics.snapshot()["operations"]
        self.assertEqual(snapshot["database.append_transaction"]["failures"], 2)
        self.assertEqual(snapshot["audit.persist"]["count"], 1)
        self.assertEqual(snapshot["audit.persist"]["failures"], 1)
        self.assertEqual(len(logs.output), 1)
        self.assertIn(repository.attempts[0], logs.output[0])
        self.assertIn("RuntimeError", logs.output[0])
        self.assertNotIn("private-id-token", logs.output[0])
        self.assertNotIn(QUERY["raw_description"], logs.output[0])

    def test_response_body_is_sent_before_blocking_write(self):
        repository = BlockingMemory()
        app = create_app(repository=repository, inference=lambda query: QUOTE)

        async def request():
            body = json.dumps(QUERY).encode()
            scope = {"type": "http", "http_version": "1.1", "method": "POST",
                     "scheme": "http", "path": "/api/v1/optimize-price", "raw_path": b"/api/v1/optimize-price",
                     "query_string": b"", "root_path": "", "server": ("test", 80), "client": ("test", 1234),
                     "headers": [(b"content-type", b"application/json")]}
            sent = asyncio.Event()
            disconnect = asyncio.Event()
            messages = []
            received = False

            async def receive():
                nonlocal received
                if not received:
                    received = True
                    return {"type": "http.request", "body": body, "more_body": False}
                await disconnect.wait()
                return {"type": "http.disconnect"}

            async def send(message):
                messages.append(message)
                if message["type"] == "http.response.body" and not message.get("more_body", False):
                    sent.set()

            task = asyncio.create_task(app(scope, receive, send))
            try:
                await asyncio.wait_for(sent.wait(), timeout=3)
                self.assertEqual(messages[0]["status"], 200)
                response_body = b"".join(message.get("body", b"") for message in messages
                                         if message["type"] == "http.response.body")
                self.assertEqual(json.loads(response_body)["final_quoted_rate"], 220.0)
                self.assertTrue(await asyncio.to_thread(repository.started.wait, 3))
                self.assertFalse(task.done())
                self.assertEqual(repository.list_transactions(), [])
            finally:
                repository.release.set()
                await asyncio.wait_for(task, timeout=3)
                disconnect.set()
            self.assertEqual(len(repository.list_transactions()), 1)

        asyncio.run(request())


if __name__ == "__main__":
    unittest.main()
