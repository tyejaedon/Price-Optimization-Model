# Platform dataset ingestion (#102)

The engine has only ever seen Upwork and freelancer rates. The platform it quotes for now publishes its own dataset from its staging API: 222 mentors with the hourly rate they list, their skills, tier, rating and city; 16k bookings with what clients paid and whether the session happened; 6k reviews. `src/ingest_platform.py` pulls it and maps mentors into the same harmonized record shape as `src/ingest_multisource.py`, so the parquet drops into the existing training path.

Every row in that dataset is synthetic. Say so wherever you report numbers from it.

## Run it

```bash
# one-off: a platform login (any ordinary account), never committed
export PLATFORM_API_EMAIL=you@example.com
export PLATFORM_API_PASSWORD=...

python -m src.ingest_platform
# fetches 5 CSVs into data/raw/career_mentor_os/, writes
#   data/processed/platform_mentor_corpus.csv
#   data/processed/platform_mentor_corpus.parquet
# and prints a summary

python -m src.ingest_platform --offline   # reuse the cache, no network
```

`PLATFORM_API_BASE_URL` defaults to the staging API. The dataset is refused with HTTP 403 on any deployment where it is switched off, and it is never served from production; the client says so instead of failing cryptically.

## Scope, decided explicitly

The engine's partitions are technical. The platform's mentors mostly are not: culinary, construction, electrical, beauty, agriculture and so on. Those categories are **excluded** and counted under `out_of_scope_category`, not pushed into `general_tech`, which would put plumbers next to backend engineers in the KD-tree.

| Platform category | Partition |
| --- | --- |
| Technology & IT | resolved from the mentor's skills with `map_industry_partition`; `general_tech` if nothing matches |
| Marketing & Communications | `digital_marketing` |
| Business & Management | `product_management` |
| everything else | excluded |

The mapping is one dict, `PLATFORM_CATEGORY_PARTITIONS`. Change it there if the engine's scope changes.

Retained rows then go through `marketplace_exclusion_reason`, the same gate as every other source, so description length and the KES rate bounds apply identically.

## Columns

The first ten columns are the harmonized shape (`source_dataset` = `career_mentor_os_sandbox`, `hourly_rate` in KES, `hourly_rate_usd` via the shared anchor, `observation_timestamp_utc` from the mentor's join date). `raw_description` is built from specialization, category, skills, tier, experience and city, because the export carries no free-text bio.

The rest is platform truth the Upwork corpus never had:

| Column | Meaning |
| --- | --- |
| `listed_hourly_rate_kes` | what the mentor asks on the platform (same value as `hourly_rate`) |
| `realised_hourly_rate_kes` | median of `amount / hours` over the mentor's COMPLETED bookings; null if none |
| `completed_sessions` | count of COMPLETED bookings |
| `no_show_rate` | NO_SHOW over bookings that reached a verdict (COMPLETED, NO_SHOW, CANCELLED) |
| `mean_review_rating`, `review_count` | from the reviews file |
| `platform_*` | ids, category, tier, verification, experience, city, skills, for joins and slicing |

## What to do with it

Two evaluations become possible that were not before:

1. Quote each in-scope mentor's `raw_description` through the engine and compare against `listed_hourly_rate_kes`. That is "does the model agree with what Kenyan mentors on this platform actually charge", per partition.
2. Compare against `realised_hourly_rate_kes` where it exists. Listed and realised differ when sessions are not priced at the hourly rate, and the gap is itself a pricing signal.

Keep the platform rows out of training when running either evaluation, or the comparison is circular.

## Tests

`tests/test_ingest_platform.py` runs against small fixtures in `tests/fixtures/platform/` and a mocked HTTP transport. Nothing in the test suite touches the network.
