import os
from contextlib import asynccontextmanager
from typing import Literal, Optional, cast

try:
    from fastapi import FastAPI, HTTPException
except ImportError as exc:
    raise RuntimeError("Install API dependencies from requirements.txt") from exc

from src.api_contracts import HealthResponseDTO, PredictionResultDTO, PricingQueryDTO
from src.ingest_multisource import SUPPORTED_INDUSTRY_PARTITIONS, map_industry_partition
from src.macro_arbitrage import (
    DEFAULT_MACRO_LOOKUP,
    ContinuousMetadataNormalizer,
    fuse_coordinates,
)
from src.nlp_pipeline import TextFeatureReducer
from src.spatial_engine import DEFAULT_QUERY_NEIGHBORS, DomainPartitionedKDTreeIndexer
from src.tariff_evaluator import DEFAULT_MPESA_TARIFF_CSV, MpesaTariffEvaluator

DEFAULT_ARTIFACT_DIR = "artifacts"
DEFAULT_FIRESTORE_ENABLED = False


class InferenceRuntime:
    """Owns serialized inference artifacts and runtime readiness state."""

    def __init__(
        self,
        artifact_dir: str = DEFAULT_ARTIFACT_DIR,
        macro_lookup_path: str = DEFAULT_MACRO_LOOKUP,
        tariff_csv_path: str = DEFAULT_MPESA_TARIFF_CSV,
        firestore_enabled: bool = DEFAULT_FIRESTORE_ENABLED,
    ) -> None:
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
        return all(
            component is not None
            for component in (self.reducer, self.metadata_normalizer, self.spatial_indexer, self.tariff_evaluator)
        )

    @property
    def database_status(self) -> Literal["firestore", "unconfigured", "unavailable"]:
        if not self.firestore_enabled:
            return "unconfigured"
        try:
            import firebase_admin  # type: ignore  # noqa: F401
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

    def industry_partition(self, selected_industry: str) -> str:
        normalized = selected_industry.strip().lower()
        if normalized in SUPPORTED_INDUSTRY_PARTITIONS:
            return normalized
        return map_industry_partition(selected_industry)

    def predict(self, query: PricingQueryDTO) -> PredictionResultDTO:
        if not self.models_loaded:
            raise RuntimeError(self.load_error or "Inference artifacts are not loaded.")
        assert self.reducer is not None
        assert self.metadata_normalizer is not None
        assert self.spatial_indexer is not None
        assert self.tariff_evaluator is not None

        text_vector = self.reducer.transform([query.raw_description])
        raw_metadata = self.metadata_normalizer.build_live_metadata_vector(
            mentor_country_iso2=query.mentor_country,
            client_country_iso2=query.client_country,
            market_saturation_score=query.market_saturation_score,
            industry_relative_density=query.competitiveness_score,
        )
        normalized_metadata = self.metadata_normalizer.transform_live_metadata(
            mentor_country_iso2=query.mentor_country,
            client_country_iso2=query.client_country,
            market_saturation_score=query.market_saturation_score,
            industry_relative_density=query.competitiveness_score,
        )
        fused = fuse_coordinates(text_vector, normalized_metadata)
        partition = self.industry_partition(query.selected_industry)
        prediction = self.spatial_indexer.predict_base_rate(
            query_vector=fused,
            requested_partition=partition,
            k=DEFAULT_QUERY_NEIGHBORS,
            allow_fallback=True,
        )
        quote = self.tariff_evaluator.evaluate_quote(
            base_predicted_rate=float(prediction["base_predicted_rate"]),
            mentor_country=query.mentor_country,
        )
        return PredictionResultDTO(
            base_predicted_rate=quote["base_predicted_rate"],
            mpesa_tariff_surcharge=quote["mpesa_tariff_surcharge"],
            final_quoted_rate=quote["final_quoted_rate"],
            currency="KES",
            bilateral_arbitrage_factor=float(raw_metadata[0, 0]),
            nearest_neighbors=prediction["nearest_neighbors"],
        )


def create_app(
    artifact_dir: str = DEFAULT_ARTIFACT_DIR,
    macro_lookup_path: str = DEFAULT_MACRO_LOOKUP,
    tariff_csv_path: str = DEFAULT_MPESA_TARIFF_CSV,
    firestore_enabled: bool = DEFAULT_FIRESTORE_ENABLED,
) -> FastAPI:
    runtime = InferenceRuntime(
        artifact_dir=artifact_dir,
        macro_lookup_path=macro_lookup_path,
        tariff_csv_path=tariff_csv_path,
        firestore_enabled=firestore_enabled,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime.load()
        app.state.inference_runtime = runtime
        yield

    app = FastAPI(
        title="Dynamic Price Optimizer API",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthResponseDTO)
    def health() -> HealthResponseDTO:
        status: Literal["HEALTHY", "DEGRADED", "UNHEALTHY"]
        if runtime.models_loaded:
            status = "HEALTHY"
        elif runtime.load_error:
            status = "DEGRADED"
        else:
            status = "UNHEALTHY"
        return HealthResponseDTO(
            status=cast(Literal["HEALTHY", "DEGRADED", "UNHEALTHY"], status),
            models_loaded=runtime.models_loaded,
            database=cast(Literal["firestore", "unconfigured", "unavailable"], runtime.database_status),
        )

    @app.post("/api/v1/optimize-price", response_model=PredictionResultDTO)
    def optimize_price(query: PricingQueryDTO) -> PredictionResultDTO:
        if not runtime.models_loaded:
            raise HTTPException(status_code=503, detail="Inference models are not ready.")
        try:
            return runtime.predict(query)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Inference failed.") from exc

    return app


app = create_app(
    artifact_dir=os.getenv("MODEL_ARTIFACT_DIR", DEFAULT_ARTIFACT_DIR),
    macro_lookup_path=os.getenv("MACRO_LOOKUP_PATH", DEFAULT_MACRO_LOOKUP),
    tariff_csv_path=os.getenv("MPESA_TARIFF_CSV", DEFAULT_MPESA_TARIFF_CSV),
    firestore_enabled=os.getenv("FIRESTORE_ENABLED", "false").strip().lower() == "true",
)

