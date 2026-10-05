"""FR-06 peer-based negotiation bounds in KES/hour (before any payment fee)."""

from __future__ import annotations

import math
from typing import Sequence


class FloorExceedsCeilingError(ValueError):
    """A requested rate floor cannot be accommodated by the peer-based ceiling."""


def _non_negative_finite(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite and non-negative")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite and non-negative") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return number


def weighted_peer_stddev(peer_rates: Sequence[float], idw_weights: Sequence[float]) -> float:
    """Calculate population dispersion from the exact peers/IDW weights used for the base rate.

    Weights need not be normalized. Call before rounding the indexer's peer payload,
    so the published six-decimal distances/weights cannot change the calculation.
    """
    if len(peer_rates) == 0 or len(peer_rates) != len(idw_weights):
        raise ValueError("non-empty, aligned peer rates and IDW weights are required")
    rates = [_non_negative_finite(rate, "peer rate") for rate in peer_rates]
    weights = [_non_negative_finite(weight, "IDW weight") for weight in idw_weights]
    total = math.fsum(weights)
    if not math.isfinite(total) or total <= 0:
        raise ValueError("IDW weights must have a positive finite total")
    mean = math.fsum(rate * weight for rate, weight in zip(rates, weights)) / total
    if not math.isfinite(mean):
        raise ValueError("weighted peer rate must be finite")
    variance = math.fsum(weight * (rate - mean) ** 2 for rate, weight in zip(rates, weights)) / total
    if not math.isfinite(variance):
        raise ValueError("weighted peer variance must be finite")
    return math.sqrt(max(0.0, variance))


def synthesize_corridor(
    base_rate: float,
    peer_stddev: float,
    bilateral_factor: float,
    base_rate_floor: float | None = None,
) -> dict[str, float]:
    """Apply FR-06 to the rounded base quote and full-precision peer dispersion.

    Bounds remain unrounded to preserve the floor and formula; presentation/cent
    rounding belongs to the future canonical contract (#83). Payment fees are
    deliberately excluded from both bounds.
    """
    base = _non_negative_finite(base_rate, "base rate")
    sigma = _non_negative_finite(peer_stddev, "peer standard deviation")
    phi = _non_negative_finite(bilateral_factor, "bilateral factor")
    if phi <= 0:
        raise ValueError("bilateral factor must be positive")
    floor = base * 0.5 if base_rate_floor is None else _non_negative_finite(base_rate_floor, "base rate floor")
    minimum = max(floor, base - 0.75 * sigma)
    maximum = (base + 1.25 * sigma) * (2 - phi if phi < 1 else 1)
    if not math.isfinite(minimum) or not math.isfinite(maximum):
        raise ValueError("pricing corridor bounds must be finite")
    if minimum > maximum:
        raise FloorExceedsCeilingError("base_rate_floor exceeds the peer-based pricing ceiling")
    return {"min_quoted_rate": minimum, "max_quoted_rate": maximum}
