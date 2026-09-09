import argparse
import json
import os
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, cast

try:
    import numpy as np
    import pandas as pd
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
    METADATA_VECTOR_DIMENSIONS,
    TEXT_VECTOR_DIMENSIONS,
    ContinuousMetadataNormalizer,
    fuse_coordinate_batches,
)
from src.nlp_pipeline import TextFeatureReducer

DEFAULT_HARMONIZED_PARQUET = os.path.join("data", "processed", "harmonized_marketplace_corpus.parquet")
DEFAULT_ARTIFACT_DIR = "artifacts"
DEFAULT_RANDOM_STATE = 42

REQUIRED_COLUMNS = (
    "raw_description",
    "industry_partition",
    "bilateral_arbitrage_factor",
    "market_saturation_score",
    "industry_relative_density",
)


@dataclass(frozen=True)
class SplitData:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame


@dataclass(frozen=True)
class TrainingMatrices:
    x_train: np.ndarray
    x_validation: np.ndarray
    x_test: np.ndarray
    y_train: np.ndarray
    y_validation: np.ndarray
    y_test: np.ndarray


def load_harmonized_parquet(parquet_path: str) -> pd.DataFrame:
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
    if frame.empty:
        raise ValueError("Harmonized parquet cannot be empty.")
    return frame


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


def _ensure_text_dimensions(matrix: np.ndarray, expected_dimensions: int = TEXT_VECTOR_DIMENSIONS) -> np.ndarray:
    if matrix.ndim != 2:
        raise ValueError(f"Expected a 2-D text matrix; got shape {matrix.shape}.")

    cols = matrix.shape[1]
    if cols == expected_dimensions:
        return matrix
    if cols > expected_dimensions:
        return matrix[:, :expected_dimensions]

    pad_width = expected_dimensions - cols
    padded = np.pad(matrix, ((0, 0), (0, pad_width)), mode="constant", constant_values=0.0)
    return padded.astype(float, copy=False)


def _fit_feature_matrices(
    split_data: SplitData,
    macro_lookup_path: str,
    n_components: int = TEXT_VECTOR_DIMENSIONS,
    max_features: int = 12000,
    alpha: float = BILATERAL_ALPHA,
    artifact_dir: str = DEFAULT_ARTIFACT_DIR,
    save_artifacts: bool = True,
) -> TrainingMatrices:
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

    x_train = fuse_coordinate_batches(train_text, train_meta)
    x_validation = fuse_coordinate_batches(validation_text, validation_meta)
    x_test = fuse_coordinate_batches(test_text, test_meta)

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
) -> Dict[str, Any]:
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
    }


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
    parser = argparse.ArgumentParser(description="M6.1 train/validation/test orchestration pipeline")
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
    parser.add_argument("--no-save-artifacts", action="store_true", help="Disable artifact persistence")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    os.makedirs(args.artifact_dir, exist_ok=True)
    macro_lookup_path = args.macro_lookup
    harmonized_parquet_path = args.harmonized_parquet

    if macro_lookup_path == DEFAULT_MACRO_LOOKUP and not os.path.exists(macro_lookup_path):
        macro_lookup_path = os.path.join(args.artifact_dir, "demo_macro_lookup_table.json")
    if harmonized_parquet_path == DEFAULT_HARMONIZED_PARQUET and not os.path.exists(harmonized_parquet_path):
        harmonized_parquet_path = os.path.join(args.artifact_dir, "demo_harmonized_marketplace_corpus.parquet")

    macro_lookup_path, harmonized_parquet_path = _ensure_demo_inputs(
        raw_dir=args.raw_dir,
        macro_lookup_path=macro_lookup_path,
        harmonized_parquet_path=harmonized_parquet_path,
    )

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

