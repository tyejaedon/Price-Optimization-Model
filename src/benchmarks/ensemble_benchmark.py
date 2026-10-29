"""Benchmark KNN Regression against Linear and Tree Ensemble Models (M16.1).

Quantifies the empirical trade-off between predictive accuracy and model
interpretability across:
1. Inverse Distance Weighted KNN (Spatial Baseline)
2. Ridge Regression (L2 Regularized Linear Model)
3. Random Forest Regressor (Bagging Tree Ensemble)
4. Gradient Boosting Regressor (Boosting Tree Ensemble)

Metric evaluation:
- MAE (Mean Absolute Error, in KES/hour)
- RMSE (Root Mean Squared Error, in KES/hour)
- MAPE (Mean Absolute Percentage Error, %)
- Inference Latency (milliseconds per single quote)
- Interpretability Score (0.0 to 1.0, measuring local peer provenance)
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    from sklearn.neighbors import KNeighborsRegressor
except ImportError as exc:
    raise RuntimeError("Missing scikit-learn dependencies. Install from requirements.txt") from exc

from src.engine.macro_arbitrage import HYBRID_VECTOR_DIMENSIONS


def compute_mape(y_true: np.ndarray, y_pred: np.ndarray, epsilon: float = 1e-4) -> float:
    """Calculate Mean Absolute Percentage Error (MAPE) in percent."""
    safe_true = np.where(np.abs(y_true) < epsilon, epsilon, y_true)
    return float(np.mean(np.abs((y_true - y_pred) / safe_true)) * 100.0)


def generate_synthetic_benchmark_dataset(
    n_samples: int = 500,
    n_features: int = HYBRID_VECTOR_DIMENSIONS,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate train and test splits simulating marketplace rates."""
    rng = np.random.RandomState(random_state)
    X = rng.randn(n_samples, n_features)

    # Realistic rate generating function: base + linear feature response + non-linear interaction + noise
    base_rate = 3000.0
    linear_effect = X[:, 0] * 350.0 + X[:, 1] * 200.0 - X[:, -1] * 180.0
    interaction_effect = 120.0 * np.sin(X[:, 2]) * np.cos(X[:, -2])
    noise = rng.normal(0, 150.0, size=n_samples)

    y = np.maximum(500.0, base_rate + linear_effect + interaction_effect + noise)

    split = int(n_samples * 0.8)
    return X[:split], y[:split], X[split:], y[split:]


def profile_inference_latency_ms(model: Any, X_sample: np.ndarray, iterations: int = 100) -> float:
    """Measure single-row prediction latency in milliseconds."""
    single_row = X_sample[:1]
    start = time.perf_counter()
    for _ in range(iterations):
        model.predict(single_row)
    total_time = time.perf_counter() - start
    return float((total_time / iterations) * 1000.0)


def run_ensemble_comparison(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    k: int = 5,
    random_state: int = 42,
) -> Dict[str, Dict[str, float]]:
    """Train and evaluate KNN vs Ridge vs Random Forest vs Gradient Boosting.

    Returns performance dictionary with MAE, RMSE, MAPE, latency_ms, and
    interpretability_score.
    """
    models: Dict[str, Any] = {
        "knn_idw": KNeighborsRegressor(n_neighbors=k, weights="distance", metric="euclidean"),
        "ridge_regression": Ridge(alpha=1.0, random_state=random_state),
        "random_forest": RandomForestRegressor(n_estimators=100, max_depth=8, random_state=random_state),
        "gradient_boosting": GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=random_state),
    }

    # Interpretability score represents capability to supply granular local peer provenance
    # KNN: 1.0 (exact peer citations with URLs and titles)
    # Ridge: 0.5 (global linear feature coefficients, no peer citations)
    # Random Forest: 0.3 (Gini/impurity feature importance, ensemble averaging)
    # Gradient Boosting: 0.2 (boosted ensemble trees, opaque individual peer attribution)
    interpretability_scores: Dict[str, float] = {
        "knn_idw": 1.0,
        "ridge_regression": 0.5,
        "random_forest": 0.3,
        "gradient_boosting": 0.2,
    }

    results: Dict[str, Dict[str, float]] = {}

    for name, model in models.items():
        t0 = time.perf_counter()
        model.fit(X_train, y_train)
        fit_time_s = time.perf_counter() - t0

        y_pred = model.predict(X_test)
        mae = float(mean_absolute_error(y_test, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mape = compute_mape(y_test, y_pred)
        latency_ms = profile_inference_latency_ms(model, X_test, iterations=50)

        results[name] = {
            "mae_kes": round(mae, 2),
            "rmse_kes": round(rmse, 2),
            "mape_percent": round(mape, 2),
            "fit_time_seconds": round(fit_time_s, 4),
            "inference_latency_ms": round(latency_ms, 4),
            "interpretability_score": interpretability_scores[name],
        }

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark KNN regression against linear and tree ensembles.")
    parser.add_argument("--samples", type=int, default=600, help="Number of benchmark samples to generate")
    parser.add_argument("--k", type=int, default=5, help="Number of nearest neighbors for KNN")
    parser.add_argument("--random-state", type=int, default=42, help="Deterministic random state")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    X_train, y_train, X_test, y_test = generate_synthetic_benchmark_dataset(
        n_samples=args.samples,
        random_state=args.random_state,
    )
    results = run_ensemble_comparison(
        X_train, y_train, X_test, y_test,
        k=args.k,
        random_state=args.random_state,
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
