# AI Dynamic Pricing Platform for Technical Mentors

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Android](https://img.shields.io/badge/Platform-Android_Compose-3DDC84.svg)](docs/Architecture/Android_App_Guide.md)
[![Tests: 389 Passed](https://img.shields.io/badge/Tests-389_Passed-brightgreen.svg)](tests/)

> **"What hourly rate should I charge for this technical mentoring engagement?"**  
> An explainable dynamic pricing engine that turns a technical service description, sovereign macroeconomic indicators, and client context into an optimal rate in Kenyan Shillings (KES/hour)—complete with localized Safaricom M-Pesa financial margin protection and comparable peer explainability.

---

## ⚡ Key Capabilities

* **Semantic NLP Vectorization:** Normalizes and lemmatizes service profiles via NLTK, fits unigram/bigram/trigram TF-IDF features (up to 15,000 terms), and projects textual semantics into a dense 50-D latent space using Truncated SVD.
* **Sovereign Macroeconomic Arbitrage:** Computes bilateral purchasing power parity $\Phi(\text{mentor}, \text{client})$ from World Bank WDI indicators and Numbeo cost-of-living indices, capturing cross-border arbitrage between international clients and emerging-market mentors.
* **53-D Coordinate Fusion & Spatial Retrieval:** Fuses 50 text dimensions with 3 continuous macro features into a unified 53-D space. Queries industry-partitioned KD-Trees with Inverse Distance Weighting (IDW) to retrieve top-$k$ comparable peers in sub-10ms.
* **Localized Financial Margin Protection:** Automatically maps quotes against Safaricom's official 15-band M-Pesa P2P tariff schedule for Kenyan mentors, ensuring mobile money transfer fees do not erode take-home pay.
* **Actionable Negotiation Corridors:** Synthesizes fee-free negotiation ranges $[\text{minQuotedRate}, \text{maxQuotedRate}]$ from peer dispersion ($\sigma_{\text{peer}}$), bilateral parity ($\Phi$), and mentor reservation floors.
* **Full-Stack Delivery:** Features Pydantic v2 DTOs, a FastAPI ASGI service, Firebase Authentication (UID ownership verification), Cloud Firestore persistence, and an Android client built with Jetpack Compose, MVVM, and Retrofit.

---

## 🏗 System Architecture

```
[Android Client / Web Demo]
            |  (HTTPS + Firebase Bearer Token)
            v
[FastAPI Pricing Gateway] <---> [Firebase Auth & Cloud Firestore]
            |                   (/mentors, /service_listings, /historical_transactions)
            v
[ML Inference Engine]
    ├── Text Pipeline: TF-IDF (15k) + Truncated SVD (50D)
    ├── Macro Scaler: Bilateral Arbitrage Phi + Saturation + Density (3D)
    ├── Spatial Indexer: Domain-Partitioned KD-Trees + IDW Regression
    └── Tariff Evaluator: 15-Band Safaricom M-Pesa Fee Schedule
```

| Component | Technology | Primary Responsibilities |
| :--- | :--- | :--- |
| **Android Client** | Kotlin, Jetpack Compose, MVVM, `StateFlow`, Retrofit | Profile input collection, Firebase token lifecycle, negotiation corridor display, peer breakdown cards. |
| **Pricing Gateway** | Python 3.11, FastAPI, Uvicorn, Pydantic v2 | Firebase Admin SDK token verification, schema validation, rate-limiting, serving `POST /api/v1/optimize-price`. |
| **ML Engine** | scikit-learn, NLTK, KDTree, NumPy, joblib | Zero-leakage training-only transforms, 53-D coordinate fusion, IDW peer search, and base-rate prediction. |
| **FinTech Layer** | Python (`MpesaTariffEvaluator`), Versioned CSV | 15-band P2P fee lookup (1–250,000 KES), single-fee surcharge calculation, net earnings margin protection. |
| **Persistence** | Firebase Auth & Cloud Firestore | Owner-bound mentor records (`/mentors`), root listings (`/service_listings`), append-only audit trail (`/historical_transactions`). |
| **MLOps & CI** | Docker, GitHub Actions, SHA-256 Manifest Pinning | 389 automated unit and invariant tests, cryptographic model provenance, sub-15ms inference budget. |

---

## 📐 How a Price is Calculated

1. **Feature Vector Construction (53-D):**
   * **Text (50D):** Sanitized, lemmatized tokens are transformed through fitted TF-IDF and SVD reducers.
   * **Metadata (3D):** Bilateral factor $\Phi(m, c)$, live market saturation, and industry listing density are scaled to $[0, 1]$.
   * **Weighted Fusion:** Vectors are fused with empirical feature weights (e.g. `text_weight = 0.50`, `metadata_weight = 2.50`):
     $$\mathbf{x}_{\text{query}} = \left[ w_{\text{text}} \cdot \mathbf{v}_{\text{text}} \;\Vert\; w_{\text{meta}} \cdot \mathbf{v}_{\text{meta}} \right] \in \mathbb{R}^{53}$$

2. **Domain-Partitioned KD-Tree Search & IDW Regression:**
   * The query is routed to its partition index (e.g. `mobile`, `web_backend`, `data_ai`).
   * Queries top-$k$ nearest peers ($k=12$) and calculates inverse-distance weights with epsilon smoothing ($\epsilon = 10^{-4}$):
     $$\hat{y}_{\text{base}} = \frac{\sum_{i=1}^k w_i \cdot y_i}{\sum_{i=1}^k w_i}, \quad w_i = \frac{1}{d_i^2 + \epsilon}$$

3. **Negotiation Corridor Synthesis:**
   * Bounded by peer standard deviation ($\sigma_{\text{peer}}$) and bilateral arbitrage factor ($\Phi$):
     $$\text{minRate} = \max(\text{floor}, \hat{y}_{\text{base}} - 0.75 \sigma), \quad \text{maxRate} = (\hat{y}_{\text{base}} + 1.25 \sigma) \times (2 - \Phi \text{ if } \Phi < 1 \text{ else } 1)$$

4. **Localized Tariff Surcharge (M-Pesa):**
   * For Kenyan mentors (`mentorCountry == 'KE'`), the fee is resolved from the 15-band Safaricom schedule and added once:
     $$\text{finalQuotedRate} = \text{basePredictedRate} + \text{mpesaTariffSurcharge}$$

---

## 🚀 Quickstart: Local Python Pipeline

### Prerequisites
* Python 3.11+
* Virtual environment (`.venv`)

### 1. Installation & Environment Setup
```bash
git clone https://github.com/tyejaedon/Price-Optimization-Model.git
cd Price-Optimization-Model

python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

pip install -r requirements.txt
python -c "import nltk, certifi, ssl; ssl._create_default_https_context = ssl.create_default_context(cafile=certifi.where()); nltk.download('stopwords'); nltk.download('wordnet')"
```

### 2. Ingestion & Preprocessing
```bash
# Build sovereign macroeconomic lookup table (117 countries)
python -m src.data.ingest_multisource --mode macro_lookup

# Ingest and harmonize freelance marketplace records into parquet
python -m src.data.ingest_multisource --mode harmonize_parquet
```

### 3. Model Training & Serialization
```bash
# Execute PCA scree elbow analysis, 40-trial Random Search, and export production artifacts
python scripts/train_optimal_random_search.py
```

### 4. Run Local API Service
```bash
# Launch FastAPI ASGI inference server
uvicorn src.api.serve:app --host 127.0.0.1 --port 8000
```
Interactive Swagger documentation will be available at `http://127.0.0.1:8000/docs`.

---

## 📡 Canonical API Contract (M10.5 / #83)

### Endpoint: `POST /api/v1/optimize-price`

#### Request Payload
```json
{
  "mentorId": "mentor-ke-042",
  "rawText": "Senior Android engineer specializing in Kotlin, Jetpack Compose, clean architecture, and reactive state management.",
  "industry": "mobile",
  "mentorCountry": "KE",
  "clientCountry": "US",
  "competitivenessScore": 0.65,
  "costOfLivingIndex": 0.74,
  "baseRateFloor": 4000.0
}
```

#### Response Payload
```json
{
  "basePredictedRate": 4700.0,
  "mpesaTariffSurcharge": 57.0,
  "finalQuotedRate": 4757.0,
  "minQuotedRate": 4460.0,
  "maxQuotedRate": 7599.0,
  "kNeighborsUsed": 12,
  "bilateralArbitrageFactor": 1.18,
  "confidenceScore": 0.0,
  "comparables": [
    {
      "listingId": "listing-882",
      "jobTitle": "Lead Mobile Architect (Android/Compose)",
      "verifiedRate": 4850.0,
      "similarityScore": 0.94,
      "euclideanDistance": 0.0638
    }
  ],
  "reason": "Weighted from 12 indexed peers in KES/hour; corridor excludes the M-Pesa surcharge. Kenyan M-Pesa fee of 57.00 KES/hour is added once to the base rate.",
  "timestamp": "2026-10-18T20:28:40Z"
}
```

*Note: Legacy callers can continue using the snake_case schema (`raw_description`, `selected_industry`, `base_predicted_rate`); the gateway handles backwards compatibility transparently.*

---

## 🔬 Experimental Rigor & Label Provenance (#91)

* **Proxy Data Scope:** Under [Issue #91 (Label Provenance Audit)](docs/Label_Provenance_Audit_91.md), training records are derived from global freelance marketplace job budgets and profile asking rates (`22,677` rows). These serve as proxy market signals, not historical verified mentor transactions.
* **Deferred Empirical R² Gate:** The exploratory $R^2 \ge 0.75$ gate is formally deferred and non-blocking for engineering delivery. On the unconstrained proxy corpus, the model achieves $R^2 \approx 0.48 - 0.51$ (a **+988% lift over the category-mean baseline** of $0.044$), matching the mutual information ceiling of text-only proxy data. When extreme outliers are filtered (Issue #93), validation $R^2$ reaches **$0.7327$**.
* **Zero-Leakage Experimental Ledger:** Single-variable sensitivity evaluations (PCA scree analysis, target transformations, neighborhood sweeps, feature ablations, text representation, repeated-seed diagnostics, and description-group disjoint splits) are cataloged in [docs/experiments/README.md](docs/experiments/README.md) and [docs/experiments/170_empirical_evaluation_and_random_search.md](docs/experiments/170_empirical_evaluation_and_random_search.md).

---

## 🧪 Testing & Verification

The test suite enforces mathematical invariants, parity, zero data leakage, and security gates:
```bash
pytest
# ======================= 389 passed in 30.62s ========================
```
Key invariant assertions:
* $\Phi(\text{KE}, \text{KE}) = 1.0000$ (Domestic Parity Invariant).
* $\Phi(\text{KE}, \text{US}) > 1.0000$ (Export Corridor Invariant).
* $\text{finalQuotedRate} = \text{basePredictedRate} + \text{mpesaTariffSurcharge}$ (Fee Invariant).
* $\text{minQuotedRate} \le \text{basePredictedRate} \le \text{maxQuotedRate}$ (Corridor Invariant).
* Strict train-only fitting for scalers, vectorizers, and indexers (Zero-Leakage Invariant).

---

## 📚 Documentation Index

* [Documentation Index & Plain-English Glossary](docs/README.md)
* [Canonical Architecture Blueprint (M9–M14)](docs/architecture_blueprint%20%281%29.md)
* [Project Milestones & Issue Breakdown](docs/Project_Milestones_and_Issues.md)
* [Label Provenance Audit (#91)](docs/Label_Provenance_Audit_91.md)
* [Experimental Evidence Index (#118)](docs/experiments/README.md)
* [Android Compose Implementation Guide](docs/Architecture/Android_App_Guide.md)
* [Interactive Pipeline Walkthrough Notebook](notebooks/pipeline_walkthrough.ipynb)

---

## 🎓 Academic Attribution

Developed as an academic thesis project at the **School of Computing and Engineering Sciences, Strathmore University, Nairobi, Kenya**.

```bibtex
@thesis{munyua2026dynamicpricing,
  author    = {Munyua, Jaedon Jeremiel},
  title     = {A Content-Based Dynamic Price Optimization Framework for Professional Mentorship Services in the Freelance Economy},
  school    = {School of Computing and Engineering Sciences, Strathmore University},
  year      = {2026},
  address   = {Nairobi, Kenya},
  type      = {Undergraduate Thesis}
}
```

---

## 📄 License

Distributed under the [MIT License](LICENSE.md).
