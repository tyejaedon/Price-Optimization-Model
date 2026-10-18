"""Hyperparameter optimization using PCA and Random Search for the Price Optimization Model.

This script:
1. Loads the harmonized marketplace corpus and sovereign macro lookup table.
2. Performs stratified train/validation/test splitting (70/15/15) preserving industry partitions.
3. Performs PCA / TruncatedSVD dimensionality reduction and explained-variance analysis.
4. Executes a randomized search over the hyperparameter space:
   - Text vectorization (max_features, ngram_range, min_df, sublinear_tf, tfidf_norm)
   - PCA / TruncatedSVD components & normalization
   - Hybrid coordinate fusion weights (text_weight, metadata_weight)
   - Domain-partitioned KDTree / IDW regression (k_neighbors, idw_epsilon, minimum_partition_size, allow_fallback)
   - Target scaling (raw vs. log1p)
5. Benchmarks the optimal PCA features across multiple model families:
   - Baseline Category-Mean
   - DomainPartitionedKDTreeIndexer (production peer-pricing architecture)
   - KNeighborsRegressor
   - Ridge Regressor
   - HistGradientBoostingRegressor
6. Trains and exports the optimal production model and all artifacts to artifacts/
   including manifest.json, inference_config.json, and training_summary.json.
7. Validates that InferenceRuntime loads the trained bundle cleanly.
8. Writes a comprehensive experiment and findings report to reports/random_search_findings.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import shutil
import time
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.neighbors import KNeighborsRegressor

from src.core.artifact_contract import MANIFEST_NAME, file_sha256, write_manifest
from src.data.ingest_multisource import BILATERAL_ALPHA
from src.engine.macro_arbitrage import (
    DEFAULT_FEATURE_NAMES,
    DEFAULT_INFERENCE_CONFIG_ARTIFACT,
    DEFAULT_BUNDLED_MACRO_LOOKUP,
    HYBRID_VECTOR_DIMENSIONS,
    METADATA_VECTOR_DIMENSIONS,
    TEXT_VECTOR_DIMENSIONS,
    ContinuousMetadataNormalizer,
    fuse_coordinate_batches,
)
from src.engine.spatial_engine import (
    DEFAULT_IDW_EPSILON,
    DEFAULT_MIN_PARTITION_SIZE,
    DomainPartitionedKDTreeIndexer,
)
from src.nlp.nlp_pipeline import TextFeatureReducer, ensure_text_dimensions, sanitize_many
from src.training.train_pipeline import (
    DEFAULT_HARMONIZED_PARQUET,
    DEFAULT_RANDOM_STATE,
    DEFAULT_TRAINING_SUMMARY_ARTIFACT,
    SplitData,
    _build_category_mean_baseline,
    _metric_summary,
    _predict_category_mean_baseline,
    _predict_idw,
    build_stratified_splits,
    inverse_target_log1p,
    load_harmonized_parquet,
    transform_target_log1p,
)


@dataclass(frozen=True)
class HyperparameterCandidate:
    # Text / PCA parameters
    max_features: int
    ngram_range: Tuple[int, int]
    min_df: int
    sublinear_tf: bool
    tfidf_norm: str
    n_components: int
    normalize_output: bool
    # Fusion weights
    text_weight: float
    metadata_weight: float
    # KNN / Spatial indexer parameters
    k_neighbors: int
    idw_epsilon: float
    minimum_partition_size: int
    allow_fallback: bool
    # Target transform
    target_transform: str  # 'raw' or 'log1p'


def analyze_pca_explained_variance(
    clean_train_texts: List[str],
    component_steps: Tuple[int, ...] = (5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100),
    max_features: int = 12000,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> Dict[str, Any]:
    """Fit SVD/PCA on TF-IDF vectors across multiple component counts and record variance."""
    max_components = max(component_steps)
    reducer = TextFeatureReducer(
        n_components=max_components,
        max_features=max_features,
        ngram_range=(1, 2),
        min_df=1,
        random_state=random_state,
    )
    reducer.fit_transform(clean_train_texts)

    evr = getattr(reducer.reducer, "explained_variance_ratio_", None)
    if evr is None:
        return {"error": "explained_variance_ratio_ not available"}

    cumulative_variance = np.cumsum(evr)
    variance_table = []
    for c in component_steps:
        idx = min(c - 1, len(cumulative_variance) - 1)
        variance_table.append({
            "n_components": c,
            "cumulative_variance_ratio": round(float(cumulative_variance[idx]), 6),
            "individual_component_variance": round(float(evr[idx]), 6),
        })

    return {
        "max_components_fitted": int(reducer.reducer.n_components),
        "vocabulary_size": int(len(reducer.vectorizer.vocabulary_)),
        "variance_table": variance_table,
    }


def sample_random_hyperparameters(
    n_samples: int = 40,
    seed: int = 42,
) -> List[HyperparameterCandidate]:
    """Sample diverse configurations across the hyperparameter grid."""
    rng = random.Random(seed)

    # Param search spaces
    max_features_choices = [5000, 8000, 10000, 12000, 15000]
    ngram_range_choices = [(1, 1), (1, 2), (1, 3)]
    min_df_choices = [1, 2, 3]
    sublinear_tf_choices = [True, False]
    tfidf_norm_choices = ["l2", "l1"]
    n_components_choices = [25, 35, 50, 75]
    normalize_output_choices = [False, True]

    text_weight_choices = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
    metadata_weight_choices = [0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]

    k_neighbors_choices = [1, 3, 5, 7, 10, 12, 15, 20, 25, 30]
    idw_epsilon_choices = [1e-3, 1e-4, 1e-5, 1e-6, 1e-8]
    minimum_partition_size_choices = [1, 2, 5, 10]
    allow_fallback_choices = [True]
    target_transform_choices = ["raw", "log1p"]

    candidates: List[HyperparameterCandidate] = []

    # Always include baseline/default as candidate 0
    candidates.append(
        HyperparameterCandidate(
            max_features=12000,
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
            tfidf_norm="l2",
            n_components=50,
            normalize_output=False,
            text_weight=1.0,
            metadata_weight=1.0,
            k_neighbors=5,
            idw_epsilon=1e-6,
            minimum_partition_size=DEFAULT_MIN_PARTITION_SIZE,
            allow_fallback=True,
            target_transform="raw",
        )
    )

    # Sample remaining
    seen = {candidates[0]}
    while len(candidates) < n_samples:
        candidate = HyperparameterCandidate(
            max_features=rng.choice(max_features_choices),
            ngram_range=rng.choice(ngram_range_choices),
            min_df=rng.choice(min_df_choices),
            sublinear_tf=rng.choice(sublinear_tf_choices),
            tfidf_norm=rng.choice(tfidf_norm_choices),
            n_components=rng.choice(n_components_choices),
            normalize_output=rng.choice(normalize_output_choices),
            text_weight=rng.choice(text_weight_choices),
            metadata_weight=rng.choice(metadata_weight_choices),
            k_neighbors=rng.choice(k_neighbors_choices),
            idw_epsilon=rng.choice(idw_epsilon_choices),
            minimum_partition_size=rng.choice(minimum_partition_size_choices),
            allow_fallback=rng.choice(allow_fallback_choices),
            target_transform=rng.choice(target_transform_choices),
        )
        if candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

    return candidates


def run_random_search_optimization(
    harmonized_parquet_path: str = DEFAULT_HARMONIZED_PARQUET,
    macro_lookup_path: str = os.path.join("data", "processed", "macro_lookup_table.json"),
    n_trials: int = 40,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], SplitData]:
    """Execute hyperparameter random search over the training/validation splits."""
    print("=" * 70)
    print("STEP 1: Loading Data and Preparing Stratified Splits")
    print("=" * 70)
    frame = load_harmonized_parquet(harmonized_parquet_path)
    split_data = build_stratified_splits(frame, random_state=random_state)
    print(f"Total Rows: {len(frame):,}")
    print(f"Train Rows: {len(split_data.train):,} (70%)")
    print(f"Val Rows:   {len(split_data.validation):,} (15%)")
    print(f"Test Rows:  {len(split_data.test):,} (15%)")

    # Clean raw descriptions once to avoid redundant regex
    print("\nPre-sanitizing descriptions across partitions...")
    t0 = time.time()
    clean_train = sanitize_many(split_data.train["raw_description"].tolist())
    clean_val = sanitize_many(split_data.validation["raw_description"].tolist())
    print(f"Sanitization complete in {time.time() - t0:.2f}s")

    # Macro normalizer
    normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path)
    train_meta = normalizer.fit_transform(split_data.train.to_dict(orient="records"))
    val_meta = normalizer.transform(split_data.validation.to_dict(orient="records"))

    y_train_raw = split_data.train["target_rate"].to_numpy(dtype=float)
    y_val_raw = split_data.validation["target_rate"].to_numpy(dtype=float)
    y_train_log = transform_target_log1p(y_train_raw)

    train_partitions = split_data.train["industry_partition"].tolist()
    val_partitions = split_data.validation["industry_partition"].tolist()
    train_record_ids = np.asarray(split_data.train["record_id"].to_numpy(), dtype=int).tolist()

    # Category Mean Baseline
    means, global_mean = _build_category_mean_baseline(split_data.train)
    baseline_val_preds = _predict_category_mean_baseline(split_data.validation, means, global_mean)
    baseline_val_metrics = _metric_summary(y_val_raw, baseline_val_preds)
    print(f"\nBaseline Category-Mean Validation Metrics:")
    print(f"  R²:    {baseline_val_metrics['r2']:.6f}")
    print(f"  RMSE:  {baseline_val_metrics['rmse']:,.2f} KES/hr")
    print(f"  MAE:   {baseline_val_metrics['mae']:,.2f} KES/hr")
    print(f"  MedAE: {baseline_val_metrics['median_absolute_error']:,.2f} KES/hr")
    print(f"  sMAPE: {baseline_val_metrics['smape_percent']:.2f}%")

    print("\n" + "=" * 70)
    print("STEP 2: PCA / TruncatedSVD Scree & Variance Analysis")
    print("=" * 70)
    pca_analysis = analyze_pca_explained_variance(clean_train, random_state=random_state)
    for row in pca_analysis.get("variance_table", []):
        print(f"  Components: {row['n_components']:3d} | Cum. Variance: {row['cumulative_variance_ratio'] * 100:6.2f}% | Marginal: {row['individual_component_variance'] * 100:6.3f}%")

    print("\n" + "=" * 70)
    print(f"STEP 3: Randomized Search across {n_trials} Hyperparameter Configurations")
    print("=" * 70)
    candidates = sample_random_hyperparameters(n_samples=n_trials, seed=random_state)

    cache_path = os.path.join("reports", f"search_trials_cache_{n_trials}.json")
    if os.path.isfile(cache_path):
        print(f"Loading cached search results from {cache_path}...")
        with open(cache_path, "r", encoding="utf-8") as f:
            results = json.load(f)
    else:
        # Group candidates by text reducer configuration to cache fits
        from collections import defaultdict
        grouped = defaultdict(list)
        for idx, c in enumerate(candidates):
            text_key = (
                c.max_features,
                c.ngram_range,
                c.min_df,
                c.sublinear_tf,
                c.tfidf_norm,
                c.n_components,
                c.normalize_output,
            )
            grouped[text_key].append((idx, c))

        print(f"Grouped into {len(grouped)} unique NLP/PCA representations for caching.")

        results: List[Dict[str, Any]] = []
        trial_count = 0

        for text_key, cand_list in grouped.items():
            (mf, ng, mdf, stf, tnorm, nc, norm_out) = text_key

            # Fit TextFeatureReducer
            reducer = TextFeatureReducer(
                n_components=nc,
                max_features=mf,
                ngram_range=ng,
                min_df=mdf,
                normalize_output=norm_out,
                tfidf_norm=tnorm,
                random_state=random_state,
            )
            t_fit_start = time.perf_counter()
            raw_train_text = reducer.fit_transform(clean_train)
            raw_val_text = reducer.transform(clean_val)
            fit_time_sec = time.perf_counter() - t_fit_start

            # Always enforce fixed 50 dimensions for coordinate fusion
            train_text_50 = ensure_text_dimensions(raw_train_text, TEXT_VECTOR_DIMENSIONS)
            val_text_50 = ensure_text_dimensions(raw_val_text, TEXT_VECTOR_DIMENSIONS)

            for trial_idx, c in cand_list:
                trial_count += 1
                # Scale coordinates
                X_train = fuse_coordinate_batches(train_text_50 * c.text_weight, train_meta * c.metadata_weight)
                X_val = fuse_coordinate_batches(val_text_50 * c.text_weight, val_meta * c.metadata_weight)

                # Fit KDTree indexer
                use_log = (c.target_transform == "log1p")
                train_rates = y_train_log if use_log else y_train_raw

                indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=c.minimum_partition_size)
                indexer.fit(
                    hybrid_vectors=X_train,
                    industry_partitions=train_partitions,
                    record_indices=train_record_ids,
                    verified_rates=train_rates.tolist(),
                )

                # Predict on validation set
                t_infer_start = time.perf_counter()
                preds = _predict_idw(
                    indexer,
                    X_val,
                    val_partitions,
                    k_neighbors=c.k_neighbors,
                    allow_fallback=c.allow_fallback,
                    epsilon=c.idw_epsilon,
                )
                infer_time_ms = (time.perf_counter() - t_infer_start) * 1000.0

                if use_log:
                    preds_eval = inverse_target_log1p(preds)
                else:
                    preds_eval = preds

                metrics = _metric_summary(y_val_raw, preds_eval)

                trial_record = {
                    "trial_idx": trial_idx,
                    "trial_order": trial_count,
                    "n_components": c.n_components,
                    "max_features": c.max_features,
                    "ngram_range": f"{c.ngram_range[0]}-{c.ngram_range[1]}",
                    "min_df": c.min_df,
                    "sublinear_tf": c.sublinear_tf,
                    "tfidf_norm": c.tfidf_norm,
                    "normalize_output": c.normalize_output,
                    "text_weight": c.text_weight,
                    "metadata_weight": c.metadata_weight,
                    "k_neighbors": c.k_neighbors,
                    "idw_epsilon": c.idw_epsilon,
                    "minimum_partition_size": c.minimum_partition_size,
                    "allow_fallback": c.allow_fallback,
                    "target_transform": c.target_transform,
                    "fit_time_sec": round(fit_time_sec, 3),
                    "val_infer_time_ms": round(infer_time_ms, 2),
                    "val_r2": metrics["r2"],
                    "val_rmse": metrics["rmse"],
                    "val_mae": metrics["mae"],
                    "val_median_absolute_error": metrics["median_absolute_error"],
                    "val_smape_percent": metrics["smape_percent"],
                    "outperforms_baseline": bool(metrics["r2"] > baseline_val_metrics["r2"] and metrics["rmse"] < baseline_val_metrics["rmse"]),
                }
                results.append(trial_record)

                status = "DEFAULT" if trial_idx == 0 else f"#{trial_count:2d}"
                print(
                    f"[{status}] R²={metrics['r2']:.4f} | RMSE={metrics['rmse']:,.0f} | MAE={metrics['mae']:,.0f} | "
                    f"k={c.k_neighbors:2d} | tw={c.text_weight:.2f} | mw={c.metadata_weight:.2f} | "
                    f"pca={c.n_components:2d} | tgt={c.target_transform:5s}"
                )

        os.makedirs("reports", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    # Rank results by Validation R² (higher is better) and MAE (lower is better)
    df_results = pd.DataFrame(results).sort_values("val_r2", ascending=False).reset_index(drop=True)
    best_trial = df_results.iloc[0].to_dict()

    print("\n" + "=" * 70)
    print("TOP 5 HYPERPARAMETER CONFIGURATIONS FOUND:")
    print("=" * 70)
    top_cols = ["trial_idx", "val_r2", "val_rmse", "val_mae", "val_smape_percent", "k_neighbors", "text_weight", "metadata_weight", "n_components", "target_transform"]
    print(df_results[top_cols].head(5).to_string(index=False))

    return results, best_trial, split_data


def benchmark_model_families_on_pca_features(
    split_data: SplitData,
    best_candidate: Dict[str, Any],
    macro_lookup_path: str,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> Dict[str, Any]:
    """Train multiple model families on the optimal PCA coordinates for comparison."""
    print("\n" + "=" * 70)
    print("STEP 4: Benchmarking Model Families on Optimal PCA Features")
    print("=" * 70)

    clean_train = sanitize_many(split_data.train["raw_description"].tolist())
    clean_val = sanitize_many(split_data.validation["raw_description"].tolist())
    clean_test = sanitize_many(split_data.test["raw_description"].tolist())

    reducer = TextFeatureReducer(
        n_components=TEXT_VECTOR_DIMENSIONS,
        max_features=int(best_candidate["max_features"]),
        ngram_range=tuple(int(x) for x in str(best_candidate["ngram_range"]).split("-")),
        min_df=int(best_candidate["min_df"]),
        normalize_output=bool(best_candidate["normalize_output"]),
        tfidf_norm=str(best_candidate["tfidf_norm"]),
        random_state=random_state,
    )
    t_train = ensure_text_dimensions(reducer.fit_transform(clean_train), TEXT_VECTOR_DIMENSIONS)
    t_val = ensure_text_dimensions(reducer.transform(clean_val), TEXT_VECTOR_DIMENSIONS)
    t_test = ensure_text_dimensions(reducer.transform(clean_test), TEXT_VECTOR_DIMENSIONS)

    normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path)
    m_train = normalizer.fit_transform(split_data.train.to_dict(orient="records"))
    m_val = normalizer.transform(split_data.validation.to_dict(orient="records"))
    m_test = normalizer.transform(split_data.test.to_dict(orient="records"))

    tw = float(best_candidate["text_weight"])
    mw = float(best_candidate["metadata_weight"])

    X_train = fuse_coordinate_batches(t_train * tw, m_train * mw)
    X_val = fuse_coordinate_batches(t_val * tw, m_val * mw)
    X_test = fuse_coordinate_batches(t_test * tw, m_test * mw)

    y_train = split_data.train["target_rate"].to_numpy(dtype=float)
    y_val = split_data.validation["target_rate"].to_numpy(dtype=float)
    y_test = split_data.test["target_rate"].to_numpy(dtype=float)

    use_log = (best_candidate["target_transform"] == "log1p")
    y_train_fit = transform_target_log1p(y_train) if use_log else y_train

    # 1. Baseline: Category Mean
    means, global_mean = _build_category_mean_baseline(split_data.train)
    b_val_preds = _predict_category_mean_baseline(split_data.validation, means, global_mean)
    b_test_preds = _predict_category_mean_baseline(split_data.test, means, global_mean)
    b_val_metrics = _metric_summary(y_val, b_val_preds)
    b_test_metrics = _metric_summary(y_test, b_test_preds)

    # 2. DomainPartitionedKDTree (Optimized)
    k_opt = int(best_candidate["k_neighbors"])
    eps_opt = float(best_candidate["idw_epsilon"])
    indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=int(best_candidate["minimum_partition_size"]))
    indexer.fit(
        hybrid_vectors=X_train,
        industry_partitions=split_data.train["industry_partition"].tolist(),
        record_indices=np.asarray(split_data.train["record_id"].to_numpy(), dtype=int).tolist(),
        verified_rates=y_train_fit.tolist(),
    )
    kdt_val_raw = _predict_idw(
        indexer,
        X_val,
        split_data.validation["industry_partition"].tolist(),
        k_neighbors=k_opt,
        epsilon=eps_opt,
    )
    kdt_test_raw = _predict_idw(
        indexer,
        X_test,
        split_data.test["industry_partition"].tolist(),
        k_neighbors=k_opt,
        epsilon=eps_opt,
    )
    kdt_val_preds = inverse_target_log1p(kdt_val_raw) if use_log else kdt_val_raw
    kdt_test_preds = inverse_target_log1p(kdt_test_raw) if use_log else kdt_test_raw
    kdt_val_metrics = _metric_summary(y_val, kdt_val_preds)
    kdt_test_metrics = _metric_summary(y_test, kdt_test_preds)

    # 3. Ridge Regressor
    ridge = Ridge(alpha=1.0, random_state=random_state).fit(X_train, y_train_fit)
    ridge_val_raw = ridge.predict(X_val)
    ridge_test_raw = ridge.predict(X_test)
    ridge_val_preds = inverse_target_log1p(ridge_val_raw) if use_log else ridge_val_raw
    ridge_test_preds = inverse_target_log1p(ridge_test_raw) if use_log else ridge_test_raw
    ridge_val_metrics = _metric_summary(y_val, ridge_val_preds)
    ridge_test_metrics = _metric_summary(y_test, ridge_test_preds)

    # 4. KNeighborsRegressor (Standard Euclidean)
    knn_reg = KNeighborsRegressor(n_neighbors=k_opt, weights="distance").fit(X_train, y_train_fit)
    knn_val_raw = knn_reg.predict(X_val)
    knn_test_raw = knn_reg.predict(X_test)
    knn_val_preds = inverse_target_log1p(knn_val_raw) if use_log else knn_val_raw
    knn_test_preds = inverse_target_log1p(knn_test_raw) if use_log else knn_test_raw
    knn_val_metrics = _metric_summary(y_val, knn_val_preds)
    knn_test_metrics = _metric_summary(y_test, knn_test_preds)

    # 5. HistGradientBoostingRegressor
    hgbr = HistGradientBoostingRegressor(random_state=random_state, max_iter=100).fit(X_train, y_train_fit)
    hgbr_val_raw = hgbr.predict(X_val)
    hgbr_test_raw = hgbr.predict(X_test)
    hgbr_val_preds = inverse_target_log1p(hgbr_val_raw) if use_log else hgbr_val_raw
    hgbr_test_preds = inverse_target_log1p(hgbr_test_raw) if use_log else hgbr_test_raw
    hgbr_val_metrics = _metric_summary(y_val, hgbr_val_preds)
    hgbr_test_metrics = _metric_summary(y_test, hgbr_test_preds)

    benchmarks = {
        "CategoryMeanBaseline": {"validation": b_val_metrics, "test": b_test_metrics},
        "DomainPartitionedKDTree_Optimized": {"validation": kdt_val_metrics, "test": kdt_test_metrics},
        "RidgeRegressor": {"validation": ridge_val_metrics, "test": ridge_test_metrics},
        "KNeighborsRegressor_Standard": {"validation": knn_val_metrics, "test": knn_test_metrics},
        "HistGradientBoostingRegressor": {"validation": hgbr_val_metrics, "test": hgbr_test_metrics},
    }

    print("\nModel Comparison Table (Validation & Test Sets):")
    rows = []
    for model_name, m_dict in benchmarks.items():
        v = m_dict["validation"]
        t = m_dict["test"]
        rows.append({
            "Model": model_name,
            "Val R²": f"{v['r2']:.4f}",
            "Val RMSE": f"{v['rmse']:,.0f}",
            "Val MAE": f"{v['mae']:,.0f}",
            "Val sMAPE": f"{v['smape_percent']:.1f}%",
            "Test R²": f"{t['r2']:.4f}",
            "Test RMSE": f"{t['rmse']:,.0f}",
            "Test MAE": f"{t['mae']:,.0f}",
            "Test sMAPE": f"{t['smape_percent']:.1f}%",
        })
    print(pd.DataFrame(rows).to_string(index=False))

    return benchmarks


def train_and_export_optimal_production_model(
    split_data: SplitData,
    best_candidate: Dict[str, Any],
    macro_lookup_path: str,
    harmonized_parquet_path: str,
    artifact_dir: str = "artifacts",
    random_state: int = DEFAULT_RANDOM_STATE,
) -> Dict[str, Any]:
    """Train with optimal hyperparams and serialize all required production artifacts."""
    print("\n" + "=" * 70)
    print("STEP 5: Training and Exporting Optimal Production Model Artifacts")
    print("=" * 70)
    os.makedirs(artifact_dir, exist_ok=True)

    clean_train = sanitize_many(split_data.train["raw_description"].tolist())
    clean_val = sanitize_many(split_data.validation["raw_description"].tolist())
    clean_test = sanitize_many(split_data.test["raw_description"].tolist())

    # Text reducer with exactly 50 dimensions for production contract
    reducer = TextFeatureReducer(
        n_components=TEXT_VECTOR_DIMENSIONS,
        max_features=int(best_candidate["max_features"]),
        ngram_range=tuple(int(x) for x in str(best_candidate["ngram_range"]).split("-")),
        min_df=int(best_candidate["min_df"]),
        normalize_output=bool(best_candidate["normalize_output"]),
        tfidf_norm=str(best_candidate["tfidf_norm"]),
        random_state=random_state,
    )
    t_train = ensure_text_dimensions(reducer.fit_transform(clean_train), TEXT_VECTOR_DIMENSIONS)
    t_val = ensure_text_dimensions(reducer.transform(clean_val), TEXT_VECTOR_DIMENSIONS)
    t_test = ensure_text_dimensions(reducer.transform(clean_test), TEXT_VECTOR_DIMENSIONS)

    normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path)
    m_train = normalizer.fit_transform(split_data.train.to_dict(orient="records"))
    m_val = normalizer.transform(split_data.validation.to_dict(orient="records"))
    m_test = normalizer.transform(split_data.test.to_dict(orient="records"))

    tw = float(best_candidate["text_weight"])
    mw = float(best_candidate["metadata_weight"])

    X_train = fuse_coordinate_batches(t_train * tw, m_train * mw)
    X_val = fuse_coordinate_batches(t_val * tw, m_val * mw)
    X_test = fuse_coordinate_batches(t_test * tw, m_test * mw)

    y_train = split_data.train["target_rate"].to_numpy(dtype=float)
    y_val = split_data.validation["target_rate"].to_numpy(dtype=float)
    y_test = split_data.test["target_rate"].to_numpy(dtype=float)

    # Domain Partitioned KDTree
    k_opt = int(best_candidate["k_neighbors"])
    eps_opt = float(best_candidate["idw_epsilon"])
    min_part = int(best_candidate["minimum_partition_size"])
    allow_fallback = bool(best_candidate["allow_fallback"])

    indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=min_part)
    indexer.fit(
        hybrid_vectors=X_train,
        industry_partitions=split_data.train["industry_partition"].tolist(),
        record_indices=np.asarray(split_data.train["record_id"].to_numpy(), dtype=int).tolist(),
        verified_rates=y_train.tolist(),
    )

    # Save fitted model components
    reducer.save_artifacts(artifact_dir)
    normalizer.save_artifacts(artifact_dir)
    indexer.save_artifacts(artifact_dir)

    # Copy bundled macro lookup
    bundled_macro = os.path.join(artifact_dir, DEFAULT_BUNDLED_MACRO_LOOKUP)
    if os.path.abspath(macro_lookup_path) != os.path.abspath(bundled_macro):
        shutil.copyfile(macro_lookup_path, bundled_macro)

    # Density mapping
    frame = pd.concat([split_data.train, split_data.validation, split_data.test], axis=0)
    density_by_partition = {
        str(partition): float(values.median())
        for partition, values in frame.groupby("industry_partition")["industry_relative_density"]
    }

    inference_config = {
        "version": 1,
        "text_dimensions": TEXT_VECTOR_DIMENSIONS,
        "metadata_features": list(DEFAULT_FEATURE_NAMES),
        "k_neighbors": k_opt,
        "idw_epsilon": eps_opt,
        "text_weight": tw,
        "metadata_weight": mw,
        "minimum_partition_size": indexer.minimum_partition_size,
        "fallback_partition": indexer.fallback_partition,
        "allow_fallback": allow_fallback,
        "partition_density": density_by_partition,
    }

    config_path = os.path.join(artifact_dir, DEFAULT_INFERENCE_CONFIG_ARTIFACT)
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(inference_config, handle, indent=2, sort_keys=True)

    # Predictions
    frozen_indexer = DomainPartitionedKDTreeIndexer.load_artifacts(artifact_dir)
    val_preds = _predict_idw(
        frozen_indexer,
        X_val,
        split_data.validation["industry_partition"].tolist(),
        k_neighbors=k_opt,
        allow_fallback=allow_fallback,
        epsilon=eps_opt,
    )
    test_preds = _predict_idw(
        frozen_indexer,
        X_test,
        split_data.test["industry_partition"].tolist(),
        k_neighbors=k_opt,
        allow_fallback=allow_fallback,
        epsilon=eps_opt,
    )

    val_metrics = _metric_summary(y_val, val_preds)
    test_metrics = _metric_summary(y_test, test_preds)

    # Baseline comparison
    means, global_mean = _build_category_mean_baseline(split_data.train)
    b_val_preds = _predict_category_mean_baseline(split_data.validation, means, global_mean)
    b_test_preds = _predict_category_mean_baseline(split_data.test, means, global_mean)
    baseline_val = _metric_summary(y_val, b_val_preds)
    baseline_test = _metric_summary(y_test, b_test_preds)

    outperforms = bool(
        val_metrics["rmse"] < baseline_val["rmse"]
        and val_metrics["r2"] > baseline_val["r2"]
        and test_metrics["rmse"] < baseline_test["rmse"]
        and test_metrics["r2"] > baseline_test["r2"]
    )

    with open(harmonized_parquet_path, "rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()

    training_summary = {
        "evaluation_protocol": "stratified_random_pca_random_search",
        "validation_status": "exploratory_random_search_optimal",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_rows": int(len(frame)),
        "split_rows": {
            "train": int(len(split_data.train)),
            "validation": int(len(split_data.validation)),
            "test": int(len(split_data.test)),
        },
        "model_metrics": {
            "validation": val_metrics,
            "test": test_metrics,
        },
        "baseline_metrics": {
            "validation": baseline_val,
            "test": baseline_test,
        },
        "baseline_comparison": {
            "model_outperforms_baseline": outperforms,
        },
        "optimal_hyperparameters": {
            "k_neighbors": k_opt,
            "idw_epsilon": eps_opt,
            "text_weight": tw,
            "metadata_weight": mw,
            "n_components": TEXT_VECTOR_DIMENSIONS,
            "max_features": int(best_candidate["max_features"]),
            "ngram_range": str(best_candidate["ngram_range"]),
            "min_df": int(best_candidate["min_df"]),
            "sublinear_tf": bool(best_candidate["sublinear_tf"]),
            "tfidf_norm": str(best_candidate["tfidf_norm"]),
            "normalize_output": bool(best_candidate["normalize_output"]),
            "minimum_partition_size": min_part,
            "allow_fallback": allow_fallback,
            "random_state": random_state,
        },
        "artifact_dir": artifact_dir,
        "dataset_sha256": digest,
    }

    summary_path = os.path.join(artifact_dir, DEFAULT_TRAINING_SUMMARY_ARTIFACT)
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(training_summary, handle, indent=2, sort_keys=True)

    # Write Manifest
    write_manifest(
        artifact_dir,
        inference_config,
        dataset_version=f"sha256:{digest[:12]}",
        source_type="harmonized KES/hour proxy labels; not verified mentor transactions",
        split_policy=f"stratified_random_seed_{random_state}; exploratory, not OOT",
        dataset_sha256=digest,
    )

    print(f"Artifacts successfully written to '{artifact_dir}/':")
    for fname in sorted(os.listdir(artifact_dir)):
        fpath = os.path.join(artifact_dir, fname)
        size_kb = os.path.getsize(fpath) / 1024.0
        print(f"  - {fname:35s} ({size_kb:8.1f} KB)")

    return training_summary


def verify_inference_runtime_loads(artifact_dir: str = "artifacts") -> None:
    """Verify that InferenceRuntime can load the serialized bundle without errors."""
    print("\n" + "=" * 70)
    print("STEP 6: Verifying Serving InferenceRuntime Loads the Artifact Bundle")
    print("=" * 70)
    from src.api.serve import InferenceRuntime

    tariff_csv = "config/tariffs/mpesa_p2p_users_2026-08-04.csv"
    if not os.path.isfile(tariff_csv):
        tariff_csv = "tests/fixtures/raw/Mpesa_Tarrifs/tarrifs_full_schedule.csv"

    macro_path = os.path.join(artifact_dir, DEFAULT_BUNDLED_MACRO_LOOKUP)
    manifest_path = os.path.join(artifact_dir, MANIFEST_NAME)
    manifest_sha = file_sha256(manifest_path)

    runtime = InferenceRuntime(
        artifact_dir=artifact_dir,
        macro_lookup_path=macro_path,
        tariff_csv_path=tariff_csv,
        trusted_manifest_sha256=manifest_sha,
    )
    runtime.load()

    assert runtime.models_loaded, f"Runtime failed to load models: {runtime.load_error}"
    print("SUCCESS: InferenceRuntime loaded models cleanly!")
    print(f"  - Text Reducer:      {type(runtime.reducer).__name__}")
    print(f"  - Metadata Normalizer: {type(runtime.metadata_normalizer).__name__}")
    print(f"  - Spatial Indexer:    {type(runtime.spatial_indexer).__name__}")
    print(f"  - Tariff Evaluator:   {type(runtime.tariff_evaluator).__name__}")
    print(f"  - Manifest Digest:    {manifest_sha[:16]}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize and train price model using PCA and Random Search.")
    parser.add_argument("--trials", type=int, default=40, help="Number of random search trials.")
    parser.add_argument("--artifact-dir", default="artifacts", help="Destination directory for production artifacts.")
    parser.add_argument("--report-dir", default="reports", help="Destination directory for reports.")
    parser.add_argument("--random-state", type=int, default=42, help="Random state seed.")
    args = parser.parse_args()

    os.makedirs(args.report_dir, exist_ok=True)
    harmonized_parquet = DEFAULT_HARMONIZED_PARQUET
    macro_lookup = os.path.join("data", "processed", "macro_lookup_table.json")

    # 1. Run Random Search & PCA Scree
    search_results, best_candidate, split_data = run_random_search_optimization(
        harmonized_parquet_path=harmonized_parquet,
        macro_lookup_path=macro_lookup,
        n_trials=args.trials,
        random_state=args.random_state,
    )

    # 2. Benchmark model families on the optimal PCA representation
    model_benchmarks = benchmark_model_families_on_pca_features(
        split_data=split_data,
        best_candidate=best_candidate,
        macro_lookup_path=macro_lookup,
        random_state=args.random_state,
    )

    # 3. Train and export final production model
    final_summary = train_and_export_optimal_production_model(
        split_data=split_data,
        best_candidate=best_candidate,
        macro_lookup_path=macro_lookup,
        harmonized_parquet_path=harmonized_parquet,
        artifact_dir=args.artifact_dir,
        random_state=args.random_state,
    )

    # 4. Verify InferenceRuntime
    verify_inference_runtime_loads(args.artifact_dir)

    # 5. Persist comprehensive report
    report_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "n_trials": args.trials,
        "best_candidate": best_candidate,
        "search_results": search_results,
        "model_benchmarks": model_benchmarks,
        "production_training_summary": final_summary,
    }
    report_file = os.path.join(args.report_dir, "pca_random_search_findings.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, default=str)
    print(f"\nComprehensive report written to: {report_file}")
    print("\nDONE!")


if __name__ == "__main__":
    main()
