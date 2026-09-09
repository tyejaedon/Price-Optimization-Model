import argparse
import json
import os
from typing import Any, Dict, List, Sequence, Tuple

try:
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.preprocessing import MinMaxScaler
except ImportError as exc:
    raise RuntimeError("Missing metadata-scaler dependencies. Install from requirements.txt") from exc

from src.ingest_multisource import (
    BILATERAL_ALPHA,
    build_harmonized_marketplace_records,
    build_macro_lookup,
    compute_bilateral_arbitrage_factor,
    export_harmonized_records_parquet,
    load_macro_lookup_table,
    map_country_to_iso2,
)
from src.nlp_pipeline import TextFeatureReducer

DEFAULT_FEATURE_NAMES: Tuple[str, str, str] = (
    "bilateral_arbitrage_factor",
    "market_saturation_score",
    "industry_relative_density",
)
DEFAULT_ARTIFACT_DIR = "artifacts"
DEFAULT_SCALER_ARTIFACT = "metadata_scaler.joblib"
DEFAULT_SCALER_METADATA = "metadata_scaler_metadata.json"
DEFAULT_MACRO_LOOKUP = os.path.join("data", "processed", "macro_lookup_table.json")
DEFAULT_HARMONIZED_PARQUET = os.path.join("data", "processed", "harmonized_marketplace_corpus.parquet")
TEXT_VECTOR_DIMENSIONS = 50
METADATA_VECTOR_DIMENSIONS = 3
HYBRID_VECTOR_DIMENSIONS = TEXT_VECTOR_DIMENSIONS + METADATA_VECTOR_DIMENSIONS


class ContinuousMetadataNormalizer:
    """Fit and apply a MinMax scaler over continuous metadata features."""

    def __init__(
        self,
        macro_lookup_path: str,
        feature_names: Tuple[str, str, str] = DEFAULT_FEATURE_NAMES,
        alpha: float = BILATERAL_ALPHA,
    ) -> None:
        self.macro_lookup_path = macro_lookup_path
        self.feature_names = feature_names
        self.alpha = float(alpha)
        self.macro_records = load_macro_lookup_table(macro_lookup_path)
        self.scaler = MinMaxScaler(feature_range=(0.0, 1.0))
        self.fitted = False

    def build_live_metadata_vector(
        self,
        mentor_country_iso2: str,
        client_country_iso2: str,
        market_saturation_score: float,
        industry_relative_density: float,
    ) -> np.ndarray:
        mentor_iso2 = map_country_to_iso2(mentor_country_iso2)
        client_iso2 = map_country_to_iso2(client_country_iso2)
        bilateral_factor = compute_bilateral_arbitrage_factor(
            mentor_iso2_code=mentor_iso2,
            client_iso2_code=client_iso2,
            macro_records=self.macro_records,
            alpha=self.alpha,
        )
        vector = np.array(
            [
                bilateral_factor,
                float(market_saturation_score),
                float(industry_relative_density),
            ],
            dtype=float,
        )
        return vector.reshape(1, -1)

    def _record_to_row(self, record: Dict[str, Any]) -> List[float]:
        return [float(record.get(feature_name, 0.0) or 0.0) for feature_name in self.feature_names]

    def fit(self, records: Sequence[Dict[str, Any]]) -> None:
        matrix = np.array([self._record_to_row(record) for record in records], dtype=float)
        if matrix.size == 0:
            raise ValueError("Cannot fit metadata scaler on an empty record set.")
        self.scaler.fit(matrix)
        self.fitted = True

    def fit_transform(self, records: Sequence[Dict[str, Any]]) -> np.ndarray:
        matrix = np.array([self._record_to_row(record) for record in records], dtype=float)
        if matrix.size == 0:
            raise ValueError("Cannot fit metadata scaler on an empty record set.")
        transformed = self.scaler.fit_transform(matrix)
        self.fitted = True
        return transformed

    def transform(self, records: Sequence[Dict[str, Any]]) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("ContinuousMetadataNormalizer must be fitted before transform().")
        matrix = np.array([self._record_to_row(record) for record in records], dtype=float)
        if matrix.size == 0:
            return np.empty((0, len(self.feature_names)), dtype=float)
        return self.scaler.transform(matrix)

    def transform_live_metadata(
        self,
        mentor_country_iso2: str,
        client_country_iso2: str,
        market_saturation_score: float,
        industry_relative_density: float,
    ) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("ContinuousMetadataNormalizer must be fitted before transform_live_metadata().")
        vector = self.build_live_metadata_vector(
            mentor_country_iso2=mentor_country_iso2,
            client_country_iso2=client_country_iso2,
            market_saturation_score=market_saturation_score,
            industry_relative_density=industry_relative_density,
        )
        return self.scaler.transform(vector)

    def fit_from_parquet(self, parquet_path: str) -> np.ndarray:
        frame = pd.read_parquet(parquet_path)
        records = frame.to_dict(orient="records")
        return self.fit_transform(records)

    def save_artifacts(self, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> None:
        if not self.fitted:
            raise RuntimeError("ContinuousMetadataNormalizer must be fitted before save_artifacts().")

        os.makedirs(artifact_dir, exist_ok=True)
        scaler_path = os.path.join(artifact_dir, DEFAULT_SCALER_ARTIFACT)
        metadata_path = os.path.join(artifact_dir, DEFAULT_SCALER_METADATA)
        joblib.dump(self.scaler, scaler_path)

        metadata = {
            "macro_lookup_path": self.macro_lookup_path,
            "feature_names": list(self.feature_names),
            "alpha": self.alpha,
            "feature_mins": [float(value) for value in self.scaler.data_min_],
            "feature_maxs": [float(value) for value in self.scaler.data_max_],
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, sort_keys=True)

    @classmethod
    def load_artifacts(cls, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> "ContinuousMetadataNormalizer":
        scaler_path = os.path.join(artifact_dir, DEFAULT_SCALER_ARTIFACT)
        metadata_path = os.path.join(artifact_dir, DEFAULT_SCALER_METADATA)

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        feature_names_raw = metadata.get("feature_names", list(DEFAULT_FEATURE_NAMES))
        if not isinstance(feature_names_raw, list) or len(feature_names_raw) != 3:
            feature_names = DEFAULT_FEATURE_NAMES
        else:
            feature_names = (str(feature_names_raw[0]), str(feature_names_raw[1]), str(feature_names_raw[2]))

        instance = cls(
            macro_lookup_path=str(metadata.get("macro_lookup_path", DEFAULT_MACRO_LOOKUP)),
            feature_names=feature_names,
            alpha=float(metadata.get("alpha", BILATERAL_ALPHA)),
        )
        instance.scaler = joblib.load(scaler_path)
        instance.fitted = True
        return instance


def _coerce_feature_vector(vector: Any, expected_size: int, vector_name: str) -> np.ndarray:
    array = np.asarray(vector, dtype=float)
    if array.ndim == 2:
        if array.shape[0] != 1:
            raise ValueError(f"{vector_name} must be a 1-D vector or single-row matrix; got shape {array.shape}.")
        array = array.reshape(-1)
    elif array.ndim != 1:
        raise ValueError(f"{vector_name} must be 1-D; got shape {array.shape}.")

    if array.size != expected_size:
        raise ValueError(f"{vector_name} must contain exactly {expected_size} values; got {array.size}.")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{vector_name} contains non-finite values.")

    return array.astype(float, copy=False)


def fuse_coordinates(dense_text_vector: Any, normalized_metadata: Any) -> np.ndarray:
    """Concatenate a 50-D text vector and 3-D normalized metadata into an immutable 53-D vector."""
    text_array = _coerce_feature_vector(dense_text_vector, TEXT_VECTOR_DIMENSIONS, "dense_text_vector")
    metadata_array = _coerce_feature_vector(normalized_metadata, METADATA_VECTOR_DIMENSIONS, "normalized_metadata")

    fused = np.concatenate([text_array, metadata_array]).astype(float, copy=False)
    fused.setflags(write=False)
    return fused


def fuse_coordinate_batches(text_vectors: Any, metadata_vectors: Any) -> np.ndarray:
    """Fuse aligned text and metadata matrices row-wise into immutable hybrid coordinates."""
    text_matrix = np.asarray(text_vectors, dtype=float)
    metadata_matrix = np.asarray(metadata_vectors, dtype=float)

    if text_matrix.ndim != 2:
        raise ValueError(f"text_vectors must be a 2-D matrix; got shape {text_matrix.shape}.")
    if metadata_matrix.ndim != 2:
        raise ValueError(f"metadata_vectors must be a 2-D matrix; got shape {metadata_matrix.shape}.")
    if text_matrix.shape[1] != TEXT_VECTOR_DIMENSIONS:
        raise ValueError(f"text_vectors must have {TEXT_VECTOR_DIMENSIONS} columns; got {text_matrix.shape[1]}.")
    if metadata_matrix.shape[1] != METADATA_VECTOR_DIMENSIONS:
        raise ValueError(
            f"metadata_vectors must have {METADATA_VECTOR_DIMENSIONS} columns; got {metadata_matrix.shape[1]}."
        )
    if text_matrix.shape[0] != metadata_matrix.shape[0]:
        raise ValueError(
            f"text_vectors and metadata_vectors must have the same row count; got {text_matrix.shape[0]} and {metadata_matrix.shape[0]}."
        )
    if not np.all(np.isfinite(text_matrix)):
        raise ValueError("text_vectors contains non-finite values.")
    if not np.all(np.isfinite(metadata_matrix)):
        raise ValueError("metadata_vectors contains non-finite values.")

    fused = np.concatenate([text_matrix, metadata_matrix], axis=1)
    fused.setflags(write=False)
    return fused


def _build_text_demo_corpus(row_count: int = 90) -> List[str]:
    alphabet = "abcdefghijklmnopqrstuvwxyz"

    def alpha_token(index: int) -> str:
        base = len(alphabet)
        chars: List[str] = []
        value = index
        while True:
            chars.append(alphabet[value % base])
            value //= base
            if value == 0:
                break
        return "tok" + "".join(chars)

    return [
        " ".join(
            [
                "data",
                "science",
                "machine",
                "learning",
                "python",
                "analytics",
                alpha_token(i),
                alpha_token(i + 200),
                alpha_token(i + 400),
            ]
        )
        for i in range(max(60, row_count))
    ]


def _ensure_demo_artifacts(raw_dir: str, macro_lookup_path: str, harmonized_parquet_path: str) -> Tuple[str, str]:
    macro_path = macro_lookup_path
    parquet_path = harmonized_parquet_path

    if not os.path.exists(macro_path):
        build_macro_lookup(raw_dir, macro_path)

    if not os.path.exists(parquet_path):
        records = build_harmonized_marketplace_records(raw_dir, macro_path)
        export_harmonized_records_parquet(records, parquet_path)

    return macro_path, parquet_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fit and use the continuous metadata normalizer.")
    parser.add_argument("--mode", choices=("fit_demo", "transform_demo", "fuse_demo"), default="fit_demo")
    parser.add_argument("--raw-dir", default=os.path.join("data", "raw"), help="Raw data directory")
    parser.add_argument("--macro-lookup", default=DEFAULT_MACRO_LOOKUP, help="Macro lookup JSON path")
    parser.add_argument(
        "--harmonized-parquet",
        default=DEFAULT_HARMONIZED_PARQUET,
        help="Harmonized parquet path used to fit metadata scaler",
    )
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR, help="Directory for scaler artifacts")
    parser.add_argument("--mentor-country", default="KE", help="Mentor ISO-2 country code")
    parser.add_argument("--client-country", default="US", help="Client ISO-2 country code")
    parser.add_argument("--market-saturation", type=float, default=0.25, help="Sample market saturation score")
    parser.add_argument("--industry-density", type=float, default=0.4, help="Sample industry density score")
    parser.add_argument("--alpha", type=float, default=BILATERAL_ALPHA, help="Bilateral arbitrage alpha")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_dir = args.raw_dir
    macro_lookup_path = args.macro_lookup
    harmonized_parquet_path = args.harmonized_parquet
    os.makedirs(args.artifact_dir, exist_ok=True)

    if macro_lookup_path == DEFAULT_MACRO_LOOKUP and not os.path.exists(macro_lookup_path):
        macro_lookup_path = os.path.join(args.artifact_dir, "demo_macro_lookup_table.json")
    if harmonized_parquet_path == DEFAULT_HARMONIZED_PARQUET and not os.path.exists(harmonized_parquet_path):
        harmonized_parquet_path = os.path.join(args.artifact_dir, "demo_harmonized_marketplace_corpus.parquet")

    macro_lookup_path, harmonized_parquet_path = _ensure_demo_artifacts(
        raw_dir=raw_dir,
        macro_lookup_path=macro_lookup_path,
        harmonized_parquet_path=harmonized_parquet_path,
    )

    normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path, alpha=args.alpha)
    transformed = normalizer.fit_from_parquet(harmonized_parquet_path)
    normalizer.save_artifacts(args.artifact_dir)

    reloaded = ContinuousMetadataNormalizer.load_artifacts(args.artifact_dir)
    live_vector = reloaded.build_live_metadata_vector(
        mentor_country_iso2=args.mentor_country,
        client_country_iso2=args.client_country,
        market_saturation_score=args.market_saturation,
        industry_relative_density=args.industry_density,
    )
    scaled_live_vector = reloaded.transform_live_metadata(
        mentor_country_iso2=args.mentor_country,
        client_country_iso2=args.client_country,
        market_saturation_score=args.market_saturation,
        industry_relative_density=args.industry_density,
    )

    payload = {
        "fit_rows": int(transformed.shape[0]),
        "fit_dimensions": int(transformed.shape[1]),
        "feature_names": list(reloaded.feature_names),
        "raw_live_vector": [round(float(value), 6) for value in live_vector[0]],
        "scaled_live_vector": [round(float(value), 6) for value in scaled_live_vector[0]],
        "artifact_dir": args.artifact_dir,
        "macro_lookup_path": macro_lookup_path,
        "harmonized_parquet_path": harmonized_parquet_path,
    }

    if args.mode == "fuse_demo":
        text_reducer = TextFeatureReducer(n_components=TEXT_VECTOR_DIMENSIONS, max_features=12000)
        demo_corpus = _build_text_demo_corpus()
        text_reducer.fit_transform(demo_corpus)
        dense_text_vector = text_reducer.transform([demo_corpus[0]])
        fused_vector = fuse_coordinates(dense_text_vector, scaled_live_vector)
        payload.update(
            {
                "dense_text_vector_shape": [int(dense_text_vector.shape[0]), int(dense_text_vector.shape[1])],
                "fused_vector_shape": [int(fused_vector.shape[0])],
                "fused_vector_preview": [round(float(value), 6) for value in fused_vector[:6]],
                "hybrid_vector_dimensions": HYBRID_VECTOR_DIMENSIONS,
            }
        )

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

