from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ISO2CountryCode = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
IndustryCode = Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]


class ContractBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class PricingQueryDTO(ContractBaseModel):
    """Validated request body for POST /api/v1/optimize-price."""

    raw_description: Annotated[str, Field(min_length=20, max_length=10000)]
    selected_industry: IndustryCode
    mentor_country: ISO2CountryCode
    client_country: ISO2CountryCode
    competitiveness_score: Annotated[float, Field(ge=0.0, le=1.0)]
    market_saturation_score: Annotated[float, Field(ge=0.0, le=1.0)]

    @field_validator("mentor_country", "client_country", mode="before")
    @classmethod
    def normalize_country_code(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class PeerMatchDTO(ContractBaseModel):
    """Explainable peer match returned by the KNN/IDW pricing engine."""

    peer_index: Annotated[int, Field(ge=0)]
    distance: Annotated[float, Field(ge=0.0)]
    verified_rate: Annotated[float, Field(ge=0.0)]
    similarity_score: Annotated[float, Field(gt=0.0, le=1.0)]
    idw_weight: Annotated[float, Field(ge=0.0, le=1.0)] | None = None


class PredictionResultDTO(ContractBaseModel):
    """Validated response body for POST /api/v1/optimize-price."""

    base_predicted_rate: Annotated[float, Field(ge=0.0)]
    mpesa_tariff_surcharge: Annotated[float, Field(ge=0.0)]
    final_quoted_rate: Annotated[float, Field(ge=0.0)]
    currency: Literal["KES"]
    bilateral_arbitrage_factor: Annotated[float, Field(ge=0.0)]
    nearest_neighbors: Annotated[list[PeerMatchDTO], Field(min_length=1, max_length=50)]

    @field_validator("final_quoted_rate")
    @classmethod
    def final_rate_covers_components(cls, value: float, info):
        base_rate = info.data.get("base_predicted_rate")
        surcharge = info.data.get("mpesa_tariff_surcharge")
        if base_rate is not None and surcharge is not None and value + 1e-6 < base_rate + surcharge:
            raise ValueError("final_quoted_rate must be at least base_predicted_rate plus surcharge")
        return value


class HealthResponseDTO(ContractBaseModel):
    """Response body for GET /health."""

    status: Literal["HEALTHY", "DEGRADED", "UNHEALTHY"]
    models_loaded: bool
    database: Literal["firestore", "unconfigured", "unavailable"] = "unconfigured"

