# Issue #91 — pricing-label provenance and OOT readiness

**Project scope decision (2026-10-04):** This is a computer-science
implementation project. Collecting or verifying paid mentor transaction rates,
demonstrating pricing accuracy, and enforcing an empirical OOT R² threshold are
**deferred, not prerequisites** for API, model-serving, Firestore, Android, or
CI engineering. Existing marketplace labels are demonstration/proxy data, not
verified mentor prices. Continue testing parsing, feature isolation, artifact
compatibility, deterministic inference, pricing invariants, authentication and
other software behavior. Do not present proxy scores as validated real-world
mentor-pricing performance. The remainder of this report preserves the audit
findings and a possible *future* experimental protocol, not a delivery gate.

Reproduce from a local checkout containing the ignored raw CSVs, macro lookup and
harmonized parquet:

```powershell
python -m src.label_provenance_audit
python -m pytest -q tests/test_label_provenance_audit.py tests/test_train_pipeline.py
```

The first command writes an **aggregate-only** JSON report to ignored
`reports/label_provenance_audit.json`. It records SHA-256 digests of the input
snapshot, source/industry exclusions, source/country counts, per-industry rate
quantiles and timestamp coverage. No individual text, job links, IDs or row-level
timestamps are exported. Figures below are for the local snapshot audited on
2026-10-04; re-run against any replacement inputs rather than reusing its counts.

## Label construction and observed coverage

* `upwork_jobs`: for hourly postings only, `hourly_low`/`hourly_high` midpoint
  (or the sole available bound) in USD/hour. **This is a client's posted budget,
  not a mentor's accepted or verified earnings.** The raw CSV has
  `published_date` with timezone; all 53,058 raw rows have parseable source
  timestamps. Ingestion previously discarded it. The date of publication is an
  observation of a *job posting*, not a mentor transaction.
* `upwork_data_scientists`: `hourlyRate` is a self-reported profile asking rate
  in USD/hour, **not a verified transaction**. There is no observation-time
  column. No ingestion/export timestamp can repair that absence.
* `src/ingest_multisource.py` keeps records with descriptions >= 40 characters
  and a USD rate whose `USD * 130` is within **[500, 35,000] KES/hour**, inclusive.
  It rounds pre-arbitrage KES to cents, derives country codes (unknown countries
  can default to KE), uses the macro lookup to calculate the bilateral factor
  with default alpha 0.5 and a KE mentor anchor, then records
  `harmonized_hourly_rate = round(hourly_rate * unrounded_factor, 2)`.
  `src/train_pipeline.py` prefers this **post-arbitrage** column as `target_rate`.
  The stored factor is rounded separately to six places; the audit tolerates
  only this small serialization error. Profile `country` is currently used as
  `client_country_iso2` despite the fixed KE mentor anchor: this is not
  validated as the actual client/mentor pairing. Bilateral scaling changes the
  label; it does not verify it.

| Source / industry | Priced candidates | Excluded pre-arbitrage | Processed | Outside post bounds |
| --- | ---: | ---: | ---: | ---: |
| Profiles / data_ai | 120 | 1 | 119 | 8 |
| Profiles / design_creative | 4 | 0 | 4 | 1 |
| Profiles / web_backend | 8 | 1 | 7 | 0 |
| Jobs / data_ai | 2,837 | 32 | 2,805 | 894 |
| Jobs / design_creative | 10,080 | 212 | 9,868 | 2,742 |
| Jobs / devops_cloud | 671 | 3 | 668 | 315 |
| Jobs / digital_marketing | 1,109 | 51 | 1,058 | 154 |
| Jobs / general_tech | 2,053 | 53 | 2,000 | 366 |
| Jobs / mobile | 684 | 4 | 680 | 166 |
| Jobs / product_management | 104 | 2 | 102 | 14 |
| Jobs / web_backend | 5,418 | 52 | 5,366 | 1,398 |
| **Totals** | **23,088** | **411** | **22,677** | **6,058** |

Of 53,058 raw job rows, 22,956 have usable hourly-rate candidates; 30,102
are non-hourly or have unusable/missing hourly ranges. Of 132 raw profiles, 132
have priced candidates. All 411 pre-arbitrage exclusions in this snapshot are
out-of-bounds rates. Retained rows are 22,547 jobs plus 130 profiles; raw
candidate counts match the parquet per source/industry. The KES/hour
pre-arbitrage distribution is min 520, median 2,925, max 34,125; the
post-arbitrage distribution is min 166.90, median 14,542.56, max 343,823.36.
Therefore the ingestion bound **does not** bound the training label. The JSON
report includes p25/p75 and per-source/industry distributions, not just these
summaries. For mapped client-country codes, jobs are concentrated in US
(10,213) and KE (7,682); profiles include 95 KE and 26 IN. These are
inferred/mapped codes, not verified population locations; consult the JSON
for all countries and segments.

## Optional future OOT eligibility design (deferred)

**Current parquet: no chronological OOT split.** It has no observation-time
column: 0/22,677 timestamps are present. Among retained raw job candidates,
22,547/22,547 have parseable timezone-aware publication times (22,041 distinct,
from 2023-12-02 through 2024-02-23 UTC); none of 130 profiles have observation
times. The ingestion path now preserves aware `published_date` values as
`observation_timestamp_utc` on *future rebuilt* parquet only; it does not
backfill, synthesize timestamps or silently replace the existing dataset.

If empirical job-budget evaluation is resumed later, predeclare the following
policy **before fitting or inspecting held-out outcomes**:

1. Keep the existing description and [500, 35,000] pre-arbitrage KES/hour
   eligibility rules. Then require a timezone-aware source publication time
   and a **post-arbitrage** harmonized rate in [500, 35,000] KES/hour. Exclude
   undated profiles from the temporal cohort; retain and report every excluded
   source/industry count. With this exact snapshot, at most 16,498 job rows
   would qualify after a timestamp-preserving rebuild (22,547 - 6,049 post-
   bound exclusions), conditional on row-level provenance checks. The
   **existing** parquet qualifies zero dated rows. These are prospective
   population rules, not tuned to a model's validation score.
2. Use a chronological cutoff determined without looking at held-out rates.
   Assign all equal source timestamps to the same side; training dates must
   precede evaluation dates strictly. Verify source-event reliability and
   source-row identity across rebuild before running the split. Fit NLP,
   metadata scalers, enrichment/statistics and KD-Trees on training rows only.
   Current stratified results are exploratory, not OOT evidence.
3. Report IQRs on training data for diagnostics; do **not** discard extra
   outliers using holdout data or a score-selected IQR rule. The original
   blueprint's **raw-KES R² >= 0.75** target is deferred, not a requirement for
   software delivery. If revisited, report scores honestly on the specified
   population without treating a proxy result as mentor-price validation.
   Do not use `hourly_rate`, `hourly_rate_usd`,
   `harmonized_hourly_rate`, `target_rate`, ID/link, or post-outcome fields as
   predictors. The 53D training path currently uses text plus three named
   metadata features; tests perturb all rate columns without changing
   coordinates. Its full-corpus saturation/density enrichment must be
   recomputed train-only in #81 to avoid future-population lookahead.

**Mentor-pricing population: not supported by these labels.** Publication
times can make job-budget OOT evaluation possible, but cannot convert posted
budgets or undated profile asking rates into dated verified mentor prices.
Acquiring consented, timestamped mentor transactions is **out of scope for now**;
do not create an acquisition dependency for #81 or downstream engineering.
Should the project later choose to validate mentor pricing empirically, define
the target population, consent, date, units, country roles and provenance in a
separate scoped issue. Do not claim the 0.75 target is achievable on this data.
