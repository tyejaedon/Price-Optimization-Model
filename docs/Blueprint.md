# Price Optimization Model Blueprint

## Purpose

This blueprint translates the project vision, README, and architecture diagrams into an executable engineering plan for the **Price Optimization Model Feature Track**.

The system is intended to recommend fair, market-aware consulting rates for technical mentors and freelancers by combining:

- semantic analysis of profile and skill text,
- macroeconomic purchasing-power adjustments,
- nearest-neighbor peer pricing retrieval, and
- localized M-Pesa fee protection for Kenyan engagements.

---

## Product Objective

Build a pricing recommendation platform that can:

1. ingest multi-source freelance and macroeconomic datasets,
2. transform free-form profile text into dense machine-learning features,
3. estimate a base rate from similar peer records,
4. adjust rate recommendations for cross-border parity, and
5. return a production-ready quote through a FastAPI inference service.

---

## Architecture Inputs Considered

The following design artifacts inform implementation sequencing and issue design:

| Artifact | Planning Use |
| --- | --- |
| `README.md` | Product story, pipeline explanation, API contract, and repository overview |
| `Docs/Architecture/System Arch/` | Defines the 4-tier system boundary: client, API, ML core, and persistence |
| `Docs/Architecture/ML Pipeline/` | Defines the sequential analytical flow from ingestion to pricing output |
| `Docs/Architecture/Class/` | Suggests major implementation modules and service boundaries |
| `Docs/Architecture/ERD/` | Informs persistence entities and auditability requirements |
| `Docs/Architecture/Database Schema/` | Supports future storage, logs, and model artifact organization |
| `Docs/Architecture/Use case/` | Captures end-user interactions and inference workflows |
| `Docs/Architecture/Conceptual Framework/` | Provides conceptual alignment between research goals and technical execution |

---

## Core Delivery Streams

| Stream | Scope | Primary Outputs |
| --- | --- | --- |
| Data Engineering | Raw dataset discovery, cleaning, currency harmonization, parquet export | `macro_lookup_table.json`, harmonized marketplace corpus |
| NLP & Feature Engineering | Text cleaning, TF-IDF, SVD, metadata scaling, coordinate fusion | vectorizer, reducer, scaler artifacts |
| Spatial Pricing Engine | KD-Tree partitioning, IDW regression, peer explainability | prediction-ready pricing engine |
| Financial Rules | M-Pesa surcharge logic and domestic margin protection | tariff evaluator module |
| API & Integration | DTOs, inference orchestration, health checks, error handling | FastAPI service |
| Quality & Operations | tests, latency profiling, audit summaries, issue tracking | CI-ready verification baseline |

---

## Implementation Principles

| Principle | Blueprint Decision |
| --- | --- |
| Reproducibility | Every derived artifact must be regenerable from files in `Data/` |
| Separation of concerns | Each pipeline stage is implemented in an isolated module with explicit inputs/outputs |
| Explainability | Predictions must include nearest-neighbor evidence and surcharge transparency |
| Safety | Unknown country metadata should fall back to safe defaults instead of crashing |
| Performance | API inference should target low-latency local execution suitable for mobile-backed flows |
| Auditability | Training summaries, validation metrics, and runtime readiness checks must be persisted |

---

## Target Module Plan

| Module | Responsibility |
| --- | --- |
| `src/ingest_multisource.py` | File discovery, source parsing, macro lookup extraction, and corpus export |
| `src/nlp_pipeline.py` | Text normalization, TF-IDF vectorization, Truncated SVD, artifact persistence |
| `src/macro_arbitrage.py` | Bilateral parity factor computation, metadata scaling, and coordinate fusion helpers |
| `src/spatial_engine.py` | Industry-partitioned KD-Tree search and inverse-distance rate regression |
| `src/tariff_evaluator.py` | Safaricom M-Pesa surcharge calculation and quote augmentation |
| `src/train_pipeline.py` | Train/validation/test orchestration, evaluation, benchmarking, and artifact export |
| `src/serve.py` | FastAPI application, DTO validation, startup loading, prediction and health routes |
| `tests/test_pipeline.py` | End-to-end mathematical and pipeline invariance checks |

> Note: the repository currently contains `Src/` and `Test/` directories, while the planned implementation modules are documented using the conventional Python naming pattern `src/` and `tests/`. Standardizing this layout should be handled early during implementation.

---

## Milestone Roadmap

| Milestone | Goal | Key Outputs |
| --- | --- | --- |
| Milestone 1 | Build multi-source data ingestion and macroeconomic harmonization | processed macro lookup + harmonized corpus |
| Milestone 2 | Deliver semantic NLP cleaning, TF-IDF, and SVD feature extraction | vectorizer and reducer artifacts |
| Milestone 3 | Implement bilateral arbitrage scaling and metadata fusion | scaler artifact + 53D feature vectors |
| Milestone 4 | Build partitioned spatial indexing and IDW regression | KD-Tree artifacts + peer explainability |
| Milestone 5 | Add M-Pesa fee protection for domestic Kenyan pricing | tariff evaluator logic |
| Milestone 6 | Train, validate, benchmark, and serialize the master model pipeline | training summary + production artifacts |
| Milestone 7 | Serve the pipeline via FastAPI with validated contracts | `/health` + `/api/v1/optimize-price` |
| Milestone 8 | Verify correctness, latency, and operational readiness | pytest suite + profiling report |

Detailed issue definitions for each milestone live in `Docs/Project_Milestones_and_Issues.md`.

---

## Delivery Gates

| Gate | Exit Criteria |
| --- | --- |
| Data Readiness | Macro lookup and harmonized corpus are generated with no critical nulls |
| Feature Readiness | Text and metadata features are deterministic, persisted, and reloadable |
| Model Readiness | Validation metrics beat baseline and satisfy target quality thresholds |
| API Readiness | FastAPI service loads artifacts on startup and returns valid structured JSON |
| Production Readiness | Tests pass, latency targets are measured, and runtime failure modes are documented |

---

## Model Selection Scope Decision

To keep the feature track focused and deliverable within the project scope, the production pricing model will remain a **KNN-style peer model**: the domain-partitioned KD-Tree with inverse-distance weighting and peer explainability payloads implemented in Milestones 4.1 and 4.2.

The experimental evaluation workflow may tune and compare:

- the number of neighbors `k`,
- distance-weighting and text/metadata feature-block weights,
- target transformations such as `log1p(target_rate)`, and
- the KNN baseline against a limited offline comparison model when useful for analysis.

These experiments support evidence-based tuning but do not expand the production scope to a collection of unrelated model families. Any alternative model is an evaluation reference only; production inference remains KNN/IDW so that peer explanations, partition routing, latency targets, and the existing API contract stay consistent.

The dependent variable remains `target_rate` in KES/hour. The independent variables remain the 53-D hybrid coordinate (`50` text dimensions plus `3` normalized metadata dimensions), together with the selected KNN configuration.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Sparse or inconsistent raw datasets | Weak model quality | Add filtering rules, fallback defaults, and validation reports in ingestion |
| Country-code mismatch across sources | Bad parity calculations | Centralize ISO normalization in Milestone 1 |
| Domain imbalance by industry | Poor peer matching in niche partitions | Apply partition fallback strategy in the spatial engine |
| Excessive feature drift from noisy text | Unstable predictions | Standardize NLP preprocessing and audit explained variance |
| Latency regression at inference time | Mobile usability degradation | Benchmark transform/search steps separately in Milestone 8 |
| Repository drift between docs and code | Planning confusion | Keep the roadmap doc and GitHub tracker synchronized |

---

## Definition of Done for the Feature Track

The feature track is considered complete when all of the following are true:

- all eight milestones are closed,
- every planned module exists and is test-covered,
- the training pipeline writes reloadable artifacts,
- the API serves valid recommendations and health state,
- automated tests pass consistently, and
- the documentation reflects the implemented architecture rather than only the intended design.

---

## GitHub Planning Convention

The GitHub execution plan should use:

- milestone titles aligned to the roadmap above,
- issue titles prefixed by milestone identifiers such as `M1.1`, `M2.2`, etc.,
- domain labels for data, NLP, ML, API, testing, and performance,
- acceptance criteria inside each issue body, and
- a shared planning label for the **Price Optimization Model Feature Track**.

---

## Immediate Next Priority

Because the repository currently has design assets and datasets but no implementation modules, the first engineering focus should be:

1. source file discovery,
2. macroeconomic lookup extraction,
3. marketplace dataset harmonization, and
4. processed corpus export.

That work unlocks all later NLP, model training, API, and verification milestones.
