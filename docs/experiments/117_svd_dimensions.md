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
