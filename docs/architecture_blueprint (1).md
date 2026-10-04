# AI Dynamic Pricing Platform: Canonical Architectural Blueprint & Implementation Specification

This document is the authoritative, zero-ambiguity system blueprint for the **Content-Based Dynamic Price Optimization Framework**. It provides exact mathematical formulas, system interaction models, data contracts, database schemas, directory layouts, and execution steps required to build and deploy the entire solution.

---

## 1. System Topology & Technology Stack

| Layer | Technology | Operational Responsibilities |
| :--- | :--- | :--- |
| **Presentation Tier** | Native Android (Kotlin 1.9+, Jetpack Compose, Coroutines, Flow) | Declarative UI, MVVM pattern, Unidirectional Data Flow (UDF), Retrofit REST client, biometric/session state. |
| **Security & Keystore** | Android Jetpack Security (`EncryptedSharedPreferences`) | AES-256-GCM token storage backed by hardware Android Keystore Provider (TEE/SE). |
| **Ingestion Gateway** | Python 3.11, FastAPI (ASGI), Uvicorn, Pydantic V2 | Asynchronous non-blocking HTTP gateway, Firebase RS256 JWT authentication, request validation, CORS, error envelopes. |
| **ML Inference Engine** | Scikit-Learn, NLTK (WordNet), NumPy, SciPy | 50D SVD NLP reduction, 3D metadata scaling, 53D coordinate fusion, partitioned KD-Tree spatial indexing, IDW regression. |
| **Persistence Tier** | Google Cloud Firestore (NoSQL Document Store) | User aggregate documents, service listings with native vector arrays, append-only historical audit telemetry, cached tariff schedules. |
| **Authentication** | Firebase Authentication & Firebase Admin SDK | RS256 cryptographic JSON Web Token issuance and remote validation. |
| **Containerization & CI** | Docker, Uvicorn worker manager, GitHub Actions, Pytest | Containerized microservice deployment on port 8000, automated PR governance, temporal OOT quality gating ($R^2 \ge 0.75$). |

---

## 2. Directory Structure & File Placement Rules

Every code generator or developer must strictly adhere to this standardized repository tree:

```
mentor-pricing-engine/
├── .github/
│   └── workflows/
│       ├── pr-governance.yml             # Branch naming and PR checklist gate
│       └── ci-checks.yml                 # Pytest, file size check, linting
├── artifacts/                            # Serialized model binaries (git-ignored)
│   ├── tfidf_vectorizer.joblib           # TF-IDF unigram/bigram model (12k features)
│   ├── svd_reducer.joblib                # Truncated SVD matrix (50 components)
│   ├── metadata_scaler.joblib            # Min-Max normalizer for 3D metadata
│   ├── industry_kdtrees.joblib           # Partitioned Scikit-Learn KD-Trees dictionary
│   └── training_summary.json             # Metrics ledger (RMSE, MAE, R^2, OOT cutoff)
├── data/
│   ├── raw/                              # Secondary corpus CSVs (git-ignored)
│   └── processed/
│       ├── macro_lookup_table.json       # Sovereign PPP and CoL dictionary
│       └── harmonized_corpus.parquet     # Unified training corpus
├── demo/
│   └── index.html                        # Browser test harness (IR-06)
├── src/
│   ├── __init__.py
│   ├── config.py                         # Environment variables and system thresholds
│   ├── ingest_multisource.py             # Data ingestion, cleaning, USD->KES conversion
│   ├── nlp_pipeline.py                   # Regex sanitization, lemmatizer, TF-IDF, SVD
│   ├── macro_arbitrage.py                # Sovereign PPP ratio and CoL normalization
│   ├── spatial_engine.py                 # KD-Tree indexing, fallback logic, IDW regression
│   ├── tariff_evaluator.py               # Safaricom 12-tier statutory surcharge lookup
│   ├── interval_synthesizer.py           # Bounded [Rate_min, Rate_max] derivation
│   ├── firestore_sync.py                 # Asynchronous background telemetry logging
│   ├── security.py                       # Firebase Admin SDK RS256 token verification
│   ├── schemas.py                        # Pydantic V2 DTOs (Request / Response / PeerMatch)
│   ├── train_pipeline.py                 # Offline OOT chronological training & evaluation
│   └── serve.py                          # FastAPI application, startup hooks, REST endpoints
├── tests/
│   ├── test_nlp_pipeline.py
│   ├── test_macro_arbitrage.py
│   ├── test_spatial_engine.py
│   ├── test_tariff_evaluator.py
│   ├── test_train_pipeline.py
│   └── test_api_endpoints.py
├── Dockerfile                            # Production container spec (port 8000)
├── requirements.txt                      # Frozen Python dependencies
└── .env.example                          # Environment template (no secrets in repo)
```

---

## 3. Mathematical Foundations & Algorithmic Invariants

### 3.1 Feature Space Decomposition ($q \in \mathbb{R}^{53}$)

```
         ┌────────────────────────────────────────────────────────┐
         │              53-Dimensional Vector (q)                 │
         └──────────────────────────┬─────────────────────────────┘
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
┌─────────────────────────┐                       ┌─────────────────────────┐
│ Latent Text Vector      │                       │ Continuous Metadata     │
│ q_text ∈ ℝ^50           │                       │ q_meta ∈ ℝ^3            │
├─────────────────────────┤                       ├─────────────────────────┤
│ • Unigram/Bigram TF-IDF │                       │ • Φ(m, c): PPP Arbitrage│
│ • Lemmatization         │                       │ • Cost_m: Mentor CoL    │
│ • Truncated SVD (D=50)  │                       │ • Saturation: Niche Comp│
└─────────────────────────┘                       └─────────────────────────┘
```

1. **Text Transformation ($q_{text} \in \mathbb{R}^{50}$):**
   * Preprocessing: Convert to lowercase, strip URLs, special characters, and numeric digits using regex.
   * Lemmatization: Apply NLTK WordNet Lemmatization; prune English stop words and tokens with length $\le 2$.
   * TF-IDF Vectorization: $n \in [1, 2]$, sublinear term frequency scaling, document frequency limits $df \in [2, 0.95]$, max vocabulary $V = 12{,}000$.
   * Latent Semantic Analysis: Compress the sparse $12{,}000$-dimensional vector using Truncated Singular Value Decomposition (SVD) to $D = 50$ latent semantic components:
     $$q_{text} = \text{SVD}_{50}(\text{TF-IDF}(rawText)) \in \mathbb{R}^{50}$$

2. **Bilateral Macroeconomic Arbitrage ($\Phi(m,c)$):**
   * Balances provider domestic cost-of-living with client economic purchasing power:
     $$\Phi(m, c) = (1 - \alpha) \cdot \frac{PPP_m}{PPP_c} + \alpha \cdot \frac{Cost_m}{Cost_c}$$
     * $\alpha = 0.50$ (equitable split).
     * For domestic transactions ($m = \text{'KE'}, c = \text{'KE'}$): $\Phi(\text{KE}, \text{KE}) = 1.00$.
     * For export corridors ($m = \text{'KE'}, c = \text{'US'}$): $\Phi(\text{KE}, \text{US}) \approx 0.51$.

3. **Continuous Metadata Normalization ($q_{meta} \in \mathbb{R}^3$):**
   * Normalize continuous attributes into the closed interval $[0.0, 1.0]$ via Min-Max Scaling:
     $$x_{scaled} = \frac{x - x_{min}}{x_{max} - x_{min}}$$
     $$q_{meta} = [\text{Scale}(\Phi(m,c)),\; \text{Scale}(Cost_m),\; \text{Scale}(Saturation)] \in \mathbb{R}^3$$

4. **Coordinate Fusion:**
   $$q = [q_{text} \mid q_{meta}] \in \mathbb{R}^{53}$$

---

### 3.2 Partitioned KD-Tree Retrieval & Spatial Regression

1. **Categorical Partitioning:**
   * Pre-filter coordinates into isolated K-Dimensional Trees partitioned by `industry_id`:
     `["data_ai", "web_backend", "mobile", "devops_cloud", "design_creative", "product_management", "digital_marketing", "general_tech"]`
   * **Fallback Routing Rule:** If the requested niche tree contains fewer records than $k=5$, query execution automatically falls back to `general_tech`.

2. **Inverse Distance Weighting (IDW) Regression:**
   * Query the partitioned KD-Tree for the $k=5$ nearest peer nodes under Euclidean distance $d(q, x_i)$.
   * Weight each neighbor using quadratic distance penalization ($p = 2.0$) with zero-division guard ($\epsilon = 10^{-6}$):
     $$w_i = \frac{1}{d(q, x_i)^2 + 10^{-6}}$$
   * Aggregate base market clearing rate ($\hat{y}_{base}$):
     $$\hat{y}_{base} = \frac{\sum_{i=1}^{k} w_i \cdot y_i}{\sum_{i=1}^{k} w_i}$$

---

### 3.3 Bounded Interval Synthesis ($[Rate_{min}, Rate_{max}]$ — FR-06)

To output an actionable, economically defensible pricing corridor rather than a single static quote:

1. **Peer Weighted Standard Deviation ($\sigma_{peers}$):**
   $$\sigma_{peers} = \sqrt{\frac{\sum_{i=1}^{k} w_i \cdot (y_i - \hat{y}_{base})^2}{\sum_{i=1}^{k} w_i}}$$

2. **Minimum Quoted Rate ($Rate_{min}$ — Negotiation Floor):**
   * Protects the consultant from underpricing while maintaining client accessibility:
     $$Rate_{min} = \max\left(baseRateFloor,\; \hat{y}_{base} - 0.75 \cdot \sigma_{peers}\right)$$
   * If `baseRateFloor` is omitted by the user, $baseRateFloor = 0.50 \cdot \hat{y}_{base}$.

3. **Maximum Quoted Rate ($Rate_{max}$ — Value Ceiling):**
   * Scales upward based on peer dispersion and cross-border purchasing power arbitrage:
     $$\text{ArbitrageMultiplier} = \begin{cases} 1.0 + (1.0 - \Phi(m,c)), & \text{if } \Phi(m,c) < 1.0 \text{ (Export Corridor)} \\ 1.0, & \text{if } \Phi(m,c) \ge 1.0 \text{ (Domestic / Regional)} \end{cases}$$
     $$Rate_{max} = \left(\hat{y}_{base} + 1.25 \cdot \sigma_{peers}\right) \cdot \text{ArbitrageMultiplier}$$

---

### 3.4 Safaricom M-Pesa 12-Tier Tariff Lookup Table (FR-07)

When `mentorCountry == 'KE'`, apply the official Safaricom regulatory transfer fee schedule to calculate the additive surcharge. For international corridors (`mentorCountry != 'KE'`), $Surcharge_{M-Pesa} = 0.00$.

```
┌────────────────────────────────────────────────────────┐
│        Safaricom M-Pesa 12-Tier Statutory Bands        │
├───────┬──────────────────────────┬─────────────────────┤
│ Tier  │ Transaction Range (KES)  │ Transfer Fee (KES)  │
├───────┼──────────────────────────┼─────────────────────┤
│ 1     │ 10.00 - 100.00           │ 0.00                │
│ 2     │ 101.00 - 500.00          │ 7.00                │
│ 3     │ 501.00 - 1,000.00        │ 13.00               │
│ 4     │ 1,001.00 - 1,500.00      │ 23.00               │
│ 5     │ 1,501.00 - 2,500.00      │ 34.00               │
│ 6     │ 2,501.00 - 3,500.00      │ 53.00               │
│ 7     │ 3,501.00 - 5,000.00      │ 57.00               │
│ 8     │ 5,001.00 - 7,500.00      │ 78.00               │
│ 9     │ 7,501.00 - 10,000.00     │ 90.00               │
│ 10    │ 10,001.00 - 15,000.00    │ 105.00              │
│ 11    │ 15,001.00 - 20,000.00    │ 115.00              │
│ 12    │ 20,001.00 - 250,000.00   │ 130.00              │
└───────┴──────────────────────────┴─────────────────────┘
```

**Final Billed Rate:**
$$\hat{y}_{final} = \hat{y}_{base} + Surcharge_{M-Pesa}$$

---

## 4. End-to-End System Sequence Diagram

```
sequenceDiagram
    autonumber
    participant UI as Jetpack Compose UI
    participant VM as PricingViewModel
    participant Repo as PricingRepositoryImpl
    participant Vault as EncryptedPrefs (Keystore)
    participant API as FastAPI Ingestion Gateway
    participant Auth as Firebase Admin SDK
    participant Core as In-Memory ML Runtime
    participant DB as Google Cloud Firestore

    UI->>VM: Submit form (Listing text + metadata)
    VM->>Repo: optimizePrice(PricingQueryDTO)
    Repo->>Vault: Read cached RS256 JWT
    Vault-->>Repo: Bearer Token
    Repo->>API: POST /api/v1/optimize-price (Payload + Bearer Header)
    API->>Auth: Verify JWT (RS256 signature, expiry, claims)
    Auth-->>API: DecodedTokenDTO (UID, Role)

    alt Profile Hydration Needed (FR-01)
        API->>DB: Fetch missing profile attributes (/mentors/{id})
        DB-->>API: Document attributes
    end

    par NLP Vectorization
        API->>Core: Lemmatize -> TF-IDF -> Truncated SVD (50D)
    and Metadata Scaling
        API->>Core: Compute Φ(m,c) -> Min-Max Scale (3D)
    end

    Core->>Core: Concatenate into 53D Vector (q)
    Core->>Core: Select Partition Tree (industry_id or fallback)
    Core->>Core: Query KD-Tree (k=5) & Compute IDW Rate (y_base)
    Core->>Core: Synthesize Corridor [Rate_min, Rate_max]
    Core->>Core: Check Tariff Schedule (MpesaTariffEvaluator)
    Core-->>API: PredictionResultDTO

    API-)DB: BackgroundTasks: Append /historical_transactions (Audit)
    API-->>Repo: 200 OK (PredictionResultDTO JSON)
    Repo-->>VM: Result.Success(PredictionResultDTO)
    VM->>VM: Mutate StateFlow (PricingUiState.Success)
    VM-->>UI: Declarative Recomposition (Cards, Charts, Corridor)
```

---

## 5. Strict Data Contracts (Pydantic V2 Schemas)

Place these schemas inside `src/schemas.py`:

```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, constr

class PricingQueryDTO(BaseModel):
    mentorId: str = Field(..., description="Unique mentor ID in Firebase")
    rawText: Optional[constr(min_length=20, max_length=2000)] = Field(
        default=None, 
        description="Unstructured capability description. If None, hydrated from Firestore."
    )
    industry: str = Field(
        ..., 
        description="Industry partition key (e.g., software_eng, data_ai, mobile)"
    )
    mentorCountry: constr(min_length=2, max_length=2) = Field(
        ..., description="ISO 3166-1 alpha-2 origin code"
    )
    clientCountry: constr(min_length=2, max_length=2) = Field(
        ..., description="ISO 3166-1 alpha-2 client destination code"
    )
    competitivenessScore: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Self-reported saturation ratio"
    )
    costOfLivingIndex: Optional[float] = Field(
        default=None, description="Optional Numbeo CoL index override"
    )
    baseRateFloor: Optional[float] = Field(
        default=None, ge=0.0, description="Absolute reservation hourly rate (KES)"
    )

class PeerMatchDTO(BaseModel):
    listingId: str
    jobTitle: str
    verifiedRate: float
    similarityScore: float = Field(..., ge=0.0, le=1.0)
    euclideanDistance: float

class PredictionResultDTO(BaseModel):
    basePredictedRate: float = Field(..., description="Distance-weighted base rate (KES)")
    mpesaTariffSurcharge: float = Field(..., description="Statutory M-Pesa fee (KES)")
    finalQuotedRate: float = Field(..., description="Base rate + tariff surcharge (KES)")
    minQuotedRate: float = Field(..., description="Negotiation floor (KES)")
    maxQuotedRate: float = Field(..., description="Arbitrage-scaled value ceiling (KES)")
    kNeighborsUsed: int = Field(default=5)
    bilateralArbitrageFactor: float = Field(..., description="Evaluated Phi(m, c)")
    confidenceScore: float = Field(..., ge=0.0, le=1.0)
    comparables: List[PeerMatchDTO]
    reason: str = Field(..., description="Natural language justification of the rate")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class HealthStatusDTO(BaseModel):
    status: str = "healthy"
    service: str = "pricing-engine"
    unit: str = "KES"
    modelsLoaded: bool
    version: str = "1.0.0"
```

---

## 6. Persistence Schema: Google Cloud Firestore

The database structure relies on denormalized collections to eliminate latency during real-time retrieval:

### 6.1 Collection: `/mentors/{mentor_id}`
```json
{
  "mentor_id": "firebase_auth_uid_169684",
  "full_name": "Jaedon Jeremiel",
  "email": "jaedon@strathmore.edu",
  "country_code": "KE",
  "purchasing_power_parity": 48.2,
  "cost_of_living_index": 42.1,
  "created_at": "2026-06-11T10:00:00Z"
}
```

### 6.2 Collection: `/service_listings/{listing_id}`
*Stored at the root collection level to enable direct partition scanning without collection-group indexing.*
```json
{
  "listing_id": "list_88923a",
  "mentor_ref": "/mentors/firebase_auth_uid_169684",
  "industry_id": "mobile",
  "title": "Senior Android Architect & Kotlin Mentor",
  "raw_description": "Senior engineer with 6+ years experience in Jetpack Compose, MVVM...",
  "latent_svd_vector": [0.0412, -0.1284, 0.0891, "...50 floats total"],
  "market_competitiveness": 0.65,
  "base_rate_floor": 2500.0,
  "is_active": true,
  "created_at": "2026-06-11T10:30:00Z"
}
```

### 6.3 Collection: `/historical_transactions/{transaction_id}`
*Append-only audit ledger dispatched asynchronously by `BackgroundTasks`.*
```json
{
  "transaction_id": "tx_20261004_9921",
  "mentor_id": "firebase_auth_uid_169684",
  "industry_id": "mobile",
  "mentor_country": "KE",
  "client_country": "US",
  "bilateral_arbitrage_phi": 0.51,
  "base_predicted_rate": 4700.0,
  "mpesa_tariff_surcharge": 150.0,
  "final_quoted_rate": 4850.0,
  "min_quoted_rate": 4200.0,
  "max_quoted_rate": 6500.0,
  "k_neighbors_used": 5,
  "retrieved_peers": ["list_001", "list_045", "list_112", "list_210", "list_089"],
  "executed_at": "2026-10-04T15:21:07Z"
}
```

---

## 7. Native Android Presentation Tier Specifications

* **Toolkit:** Jetpack Compose exclusively (zero XML layouts).
* **State Holder:** `PricingViewModel` exposing `StateFlow<PricingUiState>`.
* **State Definition:**
  ```kotlin
  sealed interface PricingUiState {
      object Idle : PricingUiState
      object Loading : PricingUiState
      data class Success(val result: PredictionResultDTO) : PricingUiState
      data class Error(val message: String) : PricingUiState
  }
  ```
* **Hardware-Backed Security:** Store the Firebase JWT in Android Keystore:
  ```kotlin
  val masterKey = MasterKey.Builder(context)
      .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
      .build()

  val securePrefs = EncryptedSharedPreferences.create(
      context,
      "secure_auth_prefs",
      masterKey,
      EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
      EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
  )
  ```
* **Coroutines Rule:** All network operations via Retrofit and SharedPreferences reads must execute on `Dispatchers.IO` to ensure 60 fps UI performance.

---

## 8. Step-by-Step Implementation Roadmap (Sprint Plan)

Instruct your Copilot to execute following this exact order:

### Sprint 1: Offline ML Pipeline & Artifact Compilation
* **Target File:** `src/train_pipeline.py`, `src/nlp_pipeline.py`, `src/macro_arbitrage.py`
* **Actions:**
  1. Implement dataset parsing with IQR outlier filtering ($500 \le \text{rate} \le 35{,}000\text{ KES/hr}$).
  2. Implement chronological Out-of-Time (OOT) temporal partition:
     $$S_{train} = \{x_t \mid t \le T_{split}\},\quad S_{eval} = \{x_t \mid t > T_{split}\}$$
  3. Fit NLTK Lemmatizer + TF-IDF (12,000 features) + Truncated SVD (50 components) exclusively on $S_{train}$.
  4. Build Scikit-Learn `KDTree(metric='euclidean', leaf_size=40)` across 8 industry categories.
  5. Assert Quality Gate: $R^2 \ge 0.75$, serialize `.joblib` artifacts into `artifacts/`.

### Sprint 2: In-Memory Inference Core & Tariff Service
* **Target File:** `src/spatial_engine.py`, `src/tariff_evaluator.py`, `src/interval_synthesizer.py`
* **Actions:**
  1. Implement `InferenceRuntime` class to load `.joblib` artifacts into RAM on boot.
  2. Implement Euclidean search with partition fallback to `general_tech`.
  3. Implement IDW regression ($p=2.0, \epsilon=10^{-6}$).
  4. Implement bounded corridor synthesizer ($[Rate_{min}, Rate_{max}]$).
  5. Implement 12-tier Safaricom M-Pesa tariff boundary lookup.

### Sprint 3: FastAPI Gateway & Security Boundary
* **Target File:** `src/serve.py`, `src/security.py`, `src/firestore_sync.py`
* **Actions:**
  1. Initialize FastAPI with `@app.on_event("startup")` loading artifacts in memory.
  2. Expose `GET /health` and `POST /api/v1/optimize-price`.
  3. Add `TokenVerificationService` extracting and verifying Firebase RS256 Bearer tokens.
  4. Use `BackgroundTasks` to write audit telemetry to Firestore asynchronously.
  5. Containerize via `Dockerfile` (Python 3.11-slim, expose port 8000).

### Sprint 4: Native Android App Presentation & Auth
* **Target Package:** `app/src/main/java/edu/strathmore/pricing/`
* **Actions:**
  1. Build user authentication with Firebase Auth; store JWT in `EncryptedSharedPreferences`.
  2. Implement `PricingViewModel` and `PricingUiState` with Unidirectional Data Flow.
  3. Construct declarative Jetpack Compose UI: `CapabilityInputForm`, `BilateralCorridorSelector`, `SaturationSlider`.

### Sprint 5: Mobile-Cloud Integration & Usability Validation
* **Target Package:** `app/src/main/java/edu/strathmore/pricing/network/`
* **Actions:**
  1. Configure Retrofit + OkHttp with Bearer token interceptor.
  2. Build Compose dashboard displaying `finalQuotedRate`, corridor $[Rate_{min}, Rate_{max}]$, and M-Pesa fee breakdown.
  3. Validate end-to-end network latency under simulated 3G cellular network ($RTT < 3.0\text{s}$).
  4. Conduct System Usability Scale testing ($SUS \ge 80.0$).