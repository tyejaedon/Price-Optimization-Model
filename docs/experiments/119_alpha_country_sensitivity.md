# #119 — Bilateral-alpha and country-anchor sensitivity

**Status: separately hashed 2026-10-13 rebuilt local proxy snapshot evaluated; original #93 snapshot unavailable.** Milestone 9, research only. [Issue #119](https://github.com/tyejaedon/Price-Optimization-Model/issues/119); [assumption register](assumptions.md). No production defaults, model schema, data, tariffs or serving artifacts change.

## Predeclared protocol (before any #93 cohort candidate outcome)

- **Question and interpretation:** How does changing the *assumed* bilateral PPP/cost-index exponent affect factor, constructed job-budget target, peer quote, fee-free negotiation corridor and peer identity? The 0.50 default is a convention, **not** an estimated optimum. No independent paid mentor transaction or verified mentor–client country pairing exists; alpha-derived labels cannot identify a real-price optimum. **Do not compute/select by R², RMSE or label accuracy against alpha-derived targets.**
- **One variable and controls:** Sweep alpha **0, 0.25, 0.50, 0.75, 1** in that order, using 0.50 as the reference. Keep KE as the *assumed* offline mentor anchor, USD/KES conversion 130, source-country-to-client proxy mapping and fallback rules, macro lookup, 50D unnormalized SVD (seed 42, 12k max TF-IDF terms, unigram+bigrams, min_df=1), 3D train-fitted MinMax metadata, equal text/metadata block weights, industry KD-Trees, k=5, quadratic IDW epsilon=1e-6, fallback minimum five, and corridor rule fixed. Same-country KE→KE is the zero-factor/zero-target-change control; its **predicted** quote need not be constant because other training peers' constructed labels change.
- **Frozen inputs:** Exactly [#93's 2026-10-05 dated posted-job-budget snapshot](../M9_93_Inference_Safe_Benchmark.md#local-run-2026-10-05-aggregate-exploratory-proxy-budgets-only): parquet SHA-256 `da5432eec261e8b8aff66d046f276562a75d24b2106d61a9c189571e8725a5ca`, macro JSON SHA-256 `30d8d6b351770b0a85287c4b2791f0549735a8f6b6eac5c914109b3c7782f901`. Require both exact hashes by default. On that snapshot #93's precomputed alpha=0.50 post-arbitrage eligibility `[500,35000]` KES/hour, chronological cutoffs **2024-02-20T00:00:00+00:00** and **2024-02-22T00:00:00+00:00**, repeated-description purge and train-only industry frequencies yield **10,703 train / 2,384 validation / 3,390 test**. Do **not** reselect eligibility for each alpha. Require original alpha=0.50 harmonized labels to match recomputation from the untouched pre-arbitrage `hourly_rate`; reject mismatches. Label is a posted job **budget**, not a paid mentor rate. `source_country` is source metadata, **not a verified client location**; missing/unknown source resolves to KE, missing macro record uses KE.
- **Train-only fit and inference:** Fit TF-IDF/SVD once on the frozen training descriptions; recompute each candidate's **training and request factors** from original country roles + macro; recompute each training/validation target as round-to-cents(`hourly_rate * factor`) instead of reusing stale 0.50 labels. Fit each candidate's metadata scaler on its training rows only; build KD-Trees and aligned rates from its training rows only. Transform unchanged validation request descriptions and the candidate's consistently recomputed factor using the training fits. Verify 53D vectors, request/peer/quote parity after loading independently serialized **research-only** artifacts, and sampled warm local inference p50/p95. Record per-split pair counts, source-normalization and macro fallback counts, overall **and per-country-pair** validation factor/constructed-target absolute change, quote and corridor-bound changes, corridor failure count, top-five Jaccard/rank/weight changes, same-country controls and scenario-out-of-bounds counts. **No individual IDs, descriptions, records, predictions or raw datasets in committed output.**
- **Holdout and decision:** #93 and #117 already opened this exact snapshot's final test; there is **no new sealed test**. The runner checks chronology and country coverage for the test cohort but intentionally computes **no test predictions or error scores**. Summarize all five scenarios and failures descriptively, without selecting a winner or claiming a causal effect on mentor pay. Request-time latency is local warmed NLP+scaler+KD-Tree/IDW, **not** authenticated HTTP, Firestore or mobile RTT. Changing deployment alpha would require a separate reviewed production study and independent paid-rate/country provenance; this issue does not promote anything.

## Reproduction and output

Requires the *original hashed* dated parquet and macro JSON above at `data/processed/harmonized_marketplace_corpus.parquet` and `data/processed/macro_lookup_table.json`. From this checkout, choose a **new empty** ignored output directory per run:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m src.alpha_sensitivity_benchmark \
  --harmonized-parquet data/processed/harmonized_marketplace_corpus.parquet \
  --macro-lookup data/processed/macro_lookup_table.json \
  --output-dir reports/m9_alpha_sensitivity_119 --samples 25
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m pytest -q -p no:cacheprovider tests/test_alpha_sensitivity_benchmark.py
```

The CLI rejects wrong SHA-256 values before touching output. `protocol_frozen.json` records hashes, cohort, candidates and fit policy **before** fitting; `benchmark.json` records each success/failure and aggregate-only outcomes. Research artifact directories are under ignored `reports/`, with **no deployable manifest**. `--allow-other-snapshot` requires an explicit `--dataset-version` and prominently marks the report `other_snapshot_not_93`; **never** describe those runs as #93 reproduction. The command does not silently rebuild the old cohort from newer raw files.

## Newly rebuilt local snapshot: preregistered extension before scenario scoring (2026-10-13)

The original #93 hashed processed files remain unavailable. Separately, local raw job CSVs were combined with **tracked portable WDI and M-Pesa reference fixtures** to generate *new*, ignored processed inputs outside this issue worktree. This fixture-assisted macro reconstruction is **not the original #93 macro provenance**, and the raw inputs do not yield independently verified paid mentor prices. Only read these inputs; all research output goes under this issue worktree's ignored `reports/`.

- New parquet SHA-256 `2cfd6e1585580ecfb5b13f59ad0167eee7ea0bce8716edff91590f9c5a46d48c`, macro SHA-256 `127856c7acfe6d67ca3d094860b501b38d90b9f1dae825ee76239a30a9a704b8`. Both differ from #93. Version: `local-rebuilt-proxy-2026-10-13-portable-fixtures`.
- **Pre-score inspection only:** 22,677 rows (22,547 jobs, 130 undated profiles), all jobs timestamped. With #93's *previously documented* aware UTC cutoffs and 0.50-label eligibility/purge, 130 other-source rows and 7,719 post-factor out-of-bounds jobs were excluded; dedup removed 14/2/3 train/validation/test descriptions. Remaining **9,615 train / 2,131 validation / 3,063 test**, different from #93's 10,703/2,384/3,390. Train ended 2024-02-19 23:59:44 UTC; validation spans 2024-02-20 00:00:43 to 2024-02-21 02:12:50; test starts 2024-02-22 01:51:34. Country roles map to the frozen KE/source-country policy and recomputed 0.50 labels match input labels exactly on train + validation. Initial coverage: 133/89/99 distinct country pairs in train/validation/test; 320/87/149 same-country rows, 268/71/125 unknown-source→KE events and 80/20/26 missing-client-macro→KE events, respectively. **These are cohort/provenance checks, not model results.**
- Use **the same predeclared five alphas and fixed 50D+3D train-only fitting** described above, the same previously documented UTC cutoffs, and the **0.50 eligible cohort frozen before any candidate scoring**. Report all five scenarios including failures; no selection, validation accuracy or test predictions. The rebuilt snapshot draws on overlapping job source material and the #93 test window was already viewed; **neither a new blind test nor independent transaction validation** is claimed. Compare only within this newly rebuilt snapshot, not numerically against #93 scores. Local warmed times depend on machine and are not production SLAs.

Run only after confirming the two hashes above and using the parent checkout's **absolute** processed-input paths (not paths relative to this issue worktree):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m src.alpha_sensitivity_benchmark \
  --harmonized-parquet /absolute/parent/worktree/data/processed/harmonized_marketplace_corpus.parquet \
  --macro-lookup /absolute/parent/worktree/data/processed/macro_lookup_table.json \
  --allow-other-snapshot --dataset-version local-rebuilt-proxy-2026-10-13-portable-fixtures \
  --output-dir reports/m9_alpha_sensitivity_119_rebuilt_20261013 --samples 25
```

### Preregistered environment correction before rerun (2026-10-13)

The first rebuilt-snapshot run below used the NLP module's fallback stopwords and token normalization because NLTK's stopwords and wordnet downloads failed SSL verification. This still passed research reload parity, but is **not the intended NLTK-resource text representation**. The missing resources are now available in the parent checkout's ignored `data/nltk_data` (NLTK 3.10.3; stopwords English file SHA-256 `f6d005956f407dbc6ea32e5ff0c7e8e6f71488d3239b9023efdc7fc139d6375b`; wordnet ZIP SHA-256 `cbda5ea6eef7f36a97a43d4a75f85e07fccbb4f23657d27b4ccbc93e2646ab59`). The resource smoke check returned 198 stopwords and lemmatized “payments” to “payment”. **Before viewing the corrected run**, freeze the same rebuilt parquet/macro hashes, same 0.50 eligibility, country roles and cutoff cohort, five alpha candidates, text/metadata dimensions, seeds, k/IDW, 25 timed validation samples and no-target-accuracy/no-test policy. The *only* environment correction is supplying intended NLP corpora through `NLTK_DATA`. Save the rerun to its own ignored directory; retain the initial fallback report and disclose both runs, without choosing an alpha on either.

```bash
NLTK_DATA=/absolute/parent/worktree/data/nltk_data OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m src.alpha_sensitivity_benchmark \
  --harmonized-parquet /absolute/parent/worktree/data/processed/harmonized_marketplace_corpus.parquet \
  --macro-lookup /absolute/parent/worktree/data/processed/macro_lookup_table.json \
  --allow-other-snapshot --dataset-version local-rebuilt-proxy-2026-10-13-portable-fixtures \
  --output-dir reports/m9_alpha_sensitivity_119_rebuilt_20261013_nltk --samples 25
```

## Original #93 snapshot: unavailable, not run (2026-10-13)

| Scenario | #93 validation factor/target/corridor/peers | Reload and local latency | Status |
| --- | --- | --- | --- |
| 0 | Not run | Not run on #93 | Blocked: original hashed inputs unavailable |
| 0.25 | Not run | Not run on #93 | Blocked: original hashed inputs unavailable |
| 0.50 control | Not run | Not run on #93 | Blocked: original hashed inputs unavailable |
| 0.75 | Not run | Not run on #93 | Blocked: original hashed inputs unavailable |
| 1 | Not run | Not run on #93 | Blocked: original hashed inputs unavailable |

The isolated worktree lacks **both original #93** hashed inputs. Available raw CSVs do not include the original WDI PPP source CSV; the newly rebuilt fixture-assisted macro/parquet **cannot** reproduce those historical SHA-256 values or #93's cohort. The synthetic fixtures exercise consistent label/factor recomputation, fallback/same-country controls, train-only fit, reload parity, hash and provenance guards; **their results are not #93 findings or validated mentor prices**. Only restore the two original matching, dated, ignored inputs from a trusted prior local snapshot to reproduce #93. A fresh independently sourced mentor-payment cohort and verified country roles are needed to decide real pricing; #91/#118 make that research non-blocking for M10–M14.

## New reconstructed snapshot: initial NLP-fallback exploratory findings (2026-10-13)

The two **new** hashes in the preregistered extension matched the local inputs at execution. `reports/m9_alpha_sensitivity_119_rebuilt_20261013/protocol_frozen.json` records the five candidates and 9,615/2,131/3,063 cohort **before model fitting**; ignored `benchmark.json` retains full aggregate results, country-pair counts, per-pair mean sensitivity, environment, and failures. All five candidates succeeded; none was selected for real-world pricing. **No R²/RMSE, independently measured paid mentor labels or final-test prediction was used.** Numbers below use only the same 2,131 validation requests on this *new* snapshot, compared with its own 0.50 baseline; absolute changes are averages, not estimates of error against real payments. Factor is unitless; rates, quotes and corridor bounds are KES/hour.

| Alpha | Mean factor | Mean absolute Δ factor | Mean absolute Δ constructed target | Mean absolute Δ base quote | Mean absolute Δ corridor min / max | Mean top-5 peer Jaccard | 0.50-eligible train / validation targets now outside bounds |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1.829 | 5.462 | 11,612.04 | 11,146.81 | 8,431.31 / 15,882.65 | 0.632 | 39 / 13 |
| 0.25 | 3.573 | 3.697 | 7,822.62 | 7,585.03 | 5,704.99 / 10,975.97 | 0.790 | 20 / 7 |
| **0.50 reference** | 7.257 | 0 | 0 | 0 | 0 / 0 | 1.000 | 0 / 0 |
| 0.75 | 15.115 | 7.865 | 16,477.60 | 16,106.10 | 11,638.86 / 24,579.52 | 0.836 | 4,186 / 963 |
| 1 | 32.045 | 24.800 | 51,670.61 | 50,299.89 | 34,329.94 / 82,153.13 | 0.703 | 6,353 / 1,385 |

**Country and corridor controls:** Validation includes **89 KE→source-country pairs**; 87 requests are KE→KE. The raw source value is *not a verified client location*. Validation has 71 unknown-source→KE substitutions and 20 missing-client-macro→KE substitutions; corresponding training counts are 268 and 80, and previously opened test counts (coverage only) are 125 and 26. The **87 KE→KE** factors and constructed targets stayed exactly unchanged in all five scenarios; their mean absolute **quote** nevertheless changed by **1,543.68 / 1,152.82 / 0 / 3,959.03 / 21,555.98** KES/hour at alpha 0 / .25 / .50 / .75 / 1, because the retrained neighbor index also contains cross-country peers whose targets changed. All 2,131 corridors were defined for each candidate; no industry-index fallback or fallback mismatch occurred. Same-rank top-five fractions were 0.442 / 0.600 / 1.000 / 0.677 / 0.537, respectively. The per-pair aggregates and full factor/target/corridor/peer-overlap changes remain in ignored `benchmark.json`; **no row-level outcomes or peer IDs are published**.

**Engineering checks and uncertainty:** All five saved research-only text/scaler/index bundles passed **25 warmed request-coordinate, peer-explanation and cent-rounded quote reload-parity samples** per alpha. Their local NLP+scaler+KD-Tree/IDW p95s were **34.84 / 38.02 / 31.87 / 38.78 / 33.70 ms** in sweep order, with about **9.93 MB of serialized research artifacts per candidate** (decimal bytes, not process RSS). These are *single-order, 25-request* measurements, **not** protected HTTP latency or a reliable runtime ranking. Environment: macOS arm64, Python 3.11.4, NumPy 2.4.6, scikit-learn 1.9.1; `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`. NLTK stopwords and wordnet were unavailable; download attempts failed SSL verification, so the shared NLP fallback preprocessing was used consistently for all candidates/reloads. Text vocabulary/SVD fitted on train once; each candidate's metadata scaler and KD-Trees fitted on train only.

**Interpretation and decision:** Alpha 1 places **1,385 of 2,131 validation constructed labels** outside the original `[500,35000]` range even though the cohort was correctly frozen at 0.50; dropping these would confound scenarios. The magnitude and sign of factor/quote changes depend on KE anchoring, unverified country roles and fixture-assisted macro construction. Similarity/quote changes measure *scenario instability*, not predictive validity or a price optimum. Retain alpha=0.50 as the unchanged engineering default; **do not promote this rebuilt model or treat the observed mean changes as real paid mentor outcomes**. Independent, consented paid rates with verified bilateral country roles and a separate reviewed production change would be required to calibrate alpha.
