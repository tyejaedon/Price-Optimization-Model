import json
import os
from typing import Dict, List, Sequence, cast

try:
    import numpy as np
    import pandas as pd
except ImportError as exc:
    raise RuntimeError("Install project dependencies from requirements.txt") from exc

from src.ingest_multisource import get_macro_record, load_macro_lookup_table, map_country_to_iso2

DEFAULT_ENRICHMENT_ARTIFACT = "metadata_enrichment_metadata.json"
BASE_METADATA_COLUMNS = (
    "bilateral_arbitrage_factor",
    "market_saturation_score",
    "industry_relative_density",
)


class LeakageSafeMetadataEnricher:
    """Fit target-free metadata features on training rows and reuse frozen statistics."""

    def __init__(self, macro_lookup_path: str) -> None:
        self.macro_lookup_path = macro_lookup_path
        self.macro_records = load_macro_lookup_table(macro_lookup_path)
        self.partition_stats: Dict[str, Dict[str, float]] = {}
        self.source_categories: List[str] = []
        self.country_pair_categories: List[str] = []
        self.feature_groups: Dict[str, List[str]] = {}
        self.fitted = False

    @staticmethod
    def _numeric(frame: pd.DataFrame, column: str) -> np.ndarray:
        if column not in frame.columns:
            return np.zeros(len(frame), dtype=float)
        values = np.asarray(pd.to_numeric(frame[column], errors="coerce"), dtype=float)
        return np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)

    @staticmethod
    def _as_float(value: object, default: float = 0.0) -> float:
        try:
            return float(cast(float, value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _country_pair(frame: pd.DataFrame) -> List[str]:
        mentor = frame.get("mentor_country_iso2", pd.Series(["KE"] * len(frame))).astype(str).str.upper()
        client = frame.get("client_country_iso2", pd.Series(["KE"] * len(frame))).astype(str).str.upper()
        return [f"{m}->{c}" for m, c in zip(mentor.tolist(), client.tolist())]

    def fit(self, training_frame: pd.DataFrame) -> None:
        if training_frame.empty:
            raise ValueError("Cannot fit metadata enrichment on an empty training frame.")

        partition_column = training_frame["industry_partition"].astype(str).str.lower()
        bilateral = self._numeric(training_frame, "bilateral_arbitrage_factor")
        self.partition_stats = {}
        for partition in sorted(str(value) for value in partition_column.unique().tolist()):
            values = bilateral[partition_column.to_numpy() == partition]
            self.partition_stats[partition] = {
                "count": float(values.size),
                "count_ratio": float(values.size / len(training_frame)),
                "bilateral_median": float(np.median(values)) if values.size else 0.0,
                "bilateral_std": float(np.std(values)) if values.size else 0.0,
                "bilateral_p90": float(np.percentile(values, 90)) if values.size else 0.0,
            }

        self.source_categories = sorted(
            training_frame.get("source_dataset", pd.Series(dtype=str)).astype(str).unique().tolist()
        )
        self.country_pair_categories = sorted(set(self._country_pair(training_frame)))
        self.feature_groups = {
            "macro_enrichment": [
                "log_bilateral_arbitrage_factor",
                "cost_of_living_difference",
                "ppp_ratio",
            ],
            "partition_statistics": [
                "partition_count_ratio",
                "partition_bilateral_median",
                "partition_bilateral_std",
                "partition_bilateral_p90",
            ],
            "source_indicators": [f"source_dataset={value}" for value in self.source_categories],
            "country_interactions": [f"country_pair={value}" for value in self.country_pair_categories],
        }
        self.fitted = True

    def _macro_features(self, frame: pd.DataFrame) -> np.ndarray:
        bilateral = self._numeric(frame, "bilateral_arbitrage_factor")
        mentor = frame.get("mentor_country_iso2", pd.Series(["KE"] * len(frame))).tolist()
        client = frame.get("client_country_iso2", pd.Series(["KE"] * len(frame))).tolist()
        output: List[List[float]] = []
        for index, (mentor_value, client_value) in enumerate(zip(mentor, client)):
            mentor_record = get_macro_record(self.macro_records, map_country_to_iso2(mentor_value))
            client_record = get_macro_record(self.macro_records, map_country_to_iso2(client_value))
            mentor_cost = self._as_float(mentor_record.get("cost_of_living_index", 0.0))
            client_cost = self._as_float(client_record.get("cost_of_living_index", 0.0))
            mentor_ppp = self._as_float(mentor_record.get("ppp_lcu_per_intl_dollar", 1.0), default=1.0)
            client_ppp = self._as_float(client_record.get("ppp_lcu_per_intl_dollar", 1.0), default=1.0)
            output.append([
                float(np.log1p(max(0.0, bilateral[index]))),
                mentor_cost - client_cost,
                mentor_ppp / client_ppp if client_ppp else 1.0,
            ])
        return np.asarray(output, dtype=float)

    def transform_groups(self, frame: pd.DataFrame) -> Dict[str, np.ndarray]:
        if not self.fitted:
            raise RuntimeError("LeakageSafeMetadataEnricher must be fitted before transform_groups().")

        partitions = frame["industry_partition"].astype(str).str.lower().tolist()
        macro = self._macro_features(frame)
        partition_rows = [
            [
                self.partition_stats.get(partition, {}).get("count_ratio", 0.0),
                self.partition_stats.get(partition, {}).get("bilateral_median", 0.0),
                self.partition_stats.get(partition, {}).get("bilateral_std", 0.0),
                self.partition_stats.get(partition, {}).get("bilateral_p90", 0.0),
            ]
            for partition in partitions
        ]
        sources = frame.get("source_dataset", pd.Series([""] * len(frame))).astype(str).tolist()
        source_matrix = np.asarray(
            [[1.0 if source == category else 0.0 for category in self.source_categories] for source in sources],
            dtype=float,
        )
        pairs = self._country_pair(frame)
        pair_matrix = np.asarray(
            [[1.0 if pair == category else 0.0 for category in self.country_pair_categories] for pair in pairs],
            dtype=float,
        )
        return {
            "macro_enrichment": macro,
            "partition_statistics": np.asarray(partition_rows, dtype=float),
            "source_indicators": source_matrix,
            "country_interactions": pair_matrix,
        }

    def transform(self, frame: pd.DataFrame, groups: Sequence[str] | None = None) -> np.ndarray:
        transformed = self.transform_groups(frame)
        selected = list(groups) if groups is not None else list(self.feature_groups)
        missing = [group for group in selected if group not in transformed]
        if missing:
            raise KeyError(f"Unknown enrichment groups: {missing}")
        if not selected:
            return np.zeros((len(frame), 0), dtype=float)
        matrix = np.concatenate([transformed[group] for group in selected], axis=1)
        if not np.all(np.isfinite(matrix)):
            raise ValueError("Enriched metadata contains non-finite values.")
        return matrix

    def save_artifacts(self, artifact_dir: str) -> str:
        if not self.fitted:
            raise RuntimeError("LeakageSafeMetadataEnricher must be fitted before save_artifacts().")
        os.makedirs(artifact_dir, exist_ok=True)
        path = os.path.join(artifact_dir, DEFAULT_ENRICHMENT_ARTIFACT)
        payload = {
            "macro_lookup_path": self.macro_lookup_path,
            "partition_stats": self.partition_stats,
            "source_categories": self.source_categories,
            "country_pair_categories": self.country_pair_categories,
            "feature_groups": self.feature_groups,
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        return path

    @classmethod
    def load_artifacts(cls, artifact_dir: str, macro_lookup_path: str | None = None) -> "LeakageSafeMetadataEnricher":
        path = os.path.join(artifact_dir, DEFAULT_ENRICHMENT_ARTIFACT)
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        instance = cls(macro_lookup_path or str(payload["macro_lookup_path"]))
        instance.partition_stats = payload["partition_stats"]
        instance.source_categories = [str(value) for value in payload["source_categories"]]
        instance.country_pair_categories = [str(value) for value in payload["country_pair_categories"]]
        instance.feature_groups = payload["feature_groups"]
        instance.fitted = True
        return instance


