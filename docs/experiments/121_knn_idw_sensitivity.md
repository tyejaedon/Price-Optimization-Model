# #121 — k/IDW epsilon and peer-evidence sensitivity

**Status: exploratory local run, 2026-10-13.** Research-only proxy job budgets in KES/hour; no verified mentor transactions, automatic artifact promotion, or change to the [deferred #81 gate](../Label_Provenance_Audit_91.md). The historical random-split k sweep and the earlier #93 chronological benchmark are **different cohorts/splits**; their scores are not a controlled comparison with this run.

## Frozen design (before candidate scoring)

- **Question:** Relative to the engineering default `k=5`, quadratic IDW `epsilon=1e-6`, how do k and epsilon alter proxy validation error, nearest-peer explanations, corridor dispersion, partition coverage, and local inference cost? Describe trade-offs without selecting a serving winner from proxy outcomes.
- **Population/label:** Dated `upwork_jobs` **posted budgets**, not mentor payments. Rebuild the ignored harmonized parquet from the available local Upwork raw input and tracked portable WDI/M-Pesa reference fixtures. The resulting input SHA-256 is `2cfd6e1585580ecfb5b13f59ad0167eee7ea0bce8716edff91590f9c5a46d48c` and macro SHA-256 is `127856c7acfe6d67ca3d094860b501b38d90b9f1dae825ee76239a30a9a704b8`. These differ from [#93's previously reported hashes](../M9_93_Inference_Safe_Benchmark.md). No conclusions are drawn by comparing their scores.
- **Eligibility/time:** Reuse #93's published UTC cutoffs, `2024-02-20T00:00:00+00:00` for train/validation and `2024-02-22T00:00:00+00:00` for validation/test; exclude undated profiles, post-arbitrage rates outside 500–35,000 KES/hour, and later repeated descriptions. Fail closed on missing/naive timestamps, empty windows and overlapping record IDs. Exact description deduplication is not verified event identity. The #93 calendar test window has already been opened; **do not score the test at all** in this sensitivity run. Validation is exploratory, not a newly sealed holdout.
- **Frozen representation:** Fit 12,000-term, unigram/bigram, `min_df=1`, sparse-L2/sublinear-TF TF-IDF, unnormalized 50D SVD (seed 42), alpha 0.50 three-column metadata scaler, density and partitioned KD-Trees **only on training rows**. Replay validation coordinates through the request-time country/metadata transform. Keep 1:1 text/metadata weights, exponent 2, minimum partition size 5, `general_tech` fallback and the existing fee-free corridor formula fixed; never optimize tariffs or corridor coefficients on budgets.
- **One-variable series:** Compare `(k,epsilon)=(5,1e-6)` against `(3,1e-6)` and `(10,1e-6)`; separately compare `(5,1e-8)` and `(5,1e-4)` to the same `(5,1e-6)` baseline. Report every candidate; no unconstrained grid. `protocol_frozen.json` is written before text/index fitting or candidate validation scores.
- **Measures/decision:** Validation raw-KES/hour MAE/RMSE/R², per-industry counts/errors, fallback/small-partition counts, shared-peer rank and Jaccard, mean absolute base/peer-dispersion/corridor-width differences vs k=5, exact-zero-distance synthetic probe, sampled post-reload request/peer/quote parity, warm search and local query p50/p95, fit time, Python allocation peak and research artifact bytes. Report descriptive effects, not a proxy-selected serving value. No individual texts, IDs, predictions or serialized models are committed.

Older [stratified/random-split M6 k results](../../tests/fixtures/portable/reports/model_evaluation/hyperparameter_results.csv) reported k=10 validation R² **0.563592** and RMSE **20,999.11**, on a different snapshot/split and with separately tuned settings; [#93's dated baseline](../M9_93_Inference_Safe_Benchmark.md) used k=5 and reported validation R² **0.729001** on *its* snapshot. Neither cross-study difference estimates the effect of changing k. The table below alone compares k on this fixed local cohort.

## Local result (2026-10-13, exploratory, no production change)

The newly rebuilt snapshot had 22,677 input rows: 130 other-source profiles and 7,719 jobs with invalid or out-of-bound post-arbitrage rates were excluded; repeated descriptions removed 14/2/3 rows in train/validation/test. The resulting windows had **9,615 train / 2,131 validation / 3,063 unscored test** jobs, with train ending Feb 19 23:59:44, validation Feb 20 00:00:43–Feb 21 02:12:50, and test starting Feb 22 01:51:34 UTC. Training industry sizes: data_ai 1,086; design_creative 4,152; devops_cloud 170; digital_marketing 569; general_tech 932; mobile 278; product_management 49; web_backend 2,379. Validation counts: 231/939/38/108/222/72/**18**/503 in that order. Per-industry MAE/RMSE/R² and sample sizes for **all five candidates** remain in ignored `benchmark.json`; the small product-management cohort limits interpretation. No candidate failed; no eligible industry needed fallback at k=3, 5 or 10. This does not test absent or tiny industries in production.

| Series, configuration | Validation MAE / RMSE (KES/hour) | R² | Peer Jaccard / shared-peer same-rank vs k=5 | Mean absolute base / corridor-width change (KES/hour) | Warm local query p50 / p95 (ms) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline k=5, eps=1e-6 | 5,269.85 / 7,036.57 | 0.552984 | 1.000 / 1.000 | 0 / 0 | 2.391 / 3.085 |
| k=3, eps=1e-6 | 5,563.03 / 7,502.35 | 0.491846 | 0.600 / 0.983 | 1,572.02 / 2,664.15 | 2.201 / 2.961 |
| k=10, eps=1e-6 | 5,120.90 / 6,770.84 | 0.586110 | 0.500 / 0.981 | 1,382.98 / 2,294.36 | 2.150 / 2.989 |
| k=5, eps=1e-8 | 5,269.83 / 7,036.57 | 0.552984 | 1.000 / 1.000 | 0.03 / 1.51 | 2.177 / 2.904 |
| k=5, eps=1e-4 | 5,271.04 / 7,036.44 | 0.553001 | 1.000 / 1.000 | 2.86 / 18.33 | 2.563 / 4.207 |

**Peer/corridor effects are not booking outcomes.** k=3/10 changed weighted peer dispersion by mean absolute 1,345.55/1,176.20 KES/hour; the two epsilon changes altered it by 0.76/9.25. With different k the top 3/5 or 5/10 peer sets overlap by construction; the shared peers' rank consistency is separately measured. Epsilon did not change the peer set/ranks. Synthetic exact-match checks used two *different-rate* zero-distance peers: k=3/5/10 with epsilon=1e-6 and k=5 with epsilon=1e-8 all returned finite **200.00 KES/hour**; epsilon=1e-4 returned **200.02**, with normalized weights. These are synthetic test inputs, not observed prices or guarantees of calibrated confidence.

**Resources/parity:** The one shared text fit took 24.22 seconds and the one KD-Tree build 0.17 seconds; 53D research artifacts totaled 9,934,597 bytes. Training Python allocation peak was 230,758,622 bytes (`tracemalloc`, **not RSS**). All five settings passed 25 sampled post-reload request-coordinate/peer/cent-rounded quote parity checks. Warm search-only p95 was 0.306/0.288/0.302/0.296/0.386 ms in table order; warm local NLP+metadata+search timings are in the table. One order of 25 samples on macOS arm64, Python 3.11.4, NumPy 2.4.6, scikit-learn 1.9.1, `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1` is **not** a reliable latency ranking or authenticated-API/mobile RTT. Source fixtures and NLTK corpora are local/ignored; no dataset or artifact is versioned in this PR.

**Decision:** Keep k=5 and epsilon=1e-6 as the current engineering defaults. k=10 had lower exploratory validation error but only 0.5 mean Jaccard with k=5, substantially different corridors and no independent paid-mentor label or new sealed final test. Tiny epsilon changes do not justify a serving migration either. A later change requires its own versioned artifact/config review, train/serve parity and protected endpoint profiling (#67/#70/#95); do not treat this proxy result as a model-quality gate.

## Reproduction

In a fresh checkout, populate ignored `data/raw/` with the local Upwork source and the tracked portable WDI/M-Pesa reference inputs, then regenerate the ignored parquet and macro lookup. Verify the hashes above **before claiming the table is reproduced**; a different upstream snapshot is a new cohort. With the required Python dependencies, NLTK corpora and a new empty output directory:

```bash
python -m src.ingest_multisource --mode macro_lookup
python -m src.ingest_multisource --mode harmonize_parquet
NLTK_DATA=data/nltk_data OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -m src.knn_sensitivity_benchmark \
  --harmonized-parquet data/processed/harmonized_marketplace_corpus.parquet \
  --macro-lookup data/processed/macro_lookup_table.json \
  --validation-cutoff 2024-02-20T00:00:00+00:00 \
  --test-cutoff 2024-02-22T00:00:00+00:00 \
  --dataset-version local-rebuilt-proxy-2026-10-13 \
  --output-dir reports/m9_knn_sensitivity_121 --samples 25
python -m pytest -q tests/test_knn_sensitivity_benchmark.py tests/test_inference_safe_benchmark.py
```

The exact local benchmark JSON, frozen protocol and model binaries remain ignored under `reports/`. Report a new hash rather than comparing a new snapshot's score with this one as if only k or epsilon changed.
