# AGENTS.md

Machine-readable operating guide for AI coding agents working in the Price-Optimization-Model repository.

---

## 1. Project Identity & Architecture

Price-Optimization-Model is an ML-driven pricing recommendation service combining semantic NLP analysis, macroeconomic purchasing-power parity adjustments, nearest-neighbor peer pricing retrieval, and domestic margin protection (M-Pesa).

| Property       | Value                                                              |
|----------------|--------------------------------------------------------------------|
| Institution    | Strathmore University — School of Computing & Engineering Sciences |
| Project Title  | A Content-Based Dynamic Price Optimization Framework               |
| Author         | Jaedon Jeremiel Munyua (Student No: 169684)                        |
| Supervisor     | Dr. Jecton Anyango                                                 |
| Academic Year  | June 2026                                                          |
| Language       | Python `3.10+`                                                     |
| Framework      | FastAPI + Uvicorn (ASGI)                                           |
| ML Core        | scikit-learn (TF-IDF, TruncatedSVD, KD-Tree / BallTree, IDW)       |
| Persistence    | Firebase Firestore (Admin SDK)                                     |
| Validation     | Pydantic v2 (`src/api/api_contracts.py`)                           |
| Testing        | Pytest                                                             |
| Container      | Docker (`python:3.11-slim`)                                        |
| Client Shell   | Android Jetpack Compose (`app/`)                                   |

---

## 2. Directory Layout & Key Boundaries

```
Price-Optimization-Model/
├── src/
│   ├── api/          # FastAPI routes, ASGI gateway, Pydantic v2 schemas/DTOs
│   ├── engine/       # Spatial indexer, IDW kernels, macro arbitrage, platform price adapter
│   ├── nlp/          # Text sanitization, TF-IDF vectorization, TruncatedSVD, SentenceTransformers
│   ├── data/         # Ingestion pipelines, secondary corpus harmonization, synthetic seeding
│   ├── benchmarks/   # Ensemble comparison, ANN scaling benchmarks, latency profiling
│   ├── training/     # Offline Out-of-Time (OOT) model compilation pipeline
│   ├── core/         # Artifact contracts, SHA-256 integrity manifest verifiers
│   └── drift_monitor.py # Continuous MLOps drift monitoring (PSI, KS-test, Wasserstein)
├── artifacts/        # Serialized ML artifacts (.joblib, .json)
├── config/           # YAML/JSON environment and industry taxonomy configurations
├── data/             # Datasets (raw, processed Parquet, lookup tables)
├── docs/             # Architecture blueprints (M1-M15), Milestone 16 specs, style guides
└── tests/            # Pytest test suite (unit, integration, regression)
```

- **Inference Isolation**: Keep model scoring logic inside `src/engine` and expose it strictly through service interfaces into `src/api`.
- **Schema Contracts**: All API input/output DTOs must use Pydantic v2 schemas in `src/api/api_contracts.py`. Never accept unvalidated raw JSON.
- **Wire Contract Immutability**:
  - `POST /price` platform adapter response MUST contain exactly four keys: `{"min", "max", "comparables", "reason"}`.
  - `POST /api/v1/optimize-price` canonical response MUST contain exactly eleven keys: `{"basePredictedRate", "mpesaTariffSurcharge", "finalQuotedRate", "minQuotedRate", "maxQuotedRate", "kNeighborsUsed", "bilateralArbitrageFactor", "confidenceScore", "comparables", "reason", "timestamp"}`.
- **Artifact Immutability**: Production model weights in `artifacts/` must never be overwritten in-place without versioning and regression testing.

---

## 3. Canonical Quality Toolchain

Run these verification commands in order before concluding tasks:

```powershell
# 1. Run all unit tests concisely (deterministic virtual environment runner)
.venv\Scripts\pytest tests/ -q

# 2. Run spatial engine & M16 algorithmic tests
.venv\Scripts\pytest tests/engine/test_spatial_engine.py tests/engine/test_spatial_engine_m16.py -v

# 3. Test API startup and health check (smoke test)
python -c "from fastapi.testclient import TestClient; from src.api.main import app; client = TestClient(app); res = client.get('/health'); print('Health Status:', res.status_code, res.json())"
```

---

## 4. Academic Documentation & Writing Standards

All documentation, commit messages, and research reports must adhere to the Strathmore University dissertation standards (*Munyua, 2026*):

1. **Academic Tone & Perspective:**
   - Use third-person objective perspective. Avoid informal first-person singular pronouns ("I", "my").
   - Employ formal passive construction for methodology ("The feature space was partitioned using k-d trees") or first-person plural for collective investigative intent ("We formulate the pricing corridor as...").
   - Frame conclusions empirically using measurable metrics (MAE in KES/hour, RMSE, MAPE %, inference latency in ms, Recall@k).

2. **Mathematical Nomenclature Standards:**
   - **Latent Feature Space:** $q = [e_1, \dots, e_n, \; \tilde{\beta}_{ij}, \; \tilde{s}, \; \tilde{\rho}]^T \in \mathbb{R}^{n+3}$, where $n$ is latent semantic dimensions ($n=50$ for SVD, $n=384$ for Sentence Transformers).
   - **Bilateral Arbitrage Factor:** $\beta_{ij} = \left( \frac{\text{PPP}_j}{\text{PPP}_i} \cdot \frac{\text{CoL}_i}{\text{CoL}_j} \right)^\alpha$, with damping coefficient $\alpha \in [0, 1]$ (default $\alpha = 0.50$). For domestic engagements ($i=j$), $\beta_{ii} \equiv 1.0$.
   - **Normalized IDW Weights:** $w_k = \frac{1}{(d_k)^p + \epsilon}$, $\bar{w}_k = \frac{w_k}{\sum_{m=1}^K w_m}$, supporting quadratic ($p=2$), linear ($p=1$), exponential ($e^{-\gamma d}$), and Gaussian RBF ($e^{-d^2 / 2\sigma^2}$) kernels.
   - **Base Predicted Rate:** $\hat{r}_{\text{base}} = \sum_{k=1}^K \bar{w}_k \cdot r_k$.
   - **Margin Protection (M-Pesa):** $\hat{r}_{\text{final}} = \hat{r}_{\text{base}} + \tau_{\text{mpesa}}(\hat{r}_{\text{base}})$.
   - **Pricing Corridor:** $[r_{\min}, r_{\max}]$ where $r_{\min} = \max(r_{\text{floor}}, \hat{r}_{\text{base}} - z \cdot \sigma_{\text{peer}})$ and $r_{\max} = \hat{r}_{\text{base}} + z \cdot \sigma_{\text{peer}}$.

3. **Core Domain Lexicon:**
   - **Cross-Border Arbitrage Paradox:** Market distortion where emerging-market freelancers undercharge foreign clients or alienate domestic clients under static pricing.
   - **Domestic Underpricing Trap:** Systematic underbidding due to lack of transparent market pricing information.
   - **International Alienation Trap:** Setting asking rates excessively high based on foreign headline rates, resulting in zero inbound bookings.
   - **Transaction Fee Vulnerability:** Severe profit margin erosion caused by non-linear tier-based mobile payment tariffs (Safaricom M-Pesa bands).
   - **Cold-Start Fallback Cascade:** 4-tier routing: Tier 1 (Direct Partition) $\to$ Tier 2 (Taxonomy Rollup) $\to$ Tier 3 (Global Semantic Pool with penalty $\lambda_{\text{industry}}$) $\to$ Tier 4 (Macro Empirical Prior).

---

## 5. Feature-Driven Development (FDD) Workflow

Development adheres to Feature-Driven Development (FDD):
1. Develop Overall Model
2. Build Feature List
3. Plan by Feature
4. Design by Feature
5. Build by Feature

### Feature Naming Syntax
All feature descriptions, issue titles, user stories, and major commit messages must conform to the standard FDD syntax template:
`⟨action⟩ the ⟨result⟩ ⟨by|to|of|from⟩ a ⟨object⟩`

*Examples:*
- `Calculate the base rate from nearest peers`
- `Normalize the continuous metadata features of a marketplace listing`
- `Route the low-volume partition query to a sibling taxonomy domain`
- `Evaluate the population stability index of historical transactions`

---

## 6. Milestone Governance & Research Track Isolation

- **Baseline Stability (M1–M8):** Core ingestion, NLP vectorization, and spatial IDW engines must remain stable and backward compatible.
- **Graduation Deliverables (M9–M15):** Production MLOps, Firebase persistence, and platform integrations take absolute priority over advisory feedback.
- **Advisory Research Track (Milestone 16):** Algorithmic benchmarks (tree ensembles, ANN search, alternative kernels, continuous drift monitoring) are strictly marked `scope:optional, track:advisory-research`. They provide empirical justification for dissertation defense without blocking core platform deliverables.
- **Environment Variables**: Never hardcode credentials. Use `.env` and `Firebase_price_optimization_key` references for secret management.
