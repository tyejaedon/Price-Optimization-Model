"""FastAPI service and administrator boundary for UC8-UC11.

Firestore and model inference are dependency-injected. Local startup defaults to an
in-memory repository and an unready inference state; production can construct a
FirestoreRepository and a loaded model callable without exposing credentials here.
"""

from __future__ import annotations

import hmac
import json
import logging
import math
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Literal, Optional, cast
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from src.artifact_contract import ARTIFACT_FILES, MANIFEST_NAME, verify_manifest
from src.platform_price import register_platform_price
from src.api_contracts import (
    CanonicalPredictionResultDTO,
    CanonicalPricingQueryDTO,
    GridSearchConfigDTO,
    HealthResponseDTO,
    HealthStatusDTO,
    MetricsResponseDTO,
    PredictionResultDTO,
    PricingQueryDTO,
    ProfileDTO,
    RetrainResponseDTO,
)
from src.interval_synthesizer import FloorExceedsCeilingError, synthesize_corridor
from src.mlops_service import MLOpsService
from src.ingest_multisource import SUPPORTED_INDUSTRY_PARTITIONS, map_industry_partition
from src.macro_arbitrage import (
    DEFAULT_BUNDLED_MACRO_LOOKUP,
    DEFAULT_FEATURE_NAMES,
    DEFAULT_INFERENCE_CONFIG_ARTIFACT,
    DEFAULT_MACRO_LOOKUP,
    HYBRID_VECTOR_DIMENSIONS,
    TEXT_VECTOR_DIMENSIONS,
    ContinuousMetadataNormalizer,
    fuse_coordinates,
)
from src.nlp_pipeline import TextFeatureReducer, ensure_text_dimensions
from src.observability import MetricsRegistry
from src.repository import InMemoryRepository, Repository, RepositoryError
from src.spatial_engine import DomainPartitionedKDTreeIndexer
from src.tariff_evaluator import DEFAULT_MPESA_TARIFF_CSV, MpesaTariffEvaluator

InferenceCallable = Callable[[PricingQueryDTO], Dict[str, Any] | PredictionResultDTO]
logger = logging.getLogger(__name__)


def _append_pricing_audit(repository: Repository, metrics: MetricsRegistry, payload: Dict[str, Any]) -> None:
    """Try a create-only write twice; never let a background exception disappear."""
    try:
        with metrics.timer("audit.persist"):
            for attempt in range(2):
                try:
                    with metrics.timer("database.append_transaction"):
                        repository.append_transaction(payload)
                    return
                except Exception:
                    if attempt == 1:
                        raise
    except Exception as exc:
        # Exception messages and tracebacks may contain credentials or profile text.
        logger.error("pricing audit not persisted transaction_id=%s attempts=2 error_type=%s",
                     payload["transaction_id"], type(exc).__name__)


class ServiceDependencies:
    def __init__(
        self,
        repository: Repository,
        mlops: MLOpsService,
        metrics: MetricsRegistry,
        inference: InferenceCallable,
        admin_token: Optional[str],
    ) -> None:
        self.repository = repository
        self.mlops = mlops
        self.metrics = metrics
        self.inference = inference
        self.admin_token = admin_token


class InferenceRuntime:
    """Loads the merged M7 artifacts and exposes the production prediction path."""

    def __init__(self, artifact_dir: str, macro_lookup_path: str, tariff_csv_path: str, firestore_enabled: bool = False,
                 trusted_manifest_sha256: Optional[str] = None) -> None:
        self.artifact_dir = artifact_dir
        self.macro_lookup_path = macro_lookup_path
        self.tariff_csv_path = tariff_csv_path
        self.firestore_enabled = firestore_enabled
        self.reducer: Optional[TextFeatureReducer] = None
        self.metadata_normalizer: Optional[ContinuousMetadataNormalizer] = None
        self.spatial_indexer: Optional[DomainPartitionedKDTreeIndexer] = None
        self.tariff_evaluator: Optional[MpesaTariffEvaluator] = None
        self.load_error: Optional[str] = None
        self.inference_config: Optional[Dict[str, Any]] = None
        self.trusted_manifest_sha256 = trusted_manifest_sha256
        self.manifest: Optional[Dict[str, Any]] = None

    @property
    def models_loaded(self) -> bool:
        return self.manifest is not None and self.inference_config is not None and all(component is not None for component in (self.reducer, self.metadata_normalizer, self.spatial_indexer, self.tariff_evaluator))

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
            manifest = verify_manifest(self.artifact_dir, self.trusted_manifest_sha256)
            with open(os.path.join(self.artifact_dir, DEFAULT_INFERENCE_CONFIG_ARTIFACT), encoding="utf-8") as handle:
                config = json.load(handle)
            if (
                config["version"] != 1
                or config["text_dimensions"] != TEXT_VECTOR_DIMENSIONS
                or config["metadata_features"] != list(DEFAULT_FEATURE_NAMES)
            ):
                raise ValueError("Incompatible inference feature schema.")
            if (
                type(config["k_neighbors"]) is not int or config["k_neighbors"] < 1
                or type(config["idw_epsilon"]) not in (int, float)
                or not math.isfinite(config["idw_epsilon"])
                or not (0 < config["idw_epsilon"] <= 1)
            ):
                raise ValueError("Invalid inference KNN configuration.")
            if not all(
                type(config[key]) in (int, float) and math.isfinite(config[key]) and config[key] >= 0
                for key in ("text_weight", "metadata_weight")
            ):
                raise ValueError("Invalid inference feature weights.")
            if not isinstance(config["partition_density"], dict) or not all(
                type(value) in (int, float) and math.isfinite(value) and value >= 0
                for value in config["partition_density"].values()
            ):
                raise ValueError("Missing partition density mapping.")
            if (manifest["query_policy"] != {key: config[key] for key in ("k_neighbors", "idw_epsilon", "text_weight", "metadata_weight")}
                or manifest["partition_policy"] != {key: config[key] for key in ("minimum_partition_size", "fallback_partition", "allow_fallback", "partition_density")}):
                raise ValueError("Incompatible manifest query or partition policy")
            if (type(config["minimum_partition_size"]) is not int or config["minimum_partition_size"] < 1
                or type(config["allow_fallback"]) is not bool
                or config["fallback_partition"] not in SUPPORTED_INDUSTRY_PARTITIONS):
                raise ValueError("Invalid partition policy")
            macro_path = os.path.join(self.artifact_dir, DEFAULT_BUNDLED_MACRO_LOOKUP)
            self.reducer = TextFeatureReducer.load_artifacts(self.artifact_dir)
            if self.reducer.n_components_requested != TEXT_VECTOR_DIMENSIONS or self.reducer.reducer.n_components > TEXT_VECTOR_DIMENSIONS:
                raise ValueError("Incompatible fitted text dimensions.")
            self.metadata_normalizer = ContinuousMetadataNormalizer.load_artifacts(self.artifact_dir, macro_lookup_path=macro_path)
            self.spatial_indexer = DomainPartitionedKDTreeIndexer.load_artifacts(self.artifact_dir)
            if (
                self.spatial_indexer.hybrid_dimensions != HYBRID_VECTOR_DIMENSIONS
                or not self.spatial_indexer.partition_verified_rates
                or not set(self.spatial_indexer.active_partitions()).issubset(config["partition_density"])
                or set(self.spatial_indexer.partition_counts) != set(self.spatial_indexer.active_partitions())
                or set(self.spatial_indexer.partition_verified_rates) != set(self.spatial_indexer.active_partitions())
                or self.spatial_indexer.minimum_partition_size != config["minimum_partition_size"]
                or self.spatial_indexer.fallback_partition != config["fallback_partition"]
                or any(len(self.spatial_indexer.partition_verified_rates[key]) != count
                       or len(self.spatial_indexer.partition_row_indices[key]) != count
                       for key, count in self.spatial_indexer.partition_counts.items())
                or set(self.spatial_indexer.partition_listing_ids) != set(self.spatial_indexer.partition_job_titles)
                or any(key not in self.spatial_indexer.partition_counts
                       or len(ids) != self.spatial_indexer.partition_counts[key]
                       or len(self.spatial_indexer.partition_job_titles[key]) != len(ids)
                       for key, ids in self.spatial_indexer.partition_listing_ids.items())
            ):
                raise ValueError("Incompatible inference KD-Tree artifact.")
            self.tariff_evaluator = MpesaTariffEvaluator.from_csv(self.tariff_csv_path)
            self.inference_config = config
            self.manifest = manifest
            self.load_error = None
        except Exception as exc:
            self.reducer = None
            self.metadata_normalizer = None
            self.spatial_indexer = None
            self.tariff_evaluator = None
            self.inference_config = None
            self.manifest = None
            # Do not expose absolute paths, pickle contents or exception payloads via health.
            if isinstance(exc, FileNotFoundError):
                name = os.path.basename(exc.filename or "")
                self.load_error = f"missing artifact file: {name}" if name in (*ARTIFACT_FILES, MANIFEST_NAME) else "missing artifact file"
            elif isinstance(exc, ValueError) and str(exc).startswith((
                "Untrusted artifacts:", "Untrusted artifact manifest:", "Incompatible artifact manifest",
                "Incompatible artifact model", "Missing or incompatible exploratory artifact provenance",
                "Incompatible artifact provenance fields", "Invalid or sensitive artifact provenance",
                "Invalid artifact dataset digest",
                "Incomplete artifact manifest", "Invalid artifact digest:", "Corrupted artifact:",
                "Incompatible artifact preprocessing policy", "Incompatible inference feature schema",
                "Invalid inference KNN configuration", "Invalid inference feature weights",
                "Missing partition density mapping", "Incompatible manifest query or partition policy",
                "Invalid partition policy", "Incompatible fitted text dimensions",
                "Incompatible inference KD-Tree artifact",
            )):
                self.load_error = str(exc)
            else:
                self.load_error = "invalid or corrupted artifact set"

    def _partition(self, selected_industry: str) -> str:
        normalized = selected_industry.strip().lower()
        return normalized if normalized in SUPPORTED_INDUSTRY_PARTITIONS else map_industry_partition(selected_industry)

    def predict(self, query: PricingQueryDTO) -> PredictionResultDTO:
        if not self.models_loaded:
            raise RuntimeError(self.load_error or "Inference artifacts are not loaded.")
        assert self.reducer is not None and self.metadata_normalizer is not None
        assert self.spatial_indexer is not None and self.tariff_evaluator is not None and self.inference_config is not None
        config = self.inference_config
        partition = self._partition(query.selected_industry)
        if partition not in config["partition_density"]:
            raise ValueError(f"No trained density for partition '{partition}'.")
        text_vector = ensure_text_dimensions(self.reducer.transform([query.raw_description]))
        raw_metadata = self.metadata_normalizer.build_live_metadata_vector(
            query.mentor_country, query.client_country, query.market_saturation_score, config["partition_density"][partition],
            mentor_cost_of_living_index=query.cost_of_living_index,
        )
        normalized_metadata = self.metadata_normalizer.transform_live_metadata(
            query.mentor_country, query.client_country, query.market_saturation_score, config["partition_density"][partition],
            mentor_cost_of_living_index=query.cost_of_living_index,
        )
        fused = fuse_coordinates(text_vector * config["text_weight"], normalized_metadata * config["metadata_weight"])
        prediction = self.spatial_indexer.predict_base_rate(
            fused, requested_partition=partition, k=config["k_neighbors"],
            allow_fallback=config["allow_fallback"], epsilon=config["idw_epsilon"]
        )
        bilateral_factor = float(raw_metadata[0, 0])
        corridor = synthesize_corridor(
            base_rate=float(prediction["base_predicted_rate"]),
            peer_stddev=float(prediction["peer_stddev"]),
            bilateral_factor=bilateral_factor,
            base_rate_floor=query.base_rate_floor,
        )
        quote = self.tariff_evaluator.evaluate_quote(float(prediction["base_predicted_rate"]), query.mentor_country)
        return PredictionResultDTO(
            base_predicted_rate=quote["base_predicted_rate"],
            mpesa_tariff_surcharge=quote["mpesa_tariff_surcharge"],
            final_quoted_rate=quote["final_quoted_rate"],
            **corridor,
            currency="KES",
            bilateral_arbitrage_factor=bilateral_factor,
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
    token_verifier: Optional[Callable[[str], Dict[str, Any]]] = None,
    readiness_probe: Optional[Callable[[], bool]] = None,
    trusted_manifest_sha256: Optional[str] = None,
) -> FastAPI:
    runtime = InferenceRuntime(artifact_dir, macro_lookup_path, tariff_csv_path, firestore_enabled,
                               trusted_manifest_sha256 or os.getenv("PRICING_ARTIFACT_MANIFEST_SHA256"))
    runtime_inference = inference is None
    resolved_inference: InferenceCallable = inference if inference is not None else runtime.predict
    resolved_metrics = metrics or MetricsRegistry()
    dependencies = ServiceDependencies(
        repository=repository or InMemoryRepository(),
        mlops=mlops or MLOpsService(),
        metrics=resolved_metrics,
        inference=resolved_inference,
        admin_token=admin_token if admin_token is not None else os.getenv("MLOPS_ADMIN_TOKEN"),
    )
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if runtime_inference:
            runtime.load()
        app.state.inference_runtime = runtime
        yield

    app = FastAPI(title="Price Optimization Model API", version="1.0.0", lifespan=lifespan)
    app.state.dependencies = dependencies
    # Career Mentor OS platform contract (#99). Closed unless PLATFORM_PRICE_KEY is set.
    register_platform_price(app, dependencies)

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
        try:
            database = runtime.database_status if runtime_inference and repository is None else dependencies.repository.health()
        except Exception:
            database = "unavailable"
        models_loaded = runtime.models_loaded if runtime_inference else dependencies.inference is not None
        healthy = models_loaded and database in {"firestore", "memory", "unconfigured"}
        if token_verifier is not None:
            healthy = healthy and database == "firestore"
        return HealthResponseDTO(
            status="HEALTHY" if healthy else "DEGRADED",
            models_loaded=models_loaded,
            database=database if database in {"firestore", "memory", "unconfigured"} else "unavailable",
            artifact_version=(f"v{runtime.manifest['schema_version']}:{runtime.trusted_manifest_sha256[:12]}"
                              if models_loaded and runtime_inference else None),
            dataset_version=runtime.manifest["provenance"]["dataset_version"] if models_loaded and runtime_inference else None,
            source_type=runtime.manifest["provenance"]["source_type"] if models_loaded and runtime_inference else None,
            validation_status=runtime.manifest["provenance"]["validation_status"] if models_loaded and runtime_inference else None,
            readiness_reason=runtime.load_error if runtime_inference and not models_loaded else None,
        )

    @app.get("/health", response_model=HealthStatusDTO)
    async def health() -> HealthStatusDTO:
        state = current_health()
        return HealthStatusDTO.model_validate({**state.model_dump(), "modelsLoaded": state.models_loaded})

    @app.get("/ready", response_model=HealthResponseDTO)
    async def ready() -> Any:
        health_state = current_health()
        if health_state.status == "HEALTHY" and readiness_probe is not None:
            try:
                if not readiness_probe():
                    raise RuntimeError("repository unavailable")
            except Exception:
                health_state = health_state.model_copy(update={"status": "DEGRADED", "database": "unavailable",
                                                        "readiness_reason": "repository unavailable"})
        if health_state.status != "HEALTHY":
            return JSONResponse(status_code=503, content=health_state.model_dump())
        return health_state

    def require_pricing_token(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
        if token_verifier is None:
            return None
        bearer = re.fullmatch(r"Bearer ([^\s]+)", authorization or "", flags=re.IGNORECASE)
        if bearer is None:
            raise HTTPException(status_code=401, detail="valid bearer token required")
        try:
            claims = token_verifier(bearer.group(1))
            uid = claims.get("uid") if isinstance(claims, dict) else None
            if not isinstance(uid, str) or not uid or uid != uid.strip():
                raise ValueError("missing verified UID")
        except Exception as exc:
            raise HTTPException(status_code=401, detail="valid bearer token required") from exc
        if current_health().database != "firestore":
            raise HTTPException(status_code=503, detail="pricing repository unavailable")
        return uid

    @app.post(
        "/api/v1/optimize-price", response_model=CanonicalPredictionResultDTO | PredictionResultDTO,
        description="CamelCase canonical request/response in KES/hour. The snake_case PricingQueryDTO/PredictionResultDTO "
                    "remains supported but is deprecated; do not mix naming styles. "
                    "rawText is required until verified profile hydration (#84) is available.",
    )
    async def optimize_price(query: CanonicalPricingQueryDTO | PricingQueryDTO, background_tasks: BackgroundTasks,
                             response: Response, uid: Optional[str] = Depends(require_pricing_token),
                             ) -> CanonicalPredictionResultDTO | PredictionResultDTO:
        canonical = isinstance(query, CanonicalPricingQueryDTO)
        if not canonical:
            response.headers["Deprecation"] = "true"
        # A body mentorId is never an authentication credential. The verified
        # Firebase UID must own the stored mentor, even when its IDs differ.
        if uid is not None:
            if query.mentor_id is None:
                raise HTTPException(status_code=403, detail="mentor authorization required")
            try:
                mentor = dependencies.repository.get_mentor(query.mentor_id, uid)
            except RepositoryError as exc:
                raise HTTPException(status_code=403, detail="mentor authorization required") from exc
            except Exception as exc:
                raise HTTPException(status_code=503, detail="pricing repository unavailable") from exc
            if mentor is None or mentor.get("account_status") != "active":
                raise HTTPException(status_code=403, detail="mentor authorization required")
            if query.mentor_country != mentor.get("country_code"):
                raise HTTPException(status_code=422, detail="mentorCountry must match verified mentor country")
        if runtime_inference and not runtime.models_loaded:
            raise HTTPException(status_code=503, detail=runtime.load_error or "model artifacts are not loaded")
        inference_query: PricingQueryDTO
        if isinstance(query, CanonicalPricingQueryDTO):
            try:
                inference_query = query.to_inference_query()
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        else:
            inference_query = cast(PricingQueryDTO, query)
        try:
            with resolved_metrics.timer("inference.optimize_price"):
                payload = dependencies.inference(cast(PricingQueryDTO, inference_query))
            prediction = PredictionResultDTO.model_validate(payload)
            if canonical:
                try:
                    result = CanonicalPredictionResultDTO.from_legacy(prediction)
                except ValueError as exc:
                    raise HTTPException(status_code=503, detail="canonical pricing result unavailable") from exc
            else:
                result = prediction
            executed_at = datetime.now(timezone.utc).isoformat()
            audit_payload = {
                "transaction_id": f"api-{uuid4().hex}",
                "schema_version": 1,
                "selected_industry": inference_query.selected_industry,
                "mentor_country_code": inference_query.mentor_country,
                "client_country_code": inference_query.client_country,
                "base_predicted_rate": prediction.base_predicted_rate,
                "mpesa_tariff_surcharge": prediction.mpesa_tariff_surcharge,
                "final_quoted_rate": prediction.final_quoted_rate,
                "executed_at": executed_at,
            }
            if uid is not None:
                audit_payload["mentor_id"] = query.mentor_id
                audit_payload["auth_uid"] = uid
            background_tasks.add_task(_append_pricing_audit, dependencies.repository, resolved_metrics, audit_payload)
            return result
        except FloorExceedsCeilingError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail="inference failed") from exc

    @app.get("/api/v1/admin/metrics", response_model=MetricsResponseDTO)
    async def admin_metrics(_: ServiceDependencies = Depends(require_admin)) -> MetricsResponseDTO:
        return MetricsResponseDTO(metrics=resolved_metrics.snapshot(), tuning=GridSearchConfigDTO.model_validate(dependencies.mlops.get_tuning().to_dict()))

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
