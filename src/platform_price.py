"""Career Mentor OS platform contract: ``POST /price``.

The platform calls every student service through a fixed adapter. For U-CS 6
it sends ``{"mentorId": "..."}`` with no Authorization header and expects
``{"min", "max", "comparables", "reason"}``. This module serves that shape on
top of the existing inference callable without touching
``/api/v1/optimize-price`` or its Firebase protection.

Closed by default. The route only answers when ``PLATFORM_PRICE_KEY`` is set
in the environment and the request carries a matching ``X-Platform-Key``
header; otherwise it returns 503 and says why. That keeps a deployed gateway's
security posture exactly as it was until an operator opts in.

Pricing inputs may be supplied inline or resolved from a stored profile whose
``profile_id`` equals ``mentorId`` (``country_code`` and
``metadata.raw_description`` / ``metadata.selected_industry``). Anything still
missing is a 422 that names the fields, never a guess.
"""

from __future__ import annotations

import hmac
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.api_contracts import PredictionResultDTO, PricingQueryDTO

PLATFORM_KEY_ENV = "PLATFORM_PRICE_KEY"
PLATFORM_KEY_HEADER = "X-Platform-Key"
DEFAULT_CLIENT_COUNTRY = "KE"


class PlatformPriceRequest(BaseModel):
    """What the platform sends, plus optional inline overrides."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mentor_id: str = Field(alias="mentorId", min_length=1, max_length=200)
    raw_description: Optional[str] = Field(default=None, min_length=3, max_length=10_000)
    selected_industry: Optional[str] = Field(default=None, min_length=1, max_length=100)
    mentor_country: Optional[str] = Field(default=None, min_length=2, max_length=2)
    client_country: Optional[str] = Field(default=None, min_length=2, max_length=2)


class PlatformComparable(BaseModel):
    peer_index: int
    rate: float
    similarity: float


class PlatformPriceResponse(BaseModel):
    """Exactly the four keys the platform adapter reads."""

    min: float = Field(ge=0.0)
    max: float = Field(ge=0.0)
    comparables: List[PlatformComparable]
    reason: str


def _platform_key() -> Optional[str]:
    value = os.getenv(PLATFORM_KEY_ENV, "").strip()
    return value or None


def _require_platform_key(provided: Optional[str]) -> None:
    expected = _platform_key()
    if expected is None:
        raise HTTPException(
            status_code=503,
            detail=f"platform pricing route is disabled; set {PLATFORM_KEY_ENV} to enable it",
        )
    if not provided or not hmac.compare_digest(provided.strip(), expected):
        raise HTTPException(status_code=401, detail=f"valid {PLATFORM_KEY_HEADER} header required")


def _profile_for(repository: Any, mentor_id: str) -> Dict[str, Any]:
    try:
        for profile in repository.list_profiles():
            if str(profile.get("profile_id", "")) == mentor_id:
                return profile
    except Exception:  # repository failures must not masquerade as "no profile"
        raise HTTPException(status_code=503, detail="pricing repository unavailable")
    return {}


def _resolve_query(request: PlatformPriceRequest, repository: Any) -> PricingQueryDTO:
    profile = _profile_for(repository, request.mentor_id)
    metadata = profile.get("metadata") or {}

    resolved = {
        "raw_description": request.raw_description or metadata.get("raw_description"),
        "selected_industry": request.selected_industry or metadata.get("selected_industry"),
        "mentor_country": request.mentor_country or profile.get("country_code"),
        "client_country": request.client_country
        or metadata.get("client_country")
        or DEFAULT_CLIENT_COUNTRY,
    }
    missing = sorted(key for key, value in resolved.items() if not value)
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "cannot price this mentor: inputs missing and no stored profile supplies them",
                "mentorId": request.mentor_id,
                "missing": missing,
                "hint": "pass them inline, or store a profile with country_code and metadata.raw_description / metadata.selected_industry",
            },
        )
    return PricingQueryDTO.model_validate(resolved)


def to_platform_response(prediction: PredictionResultDTO) -> PlatformPriceResponse:
    """Map the engine's result onto the platform's four keys.

    ``min``/``max`` are the spread of the retrieved peers' verified rates,
    bounded so the final quote always sits inside them. Peers are the
    comparables. The reason is a plain sentence a client-facing screen can show.
    """

    rates = [peer.verified_rate for peer in prediction.nearest_neighbors]
    quote = prediction.final_quoted_rate
    low = min(rates + [quote]) if rates else quote
    high = max(rates + [quote]) if rates else quote

    comparables = [
        PlatformComparable(peer_index=peer.peer_index, rate=peer.verified_rate, similarity=peer.similarity_score)
        for peer in prediction.nearest_neighbors
    ]
    surcharge = (
        f" including a {prediction.mpesa_tariff_surcharge:.2f} {prediction.currency} M-Pesa surcharge"
        if prediction.mpesa_tariff_surcharge > 0
        else ""
    )
    reason = (
        f"Weighted from {len(comparables)} comparable {'peer' if len(comparables) == 1 else 'peers'} "
        f"to {quote:.2f} {prediction.currency}{surcharge}."
    )
    return PlatformPriceResponse(min=round(low, 2), max=round(high, 2), comparables=comparables, reason=reason)


def register_platform_price(app: FastAPI, dependencies: Any) -> None:
    """Mount ``POST /price`` on an app built by ``create_app``."""

    @app.post("/price", response_model=PlatformPriceResponse, tags=["platform"])
    async def platform_price(
        request: PlatformPriceRequest,
        x_platform_key: Optional[str] = Header(default=None, alias=PLATFORM_KEY_HEADER),
    ) -> PlatformPriceResponse:
        _require_platform_key(x_platform_key)
        query = _resolve_query(request, dependencies.repository)
        try:
            payload = dependencies.inference(query)
            prediction = PredictionResultDTO.model_validate(payload)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail="inference failed") from exc
        return to_platform_response(prediction)
