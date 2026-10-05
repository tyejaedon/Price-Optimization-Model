"""Environment-only configuration for the protected deployment entrypoint."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DeploymentConfig:
    artifact_dir: str
    tariff_csv_path: str
    firebase_project_id: str

    @classmethod
    def from_env(cls) -> "DeploymentConfig":
        # Firebase Admin accepts unsigned emulator tokens when this variable is
        # set. Never allow emulator mode in the protected deployment entrypoint.
        if "FIREBASE_AUTH_EMULATOR_HOST" in os.environ or "FIRESTORE_EMULATOR_HOST" in os.environ:
            raise ValueError("Firebase emulators are not allowed in the protected API")
        project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
        if not project_id:
            raise ValueError("FIREBASE_PROJECT_ID is required for the protected API")
        return cls(
            artifact_dir=os.getenv("PRICING_ARTIFACT_DIR", "/opt/pricing/artifacts"),
            tariff_csv_path=os.getenv("PRICING_TARIFF_CSV", "/opt/pricing/tariff.csv"),
            firebase_project_id=project_id,
        )
