# AI Dynamic Pricing Platform for Technical Mentors

A planned Android-to-cloud application that recommends market-aware hourly rates for technical mentors and freelancers. A mentor describes a service, selects an industry and the two countries involved, and receives a peer-informed quote with a transparent Kenyan M-Pesa surcharge where applicable.

**Project status:** The Python data, training, pricing, and FastAPI foundations exist. The native Android client, Firebase-protected pricing endpoint, pivot DTOs, Firestore service listings, and asynchronous audit flow are **planned**, not available in this repository yet. The [canonical architecture and migration blueprint](docs/architecture_blueprint%20%281%29.md) is the target under #66; the [M1-M8 engineering blueprint](docs/Blueprint.md) records existing work. [Milestones 9-14](docs/Project_Milestones_and_Issues.md#pivot-roadmap-milestones-9-14) track the migration.

## Why this application?

Independent consultants can underquote international clients, price local clients out of reach, or overlook transaction fees. The platform aims to combine skill-based peer comparisons with bilateral purchasing-power context and, for Kenyan mentors, Safaricom M-Pesa fee protection. Quotes are recommendations, not guaranteed earnings or verified market prices.

## Target application architecture

| Tier | Intended design | Responsibility |
| --- | --- | --- |
| Android client | Kotlin, Jetpack Compose, MVVM, `StateFlow<PricingUiState>`, Retrofit/OkHttp and coroutines | Collect mentor inputs, authenticate with Firebase, request and display pricing; dispatch network calls on `Dispatchers.IO` |
| Pricing gateway | Python 3.11, FastAPI/Uvicorn and Pydantic v2 | Verify Firebase ID tokens with the Firebase Admin SDK, validate requests, load model artifacts once at application startup and serve `POST /api/v1/optimize-price` |
| ML engine | NLTK, scikit-learn and joblib | Compile peer-pricing artifacts offline; transform requests, retrieve neighbors and calculate a weighted base rate online |
| Persistence | Firebase Authentication and Cloud Firestore | Link mentors to identities, store service listings and append pricing audit records |
| Delivery | Docker and GitHub Actions | Package the API and validate backend/mobile integration without committing credentials or datasets |

The intended Firestore collections are `/mentors/{mentor_id}` (auth link and country), root `/service_listings/{listing_id}` (service text, `industry_id`, 50-float SVD vector and peer-rate metadata), and append-only `/historical_transactions/{transaction_id}`. A `mentorId` in the request must be authorized against the verified Firebase UID, not treated as authentication. Pricing audits are intended to run through FastAPI `BackgroundTasks` after the response; reliability and failure reporting are tracked in #72.

Firebase ID tokens will be supplied by the Android client and verified on the backend before pricing. The Android secure-storage approach is tracked in #75; backend Firebase credentials come from runtime secret management/application-default credentials, not the app or this repository. Versioned model artifacts must be deployed as a complete set outside Git; missing/incompatible artifacts report unready status and pricing fails explicitly.

## How a price is calculated

**Offline training:** Harmonize historical freelance rates and macroeconomic data into parquet; sanitize and lemmatize service text; fit unigram/bigram TF-IDF (up to 12,000 features) and a 50-component Truncated SVD; scale three macro/market features; fuse them into 53-dimensional coordinates; build industry-partitioned KD-Trees; and export reloadable joblib artifacts.

**Online inference:** Transform the submitted text and metadata with those *same fitted artifacts*, find up to five peers in the requested industry, and apply inverse-distance weighting to their rates. The target design uses a quadratic distance penalty (`p=2`, `epsilon=1e-6`). The base predicted rate plus any applicable Kenyan M-Pesa tariff produces the final quote:

```text
finalQuotedRate = basePredictedRate + mpesaTariffSurcharge
```

The existing ML and tariff implementations are reused, not restarted. #67 tracks any training/inference feature, IDW or artifact changes needed to match this target; #71 owns real peer listing IDs, #82 the rate floor/corridor, and #83 the new response and confidence semantics. #68 is closed as superseded by #83.

## Target pricing contract (planned)

The target `POST /api/v1/optimize-price` requires a verified Firebase ID token and a validated `PricingQueryDTO`. The following illustrates the **proposed** request and response shape, not the currently deployed API:

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
  "kNeighborsUsed": 1,
  "confidenceScore": 0.82,
  "bilateralArbitrageFactor": 0.51,
  "comparables": [
    {
      "listingId": "listing-123",
      "verifiedRate": 4900.0,
      "similarityScore": 0.82
    }
  ],
  "reason": "Illustrative peer-based recommendation with a Kenyan M-Pesa surcharge."
}
```

Rates in this example are illustrative KES/hour values. The proposed DTO limits `rawText` to 20-2,000 characters, uses two-letter country codes and bounds `competitivenessScore` to 0-1. The identity-to-mentor mapping and contract migration belong to #69 and #83; the route itself stays the same. #84 owns authorized hydration when text or metadata is missing. The legacy snake_case contract remains supported during the migration and must be deprecated explicitly before any versioned removal; **the current API does not accept this request or return this response**. `industry` maps to the training partition / Firestore `industry_id`; `costOfLivingIndex` is not a saturation score. Rates throughout are KES/hour.

## What runs today

The existing Python service exposes `POST /api/v1/optimize-price` using snake_case fields such as `raw_description`, `selected_industry`, `mentor_country`, `client_country`, `competitiveness_score` and `market_saturation_score`. Its response uses `base_predicted_rate`, `mpesa_tariff_surcharge`, `final_quoted_rate` and `nearest_neighbors`. It also exposes `GET /health` and Swagger UI at `/docs`. Pricing currently lacks Firebase token verification and writes transactions synchronously; do not treat it as the secured pivot gateway.

The local service loads model artifacts at FastAPI startup, so train and export artifacts before expecting a ready model. See `src/api_contracts.py` and `src/serve.py` for the **current** API schema and behavior.

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
uvicorn src.serve:app --host 127.0.0.1 --port 8000
```

The training command above disables the evaluation quality gate for local exploration; inspect its reported metrics before relying on its artifacts. Use `/docs` for the current request schema and `/health` for model readiness. Android build/run instructions will be added when the client exists (#74-#76).

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
