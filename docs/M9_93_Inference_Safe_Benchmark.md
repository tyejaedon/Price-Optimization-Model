# Issue #93 — inference-safe feature and hybrid-distance research

**Research only; not a serving-quality gate.** Labels are posted job budgets in
KES/hour, **not verified mentor transaction prices**. This optional work does
not block M10–M14, promote artifacts or claim the deferred #81 mentor-pricing
`R² >= 0.75` target. #94 owns comparisons with supervised estimators; #67/#70
own any eventual service/artifact or end-to-end latency changes.

## Candidate inventory and exclusions

| Signal / ablation | Source | Actual pricing request availability | Sensitivity / fit | Decision |
| --- | --- | --- | --- | --- |
| Raw description and its skill/title words | `raw_description` | `PricingQueryDTO.raw_description` | User-supplied free text; sanitize and fit TF-IDF/SVD on train only | Baseline bigrams; compare unigram TF-IDF and normalized 50D SVD without changing 53D schema |
| Bilateral country factor | `mentor_country_iso2`, `client_country_iso2` + macro lookup | `mentor_country`, `client_country` | Country inference can be sensitive; frozen macro lookup and scaler, never fit on holdout | Retain first of three metadata coordinates |
| Market saturation | `market_saturation_score` | `PricingQueryDTO.market_saturation_score` | Train-only scaler; online range 0–1 | Retain second coordinate; compare metadata block weight 1 vs 0.5 |
| Industry / relative density | `industry_partition` + train-only counts | `selected_industry` and frozen per-industry `partition_density` | Partition group is request-visible; derive counts from training rows only | Retain third coordinate and fallback, fixed `k=5`, quadratic IDW with `epsilon=1e-6` |
| `job_title`, separately supplied skills, experience | Job records or proposed future DTOs | Not separate fields in current pricing request | May reveal profile details; extraction would need trained preprocessing | **Exclude**; adding inputs requires a versioned DTO, feature/artifact schema and train/serve parity migration (#67/#70) |
| Source indicators and arbitrary country interactions | `source_dataset`, harmonized corpus | Source not an online pricing field; country mapping must be specified separately | Existing M6.5 offline enrichment changes dimensions | **Exclude** pending an explicit versioned 53D-to-new-schema migration |
| `competitiveness_score`, optional cost of living | DTO fields / future pivot field | Possible input, but not fitted in the current scaler | Must not alias saturation or alter trained scaler order | **Exclude** pending #67/#83 migration |
| Rate fields, target, IDs, links, post-outcome status | `hourly_rate`, `hourly_rate_usd`, `harmonized_hourly_rate`, `target_rate`, record IDs, etc. | Outcomes unknown when quoting | Direct leakage / identity risk | **Forbidden as features**; the post-arbitrage rate is used only for predeclared cohort eligibility, train labels and split metrics |

All benchmark candidates stay at exactly 50 text + 3 metadata dimensions. TF-IDF
vocabulary, SVD, metadata scaler, partition counts and KD-Trees fit only on the
training window. The 53D query policy and exact text settings are persisted in
research-only joblib/JSON under the ignored report directory, including
`ngram_range`, `min_df`, `normalize_output`, weights, `k`, epsilon, fallback and
frozen density mapping. No new online schema is introduced. These artifacts
have **no deployable manifest** and must not be pointed at a production gateway.

## Reproduction and limits

Use a **new empty output directory** on an ignored local corpus with trustworthy
source publication timestamps (the #91 audit's earlier snapshot lacked them).
Cutoffs must be declared using timestamp coverage **before inspecting rates or
scores**, not tuned against outcomes. Example using the local dated job-posting
snapshot and UTC windows chosen from timestamp coverage alone:

```powershell
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'
python -m src.inference_safe_benchmark --harmonized-parquet data/processed/harmonized_marketplace_corpus.parquet --macro-lookup data/processed/macro_lookup_table.json --validation-cutoff 2024-02-20T00:00:00+00:00 --test-cutoff 2024-02-22T00:00:00+00:00 --dataset-version local-proxy-job-budgets-2026-10-05 --output-dir reports/m9_inference_safe_benchmark --samples 25
python -m pytest -q tests/test_inference_safe_benchmark.py
```

Only `upwork_jobs` rows with an aware publication time and a **post-arbitrage**
KES/hour target in [500, 35,000] are eligible. Profile asking rates have no
observation time and are excluded, not synthesized. Duplicate descriptions are
purged from later windows across all industries to avoid exact text leakage;
this heuristic is **not verified source-event identity**. Timestamp absence,
naive timestamps, empty cohorts or overlapping IDs fail closed. Training dates
precede validation, which precedes the final test; tie timestamps never split.
The random stratified M6.5/M6.6 reports are **not** substitutes for this OOT
proxy-budget experiment. A real mentor-price study would require a separate
consented dated population and verified outcome definitions.

`benchmark.json` records dataset/macro SHA-256, population exclusions, windows,
per-industry sample counts, raw-unit validation metrics for the category-mean
and all predeclared 53D candidates, training Python allocation peak, warmed
local NLP+metadata+IDW p95 and research-artifact size. `selection_frozen.json`
is written **before** final-test features or labels are used. Only the baseline
and validation-selected candidate receive final-test metrics; failed ablations
remain in the report, never promoted. Parity compares request-time coordinates
and predictions after independently loading text, metadata, index and config.
Timing is machine-specific, not a full authenticated-API p95 or #70 SLA;
`tracemalloc` measures Python allocations, **not** process RSS.

## Local run: 2026-10-05 (aggregate, exploratory proxy budgets only)

The ignored parquet had SHA-256
`da5432eec261e8b8aff66d046f276562a75d24b2106d61a9c189571e8725a5ca`;
the ignored macro lookup had SHA-256
`30d8d6b351770b0a85287c4b2791f0549735a8f6b6eac5c914109b3c7782f901`.
Of 22,677 input rows, 130 undated profiles and 6,049 jobs with invalid or
out-of-range post-arbitrage rates were excluded. Another 16/2/3 repeated
descriptions were purged from train/validation/test, respectively. The frozen
UTC boundaries were **2024-02-20 00:00:00** (train/validation) and
**2024-02-22 00:00:00** (validation/test). They yielded **10,703** train,
**2,384** validation and **3,390** test jobs. The actual train window ended
2024-02-19 23:59:44, validation began 2024-02-20 00:00:43 and ended
2024-02-21 02:12:50, and test began 2024-02-22 01:51:34 (UTC).

| Model/configuration (all IDW: `k=5`, `epsilon=1e-6`) | Validation R² | Validation RMSE (KES/hour) | Final test R² | Final test RMSE (KES/hour) | Warm local p95 (ms) | Python allocation peak (bytes) | Research artifacts (bytes) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Train-fitted category mean | 0.003070 | 10,757.775 | 0.000926 | 10,403.768 | n/a | n/a | n/a |
| Baseline 53D, bigrams, block weights 1:1 | 0.729001 | 5,608.848 | 0.678648 | 5,900.409 | 16.847 | 238,622,132 | 10,427,157 |
| Unigram 53D | 0.728481 | 5,614.234 | **not opened** | **not opened** | 20.299 | 57,595,420 | 10,371,757 |
| Normalized-text 53D | 0.726509 | 5,634.586 | **not opened** | **not opened** | 17.259 | 156,324,770 | 10,427,156 |
| Metadata-half 53D, block weights 1:0.5 | **0.732678** | **5,570.670** | 0.676695 | 5,918.315 | 21.990 | 156,324,690 | 10,427,157 |

All four candidates replayed the validation request coordinates and neighbor
predictions after reload. **Metadata-half won by validation R² only**, an
improvement of 0.003677 R² over baseline, but had **worse** final-test R² and
RMSE than baseline (0.676695 vs 0.678648 and 5,918.315 vs 5,900.409).
Unigram and normalized-text lost on validation and were not tested on the final
holdout. **No configuration is promoted.** These figures do not establish
real-world mentor-rate performance, do not pass the deferred #81 mentor-pricing
gate, and do not represent the full authenticated API's #70 latency.

The validation-selected metadata-half model's per-industry breakdown includes
sparse categories rather than hiding them:

| Industry | Validation rows | Validation R² | Validation RMSE (KES/hour) | Test rows | Test R² | Test RMSE (KES/hour) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| data_ai | 261 | 0.751867 | 5,370.098 | 386 | 0.701793 | 5,454.991 |
| design_creative | 1,046 | 0.733972 | 5,580.830 | 1,502 | 0.653105 | 6,190.739 |
| devops_cloud | 50 | 0.598380 | 6,531.847 | 62 | 0.402108 | 8,186.414 |
| digital_marketing | 119 | 0.585102 | 6,258.060 | 180 | 0.533526 | 6,272.599 |
| general_tech | 248 | 0.716826 | 5,322.694 | 354 | 0.732766 | 5,251.867 |
| mobile | 82 | 0.774583 | 5,300.058 | 112 | 0.796040 | 4,237.536 |
| product_management | 18 | 0.528610 | 6,896.547 | 14 | 0.535202 | 6,159.323 |
| web_backend | 560 | 0.757077 | 5,492.972 | 780 | 0.712962 | 5,789.620 |
