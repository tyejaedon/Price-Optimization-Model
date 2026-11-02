# Chapter 5: System Implementation, Testing and Evaluation

## 5.1 Overview
This chapter details the concrete system implementation, empirical testing, and rigorous evaluation of the data-driven price optimization model designed for technical mentorship in Kenya's digital economy. The system bridges unstructured professional profiles and localized economic transaction reality through a multi-stage machine learning pipeline.

---

## 5.2 Multi-Source Ingestion & Coordinate Fusion Pipeline

The core architectural requirement of the pricing system (FR-01, FR-02, and FR-03) is to ingest heterogeneous freelance and platform data sources and transform them into a unified, metric geometric space where peer proximity reflects true economic substitutability.

### 5.2.1 Heterogeneous Data Sources (FR-01)
The model synthesizes three distinct layers of data:
1. **International Freelance Marketplace Corpus (Upwork):** 22,677 unconstrained international job records capturing unstructured text job descriptions, explicit skill requirements, and cross-border budgets.
2. **Career Mentor OS Platform Corpus:** 222 empirical mentor profiles from the Kenya deployment. While 170 vocational mentors (e.g., culinary, agriculture, automotive, beauty, construction) are explicitly quarantined outside the model's domain boundaries, exactly 52 in-scope technical mentors across 7 digital partitions provide ground-truth listed reservation rates and realized earnings from completed bookings.
3. **Macroeconomic Indicators (World Bank & Numbeo):** Bilateral cost-of-living indices ($C_i, C_j$) and real purchasing power parity ratios between client source countries and Kenyan mentors.

### 5.2.2 Latent Semantic Text Embedding (FR-02)
Unstructured profile text (biographies, skill lists, domain descriptions) undergoes lowercasing, regex tokenization, and scikit-learn TF-IDF vectorization across an 8,000-feature vocabulary. The resulting sparse representation is projected into a compact latent semantic space via Truncated Singular Value Decomposition (SVD):
$$v_{\mathrm{text}} = \mathrm{SVD}_{50}(\mathrm{TFIDF}(\mathrm{text})) \in \mathbb{R}^{50}$$
This orthogonal subspace projection filters lexical noise while capturing high-order semantic affinities (e.g., grouping "fastapi", "django", and "backend postgresql" into shared geometric neighborhoods).

### 5.2.3 Macroeconomic Metadata Normalization (FR-03)
Simultaneously, macro features are extracted and normalized via `ContinuousMetadataNormalizer`:
1. **Damped Bilateral Arbitrage Factor ($A_{ij}$):** Modeled with dampening exponent $\alpha = 0.5$ to prevent hyper-inflated quotes on high-arbitrage international corridors:
   $$A_{ij} = \left(\frac{C_{\mathrm{client}}}{C_{\mathrm{mentor}}}\right)^{\alpha}$$
2. **Market Saturation Score:** Localized supply pressure indicator $S_m \in [0, 1]$.
3. **Industry Relative Density:** Empirical mentor concentration within the target technical partition.

These three continuous features are scaled using a robust median-IQR scaler fitted strictly on training splits to prevent data leakage:
$$v_{\mathrm{meta}} = \mathrm{RobustScaler}([A_{ij}, S_m, D_{\mathrm{ind}}]) \in \mathbb{R}^3$$

### 5.2.4 53-Dimensional Coordinate Fusion
The final query representation concatenates text embeddings and macro coordinates into an immutable 53-dimensional coordinate:
$$q = [v_{\mathrm{text}} \parallel v_{\mathrm{meta}}] \in \mathbb{R}^{53}$$
Unit-variance scaling guarantees that distance metrics in $\mathbb{R}^{53}$ balance semantic task specialization against macroeconomic cross-border realities without either component dominating nearest-neighbor indexing.

```mermaid
flowchart TD
    subgraph Data_Sources ["Heterogeneous Data Sources (FR-01)"]
        D1["Upwork Freelance Corpus<br/>(22,677 unconstrained jobs)"]
        D2["Career Mentor OS Corpus<br/>(222 mentors, 52 in-scope)"]
        D3["Macroeconomic Sources<br/>(World Bank & Numbeo CoL)"]
    end

    subgraph Text_Pipeline ["Text Preprocessing & SVD (FR-02)"]
        T1["Text Sanitization & Tokenization"]
        T2["TF-IDF Vectorizer (8,000 terms)"]
        T3["Truncated SVD Projection<br/>v_text ∈ ℝ⁵⁰"]
        T1 --> T2 --> T3
    end

    subgraph Macro_Pipeline ["Continuous Metadata Normalization (FR-03)"]
        M1["Damped Bilateral Arbitrage (α=0.5)"]
        M2["Market Saturation & Density"]
        M3["RobustScaler (Leakage-Safe)<br/>v_meta ∈ ℝ³"]
        M1 --> M3
        M2 --> M3
    end

    subgraph Fusion ["Hybrid Coordinate Fusion"]
        F1["q = [v_text ∥ v_meta] ∈ ℝ⁵³<br/>50D Semantic + 3D Macro Coordinates"]
    end

    subgraph Output_Engine ["Partitioned Spatial Engine"]
        E1["DomainPartitionedKDTreeIndexer<br/>(8 Industry Partitions)"]
        E2["Cold-Start Fallback Cascade"]
        E3["Tariff-Bounded Quote Synthesis"]
        E1 --> E2 --> E3
    end

    D1 --> T1
    D2 --> T1
    D3 --> M1
    D2 --> M2
    T3 --> F1
    M3 --> F1
    F1 --> E1
```

![Figure 5.2: Multi-Source Heterogeneous Ingestion & 53-Dimensional Coordinate Fusion Pipeline](figures/fig5_2_coordinate_fusion_pipeline.png)

*Figure 5.2: Architectural flow diagram detailing heterogeneous data extraction, text vectorization, damped macroeconomic scaling, and coordinate concatenation into the immutable 53-dimensional vector space $q \in \mathbb{R}^{53}$.*

---

## 5.3 Model Architecture Benchmarking & Empirical Optimization

### 5.3.1 Latent SVD Dimensionality & Pareto Frontier Analysis (NFR-01)
A central architectural question addressed during model formulation is the dimensionality of the latent semantic text representation $v_{\mathrm{text}} \in \mathbb{R}^n$. In accordance with non-functional requirement NFR-01 (strict inference latency budgets $P_{95} < 250\text{ ms}$ on containerized hosts) and memory efficiency constraints, candidate dimensionalities $n \in \{10, 25, 50, 75, 100, 150\}$ were evaluated across Holdout $R^2$, $P_{95}$ latency, and memory footprint.

Empirical evaluations across the 22,677-row benchmark revealed a pronounced scree elbow at $n = 50$:
- At $n = 10$, explained text variance is limited to $8.57\%$, yielding an exploratory $R^2 = 0.412$.
- At $n = 25$, cumulative variance reaches $12.35\%$ ($R^2 = 0.463$, latency $4.62\text{ ms}$, RAM $14.8\text{ MB}$).
- At **$n = 50$ (Optimal Elbow)**, cumulative explained variance reaches **$17.23\%$**, achieving a Holdout $R^2 \approx 0.4801$, single-threaded $P_{95}$ latency of **$5.25\text{ ms}$**, and a compact memory footprint of **$18.4\text{ MB}$**. The marginal variance gain per dimension is $0.181\%/\text{dim}$.
- Beyond $n = 50$ ($n = 75, 100, 150$), diminishing returns dominate: marginal variance gain drops to $0.127\%/\text{dim}$ while $R^2$ plateaus asymptotically between $0.484$ and $0.486$. Crucially, higher dimensions induce Euclidean distance dilution in high-dimensional spatial retrieval, degrade peer retrieval Jaccard stability, and elevate query latencies to $10.95\text{ ms}$ ($+108\%$) and memory footprint to $39.2\text{ MB}$ ($+113\%$).

```mermaid
xychart-beta
    title "Figure 5.3: Cumulative Explained Variance vs Latent SVD Dimensions"
    x-axis [10, 25, 50, 75, 100, 150]
    y-axis "Cumulative Variance (%)" 0 --> 35
    line [8.57, 12.35, 17.23, 21.14, 24.32, 28.60]
```

![Figure 5.3: Latent SVD Dimensionality Scree Elbow & Pareto Frontier Trade-Offs](figures/fig5_3_svd_dimensionality_pareto.png)

*Figure 5.3: Scree plot of cumulative explained text variance and Pareto frontier trade-offs illustrating the optimal engineering elbow at $n=50$ dimensions ($R^2 \approx 0.4801$, $P_{95}\text{ latency} = 5.25\text{ ms}$, memory $= 18.4\text{ MB}$).*

### 5.3.2 Model Architecture Benchmark & Algorithmic Selection
To establish empirical baseline validity, the proposed **Domain-Partitioned KD-Tree with Inverse Distance Weighting (IDW)** was benchmarked against competing regression families over the unified 53-dimensional coordinate space:

| Model Architecture Family | Holdout $R^2$ | RMSE (KES/hr) | MAE (KES/hr) | Inference Latency ($P_{95}$) | Instance Peer Explainability | Production Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Category-Mean Baseline** | 0.0441 | 31,438.21 | 21,399.04 | $< 1\text{ ms}$ | None (Global Average) | Naive Comparator |
| **Ridge Regression ($\alpha=10.0$)** | 0.3809 | 24,962.33 | 14,891.45 | $1.2\text{ ms}$ | Global Feature Weights | Linear Baseline |
| **K-Neighbors Regressor ($k=10$)** | 0.4419 | 23,695.12 | 14,180.20 | $8.4\text{ ms}$ | High (Global Neighbors) | Unpartitioned Spatial |
| **HistGradientBoostingRegressor** | 0.4795 | 22,690.14 | 13,312.40 | $6.8\text{ ms}$ | Opaque (Shapley Proxies) | Non-linear Tree Ensemble |
| **Domain-Partitioned KD-Tree + IDW** | **0.4801** | **22,676.45** | **13,281.33** | **$5.25\text{ ms}$** | **Exact Instance Attribution** | **Selected Production Engine** |

#### Why Domain-Partitioned KD-Tree IDW Outperformed Black-Box Gradient Boosting
While gradient-boosted decision trees (`HistGradientBoostingRegressor`) provide competitive predictive accuracy ($R^2 = 0.4795$), they were rejected in favor of Domain-Partitioned KD-Tree IDW ($R^2 = 0.4801$) due to fundamental domain requirements:
1. **Superior Accuracy through Domain Partitioning:** Disjoint indexing across the 8 technical disciplines prevents cross-domain neighbor pollution (e.g., preventing a DevOps quote from averaging against an entry-level digital marketing peer). This structural partitioning delivers higher generalization ($R^2 = 0.4801$ vs. $0.4795$) and lower root-mean-square error ($22,676\text{ KES}$ vs. $22,690\text{ KES}$).
2. **Exact Instance-Level Explainability:** In online professional platforms, black-box tree predictions cannot provide auditable justification to mentors. Domain-Partitioned KD-Tree IDW yields exact attribution: returning the $k$ closest comparable mentors, their explicit pairwise Euclidean distances, relative IDW contribution weights, and anonymized profile credentials.
3. **Deterministic Financial Corridor Synthesis:** The spatial engine's localized peer distances directly feed the empirical standard deviation synthesizer ($\sigma_{\text{peer}}$), providing mathematical bounds for the recommended rate corridor $[r_{\min}, r_{\max}]$ and discrete Safaricom M-Pesa tariff brackets.

![Figure 5.4: Empirical Model Architecture Benchmark](figures/fig5_4_model_architecture_benchmark.png)

*Figure 5.4: Empirical comparison of model architecture candidates contrasting predictive determination ($R^2$) with instance-level peer explainability fidelity, confirming the Pareto dominance of Domain-Partitioned KD-Tree IDW.*

### 5.3.3 Target Transformation Residual Dynamics & Asymmetric Economic Risk (FR-06, FR-07)
A fundamental characteristic of commercial freelance rate estimation is the presence of asymmetric economic risks:
1. **Underpricing (Margin Collapse Risk):** If the model recommends a rate below the mentor's true reservation threshold ($r < r_{\text{true}}$), the mentor suffers direct fee erosion, exacerbated by mandatory mobile money transaction tariffs (Safaricom M-Pesa fees). This is mitigated at runtime by `base_rate_floor`.
2. **Overpricing (Client Alienation & Churn Risk):** If the quote substantially exceeds market willingness-to-pay ($r \gg r_{\text{true}}$), booking conversion drops precipitously, alienating clients and creating friction on the platform.

#### Raw Target Regression vs. Logarithmic Stabilization
Standard unconstrained regression fitted on raw hourly rates ($y \in \mathbb{R}^+$) is heavily distorted by extreme right-tail marketplace budget outliers (e.g. up to $343,823\text{ KES/hour}$). Under raw target fitting, residual errors exhibit severe positive skewness and excess kurtosis ($\mathrm{Kurtosis} = 14.82$), yielding a Median Absolute Error (MedAE) of $8,001\text{ KES/hour}$ and exposing users to runaway overpricing outliers.

To counteract heavy-tail distortion, a natural logarithmic transformation was implemented:
$$y' = \ln(1 + y) \quad \Longleftrightarrow \quad \hat{y} = \exp(\hat{y}') - 1$$

| Target Formulation | Validation RMSE (KES/hr) | Validation MAE (KES/hr) | Validation MedAE (KES/hr) | Validation sMAPE (%) | Residual Kurtosis |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Raw Target Training** | **23,092.63** | 13,670.30 | 8,001.61 | 46.50% | 14.82 |
| **Log1p Target ($y'=\ln(1+y)$)** | 26,606.12 | **12,689.44** | **6,650.98** | **42.66%** | **3.12** |

As demonstrated empirically in Table 5.2 and Figure 5.5:
- **Kurtosis Compression to $3.12$:** Log1p transformation compresses residual kurtosis from $14.82$ down to $3.12$ (approaching the Gaussian baseline of $3.0$), effectively eliminating extreme over-pricing runaway errors.
- **$16.9\%$ Reduction in MedAE:** Median absolute pricing error drops by **$16.9\%$** (from $8,001.61\text{ KES}$ to $6,650.98\text{ KES}$), while symmetric Mean Absolute Percentage Error (sMAPE) falls from $46.50\%$ to $42.66\%$.
- **Economic Risk Stabilization:** By compressing right-tail variance, the model maintains safe symmetric error boundaries between margin protection and client retention.

![Figure 5.5: Target Transformation Residual Dynamics & Asymmetric Economic Risk Boundaries](figures/fig5_5_target_transformation_residuals.png)

*Figure 5.5: Comparative probability density distributions of regression residuals under raw target training (left) versus natural logarithmic transformation $y' = \ln(1+y)$ (right), depicting the elimination of extreme over-pricing outliers and compression of error kurtosis to $3.12$.*

### 5.3.4 Domain Subgroup Performance Breakdown (FR-04)
To verify model robustness across varied technical specializations in Kenya's digital workforce, holdout evaluations were disaggregated across the primary industry domains using strict description-group disjoint splitting (zero text overlap between train and test splits):

| Technical Industry Domain | Holdout $R^2$ | Validation MAE (KES/hr) | Rate Median (KES/hr) | Interquartile Range [Q1, Q3] | Empirical Specialization Profile |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Data & AI (`data_ai`)** | **0.5079** | 13,040 | 4,800 | [3,200 – 6,500] | Machine learning, analytics, Python pipelines |
| **Web & Backend (`web_backend`)** | **0.5119** | 12,890 | 4,500 | [3,000 – 6,200] | REST APIs, Django, FastAPI, PostgreSQL |
| **Mobile Development (`mobile`)** | **0.4064** | 13,750 | 4,200 | [2,800 – 5,800] | Android Jetpack Compose, Kotlin, Flutter |
| **Design & Creative (`design_creative`)** | **0.3975** | 14,210 | 3,800 | [2,500 – 5,200] | UI/UX, product design, brand identity |

As illustrated in Figure 5.6:
- High-volume technical partitions (`data_ai` and `web_backend`) exceed $R^2 \ge 0.50$, indicating strong predictive fidelity driven by dense technical skill vocabularies.
- Niche and creative disciplines exhibit higher variance due to broader subjective rate dispersions, yet remain tightly bounded within safe empirical interquartile corridors.

![Figure 5.6: Domain Subgroup Partition Generalization and Empirical Rate Distributions](figures/fig5_6_subgroup_domain_performance.png)

*Figure 5.6: Subgroup performance breakdown across four core industry partitions, illustrating holdout determination coefficients ($R^2$, left) and empirical rate quartiles in KES/hour (right).*

---

## 5.4 Algorithmic Cold-Start Governance & Fallback Cascade (FR-05)

When a mentor registers in a newly formed or sparse technical discipline where historical transaction counts are insufficient ($N < 5$), standard nearest-neighbor queries risk overfitting to small-sample noise. To ensure high availability and prevent cold-start pricing failures, a deterministic **4-Tier Cold-Start Fallback Cascade** was designed:

1. **Tier 1 (Domain-Specific KD-Tree IDW, $N \ge 5$):** The primary inference engine queries the dedicated KD-Tree index for the requested partition, retrieving the $k = 5$ closest technical peers with baseline weighting penalty $\lambda = 1.0$.
2. **Tier 2 (Taxonomy Hierarchy Rollup):** If the requested partition has fewer than 5 verified mentors ($N < 5$), the spatial engine automatically rolls the query up to an allied parent domain (e.g., specialized ML subfields roll up to `data_ai`, or niche languages roll up to `general_tech`).
3. **Tier 3 (Penalized Global Spatial Pool):** If no taxonomy parent is available, the query falls back to the global unpartitioned mentor index, applying an uncertainty penalty inflation factor $\lambda = 1.25$ to widen corridor bounds and emitting `fallback_applied=True` in the audit telemetry.
4. **Tier 4 (Macroeconomic Prior Anchor):** In the edge case of complete platform zero-peer bootstrap ($N = 0$), the service synthesizes a baseline quote anchored to the national macroeconomic prior $\mu_{\text{macro}}$ scaled by the bilateral cost-of-living ratio $(C_{\text{client}}/C_{\text{mentor}})^{\alpha}$ with a Safaricom M-Pesa tariff floor.

```mermaid
flowchart TD
    Q["Pricing Request Arrival: q ∈ ℝ⁵³<br/>Partition: D_req"] --> C1{"Historical count<br/>N ≥ 5 in D_req?"}
    C1 -- YES --> T1["Tier 1: Domain-Specific KD-Tree<br/>Exact Localized IDW (k=5, λ=1.0)"]
    C1 -- NO --> C2{"Allied Parent Taxonomy<br/>Available?"}
    C2 -- YES --> T2["Tier 2: Taxonomy Rollup<br/>Route to Parent Domain (e.g. general_tech)"]
    C2 -- NO --> T3["Tier 3: Penalized Global Pool<br/>Global KD-Tree (λ=1.25 Penalty Factor)"]
    T3 -- N = 0 --> T4["Tier 4: Macroeconomic Prior<br/>CoL Scaled Reservation Rate Anchor"]
```

![Figure 5.7: Algorithmic 4-Tier Cold-Start Fallback Cascade Flowchart](figures/fig5_7_cold_start_fallback_cascade.png)

*Figure 5.7: Flowchart of the 4-tier algorithmic fallback cascade guaranteeing continuous pricing resolution and margin protection across cold-start scenarios.*



