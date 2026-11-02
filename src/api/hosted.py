"""Hosted ASGI entrypoint for Render and cloud services with PLATFORM_PRICE_KEY authentication.

This module configures and launches the Price Optimization service for hosted environments
such as Render (https://render.com), enabling the Career Mentor OS platform adapter
(contract #99) on ``POST /price`` with ``PLATFORM_PRICE_KEY`` authentication.

Features:
- Automatically resolves artifact directory and versioned M-Pesa tariff schedule.
- Uses pinned SHA-256 digests for artifacts and tariff schedules.
- Auto-seeds mentor profiles from ``platform_mentor_corpus`` (or fixture cache)
  so ``POST /price`` queries resolve without requiring inline description strings.
- Gracefully supports both standalone platform pricing (in-memory repository)
  and cloud persistence (Firestore + Firebase Admin) when configured.
- Conforms to Render's dynamic ``$PORT`` binding and ``/health`` probes.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

from src.api.repository import FirestoreRepository, InMemoryRepository, Repository
from src.api.serve import create_app
from src.core.config import configured_firestore_database_id, parse_cors_allowed_origins

logger = logging.getLogger(__name__)

DEFAULT_HOSTED_TARIFF_SHA256 = (
    "4390d9d5ec920c68000da8562c140e7477a0afac22ad41c8a2fa23227761e882"
)
DEFAULT_HOSTED_MANIFEST_SHA256 = (
    "568edb5c088564fd637de052d51eeaa902ab6c759d29eb10251fdc6880920226"
)


def _resolve_paths() -> tuple[str, str]:
    """Resolve artifact directory and tariff CSV path with sensible hosted fallbacks."""
    # Check explicitly configured artifact directory, then standard fallback locations
    configured_artifacts = os.getenv("PRICING_ARTIFACT_DIR", "").strip()
    if configured_artifacts and os.path.isdir(configured_artifacts):
        artifact_dir = configured_artifacts
    elif os.path.isdir("artifacts"):
        artifact_dir = "artifacts"
    elif os.path.isdir("/opt/pricing/artifacts"):
        artifact_dir = "/opt/pricing/artifacts"
    else:
        artifact_dir = "artifacts"

    # Check explicitly configured tariff CSV, then fallback locations
    configured_tariff = os.getenv("PRICING_TARIFF_CSV", "").strip()
    if configured_tariff and os.path.isfile(configured_tariff):
        tariff_csv = configured_tariff
    elif os.path.isfile("config/tariffs/mpesa_p2p_users_2026-08-04.csv"):
        tariff_csv = "config/tariffs/mpesa_p2p_users_2026-08-04.csv"
    elif os.path.isfile("/opt/pricing/tariff.csv"):
        tariff_csv = "/opt/pricing/tariff.csv"
    else:
        tariff_csv = "config/tariffs/mpesa_p2p_users_2026-08-04.csv"

    return artifact_dir, tariff_csv


def create_hosted_app():
    """Build the hosted application instance optimized for Render deployment."""
    artifact_dir, tariff_csv = _resolve_paths()

    tariff_sha256 = (
        os.getenv("PRICING_TARIFF_SHA256", "").strip()
        or DEFAULT_HOSTED_TARIFF_SHA256
    )
    manifest_sha256 = (
        os.getenv("PRICING_ARTIFACT_MANIFEST_SHA256", "").strip()
        or DEFAULT_HOSTED_MANIFEST_SHA256
    )

    firebase_project = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    repository: Repository
    token_verifier: Optional[Callable[[str], Any]] = None
    readiness_probe: Optional[Callable[[], bool]] = None
    firestore_enabled = False

    if firebase_project:
        try:
            import firebase_admin
            from firebase_admin import auth

            try:
                firebase_app = firebase_admin.get_app()
            except ValueError:
                firebase_app = firebase_admin.initialize_app(
                    options={"projectId": firebase_project}
                )

            database_id = configured_firestore_database_id()
            firestore_repo = FirestoreRepository(database_id=database_id)
            repository = firestore_repo
            token_verifier = lambda token: auth.verify_id_token(token, app=firebase_app)
            readiness_probe = firestore_repo.probe_readiness
            firestore_enabled = True
            logger.info("Hosted service connected to Firestore (project=%s, db=%s)", firebase_project, database_id)
        except Exception as exc:
            logger.warning(
                "Firestore initialization failed (%s); falling back to in-memory repository",
                exc,
            )
            repository = InMemoryRepository()
    else:
        repository = InMemoryRepository()
        logger.info("Hosted service initialized with InMemoryRepository")

    cors_env = os.getenv("PRICING_CORS_ALLOWED_ORIGINS", "").strip()
    cors_origins = parse_cors_allowed_origins(cors_env) if cors_env else ()

    auto_seed = os.getenv("SEED_PLATFORM_MENTORS", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }

    app = create_app(
        artifact_dir=artifact_dir,
        tariff_csv_path=tariff_csv,
        trusted_tariff_sha256=tariff_sha256,
        trusted_manifest_sha256=manifest_sha256,
        firestore_enabled=firestore_enabled,
        repository=repository,
        token_verifier=token_verifier,
        readiness_probe=readiness_probe,
        cors_allowed_origins=cors_origins,
        seed_platform_mentors=auto_seed,
    )

    platform_key = os.getenv("PLATFORM_PRICE_KEY", "").strip()
    if platform_key:
        logger.info("Career Mentor OS platform pricing route enabled (POST /price)")
    else:
        logger.warning("PLATFORM_PRICE_KEY is unset; POST /price will return 503 until set")

    return app


app = create_hosted_app()

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.api.hosted:app", host="0.0.0.0", port=port, reload=False)
