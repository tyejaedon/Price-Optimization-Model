"""Pydantic v2 contracts for pricing and administrator MLOps operations."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PricingQueryDTO(StrictModel):
    # Kept for existing Python and snake_case HTTP callers; see CanonicalPricingQueryDTO.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, populate_by_name=True,
                              json_schema_extra={"deprecated": True})

    # The deployed gateway requires this to equal the verified Firebase UID.
    # Keep it optional here for existing local callers until the #83 wire migration.
    mentor_id: Optional[str] = Field(default=None, alias="mentorId", min_length=1, max_length=128)
    raw_description: str = Field(min_length=3, max_length=10_000)
    selected_industry: str = Field(min_length=1, max_length=100)
    mentor_country: str = Field(min_length=2, max_length=2)
    client_country: str = Field(min_length=2, max_length=2)
    competitiveness_score: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="Legacy compatibility input; not part of the fitted 53D feature schema.",
    )
    market_saturation_score: float = Field(default=0.5, ge=0.0, le=1.0)
    base_rate_floor: Optional[float] = Field(default=None, ge=0.0, allow_inf_nan=False)
    cost_of_living_index: Optional[float] = Field(default=None, ge=0.01, le=1000.0, allow_inf_nan=False)

    @field_validator("mentor_country", "client_country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("country codes must contain letters only")
        return normalized


class PeerMatchDTO(StrictModel):
    peer_index: int = Field(ge=0)
    distance: float = Field(ge=0.0)
    verified_rate: float = Field(ge=0.0)
    similarity_score: float = Field(gt=0.0, le=1.0)
    idw_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # Only populated by an inference artifact with real listing provenance (#71).
    listing_id: Optional[str] = Field(default=None, min_length=1, max_length=200)
    job_title: Optional[str] = Field(default=None, min_length=1, max_length=200)


class PredictionResultDTO(StrictModel):
    base_predicted_rate: float = Field(ge=0.0)
    mpesa_tariff_surcharge: float = Field(ge=0.0)
    final_quoted_rate: float = Field(ge=0.0)
    min_quoted_rate: Optional[float] = Field(default=None, ge=0.0, allow_inf_nan=False)
    max_quoted_rate: Optional[float] = Field(default=None, ge=0.0, allow_inf_nan=False)
    currency: str = "KES"
    bilateral_arbitrage_factor: Optional[float] = None
    mentor_country_iso2: str = "ZZ"
    nearest_neighbors: List[PeerMatchDTO] = Field(default_factory=list)

    @field_validator("final_quoted_rate")
    @classmethod
    def quote_covers_costs(cls, value: float, info: Any) -> float:
        base = info.data.get("base_predicted_rate")
        surcharge = info.data.get("mpesa_tariff_surcharge")
        if base is not None and surcharge is not None and abs(value - base - surcharge) > 0.011:
            raise ValueError("final_quoted_rate must equal base rate plus surcharge exactly once")
        return value

    @model_validator(mode="after")
    def valid_corridor(self) -> "PredictionResultDTO":
        if (self.min_quoted_rate is None) != (self.max_quoted_rate is None):
            raise ValueError("pricing corridor must provide both min_quoted_rate and max_quoted_rate")
        if self.min_quoted_rate is not None and self.min_quoted_rate > self.max_quoted_rate:
            raise ValueError("min_quoted_rate cannot exceed max_quoted_rate")
        return self


class HealthResponseDTO(StrictModel):
    status: Literal["HEALTHY", "DEGRADED", "UNHEALTHY"]
    models_loaded: bool
    database: Literal["firestore", "memory", "unconfigured", "unavailable"]
    artifact_version: Optional[str] = None
    dataset_version: Optional[str] = None
    source_type: Optional[str] = None
    validation_status: Optional[str] = None
    readiness_reason: Optional[str] = None


class CanonicalPricingQueryDTO(StrictModel):
    """M10.5 wire request; only camelCase keys are accepted, never mixed contracts."""

    mentor_id: str = Field(alias="mentorId", min_length=1, max_length=128)
    raw_text: Optional[str] = Field(default=None, alias="rawText", min_length=20, max_length=2000,
                                    description="Required until authorized profile hydration ships in #84.")
    industry: str = Field(min_length=1, max_length=100)
    mentor_country: str = Field(alias="mentorCountry", min_length=2, max_length=2)
    client_country: str = Field(alias="clientCountry", min_length=2, max_length=2)
    competitiveness_score: float = Field(default=0.5, alias="competitivenessScore", ge=0.0, le=1.0,
                                         allow_inf_nan=False, description="Fitted market saturation feature.")
    cost_of_living_index: Optional[float] = Field(default=None, alias="costOfLivingIndex", ge=0.01, le=1000.0,
                                                  allow_inf_nan=False, description="Mentor CoL override for bilateral factor only.")
    base_rate_floor: Optional[float] = Field(default=None, alias="baseRateFloor", ge=0.0,
                                             allow_inf_nan=False, description="Reservation floor in KES/hour.")

    @field_validator("mentor_country", "client_country")
    @classmethod
    def normalize_iso2(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z]{2}", value) is None:
            raise ValueError("country codes must be two ASCII letters")
        return value.upper()

    def to_inference_query(self) -> PricingQueryDTO:
        if self.raw_text is None:
            raise ValueError("rawText is required until verified mentor profile hydration is available")
        return PricingQueryDTO(
            mentor_id=self.mentor_id, raw_description=self.raw_text, selected_industry=self.industry,
            mentor_country=self.mentor_country, client_country=self.client_country,
            market_saturation_score=self.competitiveness_score, base_rate_floor=self.base_rate_floor,
            cost_of_living_index=self.cost_of_living_index,
        )


class CanonicalPeerMatchDTO(StrictModel):
    listing_id: str = Field(alias="listingId", min_length=1, max_length=200)
    job_title: Optional[str] = Field(default=None, alias="jobTitle", min_length=1, max_length=200)
    verified_rate: float = Field(alias="verifiedRate", ge=0.0, allow_inf_nan=False)
    similarity_score: float = Field(alias="similarityScore", ge=0.0, le=1.0, allow_inf_nan=False)
    euclidean_distance: float = Field(alias="euclideanDistance", ge=0.0, allow_inf_nan=False)


class CanonicalPredictionResultDTO(StrictModel):
    base_predicted_rate: float = Field(alias="basePredictedRate", ge=0.0, allow_inf_nan=False)
    mpesa_tariff_surcharge: float = Field(alias="mpesaTariffSurcharge", ge=0.0, allow_inf_nan=False)
    final_quoted_rate: float = Field(alias="finalQuotedRate", ge=0.0, allow_inf_nan=False)
    min_quoted_rate: float = Field(alias="minQuotedRate", ge=0.0, allow_inf_nan=False)
    max_quoted_rate: float = Field(alias="maxQuotedRate", ge=0.0, allow_inf_nan=False)
    k_neighbors_used: int = Field(alias="kNeighborsUsed", ge=1)
    bilateral_arbitrage_factor: float = Field(alias="bilateralArbitrageFactor", gt=0.0, allow_inf_nan=False)
    confidence_score: float = Field(alias="confidenceScore", ge=0.0, le=1.0, allow_inf_nan=False,
                                    description="0.0: not empirically calibrated; not a probability of quote accuracy.")
    comparables: List[CanonicalPeerMatchDTO]
    reason: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def valid_quote(self) -> "CanonicalPredictionResultDTO":
        if abs(self.final_quoted_rate - self.base_predicted_rate - self.mpesa_tariff_surcharge) > 0.011:
            raise ValueError("finalQuotedRate must equal basePredictedRate plus mpesaTariffSurcharge")
        if self.min_quoted_rate > self.max_quoted_rate:
            raise ValueError("minQuotedRate cannot exceed maxQuotedRate")
        if len(self.comparables) > self.k_neighbors_used:
            raise ValueError("comparables cannot exceed kNeighborsUsed")
        return self

    @classmethod
    def from_legacy(cls, prediction: PredictionResultDTO) -> "CanonicalPredictionResultDTO":
        if prediction.min_quoted_rate is None or prediction.max_quoted_rate is None or prediction.bilateral_arbitrage_factor is None:
            raise ValueError("canonical pricing requires a computed corridor and bilateral factor")
        comparables = [
            CanonicalPeerMatchDTO(
                listingId=peer.listing_id, jobTitle=peer.job_title, verifiedRate=peer.verified_rate,
                similarityScore=peer.similarity_score, euclideanDistance=peer.distance,
            )
            for peer in prediction.nearest_neighbors if peer.listing_id is not None
        ]
        count = len(prediction.nearest_neighbors)
        if count == 0:
            raise ValueError("canonical pricing requires peer-backed inference")
        reason = f"Weighted from {count} indexed peers in KES/hour; corridor excludes the M-Pesa surcharge."
        if prediction.mentor_country_iso2 == "KE":
            reason += f" Kenyan M-Pesa fee of {prediction.mpesa_tariff_surcharge:.2f} KES/hour is added once to the base rate."
        elif prediction.mpesa_tariff_surcharge == 0:
            reason += " No Kenyan M-Pesa fee applies."
        if len(comparables) < count:
            reason += " Listing-backed comparables are unavailable for some peers."
        return cls(
            basePredictedRate=prediction.base_predicted_rate,
            mpesaTariffSurcharge=prediction.mpesa_tariff_surcharge,
            finalQuotedRate=prediction.final_quoted_rate,
            minQuotedRate=prediction.min_quoted_rate, maxQuotedRate=prediction.max_quoted_rate,
            kNeighborsUsed=count, bilateralArbitrageFactor=prediction.bilateral_arbitrage_factor,
            confidenceScore=0.0, comparables=comparables, reason=reason,
        )


class HealthStatusDTO(HealthResponseDTO):
    """Add canonical health keys without removing fields consumed by legacy clients."""

    service: Literal["pricing-engine"] = "pricing-engine"
    unit: Literal["KES/hour"] = "KES/hour"
    modelsLoaded: bool
    version: str = "1.0.0"


class GridSearchConfigDTO(StrictModel):
    k_neighbors: List[int] = Field(default_factory=lambda: [1, 3, 5, 7, 10], min_length=1, max_length=20)
    text_weight: float = Field(default=1.0, ge=0.0, le=4.0)
    metadata_weight: float = Field(default=1.0, ge=0.0, le=4.0)
    idw_epsilon: float = Field(default=1e-9, gt=0.0, le=1.0)
    minimum_partition_size: int = Field(default=1, ge=1, le=10_000)
    allow_fallback: bool = True

    @field_validator("k_neighbors")
    @classmethod
    def validate_neighbors(cls, values: List[int]) -> List[int]:
        if any(value < 1 or value > 500 for value in values):
            raise ValueError("k_neighbors values must be between 1 and 500")
        if len(set(values)) != len(values):
            raise ValueError("k_neighbors values must be unique")
        return sorted(values)


class ProfileDTO(StrictModel):
    profile_id: str = Field(min_length=1, max_length=200)
    auth_uid: Optional[str] = Field(default=None, min_length=1, max_length=128,
                                    description="Firebase Auth UID authorized to price this mentor.")
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    country_code: str = Field(min_length=2, max_length=2)
    account_status: str = Field(default="active", max_length=50)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("country_code")
    @classmethod
    def normalize_profile_country(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z]{2}", value) is None:
            raise ValueError("country_code must be two ASCII letters")
        return value.upper()


class ServiceListingDTO(StrictModel):
    """Root /service_listings/{listing_id}; vectors use the published 50D reducer."""

    listing_id: str = Field(min_length=1, max_length=200)
    mentor_id: str = Field(min_length=1, max_length=200)
    industry_id: str
    title: str = Field(min_length=1, max_length=200)
    raw_description: str = Field(min_length=20, max_length=2000)
    latent_svd_vector: List[float] = Field(min_length=50, max_length=50)
    verified_rate: float = Field(gt=0.0, allow_inf_nan=False,
                                 description="Verified peer rate in KES/hour; never infer from a proxy budget.")
    is_active: bool = True

    @field_validator("industry_id")
    @classmethod
    def valid_industry(cls, value: str) -> str:
        from src.ingest_multisource import SUPPORTED_INDUSTRY_PARTITIONS

        if value not in SUPPORTED_INDUSTRY_PARTITIONS:
            raise ValueError("industry_id must be a supported partition")
        return value

    @field_validator("latent_svd_vector", mode="before")
    @classmethod
    def native_float_vector(cls, value: Any) -> Any:
        if (not isinstance(value, list) or len(value) != 50
                or any(type(component) is not float or not math.isfinite(component) for component in value)):
            raise ValueError("latent_svd_vector must be a native array of 50 finite floats")
        return value


class HistoricalTransactionDTO(StrictModel):
    transaction_id: str = Field(min_length=1, max_length=200)
    listing_id: Optional[str] = None
    client_country_code: str = Field(min_length=2, max_length=2)
    base_predicted_rate: float = Field(ge=0.0)
    mpesa_tariff_surcharge: float = Field(ge=0.0)
    final_quoted_rate: float = Field(ge=0.0)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RetrainResponseDTO(StrictModel):
    job_id: str
    status: Literal["accepted", "running", "succeeded", "failed", "busy"]
    artifact_version: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class MetricsResponseDTO(StrictModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: Dict[str, Any] = Field(default_factory=dict)
    tuning: GridSearchConfigDTO
