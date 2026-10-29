"""Price Optimization Model - Interactive Demonstration Script.

Demonstrates end-to-end model inference:
1. NLP semantic representation (TF-IDF + TruncatedSVD dimensionality reduction)
2. Macroeconomic arbitrage & continuous feature normalization (bilateral GDP/PPP, CoL)
3. Domain-partitioned KD-Tree spatial nearest-neighbor search & Inverse Distance Weighting (IDW)
4. Corridors & Kenya M-Pesa tariff surcharge integration
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.api_contracts import PricingQueryDTO
from src.api.serve import InferenceRuntime
from src.core.artifact_contract import file_sha256


DEFAULT_EXPORT_DIR = PROJECT_ROOT / "artifacts" / "exports" / "issue-70-2026-10-05"
DEFAULT_TARIFF_CSV = PROJECT_ROOT / "config" / "tariffs" / "mpesa_p2p_users_2026-08-04.csv"
FALLBACK_TARIFF_CSV = PROJECT_ROOT / "tests" / "fixtures" / "raw" / "Mpesa_Tarrifs" / "tarrifs_full_schedule.csv"


def load_demo_runtime(export_dir: Path | None = None) -> InferenceRuntime:
    export_path = export_dir or DEFAULT_EXPORT_DIR
    manifest_file = export_path / "artifact_manifest.json"

    if not manifest_file.is_file():
        raise FileNotFoundError(f"Artifact manifest not found at {manifest_file}")

    manifest_hash = file_sha256(str(manifest_file))
    macro_lookup = export_path / "macro_lookup_table.json"

    tariff_csv = DEFAULT_TARIFF_CSV if DEFAULT_TARIFF_CSV.is_file() else FALLBACK_TARIFF_CSV
    if not tariff_csv.is_file():
        raise FileNotFoundError(f"Tariff schedule not found at {tariff_csv}")

    print(f"[*] Loading model artifacts from: {export_path}")
    print(f"[*] Pinned Artifact Manifest SHA256: {manifest_hash[:16]}...{manifest_hash[-8:]}")
    print(f"[*] Tariff Schedule: {tariff_csv.name}")

    runtime = InferenceRuntime(
        artifact_dir=str(export_path),
        macro_lookup_path=str(macro_lookup),
        tariff_csv_path=str(tariff_csv),
        trusted_manifest_sha256=manifest_hash,
    )
    runtime.load()

    if not runtime.models_loaded:
        raise RuntimeError(f"Failed to load models: {runtime.load_error}")

    print("[+] All model components successfully verified and loaded into memory!\n")
    return runtime


def run_demonstration(runtime: InferenceRuntime, query: PricingQueryDTO, scenario_title: str):
    print("=" * 80)
    print(f" SCENARIO: {scenario_title.upper()}")
    print("=" * 80)
    print(f"  • Profile Description : {query.raw_description}")
    print(f"  • Industry Domain     : {query.selected_industry}")
    print(f"  • Cross-Border Trade  : {query.mentor_country} (Mentor) -> {query.client_country} (Client)")
    print(f"  • Competitiveness     : {query.competitiveness_score:.2f}")
    print(f"  • Market Saturation   : {query.market_saturation_score:.2f}")
    if query.base_rate_floor:
        print(f"  • Reservation Floor   : KES {query.base_rate_floor:,.2f}/hr")
    print("-" * 80)

    prediction = runtime.predict(query)

    print("\n[+] 1. NEAREST NEIGHBOR PEER MATCHES (53-Dimensional Metric Space):")
    print(f"    {'Rank':<5} {'Peer Idx':<10} {'Distance':<10} {'Similarity':<12} {'IDW Weight':<12} {'Peer Rate (KES/hr)':<20}")
    print("    " + "-" * 70)
    for rank, peer in enumerate(prediction.nearest_neighbors, start=1):
        idw = f"{peer.idw_weight:.4f}" if peer.idw_weight is not None else "N/A"
        print(f"    {rank:<5} {peer.peer_index:<10} {peer.distance:<10.4f} {peer.similarity_score:<12.4f} {idw:<12} KES {peer.verified_rate:>12,.2f}")

    print("\n[+] 2. PRICING OPTIMIZATION & SYNTHESIS BREAKDOWN:")
    if prediction.bilateral_arbitrage_factor is not None:
        print(f"    • Bilateral Macro Factor      : {prediction.bilateral_arbitrage_factor:.4f}x")
    print(f"    • Synthesized Base Rate       : KES {prediction.base_predicted_rate:,.2f}/hr")
    if prediction.min_quoted_rate is not None and prediction.max_quoted_rate is not None:
        print(f"    • Recommended Corridor [Min]  : KES {prediction.min_quoted_rate:,.2f}/hr")
        print(f"    • Recommended Corridor [Max]  : KES {prediction.max_quoted_rate:,.2f}/hr")
    print(f"    • M-Pesa Tariff Surcharge     : KES {prediction.mpesa_tariff_surcharge:,.2f}")
    print("    " + "=" * 45)
    print(f"    >>> FINAL OPTIMIZED QUOTE     : KES {prediction.final_quoted_rate:,.2f}/hr <<<")
    print("    " + "=" * 45 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Price Optimization Model Demo")
    parser.add_argument("--artifacts", type=str, default=None, help="Path to exported artifacts directory")
    args = parser.parse_args()

    runtime = load_demo_runtime(Path(args.artifacts) if args.artifacts else None)

    scenarios = [
        (
            "Senior Backend Engineer (Kenya -> United States)",
            PricingQueryDTO(
                raw_description="Senior Python Backend API Engineer specializing in FastAPI, microservices, distributed caching, and PostgreSQL database optimization.",
                selected_industry="web_backend",
                mentor_country="KE",
                client_country="US",
                competitiveness_score=0.85,
                market_saturation_score=0.35,
                base_rate_floor=5000.0,
            ),
        ),
        (
            "Machine Learning / NLP Specialist (Kenya -> United Kingdom)",
            PricingQueryDTO(
                raw_description="Senior Machine Learning Specialist with hands-on experience deploying PyTorch models, transformer fine-tuning, vector search, and production MLOps pipelines.",
                selected_industry="data_science",
                mentor_country="KE",
                client_country="GB",
                competitiveness_score=0.90,
                market_saturation_score=0.25,
                base_rate_floor=6500.0,
            ),
        ),
        (
            "Local Full-Stack Developer (Kenya -> Kenya Domestic)",
            PricingQueryDTO(
                raw_description="Full-stack web application developer building responsive TypeScript React frontends and Node.js REST APIs for regional enterprise clients.",
                selected_industry="web_backend",
                mentor_country="KE",
                client_country="KE",
                competitiveness_score=0.60,
                market_saturation_score=0.50,
                base_rate_floor=2000.0,
            ),
        ),
    ]

    for title, query in scenarios:
        run_demonstration(runtime, query, title)


if __name__ == "__main__":
    main()
