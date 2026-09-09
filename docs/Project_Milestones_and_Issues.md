# Project Milestones & Engineering Issue Breakdown

This document is the execution roadmap for the **Price Optimization Model Feature Track**. It converts the current design assets in `README.md`, `Docs/Blueprint.md`, and `Docs/Architecture/` into milestone-based implementation work ready for GitHub tracking.

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
```

---

## GitHub Tracking Notes

Use this document as the source of truth for creating:
- GitHub milestones named `Milestone 1` through `Milestone 8`
- issues titled with `M1.1`, `M1.2`, ... `M8.2`
- labels for functional ownership and workstream filtering
- a planning label named `project:feature-track`

If GitHub Project assignment is enabled, add every issue in this document to the **Price Optimization Model Feature Track** project.

