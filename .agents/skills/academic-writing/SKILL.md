---
name: academic-writing
description: >-
  Academic dissertation and technical documentation writing standards for Strathmore
  University research publications. Enforces continuous paragraph prose (no point form),
  strict grammatical tense rules (past for completed actions, present for established
  evidence, future for incomplete work), concise technical explanations without padding,
  structured A4-compliant tables, publication-grade mathematical formulations (Equations 3.1-3.8),
  and the Narrative-Diagram-Interpretation presentation sequence.
---

# Academic Writing & Dissertation Documentation Skill

This skill enforces the official technical writing, linguistic style, mathematical rigor, and structural standards for the Strathmore University undergraduate research thesis (*Munyua, 2026*), aligning with institutional guidelines provided by the School of Computing and Engineering Sciences.

## 1. Core Prose & Linguistic Invariants

1. **Strict Grammatical Tense Hierarchy:**
   - **Past Tense:** Use exclusively for completed research activities, implementations, model training, and executed test suites (e.g., *"The dataset was partitioned temporally"*, *"Five candidate estimators were evaluated"*).
   - **Present Tense:** Use exclusively for established scientific knowledge, active runtime behavior, and what documents, tables, or figures illustrate (e.g., *"Figure 5.2 illustrates the coordinate fusion pipeline"*, *"Table 5.7 summarizes holdout metrics"*).
   - **Future Tense:** Restrict strictly to genuinely uncompleted activities, recommendations, or prospective extensions in Chapter 6.

2. **Continuous Flowing Paragraphs (Zero Bullet Points in Main Chapter Narrative):**
   - Academic dissertation chapters (specifically Chapters 1 through 5) must be composed in continuous, coherent prose paragraphs connected by logical transitions.
   - Do NOT present core methodologies, requirements analysis, or empirical evaluations in informal point-form outlines, dashed lists, or bullet fragments.

3. **Concise, High-Density Technical Explanations:**
   - Avoid generic conceptual tutorials or textbook filler (e.g., explaining what RAM, Docker, or cross-validation is in abstract terms).
   - Focus explanations strictly on project-specific architectural justifications, mathematical formulations, operational constraints, and empirical trade-offs.

4. **Third-Person Objective Academic Register:**
   - Use third-person formal voice or objective passive voice (*"The matrix was projected into..."*). Avoid first-person singular pronouns (*"I"*, *"my"*).

5. **Cross-Chapter Anti-Repetition Guardrail:**
   - Never re-explain problem background, conceptual definitions, or theoretical justifications already established in Chapters 1–4.
   - Use concise cross-references (*"as specified in Section 4.2.1"*, *"fulfilling FR-03"*). Focus exclusively on the new realization, concrete code artifact, or empirical measurement.

6. **Page Budget & Printing-Cost Discipline:**
   - Maintain a high information-to-ink ratio. Avoid prose bloat that needlessly expands page count for physical printing.
   - Let compact, normalized tables (3–4 columns) and vector diagrams convey structural details, reserving prose for critical analytical interpretation.

7. **Plain Technical Clarity & Thesis Communication:**
   - Communicate the core thesis directly: how content-based instance regression over a unified coordinate space yields defensible, tariff-protected pricing under strict hardware bounds.
   - Eliminate defensive caveats or meta-commentary about document guidelines. State technical facts, invariants, and findings authoritatively without padding.

8. **Chapter 5 Empirical Isolation:**
   - Chapter 5 is an empirical validation and system accounting chapter, not a design review.
   - Confine Section 5.3 to data preparation specifics, Out-of-Time split verification, ablation benchmark metrics, and holdout evaluation evidence.

## 2. Evidence-First Presentation: The Narrative–Diagram–Interpretation Triad

Every figure, graph, or visual model in Chapter 4 and Chapter 5 must follow the strict institutional presentation sequence:
1. **Narrative (Before Diagram):** Frame what the diagram represents, why it is relevant, its scope, and the specific requirement or research objective it addresses.
2. **Diagram (Visual Representation):** Clean, uncluttered diagram using approved notation (Mermaid, PlantUML, or high-resolution vector export) sized for A4 portrait layout.
3. **Figure Caption:** Numbered and captioned according to institutional rules (e.g., `Figure 5.3: Latent Text Dimensionality vs. Holdout Generalization and Query Latency`).
4. **Interpretation (After Diagram):** Critically analyze the important flows, inflection points, empirical trade-offs, and design implications instead of merely repeating the visual labels.

## 3. Standard Mathematical Nomenclature

- **Unified Coordinate Vector:** $q = [e_1, \dots, e_n, \; \tilde{\beta}_{ij}, \; \tilde{s}, \; \tilde{\rho}]^T \in \mathbb{R}^{n+3}$ ($n=50$ for production SVD, $n=384$ for sentence transformers).
- **Damped Bilateral PPP Arbitrage Factor:** $\beta_{ij} = (\frac{\text{PPP}_j}{\text{PPP}_i} \cdot \frac{\text{CoL}_i}{\text{CoL}_j})^\alpha$ with damping exponent $\alpha \in [0, 1]$ (default $0.50$; domestic $\beta_{ii} \equiv 1.0$).
- **Inverse Distance Weighting (IDW) Kernel:** $w_k = \frac{1}{(d_k)^p + \epsilon}$ normalized as $\bar{w}_k = \frac{w_k}{\sum_{m=1}^k w_m}$.
- **Pricing Corridor Bounds:** $[r_{\min}, r_{\max}]$ where $r_{\min} = \max(r_{\text{floor}}, \hat{r}_{\text{base}} - z \sigma_{\text{peer}})$ and $r_{\max} = \hat{r}_{\text{base}} + z \sigma_{\text{peer}}$.
- **Final Tariff-Protected Quote:** $\hat{r}_{\text{final}} = \hat{r}_{\text{base}} + \tau(\hat{r}_{\text{base}})$.

## 4. Canonical Mathematical Formulations (Equations 3.1 – 3.8)

Every formal mathematical expression in the dissertation must adhere strictly to these canonical definitions and render without missing symbols, placeholder glyphs, or empty parentheses:

1. **Equation 3.1: Min-Max Feature Normalization**
   Transforms continuous metadata features into the closed unit interval $[0, 1]$:
   $$\tilde{x} = \frac{x - x_{\min}}{x_{\max} - x_{\min}}$$
   where $x_{\min}$ and $x_{\max}$ are empirical boundary parameters computed exclusively from the chronologically isolated training partition $\mathcal{D}_{\text{train}}$.

2. **Equation 3.2: Inverse Distance Weighting (IDW) Kernel**
   Computes local peer influence with quadratic distance decay ($p = 2$) and an infinitesimal safeguard $\epsilon = 10^{-6}$:
   $$w_i = \frac{1}{(d(\mathbf{q}, \mathbf{x}_i))^p + \epsilon}$$
   where $\mathbf{q} \in \mathbb{R}^{n+3}$ is the query coordinate and $\mathbf{x}_i \in \mathbb{R}^{n+3}$ is the coordinate of historical peer $i$.

3. **Equation 3.3: Base Clearing Rate Aggregation (Log-Space Geometric Mean)**
   Aggregates peer historical rates using normalized weights $\bar{w}_i = \frac{w_i}{\sum_{j=1}^k w_j}$:
   $$\hat{y}_{\text{base}} = \exp\left( \sum_{i=1}^k \bar{w}_i \ln(y_i) \right)$$
   *(Note: The log-transformed representation enforces multiplicative rate dispersion and prevents positive outlier skewness).*

4. **Equation 3.4: Root Mean Squared Error (RMSE)**
   $$\text{RMSE} = \sqrt{\frac{1}{N}\sum_{i=1}^N (y_i - \hat{y}_i)^2}$$

5. **Equation 3.5: Mean Absolute Error (MAE)**
   $$\text{MAE} = \frac{1}{N}\sum_{i=1}^N |y_i - \hat{y}_i|$$

6. **Equation 3.6: Coefficient of Determination ($R^2$)**
   $$R^2 = 1 - \frac{\sum_{i=1}^N (y_i - \hat{y}_i)^2}{\sum_{i=1}^N (y_i - \bar{y})^2}$$
   where $\bar{y} = \frac{1}{N}\sum_{i=1}^N y_i$ is the empirical benchmark mean of the evaluation partition.

7. **Equation 3.7: Damped Bilateral Purchasing Power Parity (PPP) Arbitrage Factor**
   $$\Phi_{m \to c} = \left( \frac{\text{PPP}_c}{\text{PPP}_m} \cdot \frac{\text{CoL}_m}{\text{CoL}_c} \right)^\alpha$$
   where $m$ is the mentor origin country (e.g., KE), $c$ is the client market country (e.g., US), and $\alpha \in [0, 1]$ is the empirical damping parameter ($\alpha = 0.50$ by default, ensuring equitable surplus sharing). For domestic transactions ($m = c$), $\Phi_{m \to m} \equiv 1.0$.

8. **Equation 3.8: Dynamic Rate Corridor and Localized Margin Protection**
   The defensible negotiation corridor $[R_{\min}, R_{\max}]$ is bounded by:
   $$R_{\min} = \max\left( R_{\text{floor}}, \; \hat{y}_{\text{base}} - z \cdot \sigma_{\text{peer}} \right)$$
   $$R_{\max} = \hat{y}_{\text{base}} + z \cdot \sigma_{\text{peer}}$$
   where $R_{\text{floor}}$ is the mentor's minimum reservation wage, $\sigma_{\text{peer}} = \sqrt{\sum_{i=1}^k \bar{w}_i (y_i - \hat{y}_{\text{base}})^2}$ is the peer rate standard deviation, and $z$ is the corridor confidence factor ($z = 1.0$ for standard spread).
   The final quoted billing rate incorporates statutory tariff protection:
   $$\hat{y}_{\text{final}} = \hat{y}_{\text{base}} + \tau(\hat{y}_{\text{base}})$$
   where $\tau(y)$ maps the transaction into the discrete 15-tier Safaricom M-Pesa P2P schedule when $m = \text{'KE'} \land c = \text{'KE'}$, and evaluates to $0.00$ (with international payment processing/FX fee notes) for cross-border export corridors.

## 5. Algorithmic Invariants & Realism Safeguards

1. **KD-Tree Asymptotic Complexity Realism:**
   - In $D = 53$ dimensional space, branch-and-bound tree pruning degrades due to hypersphere-hypercube intersections ($2^{53} \gg N$).
   - Never describe KD-Tree search in 53D as achieving strict logarithmic $O(\log N)$ time.
   - Accurately frame sub-15 ms latency as arising from domain partitioning (restricting searches to subsets with $N \le 5,000$), optimized Cython Euclidean kernels, and leaf-size tuning (`leaf_size = 40`), behaving as bounded localized linear scans.

2. **Coordinate Fusion Metric Balancing:**
   - Acknowledge that an $L_2$-normalized SVD projection has total squared Euclidean norm $\le 1.0$, whereas three unweighted $[0, 1]$ Min-Max features can contribute up to $3.0$.
   - Explicitly document coordinate block weighting or hyperparameter tuning that prevents macroeconomic features from overwhelming lexical similarity.

3. **SVD Explained Variance Accuracy:**
   - Do not claim 50 SVD components capture $>95\%$ variance over 12,000 sparse TF-IDF features. Document the realistic empirical variance (~15%–30%) or frame 50 components as an optimal Pareto trade-off between semantic noise elimination and latency.

4. **Multi-Model Baseline Standards:**
   - All evaluation sections must benchmark against:
     - Stage 1 Heuristic Baseline (Domain Median × Experience multiplier).
     - Regularized Linear Baselines (Ridge / ElasticNet regression over TF-IDF + metadata) for direct interpretable weight comparison.
     - Offline Tree Ensembles (Random Forest / HistGradientBoosting) to establish the empirical upper-bound accuracy frontier.

## 6. Financial Tariff & Settlement Invariants

1. **M-Pesa Tariff Schedule:**
   - The implemented schedule is the **15-tier Peer-to-Peer (P2P)** schedule (`mpesa_p2p_users_2026-08-04.csv`), spanning KES 1.00 to KES 250,000.00.
2. **Domestic Gating Condition:**
   - Tariff evaluation triggers strictly when both mentor and client reside in Kenya (`mentorCountry == 'KE' and clientCountry == 'KE'`).
3. **Cross-Border Fee Disclosure:**
   - For export transactions, domestic M-Pesa tariff is zero, but standard cross-border payment aggregator and foreign exchange settlement deductions (2.9%–4.8% via Flutterwave, Paystack, or PayPal-to-M-Pesa) must be documented in system delimitations and user guidance.
## 7. Version Control & Implementation Evidence Invariants (Section 5.4)

When drafting or refining Section 5.4 (Version Control and Implementation Evidence), adhere to Strathmore University institutional guidelines:

1. **Canonical 7-Subsection Structure:**
   Section 5.4 must strictly comprise:
   - `5.4.1 Repository Setup and Access`
   - `5.4.2 Task Planning and Tracking`
   - `5.4.3 Branching Strategy`
   - `5.4.4 Commits and Development History`
   - `5.4.5 Review and Integration`
   - `5.4.6 Project Organisation and Reproducibility`
   - `5.4.7 Hosting and Deployment`

2. **Strict Space Budgeting (4–6 Pages Maximum):**
   - The entire Section 5.4 must occupy between 4 and 6 pages in standard A4 formatting.
   - Limit visual evidence to 4–6 high-value, tightly-cropped screenshots.
   - Every screenshot with its caption must occupy less than half a report page.

3. **The Four-Step Paragraph-and-Figure Evidence Pattern:**
   Every subsection must feature:
   - Practice justification (why the methodology suited this project).
   - Concrete project instance (exact issue numbers, branch names, commit hashes, or PR numbers).
   - Numbered figure callout.
   - Evidence interpretation (what technical guarantee or workflow rigor is proved).

4. **Concrete Traceability & Zero Textbook Filler:**
   - Never define Git, branches, or CI in the abstract.
   - Trace concrete links: Issue -> Branch -> Commit -> Pull Request -> Automated CI -> Deployment.

5. **Repository Hygiene & Safe Configuration:**
   - Document `.gitignore` rules preventing secret keys, `.env` files, build caches, and private raw data ingestion from entering version history.
   - Cite the open-source license (MIT License) and link the repository using the exact anchor label *"Project repository"*.

