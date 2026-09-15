"""FastAPI service and administrator boundary for UC8-UC11.

Firestore and model inference are dependency-injected. Local startup defaults to an
in-memory repository and an unready inference state; production can construct a
FirestoreRepository and a loaded model callable without exposing credentials here.
"""

from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Literal, Optional, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from src.api_contracts import (
    GridSearchConfigDTO,
    HealthResponseDTO,
    HistoricalTransactionDTO,
    MetricsResponseDTO,
    PredictionResultDTO,
    PricingQueryDTO,
    ProfileDTO,
    RetrainResponseDTO,
)
from src.mlops_service import MLOpsService
from src.ingest_multisource import SUPPORTED_INDUSTRY_PARTITIONS, map_industry_partition
from src.macro_arbitrage import DEFAULT_MACRO_LOOKUP, ContinuousMetadataNormalizer, fuse_coordinates
from src.nlp_pipeline import TextFeatureReducer
from src.observability import MetricsRegistry
from src.repository import InMemoryRepository, Repository
from src.spatial_engine import DEFAULT_QUERY_NEIGHBORS, DomainPartitionedKDTreeIndexer
from src.tariff_evaluator import DEFAULT_MPESA_TARIFF_CSV, MpesaTariffEvaluator

InferenceCallable = Callable[[PricingQueryDTO], Dict[str, Any]]


class ServiceDependencies:
    def __init__(
        self,
        repository: Repository,
        mlops: MLOpsService,
        metrics: MetricsRegistry,
        inference: Optional[InferenceCallable],
        admin_token: Optional[str],
    ) -> None:
        self.repository = repository
        self.mlops = mlops
        self.metrics = metrics
        self.inference = inference
        self.admin_token = admin_token


class InferenceRuntime:
    """Loads the merged M7 artifacts and exposes the production prediction path."""

    def __init__(self, artifact_dir: str, macro_lookup_path: str, tariff_csv_path: str, firestore_enabled: bool = False) -> None:
        self.artifact_dir = artifact_dir
        self.macro_lookup_path = macro_lookup_path
        self.tariff_csv_path = tariff_csv_path
        self.firestore_enabled = firestore_enabled
        self.reducer: Optional[TextFeatureReducer] = None
        self.metadata_normalizer: Optional[ContinuousMetadataNormalizer] = None
        self.spatial_indexer: Optional[DomainPartitionedKDTreeIndexer] = None
        self.tariff_evaluator: Optional[MpesaTariffEvaluator] = None
        self.load_error: Optional[str] = None

    @property
    def models_loaded(self) -> bool:
        return all(component is not None for component in (self.reducer, self.metadata_normalizer, self.spatial_indexer, self.tariff_evaluator))

    @property
    def database_status(self) -> Literal["firestore", "unconfigured", "unavailable"]:
        if not self.firestore_enabled:
            return "unconfigured"
        try:
            import firebase_admin  # noqa: F401
        except ImportError:
            return "unavailable"
        return "firestore"

    def load(self) -> None:
        try:
            self.reducer = TextFeatureReducer.load_artifacts(self.artifact_dir)
            self.metadata_normalizer = ContinuousMetadataNormalizer.load_artifacts(self.artifact_dir)
            self.spatial_indexer = DomainPartitionedKDTreeIndexer.load_artifacts(self.artifact_dir)
            self.tariff_evaluator = MpesaTariffEvaluator.from_csv(self.tariff_csv_path)
            self.load_error = None
        except (FileNotFoundError, KeyError, RuntimeError, ValueError, OSError) as exc:
            self.reducer = None
            self.metadata_normalizer = None
            self.spatial_indexer = None
            self.tariff_evaluator = None
            self.load_error = str(exc)

    def _partition(self, selected_industry: str) -> str:
        normalized = selected_industry.strip().lower()
        return normalized if normalized in SUPPORTED_INDUSTRY_PARTITIONS else map_industry_partition(selected_industry)

    def predict(self, query: PricingQueryDTO) -> PredictionResultDTO:
        if not self.models_loaded:
            raise RuntimeError(self.load_error or "Inference artifacts are not loaded.")
        assert self.reducer is not None and self.metadata_normalizer is not None
        assert self.spatial_indexer is not None and self.tariff_evaluator is not None
        text_vector = self.reducer.transform([query.raw_description])
        raw_metadata = self.metadata_normalizer.build_live_metadata_vector(
            query.mentor_country, query.client_country, query.market_saturation_score, query.competitiveness_score
        )
        normalized_metadata = self.metadata_normalizer.transform_live_metadata(
            query.mentor_country, query.client_country, query.market_saturation_score, query.competitiveness_score
        )
        fused = fuse_coordinates(text_vector, normalized_metadata)
        prediction = self.spatial_indexer.predict_base_rate(
            fused, requested_partition=self._partition(query.selected_industry), k=DEFAULT_QUERY_NEIGHBORS, allow_fallback=True
        )
        quote = self.tariff_evaluator.evaluate_quote(float(prediction["base_predicted_rate"]), query.mentor_country)
        return PredictionResultDTO(
            base_predicted_rate=quote["base_predicted_rate"],
            mpesa_tariff_surcharge=quote["mpesa_tariff_surcharge"],
            final_quoted_rate=quote["final_quoted_rate"],
            currency="KES",
            bilateral_arbitrage_factor=float(raw_metadata[0, 0]),
            mentor_country_iso2=quote["mentor_country_iso2"],
            nearest_neighbors=prediction["nearest_neighbors"],
        )


def _admin_guard(
    dependencies: ServiceDependencies,
    admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> ServiceDependencies:
    configured = dependencies.admin_token
    if not configured:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="administrator authorization required")
    if not admin_token or not hmac.compare_digest(admin_token, configured):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="administrator authorization required")
    return dependencies


def create_app(
    artifact_dir: str = "artifacts",
    macro_lookup_path: str = DEFAULT_MACRO_LOOKUP,
    tariff_csv_path: str = DEFAULT_MPESA_TARIFF_CSV,
    firestore_enabled: bool = False,
    *,
    repository: Optional[Repository] = None,
    mlops: Optional[MLOpsService] = None,
    metrics: Optional[MetricsRegistry] = None,
    inference: Optional[InferenceCallable] = None,
    admin_token: Optional[str] = None,
) -> FastAPI:
    runtime = InferenceRuntime(artifact_dir, macro_lookup_path, tariff_csv_path, firestore_enabled)
    runtime_inference = inference is None
    if inference is None:
        inference = runtime.predict
    resolved_metrics = metrics or MetricsRegistry()
    dependencies = ServiceDependencies(
        repository=repository or InMemoryRepository(),
        mlops=mlops or MLOpsService(),
        metrics=resolved_metrics,
        inference=inference,
        admin_token=admin_token if admin_token is not None else os.getenv("MLOPS_ADMIN_TOKEN"),
    )
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if runtime_inference:
            runtime.load()
        app.state.inference_runtime = runtime
        yield

    app = FastAPI(title="Price Optimization Model API", version="m8.7", lifespan=lifespan)
    app.state.dependencies = dependencies

    def require_admin(
        admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    ) -> ServiceDependencies:
        return _admin_guard(dependencies, admin_token)

    @app.middleware("http")
    async def record_api_latency(request: Request, call_next: Any) -> JSONResponse:
        operation = f"api.{request.method.lower()}.{request.url.path}"
        with resolved_metrics.timer(operation):
            response = await call_next(request)
        return response

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": "internal server error"})

    def current_health() -> HealthResponseDTO:
        database = runtime.database_status if runtime_inference and repository is None else dependencies.repository.health()
        models_loaded = runtime.models_loaded if runtime_inference else dependencies.inference is not None
        healthy = models_loaded and database in {"firestore", "memory", "unconfigured"}
        return HealthResponseDTO(
            status="HEALTHY" if healthy else "DEGRADED",
            models_loaded=models_loaded,
            database=database if database in {"firestore", "memory", "unconfigured"} else "unavailable",
        )

    @app.get("/health", response_model=HealthResponseDTO)
    async def health() -> HealthResponseDTO:
        return current_health()

    @app.post("/api/v1/optimize-price", response_model=PredictionResultDTO)
    async def optimize_price(query: PricingQueryDTO) -> PredictionResultDTO:
        if runtime_inference and not runtime.models_loaded:
            raise HTTPException(status_code=503, detail="model artifacts are not loaded")
        try:
            with resolved_metrics.timer("inference.optimize_price"):
                payload = dependencies.inference(query)
            prediction = PredictionResultDTO.model_validate(payload)
            audit_payload = {
                "transaction_id": f"api-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}",
                "client_country_code": query.client_country,
                "base_predicted_rate": prediction.base_predicted_rate,
                "mpesa_tariff_surcharge": prediction.mpesa_tariff_surcharge,
                "final_quoted_rate": prediction.final_quoted_rate,
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
            with resolved_metrics.timer("database.append_transaction"):
                dependencies.repository.append_transaction(audit_payload)
            return prediction
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail="inference failed") from exc

    @app.get("/api/v1/admin/metrics", response_model=MetricsResponseDTO)
    async def admin_metrics(_: ServiceDependencies = Depends(require_admin)) -> MetricsResponseDTO:
        return MetricsResponseDTO(metrics=resolved_metrics.snapshot(), tuning=dependencies.mlops.get_tuning().to_dict())

    @app.get("/api/v1/admin/grid-search", response_model=GridSearchConfigDTO)
    async def get_grid_search(_: ServiceDependencies = Depends(require_admin)) -> GridSearchConfigDTO:
        return GridSearchConfigDTO.model_validate(dependencies.mlops.get_tuning().to_dict())

    @app.put("/api/v1/admin/grid-search", response_model=GridSearchConfigDTO)
    async def update_grid_search(config: GridSearchConfigDTO, _: ServiceDependencies = Depends(require_admin)) -> GridSearchConfigDTO:
        return GridSearchConfigDTO.model_validate(dependencies.mlops.update_tuning(config).to_dict())

    @app.post("/api/v1/admin/retrain", response_model=RetrainResponseDTO)
    async def retrain(_: ServiceDependencies = Depends(require_admin)) -> RetrainResponseDTO:
        result = dependencies.mlops.trigger_retrain()
        return RetrainResponseDTO.model_validate(result)

    @app.get("/api/v1/admin/retrain/{job_id}")
    async def retrain_status(job_id: str, _: ServiceDependencies = Depends(require_admin)) -> Dict[str, Any]:
        return dependencies.mlops.job_status(job_id)

    @app.get("/api/v1/admin/profiles")
    async def list_profiles(_: ServiceDependencies = Depends(require_admin)) -> Any:
        with resolved_metrics.timer("database.list_profiles"):
            return dependencies.repository.list_profiles()

    @app.put("/api/v1/admin/profiles/{profile_id}", response_model=ProfileDTO)
    async def upsert_profile(profile_id: str, profile: ProfileDTO, _: ServiceDependencies = Depends(require_admin)) -> ProfileDTO:
        if profile.profile_id != profile_id:
            raise HTTPException(status_code=422, detail="profile_id path and payload must match")
        with resolved_metrics.timer("database.upsert_profile"):
            stored = dependencies.repository.upsert_profile(profile_id, profile.model_dump())
        return ProfileDTO.model_validate(stored)

    @app.delete("/api/v1/admin/profiles/{profile_id}")
    async def delete_profile(profile_id: str, _: ServiceDependencies = Depends(require_admin)) -> Dict[str, Any]:
        with resolved_metrics.timer("database.delete_profile"):
            deleted = dependencies.repository.delete_profile(profile_id)
        return {"profile_id": profile_id, "deleted": deleted}

    @app.get("/api/v1/admin/history")
    async def list_history(limit: int = 100, _: ServiceDependencies = Depends(require_admin)) -> Any:
        with resolved_metrics.timer("database.list_transactions"):
            return dependencies.repository.list_transactions(limit=limit)

    return app


app = create_app()

