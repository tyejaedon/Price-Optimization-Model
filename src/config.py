"""Environment-only configuration for the protected deployment entrypoint."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


def validate_firestore_database_id(database_id: str) -> str:
    """Accept the default database or a Firestore-compatible named database ID."""
    if database_id != "(default)" and (
        not isinstance(database_id, str)
        or re.fullmatch(r"[a-z][a-z0-9-]{2,61}[a-z0-9]", database_id) is None
    ):
        raise ValueError("FIRESTORE_DATABASE_ID must be (default) or a valid named database ID")
    return database_id


def configured_firestore_database_id() -> str:
    return validate_firestore_database_id(os.getenv("FIRESTORE_DATABASE_ID", "(default)"))


@dataclass(frozen=True)
class DeploymentConfig:
    artifact_dir: str
    tariff_csv_path: str
    tariff_sha256: str
    firebase_project_id: str
    firestore_database_id: str = "(default)"

    @classmethod
    def from_env(cls) -> "DeploymentConfig":
        # Firebase Admin accepts unsigned emulator tokens when this variable is
        # set. Never allow emulator mode in the protected deployment entrypoint.
        if "FIREBASE_AUTH_EMULATOR_HOST" in os.environ or "FIRESTORE_EMULATOR_HOST" in os.environ:
            raise ValueError("Firebase emulators are not allowed in the protected API")
        project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
        if not project_id:
            raise ValueError("FIREBASE_PROJECT_ID is required for the protected API")
        database_id = configured_firestore_database_id()
        tariff_sha256 = os.getenv("PRICING_TARIFF_SHA256", "")
        if re.fullmatch(r"[0-9a-f]{64}", tariff_sha256) is None:
            raise ValueError("PRICING_TARIFF_SHA256 must be a trusted lowercase SHA-256 digest")
        return cls(
            artifact_dir=os.getenv("PRICING_ARTIFACT_DIR", "/opt/pricing/artifacts"),
            tariff_csv_path=os.getenv("PRICING_TARIFF_CSV", "/opt/pricing/tariff.csv"),
            tariff_sha256=tariff_sha256,
            firebase_project_id=project_id,
            firestore_database_id=database_id,
        )
