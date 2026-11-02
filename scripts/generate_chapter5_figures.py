#!/usr/bin/env python3
"""Generate Chapter 5 thesis figures as SVG and high-resolution PNG.

Produces:
- docs/figures/fig5_2_coordinate_fusion_pipeline.svg and .png (M15.2, Issue #183)
"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = REPO_ROOT / "docs" / "figures"


def generate_figure_5_2():
    """Figure 5.2: Multi-source heterogeneous data ingestion and 53D coordinate fusion pipeline."""
    fig, ax = plt.subplots(figsize=(13, 7.5), dpi=300)
    ax.axis("off")

    # Background canvas styling
    ax.set_facecolor("#FAFAFA")
    fig.patch.set_facecolor("#FAFAFA")

    # Title & Subtitle
    ax.text(
        0.5, 0.96,
        "Figure 5.2: Multi-Source Heterogeneous Ingestion & 53-Dimensional Coordinate Fusion Pipeline",
        ha="center", va="center", fontsize=13, fontweight="bold", color="#1F2937",
        transform=ax.transAxes,
    )
    ax.text(
        0.5, 0.92,
        r"Mathematical transformation from raw corpora to $q = [v_{\mathrm{text}} \parallel v_{\mathrm{meta}}] \in \mathbb{R}^{53}$ satisfying FR-01, FR-02, and FR-03",
        ha="center", va="center", fontsize=10, fontstyle="italic", color="#4B5563",
        transform=ax.transAxes,
    )

    # Box styles
    data_box_kw = dict(boxstyle="round,pad=0.5", facecolor="#EBF5FF", edgecolor="#2563EB", lw=1.5)
    pipe_box_kw = dict(boxstyle="round,pad=0.5", facecolor="#FEF3C7", edgecolor="#D97706", lw=1.5)
    fuse_box_kw = dict(boxstyle="round,pad=0.6", facecolor="#DCFCE7", edgecolor="#16A34A", lw=2.0)
    target_box_kw = dict(boxstyle="round,pad=0.5", facecolor="#F3E8FF", edgecolor="#9333EA", lw=1.5)

    # Layer 1: Data Sources (Left, x ~ 0.04 to 0.22)
    sources = [
        ("Upwork Freelance Corpus\n(22,677 unconstrained jobs;\nskills, title, client country)", 0.76),
        ("Career Mentor OS Sandbox\n(222 mentors, 52 in-scope;\nverified completed sessions)", 0.52),
        ("World Bank & Numbeo Data\n(GDP per capita, CoL indices,\nKE pivot exchange rates)", 0.26),
    ]

    for label, y in sources:
        ax.text(
            0.13, y, label, ha="center", va="center", fontsize=8.5, color="#1E3A8A",
            bbox=data_box_kw, transform=ax.transAxes, multialignment="center"
        )

    # Layer 2: Pipeline Intermediate Transformations (Middle, x ~ 0.43)
    # Text pipeline branch
    ax.text(
        0.44, 0.76,
        "Text Preprocessing & SVD\n• Token clean & regex strip\n• TF-IDF Vectorizer (8,000 terms)\n• TruncatedSVD → $v_{\mathrm{text}} \in \mathbb{R}^{50}$",
        ha="center", va="center", fontsize=8.5, color="#78350F",
        bbox=pipe_box_kw, transform=ax.transAxes, multialignment="left"
    )

    # Target normalization branch
    ax.text(
        0.44, 0.52,
        "Target Label Calibration\n• Out-of-scope vocational filter\n• Bilateral arbitrage factor ($A_{ij}$)\n• Rate normalization (KES/hr)",
        ha="center", va="center", fontsize=8.5, color="#78350F",
        bbox=pipe_box_kw, transform=ax.transAxes, multialignment="left"
    )

    # Macro normalizer branch
    ax.text(
        0.44, 0.26,
        "Continuous Metadata Scaler\n• Bilateral factor: $A_{ij} = (C_i/C_j)^{\\alpha}$\n• Market saturation & density\n• RobustScaler → $v_{\mathrm{meta}} \in \mathbb{R}^3$",
        ha="center", va="center", fontsize=8.5, color="#78350F",
        bbox=pipe_box_kw, transform=ax.transAxes, multialignment="left"
    )

    # Layer 3: Coordinate Fusion Hub (Right-Center, x ~ 0.74)
    ax.text(
        0.75, 0.51,
        "53-Dimensional Coordinate Fusion\n"
        r"$q = [v_{\mathrm{text}} \parallel v_{\mathrm{meta}}] \in \mathbb{R}^{53}$" + "\n"
        r"$\bullet\ 50\text{D Latent Semantic Text Embedding}$" + "\n"
        r"$\bullet\ 3\text{D Scaled Macroeconomic Metadata}$" + "\n"
        r"• Unit-variance cross-space alignment",
        ha="center", va="center", fontsize=9, fontweight="bold", color="#14532D",
        bbox=fuse_box_kw, transform=ax.transAxes, multialignment="center"
    )

    # Layer 4: Output Domain Partitioned KD-Tree Indexer (Right, x ~ 0.94)
    ax.text(
        0.75, 0.16,
        "Partitioned KD-Tree Indexer & IDW\n"
        "• 8 Industry Domains ($D_1 \dots D_8$)\n"
        "• Cold-start fallback cascade\n"
        "• Tariff-bounded pricing quote",
        ha="center", va="center", fontsize=8.5, color="#581C87",
        bbox=target_box_kw, transform=ax.transAxes, multialignment="center"
    )

    # Connecting Arrows
    arrow_kw = dict(arrowstyle="->", lw=1.5, color="#4B5563", shrinkA=8, shrinkB=8)
    arrow_bold = dict(arrowstyle="->", lw=2.0, color="#16A34A", shrinkA=8, shrinkB=8)

    # Source -> Transformation
    ax.annotate("", xy=(0.33, 0.76), xytext=(0.23, 0.76), xycoords="axes fraction", arrowprops=arrow_kw)
    ax.annotate("", xy=(0.33, 0.52), xytext=(0.23, 0.52), xycoords="axes fraction", arrowprops=arrow_kw)
    ax.annotate("", xy=(0.33, 0.26), xytext=(0.23, 0.26), xycoords="axes fraction", arrowprops=arrow_kw)

    # Upwork to target branch as well
    ax.annotate("", xy=(0.33, 0.56), xytext=(0.23, 0.72), xycoords="axes fraction", arrowprops=arrow_kw)

    # Transformations -> Coordinate Fusion Hub
    ax.annotate("", xy=(0.63, 0.59), xytext=(0.55, 0.74), xycoords="axes fraction", arrowprops=arrow_bold)
    ax.annotate("", xy=(0.63, 0.43), xytext=(0.55, 0.28), xycoords="axes fraction", arrowprops=arrow_bold)

    # Target branch feeds into KD-Tree rates
    ax.annotate("", xy=(0.75, 0.23), xytext=(0.55, 0.50), xycoords="axes fraction", arrowprops=arrow_kw)

    # Fusion Hub -> Partitioned Indexer
    ax.annotate("", xy=(0.75, 0.23), xytext=(0.75, 0.39), xycoords="axes fraction", arrowprops=arrow_bold)

    # Footnote badges
    ax.text(
        0.05, 0.04,
        "[FR-01: Heterogeneous Upwork & Platform Ingestion]   "
        "[FR-02: 50D TF-IDF + Truncated SVD]   "
        "[FR-03: Macro Scaler & 53D Hybrid Vector]",
        ha="left", va="center", fontsize=8, color="#6B7280", transform=ax.transAxes,
    )

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = FIGURES_DIR / "fig5_2_coordinate_fusion_pipeline.svg"
    png_path = FIGURES_DIR / "fig5_2_coordinate_fusion_pipeline.png"

    plt.tight_layout()
    plt.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.savefig(png_path, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Exported: {svg_path} and {png_path}")


if __name__ == "__main__":
    generate_figure_5_2()
