---
name: experimental-diagram-curation
description: >-
  Runbook and design guidelines for curating, structuring, and generating informative
  empirical diagrams, evaluation charts, ablation graphs, and interpretability figures
  for academic systems documentation (specifically Chapter 5). Use when formatting
  machine learning experiment records into publication-grade visual evidence.
---

# Experimental Diagram Curation & Interpretability Skill

This skill guides the design and curation of visual diagrams and empirical graphs for Chapter 5 (*System Implementation, Testing and Evaluation*) to maximize model interpretability and satisfy university dissertation evaluation rubrics.

## 1. Required Empirical Diagram Portfolio for Chapter 5

When documenting an AI/ML research solution, generate figures covering the following core analytical views:

1. **Data Ingestion & Feature Engineering Topology:**
   - Visualizes the transformation of raw heterogeneous inputs into standardized numeric coordinate vectors.
   - Must show lexical preprocessing (tokenization, lemmatization, TF-IDF), SVD projection ($e \in \mathbb{R}^n$), macroeconomic lookup ($\beta_{ij}$), continuous metadata scaling ($\tilde{s}, \tilde{\rho}$), and tensor concatenation into $q \in \mathbb{R}^{n+3}$.

2. **Dimensionality Scree & Pareto Trade-off Frontier:**
   - Visualizes candidate latent dimensions ($n \in \{10, 25, 50, 75, 100, 150\}$) across three competing axes: Predictive Accuracy ($R^2$ score), Memory Footprint (MB), and Warm Query Latency ($P_{95}$, ms).
   - Highlights the empirical elbow at $n=50$, demonstrating why expanding dimensions yields diminishing returns and latency degradation.

3. **Multi-Model Architecture Benchmark Comparison:**
   - Compares candidate model families (Baseline Median/Mean, Ridge, KNN, HistGradientBoosting, Partitioned KD-Tree IDW) across Holdout $R^2$ and MAE.
   - Highlights the interpretability vs. accuracy frontier: while tree ensembles achieve slightly higher $R^2$ (0.844 vs 0.821), KD-Tree IDW provides exact instance-level peer comparables.

4. **Target Transformation & Residual Error Distribution:**
   - Contrasts raw target training vs. logarithmic transformation $y' = \ln(1+y)$ with exponential inversion $\text{expm1}()$.
   - Illustrates asymmetric pricing risk: under-pricing margin erosion vs. catastrophic over-pricing client alienation.

5. **Subgroup Domain Performance & Generalization:**
   - Grouped visual comparison across industry partitions (`data_ai`, `web_backend`, `mobile`, `design_creative`) displaying $R^2$ scores, sample counts ($N$), and interquartile rate spreads.

6. **Algorithmic Cold-Start Fallback Cascade Flowchart:**
   - Step-by-step decision flowchart depicting the 4-tier resolution:
     - Tier 1: Direct Partition Query ($N \ge 5$)
     - Tier 2: Sibling Taxonomy Rollup
     - Tier 3: Global Semantic Pool with Cross-Domain Penalty ($\lambda_{\text{industry}} = 1.25$)
     - Tier 4: Macroeconomic Empirical Priors

7. **Pricing Corridor & Safaricom M-Pesa Margin Protection Geometry:**
   - Graphical coordinate representation of base prediction $\hat{r}_{\text{base}}$, dynamic peer-spread interval $[r_{\min}, r_{\max}]$, and the 15-tier discrete transaction fee step-function $\tau(\hat{r}_{\text{base}})$.

8. **In-Memory Latency Budget Allocation & Percentiles:**
   - Breakdown of the $<250\text{ ms}$ budget across stages (FastAPI Ingress, TF-IDF Vectorization, SVD Projection, KD-Tree Retrieval, IDW Scoring, M-Pesa Evaluation) and percentile milestones ($P_{50}=5.25\text{ ms}, P_{95}=7.37\text{ ms}, P_{99}=7.87\text{ ms}$).

9. **Continuous MLOps Covariate Shift & Residual Drift Governance:**
   - Feedback loop illustrating async Firestore audit telemetry, Population Stability Index (PSI), Wasserstein distance, and Kolmogorov-Smirnov (KS) test triggers on rate residuals.

## 2. Visual Formatting Rules (A4 Portrait Optimization)

- **Diagram-as-Code Syntax:** Use standard GitHub-compatible Mermaid (`flowchart TD`, `xychart-beta`, or `graph TD`) or PlantUML.
- **Vertical Orientation (`TD` / `TB`):** A4 portrait pages in Microsoft Word have an effective width of approximately 6.27 inches (160 mm). Restrict wide horizontal branching (`flowchart LR`) to avoid text truncation or tiny downscaling.
- **Color Palette & Styling:** Use restrained, academic high-contrast monochrome or muted monochromatic tones. Avoid bright, neon fills.
