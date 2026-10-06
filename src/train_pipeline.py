"""Train, evaluate, and publish the hybrid peer-pricing artifacts.

The stratified evaluation path makes reproducible industry-stratified random
train/validation/test splits (70/15/15). ``--mode oot`` is a separate,
opt-in chronological protocol requiring source observation timestamps and a
prespecified cutoff. Text vocabulary/SVD, the metadata scaler, and the peer
index are fitted from training rows; held-out rows are transformed with those
frozen fits. The target is harmonized KES/hour built from marketplace job
budgets and profile asking rates, not verified mentor transactions.

Exports contain fitted inference artifacts, configuration, training summary,
and a manifest with file/input hashes and split provenance. A manifest hash is
not self-authenticating: deployment must compare it with an independently
trusted pin and fails closed on missing or mismatched trust evidence. The OOT
path stages fitted files and publishes them only after its software gate
succeeds; that gate and exploratory reports do not establish empirical mentor
accuracy or pass the deferred #81/#91 mentor-pricing gate. See
``../README.md#how-a-price-is-calculated`` and
``../README.md#what-runs-today``,
``../docs/experiments/README.md``, and
``../docs/Label_Provenance_Audit_91.md``.
"""

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, cast

try:
    import numpy as np
    import pandas as pd
    from sklearn.metrics import mean_absolute_error, median_absolute_error, mean_squared_error, r2_score
    from sklearn.model_selection import train_test_split
except ImportError as exc:
    raise RuntimeError("Missing training-pipeline dependencies. Install from requirements.txt") from exc

from src.ingest_multisource import (
    BILATERAL_ALPHA,
    build_harmonized_marketplace_records,
    build_macro_lookup,
    export_harmonized_records_parquet,
)
from src.macro_arbitrage import (
    DEFAULT_MACRO_LOOKUP,
    DEFAULT_FEATURE_NAMES,
    DEFAULT_INFERENCE_CONFIG_ARTIFACT,
    DEFAULT_BUNDLED_MACRO_LOOKUP,
    METADATA_VECTOR_DIMENSIONS,
    TEXT_VECTOR_DIMENSIONS,
    ContinuousMetadataNormalizer,
    fuse_coordinate_batches,
)
from src.nlp_pipeline import TextFeatureReducer, ensure_text_dimensions
from src.artifact_contract import write_manifest
from src.oot_gate import validate_oot_report
from src.repository import FirestoreRepository, Repository
from src.spatial_engine import DEFAULT_IDW_EPSILON, DEFAULT_MIN_PARTITION_SIZE, DomainPartitionedKDTreeIndexer

DEFAULT_HARMONIZED_PARQUET = os.path.join("data", "processed", "harmonized_marketplace_corpus.parquet")
DEFAULT_ARTIFACT_DIR = "artifacts"
DEFAULT_RANDOM_STATE = 42
DEFAULT_TRAINING_SUMMARY_ARTIFACT = "training_summary.json"
DEFAULT_IDW_NEIGHBORS = 5
DEFAULT_QUALITY_GATE_R2 = 0.75
OOT_TIMESTAMP_COLUMN = "observation_timestamp_utc"
OOT_RATE_MIN = 500.0
OOT_RATE_MAX = 35000.0

REQUIRED_COLUMNS = (
    "raw_description",
    "industry_partition",
    "bilateral_arbitrage_factor",
    "market_saturation_score",
    "industry_relative_density",
)


@dataclass(frozen=True)
class SplitData:
    """Three named row partitions consumed by feature fitting and evaluation."""

    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


@dataclass(frozen=True)
class TrainingMatrices:
    """Fixed-schema feature matrices and aligned KES/hour labels for each split."""

    x_train: np.ndarray
    x_validation: np.ndarray
    x_test: np.ndarray
    y_train: np.ndarray
    y_validation: np.ndarray
    y_test: np.ndarray


def load_harmonized_parquet(parquet_path: str) -> pd.DataFrame:
    """Load and validate the harmonized corpus, assigning stable row indices."""
    frame = pd.read_parquet(parquet_path)
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Harmonized parquet is missing required columns: {missing}")

    if "target_rate" not in frame.columns:
        if "harmonized_hourly_rate" in frame.columns:
            frame = frame.copy()
            frame["target_rate"] = frame["harmonized_hourly_rate"].astype(float)
        elif "hourly_rate" in frame.columns:
            frame = frame.copy()
            frame["target_rate"] = frame["hourly_rate"].astype(float)
        else:
            raise ValueError("Harmonized parquet must include either 'harmonized_hourly_rate' or 'hourly_rate'.")

    frame = frame.copy()
    frame["record_id"] = np.arange(len(frame), dtype=int)
    frame["industry_partition"] = frame["industry_partition"].astype(str).str.strip().str.lower()
    frame["raw_description"] = frame["raw_description"].astype(str)
    if "listing_id" in frame.columns:
        ids = frame["listing_id"].dropna()
        if ids.duplicated().any():
            raise ValueError("listing_id must be unique across the source snapshot")
    if frame.empty:
        raise ValueError("Harmonized parquet cannot be empty.")
    return frame


def _verified_listing_provenance(
    train: pd.DataFrame, rates: np.ndarray, repository: Optional[Repository],
    reducer: Optional[TextFeatureReducer] = None,
) -> Tuple[Optional[List[Optional[str]]], Optional[List[Optional[str]]]]:
    """Bind only training rows explicitly linked to their actual root listings."""
    if "listing_id" not in train.columns:
        return None, None
    expected_vectors = (ensure_text_dimensions(reducer.transform(train["raw_description"].tolist()))
                        if reducer is not None else None)
    ids: List[Optional[str]] = []
    titles: List[Optional[str]] = []
    for position, (row, rate) in enumerate(zip(train.to_dict(orient="records"), rates.tolist())):
        listing_id = row["listing_id"]
        if pd.isna(listing_id):
            ids.append(None)
            titles.append(None)
            continue
        if not isinstance(listing_id, str) or not listing_id or listing_id != listing_id.strip():
            raise ValueError("Invalid listing_id in training snapshot")
        if repository is None:
            raise ValueError("A listing repository is required to verify listing_id provenance")
        listing = repository.get_listing(listing_id)
        if listing is None or not listing["is_active"]:
            raise ValueError("Missing or inactive root service listing in training snapshot")
        if (listing["industry_id"] != row["industry_partition"]
                or listing["raw_description"] != row["raw_description"]
                or not np.isclose(listing["verified_rate"], rate, rtol=0, atol=0.005)
                or ("job_title" in row and listing["title"] != row["job_title"])):
            raise ValueError("Training peer does not match stored root service listing")
        if expected_vectors is not None and not np.allclose(
                listing["latent_svd_vector"], expected_vectors[position], rtol=0, atol=1e-6):
            raise ValueError("Root service listing SVD vector does not match fitted reducer")
        ids.append(listing_id)
        titles.append(listing["title"])
    return ids, titles


def _validate_split_ratios(train_ratio: float, validation_ratio: float, test_ratio: float) -> None:
    total = float(train_ratio + validation_ratio + test_ratio)
    if abs(total - 1.0) > 1e-9:
        raise ValueError("Split ratios must sum to 1.0.")
    if min(train_ratio, validation_ratio, test_ratio) <= 0.0:
        raise ValueError("Each split ratio must be greater than 0.")


def _can_stratify(labels: pd.Series) -> bool:
    counts = labels.value_counts()
    return bool(not counts.empty and counts.min() >= 2)


def build_stratified_splits(
    frame: pd.DataFrame,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> SplitData:
    """Split rows randomly at the requested ratios, stratifying by industry.

    This historical exploratory split is not chronological out-of-time (OOT)
    evidence; use :func:`build_chronological_splits` for that separate protocol.
    """
    _validate_split_ratios(train_ratio, validation_ratio, test_ratio)

    labels = frame["industry_partition"]
    stratify_main = labels if _can_stratify(labels) else None

    train_frame, temp_frame = train_test_split(
        frame,
        train_size=train_ratio,
        random_state=random_state,
        stratify=stratify_main,
    )

    validation_fraction_of_temp = validation_ratio / (validation_ratio + test_ratio)
    temp_labels = temp_frame["industry_partition"]
    stratify_temp = temp_labels if _can_stratify(temp_labels) else None

    validation_frame, test_frame = train_test_split(
        temp_frame,
        train_size=validation_fraction_of_temp,
        random_state=random_state,
        stratify=stratify_temp,
    )

    return SplitData(
        train=train_frame.sort_values("record_id").reset_index(drop=True),
        validation=validation_frame.sort_values("record_id").reset_index(drop=True),
        test=test_frame.sort_values("record_id").reset_index(drop=True),
    )


def build_chronological_splits(frame: pd.DataFrame, cutoff: str) -> SplitData:
    """Split on a prespecified timezone-aware source time, with strict future test.

    All rows through the UTC cutoff are historical training data, and only
    later rows are held out. The validation slot aliases the future test for
    compatibility with common feature fitting; neither is used to fit.
    """
    if OOT_TIMESTAMP_COLUMN not in frame.columns:
        raise ValueError(f"Missing {OOT_TIMESTAMP_COLUMN}; source observation times are required for OOT training.")
    try:
        boundary = pd.Timestamp(cutoff)
    except (TypeError, ValueError) as exc:
        raise ValueError("OOT cutoff must be an ISO-8601 timezone-aware timestamp.") from exc
    if pd.isna(boundary) or boundary.tzinfo is None:
        raise ValueError("OOT cutoff must be an ISO-8601 timezone-aware timestamp.")
    times = frame[OOT_TIMESTAMP_COLUMN]
    if times.isna().any():
        raise ValueError("Missing observation timestamps; do not substitute ingestion or export times.")
    try:
        parsed = times.map(lambda value: pd.Timestamp(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid observation timestamps in OOT input.") from exc
    if parsed.map(lambda value: pd.isna(value) or value.tzinfo is None).any():
        raise ValueError("Observation timestamps must all be timezone-aware; no inferred dates allowed.")
    normalized = pd.to_datetime(parsed, utc=True)
    frame = frame.copy()
    frame[OOT_TIMESTAMP_COLUMN] = normalized
    boundary = boundary.tz_convert("UTC")
    train = frame.loc[normalized <= boundary].sort_values([OOT_TIMESTAMP_COLUMN, "record_id"]).reset_index(drop=True)
    test = frame.loc[normalized > boundary].sort_values([OOT_TIMESTAMP_COLUMN, "record_id"]).reset_index(drop=True)
    if len(train) < 2 or len(test) < 2:
        raise ValueError("OOT requires at least two historical and two strictly later eligible records.")
    # The common feature fitter transforms both held-out slots, but fits ONLY train.
    return SplitData(train=train, validation=test, test=test)


def _oot_train_derived_metadata(split: SplitData) -> SplitData:
    """Derive saturation and density for every split from training counts only."""
    counts = split.train["industry_partition"].value_counts()
    total = len(split.train)
    maximum = int(counts.max())

    def transform(frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()
        frequency = result["industry_partition"].map(counts).fillna(0).astype(int)
        result["industry_frequency"] = frequency
        result["market_saturation_score"] = (frequency / total).round(6)
        result["industry_relative_density"] = (frequency / maximum).round(6)
        return result

    return SplitData(train=transform(split.train), validation=transform(split.validation), test=transform(split.test))


def evaluate_chronological_oot(
    harmonized_parquet_path: str,
    macro_lookup_path: str,
    cutoff: str,
    artifact_dir: str = DEFAULT_ARTIFACT_DIR,
    dataset_version: str = "",
    listing_repository: Optional[Repository] = None,
) -> Dict[str, Any]:
    """Evaluate a strictly future proxy-label holdout and publish only on gate pass.

    Requires timestamped source records, an immutable dataset version, and an
    empty output directory. Feature fits use training data only; failed score
    or chronology checks leave fitted models unpublished. The gate is an
    engineering/report check on harmonized KES/hour proxy labels, not evidence
    of mentor-price accuracy or completion of deferred empirical gate #81/#91.
    Successful reports record the input SHA-256 and protocol.
    """
    if not dataset_version.strip():
        raise ValueError("Provide an immutable dataset_version for chronological OOT provenance.")
    if os.path.exists(artifact_dir) and os.listdir(artifact_dir):
        raise ValueError("OOT artifact_dir must be empty; use a fresh directory to avoid stale deployable models.")
    frame = load_harmonized_parquet(harmonized_parquet_path)
    if OOT_TIMESTAMP_COLUMN not in frame.columns:
        raise ValueError(f"Missing {OOT_TIMESTAMP_COLUMN}; current parquet cannot support chronological OOT.")
    if "harmonized_hourly_rate" not in frame.columns:
        raise ValueError("OOT requires harmonized_hourly_rate (KES/hour); do not use raw or unverified target_rate.")
    if frame[OOT_TIMESTAMP_COLUMN].isna().any():
        raise ValueError("Missing observation timestamps; do not substitute ingestion or export times.")
    rates = pd.Series(pd.to_numeric(frame["harmonized_hourly_rate"].to_numpy(), errors="coerce"), index=frame.index)
    eligible = cast(pd.Series, rates.notna() & rates.ge(OOT_RATE_MIN) & rates.le(OOT_RATE_MAX))
    frame = frame.loc[eligible].copy()
    frame["target_rate"] = rates.loc[eligible]
    split = _oot_train_derived_metadata(build_chronological_splits(frame, cutoff))
    train_end = split.train[OOT_TIMESTAMP_COLUMN].max()
    test_start = split.test[OOT_TIMESTAMP_COLUMN].min()
    train_rates = split.train["target_rate"].to_numpy(dtype=float)
    q1, q3 = np.percentile(train_rates, [25, 75])
    iqr = q3 - q1
    with open(harmonized_parquet_path, "rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()

    # Stage all fitted files outside the final export. Failed gates never publish models.
    with tempfile.TemporaryDirectory() as staged:
        matrices = _fit_feature_matrices(split, macro_lookup_path, artifact_dir=staged)
        has_listings = "listing_id" in split.train.columns and split.train["listing_id"].notna().any()
        listing_ids, job_titles = _verified_listing_provenance(
            split.train, matrices.y_train, listing_repository,
            TextFeatureReducer.load_artifacts(staged) if has_listings else None)
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=DEFAULT_MIN_PARTITION_SIZE)
        indexer.fit(
            hybrid_vectors=matrices.x_train,
            industry_partitions=split.train["industry_partition"].tolist(),
            record_indices=split.train["record_id"].tolist(),
            verified_rates=matrices.y_train.tolist(),
            listing_ids=listing_ids, job_titles=job_titles,
        )
        indexer.save_artifacts(staged)
        shutil.copyfile(macro_lookup_path, os.path.join(staged, DEFAULT_BUNDLED_MACRO_LOOKUP))
        config = {
            "version": 1,
            "text_dimensions": TEXT_VECTOR_DIMENSIONS,
            "metadata_features": list(DEFAULT_FEATURE_NAMES),
            "k_neighbors": DEFAULT_IDW_NEIGHBORS,
            "idw_epsilon": DEFAULT_IDW_EPSILON,
            "text_weight": 1.0,
            "metadata_weight": 1.0,
            "minimum_partition_size": indexer.minimum_partition_size,
            "fallback_partition": indexer.fallback_partition,
            "allow_fallback": True,
            "partition_density": {
                str(partition): float(values.median())
                for partition, values in split.train.groupby("industry_partition")["industry_relative_density"]
            },
        }
        with open(os.path.join(staged, DEFAULT_INFERENCE_CONFIG_ARTIFACT), "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2, sort_keys=True)
        frozen = DomainPartitionedKDTreeIndexer.load_artifacts(staged)
        predictions = _predict_idw(
            frozen, matrices.x_test, split.test["industry_partition"].tolist(), DEFAULT_IDW_NEIGHBORS,
            epsilon=DEFAULT_IDW_EPSILON,
        )
        if not np.isfinite(predictions).all() or np.var(matrices.y_test) == 0:
            raise ValueError("OOT holdout has non-finite predictions or constant labels; R2 is undefined.")
        metrics = _metric_summary(matrices.y_test, predictions)
        metrics["r2"] = float(r2_score(matrices.y_test, predictions))  # Do not round across the quality threshold.
        report = {
            "evaluation_protocol": "chronological_out_of_time",
            "dataset_version": dataset_version,
            "dataset_sha256": digest,
            "label_provenance": "harmonized KES/hour proxy labels; not verified mentor transactions",
            "rate_policy": {
                "target_kes_per_hour_min": OOT_RATE_MIN,
                "target_kes_per_hour_max": OOT_RATE_MAX,
                "excluded_out_of_bounds_or_invalid": int(len(eligible) - eligible.sum()),
                "iqr_policy": "diagnostic only; no holdout-dependent exclusions",
                "train_iqr_lower": float(q1 - 1.5 * iqr),
                "train_iqr_upper": float(q3 + 1.5 * iqr),
            },
            "time_cutoff": pd.Timestamp(cutoff).tz_convert("UTC").isoformat(),
            "train_end": train_end.isoformat(),
            "test_start": test_start.isoformat(),
            "split_rows": {"train": len(split.train), "test": len(split.test)},
            "test": metrics,
            "quality_gate": {"metric": "test_r2", "threshold": DEFAULT_QUALITY_GATE_R2,
                             "passed": bool(metrics["r2"] >= DEFAULT_QUALITY_GATE_R2)},
        }
        os.makedirs(artifact_dir, exist_ok=True)
        summary_path = os.path.join(artifact_dir, DEFAULT_TRAINING_SUMMARY_ARTIFACT)
        with open(summary_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
        # The gate checks the held-out score and strict timestamp ordering.
        try:
            validate_oot_report(report)
        except ValueError as exc:
            raise RuntimeError(f"Quality gate failed: {exc}; inspect {summary_path} and acquire reliable labels/timestamps.") from exc
        for name in os.listdir(staged):
            shutil.move(os.path.join(staged, name), os.path.join(artifact_dir, name))
        write_manifest(artifact_dir, config, dataset_version=dataset_version,
                       source_type="harmonized KES/hour proxy labels; not verified mentor transactions",
                       split_policy="chronological_out_of_time", dataset_sha256=digest)
        return report


def _ensure_text_dimensions(matrix: np.ndarray, expected_dimensions: int = TEXT_VECTOR_DIMENSIONS) -> np.ndarray:
    return ensure_text_dimensions(matrix, expected_dimensions)


def _fit_feature_matrices(
    split_data: SplitData,
    macro_lookup_path: str,
    n_components: int = TEXT_VECTOR_DIMENSIONS,
    max_features: int = 12000,
    alpha: float = BILATERAL_ALPHA,
    artifact_dir: str = DEFAULT_ARTIFACT_DIR,
    save_artifacts: bool = True,
    text_weight: float = 1.0,
    metadata_weight: float = 1.0,
) -> TrainingMatrices:
    """Fit transforms only on train rows, then return aligned (N, 53) matrices.

    Validation/test reuse the vocabulary, SVD and scaler so their text/extrema
    cannot influence fitting. Target arrays are separate KES/hour labels, never
    feature columns. Persistent serving exports require 50 requested text axes.
    """
    if not np.isfinite(float(text_weight)) or float(text_weight) < 0.0:
        raise ValueError("text_weight must be finite and non-negative.")
    if not np.isfinite(float(metadata_weight)) or float(metadata_weight) < 0.0:
        raise ValueError("metadata_weight must be finite and non-negative.")
    if n_components != TEXT_VECTOR_DIMENSIONS and save_artifacts:
        raise ValueError("Production artifacts require a 50-component text reducer.")
    train_texts = [str(value) for value in split_data.train["raw_description"].tolist()]
    validation_texts = [str(value) for value in split_data.validation["raw_description"].tolist()]
    test_texts = [str(value) for value in split_data.test["raw_description"].tolist()]

    train_records = cast(List[Dict[str, Any]], split_data.train.to_dict(orient="records"))
    validation_records = cast(List[Dict[str, Any]], split_data.validation.to_dict(orient="records"))
    test_records = cast(List[Dict[str, Any]], split_data.test.to_dict(orient="records"))

    reducer = TextFeatureReducer(n_components=n_components, max_features=max_features)
    train_text = _ensure_text_dimensions(reducer.fit_transform(train_texts))
    validation_text = _ensure_text_dimensions(reducer.transform(validation_texts))
    test_text = _ensure_text_dimensions(reducer.transform(test_texts))

    normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path, alpha=alpha)
    train_meta = normalizer.fit_transform(train_records)
    validation_meta = normalizer.transform(validation_records)
    test_meta = normalizer.transform(test_records)

    if train_meta.shape[1] != METADATA_VECTOR_DIMENSIONS:
        raise ValueError(
            f"Metadata vector dimensionality mismatch: expected {METADATA_VECTOR_DIMENSIONS}, got {train_meta.shape[1]}"
        )

    x_train = fuse_coordinate_batches(train_text * float(text_weight), train_meta * float(metadata_weight))
    x_validation = fuse_coordinate_batches(validation_text * float(text_weight), validation_meta * float(metadata_weight))
    x_test = fuse_coordinate_batches(test_text * float(text_weight), test_meta * float(metadata_weight))

    y_train = split_data.train["target_rate"].to_numpy(dtype=float)
    y_validation = split_data.validation["target_rate"].to_numpy(dtype=float)
    y_test = split_data.test["target_rate"].to_numpy(dtype=float)

    if save_artifacts:
        os.makedirs(artifact_dir, exist_ok=True)
        reducer.save_artifacts(artifact_dir)
        normalizer.save_artifacts(artifact_dir)

    return TrainingMatrices(
        x_train=x_train,
        x_validation=x_validation,
        x_test=x_test,
        y_train=y_train,
        y_validation=y_validation,
        y_test=y_test,
    )


def _distribution(frame: pd.DataFrame) -> Dict[str, float]:
    counts = Counter(frame["industry_partition"].tolist())
    total = max(1, len(frame))
    return {key: round(value / total, 6) for key, value in sorted(counts.items())}


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(mean_squared_error(y_true, y_pred) ** 0.5)


def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    denominator = np.abs(actual) + np.abs(predicted)
    numerator = 2.0 * np.abs(predicted - actual)
    values = np.divide(numerator, denominator, out=np.zeros_like(numerator), where=denominator > 0.0)
    return float(np.mean(values) * 100.0)


def transform_target_log1p(target: np.ndarray) -> np.ndarray:
    """Apply the optional non-negative ``log1p`` target transform."""
    values = np.asarray(target, dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("Target contains non-finite values.")
    if np.any(values < 0.0):
        raise ValueError("log1p target transformation requires non-negative target values.")
    return np.log1p(values)


def inverse_target_log1p(target_log: np.ndarray) -> np.ndarray:
    """Map log1p-scale predictions back to non-negative raw target units."""
    values = np.asarray(target_log, dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("Log-transformed target contains non-finite values.")
    return np.maximum(0.0, np.expm1(values))


def _metric_summary(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Summarize label error: MAE/RMSE/median in target units, sMAPE in percent.

    Raw targets use KES/hour; optional log-space comparisons use log1p units.
    R2 is dimensionless fit relative to a mean predictor and may be negative;
    none of these proxy-label scores establishes verified mentor-price accuracy.
    """
    return {
        "rmse": round(_rmse(y_true, y_pred), 6),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 6),
        "median_absolute_error": round(float(median_absolute_error(y_true, y_pred)), 6),
        "smape_percent": round(_smape(y_true, y_pred), 6),
        "r2": round(float(r2_score(y_true, y_pred)), 6),
    }


def _build_category_mean_baseline(train_frame: pd.DataFrame) -> Tuple[Dict[str, float], float]:
    grouped = train_frame.groupby("industry_partition")["target_rate"].mean()
    means = {str(k): float(v) for k, v in grouped.to_dict().items()}
    global_mean = float(train_frame["target_rate"].mean())
    return means, global_mean


def _predict_category_mean_baseline(
    frame: pd.DataFrame,
    partition_means: Dict[str, float],
    global_mean: float,
) -> np.ndarray:
    return np.array(
        [float(partition_means.get(str(partition), global_mean)) for partition in frame["industry_partition"].tolist()],
        dtype=float,
    )


def _predict_idw(
    indexer: DomainPartitionedKDTreeIndexer,
    feature_matrix: np.ndarray,
    partitions: List[str],
    k_neighbors: int,
    allow_fallback: bool = True,
    epsilon: float = DEFAULT_IDW_EPSILON,
) -> np.ndarray:
    predictions: List[float] = []
    for row_number, partition in enumerate(partitions):
        prediction = indexer.predict_base_rate(
            query_vector=feature_matrix[row_number],
            requested_partition=partition,
            k=k_neighbors,
            allow_fallback=allow_fallback,
            epsilon=epsilon,
        )
        predictions.append(float(prediction["base_predicted_rate"]))
    return np.asarray(predictions, dtype=float)


def orchestrate_training(
    harmonized_parquet_path: str,
    macro_lookup_path: str,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_state: int = DEFAULT_RANDOM_STATE,
    n_components: int = TEXT_VECTOR_DIMENSIONS,
    max_features: int = 12000,
    alpha: float = BILATERAL_ALPHA,
    artifact_dir: str = DEFAULT_ARTIFACT_DIR,
    save_artifacts: bool = True,
    text_weight: float = 1.0,
    metadata_weight: float = 1.0,
) -> Dict[str, Any]:
    """Build the stratified splits and report feature shapes and split counts."""
    frame = load_harmonized_parquet(harmonized_parquet_path)
    split_data = build_stratified_splits(
        frame,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        test_ratio=test_ratio,
        random_state=random_state,
    )

    split_ids = {
        "train": set(split_data.train["record_id"].tolist()),
        "validation": set(split_data.validation["record_id"].tolist()),
        "test": set(split_data.test["record_id"].tolist()),
    }
    has_overlap = bool(
        (split_ids["train"] & split_ids["validation"])
        or (split_ids["train"] & split_ids["test"])
        or (split_ids["validation"] & split_ids["test"])
    )

    matrices = _fit_feature_matrices(
        split_data=split_data,
        macro_lookup_path=macro_lookup_path,
        n_components=n_components,
        max_features=max_features,
        alpha=alpha,
        artifact_dir=artifact_dir,
        save_artifacts=save_artifacts,
        text_weight=text_weight,
        metadata_weight=metadata_weight,
    )

    return {
        "input_rows": int(len(frame)),
        "split_rows": {
            "train": int(len(split_data.train)),
            "validation": int(len(split_data.validation)),
            "test": int(len(split_data.test)),
        },
        "split_distributions": {
            "train": _distribution(split_data.train),
            "validation": _distribution(split_data.validation),
            "test": _distribution(split_data.test),
        },
        "has_split_overlap": has_overlap,
        "feature_shapes": {
            "x_train": [int(v) for v in matrices.x_train.shape],
            "x_validation": [int(v) for v in matrices.x_validation.shape],
            "x_test": [int(v) for v in matrices.x_test.shape],
            "y_train": int(matrices.y_train.shape[0]),
            "y_validation": int(matrices.y_validation.shape[0]),
            "y_test": int(matrices.y_test.shape[0]),
        },
        "artifact_dir": artifact_dir if save_artifacts else None,
        "runtime_tuning": {
            "text_weight": float(text_weight),
            "metadata_weight": float(metadata_weight),
        },
    }


def evaluate_and_serialize_training(
    harmonized_parquet_path: str,
    macro_lookup_path: str,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
    random_state: int = DEFAULT_RANDOM_STATE,
    n_components: int = TEXT_VECTOR_DIMENSIONS,
    max_features: int = 12000,
    alpha: float = BILATERAL_ALPHA,
    artifact_dir: str = DEFAULT_ARTIFACT_DIR,
    k_neighbors: int = DEFAULT_IDW_NEIGHBORS,
    quality_gate_r2: float = DEFAULT_QUALITY_GATE_R2,
    enforce_quality_gate: bool = True,
    text_weight: float = 1.0,
    metadata_weight: float = 1.0,
    minimum_partition_size: int = DEFAULT_MIN_PARTITION_SIZE,
    idw_epsilon: float = DEFAULT_IDW_EPSILON,
    allow_fallback: bool = True,
    dataset_version: str | None = None,
    listing_repository: Optional[Repository] = None,
) -> Dict[str, Any]:
    """Fit, evaluate, and export the stratified exploratory pricing pipeline.

    Vectorizers, SVD, metadata scaling, and the IDW index are fitted from the
    training partition; validation/test rows are transformed/scored separately.
    Labels and reported rates are KES/hour proxies, not verified mentor rates.
    The manifest records hashes and split/source provenance for downstream
    independent pinning; it does not itself establish artifact trust or empirical
    accuracy. In this stratified path, fitted files are written before the
    optional quality checks; a rejected run raises and does not write its final
    manifest. Do not publish or trust such an output directory. Unlike the OOT
    path, the stratified path does not stage model files atomically.
    """
    if n_components != TEXT_VECTOR_DIMENSIONS:
        raise ValueError("Production artifacts require a 50-component text reducer.")
    if int(k_neighbors) < 1 or not np.isfinite(idw_epsilon) or idw_epsilon <= 0:
        raise ValueError("KNN neighbors and IDW epsilon must be positive.")
    frame = load_harmonized_parquet(harmonized_parquet_path)
    split_data = build_stratified_splits(
        frame,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        test_ratio=test_ratio,
        random_state=random_state,
    )

    split_ids = {
        "train": set(split_data.train["record_id"].tolist()),
        "validation": set(split_data.validation["record_id"].tolist()),
        "test": set(split_data.test["record_id"].tolist()),
    }
    has_overlap = bool(
        (split_ids["train"] & split_ids["validation"])
        or (split_ids["train"] & split_ids["test"])
        or (split_ids["validation"] & split_ids["test"])
    )

    os.makedirs(artifact_dir, exist_ok=True)
    matrices = _fit_feature_matrices(
        split_data=split_data,
        macro_lookup_path=macro_lookup_path,
        n_components=n_components,
        max_features=max_features,
        alpha=alpha,
        artifact_dir=artifact_dir,
        save_artifacts=True,
        text_weight=text_weight,
        metadata_weight=metadata_weight,
    )

    idw_indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=minimum_partition_size)
    train_record_indices = np.asarray(split_data.train["record_id"].to_numpy(), dtype=int).tolist()
    has_listings = "listing_id" in split_data.train.columns and split_data.train["listing_id"].notna().any()
    listing_ids, job_titles = _verified_listing_provenance(
        split_data.train, matrices.y_train, listing_repository,
        TextFeatureReducer.load_artifacts(artifact_dir) if has_listings else None)
    idw_indexer.fit(
        hybrid_vectors=matrices.x_train,
        industry_partitions=[str(v) for v in split_data.train["industry_partition"].tolist()],
        record_indices=train_record_indices,
        verified_rates=matrices.y_train.tolist(),
        listing_ids=listing_ids, job_titles=job_titles,
    )
    idw_indexer.save_artifacts(artifact_dir)
    bundled_macro = os.path.join(artifact_dir, DEFAULT_BUNDLED_MACRO_LOOKUP)
    if os.path.abspath(macro_lookup_path) != os.path.abspath(bundled_macro):
        shutil.copyfile(macro_lookup_path, bundled_macro)
    density_by_partition = {
        str(partition): float(values.median())
        for partition, values in frame.groupby("industry_partition")["industry_relative_density"]
    }
    inference_config = {
        "version": 1,
        "text_dimensions": TEXT_VECTOR_DIMENSIONS,
        "metadata_features": list(DEFAULT_FEATURE_NAMES),
        "k_neighbors": int(k_neighbors),
        "idw_epsilon": float(idw_epsilon),
        "text_weight": float(text_weight),
        "metadata_weight": float(metadata_weight),
        "minimum_partition_size": idw_indexer.minimum_partition_size,
        "fallback_partition": idw_indexer.fallback_partition,
        "allow_fallback": bool(allow_fallback),
        "partition_density": density_by_partition,
    }
    with open(os.path.join(artifact_dir, DEFAULT_INFERENCE_CONFIG_ARTIFACT), "w", encoding="utf-8") as handle:
        json.dump(inference_config, handle, indent=2, sort_keys=True)

    frozen_indexer = DomainPartitionedKDTreeIndexer.load_artifacts(artifact_dir)
    validation_predictions = _predict_idw(
        frozen_indexer,
        matrices.x_validation,
        [str(v) for v in split_data.validation["industry_partition"].tolist()],
        k_neighbors=max(1, int(k_neighbors)),
        allow_fallback=allow_fallback,
        epsilon=idw_epsilon,
    )
    test_predictions = _predict_idw(
        frozen_indexer,
        matrices.x_test,
        [str(v) for v in split_data.test["industry_partition"].tolist()],
        k_neighbors=max(1, int(k_neighbors)),
        allow_fallback=allow_fallback,
        epsilon=idw_epsilon,
    )

    partition_means, global_mean = _build_category_mean_baseline(split_data.train)
    baseline_validation_predictions = _predict_category_mean_baseline(split_data.validation, partition_means, global_mean)
    baseline_test_predictions = _predict_category_mean_baseline(split_data.test, partition_means, global_mean)

    model_validation_metrics = _metric_summary(matrices.y_validation, validation_predictions)
    model_test_metrics = _metric_summary(matrices.y_test, test_predictions)
    baseline_validation_metrics = _metric_summary(matrices.y_validation, baseline_validation_predictions)
    baseline_test_metrics = _metric_summary(matrices.y_test, baseline_test_predictions)
    log_train_rates = transform_target_log1p(matrices.y_train)
    log_validation_rates = transform_target_log1p(matrices.y_validation)
    log_test_rates = transform_target_log1p(matrices.y_test)
    log_indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=1)
    log_indexer.fit(
        hybrid_vectors=matrices.x_train,
        industry_partitions=[str(v) for v in split_data.train["industry_partition"].tolist()],
        record_indices=train_record_indices,
        verified_rates=log_train_rates.tolist(),
    )
    log_validation_predictions = _predict_idw(
        log_indexer,
        matrices.x_validation,
        [str(v) for v in split_data.validation["industry_partition"].tolist()],
        k_neighbors=max(1, int(k_neighbors)),
    )
    log_test_predictions = _predict_idw(
        log_indexer,
        matrices.x_test,
        [str(v) for v in split_data.test["industry_partition"].tolist()],
        k_neighbors=max(1, int(k_neighbors)),
    )
    log_target_metrics = {
        "transformation": "log1p",
        "inverse_transformation": "expm1",
        "validation_log_space": _metric_summary(log_validation_rates, log_validation_predictions),
        "test_log_space": _metric_summary(log_test_rates, log_test_predictions),
        "validation_raw_space": _metric_summary(matrices.y_validation, inverse_target_log1p(log_validation_predictions)),
        "test_raw_space": _metric_summary(matrices.y_test, inverse_target_log1p(log_test_predictions)),
    }

    outperforms_baseline = bool(
        model_validation_metrics["rmse"] < baseline_validation_metrics["rmse"]
        and model_validation_metrics["r2"] > baseline_validation_metrics["r2"]
        and model_test_metrics["rmse"] < baseline_test_metrics["rmse"]
        and model_test_metrics["r2"] > baseline_test_metrics["r2"]
    )
    quality_gate_passed = bool(model_validation_metrics["r2"] >= float(quality_gate_r2))

    summary = {
        "evaluation_protocol": "stratified_random_exploratory",
        "validation_status": "exploratory_not_empirically_approved",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_rows": int(len(frame)),
        "split_rows": {
            "train": int(len(split_data.train)),
            "validation": int(len(split_data.validation)),
            "test": int(len(split_data.test)),
        },
        "split_distributions": {
            "train": _distribution(split_data.train),
            "validation": _distribution(split_data.validation),
            "test": _distribution(split_data.test),
        },
        "has_split_overlap": has_overlap,
        "feature_shapes": {
            "x_train": [int(v) for v in matrices.x_train.shape],
            "x_validation": [int(v) for v in matrices.x_validation.shape],
            "x_test": [int(v) for v in matrices.x_test.shape],
            "y_train": int(matrices.y_train.shape[0]),
            "y_validation": int(matrices.y_validation.shape[0]),
            "y_test": int(matrices.y_test.shape[0]),
        },
        "model_metrics": {
            "validation": model_validation_metrics,
            "test": model_test_metrics,
        },
        "target_transformation_comparison": {
            "raw": {
                "transformation": "identity",
                "inverse_transformation": "none",
                "validation_raw_space": model_validation_metrics,
                "test_raw_space": model_test_metrics,
            },
            "log1p": log_target_metrics,
        },
        "baseline_metrics": {
            "validation": baseline_validation_metrics,
            "test": baseline_test_metrics,
        },
        "baseline_comparison": {
            "model_outperforms_baseline": outperforms_baseline,
        },
        "quality_gate": {
            "metric": "validation_r2",
            "threshold": float(quality_gate_r2),
            "passed": quality_gate_passed,
            "enforced": bool(enforce_quality_gate),
        },
        "pipeline_config": {
            "k_neighbors": int(max(1, int(k_neighbors))),
            "n_components": int(n_components),
            "max_features": int(max_features),
            "alpha": float(alpha),
            "random_state": int(random_state),
        },
        "artifact_dir": artifact_dir,
        "training_summary_path": os.path.join(artifact_dir, DEFAULT_TRAINING_SUMMARY_ARTIFACT),
        "harmonized_parquet_path": harmonized_parquet_path,
        "macro_lookup_path": macro_lookup_path,
    }

    summary_path = os.path.join(artifact_dir, DEFAULT_TRAINING_SUMMARY_ARTIFACT)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    if enforce_quality_gate and not quality_gate_passed:
        raise RuntimeError(
            f"Quality gate failed: validation R2 {model_validation_metrics['r2']} is below threshold {quality_gate_r2}."
        )
    if enforce_quality_gate and not outperforms_baseline:
        raise RuntimeError("Model did not outperform category-mean baseline on validation and test metrics.")

    with open(harmonized_parquet_path, "rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    sources = set(str(value) for value in frame["source_dataset"].dropna().unique()) if "source_dataset" in frame else set()
    known_sources = {"upwork_jobs", "upwork_data_scientists"}
    source_labels = sorted(sources & known_sources)
    if sources - known_sources:
        source_labels.append("other/unclassified")
    source_labels.sort()
    write_manifest(artifact_dir, inference_config, dataset_version=dataset_version or f"sha256:{digest}",
                   source_type="proxy marketplace data: " + (", ".join(source_labels) if source_labels else "unspecified source"),
                   split_policy=f"stratified_random_seed_{random_state}; exploratory, not OOT",
                   dataset_sha256=digest)
    return summary


def _ensure_demo_inputs(raw_dir: str, macro_lookup_path: str, harmonized_parquet_path: str) -> Tuple[str, str]:
    resolved_macro_lookup = macro_lookup_path
    resolved_parquet = harmonized_parquet_path

    if not os.path.exists(resolved_macro_lookup):
        build_macro_lookup(raw_dir, resolved_macro_lookup)

    if not os.path.exists(resolved_parquet):
        records = build_harmonized_marketplace_records(raw_data_dir=raw_dir, macro_lookup_path=resolved_macro_lookup)
        export_harmonized_records_parquet(records, resolved_parquet)

    return resolved_macro_lookup, resolved_parquet


def parse_args() -> argparse.Namespace:
    """Parse options for stratified orchestration/evaluation or chronological OOT."""
    parser = argparse.ArgumentParser(description="Training and chronological OOT evaluation pipeline")
    parser.add_argument("--mode", choices=("orchestrate", "evaluate", "oot"), default="orchestrate")
    parser.add_argument("--oot-cutoff", help="Prespecified ISO-8601 timezone-aware train/evaluation cutoff")
    parser.add_argument("--dataset-version", help="Immutable version of the timestamped source dataset")
    parser.add_argument("--raw-dir", default=os.path.join("data", "raw"), help="Raw data directory used for demo fallbacks")
    parser.add_argument("--harmonized-parquet", default=DEFAULT_HARMONIZED_PARQUET, help="Input harmonized parquet path")
    parser.add_argument("--macro-lookup", default=DEFAULT_MACRO_LOOKUP, help="Macro lookup JSON path")
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR, help="Directory to persist fitted artifacts")
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--validation-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--random-state", type=int, default=DEFAULT_RANDOM_STATE)
    parser.add_argument("--n-components", type=int, default=TEXT_VECTOR_DIMENSIONS)
    parser.add_argument("--max-features", type=int, default=12000)
    parser.add_argument("--alpha", type=float, default=BILATERAL_ALPHA)
    parser.add_argument("--k-neighbors", type=int, default=DEFAULT_IDW_NEIGHBORS)
    parser.add_argument("--quality-gate-r2", type=float, default=DEFAULT_QUALITY_GATE_R2)
    parser.add_argument("--no-enforce-quality-gate", action="store_true")
    parser.add_argument("--no-save-artifacts", action="store_true", help="Disable artifact persistence")
    parser.add_argument("--verify-listings-firestore", action="store_true",
                        help="Verify listing_id rows against root Firestore service_listings before export (ADC required)")
    return parser.parse_args()


def main() -> None:
    """Dispatch the selected training mode and print its summary."""
    args = parse_args()

    if args.verify_listings_firestore and args.mode == "orchestrate":
        raise ValueError("--verify-listings-firestore requires --mode evaluate or --mode oot")
    if args.mode == "oot" and (not args.oot_cutoff or not args.dataset_version):
        raise ValueError("OOT mode requires --oot-cutoff and --dataset-version.")
    if args.mode != "oot":
        os.makedirs(args.artifact_dir, exist_ok=True)
    macro_lookup_path = args.macro_lookup
    harmonized_parquet_path = args.harmonized_parquet

    if args.mode != "oot" and macro_lookup_path == DEFAULT_MACRO_LOOKUP and not os.path.exists(macro_lookup_path):
        macro_lookup_path = os.path.join(args.artifact_dir, "demo_macro_lookup_table.json")
    if args.mode != "oot" and harmonized_parquet_path == DEFAULT_HARMONIZED_PARQUET and not os.path.exists(harmonized_parquet_path):
        harmonized_parquet_path = os.path.join(args.artifact_dir, "demo_harmonized_marketplace_corpus.parquet")

    if args.mode != "oot":
        macro_lookup_path, harmonized_parquet_path = _ensure_demo_inputs(
            raw_dir=args.raw_dir,
            macro_lookup_path=macro_lookup_path,
            harmonized_parquet_path=harmonized_parquet_path,
        )

    if args.mode == "oot":
        listing_repository = FirestoreRepository() if args.verify_listings_firestore else None
        payload = evaluate_chronological_oot(
            harmonized_parquet_path, macro_lookup_path, args.oot_cutoff, args.artifact_dir, args.dataset_version,
            listing_repository=listing_repository,
        )
    elif args.mode == "evaluate":
        payload = evaluate_and_serialize_training(
            harmonized_parquet_path=harmonized_parquet_path,
            macro_lookup_path=macro_lookup_path,
            train_ratio=args.train_ratio,
            validation_ratio=args.validation_ratio,
            test_ratio=args.test_ratio,
            random_state=args.random_state,
            n_components=args.n_components,
            max_features=args.max_features,
            alpha=args.alpha,
            artifact_dir=args.artifact_dir,
            k_neighbors=args.k_neighbors,
            quality_gate_r2=args.quality_gate_r2,
            enforce_quality_gate=not args.no_enforce_quality_gate,
            listing_repository=FirestoreRepository() if args.verify_listings_firestore else None,
        )
    else:
        payload = orchestrate_training(
            harmonized_parquet_path=harmonized_parquet_path,
            macro_lookup_path=macro_lookup_path,
            train_ratio=args.train_ratio,
            validation_ratio=args.validation_ratio,
            test_ratio=args.test_ratio,
            random_state=args.random_state,
            n_components=args.n_components,
            max_features=args.max_features,
            alpha=args.alpha,
            artifact_dir=args.artifact_dir,
            save_artifacts=not args.no_save_artifacts,
        )
    payload["harmonized_parquet_path"] = harmonized_parquet_path
    payload["macro_lookup_path"] = macro_lookup_path
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
