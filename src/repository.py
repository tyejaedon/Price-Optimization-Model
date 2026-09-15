"""Repository boundary for UC8 with memory and lazy Firestore implementations."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Dict, List, Optional


class RepositoryError(RuntimeError):
    """Raised when a repository operation cannot be completed."""


class Repository(ABC):
    @abstractmethod
    def list_profiles(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def upsert_profile(self, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def delete_profile(self, profile_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def append_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> str:
        raise NotImplementedError


class InMemoryRepository(Repository):
    """Deterministic repository used for local development and tests."""

    def __init__(self) -> None:
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._transactions: List[Dict[str, Any]] = []

    def list_profiles(self) -> List[Dict[str, Any]]:
        return deepcopy(list(self._profiles.values()))

    def upsert_profile(self, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        stored = {"profile_id": profile_id, **deepcopy(payload)}
        self._profiles[profile_id] = stored
        return deepcopy(stored)

    def delete_profile(self, profile_id: str) -> bool:
        return self._profiles.pop(profile_id, None) is not None

    def list_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        return deepcopy(self._transactions[-max(1, min(int(limit), 1000)) :])

    def append_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        stored = deepcopy(payload)
        self._transactions.append(stored)
        return deepcopy(stored)

    def health(self) -> str:
        return "memory"


class FirestoreRepository(Repository):
    """Lazy Firebase Admin Firestore adapter.

    The adapter uses ``firebase_admin.initialize_app()`` and Application Default
    Credentials. It never accepts or reads a service-account path itself; deployment
    should provide credentials through the platform environment.
    """

    def __init__(self, client: Optional[Any] = None) -> None:
        if client is not None:
            self._client = client
            return
        try:
            import firebase_admin
            from firebase_admin import firestore
        except ImportError as exc:  # pragma: no cover - dependency-specific path
            raise RepositoryError("firebase-admin is required for FirestoreRepository") from exc
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            self._client = firestore.client()
        except Exception as exc:  # pragma: no cover - requires cloud credentials
            raise RepositoryError("Firestore initialization failed") from exc

    def _timed(self, operation: Any) -> Any:
        started = time.perf_counter()
        try:
            return operation()
        finally:
            self.last_latency_ms = (time.perf_counter() - started) * 1000.0

    def list_profiles(self) -> List[Dict[str, Any]]:
        return self._timed(lambda: [{"profile_id": doc.id, **doc.to_dict()} for doc in self._client.collection("mentors").stream()])

    def upsert_profile(self, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self._timed(lambda: self._client.collection("mentors").document(profile_id).set(payload, merge=True))
        return {"profile_id": profile_id, **deepcopy(payload)}

    def delete_profile(self, profile_id: str) -> bool:
        self._timed(lambda: self._client.collection("mentors").document(profile_id).delete())
        return True

    def list_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        query = self._client.collection("historical_transactions").limit(max(1, min(int(limit), 1000)))
        return self._timed(lambda: [{"transaction_id": doc.id, **doc.to_dict()} for doc in query.stream()])

    def append_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        transaction_id = str(payload["transaction_id"])
        self._timed(lambda: self._client.collection("historical_transactions").document(transaction_id).set(payload))
        return deepcopy(payload)

    def health(self) -> str:
        return "firestore"

