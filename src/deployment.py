"""Protected ASGI entrypoint for deployments, unlike unauthenticated ``src.serve:app``.

This module builds the production dependency set explicitly: Firebase Admin verifies
bearer tokens, Firestore is required (there is no in-memory fallback), and ``/ready``
probes repository availability. ``create_app`` also receives the independently
configured manifest digest so artifact bytes are pinned before joblib loading.
"""

import firebase_admin
from firebase_admin import auth

from src.config import DeploymentConfig
from src.repository import FirestoreRepository
from src.serve import create_app


def create_deployment_app():
    """Construct the deployed gateway and reject Firebase project mismatches."""
    config = DeploymentConfig.from_env()
    try:
        firebase_app = firebase_admin.get_app()
    except ValueError:
        firebase_app = firebase_admin.initialize_app(options={"projectId": config.firebase_project_id})
    if firebase_app.project_id != config.firebase_project_id:
        raise ValueError("Firebase Admin project does not match FIREBASE_PROJECT_ID")
    # FirestoreRepository initializes Firebase Admin with ADC if needed. Never
    # silently substitute an in-memory repository in a deployed gateway.
    repository = FirestoreRepository(database_id=config.firestore_database_id)

    def verify_token(token: str):
        return auth.verify_id_token(token, app=firebase_app)

    return create_app(
        artifact_dir=config.artifact_dir,
        tariff_csv_path=config.tariff_csv_path,
        trusted_tariff_sha256=config.tariff_sha256,
        firestore_enabled=True,
        repository=repository,
        token_verifier=verify_token,
        readiness_probe=repository.probe_readiness,
    )


app = create_deployment_app()
