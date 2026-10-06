"""Repository boundary for UC8 with memory and lazy Firestore implementations."""

from __future__ import annotations

import time
import threading
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Dict, List, Optional

from src.api_contracts import ProfileDTO, ServiceListingDTO
from src.config import configured_firestore_database_id, validate_firestore_database_id


class RepositoryError(RuntimeError):
    """Raised when a repository operation cannot be completed."""


def _document_id(value: str, field: str, max_length: int = 200) -> None:
    if (not isinstance(value, str) or not value or value != value.strip()
            or len(value) > max_length or value in {".", ".."} or "/" in value):
        raise RepositoryError(f"valid {field} is required")


def _profile(profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _document_id(profile_id, "mentor_id")
    if payload.get("profile_id", profile_id) != profile_id:
        raise RepositoryError("profile_id must match mentor document ID")
    profile = ProfileDTO.model_validate({**payload, "profile_id": profile_id}).model_dump(exclude_none=True)
    if "auth_uid" in profile:
        _document_id(profile["auth_uid"], "auth_uid", 128)
    return profile


def _listing(listing_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _document_id(listing_id, "listing_id")
    if payload.get("listing_id", listing_id) != listing_id:
        raise RepositoryError("listing_id must match listing document ID")
    listing = ServiceListingDTO.model_validate({**payload, "listing_id": listing_id}).model_dump()
    _document_id(listing["mentor_id"], "mentor_id")
    return listing


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
    def get_mentor(self, mentor_id: str, verified_uid: str) -> Optional[Dict[str, Any]]:
        """Return an owned mentor, None if missing, or reject an unauthorized read."""
        raise NotImplementedError

    @abstractmethod
    def get_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Read a root listing by its stable document ID (trusted service only)."""
        raise NotImplementedError

    @abstractmethod
    def upsert_listing(self, listing_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Publish a verified root listing; never change its mentor ownership."""
        raise NotImplementedError

    @abstractmethod
    def list_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def append_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create an audit with a unique transaction_id; never replace an existing one."""
        raise NotImplementedError

    @abstractmethod
    def health(self) -> str:
        raise NotImplementedError


class InMemoryRepository(Repository):
    """Deterministic repository used for local development and tests."""

    def __init__(self) -> None:
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._listings: Dict[str, Dict[str, Any]] = {}
        self._transactions: List[Dict[str, Any]] = []
        self._transaction_ids: set[str] = set()
        self._transaction_lock = threading.Lock()

    def list_profiles(self) -> List[Dict[str, Any]]:
        return deepcopy(list(self._profiles.values()))

    def upsert_profile(self, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        stored = _profile(profile_id, payload)
        previous = self._profiles.get(profile_id)
        if previous and previous.get("auth_uid") and previous["auth_uid"] != stored.get("auth_uid", previous["auth_uid"]):
            raise RepositoryError("mentor auth_uid cannot change")
        if previous and previous.get("auth_uid") and "auth_uid" not in stored:
            stored["auth_uid"] = previous["auth_uid"]
        self._profiles[profile_id] = stored
        return deepcopy(stored)

    def delete_profile(self, profile_id: str) -> bool:
        return self._profiles.pop(profile_id, None) is not None

    def get_mentor(self, mentor_id: str, verified_uid: str) -> Optional[Dict[str, Any]]:
        _document_id(mentor_id, "mentor_id")
        _document_id(verified_uid, "verified_uid", 128)
        profile = self._profiles.get(mentor_id)
        if profile is not None and profile.get("auth_uid") != verified_uid:
            raise RepositoryError("mentor authorization required")
        return deepcopy(profile)

    def get_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        _document_id(listing_id, "listing_id")
        return deepcopy(self._listings.get(listing_id))

    def upsert_listing(self, listing_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        stored = _listing(listing_id, payload)
        if stored["mentor_id"] not in self._profiles:
            raise RepositoryError("listing mentor does not exist")
        previous = self._listings.get(listing_id)
        if previous and previous["mentor_id"] != stored["mentor_id"]:
            raise RepositoryError("listing mentor_id cannot change")
        self._listings[listing_id] = stored
        return deepcopy(stored)

    def list_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._transaction_lock:
            return deepcopy(self._transactions[-max(1, min(int(limit), 1000)) :])

    def append_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        stored = deepcopy(payload)
        transaction_id = stored.get("transaction_id")
        if not isinstance(transaction_id, str) or not transaction_id or "/" in transaction_id:
            raise RepositoryError("valid transaction_id is required")
        with self._transaction_lock:
            if transaction_id in self._transaction_ids:
                raise RepositoryError("transaction_id already exists")
            self._transactions.append(stored)
            self._transaction_ids.add(transaction_id)
        return deepcopy(stored)

    def health(self) -> str:
        return "memory"


class FirestoreRepository(Repository):
    """Lazy Firebase Admin Firestore adapter.

    The adapter uses ``firebase_admin.initialize_app()`` and Application Default
    Credentials. It never accepts or reads a service-account path itself; deployment
    should provide credentials through the platform environment.
    """

    def __init__(self, client: Optional[Any] = None, *, database_id: Optional[str] = None) -> None:
        if client is not None:
            if database_id is not None:
                validate_firestore_database_id(database_id)
            self._client = client
            return
        selected_database = (configured_firestore_database_id() if database_id is None
                             else validate_firestore_database_id(database_id))
        try:
            import firebase_admin
            from firebase_admin import firestore
        except ImportError as exc:  # pragma: no cover - dependency-specific path
            raise RepositoryError("firebase-admin is required for FirestoreRepository") from exc
        try:
            if not firebase_admin._apps:
                firebase_admin.initialize_app()
            self._client = firestore.client(database_id=selected_database)
        except Exception as exc:  # pragma: no cover - requires cloud credentials
            raise RepositoryError("Firestore initialization failed") from exc

    def _timed(self, operation: Any) -> Any:
        started = time.perf_counter()
        try:
            return operation()
        finally:
            self.last_latency_ms = (time.perf_counter() - started) * 1000.0

    def list_profiles(self) -> List[Dict[str, Any]]:
        return self._timed(lambda: [{"profile_id": doc.id, **(doc.to_dict() or {})} for doc in self._client.collection("mentors").stream()])

    def upsert_profile(self, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        stored = _profile(profile_id, payload)
        document = self._client.collection("mentors").document(profile_id)
        previous = self._timed(lambda: document.get())
        existing = previous.to_dict() if previous.exists else None
        if existing and existing.get("auth_uid") and existing["auth_uid"] != stored.get("auth_uid", existing["auth_uid"]):
            raise RepositoryError("mentor auth_uid cannot change")
        if existing and existing.get("auth_uid") and "auth_uid" not in stored:
            stored["auth_uid"] = existing["auth_uid"]
        self._timed(lambda: document.set(stored, merge=True))
        return deepcopy(stored)

    def delete_profile(self, profile_id: str) -> bool:
        self._timed(lambda: self._client.collection("mentors").document(profile_id).delete())
        return True

    def get_mentor(self, mentor_id: str, verified_uid: str) -> Optional[Dict[str, Any]]:
        _document_id(mentor_id, "mentor_id")
        _document_id(verified_uid, "verified_uid", 128)
        snapshot = self._timed(lambda: self._client.collection("mentors").document(mentor_id).get())
        if not snapshot.exists:
            return None
        profile = snapshot.to_dict()
        if profile.get("auth_uid") != verified_uid:
            raise RepositoryError("mentor authorization required")
        return {**deepcopy(profile), "profile_id": mentor_id}

    def get_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        _document_id(listing_id, "listing_id")
        snapshot = self._timed(lambda: self._client.collection("service_listings").document(listing_id).get())
        if not snapshot.exists:
            return None
        return _listing(listing_id, snapshot.to_dict())

    def upsert_listing(self, listing_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        stored = _listing(listing_id, payload)
        mentor = self._timed(lambda: self._client.collection("mentors").document(stored["mentor_id"]).get())
        if not mentor.exists:
            raise RepositoryError("listing mentor does not exist")
        document = self._client.collection("service_listings").document(listing_id)
        previous = self._timed(lambda: document.get())
        if previous.exists and previous.to_dict().get("mentor_id") != stored["mentor_id"]:
            raise RepositoryError("listing mentor_id cannot change")
        self._timed(lambda: document.set(stored))
        return deepcopy(stored)

    def list_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        query = self._client.collection("historical_transactions").limit(max(1, min(int(limit), 1000)))
        return self._timed(lambda: [{"transaction_id": doc.id, **(doc.to_dict() or {})} for doc in query.stream()])

    def append_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        transaction_id = payload.get("transaction_id")
        if not isinstance(transaction_id, str) or not transaction_id or "/" in transaction_id:
            raise RepositoryError("valid transaction_id is required")
        self._timed(lambda: self._client.collection("historical_transactions").document(transaction_id).create(payload))
        return deepcopy(payload)

    def health(self) -> str:
        return "firestore"

    def probe_readiness(self) -> bool:
        """Verify the configured Firestore backend is reachable without writing data."""
        self._client.collection("mentors").limit(1).get(timeout=3)
        return True

