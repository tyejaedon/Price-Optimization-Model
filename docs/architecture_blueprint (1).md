# AI Dynamic Pricing Platform: Canonical Architectural Blueprint & Implementation Specification

This is the canonical **target architecture and migration plan** for the Content-Based Dynamic Price Optimization Framework, adopted in [M9.1 (#66)](https://github.com/tyejaedon/Price-Optimization-Model/issues/66). It describes intended behavior, not a claim that the Android app, authenticated API, Firestore pricing flow, OOT evaluation or corridor already exist. [Blueprint.md](Blueprint.md) and [Project_Milestones_and_Issues.md](Project_Milestones_and_Issues.md) retain the M1-M8 history and map it to the pivot; [README.md](../README.md) distinguishes the running service from this target.

**Decisions that override the proposal below:** Keep the existing `POST /api/v1/optimize-price` and `GET /health` routes; do not introduce `POST /price`. Extend the existing `src/api_contracts.py` (or add a documented adapter) instead of creating a competing `src/schemas.py`. Use this repository's `docs/`, `src/`, `tests/`, `data/` and `artifacts/` paths. Preserve `src/repository.py`, `src/observability.py` and `src/mlops_service.py`; the tree below lists pivot additions, not replacements. The browser demo is a future test harness (#85), not the Android client. The migration and ownership decisions in section 9 govern any examples below.

**Scope update (#91, 2026-10-04):** This is currently a computer-science implementation project. Verified mentor transaction data acquisition, empirical pricing validation and the proposed chronological OOT `R^2 >= 0.75` quality gate are deferred, **not prerequisites** for the M10-M14 API, Firestore, Android or deployment work. The existing training labels are proxy job budgets/profile asking rates, not verified mentor earnings. Retain deterministic software tests, artifact/train-serve parity, security and pricing invariants; label demo outputs and historical metrics honestly. The OOT/gate steps below describe a future research option, not the current definition of done. See [issue #91 audit](Label_Provenance_Audit_91.md).

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
| **Containerization & CI** | Docker, Uvicorn worker manager, GitHub Actions, Pytest | Containerized microservice deployment on port 8000, automated PR governance and software tests; empirical OOT quality gating is deferred. |

---

## 2. Directory Structure & File Placement Rules

Use the existing repository layout. The following are representative locations; files not yet present are **planned**, not prerequisites for running the current service:

```
Price-Optimization-Model/
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
│       └── harmonized_marketplace_corpus.parquet # Existing training corpus
├── demo/
│   └── index.html                        # Browser test harness (IR-06)
├── src/
│   ├── __init__.py
│   ├── config.py                         # Environment variables and system thresholds
│   ├── ingest_multisource.py             # Data ingestion, cleaning, USD->KES conversion
│   ├── nlp_pipeline.py                   # Regex sanitization, lemmatizer, TF-IDF, SVD
│   ├── macro_arbitrage.py                # Sovereign PPP ratio and CoL normalization
│   ├── spatial_engine.py                 # KD-Tree indexing, fallback logic, IDW regression
│   ├── tariff_evaluator.py               # Existing tariff evaluator; #73 reconciles schedule
│   ├── interval_synthesizer.py           # Bounded [Rate_min, Rate_max] derivation
│   ├── repository.py                     # Existing Firestore/in-memory boundary
│   ├── observability.py                  # Existing latency/error metrics
│   ├── mlops_service.py                  # Existing artifact publication
│   ├── firestore_sync.py                 # Planned background telemetry adapter
│   ├── security.py                       # Firebase Admin SDK RS256 token verification
│   ├── api_contracts.py                  # Existing Pydantic V2 DTOs; extend for pivot
│   ├── train_pipeline.py                 # Offline OOT chronological training & evaluation
│   └── serve.py                          # FastAPI application, startup hooks, REST endpoints
├── tests/
│   ├── test_nlp_pipeline.py
│   ├── test_macro_arbitrage.py
│   ├── test_spatial_engine.py
│   ├── test_tariff_evaluator.py
│   ├── test_train_pipeline.py
│   └── test_api_endpoints.py
├── Dockerfile                            # Planned container spec (port 8000)
├── requirements.txt                      # Frozen Python dependencies
└── .env.example                          # Planned environment template (no secrets)
```

`data/` (including raw and processed inputs), `artifacts/` and generated reports are ignored; never commit datasets, model binaries or service-account credentials. The browser `demo/` belongs to #85, and the Android `app/` belongs to #74-#76. Existing tests and modules not shown remain in place.

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

When `mentorCountry == 'KE'`, apply the validated M-Pesa consumer transfer schedule to calculate the additive surcharge. The 12-tier table below is a **proposed schedule for #73 to verify** against the existing evaluator and a dated source before production use, not a claim of current statutory rates. For non-Kenyan mentors (`mentorCountry != 'KE'`), $Surcharge_{M-Pesa} = 0.00$.

```
┌────────────────────────────────────────────────────────┐
│        Proposed M-Pesa 12-Tier Transfer Bands          │
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
    Repo->>Vault: Obtain current Firebase ID token
    Vault-->>Repo: Bearer Token
    Repo->>API: POST /api/v1/optimize-price (Payload + Bearer Header)
    API->>Auth: Verify JWT (RS256 signature, expiry, claims)
    Auth-->>API: Verified Firebase UID

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

    API-)DB: BackgroundTasks: Append /historical_transactions (Audit; failures observable)
    API-->>Repo: 200 OK (PredictionResultDTO JSON)
    Repo-->>VM: Result.Success(PredictionResultDTO)
    VM->>VM: Mutate StateFlow (PricingUiState.Success)
    VM-->>UI: Declarative Recomposition (Cards, Charts, Corridor)
```

---

## 5. Strict Data Contracts (Pydantic V2 Schemas)

The following is an illustrative **target wire contract**, not executable code to paste over the currently deployed models in `src/api_contracts.py`. #83 owns validation, OpenAPI and backward-compatible translation on the existing route; #84 owns hydration of omitted fields. The legacy snake_case DTO remains in use until that migration is implemented.

```python
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, constr

class PricingQueryDTO(BaseModel):
    mentorId: str = Field(..., description="Mentor document ID authorized for the verified Firebase UID")
    rawText: Optional[constr(min_length=20, max_length=2000)] = Field(
        default=None,
        description="Unstructured capability description. If None, hydrated from Firestore."
    )
    industry: str = Field(
        ...,
        description="Industry partition key (e.g., data_ai, mobile)"
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
        default=None, description="Optional mentor cost-of-living index override"
    )
    baseRateFloor: Optional[float] = Field(
        default=None, ge=0.0, description="Absolute reservation rate (KES/hour)"
    )

class PeerMatchDTO(BaseModel):
    listingId: str
    jobTitle: str
    verifiedRate: float
    similarityScore: float = Field(..., ge=0.0, le=1.0)
    euclideanDistance: float

class PredictionResultDTO(BaseModel):
    basePredictedRate: float = Field(..., description="Distance-weighted base rate (KES/hour)")
    mpesaTariffSurcharge: float = Field(..., description="M-Pesa fee added to hourly quote (KES/hour)")
    finalQuotedRate: float = Field(..., description="Base rate + tariff surcharge (KES/hour)")
    minQuotedRate: float = Field(..., description="Negotiation floor (KES/hour)")
    maxQuotedRate: float = Field(..., description="Arbitrage-scaled value ceiling (KES/hour)")
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
  "mpesa_tariff_surcharge": 57.0,
  "final_quoted_rate": 4757.0,
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
* **Android authentication:** #75 decides secure token handling. The following encrypted-preferences example is illustrative, not a requirement to persist Firebase ID tokens; prefer a fresh token from the Firebase Auth SDK and never embed admin credentials in the client.
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

These are delivery stages, not instructions to reimplement completed M1-M8 work. The **mapping and overrides in section 9** supersede the provisional sprint task lists below.

### Sprint 1: Blueprint and offline model alignment (Milestone 9: #66, #67, #81)
* **Target File:** `src/train_pipeline.py`, `src/nlp_pipeline.py`, `src/macro_arbitrage.py`
* **Actions:**
  1. Reuse existing dataset parsing and accepted KES/hour bounds; do not re-ingest or commit local datasets.
  2. Implement chronological Out-of-Time (OOT) temporal partition:
     $$S_{train} = \{x_t \mid t \le T_{split}\},\quad S_{eval} = \{x_t \mid t > T_{split}\}$$
  3. Fit NLTK Lemmatizer + TF-IDF (12,000 features) + Truncated SVD (50 components) exclusively on $S_{train}$.
  4. Build Scikit-Learn `KDTree(metric='euclidean', leaf_size=40)` across 8 industry categories.
  5. **Deferred empirical option:** Assess the proposed $R^2 \ge 0.75$ OOT target on an appropriate dated population. For current engineering work, serialize compatible `.joblib` demonstration artifacts without claiming validated mentor-pricing accuracy.

### Sprint 2: In-memory inference, corridor and protected gateway (Milestone 10: #69, #70, #82, #83)
* **Target File:** `src/spatial_engine.py`, `src/tariff_evaluator.py`, `src/interval_synthesizer.py`
* **Actions:**
  1. Extend the existing `InferenceRuntime` to load a compatible `.joblib` artifact set into RAM on boot.
  2. Implement Euclidean search with partition fallback to `general_tech`.
  3. Implement IDW regression ($p=2.0, \epsilon=10^{-6}$).
  4. Implement bounded corridor synthesis ($[Rate_{min}, Rate_{max}]$), including contradictory floor/ceiling handling under #82.
  5. Reuse the tariff evaluator; validate any schedule changes under #73.

### Sprint 3: Firestore persistence and asynchronous pricing audit (Milestone 11: #71, #72, #73, #84)
* **Target Files:** `src/repository.py`, `src/observability.py`, `src/serve.py` (reuse); `src/firestore_sync.py` (if needed).
* **Actions:**
  1. Reuse the existing FastAPI lifespan to load artifacts in memory.
  2. Reuse `GET /health` and `POST /api/v1/optimize-price`; do not create another route.
  3. Add `TokenVerificationService` extracting and verifying Firebase RS256 Bearer tokens.
  4. Use `BackgroundTasks` to append audit telemetry and expose failures via observability.
  5. Align Firestore service listings and mentor documents; containerization belongs to #77. Gateway authentication in this provisional list belongs to #69 in Milestone 10.

### Sprint 4: Native Android app presentation and auth (Milestone 12: #74, #75)
* **Target Package:** `app/src/main/java/edu/strathmore/pricing/`
* **Actions:**
  1. Build user authentication with Firebase Auth; obtain fresh ID tokens via the SDK and follow #75 for secure storage.
  2. Implement `PricingViewModel` and `PricingUiState` with Unidirectional Data Flow.
  3. Construct declarative Jetpack Compose UI: `CapabilityInputForm`, `BilateralCorridorSelector`, `SaturationSlider`.

### Sprint 5: Mobile-cloud integration and deployment (Milestone 13: #76, #77)
* **Target Package:** `app/src/main/java/edu/strathmore/pricing/network/`
* **Actions:**
  1. Configure Retrofit + OkHttp with Bearer token interceptor.
  2. Build Compose dashboard displaying `finalQuotedRate`, corridor $[Rate_{min}, Rate_{max}]$, and M-Pesa fee breakdown.
  3. Containerize the backend and gate the authenticated integration path in CI.

### Sprint 6: Demo and end-to-end validation (Milestone 14: #85, #86, #87)

1. Add the optional IR-06 browser harness as a protected-API test client, never an auth bypass.
2. Validate mobile round-trip latency under simulated 3G ($RTT < 3.0\text{s}$).
3. Conduct System Usability Scale testing ($SUS \ge 80.0$).

---

## 9. Migration decisions and ownership

| Boundary | Existing M1-M8 work | Pivot decision and owner |
| :--- | :--- | :--- |
| Data and model | Harmonized marketplace parquet, macro lookup, 50D SVD + 3 scaled metadata features, partitioned KD-Trees, IDW and joblib artifacts already exist. Rates and targets are **KES/hour**; labels are proxy job budgets/profile asking rates. | #67 reconciles fitted offline/online transforms, `k=5`, quadratic IDW (`p=2`, `epsilon=1e-6`) and artifact parity. #91 records data limits; #81's empirical OOT/R2 gate is deferred and does not block engineering or require verified mentor transactions. #95 tracks artifact compatibility/inference parity without score-based readiness. Do not treat old stratified 70/15/15 reports as OOT or real-world mentor-price evidence. |
| Metadata | Training uses `industry_partition`, mentor cost of living from the macro lookup, `market_saturation_score` and `competitiveness_score`; current API takes `selected_industry`. | The pivot wire field `industry` maps to an accepted partition key (`industry_id` in Firestore, `industry_partition` in training); reject unknown keys instead of silently mapping unrelated industries. `costOfLivingIndex` is an optional validated mentor CoL override, **not** an alias for saturation. `competitivenessScore` and training saturation remain distinct: #67/#83 must specify and test their feature mapping without changing the trained scaler's column order. |
| Identity and listings | Current pricing DTO has no mentor ID or token. Existing repository and admin endpoints are not a Firebase-protected pricing gateway. Peer payloads carry positional indices, not durable listing IDs. | #69 verifies server-side Firebase ID tokens and binds the authenticated UID to the requested `mentorId`; never trust a body ID as authentication. #71 binds actual root `/service_listings/{listing_id}` to peer coordinates; do not fabricate `listingId`, `jobTitle` or `verifiedRate`. #84 hydrates missing fields only from authorized records and fails explicitly when required data is absent. |
| API contract | `src/api_contracts.py` defines snake_case DTOs; `src/serve.py` implements `POST /api/v1/optimize-price` and `GET /health`. | #83 extends that module or supplies a clearly documented adapter for camelCase DTOs on **the same route**. Preserve old callers during a measured compatibility window, document deprecation in OpenAPI and README, and remove the legacy shape only in a separately tracked, versioned breaking change after client migration; #68 is closed as superseded, not reopened. #82 owns corridor invariants and handling of out-of-range floors. Missing artifacts return explicit unready health and HTTP 503, not invented predictions. |
| Authentication and credentials | Local model testing needs no Firebase keys. Existing admin-token operations are separate from user pricing authentication. | #69 owns Firebase Admin initialization, token verification and authorization in the backend; credentials come from runtime secret management/application-default credentials, never Android, HTML, Git, `data/` or bundled artifacts. #75 owns Android Firebase Auth and token refresh/secure handling. #85 requires a temporary externally supplied test token and scoped CORS; never bypass verification in the demo. |
| Deployment and failure reporting | `src/mlops_service.py` has versioned artifact publication; `src/observability.py` records metrics; repository supports memory and Firestore modes. | #70/#77 package a complete, versioned set of trained artifacts outside Git with the container or mounted at deployment; startup loads once using the existing lifespan and reports missing/incompatible sets as unready. #72 records append-only audit failures in metrics/logs with correlation identifiers, not a false success; no raw text, tokens or credentials in logs. Firestore unavailability must not silently turn a protected production request into an in-memory write. |

The example DTOs and sample documents above are design illustrations: #83/#71 own their final validated schema, including whether omitted country and metadata fields can be hydrated safely under #84. The formulae are target requirements subject to targeted tests and rollout, not guarantees about the present service.