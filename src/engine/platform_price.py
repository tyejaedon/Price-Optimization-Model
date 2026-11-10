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

from src.api.api_contracts import PredictionResultDTO, PricingQueryDTO
from src.data.ingest_platform import PLATFORM_CATEGORY_PARTITIONS

PLATFORM_KEY_ENV = "PLATFORM_PRICE_KEY"
PLATFORM_KEY_HEADER = "X-Platform-Key"
PLATFORM_OUT_OF_SCOPE_AS_ERROR_ENV = "PLATFORM_OUT_OF_SCOPE_AS_ERROR"
PLATFORM_ERROR_OUT_OF_SCOPE_HEADER = "X-Platform-Error-On-Out-Of-Scope"
DEFAULT_CLIENT_COUNTRY = "KE"

# Canonical normalized dictionary of vocational and out-of-scope categories
# derived from Career Mentor OS platform corpus partitions and supervisor directive.
OUT_OF_SCOPE_CATEGORIES: Dict[str, str] = {
    "agriculture & farming": "Agriculture & Farming",
    "automotive & mechanics": "Automotive & Mechanics",
    "beauty & cosmetology": "Beauty & Cosmetology",
    "construction & building": "Construction & Building",
    "culinary & hospitality": "Culinary & Hospitality",
    "education & academia": "Education & Academia",
    "electrical & electronics": "Electrical & Electronics",
    "events & entertainment": "Events & Entertainment",
    "fashion & textiles": "Fashion & Textiles",
    "finance & accounting": "Finance & Accounting",
    "healthcare & medical": "Healthcare & Medical",
    "installation, maintenance & repair": "Installation, Maintenance & Repair",
    "legal & compliance": "Legal & Compliance",
    "manufacturing & production": "Manufacturing & Production",
    "mining & natural resources": "Mining & Natural Resources",
    "personal development": "Personal Development",
    "public service & non-profit": "Public Service & Non-Profit",
    "real estate & property": "Real Estate & Property",
    "retail & consumer goods": "Retail & Consumer Goods",
    "security & protective services": "Security & Protective Services",
    "sports, fitness & recreation": "Sports, Fitness & Recreation",
    "transport & logistics": "Transport & Logistics",
    "travel & tourism": "Travel & Tourism",
}


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
        if hasattr(repository, "get_profile"):
            direct = repository.get_profile(mentor_id)
            if direct:
                return direct
        for profile in repository.list_profiles():
            pid = str(profile.get("profile_id", ""))
            metadata = profile.get("metadata") or {}
            user_id = str(metadata.get("platform_mentor_user_id", ""))
            if pid == mentor_id or (user_id and user_id == mentor_id):
                return profile
    except Exception:  # repository failures must not masquerade as "no profile"
        raise HTTPException(status_code=503, detail="pricing repository unavailable")
    return {}


def detect_out_of_scope(request: PlatformPriceRequest, profile: Dict[str, Any]) -> Optional[str]:
    """Inspect mentor inputs and profile attributes to detect vocational/out-of-scope disciplines.

    Returns the canonical category name if out-of-scope, or None if in-scope.
    """
    metadata = profile.get("metadata") or {}
    candidates = [
        request.selected_industry,
        metadata.get("platform_category"),
        metadata.get("selected_industry"),
        profile.get("category"),
        profile.get("selected_industry"),
        metadata.get("platform_specialization"),
    ]
    for candidate in candidates:
        if not candidate or not isinstance(candidate, str):
            continue
        cleaned = candidate.strip()
        norm = cleaned.lower()
        if norm in OUT_OF_SCOPE_CATEGORIES:
            return OUT_OF_SCOPE_CATEGORIES[norm]
        for cat, partition in PLATFORM_CATEGORY_PARTITIONS.items():
            if partition is None and norm == cat.strip().lower():
                return cat

    mentor_type = str(
        metadata.get("platform_mentor_type")
        or profile.get("mentor_type")
        or ""
    ).strip().upper()
    if mentor_type == "VOCATIONAL":
        category_name = (
            metadata.get("platform_category")
            or metadata.get("platform_specialization")
            or profile.get("category")
            or "Vocational Mentorship"
        )
        return str(category_name)

    return None


def build_outside_scope_response(category: str) -> PlatformPriceResponse:
    """Build structured deterministic 200 response with zero bounds and domain boundary reason."""
    category_display = category or "Vocational / Non-Technical"
    reason = (
        f"Mentorship category '{category_display}' is outside technical pricing scope. "
        "Recommendations are available for software, data, product, and digital specializations only."
    )
    return PlatformPriceResponse(
        min=0.0,
        max=0.0,
        comparables=[],
        reason=reason,
    )


def _resolve_query(
    request: PlatformPriceRequest, repository: Any, profile: Optional[Dict[str, Any]] = None
) -> PricingQueryDTO:
    if profile is None:
        profile = _profile_for(repository, request.mentor_id)
    metadata = profile.get("metadata") or {}

    resolved = {
        "mentor_id": request.mentor_id,
        "raw_description": request.raw_description or metadata.get("raw_description"),
        "selected_industry": request.selected_industry or metadata.get("selected_industry"),
        "mentor_country": request.mentor_country or profile.get("country_code"),
        "client_country": request.client_country
        or metadata.get("client_country")
        or DEFAULT_CLIENT_COUNTRY,
    }
    missing = sorted(key for key, value in resolved.items() if not value and key != "mentor_id")
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
        x_platform_error_out_of_scope: Optional[str] = Header(
            default=None, alias=PLATFORM_ERROR_OUT_OF_SCOPE_HEADER
        ),
    ) -> PlatformPriceResponse:
        _require_platform_key(x_platform_key)
        profile = _profile_for(dependencies.repository, request.mentor_id)

        # Short-circuit vocational/out-of-scope mentors before invoking inference
        out_of_scope_category = detect_out_of_scope(request, profile)
        if out_of_scope_category:
            should_error = (
                (
                    x_platform_error_out_of_scope is not None
                    and x_platform_error_out_of_scope.strip().lower() in {"true", "1", "yes"}
                )
                or os.getenv(PLATFORM_OUT_OF_SCOPE_AS_ERROR_ENV, "").strip().lower()
                in {"true", "1", "yes"}
            )
            if should_error:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "OUT_OF_SCOPE_CATEGORY",
                        "category": out_of_scope_category,
                        "message": "Category is outside technical mentorship pricing scope.",
                    },
                )
            return build_outside_scope_response(out_of_scope_category)

        query = _resolve_query(request, dependencies.repository, profile=profile)
        try:
            payload = dependencies.inference(query)
            prediction = PredictionResultDTO.model_validate(payload)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail="inference failed") from exc
        return to_platform_response(prediction)
