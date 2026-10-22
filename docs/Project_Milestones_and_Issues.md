# Project Milestones & Engineering Issue Breakdown

This document retains the **M1-M8 execution history** for the Price Optimization Model Feature Track. The [canonical pivot blueprint](architecture_blueprint%20%281%29.md) and its section 9 govern M9-M14. The M1-M8 issue checkboxes below reflect original acceptance criteria, not current GitHub issue states; do not reopen completed issues based on unchecked boxes.

---

## Roadmap Overview

```text
Milestone 1: Data Ingestion & Macroeconomic Harmonization
      |
      v
Milestone 2: Semantic NLP & Dimensionality Reduction Pipeline
      |
      v
Milestone 3: Bilateral Arbitrage Scaler & Coordinate Fusion
      |
      v
Milestone 4: Partitioned Spatial Indexing & IDW Regression
      |
      v
Milestone 5: Localized Financial Margin Protection (M-Pesa)
      |
      v
Milestone 6: Master Pipeline Training, Validation & Auditing
      |
      v
Milestone 7: Production ASGI API Service (FastAPI)
      |
      v
Milestone 8: Automated Verification, Latency Profiling & MLOps
      |
      v
Milestones 9-14: Canonical Pivot, Auth, Mobile & Usability
      |
      v
Milestone 15: System Documentation, AI/ML Implementation & Empirical Evaluation
      |
      v
Milestone 16: Advanced Algorithmic Optimization, Vector Search Scaling & Continuous MLOps
```

---

## Milestone 1: Multi-Source Data Ingestion & Macroeconomic Harmonization

**Goal:** Ingest and clean local raw datasets, normalize market pricing records, and construct sovereign macroeconomic lookup artifacts.

**Deliverables:**
- `data/processed/macro_lookup_table.json`
- `data/processed/harmonized_marketplace_corpus.parquet`

### Issue M1.1 — Build Automated File Discovery & Macroeconomic Lookup Extractor
**Labels:** `data-engineering`, `macroeconomics`, `project:feature-track`

**Tasks**
- [ ] Implement `find_file_in_dir()` utility for recursive raw-file discovery
- [ ] Extract `PA.NUS.PPP` indicator from World Development Indicators
- [ ] Normalize country codes from ISO-3 to ISO-2
- [ ] Parse and standardize cost-of-living metrics from `Cost_Index`
- [ ] Export fallback macro records to `data/processed/macro_lookup_table.json`

**Acceptance Criteria**
- [ ] Lookup file exists and contains baseline records for `KE`, `UG`, `TZ`, `RW`, `US`, `GB`, `DE`, `CA`, and `IN`
- [ ] Country-code normalization is unit tested
- [ ] Lookup access is deterministic and non-blocking

**Dependency Notes**
- Blocks `M1.3`

### Issue M1.2 — Parse Freelance Marketplace Corpus & Harmonize Currency
**Labels:** `data-engineering`, `nlp-prep`, `project:feature-track`

**Tasks**
- [ ] Ingest `upwork-jobs.csv` and `Data_Scientist_Upwork` datasets
- [ ] Filter out non-hourly and low-signal records with descriptions shorter than 40 characters
- [ ] Convert pricing to KES using the agreed USD→KES rate anchor
- [ ] Remove rate outliers outside `500` to `35000` KES/hour
- [ ] Implement `map_industry_partition()` for target industry buckets

**Acceptance Criteria**
- [ ] No critical nulls remain in `raw_description`, `industry_partition`, or `hourly_rate`
- [ ] All retained rates fall within the accepted KES bounds
- [ ] Industry mapping covers all supported target domains

**Dependency Notes**
- Blocks `M1.3`

### Issue M1.3 — Compute Bilateral Arbitrage Factors & Export Harmonized Parquet
**Labels:** `data-engineering`, `pipeline`, `project:feature-track`

**Tasks**
- [ ] Join cleaned marketplace records with the macro lookup table
- [ ] Compute bilateral arbitrage factor using `alpha = 0.50`
- [ ] Compute market saturation features from industry frequencies
- [ ] Export `harmonized_marketplace_corpus.parquet` with `pyarrow`

**Acceptance Criteria**
- [ ] Exported parquet is readable with `pd.read_parquet()`
- [ ] Domestic `KE -> KE` parity resolves to `1.0`
- [ ] Harmonized corpus is ready for downstream feature engineering

**Dependency Notes**
- Depends on `M1.1` and `M1.2`
- Blocks `M6.1`

### Issues M1.4-M1.6 — Validate and Expand Country Coverage (#59-#61)

Macro lookup country support is derived from the intersection of usable WDI
`PA.NUS.PPP` observations and positive cost-of-living rows. ISO-3 to ISO-2
conversion uses `pycountry`; a few source-specific cost-country names have
explicit aliases. New countries are included only when both inputs are present.
The original nine baseline countries remain in the lookup; Rwanda retains its
existing cost-index fallback. Other unsupported or partially covered countries
are excluded, and `validate_macro_country_coverage(raw_dir, ["NG", ...])`
reports missing source rows for explicitly requested countries.
The selected country set and lookup records are deterministic for fixed inputs;
the existing generation timestamp in lookup metadata changes on each run.

Place the DataBank export in the ignored
`data/raw/World_Development_Indicators/` directory as `Data.csv` or with a
filename containing `_Data` (for example, `World_Data.csv`). Its first row must include
`Country Name`, `Country Code`, `Series Code`, and year columns. Build the ignored
`data/processed/macro_lookup_table.json` with
`python -m src.ingest_multisource --mode macro_lookup`. Do not commit raw CSVs
or generated lookup artifacts.

---

## Milestone 2: Semantic NLP & Dimensionality Reduction Pipeline

**Goal:** Build a robust NLP processor that cleans text, computes TF-IDF features, and reduces dimensionality to a stable latent space.

**Deliverables:**
- `src/nlp_pipeline.py`
- `artifacts/tfidf_vectorizer.joblib`
- `artifacts/svd_reducer.joblib`

### Issue M2.1 — Implement Text Sanitization & Morphological Lemmatization
**Labels:** `nlp`, `preprocessing`, `project:feature-track`

**Tasks**
- [ ] Initialize NLTK stop words and WordNet lemmatizer
- [ ] Remove URLs, digits, punctuation, and noisy symbols with regex cleaning
- [ ] Ignore tokens with length less than or equal to 2
- [ ] Produce normalized token strings suitable for TF-IDF processing

**Acceptance Criteria**
- [ ] Sample noisy profiles reduce to clean, normalized lemma sequences
- [ ] The sanitizer is deterministic across repeated runs
- [ ] Failure modes for empty or near-empty text are handled safely

**Dependency Notes**
- Blocks `M2.2`

### Issue M2.2 — Build TF-IDF Vectorizer & Truncated SVD Reducer
**Labels:** `nlp`, `machine-learning`, `project:feature-track`

**Tasks**
- [ ] Configure `TfidfVectorizer` with target n-gram and vocabulary limits
- [ ] Integrate `TruncatedSVD(n_components=50, random_state=42)`
- [ ] Implement `fit_transform()`, `transform()`, `save_artifacts()`, and `load_artifacts()`
- [ ] Audit cumulative explained variance across the reduced dimensions

**Acceptance Criteria**
- [ ] Each transformed document returns a dense vector of shape `(50,)`
- [ ] Artifacts can be saved and loaded without shape drift
- [ ] Per-document transform time stays below the target threshold in local profiling

**Dependency Notes**
- Depends on `M2.1`
- Blocks `M6.1` and `M7.2`

---

## Milestone 3: Bilateral Arbitrage Scaler & Coordinate Fusion

**Goal:** Normalize continuous macroeconomic metadata and combine it with dense NLP features into a unified hybrid coordinate space.

**Deliverables:**
- `src/macro_arbitrage.py`
- `artifacts/metadata_scaler.joblib`

### Issue M3.1 — Build Continuous Metadata Normalizer
**Labels:** `machine-learning`, `feature-engineering`, `project:feature-track`

**Tasks**
- [ ] Load cached `macro_lookup_table.json`
- [ ] Compute live bilateral arbitrage factor `Phi(m, c)`
- [ ] Fit `MinMaxScaler(feature_range=(0.0, 1.0))` across training metadata
- [ ] Save and load the scaler artifact reproducibly

**Acceptance Criteria**
- [ ] All transformed metadata values fall within `[0.0, 1.0]`
- [ ] Unknown country codes fall back safely to default anchors
- [ ] Serialization and reload retain transformation behavior

**Dependency Notes**
- Depends on `M1.1`
- Blocks `M3.2` and `M6.1`

### Issue M3.2 — Implement Hybrid Coordinate Fusion
**Labels:** `machine-learning`, `feature-engineering`, `project:feature-track`

**Tasks**
- [ ] Implement `fuse_coordinates(dense_text_vector, normalized_metadata)`
- [ ] Validate dimensions before concatenation
- [ ] Return immutable hybrid vectors for search and prediction

**Acceptance Criteria**
- [ ] Concatenation of 50-D text and 3-D metadata yields a `(53,)` vector
- [ ] Fusion rejects malformed input arrays with explicit validation errors
- [ ] Output is stable across repeated identical inputs

**Dependency Notes**
- Depends on `M2.2` and `M3.1`
- Blocks `M4.1` and `M8.1`

---

## Milestone 4: Partitioned Spatial Indexing & IDW Regression

**Goal:** Build the nearest-neighbor retrieval and explainable weighted-rate prediction engine.

**Deliverables:**
- `src/spatial_engine.py`
- `artifacts/industry_kdtrees.joblib`

### Issue M4.1 — Build Domain-Partitioned KD-Tree Indexer
**Labels:** `machine-learning`, `spatial`, `project:feature-track`

**Tasks**
- [ ] Partition training vectors by `industry_partition`
- [ ] Build `KDTree` indices with `leaf_size=40` and Euclidean distance
- [ ] Implement fallback routing for low-volume niche categories
- [ ] Persist trained tree structures for inference reuse

**Acceptance Criteria**
- [ ] A dedicated KD-Tree exists for every active supported domain
- [ ] Queries remain inside the chosen partition unless fallback is explicitly triggered
- [ ] Persisted tree artifacts can be reloaded for inference

**Dependency Notes**
- Depends on `M3.2`
- Blocks `M4.2`

### Issue M4.2 — Implement IDW Regression & Peer Explainability Payloads
**Labels:** `machine-learning`, `algorithms`, `project:feature-track`

**Tasks**
- [ ] Query top `k=5` nearest neighbors by distance and index
- [ ] Compute inverse-distance weights with epsilon protection
- [ ] Produce weighted base-rate prediction
- [ ] Return explainability payloads with peer index, rate, distance, and similarity

**Acceptance Criteria**
- [ ] Exact-match queries return stable results without division-by-zero errors
- [ ] Similarity scores remain bounded within `(0.0, 1.0]`
- [ ] Response includes all top-`k` peer explanations in a consistent schema

**Dependency Notes**
- Depends on `M4.1`
- Blocks `M6.2`, `M7.2`, and `M8.1`

---

## Milestone 5: Localized Financial Margin Protection (M-Pesa)

**Goal:** Protect domestic Kenyan take-home earnings by modeling Safaricom fee bands and adding the correct surcharge to the final quote.

**Deliverables:**
- `src/tariff_evaluator.py`

### Issue M5.1 — Implement Tiered M-Pesa Tariff Evaluator
**Labels:** `fintech`, `margin-protection`, `project:feature-track`

**Tasks**
- [ ] Encode the Safaricom tariff bands from low-value through high-value brackets
- [ ] Apply surcharge only when `mentor_country == 'KE'`
- [ ] Compute final quoted rate as base prediction plus tariff surcharge
- [ ] Return surcharge values in a form usable by the API layer

**Acceptance Criteria**
- [ ] A domestic KES `4500` case yields the expected KES `55` surcharge
- [ ] International mentor-country cases return `0.0` surcharge
- [ ] Bracket transitions are deterministic and edge-tested

**Dependency Notes**
- Blocks `M7.2` and `M8.1`

---

## Milestone 6: Master Pipeline Training, Validation & Auditing

**Goal:** Orchestrate training, validation, baseline comparison, and artifact serialization for the full pricing engine.

**Deliverables:**
- `src/train_pipeline.py`
- `artifacts/training_summary.json`
- serialized production artifacts in `artifacts/`

### Issue M6.1 — Build Stratified Split & Training Orchestration Pipeline
**Labels:** `machine-learning`, `model-training`, `project:feature-track`

**Tasks**
- [ ] Load `harmonized_marketplace_corpus.parquet`
- [ ] Execute 70/15/15 stratified train/validation/test splits
- [ ] Fit NLP and metadata components on the training partition only
- [ ] Transform validation and test partitions using frozen training artifacts

**Acceptance Criteria**
- [ ] No data leakage exists across splits
- [ ] Domain frequencies are preserved across all partitions
- [ ] The pipeline can run end-to-end from processed corpus to feature matrices

**Dependency Notes**
- Depends on `M1.3`, `M2.2`, and `M3.1`
- Blocks `M6.2`

### Issue M6.2 — Evaluate Model Quality, Benchmark Baseline & Serialize Artifacts
**Labels:** `machine-learning`, `evaluation`, `project:feature-track`

**Tasks**
- [ ] Compute validation RMSE and `R^2`
- [ ] Implement a category-mean baseline comparator
- [ ] Run held-out test evaluation using frozen artifacts
- [ ] Assert target quality threshold and write `training_summary.json`
- [ ] Serialize all inference-time components to `artifacts/`

**Acceptance Criteria**
- [ ] Validation and test metrics are logged and persisted
- [ ] The trained approach outperforms the category-mean baseline
- [ ] The target `R^2 >= 0.75` gate is enforced programmatically

**Dependency Notes**
- Depends on `M4.2` and `M6.1`
- Blocks `M7.2`

### M6.2 Experimental Scope Decision: Retain KNN for Production

Because of the scope of this feature track, production inference will continue to use the KNN-style peer pricing approach delivered in `M4.1` and `M4.2`: domain-partitioned KD-Tree retrieval with inverse-distance weighting and peer explainability.

The experimental workflow should focus on tuning the KNN approach rather than introducing a broad collection of production model families. Recommended experiments are:

- sweep `k_neighbors`,
- tune distance weighting and text/metadata block weights,
- evaluate raw versus `log1p(target_rate)` transformations,
- compare validation/test RMSE, MAE, median absolute error, and `R^2`, and
- use a category-mean model as the required baseline comparator.

Alternative regressors may be used as offline reference points in the report, but they are not production deliverables for this milestone. The production independent variables remain the 53-D hybrid coordinate, and the dependent variable remains `target_rate` in KES/hour.

### Issue M6.3 — Evaluate Target Transformations & Robust Error Metrics
**GitHub issue:** #35
**Labels:** `machine-learning`, `evaluation`, `project:feature-track`

**Goal:** Reduce the influence of extreme harmonized rates and report metrics that better represent practical pricing error.

**Scope:** Compare raw and `log1p(target_rate)` training targets, invert predictions with `expm1()`, and report RMSE, MAE, median absolute error, sMAPE, and R² for validation and test splits.

**Dependency Notes:** Extends M6.2 and preserves the KNN/IDW production target contract.

### Issue M6.4 — Expand KNN Hyperparameter & Hybrid-Distance Tuning
**GitHub issue:** #36
**Labels:** `machine-learning`, `algorithms`, `evaluation`, `project:feature-track`

**Goal:** Extend the KNN experiment beyond the current `k <= 10` sweep while keeping KNN/IDW as the production model family.

**Scope:** Sweep `k_neighbors` through `1, 3, 5, 7, 10, 15, 20, 30, 50`; tune partition thresholds, epsilon, fallback policy, text/metadata block weights, and normalized versus raw hybrid distances.

**Dependency Notes:** Extends M4.2 and M6.2.

### Issue M6.5 — Add Leakage-Safe Metadata Enrichment & Feature Ablations
**GitHub issue:** #37
**Labels:** `machine-learning`, `feature-engineering`, `evaluation`, `project:feature-track`

**Goal:** Add useful macroeconomic, partition, source, and country-pair features without leaking validation/test information.

**Scope:** Evaluate log bilateral factors, training-derived partition statistics, source indicators, country interactions, cost-of-living differences, PPP ratios, rate percentiles, and feature-group ablations.

**Dependency Notes:** Extends M1.3, M3.1, M4.2, and M6.2.

### Issue M6.6 — Evaluate Text Representation & Hybrid Normalization Settings
**GitHub issue:** #38
**Labels:** `nlp`, `feature-engineering`, `evaluation`, `project:feature-track`

**Goal:** Determine whether text dimensionality, n-gram settings, vocabulary limits, and normalization improve KNN retrieval while preserving the 50-D production compatibility path.

**Scope:** Compare SVD dimensions, n-gram ranges, `min_df`, vocabulary limits, normalized versus unnormalized text vectors, quality, latency, and artifact reload stability.

**Dependency Notes:** Extends M2.2, M3.2, M4.2, and M6.2.

### Issue M6.7 — Strengthen Leakage-Safe Validation & Per-Partition Diagnostics
**GitHub issue:** #39
**Labels:** `model-training`, `evaluation`, `qa`, `project:feature-track`

**Goal:** Make reported model progress robust to source imbalance, duplicates, metadata leakage, and weak industry partitions.

**Scope:** Add duplicate detection, source-grouped split comparisons, training-only aggregations, per-partition metrics, minimum-volume diagnostics, repeated-seed confidence intervals, and complete split metadata in reports.

**Dependency Notes:** Extends M6.1 and M6.2.

### Issue M8.3 — Create Canonical Model Class Diagram in PlantUML
**GitHub issue:** #50
**Labels:** `documentation`, `machine-learning`, `project:feature-track`

**Deliverable:** `docs/Architecture/PlantUML/model_class_diagram.puml` covering the implemented ingestion, feature engineering, spatial, tariff, training, API, and evaluation boundaries.

### Issue M8.4 — Create Canonical Pricing ERD in PlantUML
**GitHub issue:** #51
**Labels:** `documentation`, `qa`, `project:feature-track`

**Deliverable:** `docs/Architecture/PlantUML/model_erd.puml` aligned with the supplied ERD and showing domain entities, cardinalities, references, prediction fields, tariff fields, and audit fields.

### Issue M8.5 — Create Canonical System Architecture Diagram in PlantUML
**GitHub issue:** #52
**Labels:** `documentation`, `api`, `project:feature-track`

**Deliverable:** `docs/Architecture/PlantUML/system_architecture.puml` showing client, API, ML runtime, Firestore, external data, artifact loading, health, inference, KNN/IDW, and tariff boundaries.

### Issue M8.6 — Create Canonical Firestore Database Schema in PlantUML
**GitHub issue:** #53
**Labels:** `documentation`, `data-engineering`, `project:feature-track`

**Deliverable:** `docs/Architecture/PlantUML/firestore_database_schema.puml` aligned with the supplied database schema and Firestore collections: `mentors`, `macro_indices`, `industry_partitions`, `service_listings`, `mpesa_tariffs`, and `historical_transactions`.

---

## Milestone 7: Production ASGI API Service (FastAPI)

**Goal:** Expose the trained pricing engine through validated, low-latency, production-oriented HTTP endpoints.

**Deliverables:**
- `src/serve.py`

### Issue M7.1 — Define Pydantic V2 Request/Response Contracts
**Labels:** `api`, `schemas`, `project:feature-track`

**Tasks**
- [ ] Define `PricingQueryDTO` with strict field and range validation
- [ ] Define `PeerMatchDTO` and `PredictionResultDTO`
- [ ] Enforce required fields and numerical constraints
- [ ] Align response payloads with the README contract

**Acceptance Criteria**
- [ ] Invalid payloads return HTTP 422 responses
- [ ] DTOs match the documented response structure
- [ ] Enumerations and bounds are explicit and testable

**Dependency Notes**
- Depends on `M2.2`
- Blocks `M7.2`

### Issue M7.2 — Build FastAPI Inference Service & Health Endpoints
**Labels:** `api`, `backend`, `project:feature-track`

**Tasks**
- [ ] Load all serialized artifacts at application startup
- [ ] Implement `POST /api/v1/optimize-price`
- [ ] Implement `GET /health`
- [ ] Add exception handling and runtime failure responses
- [ ] Wire the tariff evaluator into final quote generation

**Acceptance Criteria**
- [ ] `/health` reports readiness and model-load status
- [ ] Valid optimize requests return complete prediction payloads
- [ ] Localhost response time meets the target latency budget under normal load

**Dependency Notes**
- Depends on `M5.1`, `M6.2`, and `M7.1`
- Blocks `M8.2`

---

## Milestone 8: Automated Verification, Latency Profiling & MLOps

**Goal:** Validate mathematical correctness, measure runtime performance, and establish readiness checks for continued development.

**Deliverables:**
- `tests/test_pipeline.py`
- latency/profile report

### Issue M8.1 — Build Unit Test Suite for Parity, Fusion & Tariff Logic
**Labels:** `testing`, `qa`, `project:feature-track`

**Tasks**
- [ ] Test domestic parity invariance `Phi(KE, KE) ~= 1.0`
- [ ] Test export corridor parity `Phi(KE, US) > 1.0`
- [ ] Test hybrid coordinate output shape `(53,)`
- [ ] Test M-Pesa surcharge accuracy and international bypass behavior

**Acceptance Criteria**
- [ ] All targeted mathematical invariants pass under `pytest`
- [ ] Edge cases are covered for domestic, international, and malformed inputs
- [ ] Regression coverage protects core pricing logic from silent drift

**Dependency Notes**
- Depends on `M3.2`, `M4.2`, and `M5.1`

### Issue M8.2 — Profile Inference Latency & Operational Stability
**Labels:** `performance`, `benchmarking`, `project:feature-track`

**Tasks**
- [ ] Benchmark NLP transform latency
- [ ] Benchmark KD-Tree search and IDW latency
- [ ] Measure end-to-end API response time under repeated requests
- [ ] Check for obvious memory growth across long sequential runs

**Acceptance Criteria**
- [ ] Server-side inference remains within the target latency envelope
- [ ] No obvious memory leak appears across 1,000 consecutive requests
- [ ] Performance findings are written down for future optimization work

**Dependency Notes**
- Depends on `M7.2`

### Issue M8.7 — Implement Administrator MLOps Controls and Observability for UC8-UC11
**GitHub issue:** #56
**Labels:** `backend`, `performance`, `testing`, `machine-learning`, `project:feature-track`

**Tasks**
- [ ] Provide an admin-only repository boundary for mentor profiles and historical transactions, with Firestore and in-memory implementations.
- [ ] Expose API, inference, and database latency/error metrics without exposing credentials or sensitive payloads.
- [ ] Provide serialized manual retraining with versioned artifact directories and an atomic active-model manifest.
- [ ] Persist bounded KNN/grid-search overrides for `k_neighbors`, empirical text/metadata weights, IDW epsilon, partition size, and fallback behavior.
- [ ] Map UC8, UC9, UC10, and UC11 to executable modules and endpoints.

**Acceptance Criteria**
- [ ] Missing or invalid administrator credentials are rejected with HTTP 401/403.
- [ ] Firestore is optional at local startup and is initialized only through application-default credentials when explicitly configured.
- [ ] Retraining cannot run concurrently and never publishes a partial active artifact manifest.
- [ ] Invalid tuning bounds return HTTP 422 and valid settings affect model-side runtime coordinates/evaluation.
- [ ] Metrics and health responses contain operational state but no secrets.
- [ ] Unit and API tests cover success, rejection, locking, persistence, and failure paths.

**Dependency Notes**
- Builds on `M4.2`, `M5.1`, `M6.1`, `M7.1`, `M7.2`, and `M8.2`.

---

## Issue Dependency Graph

```text
M1.1 (Macro Extractor) ----.
                            \
                             > M1.3 (Corpus Fusion) --> M6.1 (Train Split) --> M6.2 (Eval & Save)
                            /
M1.2 (Corpus Parser)  -----'

M2.1 (Text Cleaner) ------> M2.2 (TF-IDF & SVD) ---------------------------> M7.1 (DTO Schemas)
                                      |                                         |
                                      |                                         v
                                      '--> M3.2 (Vector Fusion) --> M4.1 --> M4.2 --> M8.1

M3.1 (Meta Scaler) -------> M3.2 -------------------------------------------> M8.1
M5.1 (M-Pesa Tariff) -------------------------------------------------------> M7.2 --> M8.2
M7.2 + M8.2 ---------------------------------------------------------------> M8.7 (UC8-UC11 MLOps controls)
```

---

## GitHub Tracking Notes

Use this document as the source of truth for creating:
- GitHub milestones named `Milestone 1` through `Milestone 8`
- issues titled with `M1.1`, `M1.2`, ... `M8.2`
- labels for functional ownership and workstream filtering
- a planning label named `project:feature-track`

If GitHub Project assignment is enabled, add every issue in this document to the **Price Optimization Model Feature Track** project.

---

## Pivot roadmap: Milestones 9-14

The [canonical blueprint](architecture_blueprint%20%281%29.md) defines the target architecture, migration and ownership decisions; [Blueprint.md](Blueprint.md) records M1-M8. GitHub issues linked below carry the implementation acceptance criteria. Preserve their current open/closed states and milestone assignments; #68 is superseded by #83 and #64 by #70. No pivot task requires tracking local datasets or model binaries.

**Current scope (#91):** Deliver the CS implementation using clearly labeled proxy data. Verified mentor transaction acquisition, empirical OOT accuracy and an `R2 >= 0.75` serving gate are deferred and do not block M10-M14. Continue software correctness, security, inference parity, pricing invariants and CI checks. See [the label provenance audit](Label_Provenance_Audit_91.md); #95 owns artifact compatibility, not score-based promotion.

**Optional #93 research (non-blocking):** [The inference-safe 53D benchmark](M9_93_Inference_Safe_Benchmark.md) evaluates dated job-posting **proxy budgets** using fixed train/validation/test cutoffs, training-only transforms and an untouched final test. Its local reports and research artifacts do not promote a production model, establish mentor-price accuracy or change the deferred #81 gate; #94's supervised estimator comparison remains separate. #67/#70 own any later serving or latency changes.

**Experimental design register (#118, non-blocking):** The [evidence index and assumption register](experiments/README.md) distinguish past proxy measurements from code defaults and untested hypotheses. The [#117 dated SVD dimension study](experiments/117_svd_dimensions.md) is exploratory research on a previously opened job-budget test window, not a production change. Remaining one-variable questions cover country/alpha sensitivity (#119), text normalization and TF-IDF defaults (#120), and peer/IDW settings (#121). None is a prerequisite for M10–M14.

| Sprint | GitHub milestone | Linked delivery issues | Depends on / outcome |
| --- | --- | --- | --- |
| 1 | Milestone 9: Canonical Blueprint & OOT Model Alignment | #66 blueprint; #67 offline/online 53D alignment; #91 provenance audit; #81 empirical OOT (deferred); #92 diagnostics (closed); #93 optional research benchmark; #94 supervised estimator research (deferred); #78 README (closed) | Reuse M1-M8 NLP, parity, KD-Tree, tariff and training foundations; empirical quality gating is not a delivery prerequisite. |
| 2 | Milestone 10: In-Memory Inference, Pricing Corridor & Secure Gateway | #69 Firebase verification; #70 artifact preload/benchmark; #82 corridor; #83 DTO/route migration; #95 artifact/inference parity; #68 (closed/superseded) | Requires canonical contract and compatible model artifacts, **not** a passed empirical R2 gate; retain `POST /api/v1/optimize-price`, legacy compatibility and explicit unready responses. |
| 3 | Milestone 11: Firestore Persistence & Asynchronous Pricing Audit | #71 root listings; #72 audit; #73 tariff correction; #84 mentor hydration; #113 named database selection | Requires verified UID and listing identity; reuse repository, observability and tariff modules. |
| 4 | Milestone 12: Native Android Shell & Firebase Authentication | #74 Compose app; #75 sign-in/token handling; #140 design system/accessibility | Client uses protected pricing gateway; no backend admin credentials on device. |
| 5 | Milestone 13: Mobile Integration & Backend Deployment | #76 Retrofit integration; #77 Docker/CI (closed); #141 Android CI pipeline; #142 results dashboard UX | Integrate with the canonical DTO and deploy a complete artifact set outside Git. |
| 6 | Milestone 14: Mobile Usability & End-to-End Validation | #85 protected demo; #86 3G RTT; #87 SUS | Validate authenticated system; the demo does not replace Android or bypass auth. |
| 7 | Milestone 15: System Documentation, AI/ML Implementation & Empirical Evaluation | #147 System Implementation & Environment; #148 AI/ML Data & Model Implementation; #149 Testing & Baseline Evaluation; #150 Results Presentation & Error Analysis; #151 Discussion, Risks & Limitations | Formalize production-grade engineering documentation, empirical evaluation baselines, error analysis, and environment reproducibility. |
| 8 | Milestone 16: Advanced Algorithmic Optimization, Vector Search Scaling & Continuous MLOps | M16.1 Ensemble Benchmarks; M16.2 Systematic KNN Tuning; M16.3 Distance Weighting Kernels; M16.4 SVD vs Transformers; M16.5 Cold-Start Fallbacks; M16.6 Vector Search Scaling; M16.7 Automated Retraining & Drift | Operationalize supervisor guidance: benchmark tree ensembles/linear models against KNN, optimize distance metrics and IDW kernels, benchmark MiniLM sentence embeddings against SVD, architect multi-tier cold-start fallbacks, evaluate FAISS CPU vector scaling, and design Firestore drift-driven retraining. |

**Android implementation guide (#74, #140-#142):** The `app/` Gradle module scaffolded under this
roadmap follows `docs/Architecture/Android_App_Guide.md`, which maps every Android source file back
to an issue and to the class/composable names in `docs/Architecture/Class/mobile class diagram.svg`.
It ships with `FakePricingRepository` as the default (`BuildConfig.USE_LIVE_BACKEND = false`) so the
Idle/Loading/Success/Error flow and results dashboard are demoable before #75 (auth) and #76 (live
networking) land; flipping that flag is explicitly scoped to #76, not this scaffold.

**M11.3 tariff reconciliation (#73):** The Safaricom Consumer Tariffs & Limits page last updated August 4, 2026 contains **15** transfer-to-M-PESA-user bands (1–250,000 KES), replacing the blueprint's superseded 12-band proposal. The versioned P2P CSV is the only schedule wired to quotes; the separate catalog of other-network, withdrawal, Pochi, Buy Goods and till tariffs is reference data, not an API feature. Any new payment rail, such as a bank Visa commission, needs a scoped follow-up issue and a source/contract review before implementation.

Existing `industry_partition` training labels map to target `industry`/Firestore `industry_id`; existing numeric rates are KES/hour. The optional `costOfLivingIndex` must not be silently mapped to `market_saturation_score`. `mentorId` is authorized against the verified Firebase UID, not presumed equivalent. #67, #69, #71, #83 and #84 own these translations; see the canonical blueprint's migration table for details.

**M10.5 implementation (#83):** `src/api_contracts.py` provides separate canonical camelCase DTOs alongside the deprecated legacy snake_case DTOs. Both use the existing versioned route with matching response shapes and a `Deprecation` header for successful legacy requests. Canonical competitiveness maps to the fitted saturation feature; optional mentor CoL overrides only bilateral parity. Existing proxy artifacts do not contain listing IDs, so their canonical comparables remain empty rather than fabricated; confidence remains explicitly uncalibrated. #71 enables verified root listing provenance in new exports; #84 owns authorized text hydration.


---

## Milestone 15: System Documentation, AI/ML Implementation & Empirical Evaluation

**Goal:** Establish end-to-end, publication-grade system documentation covering the implementation environment, AI/ML lifecycle architecture, baseline evaluations, subgroup error analysis, and production reproducibility constraints.

**Deliverables:**
- docs/M15_System_Documentation.md
- Baseline benchmarking and comparative evaluation tables
- Subgroup and class-wise regression metric reports
- Residual and consequential error analyses (over/under-pricing dynamics)
- Environment and container reproducibility specifications

---

### Issue M15.1 — System Implementation & Environment Specification
**Labels:** documentation, ackend, devops, project:feature-track

**Scope & Sub-Issues:**
- **M15.1.1 — Implementation Environment:** Document the separation between development (local workstation, Windows 11, PyCharm, Android Studio, virtual envs, offline stubs), test (pytest, Gradle testDebugUnitTest, GitHub Actions Ubuntu runners), and staging/private deployment environments. Explicitly confirm no public deployment exists.
- **M15.1.2 — Hardware and Deployment Environment:** Detail the exact host specifications (AMD64 12 logical cores, single-thread BLAS/OMP/MKL bindings), CI runners (2-core Ubuntu VMs), and client targets (Android minSdk 26, targetSdk 34).
- **M15.1.3 — Software, Services, and Configuration:** Specify runtime dependencies (Python 3.11/3.13, Gradle 8.9, JDK 17, FastAPI, Uvicorn, NLTK corpuses) and external cloud services (Firebase Authentication token verification, Cloud Firestore named database priceoptimizationmodel).
- **M15.1.4 — Deployment and Reproducibility:** Document containerization via Dockerfile (python:3.11-slim), non-root pricing user execution, read-only external mounts (/opt/pricing/artifacts, /opt/pricing/tariff.csv), and independent SHA-256 manifest pinning (PRICING_ARTIFACT_MANIFEST_SHA256).

**Tasks:**
- [ ] Define environment isolation boundaries between local dev, automated CI, and containerized staging
- [ ] Document tested hardware configurations and resource bounds (1 CPU thread lock, < 1MB allocation growth)
- [ ] List required external cloud services, credentials provisioning (ADC), and fail-closed configurations
- [ ] Provide step-by-step container build and run commands with read-only volume mounts and SHA-256 validation

**Acceptance Criteria:**
- [ ] Explicitly discloses that no public access deployment exists (local prototype / private deployment only)
- [ ] Minimum hardware and software configurations are justified against real benchmark data
- [ ] Zero secret leakage: all credential and manifest configurations use external environment variables

---

### Issue M15.2 — Data and Model Implementation for AI/ML Projects
**Labels:** documentation, machine-learning, data-engineering, project:feature-track

**Scope & Sub-Issues:**
- **M15.2.1 — Dataset Provenance & Sourcing:** Document the lineage of raw data sources (World Bank WDI PPP factors, cost-of-living indices, Kaggle/Upwork freelance job corpuses) and explicitly document their exploratory proxy status (not verified mentor earnings).
- **M15.2.2 — Data Preparation & Harmonization:** Document text cleaning (WordNet lemmatization, stopword filtering), currency normalization to KES, target filtering (500–35,000 KES/hr), and train-only saturation/density computation to prevent data leakage.
- **M15.2.3 — Experiment Design & Hypothesis Tracking:** Formalize the experimental design registry (docs/experiments/), tracking one-variable ablations, parameter grids (SVD dimensions 25–100, TF-IDF n-grams, KNN k in {1, 3, 5}), and rejection criteria.
- **M15.2.4 — Model Training & Coordinate Fusion:** Detail the training pipeline orchestration (orchestrate_training), log1p target transformation (	ransform_target_log1p), continuous metadata normalization (StandardScaler), and 53D coordinate fusion (50D SVD text + 3D metadata).
- **M15.2.5 — Model Packaging & Manifest Integrity:** Document joblib artifact serialization, rtifact_manifest.json generation with cryptographic SHA-256 hashes, and explicit tagging of exploratory_not_empirically_approved.
- **M15.2.6 — Inference Engine & Operational Monitoring:** Detail lifespan preloading, IDW spatial regression querying (DomainPartitionedKDTreeIndexer), fallback partition routing, health endpoints (/health, /ready), and asynchronous pricing audit logging.

**Tasks:**
- [ ] Document dataset origins, licensing, and proxy limitations in data governance records
- [ ] Trace data transformation steps from raw text and currencies to harmonized Parquet format
- [ ] Record one-variable ablation parameters and evaluation metrics in experiment logs
- [ ] Document coordinate fusion math, SVD dimensionality reduction, and KD-Tree partitioning
- [ ] Document artifact manifest schema, cryptographic verification, and tamper detection
- [ ] Detail inference execution path, IDW distance weighting, and M-Pesa tariff fee evaluation

**Acceptance Criteria:**
- [ ] Ingestion and preprocessing pipelines prove zero data leakage between train and holdout splits
- [ ] Artifact manifests record dataset and file SHA-256 digests and explicit exploratory status
- [ ] Inference runtime verifies manifests before deserialization and fails closed on hash mismatches

---

### Issue M15.3 — Testing and Baseline Evaluation Framework
**Labels:** documentation, 	esting, evaluation, qa, project:feature-track

**Scope & Sub-Issues:**
- **M15.3.1 — Meaningful Baseline Comparison:** Benchmark the 53D KD-Tree IDW model against standard reference baselines: industry median dummy estimator, partition mean rate, unweighted KNN regression, and linear regression.
- **M15.3.2 — Task-Appropriate Metrics & Subgroup/Partition Results:** Evaluate models using RMSE, MAE, Median Absolute Error (MedAE), SMAPE (%), and R^2, segmented by industry partitions (data_ai, web_backend, design_creative, mobile).
- **M15.3.3 — Error & Residual Analysis:** Document error distribution curves, identify heteroscedasticity, and analyze consequential errors (under-pricing risking mentor margin erosion vs over-pricing causing client drop-off).
- **M15.3.4 — Variation Across Runs, Seeds, and Folds:** Quantify model stability across repeated runs with varying random seeds (e.g., 42, 123, 999) and stratified cross-validation folds.
- **M15.3.5 — Final Held-Out Test Performance & OOT Gating:** Evaluate models on held-out test splits, contrasting random stratified holdouts with chronological Out-of-Time (OOT) holdout windows, and document programmatic enforcement of the R^2 >= 0.75 quality gate.

**Tasks:**
- [ ] Implement and evaluate baseline estimators against the primary KD-Tree IDW pipeline
- [ ] Compute comprehensive metric summaries (RMSE, MAE, MedAE, SMAPE, R^2) overall and per industry partition
- [ ] Conduct residual analysis and classify asymmetric pricing error risks
- [ ] Run multi-seed stability benchmarks to document metric variance across runs
- [ ] Document holdout performance on untouched test splits and chronological OOT evaluation results

**Acceptance Criteria:**
- [ ] All reported evaluation metrics derive from verified test pipeline runs
- [ ] Baseline comparisons demonstrate statistically significant predictive improvement over naive baselines
- [ ] Asymmetric error risks (under-pricing vs over-pricing) are explicitly analyzed from an economic perspective

---

### Issue M15.4 — Results Presentation and Interpretation
**Labels:** documentation, evaluation, enchmarking, project:feature-track

**Scope & Sub-Issues:**
- **M15.4.1 — Results Presentation & Visualizations:** Generate and document structured comparative tables, hyperparameter trend plots, target transformation comparisons (raw vs log1p), and residual histograms.
- **M15.4.2 — Feature Attribution & Coordinate Fusion Interpretation:** Analyze how semantic SVD components and continuous metadata dimensions (bilateral arbitrage, saturation, density) contribute to spatial distance and final pricing.
- **M15.4.3 — Latency vs Accuracy Trade-off Analysis:** Document the trade-offs between model complexity (e.g. SVD component size, KD-Tree leaf size, neighbor count k) and runtime inference latency (P50/P95/P99).

**Tasks:**
- [ ] Compile tabular summaries of hyperparameter tuning and ablation results
- [ ] Document visual artifacts illustrating model error distributions and variable effects
- [ ] Analyze feature vector interactions between text semantics and macroeconomic parity factors
- [ ] Correlate accuracy improvements against operational latency benchmarks

**Acceptance Criteria:**
- [ ] Visual charts and tables present clear, reproducible metrics with units (KES/hr, ms)
- [ ] Coordinate fusion mechanics are mathematically interpreted and validated against test cases
- [ ] Latency profiling verifies adherence to the P95 < 250 ms operational threshold

---

### Issue M15.5 — Evaluation Results, Discussion, and Limitations
**Labels:** documentation, qa, project:feature-track

**Scope & Sub-Issues:**
- **M15.5.1 — Comprehensive Discussion of Findings:** Synthesize findings regarding spatial peer matching, IDW weighting stability, and price corridor boundaries across domestic and cross-border scenarios.
- **M15.5.2 — Technical & Data Limitations:** Detail explicit technical limitations: use of proxy job postings instead of real mentor receipts, uncalibrated confidence intervals, cold-start sparsity in low-volume industries, and lack of real-time market feedback.
- **M15.5.3 — Economic, Ethical, and Regulatory Risk Assessment:** Assess systemic risks including currency exchange fluctuations, Safaricom M-Pesa tariff updates, fee absorption edge cases, and ethical safeguards against discriminatory or predatory pricing.

**Tasks:**
- [ ] Formulate a detailed engineering discussion of model strengths and failure modes
- [ ] Document all data provenance disclaimers and proxy caveats
- [ ] Conduct a risk assessment covering financial margin protection, regulatory compliance, and economic shocks

**Acceptance Criteria:**
- [ ] Explicitly separates verified engineering findings from proxy data assumptions
- [ ] Documents clear recommendations and migration criteria for future live mentor transaction data
- [ ] Outlines operational recovery protocols for tariff schedule and macroeconomic factor changes


---

## Milestone 16: Advanced Algorithmic Optimization, Vector Search Scaling & Continuous MLOps

**Goal:** Execute systematic research and engineering extensions addressing supervisory recommendations: quantify predictive accuracy vs. peer interpretability trade-offs across tree ensembles (XGBoost, Random Forest) and regularized linear models (Ridge); tune KNN hyperparameters and alternative distance metrics (Cosine, Manhattan) dynamically; optimize distance weighting decay kernels (Gaussian RBF, Exponential, Power IDW); benchmark the TF-IDF + Truncated SVD pipeline against pre-trained dense sentence transformers (`all-MiniLM-L6-v2`); architect multi-tier cold-start fallbacks for sparse partitions and niche skill stacks; evaluate Approximate Nearest Neighbor (ANN) vector search scalability (FAISS CPU, Annoy); and design an automated, drift-aware continuous retraining workflow leveraging Firestore transaction logs.

**Deliverables:**
- `reports/experiments/m16_ensemble_benchmarks.md`: Empirical evaluation of Ridge, Random Forest, and XGBoost vs. KD-Tree IDW, featuring accuracy-vs-interpretability frontier analysis.
- `reports/experiments/m16_knn_idw_tuning.md`: Multi-metric grid search sweep across $k \in [1, 50]$, distance metrics ($L_1$, $L_2$, Cosine), and weighting kernels (Power IDW, Exponential, Gaussian RBF).
- `reports/experiments/m16_svd_vs_transformers.md`: Latent SVD vs. `all-MiniLM-L6-v2` benchmark covering retrieval precision, regression accuracy, memory footprint, and single-thread CPU P95 inference latency.
- `src/spatial_engine.py` (Extended): Multi-tier cold-start fallback cascade (Partition -> Taxonomy -> Global Semantic -> Macro Prior) and configurable distance metric / weighting kernel adapter.
- `src/ann_indexer.py` & `reports/m16_vector_search_scaling.md`: Scalability analysis and FAISS CPU / Annoy ANN indexing prototype for $10^4$ to $10^6$ listings.
- `src/drift_monitor.py` & `docs/M16_Continuous_Retraining_Workflow.md`: Statistical drift detector (PSI, Wasserstein, Kolmogorov-Smirnov) and automated retraining runbook consuming Firestore `/historical_transactions`.

---

### Issue M16.1 — Benchmark Against Ensemble & Linear Models (XGBoost, Random Forest, Ridge)
**Labels:** `machine-learning`, `benchmarking`, `algorithms`, `interpretability`, `project:feature-track`

**Goal:** Compare the production KNN regression engine against gradient boosted trees (XGBoost), tree ensembles (Random Forest), and regularized linear models (Ridge Regression) on identical 53-dimensional coordinates to rigorously quantify the trade-off between predictive accuracy and model interpretability.

**Scope & Sub-Issues:**
- **M16.1.1 — Standardized Baseline Harness:** Build a reproducible benchmarking harness training Ridge Regression (L2 penalty), Random Forest Regressor, and XGBoost Regressor on the exact 53-D fused feature matrices ($50\text{D SVD} + 3\text{D continuous metadata}$) and target rates ($\text{raw}$ and $\log(1 + y)$) used by the primary spatial engine.
- **M16.1.2 — Empirical Metric Evaluation:** Evaluate models on the frozen chronological Out-of-Time (OOT) holdout split, measuring RMSE, MAE, Median Absolute Error (MedAE), sMAPE (%), and $R^2$ across the overall test cohort and per industry partition (`data_ai`, `web_backend`, `design_creative`, `mobile`).
- **M16.1.3 — Accuracy vs. Interpretability Trade-Off:** Quantify the predictive improvement (or gap) of tree ensembles over KNN. Formally contrast global/local feature attributions (Tree SHAP values, Ridge standardized coefficients) against KNN's explicit peer-based instance explanations (`comparables` payload with peer rates, similarities, and distance metrics).
- **M16.1.4 — Inference Latency & Resource Footprint:** Benchmark single-threaded CPU inference latency (P50, P95, P99) and resident memory footprint under deployment constraints (`OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`) to determine production serving feasibility.

**Tasks:**
- [ ] Implement training and evaluation harness in `src/ensemble_benchmark.py`
- [ ] Execute hyperparameter search for Ridge (`alpha`), Random Forest (`n_estimators`, `max_depth`, `min_samples_leaf`), and XGBoost (`n_estimators`, `learning_rate`, `max_depth`, `subsample`)
- [ ] Compute comparative regression metrics on frozen chronological validation and test splits
- [ ] Compute per-partition breakdowns and residual heteroscedasticity diagnostics
- [ ] Compute Tree SHAP feature importances and compare against top-$k$ nearest peer contributions
- [ ] Profile single-thread P50/P95 inference latencies and serialized artifact disk sizes
- [ ] Publish findings in `reports/experiments/m16_ensemble_benchmarks.md`

**Acceptance Criteria:**
- [ ] All models evaluate on identical train, validation, and test splits with zero data leakage
- [ ] Metric report includes RMSE, MAE, MedAE, sMAPE, $R^2$, P95 latency (ms), and model size (MB)
- [ ] Clear quantitative documentation of whether accuracy gains from tree ensembles justify sacrificing direct comparable peer explainability
- [ ] Reproducible under fixed random seeds (`42`, `123`, `999`) with deterministic environment variables

**Dependency Notes:**
- Extends `M6.2`, `M9.3`, and `M15.3`.

---

### Issue M16.2 — Systematic KNN Hyperparameter Tuning & Distance Metric Evaluation
**Labels:** `machine-learning`, `hyperparameter-tuning`, `spatial-indexing`, `algorithms`, `project:feature-track`

**Goal:** Conduct an exhaustive, systematic hyperparameter grid search across neighbor count $k$ and alternative distance metrics (Cosine, Manhattan) against standard Euclidean distance to identify optimal spatial peer retrieval configurations.

**Scope & Sub-Issues:**
- **M16.2.1 — Dynamic k Range Sweep:** Sweep $k \in \{1, 3, 5, 7, 10, 15, 20, 25, 30, 50\}$ dynamically across industry partitions, evaluating predictive accuracy and sensitivity to local label noise.
- **M16.2.2 — Alternative Distance Metrics:** Formulate and evaluate alternative metric geometries in 53D space:
  - *Euclidean ($L_2$ norm)*: Default baseline measuring geometric distance.
  - *Manhattan ($L_1$ norm)*: Mitigates distance concentration effects and outlier feature pulling in high dimensions.
  - *Cosine Distance*: Evaluates angular similarity of semantic vectors, isolating directional orientation from magnitude.
- **M16.2.3 — Peer Stability & Corridor Sensitivity:** Measure retrieved peer set stability (Jaccard similarity and rank correlation against the baseline $k=5$ Euclidean configuration) and analyze impact on negotiation corridor bounds ($[\text{minQuotedRate}, \text{maxQuotedRate}]$).
- **M16.2.4 — Query Latency Profiling:** Profile KD-Tree / BallTree retrieval latency across each metric and neighbor count under single-threaded CPU constraints to safeguard the P95 $< 250\text{ ms}$ gateway envelope.

**Tasks:**
- [ ] Parameterize distance metric selection in `spatial_engine.py` (supporting Euclidean, Manhattan, and Cosine via BallTree or pre-normalized embeddings)
- [ ] Execute automated cross-validation grid search over $k \in [1, 50]$ and distance metrics
- [ ] Measure validation and OOT test metrics (MAE, RMSE, $R^2$, sMAPE) for all candidates
- [ ] Compute peer-match Jaccard similarity and base-quote shift relative to the production $k=5$ Euclidean baseline
- [ ] Measure query latency distributions (P50, P95, P99)
- [ ] Document optimal configurations and parameter sensitivities in `reports/experiments/m16_knn_idw_tuning.md`

**Acceptance Criteria:**
- [ ] Grid search explores all specified $k$ values and distance metrics across all industry partitions
- [ ] Identifies whether Manhattan or Cosine distance mitigates high-dimensional concentration in 53D space
- [ ] Validates that candidate configurations preserve the P95 $< 250\text{ ms}$ response budget
- [ ] Backward compatibility verified: candidate configurations preserve canonical DTO contracts

**Dependency Notes:**
- Extends `M4.1`, `M4.2`, `M6.4`, and `assumptions.md`.

---

### Issue M16.3 — Optimize Distance Weighting Kernels (Gaussian RBF, Exponential & IDW Variants)
**Labels:** `machine-learning`, `spatial-indexing`, `algorithms`, `evaluation`, `project:feature-track`

**Goal:** Formulate, test, and benchmark alternative peer distance weighting decay functions (Gaussian RBF, Exponential, and Power-p IDW) alongside quadratic penalization to refine how peer proximity governs pricing quotes and corridor widths.

**Scope & Sub-Issues:**
- **M16.3.1 — Weighting Kernel Formulations:** Implement and evaluate candidate distance weighting decay functions:
  - *Linear IDW*: $w_i = \frac{1}{d_i + \epsilon}$ ($p=1$)
  - *Quadratic IDW (Baseline)*: $w_i = \frac{1}{d_i^2 + \epsilon}$ ($p=2$)
  - *Cubic / Higher-Power IDW*: $w_i = \frac{1}{d_i^p + \epsilon}$ ($p \in \{3, 4\}$)
  - *Exponential Decay*: $w_i = \exp(-\gamma \cdot d_i)$
  - *Gaussian Radial Basis Function (RBF)*: $w_i = \exp\left(-\frac{d_i^2}{2\sigma^2}\right)$, with adaptive bandwidth $\sigma = \text{median}(d_1, \dots, d_k)$ or fixed scale.
- **M16.3.2 — Density-Dependent Weight Dynamics:** Analyze weight distribution entropy across dense partitions (`design_creative`, `web_backend`) versus sparse partitions (`product_management`, `devops_cloud`) to prevent single-neighbor dominance.
- **M16.3.3 — Negotiation Corridor Impact:** Evaluate the effect of kernel choice on weighted peer standard deviation ($\sigma_{\text{peer}}$), determining whether exponential or Gaussian decay provides more realistic and robust negotiation intervals.

**Tasks:**
- [ ] Implement modular weighting kernel functions in `src/spatial_engine.py`
- [ ] Evaluate regression metrics (MAE, RMSE, $R^2$) and prediction bias across all kernel variants on validation data
- [ ] Test numerical stability under edge conditions ($d_i \to 0$ exact matches, $d_i \gg 1$ distant outliers)
- [ ] Analyze corridor width stability ($\text{maxQuotedRate} - \text{minQuotedRate}$) across candidate kernels
- [ ] Document kernel comparison results in `reports/experiments/m16_knn_idw_tuning.md`

**Acceptance Criteria:**
- [ ] Mathematical definitions and parameter bounds ($\epsilon, \gamma, \sigma, p$) clearly documented
- [ ] Zero division-by-zero or numerical underflow/overflow errors across extreme distance inputs
- [ ] Quantifies trade-offs between localized sensitivity (quadratic/cubic) and peer smoothing (linear/Gaussian)
- [ ] Preserves fee-free negotiation corridor invariants and non-negative output guarantees

**Dependency Notes:**
- Builds on `M4.2`, `M8.2`, and `M16.2`.

---

### Issue M16.4 — Semantic NLP Pipeline Comparison: TF-IDF + SVD vs Pre-Trained Sentence Transformers
**Labels:** `nlp`, `deep-learning`, `benchmarking`, `performance`, `project:feature-track`

**Goal:** Benchmark the production TF-IDF + Truncated SVD pipeline against pre-trained sentence transformer embeddings (`sentence-transformers/all-MiniLM-L6-v2`) to empirically evaluate semantic retrieval quality against low-latency inference constraints.

**Scope & Sub-Issues:**
- **M16.4.1 — Transformer Embedding Pipeline:** Build an experimental feature extraction pipeline embedding raw mentor and job descriptions using `all-MiniLM-L6-v2` (384-dimensional dense vectors) via PyTorch / ONNX CPU runtime.
- **M16.4.2 — Semantic Retrieval Quality:** Benchmark qualitative and semantic peer retrieval: measure semantic cosine alignment between query texts and retrieved peer listings, evaluating polysemy handling and domain terminology overlap.
- **M16.4.3 — Downstream Rate Regression Accuracy:** Evaluate downstream pricing performance (MAE, RMSE, $R^2$) using: (a) raw 384D transformer embeddings + 3D metadata, (b) PCA/SVD-reduced 50D transformer embeddings + 3D metadata, and (c) production 50D TF-IDF + SVD + 3D metadata.
- **M16.4.4 — Latency, Memory & Hardware Profiling:** Profile CPU transformation latency (P50/P95/P99), cold-start initialization time, memory peak (`tracemalloc` and process RSS), and artifact disk footprint on standard deployment hardware (AMD64 and ARM64 single-thread).

**Tasks:**
- [ ] Implement transformer feature extractor in `src/transformer_benchmark.py`
- [ ] Extract 384D embeddings across the harmonized marketplace corpus
- [ ] Train domain-partitioned spatial indexes on transformer-fused coordinates
- [ ] Evaluate holdout regression metrics on identical validation and OOT test windows
- [ ] Profile memory usage and inference latency per document on single-threaded CPU
- [ ] Document latency vs. semantic accuracy trade-offs in `reports/experiments/m16_svd_vs_transformers.md`

**Acceptance Criteria:**
- [ ] Rigorous empirical comparison between TF-IDF + SVD (50D) and `all-MiniLM-L6-v2` (384D / reduced 50D)
- [ ] Hardware and memory profiling executed under single-thread CPU bindings (`OPENBLAS_NUM_THREADS=1`)
- [ ] Provides documented justification: whether SVD remains the justified choice for low-latency edge/container serving, or defines the exact OOT accuracy gain provided by transformers
- [ ] Confirms artifact sizes, dependencies, and ONNX runtime viability for future migration

**Dependency Notes:**
- Extends `M2.2`, `M6.6`, `assumptions.md`, and `117_svd_dimensions.md`.

---

### Issue M16.5 — Algorithmic "Cold-Start" Fallback Architecture for Sparse Partitions & Niche Skills
**Labels:** `architecture`, `spatial-indexing`, `backend`, `robustness`, `project:feature-track`

**Goal:** Architect and implement a robust multi-tier cold-start fallback cascade that guarantees reliable rate recommendations and transparent uncertainty signaling when a mentor or specialized skill stack has fewer than $k$ historical listings in its partition.

**Scope & Sub-Issues:**
- **M16.5.1 — Multi-Tier Algorithmic Fallback Cascade:**
  - *Tier 1 (Partition Match)*: Primary domain KD-Tree query when $N_{\text{partition}} \ge \max(k, \text{min\_size})$.
  - *Tier 2 (Taxonomy Hierarchy Rollup)*: Query nearest parent or sibling domain in a structured industry taxonomy tree (e.g., `mobile_flutter` -> `mobile` -> `general_tech`).
  - *Tier 3 (Global Semantic Nearest-Neighbor Retrieval)*: Query a unified global KD-Tree across all listings using the 50D text representation, penalizing cross-industry distance with an explicit domain divergence weight $\lambda_{\text{industry}}$.
  - *Tier 4 (Macroeconomic Empirical Prior)*: When total nearest peers $< k$ globally, compute a Bayesian prior rate from mentor country macroeconomic baseline ($PPP \times \text{baseline}$), with widened uncertainty corridor and zero listing comparables.
- **M16.5.2 — Transparent Contract Diagnostics:** Extend API response metadata to explicitly disclose fallback execution (`fallbackTier: "exact" | "taxonomy" | "global_semantic" | "macro_prior"`, `coldStart: true`, `confidenceScore: 0.0`).
- **M16.5.3 — Dynamic Corridor Adjustment:** Dynamically expand the negotiation corridor width ($\sigma_{\text{peer}}$) when fallback tiers are activated, reflecting elevated epistemic uncertainty.

**Tasks:**
- [ ] Construct hierarchical industry taxonomy mapping in `config/industry_taxonomy.json`
- [ ] Implement global unified spatial index and domain divergence penalty in `src/spatial_engine.py`
- [ ] Implement macroeconomic prior fallback for total cold-start scenarios
- [ ] Update Pydantic DTOs and API contracts with fallback diagnostics
- [ ] Write comprehensive unit and integration tests covering all 4 fallback tiers

**Acceptance Criteria:**
- [ ] System never crashes or returns unhandled exceptions when querying partitions with $0 \le N < k$ listings
- [ ] Fallback tiers execute deterministically in strict priority order (Tier 1 -> Tier 2 -> Tier 3 -> Tier 4)
- [ ] Fallback status is transparently surfaced in API responses without breaking backward compatibility
- [ ] Corridor bounds dynamically widen under cold-start conditions to signal uncertainty

**Dependency Notes:**
- Builds on `M4.1`, `M4.2`, `M7.1`, and `M10.5`.

---

### Issue M16.6 — Vector Search Scalability Planning & Approximate Nearest Neighbor (ANN) Indexing
**Labels:** `performance`, `spatial-indexing`, `scalability`, `architecture`, `project:feature-track`

**Goal:** Evaluate Approximate Nearest Neighbor (ANN) vector search libraries (FAISS on CPU and Annoy) to establish an architectural scaling blueprint when historical transaction volume exceeds the computational capacity of exact KD-Trees.

**Scope & Sub-Issues:**
- **M16.6.1 — ANN Architecture Selection & Prototyping:**
  - Evaluate **FAISS (Facebook AI Similarity Search)** on CPU: Test `IndexFlatL2` (exact baseline), `IndexIVFFlat` (inverted file clusters), and `IndexHNSWFlat` (hierarchical navigable small world graphs).
  - Evaluate **Annoy (Spotify)**: Test multi-tree random projection indexing with memory-mapped (`mmap`) cross-process sharing.
- **M16.6.2 — Scalability & Recall Benchmarking:** Simulate corpus growth across orders of magnitude: $N \in \{10^4, 5 \times 10^4, 10^5, 5 \times 10^5, 10^6\}$ synthetic 53D vectors. Benchmark:
  - Index build time and memory usage during construction
  - Index file size on disk and memory-mapped RAM footprint
  - Query latency (P50, P95, P99) under single-thread CPU execution (`OMP_NUM_THREADS=1`)
  - Recall@k accuracy relative to exact KD-Tree ground truth ($k=5$)
- **M16.6.3 — Production Migration Thresholds:** Establish quantitative thresholds (e.g. $N > 50,000$ or P95 search latency $> 15\text{ ms}$) that trigger automated migration from KD-Tree to FAISS CPU indexing.

**Tasks:**
- [ ] Implement standalone benchmarking harness `src/ann_benchmark.py` supporting KD-Tree, FAISS CPU, and Annoy
- [ ] Generate synthetic 53D vectors scaled from $10^4$ to $10^6$ entries
- [ ] Measure Recall@k, index size, build time, and query latencies
- [ ] Document threading constraints (`OMP_NUM_THREADS=1`) for Docker container deployment
- [ ] Publish architectural scalability blueprint in `reports/m16_vector_search_scaling.md`

**Acceptance Criteria:**
- [ ] Benchmark evaluates KD-Tree vs FAISS CPU vs Annoy across $N=10^4$ to $10^6$ vectors
- [ ] Recall@5 remains $\ge 98\%$ for chosen ANN configurations
- [ ] Query latency P95 remains $< 5\text{ ms}$ at $N=1,000,000$ vectors on single-thread CPU
- [ ] Concrete migration criteria, dependency specifications, and container integration plans defined

**Dependency Notes:**
- Extends `M4.1`, `M8.2`, and `M15.1`.

---

### Issue M16.7 — Continuous Retraining Pipeline, Market Drift Monitoring & Economic Adaptation
**Labels:** `mlops`, `data-engineering`, `observability`, `automation`, `project:feature-track`

**Goal:** Design an automated, scheduled retraining workflow leveraging verified Firestore transactions (`historical_transactions`) to continuously detect concept/covariate drift, adapt to macroeconomic inflation, and execute zero-downtime atomic model updates.

**Scope & Sub-Issues:**
- **M16.7.1 — Firestore Data Ingestion & Windowing:**
  - Query `/historical_transactions` filtering for verified, paid transaction records within sliding time windows (e.g., 90-day active window + historical reference).
  - Harmonize transaction amounts against prevailing macroeconomic lookup tables (`PA.NUS.PPP`, cost-of-living indices).
- **M16.7.2 — Statistical Drift Detection Engine:**
  - *Covariate Shift ($P(X)$)*: Monitor text embedding distributions and continuous metadata using Population Stability Index (PSI) and Wasserstein Distance.
  - *Concept Drift ($P(Y|X)$)*: Monitor residual distributions and pricing target changes using the Kolmogorov-Smirnov (KS) two-sample test and tracking rolling mean rate drift.
- **M16.7.3 — Automated Retraining Cadence & Triggering:**
  - Define scheduled cadence (e.g., monthly cron schedule via Cloud Scheduler / GitHub Actions workflow).
  - Define automated event-driven triggers: trigger automated retraining when PSI $> 0.25$ or KS test $p$-value $< 0.01$ indicates significant market divergence.
- **M16.7.4 — Shadow Evaluation & Zero-Downtime Atomic Promotion:**
  - Execute training in an isolated staging environment producing candidate artifacts.
  - Evaluate candidate against latest out-of-time (OOT) transaction holdout window; enforce quality and regression guardrails.
  - Compute cryptographic SHA-256 digest of `artifact_manifest.json`.
  - Atomically promote new artifact set by updating the active manifest reference in runtime configuration without API downtime.

**Tasks:**
- [ ] Implement drift monitoring module `src/drift_monitor.py` calculating PSI, Wasserstein distance, and KS statistics
- [ ] Implement transaction ingestion extractor querying Firestore `historical_transactions`
- [ ] Define automated retraining orchestration workflow (`.github/workflows/scheduled_retrain.yml` specification)
- [ ] Implement shadow validation gate comparing candidate vs active model on recent transactions
- [ ] Document atomic promotion protocol and rollback procedures in `docs/M16_Continuous_Retraining_Workflow.md`

**Acceptance Criteria:**
- [ ] Drift detection algorithms (PSI, KS test) mathematically specified with explicit warning/alert thresholds
- [ ] Retraining pipeline operates end-to-end from Firestore query to evaluated artifact candidate
- [ ] Zero-downtime atomic promotion protocol guarantees fail-closed rollback if manifest verification fails
- [ ] Complete operational runbook documented covering monitoring alerts, manual overrides, and audit trails

**Dependency Notes:**
- Builds on `M8.7`, `M11.2`, `M15.1`, and `M15.2`.
