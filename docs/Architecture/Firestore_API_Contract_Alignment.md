# Firestore and API Contract Alignment

## Scope

M7.1 defines validation contracts only. Firestore runtime wiring is intentionally deferred to M7.2, but the DTO field names are aligned with the supplied architecture assets:

- `docs/Architecture/Database Schema/Database Schema.svg`
- `docs/Architecture/ERD/ERD.svg`

The persistence design is Google Cloud Firestore NoSQL.

## Firestore collection mapping

| Firestore collection | Schema entity | M7.1/API relevance |
| --- | --- | --- |
| `mentors` | `MENTOR` / `Mentors` | Resolves mentor country and account context for pricing requests |
| `macro_indices` | `COUNTRY_MACRO_INDEX` / `Macro` | Stores currency, PPP, cost-of-living index, and recalibration metadata |
| `industry_partitions` | `INDUSTRY_PARTITION` / `Industry` | Stores active industry partitions and baseline-rate references |
| `service_listings` | `SERVICE_LISTING` / `Listings` | Stores listing text, latent vectors, industry assignment, and floor-rate data |
| `mpesa_tariffs` | `MPESA_TARIFF_BRACKET` / `Tariffs` | Stores transaction type, amount bands, and transfer fees |
| `historical_transactions` | `HISTORICAL_TRANSACTION` / `Transactions` | Stores prediction, surcharge, KNN, similarity, and execution audit fields |

## API DTO mapping

### `PricingQueryDTO`

The request contract is an inference-time DTO and does not write directly to Firestore. Its fields resolve to persistence data as follows:

| DTO field | Source/related persistence field |
| --- | --- |
| `raw_description` | `service_listings.raw_description` |
| `selected_industry` | `service_listings.industry_id` / `industry_partitions.industry_id` |
| `mentor_country` | `mentors.country_code` |
| `client_country` | `historical_transactions.client_country_code` and `macro_indices.country_code` |
| `competitiveness_score` | `service_listings.market_competitiveness` |
| `market_saturation_score` | Derived feature used by the M3/M6 feature pipeline |

### `PredictionResultDTO`

The response fields align with the transaction/audit entity:

| DTO field | Persistence/audit field |
| --- | --- |
| `base_predicted_rate` | `historical_transactions.base_predicted_rate` |
| `mpesa_tariff_surcharge` | `historical_transactions.mpesa_tariff_surcharge` |
| `final_quoted_rate` | `historical_transactions.final_quoted_rate` |
| `bilateral_arbitrage_factor` | `historical_transactions.bilateral_arbitrage_factor` |
| `nearest_neighbors[].peer_index` | KNN peer reference/index in the inference payload |
| `nearest_neighbors[].distance` | Peer distance used for explainability |
| `nearest_neighbors[].verified_rate` | Historical peer verified rate |
| `nearest_neighbors[].similarity_score` | Historical transaction similarity field |
| `nearest_neighbors[].idw_weight` | Derived IDW contribution; persisted only if the audit schema enables it |
| `currency` | Country/currency context; current pricing contract is `KES` |

## Contract boundaries

- Pydantic validation happens before inference or persistence.
- Firestore document IDs and references are persistence concerns, not accepted from the public pricing request.
- Extra request fields are rejected to prevent accidental persistence/API drift.
- Country codes are normalized to uppercase ISO-2 values before downstream use.
- `target_rate`, peer training rows, and internal model artifacts are never accepted from a public request.
- M7.2 will add Firestore/model loading and route wiring without changing these public DTO names unless a new versioned API contract is approved.

## M7.1 implementation

The public contracts are defined in `src/api_contracts.py`:

- `PricingQueryDTO`
- `PeerMatchDTO`
- `PredictionResultDTO`
- `HealthResponseDTO`

The DTO layer does not require the Firebase Admin SDK. That dependency belongs to the M7.2 service integration and should be introduced only when startup loading and persistence behavior are implemented.

