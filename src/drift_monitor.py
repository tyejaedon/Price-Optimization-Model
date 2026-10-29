"""Automated Retraining and Continuous Drift Monitoring for MLOps (M16.7).

Monitors feature distributions (covariate drift) and pricing transaction rates
(concept/target drift) from logged Firestore transactions (historical_transactions)
to detect macroeconomic inflation, market saturation shifts, and latent concept drift.

Statistical tests:
1. Population Stability Index (PSI):
   - PSI < 0.1: Stable, no significant shift.
   - 0.1 <= PSI < 0.2: Moderate shift, warning threshold.
   - PSI >= 0.2: Significant drift, automated retraining trigger.
2. Two-sample Kolmogorov-Smirnov Test (KS-Test):
   - Computes maximum difference between empirical cumulative distributions.
3. Wasserstein Distance (Earth Mover's Distance):
   - Measures metric transport distance between distributions.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import numpy as np
    from scipy.stats import ks_2samp, wasserstein_distance
except ImportError as exc:
    raise RuntimeError("Missing statistical dependencies. Install scipy and numpy from requirements.txt") from exc

PSI_STABLE_THRESHOLD = 0.10
PSI_DRIFT_THRESHOLD = 0.20


def compute_psi(
    reference: Sequence[float],
    current: Sequence[float],
    num_buckets: int = 10,
    epsilon: float = 1e-4,
) -> float:
    """Calculate Population Stability Index (PSI) between two continuous distributions.

    Reference distribution establishes quantile bin boundaries. The proportion
    of current observations falling into each bin is compared against reference.
    """
    ref_arr = np.asarray(reference, dtype=float).reshape(-1)
    cur_arr = np.asarray(current, dtype=float).reshape(-1)

    if ref_arr.size == 0 or cur_arr.size == 0:
        raise ValueError("Distributions cannot be empty.")

    # Generate quantile bin edges from reference with infinite bounds to capture extreme shifts
    quantiles = np.linspace(0, 100, num_buckets + 1)
    bin_edges = np.percentile(ref_arr, quantiles)
    # Ensure strictly monotonic internal bin edges
    for i in range(1, len(bin_edges) - 1):
        if bin_edges[i] <= bin_edges[i - 1]:
            bin_edges[i] = bin_edges[i - 1] + 1e-6
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    ref_counts, _ = np.histogram(ref_arr, bins=bin_edges)
    cur_counts, _ = np.histogram(cur_arr, bins=bin_edges)

    ref_pct = np.maximum(ref_counts / float(ref_arr.size), epsilon)
    cur_pct = np.maximum(cur_counts / float(cur_arr.size), epsilon)

    # Normalize after epsilon floor
    ref_pct /= np.sum(ref_pct)
    cur_pct /= np.sum(cur_pct)

    psi_value = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return max(0.0, psi_value)


def compute_kolmogorov_smirnov(
    reference: Sequence[float],
    current: Sequence[float],
) -> Tuple[float, float]:
    """Perform two-sample Kolmogorov-Smirnov test.

    Returns (statistic, p_value).
    """
    ref_arr = np.asarray(reference, dtype=float).reshape(-1)
    cur_arr = np.asarray(current, dtype=float).reshape(-1)

    res = ks_2samp(ref_arr, cur_arr)
    return float(res.statistic), float(res.pvalue)


def compute_wasserstein(
    reference: Sequence[float],
    current: Sequence[float],
) -> float:
    """Calculate first Wasserstein distance (Earth Mover's Distance)."""
    ref_arr = np.asarray(reference, dtype=float).reshape(-1)
    cur_arr = np.asarray(current, dtype=float).reshape(-1)

    return float(wasserstein_distance(ref_arr, cur_arr))


def evaluate_retraining_trigger(
    target_psi: float,
    feature_psis: Dict[str, float],
    psi_drift_threshold: float = PSI_DRIFT_THRESHOLD,
) -> Dict[str, Any]:
    """Evaluate whether observed drift levels warrant automated pipeline retraining.

    Triggers retraining if target rate drift exceeds threshold or if more than
    half of tracked continuous features exhibit significant drift.
    """
    target_drifted = bool(target_psi >= psi_drift_threshold)
    drifted_features = [feat for feat, psi in feature_psis.items() if psi >= psi_drift_threshold]
    severe_feature_drift = len(drifted_features) >= max(1, len(feature_psis) // 2)

    trigger_retrain = target_drifted or severe_feature_drift

    status = "STABLE"
    if trigger_retrain:
        status = "DRIFT_DETECTED"
    elif target_psi >= PSI_STABLE_THRESHOLD or len(drifted_features) > 0:
        status = "WARNING"

    reasons: List[str] = []
    if target_drifted:
        reasons.append(f"Target transaction rate PSI ({target_psi:.4f}) exceeds threshold ({psi_drift_threshold:.2f}).")
    if drifted_features:
        reasons.append(f"Continuous features exhibiting drift: {', '.join(drifted_features)}.")
    if not trigger_retrain and not reasons:
        reasons.append("All continuous features and transaction rates remain within empirical stability bounds.")

    return {
        "status": status,
        "trigger_retrain": trigger_retrain,
        "target_rate_psi": round(target_psi, 4),
        "feature_psis": {k: round(v, 4) for k, v in feature_psis.items()},
        "drifted_features": drifted_features,
        "reasons": reasons,
    }


def analyze_transaction_drift(
    reference_transactions: Sequence[Dict[str, Any]],
    current_transactions: Sequence[Dict[str, Any]],
    target_field: str = "final_quoted_rate",
    feature_fields: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Analyze covariate and target drift between baseline and production transactions.

    Extracts numerical series from transaction logs (e.g. from Firestore historical_transactions).
    """
    if feature_fields is None:
        feature_fields = ("base_predicted_rate", "mpesa_tariff_surcharge")

    ref_targets = [float(tx[target_field]) for tx in reference_transactions if target_field in tx]
    cur_targets = [float(tx[target_field]) for tx in current_transactions if target_field in tx]

    target_psi = compute_psi(ref_targets, cur_targets)
    ks_stat, ks_pval = compute_kolmogorov_smirnov(ref_targets, cur_targets)
    w_dist = compute_wasserstein(ref_targets, cur_targets)

    feature_psis: Dict[str, float] = {}
    for feat in feature_fields:
        ref_feat = [float(tx[feat]) for tx in reference_transactions if feat in tx]
        cur_feat = [float(tx[feat]) for tx in current_transactions if feat in tx]
        if ref_feat and cur_feat:
            feature_psis[feat] = compute_psi(ref_feat, cur_feat)

    decision = evaluate_retraining_trigger(target_psi, feature_psis)

    return {
        **decision,
        "target_ks_statistic": round(ks_stat, 4),
        "target_ks_pvalue": round(ks_pval, 6),
        "target_wasserstein_distance": round(w_dist, 4),
        "reference_sample_count": len(ref_targets),
        "current_sample_count": len(cur_targets),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuous drift monitoring and retraining trigger evaluator.")
    parser.add_argument("--drift-magnitude", type=float, default=0.25, help="Simulated distribution shift multiplier")
    parser.add_argument("--samples", type=int, default=200, help="Sample count for simulated evaluation")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = np.random.RandomState(42)

    # Reference transactions baseline (e.g. historical logged listings)
    ref_rates = rng.normal(3000.0, 400.0, size=args.samples)
    cur_rates = rng.normal(3000.0 * (1.0 + args.drift_magnitude), 450.0, size=args.samples)

    ref_txs = [{"final_quoted_rate": r, "base_predicted_rate": r - 50.0, "mpesa_tariff_surcharge": 50.0} for r in ref_rates]
    cur_txs = [{"final_quoted_rate": r, "base_predicted_rate": r - 50.0, "mpesa_tariff_surcharge": 50.0} for r in cur_rates]

    report = analyze_transaction_drift(ref_txs, cur_txs)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
