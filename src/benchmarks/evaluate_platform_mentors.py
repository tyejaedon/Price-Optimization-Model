"""Empirical evaluation of pricing model quotes against platform mentor corpus.

Supervisor Guidance:
"(4) R² 0.48 against your own 0.75 gate is fine if you say so plainly;
the number the examiner will want is your quotes against the 52 in-scope
mentors' listed and realised rates in that corpus — nobody has run it yet."

This script runs the pinned inference runtime against the in-scope platform mentors,
evaluating both the initial 52-mentor cohort (from the first 222 mentors) and the full
92-mentor corpus against both listed hourly rates and realised hourly rates.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.api.api_contracts import PricingQueryDTO
from src.api.serve import InferenceRuntime
from src.engine.macro_arbitrage import DEFAULT_MACRO_LOOKUP
from src.engine.tariff_evaluator import DEFAULT_MPESA_TARIFF_CSV

DEFAULT_CORPUS_CSV = os.path.join("data", "processed", "platform_mentor_corpus.csv")
DEFAULT_RAW_MENTORS_CSV = os.path.join("data", "raw", "career_mentor_os", "mentors.csv")
DEFAULT_ARTIFACT_DIR = os.path.join("artifacts", "exports", "issue-70-2026-10-05")
DEFAULT_MANIFEST_SHA256 = "d16876fbf055650d0dd41a69332eef8d66ca38a6d728b1828a30fba133f3e87f"


def calculate_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute standard regression metrics."""
    if len(y_true) == 0:
        return {}
    errors = y_pred - y_true
    abs_errors = np.abs(errors)
    mae = float(np.mean(abs_errors))
    median_ae = float(np.median(abs_errors))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    mean_error = float(np.mean(errors))
    
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    ss_res = float(np.sum(errors ** 2))
    r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else float("nan")
    
    # Pearson correlation
    if len(y_true) > 1 and np.std(y_true) > 0 and np.std(y_pred) > 0:
        corr = float(np.corrcoef(y_true, y_pred)[0, 1])
    else:
        corr = float("nan")

    return {
        "count": len(y_true),
        "mean_true": float(np.mean(y_true)),
        "mean_pred": float(np.mean(y_pred)),
        "mean_error": mean_error,
        "mae": mae,
        "median_ae": median_ae,
        "rmse": rmse,
        "r2": r2,
        "pearson_r": corr,
    }


def evaluate_platform_corpus(
    corpus_csv_path: str = DEFAULT_CORPUS_CSV,
    raw_mentors_csv_path: Optional[str] = DEFAULT_RAW_MENTORS_CSV,
    artifact_dir: str = DEFAULT_ARTIFACT_DIR,
    trusted_manifest_sha256: str = DEFAULT_MANIFEST_SHA256,
    macro_lookup_path: str = DEFAULT_MACRO_LOOKUP,
    tariff_csv_path: str = DEFAULT_MPESA_TARIFF_CSV,
) -> Dict[str, Any]:
    """Execute evaluation and return comprehensive metric breakdown."""
    if not os.path.exists(corpus_csv_path):
        raise FileNotFoundError(f"Corpus file not found: {corpus_csv_path}")

    df = pd.read_csv(corpus_csv_path)

    # Initialize runtime
    runtime = InferenceRuntime(
        artifact_dir=artifact_dir,
        macro_lookup_path=macro_lookup_path,
        tariff_csv_path=tariff_csv_path,
        trusted_manifest_sha256=trusted_manifest_sha256,
    )
    runtime.load()
    if not runtime.models_loaded:
        raise RuntimeError(f"Failed to load inference runtime: {runtime.load_error}")

    # Quote each mentor
    quotes = []
    base_rates = []
    surcharges = []
    corridor_mins = []
    corridor_maxs = []

    for _, row in df.iterrows():
        query = PricingQueryDTO(
            raw_description=str(row["raw_description"]),
            selected_industry=str(row["industry_partition"]),
            mentor_country="KE",
            client_country="KE",
        )
        prediction = runtime.predict(query)
        quotes.append(prediction.final_quoted_rate)
        base_rates.append(prediction.base_predicted_rate)
        surcharges.append(prediction.mpesa_tariff_surcharge)
        corridor_mins.append(prediction.min_quoted_rate)
        corridor_maxs.append(prediction.max_quoted_rate)

    df["model_quoted_rate"] = quotes
    df["base_predicted_rate"] = base_rates
    df["mpesa_tariff_surcharge"] = surcharges
    df["min_quoted_rate"] = corridor_mins
    df["max_quoted_rate"] = corridor_maxs

    # Identify the initial 52-mentor cohort (from first 222 mentors in raw dataset)
    if raw_mentors_csv_path and os.path.exists(raw_mentors_csv_path):
        raw_df = pd.read_csv(raw_mentors_csv_path)
        first_222_ids = set(raw_df.iloc[:222]["mentor_user_id"])
        df["is_first_cohort"] = df["platform_mentor_user_id"].isin(first_222_ids)
    else:
        df["is_first_cohort"] = False

    cohort_52_df = df[df["is_first_cohort"]].copy()

    def run_cohort_evaluation(eval_df: pd.DataFrame, label: str) -> Dict[str, Any]:
        y_true_listed = eval_df["listed_hourly_rate_kes"].to_numpy(dtype=float)
        y_pred = eval_df["model_quoted_rate"].to_numpy(dtype=float)
        listed_metrics = calculate_regression_metrics(y_true_listed, y_pred)

        # Realised rates evaluation
        realised_mask = eval_df["realised_hourly_rate_kes"].notna()
        df_realised = eval_df[realised_mask]
        if len(df_realised) > 0:
            y_true_realised = df_realised["realised_hourly_rate_kes"].to_numpy(dtype=float)
            y_pred_realised = df_realised["model_quoted_rate"].to_numpy(dtype=float)
            realised_metrics = calculate_regression_metrics(y_true_realised, y_pred_realised)
        else:
            realised_metrics = {}

        # Partition breakdowns
        by_partition = {}
        for partition, group in eval_df.groupby("industry_partition"):
            p_y_true = group["listed_hourly_rate_kes"].to_numpy(dtype=float)
            p_y_pred = group["model_quoted_rate"].to_numpy(dtype=float)
            by_partition[str(partition)] = calculate_regression_metrics(p_y_true, p_y_pred)

        # Corridor containment
        in_corridor = (
            (eval_df["listed_hourly_rate_kes"] >= eval_df["min_quoted_rate"])
            & (eval_df["listed_hourly_rate_kes"] <= eval_df["max_quoted_rate"])
        )
        corridor_coverage = float(np.mean(in_corridor))

        return {
            "label": label,
            "sample_size": len(eval_df),
            "listed_rate_metrics": listed_metrics,
            "realised_rate_metrics": realised_metrics,
            "partition_breakdown": by_partition,
            "corridor_coverage": corridor_coverage,
        }

    results = {
        "full_corpus_92": run_cohort_evaluation(df, "Full In-Scope Corpus (N=92)"),
    }
    if len(cohort_52_df) > 0:
        results["cohort_52"] = run_cohort_evaluation(cohort_52_df, f"First-Batch Cohort (N={len(cohort_52_df)})")

    return results


def format_markdown_report(results: Dict[str, Any]) -> str:
    """Format evaluation results into publication-grade Markdown."""
    lines = [
        "# Empirical Evaluation: Pricing Model Quotes vs Platform Mentor Corpus",
        "",
        "> **Examiner Evaluation Report:** Evaluation of the canonical KD-Tree/IDW pricing engine against",
        "> real Career Mentor OS mentor profiles from staging API dataset `career_mentor_os_sandbox`.",
        "",
        "## 1. Executive Summary & Context",
        "",
        "- **Training Baseline**: The model was trained on Upwork and freelance marketplace data with an R² of ~0.48",
        "  on out-of-time (OOT) validation (against an internal heuristic target gate of 0.75).",
        "- **Target Platform Truth**: The platform operates with Kenyan mentors charging local rates (in KES).",
        "- **Scope Separation**: Vocational mentors (construction, culinary, welding, etc.) are explicitly excluded",
        "  from the technical model scope to prevent domain distortion. This evaluation scores the model *only*",
        "  against valid in-scope technical and professional mentors.",
        "",
    ]

    for key, data in results.items():
        label = data["label"]
        n = data["sample_size"]
        listed = data["listed_rate_metrics"]
        realised = data["realised_rate_metrics"]
        cov = data["corridor_coverage"]

        lines.extend([
            f"---",
            f"## {label}",
            "",
            f"### A. Evaluation against Listed Rates (What Mentors Ask, N={n})",
            "",
            f"| Metric | Value |",
            f"| --- | --- |",
            f"| **Sample Size ($N$)** | {n} |",
            f"| **Mean Listed Rate** | KES {listed['mean_true']:.2f}/hr |",
            f"| **Mean Model Quote** | KES {listed['mean_pred']:.2f}/hr |",
            f"| **Mean Error (Bias)** | KES {listed['mean_error']:+.2f}/hr |",
            f"| **Mean Absolute Error (MAE)** | KES {listed['mae']:.2f}/hr |",
            f"| **Median Absolute Error (MedAE)** | KES {listed['median_ae']:.2f}/hr |",
            f"| **Root Mean Squared Error (RMSE)** | KES {listed['rmse']:.2f}/hr |",
            f"| **$R^2$ Score** | {listed['r2']:.4f} |",
            f"| **Pearson Correlation ($r$)** | {listed['pearson_r']:.4f} |",
            f"| **Pricing Corridor Coverage** | {cov * 100:.1f}% |",
            "",
        ])

        if realised and realised.get("count", 0) > 0:
            lines.extend([
                f"### B. Evaluation against Realised Rates (Completed Bookings, N={realised['count']})",
                "",
                f"| Metric | Value |",
                f"| --- | --- |",
                f"| **Sample Size with Bookings ($N$)** | {realised['count']} |",
                f"| **Mean Realised Rate** | KES {realised['mean_true']:.2f}/hr |",
                f"| **Mean Model Quote** | KES {realised['mean_pred']:.2f}/hr |",
                f"| **Mean Error (Bias)** | KES {realised['mean_error']:+.2f}/hr |",
                f"| **Mean Absolute Error (MAE)** | KES {realised['mae']:.2f}/hr |",
                f"| **Median Absolute Error (MedAE)** | KES {realised['median_ae']:.2f}/hr |",
                f"| **Root Mean Squared Error (RMSE)** | KES {realised['rmse']:.2f}/hr |",
                f"| **$R^2$ Score** | {realised['r2']:.4f} |",
                f"| **Pearson Correlation ($r$)** | {realised['pearson_r']:.4f} |",
                "",
            ])

        lines.extend([
            f"### C. Partition Breakdown (Listed Rates)",
            "",
            f"| Industry Partition | N | Mean Listed (KES) | Mean Quote (KES) | MAE (KES) | RMSE (KES) | R² |",
            f"| --- | --- | --- | --- | --- | --- | --- |",
        ])
        for part, p_met in data["partition_breakdown"].items():
            lines.append(
                f"| `{part}` | {p_met['count']} | {p_met['mean_true']:.1f} | {p_met['mean_pred']:.1f} | "
                f"{p_met['mae']:.1f} | {p_met['rmse']:.1f} | {p_met['r2']:.4f} |"
            )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate pricing model quotes against platform mentor corpus.")
    parser.add_argument("--corpus-csv", default=DEFAULT_CORPUS_CSV, help="Path to platform mentor corpus CSV.")
    parser.add_argument("--raw-mentors-csv", default=DEFAULT_RAW_MENTORS_CSV, help="Path to raw mentors CSV.")
    parser.add_argument("--output-report", default="reports/m15_platform_mentor_evaluation.md", help="Report file.")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output_report), exist_ok=True)
    results = evaluate_platform_corpus(
        corpus_csv_path=args.corpus_csv,
        raw_mentors_csv_path=args.raw_mentors_csv,
    )
    report_text = format_markdown_report(results)
    with open(args.output_report, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(report_text)
    print(f"\n[OK] Report saved to {args.output_report}")


if __name__ == "__main__":
    main()
