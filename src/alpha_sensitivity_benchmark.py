"""Research-only #119 scenario sweep; alpha-derived proxy labels are not ground truth."""

import argparse
import hashlib
import json
import platform
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn

from src.inference_safe_benchmark import _split_population
from src.ingest_multisource import (
    BILATERAL_ALPHA, compute_bilateral_arbitrage_factor, load_macro_lookup_table,
    map_country_to_iso2,
)
from src.interval_synthesizer import FloorExceedsCeilingError, synthesize_corridor
from src.macro_arbitrage import ContinuousMetadataNormalizer, DEFAULT_FEATURE_NAMES
from src.nlp_pipeline import TextFeatureReducer
from src.spatial_engine import DEFAULT_IDW_EPSILON, DEFAULT_MIN_PARTITION_SIZE, DomainPartitionedKDTreeIndexer
from src.svd_dimension_benchmark import _peer_stability, _profile, _vectors
from src.train_pipeline import DEFAULT_IDW_NEIGHBORS, load_harmonized_parquet

ALPHAS = (0.0, 0.25, 0.5, 0.75, 1.0)
PARQUET_SHA93 = "da5432eec261e8b8aff66d046f276562a75d24b2106d61a9c189571e8725a5ca"
MACRO_SHA93 = "30d8d6b351770b0a85287c4b2791f0549735a8f6b6eac5c914109b3c7782f901"
VALIDATION_CUTOFF = "2024-02-20T00:00:00+00:00"
TEST_CUTOFF = "2024-02-22T00:00:00+00:00"


def _sha(path: str) -> str:
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _mean(values: list[float]) -> float | None:
    return round(float(np.mean(values)), 6) if values else None


def _country_coverage(frame: pd.DataFrame, macro: dict[str, Any]) -> dict[str, Any]:
    """Diagnose lookup substitutions, including source-country normalization to KE."""
    pairs: Counter[str] = Counter()
    fallbacks: Counter[str] = Counter()
    if "source_country" not in frame or "mentor_country_iso2" not in frame or "client_country_iso2" not in frame:
        raise ValueError("source_country and both country roles are required to audit fallback.")
    for row in frame.itertuples(index=False):
        raw = getattr(row, "source_country")
        raw_code = map_country_to_iso2(raw, default_iso2_code="ZZ") if pd.notna(raw) else "ZZ"
        mentor = str(getattr(row, "mentor_country_iso2"))
        client = str(getattr(row, "client_country_iso2"))
        if mentor != "KE" or client != map_country_to_iso2(raw if pd.notna(raw) else None):
            raise ValueError("Country roles differ from the frozen KE-anchor/source-country policy.")
        pairs[f"{mentor}->{client}"] += 1
        if raw_code == "ZZ":
            fallbacks["source_country_unknown_or_missing_to_KE"] += 1
        if mentor not in macro:
            fallbacks["mentor_macro_lookup_to_KE"] += 1
        if client not in macro:
            fallbacks["client_macro_lookup_to_KE"] += 1
        for role, country in (("mentor", mentor), ("client", client)):
            record = macro.get(country, macro.get("KE", {}))
            for field in ("ppp_lcu_per_intl_dollar", "cost_of_living_index"):
                try:
                    value = float(record.get(field))
                except (TypeError, ValueError):
                    value = float("nan")
                if not np.isfinite(value) or value <= 0:
                    fallbacks[f"{role}_{field}_default_to_1"] += 1
    return {
        "rows": len(frame), "country_pairs": dict(sorted(pairs.items())),
        "same_country_rows": pairs["KE->KE"], "fallback_events": dict(sorted(fallbacks.items())),
        "distinct_client_countries": len({pair.split("->")[1] for pair in pairs}),
    }


def _scenario(frame: pd.DataFrame, macro: dict[str, Any], alpha: float) -> pd.DataFrame:
    result = frame.copy()
    factors = np.array([
        compute_bilateral_arbitrage_factor(mentor, client, macro, alpha=alpha)
        for mentor, client in zip(result["mentor_country_iso2"], result["client_country_iso2"])
    ], dtype=float)
    base = pd.to_numeric(result["hourly_rate"], errors="coerce").to_numpy(dtype=float)
    if not np.all(np.isfinite(base) & (base > 0)) or not np.all(np.isfinite(factors) & (factors > 0)):
        raise ValueError("Frozen cohort has invalid pre-arbitrage rates or scenario factors.")
    result["bilateral_arbitrage_factor"] = factors
    result["target_rate"] = np.round(base * factors, 2)
    return result


def _queries(indexer: DomainPartitionedKDTreeIndexer, vectors: np.ndarray,
             frame: pd.DataFrame) -> tuple[np.ndarray, list[dict[str, Any]], list[dict[str, float] | None]]:
    predictions, peers, corridors = [], [], []
    for vector, row in zip(vectors, frame.itertuples(index=False)):
        prediction = indexer.predict_base_rate(vector, row.industry_partition,
                                                k=DEFAULT_IDW_NEIGHBORS, epsilon=DEFAULT_IDW_EPSILON)
        predictions.append(prediction["base_predicted_rate"])
        peers.append({
            "ids": [p["peer_index"] for p in prediction["nearest_neighbors"]],
            "weights": {p["peer_index"]: p["idw_weight"] for p in prediction["nearest_neighbors"]},
            "similarity": {p["peer_index"]: p["similarity_score"] for p in prediction["nearest_neighbors"]},
            "fallback": prediction["fallback_triggered"],
        })
        try:
            corridors.append(synthesize_corridor(prediction["base_predicted_rate"],
                                                 prediction["peer_stddev"], row.bilateral_arbitrage_factor))
        except FloorExceedsCeilingError:
            corridors.append(None)
    return np.asarray(predictions, dtype=float), peers, corridors


def _changes(base: pd.DataFrame, trial: pd.DataFrame, base_predictions: np.ndarray,
             predictions: np.ndarray, base_peers: list[dict[str, Any]], peers: list[dict[str, Any]],
             base_corridors: list[dict[str, float] | None],
             corridors: list[dict[str, float] | None]) -> dict[str, Any]:
    diffs = np.abs(trial["bilateral_arbitrage_factor"].to_numpy() - base["bilateral_arbitrage_factor"].to_numpy())
    label_diffs = np.abs(trial["target_rate"].to_numpy() - base["target_rate"].to_numpy())
    same = base["mentor_country_iso2"].to_numpy() == base["client_country_iso2"].to_numpy()
    bounds = {}
    for field in ("min_quoted_rate", "max_quoted_rate"):
        paired = [(b[field], t[field]) for b, t in zip(base_corridors, corridors) if b is not None and t is not None]
        bounds[f"mean_absolute_{field}_change_kes"] = _mean([abs(b - t) for b, t in paired])
    pairs: dict[str, Any] = {}
    for (mentor, client), group in trial.groupby(["mentor_country_iso2", "client_country_iso2"], sort=True):
        positions = group.index.to_numpy(dtype=int)
        pairs[f"{mentor}->{client}"] = {
            "rows": len(positions),
            "mean_factor": _mean(trial.iloc[positions].bilateral_arbitrage_factor.tolist()),
            "mean_absolute_factor_change": _mean(diffs[positions].tolist()),
            "mean_absolute_scenario_target_change_kes": _mean(label_diffs[positions].tolist()),
            "mean_absolute_base_quote_change_kes":
                _mean(np.abs(predictions[positions] - base_predictions[positions]).tolist()),
        }
    return {
        "mean_absolute_factor_change": _mean(diffs.tolist()),
        "mean_absolute_label_change_kes": _mean(label_diffs.tolist()),
        "mean_absolute_base_quote_change_kes": _mean(np.abs(predictions - base_predictions).tolist()),
        "same_country_rows": int(same.sum()),
        "same_country_factor_changes": int(np.count_nonzero(diffs[same] > 1e-10)),
        "same_country_label_changes": int(np.count_nonzero(label_diffs[same] > 1e-9)),
        "same_country_mean_absolute_quote_change_kes": _mean(np.abs(predictions[same] - base_predictions[same]).tolist()),
        "corridors_defined": sum(value is not None for value in corridors),
        "corridors_undefined_floor_exceeds_ceiling": sum(value is None for value in corridors),
        "corridors_comparable": sum(b is not None and t is not None for b, t in zip(base_corridors, corridors)),
        "validation_country_pair_sensitivity": pairs,
        **bounds,
        "peer_overlap": _peer_stability(base_peers, peers, base_predictions, predictions),
    }


def run_benchmark(parquet_path: str, macro_path: str, output_dir: str = "reports/m9_alpha_sensitivity_119",
                  samples: int = 25, *, allow_other_snapshot: bool = False) -> dict[str, Any]:
    """Use #93's exact frozen cohort; opt-in non-#93 snapshots are labelled as such."""
    if samples < 1:
        raise ValueError("samples must be positive.")
    hashes = {"parquet": _sha(parquet_path), "macro_lookup": _sha(macro_path)}
    is_93 = hashes == {"parquet": PARQUET_SHA93, "macro_lookup": MACRO_SHA93}
    if not is_93 and not allow_other_snapshot:
        raise ValueError("Input SHA-256 does not match the frozen #93 parquet and macro lookup.")
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty report directory for each run.")
    macro = load_macro_lookup_table(macro_path)
    split, provenance = _split_population(load_harmonized_parquet(parquet_path), VALIDATION_CUTOFF, TEST_CUTOFF)
    if is_93 and provenance["split_rows"] != {"train": 10703, "validation": 2384, "test": 3390}:
        raise ValueError("Frozen #93 cohort row counts differ.")
    research_rows = pd.concat((split.train, split.validation), ignore_index=True)
    coverage = {name: _country_coverage(part, macro) for name, part in
                (("train", split.train), ("validation", split.validation), ("test_not_scored", split.test))}
    original = research_rows["harmonized_hourly_rate"].to_numpy(dtype=float)
    baseline = _scenario(research_rows, macro, BILATERAL_ALPHA)
    if not np.allclose(original, baseline["target_rate"].to_numpy(dtype=float), rtol=0, atol=0.02):
        raise ValueError("Frozen #93 labels do not match alpha=0.50 factors; cannot rebase scenarios.")
    if "arbitrage_alpha" in research_rows and not np.allclose(research_rows["arbitrage_alpha"].to_numpy(dtype=float), 0.5):
        raise ValueError("Input was not harmonized with the frozen alpha=0.50.")
    train_n, validation_n = len(split.train), len(split.validation)
    report: dict[str, Any] = {
        "issue": 119, "status": "research_only_no_promotion",
        "snapshot": "frozen_93_previously_opened" if is_93 else "other_snapshot_not_93",
        "input_sha256": hashes, "protocol": provenance, "country_coverage": coverage,
        "predeclared_alphas": list(ALPHAS), "baseline_alpha": 0.5,
        "fixed": {"text_dimensions": 50, "metadata_features": list(DEFAULT_FEATURE_NAMES),
                  "tfidf_max_features": 12000, "ngram_range": [1, 2], "min_df": 1,
                  "normalize_output": False, "svd_seed": 42, "text_weight": 1.0,
                  "metadata_weight": 1.0, "k": DEFAULT_IDW_NEIGHBORS,
                  "epsilon": DEFAULT_IDW_EPSILON, "minimum_partition_size": DEFAULT_MIN_PARTITION_SIZE},
        "eligibility": "fixed at stored alpha=0.50 harmonized rate [500,35000]; NEVER reselect per alpha",
        "score_policy": "NO error/R2 or optimization: all targets depend on the tested alpha; #93 test already opened; no test predictions",
        "country_policy": "KE assumed mentor anchor; source_country is not a verified client; unknown source normalizes to KE; missing macro falls back to KE",
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "numpy": np.__version__, "sklearn": sklearn.__version__},
        "results": [], "no_production_promotion": True,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "protocol_frozen.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    reducer = TextFeatureReducer(n_components=50, max_features=12000, ngram_range=(1, 2),
                                 min_df=1, random_state=42, normalize_output=False)
    reducer.fit_transform(split.train["raw_description"].tolist())
    if reducer.reducer.n_components != 50:
        raise ValueError("Train-only SVD did not fit 50 dimensions.")
    comparisons = {}
    for alpha in ALPHAS:
        row: dict[str, Any] = {"alpha": alpha, "status": "failed"}
        report["results"].append(row)
        try:
            scenario = _scenario(research_rows, macro, alpha)
            train = scenario.iloc[:train_n].reset_index(drop=True)
            validation = scenario.iloc[train_n:train_n + validation_n].reset_index(drop=True)
            normalizer = ContinuousMetadataNormalizer(macro_path, alpha=alpha)
            normalizer.fit(train.to_dict(orient="records"))
            train_vectors = _vectors(reducer, normalizer, train, 50)
            validation_vectors = _vectors(reducer, normalizer, validation, 50)
            indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=DEFAULT_MIN_PARTITION_SIZE)
            indexer.fit(train_vectors, train["industry_partition"].tolist(), record_indices=train["record_id"].tolist(),
                        verified_rates=train["target_rate"].tolist())
            predictions, peers, corridors = _queries(indexer, validation_vectors, validation)
            artifact_dir = output / f"alpha_{alpha:.2f}"
            row.update(_profile(reducer, normalizer, indexer, validation, validation_vectors,
                                artifact_dir, macro_path, samples))
            row.update({
                "status": "ok", "validation_rows": len(validation),
                "train_scenario_target_outside_500_35000": int(((train.target_rate < 500) | (train.target_rate > 35000)).sum()),
                "validation_scenario_target_outside_500_35000": int(((validation.target_rate < 500) | (validation.target_rate > 35000)).sum()),
                "validation_mean_factor": _mean(validation.bilateral_arbitrage_factor.tolist()),
                "validation_mean_scenario_target_kes": _mean(validation.target_rate.tolist()),
                "validation_industry_counts": dict(sorted(validation.industry_partition.value_counts().to_dict().items())),
                "validation_corridors_undefined": sum(c is None for c in corridors),
            })
            comparisons[alpha] = (validation, predictions, peers, corridors)
        except (ValueError, KeyError, RuntimeError) as exc:
            row["failure"] = f"{type(exc).__name__}: {exc}"
    if 0.5 in comparisons:
        base, base_pred, base_peers, base_corridors = comparisons[0.5]
        for row in report["results"]:
            if row["alpha"] in comparisons:
                trial, predictions, peers, corridors = comparisons[row["alpha"]]
                row["vs_alpha_0_50"] = _changes(base, trial, base_pred, predictions, base_peers, peers,
                                                base_corridors, corridors)
    else:
        report["baseline_failure"] = "alpha=0.50 failed; candidate differences cannot be computed"
    (output / "benchmark.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harmonized-parquet", required=True)
    parser.add_argument("--macro-lookup", required=True)
    parser.add_argument("--output-dir", default="reports/m9_alpha_sensitivity_119")
    parser.add_argument("--samples", type=int, default=25)
    parser.add_argument("--allow-other-snapshot", action="store_true",
                        help="Label non-#93 data explicitly (synthetic/testing); never present it as #93.")
    args = parser.parse_args()
    report = run_benchmark(args.harmonized_parquet, args.macro_lookup, args.output_dir,
                           args.samples, allow_other_snapshot=args.allow_other_snapshot)
    print(json.dumps({"snapshot": report["snapshot"], "input_sha256": report["input_sha256"],
                      "results": [{"alpha": r["alpha"], "status": r["status"],
                                   "failure": r.get("failure")} for r in report["results"]]}, indent=2))


if __name__ == "__main__":
    main()
