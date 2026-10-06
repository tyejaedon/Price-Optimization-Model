# AI Dynamic Pricing Platform for Technical Mentors

**"What hourly rate could I suggest for this mentoring service?"** This project turns a service description, industry, and mentor/client countries into a suggested rate in Kenyan shillings per hour (KES/hour). It compares the description with similar records, accounts for country and market context, and optionally adds a Kenyan M-Pesa fee. It does not negotiate, transfer money, or guarantee earnings.

The journey is **profile/service text -> comparable peers -> suggested KES/hour base rate and negotiation range -> optional M-Pesa fee -> final quote**. For example, an illustrative base rate of **4,700 KES/hour** plus the configured **57 KES** Kenyan transfer fee gives **4,757 KES/hour**. The negotiation range excludes the fee. This is arithmetic, not a measured price recommendation: today's training labels are advertised freelance rates and job budgets (**proxy labels**), not verified mentor payments.

### Available now vs planned

| Available in this repository | Planned or not established |
| --- | --- |
| Python ingestion, fitted text/metadata features, peer search, fee/corridor calculation, training and artifact export | Empirical accuracy against verified mentor transactions; the proposed out-of-time quality gate remains deferred (#81/#91) |
| Local unauthenticated FastAPI app; separate Firebase-protected deployment entrypoint; camelCase contract with legacy compatibility | Evidence that a production mobile-to-cloud service is ready; local execution is not a deployed-service measurement |
| In-memory and Firestore repositories, owner-bound mentor reads, root service-listing provenance, observable background quote audits | Automatic hydration of omitted request text (#84); durable audit retries are not guaranteed |
| Docker/CI foundations and an in-process protected-pricing benchmark (#70) | Native Android client and live authenticated 3G round-trip-time measurement (#86) |

The protected components need external reviewed artifacts, approved tariff pins, Firebase configuration and credentials supplied at runtime. Their presence in source is not proof of a working cloud deployment. The unauthenticated local app **must not be deployed**. A quote's confidence field is currently uncalibrated, not an accuracy probability.

### Start here / read next

Read this introduction, then try the [cell-by-cell local demo notebook](notebooks/pipeline_walkthrough.ipynb) without private datasets or Firebase. The [documentation index and plain-English glossary](docs/README.md) explain the terms used below and link implementation notes.

For deeper reading, use the [M1-M8 historical baseline](docs/Blueprint.md), the [canonical M9-M14 target and migration decisions](docs/architecture_blueprint%20%281%29.md), and the [issue/milestone roadmap](docs/Project_Milestones_and_Issues.md). These are planning/history documents, not assertions that every proposed feature is implemented. See the [label provenance audit](docs/Label_Provenance_Audit_91.md) before interpreting any model metric.

## Why this application?

Independent consultants can underquote international clients, price local clients out of reach, or overlook transaction fees. The platform aims to combine skill-based peer comparisons with bilateral purchasing-power context and, for Kenyan mentors, Safaricom M-Pesa fee protection. Quotes are recommendations, not guaranteed earnings or verified market prices.

## Target application architecture

| Tier            | Intended design                                                                            | Responsibility                                                                                                                                                     |
|-----------------|--------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Android client  | Kotlin, Jetpack Compose, MVVM, `StateFlow<PricingUiState>`, Retrofit/OkHttp and coroutines | Collect mentor inputs, authenticate with Firebase, request and display pricing; dispatch network calls on `Dispatchers.IO`                                         |
| Pricing gateway | Python 3.11, FastAPI/Uvicorn and Pydantic v2                                               | Verify Firebase ID tokens with the Firebase Admin SDK, validate requests, load model artifacts once at application startup and serve `POST /api/v1/optimize-price` |
| ML engine       | NLTK, scikit-learn and joblib                                                              | Compile peer-pricing artifacts offline; transform requests, retrieve neighbors and calculate a weighted base rate online                                           |
| Persistence     | Firebase Authentication and Cloud Firestore                                                | Link mentors to identities, store service listings and append pricing audit records                                                                                |
| Delivery        | Docker and GitHub Actions                                                                  | Package the API and validate backend/mobile integration without committing credentials or datasets                                                                 |

The Firestore adapter uses `/mentors/{mentor_id}` (auth link and country), root `/service_listings/{listing_id}` (service text, `industry_id`, 50-float SVD vector and peer-rate metadata), and append-only `/historical_transactions/{transaction_id}`. A `mentorId` in the request must be authorized against the verified Firebase UID, not treated as authentication. The stored mentor's `auth_uid` must equal that verified UID; the mentor document ID may differ. Successful protected audit records include the authorized `mentor_id`. Pricing audits run through FastAPI `BackgroundTasks` after the response is formed; failures are observable but there is no durable retry guarantee. See [audit semantics](docs/M11.2_Pricing_Audit.md).

The protected backend verifies Firebase ID tokens before pricing; the planned Android client will supply them. The Android secure-storage approach is tracked in #75; backend Firebase credentials come from runtime secret management/application-default credentials, not the app or this repository. Local tests inject a fake verifier and use no live Firebase keys; `src.deployment:app` refuses to start with Firebase Auth or Firestore emulator environment variables set (the Auth emulator accepts unsigned tokens). Versioned model artifacts must be deployed as a complete set outside Git; missing/incompatible artifacts report unready status and pricing fails explicitly.

## How a price is calculated

**Offline training:** Harmonize historical freelance rates and macroeconomic data into parquet; sanitize and lemmatize service text; fit unigram/bigram TF-IDF (up to 12,000 features) and a 50-component Truncated SVD; scale three macro/market features; fuse them into 53-dimensional coordinates; build industry-partitioned KD-Trees; and export reloadable joblib artifacts.

**Online inference:** Transform the submitted text and metadata with those *same fitted artifacts*, retrieve five peers in the requested industry (or `general_tech` if that niche has fewer than five), and apply quadratic inverse-distance weighting (`1 / (distance² + 1e-6)`). If neither partition has five peers, inference fails rather than silently changing industries. The base predicted rate plus any applicable Kenyan M-Pesa tariff produces the final quote:

```text
finalQuotedRate = basePredictedRate + mpesaTariffSurcharge
```

M11.3 (#73) applies one configured **transfer-to-M-PESA-user** fee from the 15-band Safaricom table last updated August 4, 2026, only to an **authorized Kenyan mentor's** base quote. Other mentors receive zero surcharge. The `baseRateFloor` and corridor remain fee-free; unsupported amounts fail instead of extrapolating. The date-versioned P2P transcription is `config/tariffs/mpesa_p2p_users_2026-08-04.csv`. `config/tariffs/mpesa_other_services_2026-08-04.csv` records other-network, withdrawal, Pochi and merchant/till fees **for reference only**; none affect today's quote or API. A release requires a human review of the live source and a separately approved `PRICING_TARIFF_SHA256` pin; see [tariff policy](docs/M11.3_Mpesa_Tariff.md).

The existing ML and tariff implementations are reused, not restarted. #67 tracks training/inference artifact changes; #71 owns real peer listing IDs, #82 the rate floor/corridor, and #83 the canonical DTO adapter. #68 is closed as superseded by #83.

## Canonical pricing contract (M10.5 / #83)

`POST /api/v1/optimize-price` accepts a camelCase canonical request (a verified Firebase ID token is required in the deployment entrypoint; local `src.serve:app` is unauthenticated). The protected gateway checks the mentor's stored `auth_uid` against the verified Firebase UID. This is an **example request**; `costOfLivingIndex` and `baseRateFloor` are optional:

```json
{
  "mentorId": "mentor-123",
  "rawText": "Experienced Android developer specializing in Kotlin, Jetpack Compose, and mentoring mobile teams.",
  "industry": "mobile",
  "mentorCountry": "KE",
  "clientCountry": "US",
  "competitivenessScore": 0.65,
  "costOfLivingIndex": 0.74,
  "baseRateFloor": 4000.0
}
```

```json
{
  "basePredictedRate": 4700.0,
  "mpesaTariffSurcharge": 57.0,
  "finalQuotedRate": 4757.0,
  "minQuotedRate": 4460.0,
  "maxQuotedRate": 7599.0,
  "kNeighborsUsed": 5,
  "bilateralArbitrageFactor": 0.51,
  "confidenceScore": 0.0,
  "comparables": [],
  "reason": "Weighted from 5 indexed peers in KES/hour; corridor excludes the M-Pesa surcharge. Kenyan M-Pesa fee of 57.00 KES/hour is added once to the base rate. Listing-backed comparables are unavailable for some peers.",
  "timestamp": "2026-10-06T12:00:00Z"
}
```

The response illustrates an assumed peer base of 4,700 KES/hour, weighted peer standard deviation of 320 KES/hour and bilateral factor of 0.51: the lower bound is `max(4000, 4700 - 0.75*320) = 4460`, and the upper bound is `(4700 + 1.25*320)*(2 - 0.51) = 7599`. These inputs are illustrative, not the output of the request against a particular trained bundle; actual rates and country factors depend on the fitted export and lookup. Rates above are KES/hour **proxy estimates**, not empirically verified mentor prices. Canonical requests require `mentorId`, `industry`, `mentorCountry`, `clientCountry` and (for now) `rawText` (20–2000 characters); omitted text returns 422 until verified Firestore hydration is added in #84. Countries must be two ASCII letters (uppercased); `competitivenessScore` defaults to 0.5, must be in [0, 1], and maps to the **fitted** `market_saturation_score` feature, not partition density. An optional finite `costOfLivingIndex` in [0.01, 1000] replaces only the mentor-side lookup value when computing the bilateral factor; it is **not** a fourth feature or an alias of saturation. An optional finite non-negative `baseRateFloor` is in KES/hour; if it exceeds the computed ceiling the API returns 422. All quote/corridor rates are KES/hour, and the corridor excludes M-Pesa fees, so `finalQuotedRate` can exceed `maxQuotedRate`. The returned `kNeighborsUsed` counts indexed peers actually used by IDW; `similarityScore = 1 / (1 + euclideanDistance)` (rounded in legacy index results). Only peers explicitly matched during export to actual root `/service_listings/{listing_id}` documents are returned in `comparables` (with the stored `jobTitle`); existing proxy artifacts still have row indices only and yield empty comparables. `confidenceScore` is **0.0 = not empirically calibrated**, not a probability of accuracy. `reason` reports the number of peers and missing listing provenance; `timestamp` is a UTC response creation time. No peer IDs or confidence claims are invented.

**Compatibility/deprecation:** Existing snake_case callers can continue to use the **same** `POST /api/v1/optimize-price` with `raw_description`, `selected_industry`, `mentor_country`, `client_country`, optional `market_saturation_score`, `base_rate_floor`, and (for protected calls) `mentorId`/`mentor_id`. They receive the original snake_case `PredictionResultDTO` with `nearest_neighbors` and a `Deprecation: true` response header. The OpenAPI operation exposes both request/response schemas and calls out the deprecated legacy DTO. Do not mix snake_case and camelCase fields in one request (422); there is no new endpoint or removal date. `GET /health` now adds `service`, `unit: "KES/hour"`, `modelsLoaded` and `version` while retaining all legacy health fields; `/ready` is unchanged. The separate platform integration `POST /price` (#99) is not the canonical API.

## What runs today

The protected deployment returns 401 for missing/invalid bearer tokens, 403 for absent/inactive mentors or an owner UID mismatch, 422 for a request country differing from the stored mentor or invalid inputs/floors, and 503 for missing/untrusted model artifacts or a failed mentor lookup. These failures never schedule an audit. Mentor document ID is not presumed equal to the verified Firebase UID: `/mentors/{mentor_id}.auth_uid` is the trusted owner mapping; existing unbound profiles do not grant access. Successful quotes schedule an observable append-only background audit (#72). Injected **legacy** inference implementations may still omit the optional corridor; canonical calls then return 503 rather than a fabricated range. The service also exposes Swagger UI at `/docs`. The unauthenticated `src.serve:app` entrypoint is for local use only and **must not be deployed**.

**Listing provenance (#71):** The trusted memory/Firestore repository validates root listing documents (native 50-float SVD vector, partition, mentor parent, active status, title and source-approved KES/hour peer rate); it exposes no public listing-write endpoint. A harmonized training row with a `listing_id` must match that stored document's text, title, partition and rate, or export fails. `--verify-listings-firestore` opts an evaluation/OOT export into root-document verification using externally supplied Application Default Credentials; without a repository, a claimed training listing ID fails rather than being treated as proven. Legacy/proxy rows without IDs remain valid but unlisted. See [M11.1 schema and listing release procedure](docs/M11.1_Firestore_Listing_Peers.md) for sourcing, vector refresh, IAM and snapshot consistency. No generated data or artifacts are checked into Git.

The local service loads model artifacts at FastAPI startup, so train and export artifacts before expecting a ready model. See `src/api_contracts.py` and `src/serve.py` for the **current** API schema and behavior.

**Container delivery (#77):** `Dockerfile` starts the separate `src.deployment:app` entrypoint, which requires a configured Firebase project, Admin SDK token verification, Firestore and read-only external artifact/tariff mounts; `/ready` returns 503 on missing artifacts or Firestore failure. Set `FIRESTORE_DATABASE_ID=priceoptimizationmodel` in the runtime environment for this project's named database (#113); if unset, the SDK uses `(default)`, which will not work after that database is removed. This ID is not a credential. The legacy local `src.serve:app` remains unauthenticated and **must not be deployed**. [Container setup and CI gate status](docs/M13.2_Container_and_CI.md) records the required secrets, fake-backed tests, and pending Android/emulator and staging validation. Empirical OOT pricing validation is deferred (#91), not a software deployment gate; no production-ready mobile-cloud claim is made until the remaining integration work lands.

The current 53D feature schema remains `[bilateral_arbitrage_factor, market_saturation_score, industry_relative_density]`, in that order after 50 text features. Evaluation exports now include `inference_config.json`, bundled macro lookup and a **versioned `artifact_manifest.json`** alongside all fitted files. The manifest records preprocessing, partition/fallback and IDW query policy (default k=5, epsilon=1e-6), file and dataset SHA-256, source/split provenance, and `exploratory_not_empirically_approved`. Serve **only internally reviewed, immutable exports**: set `PRICING_ARTIFACT_MANIFEST_SHA256` to the SHA-256 of the manifest from an **independent trusted release record**, not one computed automatically from an arbitrary mounted artifact set. A missing pin, old unsigned set, mismatched hash, schema or corrupt file yields 503 `/ready` before joblib deserialization. `/health` reports the manifest revision, dataset version, source type and exploratory status (or a sanitized failure reason). A compatible proxy demo is **not** evidence of verified mentor pricing or OOT accuracy. See [#95 deployment steps](docs/M13.2_Container_and_CI.md).

For why modeling defaults were chosen, what has actually been tested and how to record future one-variable experiments, use the [experimental design and evidence index](docs/experiments/README.md). Its proxy findings do not change the deferred mentor-pricing validation scope.

Online density is the median training value for the selected partition, not the legacy request's `competitiveness_score` (still accepted but unused). Canonical `competitivenessScore` maps to the trained **second** saturation feature; `costOfLivingIndex` affects only the existing bilateral factor, not a new scaler dimension. The trained third feature is density, not the proposed mentor cost-of-living feature. The existing TF-IDF training `min_df=1` differs from the proposed `df>=2`; neither is relabeled as though it were migrated. The existing stratified evaluation is not chronological OOT evidence (#81). No generated model or data files belong in Git.

### Run the existing Python pipeline locally

Requires Python 3.11+, raw input datasets under `data/raw/` for ingestion, and the dependencies in `requirements.txt`. Datasets, generated artifacts and service credentials must remain outside version control.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet')"

python -m src.ingest_multisource --mode macro_lookup --output data/processed/macro_lookup_table.json
python -m src.ingest_multisource --mode harmonize_parquet --macro-lookup data/processed/macro_lookup_table.json --output data/processed/harmonized_marketplace_corpus.parquet
python -m src.train_pipeline --mode evaluate --harmonized-parquet data/processed/harmonized_marketplace_corpus.parquet --macro-lookup data/processed/macro_lookup_table.json --artifact-dir artifacts --no-enforce-quality-gate
$env:PRICING_ARTIFACT_MANIFEST_SHA256 = (Get-FileHash .\artifacts\artifact_manifest.json -Algorithm SHA256).Hash.ToLowerInvariant()  # local export only
uvicorn src.serve:app --host 127.0.0.1 --port 8000
```

The training command above disables historical stratified R² and baseline promotion checks for **local exploratory export only**; its proxy job-budget/profile-rate metrics do not validate real mentor earnings. The local hash command is appropriate only for an export you just built yourself; **never** auto-pin a downloaded/untrusted bundle. Old artifacts require retraining/re-exporting, not an on-the-fly manifest generated around unknown joblib. Verified mentor transaction acquisition and empirical OOT/R2 gating are deferred, not prerequisites for the CS-focused API, security, artifact-parity and Android work (see [issue #91 audit](docs/Label_Provenance_Audit_91.md)). Continue software correctness and security tests. Use `/docs` for the current request schema and `/health` for model readiness. Android build/run instructions will be added when the client exists (#74-#76).

### Chronological OOT training (#81; opt-in research)

`--mode oot` requires a versioned parquet with the ingestion field `observation_timestamp_utc` containing genuine timezone-aware source observation times on **every input row**. Choose the UTC cutoff **before** examining future labels. Rebuilding the local parquet from raw sources preserves job `published_date` on 22,547 job rows, but the 130 profile rows have no source observation date and remain null. OOT training on this mixed parquet therefore fails closed; curate a **separately versioned, predeclared** timestamp-complete job-only dataset rather than fabricating dates or silently discarding undated profiles. Job-post timestamps measure posted *budgets*, not verified mentor transactions. This is non-blocking research, not a claim of validated mentor pricing or a deployment/CI prerequisite.

```powershell
python -m src.train_pipeline --mode oot --harmonized-parquet path/to/timestamped.parquet --macro-lookup data/processed/macro_lookup_table.json --oot-cutoff "2025-01-01T00:00:00+00:00" --dataset-version "source-snapshot-v1" --artifact-dir path/to/new-empty-export
```

The OOT policy excludes non-finite or out-of-range **harmonized target** rates outside 500–35,000 KES/hour before splitting (the ingestion bounds instead apply to pre-arbitrage rates). IQR fences are computed on training labels for diagnostics only; no IQR-based exclusions or outcome-driven tuning are performed. All observations at or before the cutoff train; only strictly later records evaluate. Precomputed corpus-wide saturation/density are replaced by train-only counts; WordNet preprocessing, max-12,000-feature unigram/bigram TF-IDF, 50D SVD, 3D scaler, and k=5 quadratic IDW KD-Trees fit on training rows only. The fresh export contains `training_summary.json` with source SHA-256/version, cutoff, counts, train-only IQR bounds, MAE, RMSE and full-precision raw-KES/hour holdout R². If R² < 0.75 or chronology/features are unusable, the command fails and **does not publish fitted model artifacts**; the failure summary remains for inspection. Never deploy a failed export or treat a synthetic test as empirical OOT evidence. Legacy `--mode evaluate` is stratified and **not** an OOT gate.

## Pivot delivery sequence

| Stage | Milestone | Outcome |
| --- | --- | --- |
| 1 | [Milestone 9](https://github.com/tyejaedon/Price-Optimization-Model/milestone/9) | Adopt the new blueprint and reconcile reusable ML artifacts |
| 2 | [Milestone 10](https://github.com/tyejaedon/Price-Optimization-Model/milestone/10) | Migrate the API contract and secure pricing with Firebase |
| 3 | [Milestone 11](https://github.com/tyejaedon/Price-Optimization-Model/milestone/11) | Align Firestore collections, tariffs and asynchronous audit |
| 4 | [Milestone 12](https://github.com/tyejaedon/Price-Optimization-Model/milestone/12) | Build the Android Compose shell and Firebase sign-in |
| 5 | [Milestone 13](https://github.com/tyejaedon/Price-Optimization-Model/milestone/13) | Integrate Retrofit pricing and prepare Docker/CI delivery |
| 6 | [Milestone 14](https://github.com/tyejaedon/Price-Optimization-Model/milestone/14) | Exercise protected browser demo and validate mobile latency/usability |

Contributions follow the issue-first, draft-PR workflow in [CONTRIBUTING.md](CONTRIBUTING.md). The current project structure is `src/` for Python modules, `tests/` for tests, `docs/` for architecture and planning, and `data/` for ignored local datasets.

## Academic attribution

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

## License

Distributed under the [MIT License](LICENSE.md).
