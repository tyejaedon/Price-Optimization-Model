import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
except ImportError as exc:
    raise RuntimeError("Install reporting dependencies with: python -m pip install -r requirements.txt") from exc

from src.ingest_multisource import BILATERAL_ALPHA
from src.macro_arbitrage import TEXT_VECTOR_DIMENSIONS
from src.spatial_engine import DomainPartitionedKDTreeIndexer
from src.train_pipeline import (
    DEFAULT_HARMONIZED_PARQUET,
    DEFAULT_RANDOM_STATE,
    _build_category_mean_baseline,
    _fit_feature_matrices,
    _metric_summary,
    _predict_category_mean_baseline,
    _predict_idw,
    build_stratified_splits,
    inverse_target_log1p,
    load_harmonized_parquet,
    transform_target_log1p,
)

DEFAULT_REPORT_DIR = os.path.join("reports", "model_evaluation")
DEFAULT_K_VALUES = (1, 3, 5, 7, 10)
METADATA_FEATURE_NAMES = (
    "bilateral_arbitrage_factor",
    "market_saturation_score",
    "industry_relative_density",
)


def _feature_names() -> List[str]:
    return [f"text_svd_{index:02d}" for index in range(TEXT_VECTOR_DIMENSIONS)] + list(METADATA_FEATURE_NAMES)


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _fit_indexer(
    matrices: Any,
    split_data: Any,
    verified_rates: np.ndarray | None = None,
) -> DomainPartitionedKDTreeIndexer:
    indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=1)
    indexer.fit(
        hybrid_vectors=matrices.x_train,
        industry_partitions=[str(value) for value in split_data.train["industry_partition"].tolist()],
        record_indices=np.asarray(split_data.train["record_id"].to_numpy(), dtype=int).tolist(),
        verified_rates=(matrices.y_train if verified_rates is None else verified_rates).tolist(),
    )
    return indexer


def _target_summary(split_data: Any, model_metrics: Dict[str, Dict[str, float]], baseline_metrics: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for split_name, frame in (("train", split_data.train), ("validation", split_data.validation), ("test", split_data.test)):
        values = frame["target_rate"].to_numpy(dtype=float)
        row: Dict[str, Any] = {
            "split": split_name,
            "rows": int(values.size),
            "target_mean_kes": round(float(np.mean(values)), 6),
            "target_std_kes": round(float(np.std(values)), 6),
            "target_min_kes": round(float(np.min(values)), 6),
            "target_max_kes": round(float(np.max(values)), 6),
        }
        if split_name in model_metrics:
            row.update({
                "model_rmse": model_metrics[split_name]["rmse"],
                "model_r2": model_metrics[split_name]["r2"],
                "baseline_rmse": baseline_metrics[split_name]["rmse"],
                "baseline_r2": baseline_metrics[split_name]["r2"],
            })
        rows.append(row)
    return pd.DataFrame(rows)


def _independent_summary(x_train: np.ndarray, y_train: np.ndarray) -> pd.DataFrame:
    names = _feature_names()
    rows: List[Dict[str, Any]] = []
    for index, name in enumerate(names):
        values = x_train[:, index]
        correlation = 0.0 if np.std(values) == 0.0 else float(np.corrcoef(values, y_train)[0, 1])
        rows.append(
            {
                "feature_index": index,
                "feature_group": "text" if index < TEXT_VECTOR_DIMENSIONS else "metadata",
                "feature_name": name,
                "mean": round(float(np.mean(values)), 8),
                "std": round(float(np.std(values)), 8),
                "min": round(float(np.min(values)), 8),
                "max": round(float(np.max(values)), 8),
                "target_pearson_correlation": round(correlation, 8),
                "absolute_target_correlation": round(abs(correlation), 8),
            }
        )
    return pd.DataFrame(rows).sort_values("absolute_target_correlation", ascending=False).reset_index(drop=True)


def _run_k_sweep(
    indexer: DomainPartitionedKDTreeIndexer,
    matrices: Any,
    split_data: Any,
    k_values: Sequence[int],
    baseline_validation_metrics: Dict[str, float],
    baseline_test_metrics: Dict[str, float],
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    validation_partitions = [str(value) for value in split_data.validation["industry_partition"].tolist()]
    test_partitions = [str(value) for value in split_data.test["industry_partition"].tolist()]
    for k in sorted({max(1, int(value)) for value in k_values}):
        validation_predictions = _predict_idw(indexer, matrices.x_validation, validation_partitions, k)
        test_predictions = _predict_idw(indexer, matrices.x_test, test_partitions, k)
        validation_metrics = _metric_summary(matrices.y_validation, validation_predictions)
        test_metrics = _metric_summary(matrices.y_test, test_predictions)
        rows.append(
            {
                "model": "idw",
                "k_neighbors": k,
                "validation_rmse": validation_metrics["rmse"],
                "validation_mae": validation_metrics["mae"],
                "validation_median_absolute_error": validation_metrics["median_absolute_error"],
                "validation_smape_percent": validation_metrics["smape_percent"],
                "validation_r2": validation_metrics["r2"],
                "test_rmse": test_metrics["rmse"],
                "test_mae": test_metrics["mae"],
                "test_median_absolute_error": test_metrics["median_absolute_error"],
                "test_smape_percent": test_metrics["smape_percent"],
                "test_r2": test_metrics["r2"],
                "validation_rmse_improvement_vs_baseline": round(baseline_validation_metrics["rmse"] - validation_metrics["rmse"], 6),
                "test_rmse_improvement_vs_baseline": round(baseline_test_metrics["rmse"] - test_metrics["rmse"], 6),
                "validation_r2_improvement_vs_baseline": round(validation_metrics["r2"] - baseline_validation_metrics["r2"], 6),
                "test_r2_improvement_vs_baseline": round(test_metrics["r2"] - baseline_test_metrics["r2"], 6),
            }
        )
    results = pd.DataFrame(rows)
    best_index = results["validation_r2"].idxmax()
    results["best_validation_configuration"] = False
    results.loc[best_index, "best_validation_configuration"] = True
    return results


def _run_log_target_sweep(
    indexer: DomainPartitionedKDTreeIndexer,
    matrices: Any,
    split_data: Any,
    k_values: Sequence[int],
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    log_validation_targets = transform_target_log1p(matrices.y_validation)
    log_test_targets = transform_target_log1p(matrices.y_test)
    validation_partitions = [str(value) for value in split_data.validation["industry_partition"].tolist()]
    test_partitions = [str(value) for value in split_data.test["industry_partition"].tolist()]
    for k in sorted({max(1, int(value)) for value in k_values}):
        validation_log_predictions = _predict_idw(indexer, matrices.x_validation, validation_partitions, k)
        test_log_predictions = _predict_idw(indexer, matrices.x_test, test_partitions, k)
        validation_raw_predictions = inverse_target_log1p(validation_log_predictions)
        test_raw_predictions = inverse_target_log1p(test_log_predictions)
        validation_log_metrics = _metric_summary(log_validation_targets, validation_log_predictions)
        test_log_metrics = _metric_summary(log_test_targets, test_log_predictions)
        validation_raw_metrics = _metric_summary(matrices.y_validation, validation_raw_predictions)
        test_raw_metrics = _metric_summary(matrices.y_test, test_raw_predictions)
        rows.append(
            {
                "model": "idw_log1p",
                "k_neighbors": k,
                "validation_log_r2": validation_log_metrics["r2"],
                "test_log_r2": test_log_metrics["r2"],
                "validation_log_rmse": validation_log_metrics["rmse"],
                "test_log_rmse": test_log_metrics["rmse"],
                "validation_raw_r2": validation_raw_metrics["r2"],
                "test_raw_r2": test_raw_metrics["r2"],
                "validation_raw_rmse": validation_raw_metrics["rmse"],
                "test_raw_rmse": test_raw_metrics["rmse"],
                "validation_raw_mae": validation_raw_metrics["mae"],
                "test_raw_mae": test_raw_metrics["mae"],
                "validation_raw_median_absolute_error": validation_raw_metrics["median_absolute_error"],
                "test_raw_median_absolute_error": test_raw_metrics["median_absolute_error"],
                "validation_raw_smape_percent": validation_raw_metrics["smape_percent"],
                "test_raw_smape_percent": test_raw_metrics["smape_percent"],
            }
        )
    results = pd.DataFrame(rows)
    results["best_validation_log_configuration"] = False
    results.loc[results["validation_log_r2"].idxmax(), "best_validation_log_configuration"] = True
    return results
def _plot_hyperparameter_trends(results: pd.DataFrame, output_path: Path, quality_gate_r2: float) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    axes[0].plot(results["k_neighbors"], results["validation_r2"], marker="o", label="Validation R²")
    axes[0].plot(results["k_neighbors"], results["test_r2"], marker="s", label="Test R²")
    axes[0].axhline(quality_gate_r2, color="red", linestyle="--", label=f"Gate R²={quality_gate_r2:.2f}")
    axes[0].set_xlabel("k neighbors")
    axes[0].set_ylabel("R²")
    axes[0].set_title("IDW hyperparameter tuning: R² trend")
    axes[0].legend()
    axes[0].grid(alpha=0.25)

    axes[1].plot(results["k_neighbors"], results["validation_rmse"], marker="o", label="Validation RMSE")
    axes[1].plot(results["k_neighbors"], results["test_rmse"], marker="s", label="Test RMSE")
    axes[1].set_xlabel("k neighbors")
    axes[1].set_ylabel("RMSE (KES/hour)")
    axes[1].set_title("IDW hyperparameter tuning: error trend")
    axes[1].legend()
    axes[1].grid(alpha=0.25)
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def _plot_model_progress(results: pd.DataFrame, output_path: Path, baseline_metrics: Dict[str, Dict[str, float]]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    labels = [f"IDW k={int(k)}" for k in results["k_neighbors"]]
    x = np.arange(len(labels))
    width = 0.36
    axes[0].bar(x - width / 2, results["validation_r2"], width, label="IDW validation")
    axes[0].bar(x + width / 2, results["test_r2"], width, label="IDW test")
    axes[0].axhline(baseline_metrics["validation"]["r2"], color="tab:blue", linestyle=":", label="Baseline validation")
    axes[0].axhline(baseline_metrics["test"]["r2"], color="tab:orange", linestyle=":", label="Baseline test")
    axes[0].set_xticks(x, labels, rotation=35, ha="right")
    axes[0].set_ylabel("R²")
    axes[0].set_title("Model progress vs category-mean baseline")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].bar(x - width / 2, results["validation_rmse"], width, label="IDW validation")
    axes[1].bar(x + width / 2, results["test_rmse"], width, label="IDW test")
    axes[1].axhline(baseline_metrics["validation"]["rmse"], color="tab:blue", linestyle=":", label="Baseline validation")
    axes[1].axhline(baseline_metrics["test"]["rmse"], color="tab:orange", linestyle=":", label="Baseline test")
    axes[1].set_xticks(x, labels, rotation=35, ha="right")
    axes[1].set_ylabel("RMSE (KES/hour)")
    axes[1].set_title("Error progress vs category-mean baseline")
    axes[1].legend(fontsize=8)
    axes[1].grid(axis="y", alpha=0.25)
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def _plot_variable_effects(independent_summary: pd.DataFrame, target_summary: pd.DataFrame, output_path: Path) -> None:
    top_features = independent_summary.head(12).sort_values("target_pearson_correlation")
    figure, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    colors = ["tab:blue" if value >= 0 else "tab:red" for value in top_features["target_pearson_correlation"]]
    axes[0].barh(top_features["feature_name"], top_features["target_pearson_correlation"], color=colors)
    axes[0].axvline(0.0, color="black", linewidth=0.8)
    axes[0].set_xlabel("Pearson correlation with target_rate")
    axes[0].set_title("Independent-variable effects")
    axes[0].grid(axis="x", alpha=0.25)

    x = np.arange(len(target_summary))
    axes[1].bar(
        x,
        target_summary["target_mean_kes"],
        yerr=target_summary["target_std_kes"],
        capsize=5,
        color="tab:green",
        alpha=0.8,
    )
    axes[1].set_xticks(x, target_summary["split"].tolist())
    axes[1].set_ylabel("Target rate (KES/hour), mean +/- std")
    axes[1].set_title("Dependent-variable split summary")
    axes[1].grid(axis="y", alpha=0.25)
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def _plot_target_transformations(raw_results: pd.DataFrame, log_results: pd.DataFrame, output_path: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    x = np.arange(len(raw_results))
    labels = [f"k={int(value)}" for value in raw_results["k_neighbors"]]
    axes[0, 0].plot(x, raw_results["validation_r2"], marker="o", label="Raw target")
    axes[0, 0].plot(x, log_results["validation_log_r2"], marker="s", label="Log1p target, log space")
    axes[0, 0].set_title("Validation R? by target transformation")
    axes[0, 0].set_ylabel("R?")
    axes[0, 0].legend()
    axes[0, 0].grid(alpha=0.25)
    axes[0, 0].set_xticks(x, labels)
    axes[0, 1].plot(x, raw_results["test_r2"], marker="o", label="Raw target")
    axes[0, 1].plot(x, log_results["test_log_r2"], marker="s", label="Log1p target, log space")
    axes[0, 1].set_title("Test R? by target transformation")
    axes[0, 1].set_ylabel("R?")
    axes[0, 1].legend()
    axes[0, 1].grid(alpha=0.25)
    axes[0, 1].set_xticks(x, labels)
    axes[1, 0].plot(x, raw_results["validation_rmse"], marker="o", label="Raw target")
    axes[1, 0].plot(x, log_results["validation_raw_rmse"], marker="s", label="Log1p + expm1, raw KES")
    axes[1, 0].set_title("Validation RMSE in KES/hour")
    axes[1, 0].set_ylabel("RMSE")
    axes[1, 0].legend()
    axes[1, 0].grid(alpha=0.25)
    axes[1, 0].set_xticks(x, labels)
    axes[1, 1].plot(x, log_results["validation_log_rmse"], marker="s", color="tab:purple")
    axes[1, 1].set_title("Validation RMSE in log space")
    axes[1, 1].set_ylabel("RMSE(log1p target)")
    axes[1, 1].grid(alpha=0.25)
    axes[1, 1].set_xticks(x, labels)
    figure.savefig(output_path, dpi=160)
    plt.close(figure)
def _write_markdown_report(
    output_path: Path,
    config: Dict[str, Any],
    results: pd.DataFrame,
    log_results: pd.DataFrame,
    independent_summary: pd.DataFrame,
    target_summary: pd.DataFrame,
    baseline_metrics: Dict[str, Dict[str, float]],
) -> None:
    best = results.iloc[int(results["validation_r2"].idxmax())]
    lines = [
        "# Model Evaluation and Hyperparameter Tuning Report",
        "",
        f"Generated: `{config['generated_at_utc']}`",
        "",
        "## Experimental design",
        "",
        "- Independent variables: 50 text SVD coordinates, 3 normalized metadata coordinates, and `k_neighbors`.",
        "- Dependent variable: `target_rate` in KES/hour.",
        "- Split: stratified 70/15/15 train/validation/test.",
        "- Model family: inverse-distance weighting over domain-partitioned KD-Trees.",
        f"- Hyperparameter sweep: `k_neighbors = {config['k_values']}`.",
        "",
        "## Best configuration",
        "",
        f"- Best validation R²: **{best['validation_r2']:.6f}** at `k_neighbors={int(best['k_neighbors'])}`.",
        f"- Corresponding validation RMSE: **{best['validation_rmse']:.3f} KES/hour**.",
        f"- Test R² at that configuration: **{best['test_r2']:.6f}**.",
        "",
        "## Baseline comparison",
        "",
        _markdown_table(
            pd.DataFrame(
                [
                    {"split": split, **metrics, "model": "category_mean"}
                    for split, metrics in baseline_metrics.items()
                ]
            )
        ),
        "",
        "## Hyperparameter results",
        "",
        _markdown_table(results),
        "",
        "## Raw versus log1p target comparison",
        "",
        "The log1p model is evaluated in log space and after expm1 inversion into KES/hour.",
        "",
        _markdown_table(log_results),
        "",
        "## Dependent-variable summary",
        "",
        _markdown_table(target_summary),
        "",
        "## Strongest independent-variable effects",
        "",
        _markdown_table(independent_summary.head(15)),
        "",
        "## Generated diagrams",
        "",
        "- `hyperparameter_trends.png`: R² and RMSE trend across `k_neighbors`.",
        "- `model_progress.png`: tuned IDW progress against the category-mean baseline.",
        "- `variable_effects.png`: strongest feature/target correlations and split target summary.",
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_experiment_report(
    harmonized_parquet_path: str,
    macro_lookup_path: str,
    output_dir: str = DEFAULT_REPORT_DIR,
    k_values: Sequence[int] = DEFAULT_K_VALUES,
    random_state: int = DEFAULT_RANDOM_STATE,
    n_components: int = TEXT_VECTOR_DIMENSIONS,
    max_features: int = 12000,
    alpha: float = BILATERAL_ALPHA,
    quality_gate_r2: float = 0.75,
) -> Dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    frame = load_harmonized_parquet(harmonized_parquet_path)
    split_data = build_stratified_splits(frame, random_state=random_state)
    matrices = _fit_feature_matrices(
        split_data=split_data,
        macro_lookup_path=macro_lookup_path,
        n_components=n_components,
        max_features=max_features,
        alpha=alpha,
        artifact_dir=str(output_path / "artifacts"),
        save_artifacts=False,
    )
    indexer = _fit_indexer(matrices, split_data)
    log_train_targets = transform_target_log1p(matrices.y_train)
    log_indexer = _fit_indexer(matrices, split_data, verified_rates=log_train_targets)
    partition_means, global_mean = _build_category_mean_baseline(split_data.train)
    baseline_validation = _predict_category_mean_baseline(split_data.validation, partition_means, global_mean)
    baseline_test = _predict_category_mean_baseline(split_data.test, partition_means, global_mean)
    baseline_metrics = {
        "validation": _metric_summary(matrices.y_validation, baseline_validation),
        "test": _metric_summary(matrices.y_test, baseline_test),
    }
    results = _run_k_sweep(indexer, matrices, split_data, k_values, baseline_metrics["validation"], baseline_metrics["test"])
    log_results = _run_log_target_sweep(log_indexer, matrices, split_data, k_values)
    model_metrics = {
        "validation": _metric_summary(matrices.y_validation, _predict_idw(indexer, matrices.x_validation, [str(v) for v in split_data.validation["industry_partition"].tolist()], int(results.iloc[int(results["validation_r2"].idxmax())]["k_neighbors"]))),
        "test": _metric_summary(matrices.y_test, _predict_idw(indexer, matrices.x_test, [str(v) for v in split_data.test["industry_partition"].tolist()], int(results.iloc[int(results["validation_r2"].idxmax())]["k_neighbors"]))),
    }
    independent_summary = _independent_summary(matrices.x_train, matrices.y_train)
    target_summary = _target_summary(split_data, model_metrics, baseline_metrics)
    generated_at = datetime.now(timezone.utc).isoformat()
    config = {
        "generated_at_utc": generated_at,
        "k_values": [int(value) for value in sorted({max(1, int(value)) for value in k_values})],
        "random_state": int(random_state),
        "quality_gate_r2": float(quality_gate_r2),
        "input_rows": int(len(frame)),
        "split_rows": {"train": len(split_data.train), "validation": len(split_data.validation), "test": len(split_data.test)},
        "independent_variable_dimensions": int(matrices.x_train.shape[1]),
        "dependent_variable": "target_rate",
    }
    results.to_csv(output_path / "hyperparameter_results.csv", index=False)
    independent_summary.to_csv(output_path / "independent_variable_summary.csv", index=False)
    target_summary.to_csv(output_path / "dependent_variable_summary.csv", index=False)
    log_results.to_csv(output_path / "target_transformation_results.csv", index=False)
    _plot_hyperparameter_trends(results, output_path / "hyperparameter_trends.png", quality_gate_r2)
    _plot_target_transformations(results, log_results, output_path / "target_transformation_comparison.png")
    _plot_model_progress(results, output_path / "model_progress.png", baseline_metrics)
    _plot_variable_effects(independent_summary, target_summary, output_path / "variable_effects.png")
    _write_markdown_report(output_path / "experiment_report.md", config, results, log_results, independent_summary, target_summary, baseline_metrics)
    payload = {
        "config": config,
        "best_configuration": results.loc[results["validation_r2"].idxmax()].to_dict(),
        "best_log_configuration": log_results.loc[log_results["validation_log_r2"].idxmax()].to_dict(),
        "baseline_metrics": baseline_metrics,
        "target_transformation": {
            "raw": "identity",
            "log": "log1p",
            "inverse": "expm1",
        },
        "best_model_metrics": model_metrics,
        "output_dir": str(output_path),
        "files": [],
    }
    report_json_path = output_path / "experiment_report.json"
    payload["files"] = sorted(
        {path.name for path in output_path.iterdir() if path.is_file()} | {report_json_path.name}
    )
    report_json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate reproducible model tuning tables and diagrams.")
    parser.add_argument("--harmonized-parquet", default=DEFAULT_HARMONIZED_PARQUET)
    parser.add_argument("--macro-lookup", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--k-values", nargs="+", type=int, default=list(DEFAULT_K_VALUES))
    parser.add_argument("--random-state", type=int, default=DEFAULT_RANDOM_STATE)
    parser.add_argument("--n-components", type=int, default=TEXT_VECTOR_DIMENSIONS)
    parser.add_argument("--max-features", type=int, default=12000)
    parser.add_argument("--alpha", type=float, default=BILATERAL_ALPHA)
    parser.add_argument("--quality-gate-r2", type=float, default=0.75)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_experiment_report(
        harmonized_parquet_path=args.harmonized_parquet,
        macro_lookup_path=args.macro_lookup,
        output_dir=args.output_dir,
        k_values=args.k_values,
        random_state=args.random_state,
        n_components=args.n_components,
        max_features=args.max_features,
        alpha=args.alpha,
        quality_gate_r2=args.quality_gate_r2,
    )
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()

