"""Trusted-service persistence boundary for mentors, root listings and quote audits.

``InMemoryRepository`` is a process-local development/test substitute; Firestore
uses durable root collections through Firebase Admin. Neither adapter verifies
tokens: callers supply an already verified Firebase UID to ``get_mentor``. The
mentor document ID may differ from that UID; ownership is the stored ``auth_uid``
binding, never coincidental ID equality. Gateway checks of account status and
country are separate from this repository's ownership check.

Root ``service_listings`` use stable source document IDs and a ``mentor_id``
lookup key, not a nested collection or relational join. DTO validation checks
shape, not empirical provenance: trusted publishers must approve consented text,
the KES/hour peer rate and the release-matched 50D vector. Marketplace asking
rates/job budgets are not thereby verified payments or mentor earnings.

``historical_transactions`` are append-only pricing audits, not payment
settlements. Missing reads return None; authorization/validation and backend
failures must not be treated as missing records. A successful quote does not
guarantee its asynchronous audit was persisted.

See ../docs/README.md (glossary), ../docs/M11.1_Firestore_Listing_Peers.md
(ownership/provenance) and ../docs/M11.2_Pricing_Audit.md (retry/durability limits).
"""

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
    """Service/admin contract; not a client-facing authorization or payment API."""

    @abstractmethod
    def list_profiles(self) -> List[Dict[str, Any]]:
        """List mentor profiles for trusted administration, including private fields."""
        raise NotImplementedError

    @abstractmethod
    def upsert_profile(self, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a mentor and retain any existing immutable ``auth_uid`` binding."""
        raise NotImplementedError

    @abstractmethod
    def delete_profile(self, profile_id: str) -> bool:
        """Delete a mentor only; this does not cascade to listings or quote audits."""
        raise NotImplementedError

    @abstractmethod
    def get_mentor(self, mentor_id: str, verified_uid: str) -> Optional[Dict[str, Any]]:
        """Match stored ``auth_uid`` to a caller-verified UID, or reject the read.

        Return None only for a missing mentor. This does not verify a token or
        check account status/country; those remain the protected gateway's job.
        """
        raise NotImplementedError

    @abstractmethod
    def get_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Read a root listing by its stable document ID (trusted service only)."""
        raise NotImplementedError

    @abstractmethod
    def upsert_listing(self, listing_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate/publish a root listing whose provenance the caller approved.

        Require an existing mentor and preserve its ownership key. Schema
        validation cannot independently verify the source rate or fitted vector.
        """
        raise NotImplementedError

    @abstractmethod
    def list_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Read persisted quote audits with a limit clamped to 1..1000, not payments."""
        raise NotImplementedError

    @abstractmethod
    def append_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create an audit with a unique transaction_id; never replace an existing one.

        A duplicate is an error, not an update or a guarantee of retry success.
        Callers own payload construction, retry policy and failure reporting.
        """
        raise NotImplementedError

    @abstractmethod
    def health(self) -> str:
        """Return the adapter label, not proof of live backend connectivity."""
        raise NotImplementedError


class InMemoryRepository(Repository):
    """Process-local repository for development/tests, lost on process restart.

    Reads/returned writes are deep copies. Only transaction append/read operations
    are lock-protected; this is not a general concurrent Firestore emulator.
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._listings: Dict[str, Dict[str, Any]] = {}
        self._transactions: List[Dict[str, Any]] = []
        self._transaction_ids: set[str] = set()
        self._transaction_lock = threading.Lock()

    def list_profiles(self) -> List[Dict[str, Any]]:
        """Return detached copies of all locally stored mentor profiles."""
        return deepcopy(list(self._profiles.values()))

    def upsert_profile(self, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Replace a validated local profile, preserving its existing owner UID."""
        stored = _profile(profile_id, payload)
        previous = self._profiles.get(profile_id)
        if previous and previous.get("auth_uid") and previous["auth_uid"] != stored.get("auth_uid", previous["auth_uid"]):
            raise RepositoryError("mentor auth_uid cannot change")
        if previous and previous.get("auth_uid") and "auth_uid" not in stored:
            stored["auth_uid"] = previous["auth_uid"]
        self._profiles[profile_id] = stored
        return deepcopy(stored)

    def delete_profile(self, profile_id: str) -> bool:
        """Remove a local mentor and report whether it existed; do not cascade."""
        return self._profiles.pop(profile_id, None) is not None

    def get_mentor(self, mentor_id: str, verified_uid: str) -> Optional[Dict[str, Any]]:
        """Return a copy only for the stored owner UID; missing mentors yield None."""
        _document_id(mentor_id, "mentor_id")
        _document_id(verified_uid, "verified_uid", 128)
        profile = self._profiles.get(mentor_id)
        if profile is not None and profile.get("auth_uid") != verified_uid:
            raise RepositoryError("mentor authorization required")
        return deepcopy(profile)

    def get_listing(self, listing_id: str) -> Optional[Dict[str, Any]]:
        """Read a detached root listing by validated ID, or None if absent."""
        _document_id(listing_id, "listing_id")
        return deepcopy(self._listings.get(listing_id))

    def upsert_listing(self, listing_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Replace a validated listing without reassigning its existing mentor."""
        stored = _listing(listing_id, payload)
        if stored["mentor_id"] not in self._profiles:
            raise RepositoryError("listing mentor does not exist")
        previous = self._listings.get(listing_id)
        if previous and previous["mentor_id"] != stored["mentor_id"]:
            raise RepositoryError("listing mentor_id cannot change")
        self._listings[listing_id] = stored
        return deepcopy(stored)

    def list_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return copies of the latest appended audits in their insertion order."""
        with self._transaction_lock:
            return deepcopy(self._transactions[-max(1, min(int(limit), 1000)) :])

    def append_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Atomically reserve a unique ID and append a copied audit; reject duplicates."""
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
        """Report ``memory`` without implying durable persistence."""
        return "memory"


class FirestoreRepository(Repository):
    """Lazy Firebase Admin Firestore adapter.

    The adapter uses ``firebase_admin.initialize_app()`` and Application Default
    Credentials. It never accepts or reads a service-account path itself; deployment
    should provide credentials through the platform environment.

    An injected client supports offline tests; otherwise initialization selects
    the configured database. Backend exceptions propagate from operations.
    ``last_latency_ms`` describes only the last timed call, not aggregate metrics.
    Ownership read-then-write checks are not atomic Firestore transactions;
    trusted writers and IAM remain necessary.
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
        """Stream root ``mentors`` for trusted administration, without pagination."""
        return self._timed(lambda: [{"profile_id": doc.id, **(doc.to_dict() or {})} for doc in self._client.collection("mentors").stream()])

    def upsert_profile(self, profile_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Merge a validated mentor after checking/preserving its stored owner UID."""
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
        """Delete a mentor without cascading; return True even if it was absent."""
        self._timed(lambda: self._client.collection("mentors").document(profile_id).delete())
        return True

    def get_mentor(self, mentor_id: str, verified_uid: str) -> Optional[Dict[str, Any]]:
        """Read one mentor and enforce stored UID ownership; propagate backend failures."""
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
        """Validate one root listing on read; return None only for a missing document."""
        _document_id(listing_id, "listing_id")
        snapshot = self._timed(lambda: self._client.collection("service_listings").document(listing_id).get())
        if not snapshot.exists:
            return None
        return _listing(listing_id, snapshot.to_dict())

    def upsert_listing(self, listing_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Replace a root listing after mentor existence and stable-ownership checks."""
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
        """Read up to the clamped audit limit; no chronological ordering is requested."""
        query = self._client.collection("historical_transactions").limit(max(1, min(int(limit), 1000)))
        return self._timed(lambda: [{"transaction_id": doc.id, **(doc.to_dict() or {})} for doc in query.stream()])

    def append_transaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Use Firestore create-only semantics; duplicate IDs/backend errors propagate."""
        transaction_id = payload.get("transaction_id")
        if not isinstance(transaction_id, str) or not transaction_id or "/" in transaction_id:
            raise RepositoryError("valid transaction_id is required")
        # create(), unlike set(), cannot overwrite an earlier audit on retry.
        self._timed(lambda: self._client.collection("historical_transactions").document(transaction_id).create(payload))
        return deepcopy(payload)

    def health(self) -> str:
        """Report ``firestore``; use probe_readiness for a live connectivity check."""
        return "firestore"

    def probe_readiness(self) -> bool:
        """Verify the configured Firestore backend is reachable without writing data."""
        self._client.collection("mentors").limit(1).get(timeout=3)
        return True
