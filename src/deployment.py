"""Protected ASGI entrypoint for container deployments (not the legacy local app)."""

import firebase_admin
from firebase_admin import auth

from src.config import DeploymentConfig
from src.repository import FirestoreRepository
from src.serve import create_app


def create_deployment_app():
    config = DeploymentConfig.from_env()
    try:
        firebase_app = firebase_admin.get_app()
    except ValueError:
        firebase_app = firebase_admin.initialize_app(options={"projectId": config.firebase_project_id})
    if firebase_app.project_id != config.firebase_project_id:
        raise ValueError("Firebase Admin project does not match FIREBASE_PROJECT_ID")
    # FirestoreRepository initializes Firebase Admin with ADC if needed. Never
    # silently substitute an in-memory repository in a deployed gateway.
    repository = FirestoreRepository()

    def verify_token(token: str):
        return auth.verify_id_token(token, app=firebase_app)

    return create_app(
        artifact_dir=config.artifact_dir,
        tariff_csv_path=config.tariff_csv_path,
        firestore_enabled=True,
        repository=repository,
        token_verifier=verify_token,
        readiness_probe=repository.probe_readiness,
    )


app = create_deployment_app()
