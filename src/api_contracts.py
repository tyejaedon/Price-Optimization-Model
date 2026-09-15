"""Pydantic v2 contracts for pricing and administrator MLOps operations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PricingQueryDTO(StrictModel):
    raw_description: str = Field(min_length=3, max_length=10_000)
    selected_industry: str = Field(min_length=1, max_length=100)
    mentor_country: str = Field(min_length=2, max_length=2)
    client_country: str = Field(min_length=2, max_length=2)
    competitiveness_score: float = Field(default=0.5, ge=0.0, le=1.0)
    market_saturation_score: float = Field(default=0.5, ge=0.0, le=1.0)

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


class PredictionResultDTO(StrictModel):
    base_predicted_rate: float = Field(ge=0.0)
    mpesa_tariff_surcharge: float = Field(ge=0.0)
    final_quoted_rate: float = Field(ge=0.0)
    currency: str = "KES"
    bilateral_arbitrage_factor: Optional[float] = None
    mentor_country_iso2: str = "ZZ"
    nearest_neighbors: List[PeerMatchDTO] = Field(default_factory=list)

    @field_validator("final_quoted_rate")
    @classmethod
    def quote_covers_costs(cls, value: float, info: Any) -> float:
        base = info.data.get("base_predicted_rate")
        surcharge = info.data.get("mpesa_tariff_surcharge")
        if base is not None and surcharge is not None and value + 1e-9 < base + surcharge:
            raise ValueError("final_quoted_rate must cover base rate plus surcharge")
        return value


class HealthResponseDTO(StrictModel):
    status: Literal["HEALTHY", "DEGRADED", "UNHEALTHY"]
    models_loaded: bool
    database: Literal["firestore", "memory", "unconfigured", "unavailable"]


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
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    country_code: str = Field(min_length=2, max_length=2)
    account_status: str = Field(default="active", max_length=50)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("country_code")
    @classmethod
    def normalize_profile_country(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("country_code must contain letters only")
        return normalized


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

