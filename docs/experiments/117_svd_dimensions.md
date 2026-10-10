# #117 — SVD dimensions and peer-pricing trade-offs

**Status: completed local exploratory run, 2026-10-10.** Protocol below was written *before* candidate scoring. [Issue #117](https://github.com/tyejaedon/Price-Optimization-Model/issues/117), Milestone 9. Research only, no production artifact promotion or empirical mentor-pricing gate.

## Preregistered protocol (before inspecting #117 candidate scores)

- **Question:** Relative to the existing 50 text + 3 metadata coordinates, do 25, 75 or 100 latent SVD text components offer an informative *proxy-budget* accuracy gain without materially worsening peer-explanation stability, warm query cost or artifact size? No universal optimum or fixed improvement threshold is claimed; describe trade-offs and retain the 50D serving default unless a separately reviewed migration is justified.
- **Population and label:** Same dated `upwork_jobs` *posted budgets* as [#93](../M9_93_Inference_Safe_Benchmark.md); not paid mentor transactions. Input `data/processed/harmonized_marketplace_corpus.parquet` SHA-256 `da5432eec261e8b8aff66d046f276562a75d24b2106d61a9c189571e8725a5ca`, macro `data/processed/macro_lookup_table.json` SHA-256 `30d8d6b351770b0a85287c4b2791f0549735a8f6b6eac5c914109b3c7782f901`. #93 reported 22,677 input rows, 130 undated profiles and 6,049 invalid/out-of-bounds jobs excluded, with 16/2/3 repeated descriptions removed from train/validation/test. Train 10,703, validation 2,384, test 3,390. Benchmark fails on missing/naive time, overlapping IDs or empty windows; same train-only industry metadata is recomputed for each candidate. The duplicate-description purge is not verified source-event identity.
- **Frozen chronology:** Train through **2024-02-20T00:00:00+00:00**; validation after that through **2024-02-22T00:00:00+00:00**; test strictly after. These are the #93 cutoffs, *not* newly chosen based on #117 outcomes. #93 **already opened this snapshot's final test**, so any reused test scores are exploratory OOT comparisons, **not fresh blind confirmation**. Validate all candidates on validation, freeze the comparison before calculating their test scores, never select/reselect by test. A future independent dated snapshot would be needed for a blind confirmatory test.
- **Only variable:** Requested SVD text dimensions **25, 50, 75, 100**, yielding **28, 53, 78, 103** hybrid columns. Same train-only TF-IDF (12,000 terms, unigrams+bigrams, `min_df=1`, L2/sublinear TF), no dense normalization, SVD seed 42, bilateral alpha 0.5, three fitted metadata features, weights 1:1, train-only industry density, partitioned KD-Trees, `k=5`, epsilon `1e-6`, minimum partition 5 and standard fallback. Raw KES/hour IDW target, plus training-only category-mean comparator. No #94 supervised estimators, other text settings or target transformations.
- **Measures:** Raw-unit MAE, RMSE, R², bias and per-industry errors/counts; explained variance (context only). On the *same full validation request cohort*: mean top-5 peer Jaccard and same-rank fraction vs 50D, mean change in peer weights and shared-peer similarity, base-quote difference, fallback count/mismatch. Do not serialize peer IDs or fabricated listing IDs. Profile fixed spaced validation samples (warm text, KD-Tree/IDW, local NLP+metadata+IDW p50/p95), text/tree fit time, Python `tracemalloc` allocation peak (**not RSS**) and saved research-artifact bytes. Persist/verify finite dimensions and post-reload request-coordinate, peer-payload and quote parity. Hardware/versions and any infeasible candidate are recorded in the ignored JSON report. These local timings are not full authenticated HTTP or mobile RTT.
- **Decision:** Assess 50D as an engineering trade-off using validation error *and* peer, time and size costs; report uncertainty from one seed, sparse industries, previously opened test and time drift rather than declaring an optimum or using the deferred #81 quality gate. Any non-50D serving change needs a new issue for schema, manifest/index rebuild, train/serve parity, protected latency and rollback (#67/#70/#95).

The ignored aggregate-only report directory is `reports/m9_svd_dimensions_117/`. This Markdown record and the [experiment index](README.md) can be updated with results after the run; do not commit local data, serialized artifacts, individual predictions or peer IDs.

## Reproduce on this snapshot

Use a new empty ignored output directory per run. In PowerShell, from the repository root:

```powershell
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
python -m src.svd_dimension_benchmark --harmonized-parquet data/processed/harmonized_marketplace_corpus.parquet --macro-lookup data/processed/macro_lookup_table.json --validation-cutoff 2024-02-20T00:00:00+00:00 --test-cutoff 2024-02-22T00:00:00+00:00 --dataset-version local-proxy-job-budgets-2026-10-05 --output-dir reports/m9_svd_dimensions_117 --samples 40
python -m pytest -q tests/test_svd_dimension_benchmark.py tests/test_inference_safe_benchmark.py
```

`protocol_frozen.json` records the configuration before fitting; `validation_frozen.json` records validation comparisons before test evaluation; `benchmark.json` includes the exploratory test and per-industry aggregates. No deployable manifest is written.

## Local results, 2026-10-10 (posted job budgets, **not** mentor transactions)

The recorded SHA-256 values above matched the input files. Exclusions and counts matched #93 exactly: **10,703 train / 2,384 validation / 3,390 test**. Each candidate fitted the requested number of text coordinates and three metadata coordinates, yielded finite vectors, passed 40 post-reload request/peer/quote parity samples, and was retained as **research-only**. Category-mean validation MAE/RMSE/R² were 9,386.10/10,757.77/0.003070; exploratory test MAE/RMSE/R² were 9,063.47/10,403.77/0.000926. No candidate failed. The test values below use #93's **previously opened** window and were calculated only after `validation_frozen.json`; they are *not* an independent confirmation or selection criterion.

| SVD text + 3D | Validation MAE / RMSE (KES/h) | Validation R² / bias (KES/h) | Exploratory test MAE / RMSE (KES/h) | Exploratory test R² | SVD variance sum | Val peer Jaccard vs 50D | Warm local p95 (ms) | Python peak (MiB) | Artifacts (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 25 + 3 | 3,657.15 / 5,583.24 | 0.731471 / -521.46 | 3,846.94 / 5,881.96 | 0.680655 | 0.128579 | 0.432486 | 22.57 | 227.57 | 5.48 |
| **50 + 3 (current)** | 3,664.68 / 5,608.85 | 0.729001 / -521.23 | 3,846.62 / 5,900.41 | 0.678648 | 0.176129 | 1.000000 | 23.75 | 149.08 | 9.94 |
| 75 + 3 | 3,612.75 / 5,507.22 | **0.738733** / -513.92 | 3,853.93 / 5,909.92 | 0.677612 | 0.209540 | 0.615689 | 20.55 | 149.08 | 14.41 |
| 100 + 3 | 3,635.47 / 5,537.00 | 0.735900 / -522.68 | 3,822.51 / 5,847.00 | 0.684439 | 0.236338 | 0.510829 | 30.44 | 149.08 | 18.87 |

Numbers are rounded for this record; exact values, validation/test per-industry MAE/RMSE/R², fit time, warm text/search p50/p95 and bytes are in ignored `benchmark.json`. All four scored better on validation than the category-mean comparator. **75D had the best validation error** (RMSE 101.63 KES/h less than 50D; R² +0.009732), but its exploratory test RMSE was 9.51 KES/h *worse* than 50D. The 100D exploratory test R² was highest, but using this already-viewed test to select 100D would be holdout-driven tuning.

### Peer explanations and partition coverage

Across the *same 2,384 validation requests*, retrieval stayed in the requested industry for all four dimensions (zero fallbacks/mismatches). Similarity is `1/(1+distance)`, not a human-readable SVD concept. All quantities below compare the same request with 50D, averaged without publishing peer IDs, text or individual rates:

| Text dimensions | Same-position top-5 fraction | Mean absolute IDW-weight change | Mean shared-peer similarity change | Mean absolute base-quote change (KES/h) |
| --- | ---: | ---: | ---: | ---: |
| 25 | 0.222735 | 0.116215 | 0.046886 | 1,366.52 |
| 50 | 1.000000 | 0.000000 | 0.000000 | 0.00 |
| 75 | 0.340017 | 0.078872 | 0.032097 | 920.72 |
| 100 | 0.253943 | 0.100420 | 0.056364 | 1,184.68 |

Industry diagnostics are retained in both validation/test aggregate JSON; validation counts and RMSE in KES/h illustrate why the aggregate does not represent every domain:

| Industry | Validation rows | 25D RMSE | 50D RMSE | 75D RMSE | 100D RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| data_ai | 261 | 5,515 | 5,444 | 5,213 | 5,178 |
| design_creative | 1,046 | 5,636 | 5,584 | 5,559 | 5,621 |
| devops_cloud | 50 | 6,239 | 6,775 | 6,186 | 6,122 |
| digital_marketing | 119 | 5,839 | 6,360 | 6,080 | 6,066 |
| general_tech | 248 | 5,244 | 5,445 | 5,308 | 5,419 |
| mobile | 82 | 5,363 | 5,398 | 5,172 | 5,361 |
| product_management | **18** | 6,459 | 6,805 | 6,496 | 6,409 |
| web_backend | 560 | 5,545 | 5,504 | 5,450 | 5,414 |

**Costs and uncertainty:** Run on Windows 11, AMD64 Family 25 Model 80, Python 3.13.2, NumPy 2.5.3, scikit-learn 1.9.0, with `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1`. Seed 42; **one** text fit per dimension, fixed candidate order 25→50→75→100; 40 warmed, evenly spaced validation requests for timings. Text fit was approximately 67/56/56/45 s and tree fit 0.61/0.66/0.48/0.82 s for 25/50/75/100D; no monotonic training-time conclusion follows from a single order. Warm text p95 was 17.80/20.82/16.99/26.93 ms and search/IDW p95 was 2.77/2.15/1.75/2.87 ms. The 75D local p95 being lower than 50D here is **not** a reliable latency win: sample size is small, workloads and tracing affect timing, there are no repeats/intervals, and none of these are authenticated-HTTP measurements. The 25D first-fit Python allocation peak was higher than subsequent candidates, likely order/tracing-sensitive; it is **not** evidence that fewer dimensions use more process RSS. Sparse industries (especially 18 product-management validation rows), repeated-description heuristics, proxy country assumptions and time drift add uncertainty.

**Measurement correction:** An initial dry run rejected 25D/100D reload parity because two/one sampled peer payloads, respectively, differed by a rounded last decimal. The peer IDs/order and base quotes were unchanged; the discrepancy arose from request-coordinate differences below `5e-8`. The final run requires identical peer IDs/order, routing and cent-rounded quotes, with at most `2e-6` numerical tolerance on six-decimal peer distance/weight/similarity fields. The corrected run passed all four candidates. This is a numerical comparison fix, not permission to hide changed peers.

**Decision:** Keeping **50D is a reasonable *compatibility and explanation-continuity* engineering choice**, not a demonstrated optimum on proxy error, runtime or memory. 25D has slightly lower validation error and smaller artifacts but substantial peer churn; 75D has the best validation error but also churn and ~45% larger artifacts, without improvement on the already-opened test; 100D is ~90% larger than 50D and has mean top-five Jaccard 0.51 vs 50D, while its test improvement is exploratory only. Do **not** promote any candidate or change the deployed 53D schema. Replicate on another independent, dated proxy snapshot and separately review schema/artifact/latency migration if a different dimension remains worthwhile; verified paid mentor labels would be needed to evaluate actual mentor-price accuracy. No `R² >= 0.75` quality gate is reinstated.

## Follow-up: retrospective rolling sensitivity (#117, no new data)

**Registered after the first #117 results were viewed, before this follow-up run.** This is an explicitly *exploratory* robustness check, not a new independent test or a post-hoc 95%-confidence winner. The input and macro SHA-256 are unchanged. By inspecting **only publication-date counts**, we found very few jobs before February 13; the five daily validation windows below were chosen to have meaningful coverage, not from their price labels or scores. They end by February 20, before #93's previously viewed validation (February 20–22) and test (after February 22). Do not score either #93 holdout again in this follow-up.

- Expand training through midnight UTC on **February 15, 16, 17, 18 and 19, 2024**; validate on the immediately following, non-overlapping one-day window ending midnight UTC on February 16, 17, 18, 19 and 20 respectively. Ties stay on the training side. Use #93's dated `upwork_jobs` eligibility, post-arbitrage bounds and earliest-description deduplication over earlier records; compute industry saturation and density *from each training window only*. Profile and score only the eligible, deduplicated earlier jobs.
- Compare **25, 50 and 75** text components (+3 metadata) on identical jobs with SVD seeds **42 and 7**, refitting text, metadata scaler and trees on training only per window and seed. Keep TF-IDF, alpha, IDW, `k=5`, weights and fallback fixed. 100D remains recorded in the first study but is outside this focused 25/50/75 robustness check; its earlier results are not erased. No rates, IDs, future text or target-derived features enter the query coordinates.
- For every window/seed/dimension report raw-KES MAE, RMSE, R², per-industry counts/errors, neighbor Jaccard/rank/weight vs the *same-window, same-seed* 50D baseline, reload parity, text/tree fit time, 20 warmed, spaced local text/search/query p50/p95 samples and research artifact size. Include failed candidates. Aggregate *paired* job-level MAE and RMSE differences vs 50D across **disjoint validation days**, with a seeded date-block bootstrap interval for the paired MAE difference. Keep per-job residuals, source IDs, text and peer IDs in memory only; commit aggregate-only results.
- Interpret day-block intervals **descriptively**: five adjacent dates, nested training sets, proxy budgets and already viewed outcomes do not yield independent confirmation. SVD seeds measure algorithmic variability, not additional observations; report results separately by seed, not as ten independent test windows. No minimum practical improvement threshold was declared: weigh observed error, explanation shifts, noisy timing and bytes *after* inspecting all outcomes, explain the chosen trade-off or record an inconclusive engineering choice. Never call the smallest numerical MAE a universally or statistically proven winner.

Run from PowerShell with the same ignored local inputs, using a fresh output directory:

```powershell
$env:OPENBLAS_NUM_THREADS='1'; $env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
python -m src.svd_rolling_benchmark --harmonized-parquet data/processed/harmonized_marketplace_corpus.parquet --macro-lookup data/processed/macro_lookup_table.json --dataset-version local-proxy-job-budgets-2026-10-05 --output-dir reports/m9_svd_rolling_117 --samples 20
python -m pytest -q tests/test_svd_rolling_benchmark.py tests/test_svd_dimension_benchmark.py
```

The runner rejects timestamp-naive data and, for this known input SHA-256, any retrospective validation ending after February 20. It freezes the configuration before fitting, writes only aggregate-only JSON, deletes temporary model binaries, and makes no production parameter/manifest change.

### Local follow-up result, 2026-10-10 (retrospective, not a new blind test)

The ignored `reports/m9_svd_rolling_117/benchmark.json` matched the original dataset/macro SHA-256 values above. Of **14,834** jobs published through February 20, **4,115** failed the fixed post-arbitrage rate rule and **16** repeated descriptions were removed, leaving **10,703** eligible distinct earlier jobs. Five non-overlapping validation days contained **519 / 1,970 / 1,382 / 1,258 / 2,213 = 7,342** jobs; their expanding training windows contained **3,361 / 3,880 / 5,850 / 7,232 / 8,490** jobs. All **30** dimension × seed × window candidates passed finite-vector and sampled request/reload/peer/quote parity. No #93 validation or final-test rows were scored, and no individual predictions, texts or peers were persisted.

| SVD seed | Text dimensions | Pooled validation MAE (KES/h) | Paired MAE change vs same-seed 50D (KES/h) | Pooled RMSE / change vs 50D (KES/h) | Descriptive 95% day-block interval for MAE change | Days with lower MAE than 50D |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 42 | 25 | 4,028.59 | **+21.86** | 6,035.25 / +44.71 | [-6.51, 38.94] | 1/5 |
| 42 | **50** | 4,006.72 | 0 | 5,990.54 / 0 | [0, 0] | baseline |
| 42 | 75 | **3,994.58** | **-12.14** | 5,982.97 / -7.57 | [-22.93, 0.81] | 4/5 |
| 7 | 25 | 4,027.69 | **+29.94** | 6,032.52 / +41.55 | [-16.62, 60.72] | 2/5 |
| 7 | **50** | **3,997.76** | 0 | 5,990.97 / 0 | [0, 0] | baseline |
| 7 | 75 | 4,018.54 | **+20.78** | 6,016.49 / +25.52 | [-2.88, 50.94] | 2/5 |

**Negative** paired change favors the candidate; positive favors 50D. The five individual validation MAEs (KES/h) show the reversal instead of hiding it inside a pooled number:

| Validation day (2024 UTC) | 42: 25 / 50 / 75D | 7: 25 / 50 / 75D |
| --- | --- | --- |
| Feb 15 | 5,192.92 / 5,185.46 / 5,214.21 | 5,184.29 / 5,170.96 / 5,248.78 |
| Feb 16 | 4,126.85 / 4,082.21 / 4,052.52 | 4,131.70 / 4,051.34 / 4,112.37 |
| Feb 17 | 4,103.68 / 4,129.85 / 4,113.56 | 4,127.29 / 4,143.97 / 4,136.79 |
| Feb 18 | 3,844.71 / 3,819.53 / 3,817.08 | 3,800.83 / 3,823.56 / 3,820.69 |
| Feb 19 | 3,725.68 / 3,692.60 / 3,683.58 | 3,730.63 / 3,682.63 / 3,685.11 |

The reported MAE/RMSE pools weight **distinct validation jobs** across days; seed 7 is a second fitting run on the *same* jobs, not 7,342 additional observations. Each bootstrap resamples **five calendar days** as blocks, with the same jobs/seed paired across candidates. All challenger intervals include zero even as a descriptive measure; these small, adjacent, previously viewed proxy days with nested training sets cannot establish statistical superiority or real mentor-rate accuracy. Full per-window/per-industry error and sample-count aggregates are in the ignored JSON. `product_management` has only **2–12** validation jobs per day, so its day-specific R²/error is especially unstable.

**Explanations/resources:** Weighted across validation requests, 25D's top-five peer Jaccard vs 50D was **0.483/0.488** (seeds 42/7), with mean absolute base-quote changes **1,322/1,309 KES/h**; for 75D these were **0.650/0.649** and **915/917 KES/h**. 25D research artifacts were **3.64–4.93 MiB**, vs **6.63–8.94 MiB** at 50D and **9.61–12.96 MiB** at 75D, for the *same training window*. Twenty warmed local query timings per candidate/window are recorded, but their p95 ranges overlap and are noisy; do not claim a latency winner or an authenticated-HTTP timing improvement. No repeated process-RSS measurement was made.

**Failure and correction:** The first attempted run stopped in window 2/seed 7 when a 50D reload parity check found a **0.01 KES/h cent-rounding change** despite identical peer order and <`5e-8` coordinate differences. The stored offline bilateral factor differed slightly from the factor reconstructed from the frozen macro lookup at request time. The runner now constructs *every* held-out coordinate through the request-time country/metadata transform before prediction; it retains the strict quote/peer parity assertion. This correction changes validation-coordinate construction relative to the first #117 study. Re-running all windows with the correction passed all candidates; the two studies are not a single frozen blind comparison.

**Decision from this dataset:** There is **no statistically confirmed dimension winner** and no consistent proxy-error gain from switching to 25D or 75D. 25D reduces artifact bytes substantially but has higher pooled MAE/RMSE for *both* seeds and substantial peer changes. 75D improves MAE by only **12.14 KES/h** on seed 42 but worsens it by **20.78 KES/h** on seed 7, uses larger artifacts and changes retrieved peers. **Retain 50D as the current engineering choice based on error consistency and peer behavior, not on compatibility alone or an alleged universal optimum.** Size savings could motivate a *separate* 25D product-policy choice, but this experiment does not show it is the more accurate peer-pricer. No serving artifact, gate or schema is changed; any migration requires its own issue and review.
