# #120 — fixed-53D text preprocessing sensitivity

**Status: #93-hash data not run; separately rebuilt local snapshot measured on validation (2026-10-13).** [Issue #120](https://github.com/tyejaedon/Price-Optimization-Model/issues/120), Milestone 9. Research-only; no serving defaults, models or protected endpoint changed. The protocol and new-snapshot amendment below were committed before any #120 real-data outcomes.

## Frozen question and comparator

Does sparse TF-IDF **L1 rather than L2**, or **unit-normalized rather than raw post-SVD text**, improve validation raw-KES/hour job-*budget* error enough to justify retrieval/operational trade-offs? Neither variable is a supervised target transformation. The current 12,000-token vocabulary cap's exact rationale is not established. `min_df=1` and the cap stay fixed: no measured training vocabulary saturation, OOV or resource pressure on an eligible dated snapshot here justifies adding another alternative *after seeing results*. Any later cap/min_df study needs a new preregistration.

Historical [#38](https://github.com/tyejaedon/Price-Optimization-Model/pull/45) explored a **smaller stratified** 25/50D example (50D `(1,3)` normalized yielded validation R² 0.566696 / test R² 0.578518 on that older split). It is not a comparator on this cohort. The [#93 dated job-budget run](../M9_93_Inference_Safe_Benchmark.md#local-run-2026-10-05-aggregate-exploratory-proxy-budgets-only) used 50+3D: baseline validation R² 0.729001 / RMSE 5,608.848 KES/h and normalized-text validation R² 0.726509 / RMSE 5,634.586. The normalized-text candidate's test was **not opened** in #93, but that snapshot's final window *was* opened for other models. These are **prior #93 results, not #120 results**. [#117](117_svd_dimensions.md) studied SVD dimension changes separately and retained 50D for error consistency/peer behavior, not proven optimality.

## Protocol fixed before candidate outcomes

- **Inputs/provenance:** Reuse #93's immutable local `data/processed/harmonized_marketplace_corpus.parquet` (SHA-256 `da5432eec261e8b8aff66d046f276562a75d24b2106d61a9c189571e8725a5ca`) and `data/processed/macro_lookup_table.json` (SHA-256 `30d8d6b351770b0a85287c4b2791f0549735a8f6b6eac5c914109b3c7782f901`), **only if both hashes match**. The labels are harmonized posted Upwork job budgets in KES/hour, not observed mentor payments. The KE mentor country and USD/KES=130 anchor are assumptions, not observed mentor/client pairs. No target-derived fields enter coordinates. Rebuilding from raw files is not equivalent to recovering the hashed snapshot.
- **Population and exclusion:** Use #93's `_split_population`: `upwork_jobs` only, finite post-arbitrage rates 500–35,000 KES/hour, mandatory timezone-aware observations, chronological description deduplication, disjoint record IDs, train-derived saturation/density. On that historical snapshot, #93 found 22,677 inputs, 130 other-source rows, 6,049 out-of-bounds/invalid jobs, 16/2/3 repeated descriptions purged, yielding 10,703 train / 2,384 validation / 3,390 test. These are **historical #93 counts**, not confirmed #120 counts; reject missing/changed input rather than assuming they recur.
- **Frozen UTC windows:** train through `2024-02-20T00:00:00+00:00`; validation after that through `2024-02-22T00:00:00+00:00`; **do not score the previously opened final test**. Missing/naive observation timestamps fail closed. No blind test is available without a genuinely independent later snapshot.
- **One-variable-at-a-time candidates:** (1) `baseline_l2_raw`: sparse L2, no post-SVD normalization; (2) `sparse_l1`: sparse L1 **only**; (3) `post_svd_unit`: post-SVD unit vectors **only**. All use sublinear-TF 12,000 max features, `(1,2)` n-grams, `min_df=1`, 50-component TruncatedSVD/seed 42, 3 train-only-scaled metadata coordinates, alpha 0.50, text:metadata weights 1:1, partitioned KD-Trees, `k=5`, IDW epsilon `1e-6`, minimum partition 5, unchanged fallback. No L1+unit combination, grid, dimension sweep or altered production artifacts.
- **Readout:** Validation raw-KES/h MAE/RMSE/R²/bias and per-industry counts/errors; fitted vocabulary, train/validation OOV n-gram fraction and zero sparse/dense rows, SVD explained variance (not predictive proof), mean same-request top-5 Jaccard/rank/IDW weight/shared-peer similarity/base-quote change and fallback changes vs baseline. Training text/tree fit, validation batch transform, warmed local text/search/combined p50/p95 on 25 evenly spaced validation requests, peak Python `tracemalloc` bytes (**not process RSS**), saved research-only artifact bytes; verify 53 finite features and sampled coordinate/peer/quote parity after reload. No raw rows, individual predictions or peer IDs in reports.
- **Decision:** Describe validation error **and** peer/cost trade-offs, including failures. No numerical winner threshold was defensibly calibrated in advance, so **no automatic winner or deployment change**. Previously opened #93 test is not confirmation; paid mentor-price accuracy and real API/mobile latency remain unmeasured. If an independently reviewed serving change is later proposed, rebuild/pin text+metadata+index artifacts and verify online parity/latency under #67/#70.

## Execution / reproducibility

From the repo root, with the **original** hashed local processed files present, use a new ignored directory for each run:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m src.text_sensitivity_benchmark \
  --harmonized-parquet data/processed/harmonized_marketplace_corpus.parquet \
  --macro-lookup data/processed/macro_lookup_table.json \
  --validation-cutoff 2024-02-20T00:00:00+00:00 \
  --test-cutoff 2024-02-22T00:00:00+00:00 \
  --dataset-version local-proxy-job-budgets-2026-10-05 \
  --expected-parquet-sha256 da5432eec261e8b8aff66d046f276562a75d24b2106d61a9c189571e8725a5ca \
  --expected-macro-sha256 30d8d6b351770b0a85287c4b2791f0549735a8f6b6eac5c914109b3c7782f901 \
  --output-dir reports/m9_text_sensitivity_120 --samples 25
```

`protocol_frozen.json` is written before fitting or scoring, then aggregate `benchmark.json` records successes/failures; neither is committed. The CLI verifies both hashes *before* creating report output. Change the protocol in a reviewed record **before** running if an independently versioned snapshot is used; never substitute hashes after seeing outcomes. Environment versions/CPU/platform are recorded by the CLI. The runner never scores final test records.

## Outcomes / blockers (2026-10-13)

| Candidate | Real proxy validation MAE/RMSE/R²/bias | Industry / peer / OOV / variance | Fit, warmed latency, Python peak, bytes | Final test |
| --- | --- | --- | --- | --- |
| `baseline_l2_raw` | **Not run** | **Not run** | **Not run** | Not run; previously opened in #93 |
| `sparse_l1` | **Not run** | **Not run** | **Not run** | Not run |
| `post_svd_unit` | **Not run** | **Not run** | **Not run** | Not run; #93 validation is historical only |

The isolated worktree has raw CSVs but **no** `data/processed/harmonized_marketplace_corpus.parquet` or `data/processed/macro_lookup_table.json`. In particular, the WDI CSV required for the macro lookup is missing, so the original dated harmonized snapshot cannot be independently reconstructed and hash-verified here. Raw upstream CSVs alone do not establish that every eligible row has the required UTC observation timestamp. No original processed data was copied into Git; no real-data #120 fit/score, industry errors, timings, memory or artifacts are claimed. Synthetic chronological fixtures exercise fitting, OOV diagnostics, three candidate isolation, held-out/test isolation, finite 53D vectors and reload parity; they **are software checks, not empirical price evidence**. Retain production sparse L2 and unnormalized post-SVD defaults pending a properly versioned real-data run and review.

## Pre-outcome amendment: newly rebuilt local snapshot (2026-10-13)

The original **#93-hash** run above remains not run. A new, **different** ignored local snapshot was supplied in the *parent* worktree after this record was written; its inputs are read-only to this benchmark, and outputs remain under this isolated issue worktree. The operator reports rebuilding from existing local raw marketplace/cost data plus tracked portable WDI and M-Pesa reference fixtures (`tests/fixtures/portable/raw/World_Development_Indicators/` and `tests/fixtures/portable/raw/Mpesa_Tarrifs/`). The generated macro JSON may contain tariff reference entries, but tariff fees are **not** optimized or used as text inputs here. This provenance is operator-reported; no independent build log or byte-for-byte reconstruction of #93 is asserted. This newly rebuilt snapshot's different macro/target values **cannot be compared to #93 scores as if only text settings changed**.

- **Frozen *new* inputs:** parent ignored `data/processed/harmonized_marketplace_corpus.parquet`, SHA-256 `2cfd6e1585580ecfb5b13f59ad0167eee7ea0bce8716edff91590f9c5a46d48c` (13,423,173 bytes); parent ignored `data/processed/macro_lookup_table.json`, SHA-256 `127856c7acfe6d67ca3d094860b501b38d90b9f1dae825ee76239a30a9a704b8` (56,175 bytes). The runner checks both digests before writing a protocol or fitting. Recheck hashes after the run; if either changed, discard that run.
- **Eligibility/timing checked without scoring:** 22,677 rows (22,547 `upwork_jobs` with non-null dated UTC observations spanning 2023-12-02 19:07:53 to 2024-02-23 18:19:08, and 130 undated profiles excluded); 7,719 invalid/out-of-bounds jobs excluded; 14/2/3 repeated descriptions purged; 9,615 train, 2,131 validation, 3,063 **unscored** later-window jobs. Predeclared #93 chronological UTC cutoffs remain **2024-02-20T00:00:00+00:00** and **2024-02-22T00:00:00+00:00**; validation spans 2024-02-20 00:00:43 to 2024-02-21 02:12:50 UTC. Deduplication by normalized description is not a verified source-event identity.
- **Frozen comparison/method:** Exactly the three candidates, settings, metrics, seed, training-only fits, 25 evenly spaced warmed validation requests and descriptive no-automatic-promotion rule above. No cap/min_df expansion or sealed/blind-test claim. This is a **new local proxy-job-budget validation sensitivity**, not an independent paid mentor cohort or fresh final-test evaluation.
- **Environment before scoring:** Apple M1, macOS 27 arm64, Python 3.11.4, numpy 2.4.6, pandas 3.0.6, scikit-learn 1.9.1, scipy 1.17.1; `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`. The runner logs measured Python/system/library versions in its ignored report.
- **Pre-score interruption:** The first attempt wrote only `protocol_frozen.json`, then was stopped before any candidate result after the optional NLTK WordNet download failed SSL verification and per-token missing-corpus exceptions made preprocessing unreasonably slow. The missing-corpus fallback was made once-per-process, retaining its existing unchanged-token behavior; synthetic tests cover that case. No candidate scores were inspected, no settings/hashes/cutoffs were changed, and the incomplete local report directory is removed before retrying.
- **Second-attempt failure:** Baseline fitting/scoring completed, but the prior #117 profiling helper rejected its reload parity: a ~`2.1e-8` batch-vs-single SVD coordinate difference crossed a two-decimal quote rounding boundary for **one of 25** sampled validation requests (difference 0.01 KES/h, **zero** differing peer ranks). L1 and post-SVD unit candidates passed the old check, but without a valid baseline the partial run is rejected; no candidate validation error scores were used for selection. The helper now checks *original live single request* against *reloaded live single request*, still requires the same peers/quote, separately checks batch-vs-live peers and flags one-cent batch/live quote differences. Frozen candidates, cutoffs, input hashes, seeds and metrics remain unchanged; rerun all from a new empty ignored output directory.

From the issue worktree root, `PARENT` resolves to an **absolute** path for input arguments; the output remains local and ignored:

```bash
PARENT="$(cd ../.. && pwd)"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m src.text_sensitivity_benchmark \
  --harmonized-parquet "$PARENT/data/processed/harmonized_marketplace_corpus.parquet" \
  --macro-lookup "$PARENT/data/processed/macro_lookup_table.json" \
  --validation-cutoff 2024-02-20T00:00:00+00:00 \
  --test-cutoff 2024-02-22T00:00:00+00:00 \
  --dataset-version parent-local-rebuilt-proxy-2026-10-13 \
  --expected-parquet-sha256 2cfd6e1585580ecfb5b13f59ad0167eee7ea0bce8716edff91590f9c5a46d48c \
  --expected-macro-sha256 127856c7acfe6d67ca3d094860b501b38d90b9f1dae825ee76239a30a9a704b8 \
  --output-dir reports/m9_text_sensitivity_120_rebuilt_2026-10-13_rerun --samples 25
```

**New-snapshot results: not run yet at the time of this amendment.** Append the aggregate outcome, including failures, without rewriting the preregistration above.

## Rebuilt-snapshot results (2026-10-13; **exploratory posted job budgets only**)

All three candidates succeeded on the **same 9,615 train / 2,131 validation** rows. The 3,063 later-window records were used solely to establish eligibility/time counts; **no final-window text coordinates or error scores were evaluated**. Both parent input hashes still matched the frozen values after the run. Sampled reloaded live request coordinates, top-5 peers and rounded quotes matched the original live path for 25/25 requests per candidate. Baseline batch-vs-live scored the same peers but one of 25 sampled quotes differed by **0.01 KES/h** at a rounding boundary; L1 and normalized variants had no sampled cent mismatch. All fitted training/validation hybrid vectors were finite 53D. These research-only serialized copies are in ignored `reports/m9_text_sensitivity_120_rebuilt_2026-10-13_rerun/`, **not** the deployed artifact directory.

| Candidate (sole change vs baseline) | Val MAE / RMSE (KES/h) | Val R² / bias (KES/h) | Vocabulary / SVD variance | Val OOV n-grams / zero TF-IDF rows / zero SVD rows | Peer Jaccard / same-rank vs baseline | Warm local p50 / p95 (ms) | Python peak / saved bundle (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| L2 + raw post-SVD (baseline) | 5,258.80 / 7,038.27 | 0.552769 / -472.63 | 12,000 / 0.175336 | 32.6144% / 0 / 0 | 1.000000 / 1.000000 | 5.34 / 7.35 | 150.30 / 9.47 |
| Sparse L1 only | 5,166.03 / 7,036.58 | 0.552983 / -520.81 | 12,000 / 0.180692 | 32.6144% / 0 / 0 | 0.267277 / 0.130643 | 4.66 / 6.37 | 150.02 / 9.47 |
| Post-SVD unit only | 5,976.14 / 7,716.00 | 0.462492 / -92.24 | 12,000 / 0.175336 | 32.6144% / 0 / 0 | 0.504041 / 0.283060 | 5.01 / 6.69 | 150.02 / 9.47 |

The **training** OOV n-gram fraction was 32.2944% for all three (the 12,000-term cap removes in-training n-grams). Neither training nor validation had zero sparse/dense rows. OOV counts use fitted-vocabulary membership over the vectorizer's analyzed uni/bi-grams; they are not a fraction of wholly unseen descriptions. Explained variance is descriptive, **not** price-prediction validity.

| Industry | Train / validation rows | Baseline val MAE / RMSE / R² | L1 val MAE / RMSE / R² | Unit val MAE / RMSE / R² |
| --- | ---: | ---: | ---: | ---: |
| data_ai | 1,086 / 231 | 5,556.72 / 7,359.74 / .511247 | 5,056.25 / 6,776.01 / .585702 | 6,556.15 / 8,292.84 / .379459 |
| design_creative | 4,152 / 939 | 5,247.05 / 6,993.86 / .558767 | 5,200.55 / 7,053.60 / .551196 | 5,904.48 / 7,587.86 / .480634 |
| devops_cloud | 170 / 38 | 6,357.03 / 7,922.79 / .365469 | 6,046.07 / 7,496.06 / .431981 | 7,057.10 / 9,267.53 / .131790 |
| digital_marketing | 569 / 108 | 5,496.83 / 7,597.31 / .386161 | 5,128.97 / 7,400.30 / .417583 | 6,030.13 / 7,999.44 / .319459 |
| general_tech | 932 / 222 | 4,471.39 / 6,382.04 / .626746 | 4,593.22 / 6,846.30 / .570467 | 5,253.50 / 7,109.61 / .536791 |
| mobile | 278 / 72 | 5,330.29 / 7,261.84 / .527187 | 5,198.03 / 6,815.27 / .583551 | 6,305.98 / 8,274.60 / .386110 |
| product_management | 49 / 18 | 6,880.03 / 7,696.19 / .296632 | 6,290.16 / 7,710.33 / .294045 | 7,533.75 / 8,165.73 / .208191 |
| web_backend | 2,379 / 503 | 5,289.11 / 6,992.91 / .567847 | 5,301.46 / 7,094.76 / .555166 | 5,966.26 / 7,644.81 / .483518 |

Peer changes are substantial despite L1's small pooled error change: across **all 2,131** aligned validation requests, L1 vs baseline changed the mean base quote by 2,739.97 KES/h, mean absolute IDW weight by .145837 and shared-peer similarity by .141964; post-SVD unit changed them by 2,512.46 KES/h, .098698 and .142191. No fallback was triggered in any candidate. Aggregate comparisons contain no source record IDs or individual quotes.

With single-threaded BLAS on the stated machine, text-fit times were 8,680.55 / 8,344.95 / 8,168.48 ms; KD-Tree fits 206.21 / 194.65 / 200.83 ms; validation batch transform 2,350.89 / 2,213.61 / 2,271.01 ms (baseline/L1/unit). Across the same 25 evenly spaced **warmed** validation requests, text p95 was 5.89 / 5.30 / 5.56 ms and search p95 .94 / .64 / .76 ms; combined p95 is tabulated above. Peak values are Python `tracemalloc` allocations, **not** RSS; saved bytes were 9,926,957 / 9,926,956 / 9,926,956 respectively (include research-only macro/metadata/index copies). Timings are local research NLP+metadata+KD-Tree/IDW, not authenticated HTTP, mobile RTT or stable cross-machine speed claims.

**Interpretation / decision:** L1 reduces validation MAE by 92.77 KES/h but lowers RMSE by only 1.69 KES/h and raises R² just .000214; its lower MAE is not uniform across industries, and it changes most neighbor ranks. Unit normalization worsens MAE by 717.34 KES/h, RMSE by 677.73 KES/h and R² by .090277. Under the prespecified *descriptive trade-off* rule, neither alternative warrants promotion on this snapshot; retain production sparse L2 and raw post-SVD. The large OOV fraction could motivate a **separately preregistered** vocabulary/min_df study, not an after-the-fact candidate here. One rebuilt, provenance-limited job-budget snapshot, small categories (e.g. product_management 18 validation records), WordNet-unavailable fallback, known prior final-window exposure and drift prevent a statistical/causal winner, paid mentor-price validation or blind-test claims. No artifact was promoted and no #81 pricing gate was assessed.

## Pre-outcome NLTK resource amendment (2026-10-13)

The parent has now made **downloaded NLTK English stopwords and WordNet** available under ignored `data/nltk_data`. The run above used `FALLBACK_STOPWORDS` and unchanged tokens when corpus downloads failed SSL; it is a **different preprocessing-resource condition** from the intended NLTK-enabled pipeline. Retain its complete exploratory outcomes and failures above, but do **not** compare the two conditions as a single-variable text-setting experiment. Rerun **all three** previously frozen candidates on exactly the same input digests, eligibility, cutoffs, seeds, k/epsilon, 53D schema and 25 spaced warm samples. This is a resource-consistency rerun, not choosing a candidate because of its earlier scores; no final-test scoring or promotion.

- **Input fingerprints rechecked before rerun:** parent parquet SHA-256 `2cfd6e1585580ecfb5b13f59ad0167eee7ea0bce8716edff91590f9c5a46d48c`, parent macro JSON SHA-256 `127856c7acfe6d67ca3d094860b501b38d90b9f1dae825ee76239a30a9a704b8`. NLTK corpus ZIPs in parent ignored `data/nltk_data/corpora/`: `stopwords.zip` SHA-256 `48c0e52d8b52546e827f53761fb30300c0ab94f70660d28bd65ba0a86270946b`; `wordnet.zip` SHA-256 `cbda5ea6eef7f36a97a43d4a75f85e07fccbb4f23657d27b4ccbc93e2646ab59`. Extracted English stopword file SHA-256 `f6d005956f407dbc6ea32e5ff0c7e8e6f71488d3239b9023efdc7fc139d6375b`. The code now recognizes zipped WordNet without attempting a redundant network download; tests cover both zipped and unavailable corpora.
- **Resource readiness pre-score:** with `NLTK_DATA` set to that absolute parent directory, `WordNetLemmatizer` is available, English stopwords count is 198 and `sanitize_text("Dogs running through cities")` yields `"dog running city"`. These resources are local inputs; nothing is copied into the tracked repository or model service.
- **Frozen decision/readout:** same prespecified descriptive validation/peer/operational measures and no numerical winner/promotion threshold. New NLTK-enabled results must be labeled separately from the fallback run above. No #93 cross-snapshot comparison, no blind final test or paid mentor-price claim.

From the issue worktree root, resolve the parent to an absolute path and write **only** to a fresh, ignored issue-worktree report directory:

```bash
PARENT="$(cd ../.. && pwd)"
NLTK_DATA="$PARENT/data/nltk_data" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m src.text_sensitivity_benchmark \
  --harmonized-parquet "$PARENT/data/processed/harmonized_marketplace_corpus.parquet" \
  --macro-lookup "$PARENT/data/processed/macro_lookup_table.json" \
  --validation-cutoff 2024-02-20T00:00:00+00:00 \
  --test-cutoff 2024-02-22T00:00:00+00:00 \
  --dataset-version parent-local-rebuilt-proxy-2026-10-13-nltk \
  --expected-parquet-sha256 2cfd6e1585580ecfb5b13f59ad0167eee7ea0bce8716edff91590f9c5a46d48c \
  --expected-macro-sha256 127856c7acfe6d67ca3d094860b501b38d90b9f1dae825ee76239a30a9a704b8 \
  --output-dir reports/m9_text_sensitivity_120_rebuilt_nltk_2026-10-13 --samples 25
```

**NLTK-enabled results: not run at the time of this amendment.**

## Pre-outcome timing correction for NLTK-enabled rerun

The first NLTK-enabled run passed all three parity checks on the same frozen inputs and gave validation MAE/RMSE/R² of **5,269.85 / 7,036.57 / .552984** (baseline), **5,170.53 / 7,068.38 / .548934** (L1) and **5,985.10 / 7,729.14 / .460659** (unit). Its **first candidate** also lazily loaded the WordNet corpus *inside* the fit timer and Python allocation tracer (baseline fit 21.70 s / Python peak 230.64 MB vs L1 11.90 s / 145.67 MB), so that candidate-order resource setup confounds operational comparisons. Retain these observed validation scores as exploratory; do not select on them or compare their cold baseline timing to the warmed alternatives.

Before the final all-candidate repetition, preload the same NLTK corpora **once before any candidate timer/tracer**, without fitting vocabulary, reading rates or inspecting validation outcomes. Keep every candidate, hash, seed, cutoff, NLTK input, BLAS thread setting, accuracy/peer metric and 25 spaced warm request sample unchanged. Write into a *new* ignored `reports/m9_text_sensitivity_120_rebuilt_nltk_warmed_2026-10-13` directory using the identical command above with only `--output-dir` changed. Record both runs and compare within the uniformly warmed run only; the cold-corpus resource setup was not an experimental candidate.

## Uniformly warmed NLTK-enabled results (2026-10-13; **primary resource-consistent comparison**)

After the full rerun, the parquet, macro JSON, both NLTK ZIPs and extracted English stopword hashes **still matched** the predeclared digests. The population remained 9,615 training / 2,131 validation / 3,063 later-window eligibility-only jobs, with exactly the same UTC cutoffs. All three 53D candidates fitted successfully; their validation errors and peer aggregates matched the first NLTK-enabled run **exactly**, confirming that corpus warmup changed only measurement setup. No later-window text features or prediction errors were scored. The 25/25 sampled per-candidate original-live versus reloaded-live requests matched coordinates, peers and quotes; batch-vs-single quotes differed by one cent in **one L1 request only**, without any peer change. Reports and research artifacts remain ignored in `reports/m9_text_sensitivity_120_rebuilt_nltk_warmed_2026-10-13/`.

| Candidate (only setting changed from L2/raw) | Val MAE / RMSE (KES/h) | Val R² / bias (KES/h) | Vocabulary / SVD variance | Val OOV n-grams / zero sparse / zero SVD rows | Peer Jaccard / same-rank vs baseline | Warm local p50 / p95 (ms) | Python peak / saved (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| L2 + raw post-SVD (baseline) | 5,269.85 / 7,036.57 | .552984 / -499.29 | 12,000 / .178803 | 32.5336% / 0 / 0 | 1.000000 / 1.000000 | 4.52 / 8.75 | 139.06 / 9.47 |
| Sparse L1 only | 5,170.53 / 7,068.38 | .548934 / -586.03 | 12,000 / .182390 | 32.5336% / 0 / 0 | .273512 / .138339 | 4.41 / 6.72 | 138.92 / 9.47 |
| Post-SVD unit only | 5,985.10 / 7,729.14 | .460659 / -306.96 | 12,000 / .178803 | 32.5336% / 0 / 0 | .500421 / .288691 | 4.37 / 6.81 | 138.92 / 9.47 |

All candidates also had **32.0543%** training OOV analyzed uni/bi-grams, with zero training sparse/SVD zero rows. Validation OOV counts were 137,913 of 423,909 analyzed n-grams for each. Cap-excluded *training* terms count as OOV in this diagnostic; this is not 32% fully unseen descriptions. Explained variance is context, not evidence of price validity.

| Industry | Train / val rows | Baseline val MAE / RMSE / R² | L1 val MAE / RMSE / R² | Unit val MAE / RMSE / R² |
| --- | ---: | ---: | ---: | ---: |
| data_ai | 1,086 / 231 | 5,364.50 / 7,162.95 / .537036 | 5,018.23 / 6,728.14 / .591535 | 6,415.98 / 8,168.54 / .397922 |
| design_creative | 4,152 / 939 | 5,261.39 / 7,013.96 / .556227 | 5,257.18 / 7,173.87 / .535762 | 5,767.01 / 7,474.54 / .496031 |
| devops_cloud | 170 / 38 | 6,638.72 / 8,258.99 / .310474 | 5,982.45 / 7,675.19 / .404509 | 7,434.61 / 9,170.71 / .149835 |
| digital_marketing | 569 / 108 | 5,368.33 / 7,435.88 / .411969 | 5,190.78 / 7,512.38 / .399808 | 6,428.33 / 8,304.38 / .266587 |
| general_tech | 932 / 222 | 4,709.89 / 6,499.86 / .612838 | 4,668.31 / 6,893.02 / .564583 | 5,359.16 / 7,233.52 / .520504 |
| mobile | 278 / 72 | 5,288.84 / 7,209.50 / .533977 | 4,915.00 / 6,510.03 / .620018 | 6,583.65 / 8,620.47 / .333718 |
| product_management | 49 / 18 | 6,323.51 / 7,210.60 / .382590 | 6,033.86 / 7,248.28 / .376121 | 6,573.19 / 7,284.62 / .369850 |
| web_backend | 2,379 / 503 | 5,324.31 / 7,028.10 / .563486 | 5,240.36 / 7,022.86 / .564137 | 6,159.22 / 7,833.44 / .457715 |

On all **2,131** validation requests, L1's mean same-request top-5 Jaccard was .273512 and identical-rank fraction .138339; mean absolute changes were .144759 in IDW weight, .139028 in shared-peer similarity and 2,713.18 KES/h in base quote. Unit output had Jaccard .500421 / rank .288691, and changes .099405 / .139739 / 2,449.25 KES/h respectively. Neither produced a fallback or a changed routed partition. No peer IDs/individual quotes are published.

The warmed training text-fit times were **12,224.66 / 12,194.79 / 12,952.24 ms**, KD-Tree fits **166.45 / 183.56 / 167.47 ms**, and validation batch transforms **3,120.97 / 3,403.07 / 3,267.69 ms** (baseline/L1/unit). On the same 25 spaced warmed validation requests, text p95 was **7.48 / 5.94 / 5.96 ms**, search p95 **.61 / .52 / .57 ms**, and combined p95 is tabulated above. Saved research bundle bytes were **9,934,761 / 9,934,761 / 9,934,760**. `tracemalloc` peaks are Python allocation peaks (**not RSS**), and single-machine timings vary with runtime cache/order; apparent p95 advantages are not proven latency gains for the protected HTTP route or mobile devices.

**Decision and limits:** On this new dated *posted budget* snapshot, L1 lowers validation MAE by **99.32 KES/h** but raises RMSE by **31.80 KES/h** and lowers R² by **.004050** versus baseline; improvement varies across industries and peer ranks change markedly. Unit normalization worsens MAE by **715.25 KES/h**, RMSE by **692.57 KES/h** and R² by **.092325**. Under the prespecified descriptive error/peer/cost rule, **retain sparse L2 and raw post-SVD**; no alternative is promoted. The high OOV fraction may motivate a separately preregistered cap/min_df study, not post-hoc changes in this one. This is one rebuilt proxy snapshot with operator-reported provenance, small categories (product_management 18 validation rows), already-exposed prior time window, no verified mentor transactions, no independent confirmatory blind test, and no statistical optimum. Neither #93 cross-snapshot scores nor fallback-resource scores above are treated as one-variable comparisons with this NLTK-enabled run.
