# #119 — Bilateral-alpha and country-anchor sensitivity

**Status: protocol and synthetic software checks complete; dated #93 local research not run (missing inputs).** Milestone 9, research only. [Issue #119](https://github.com/tyejaedon/Price-Optimization-Model/issues/119); [assumption register](assumptions.md). No production defaults, model schema, data, tariffs or serving artifacts change.

## Predeclared protocol (before any #119 local candidate outcome)

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

The CLI rejects wrong SHA-256 values before touching output. `protocol_frozen.json` records hashes, cohort, candidates and fit policy **before** fitting; `benchmark.json` records each success/failure and aggregate-only outcomes. Research artifact directories are under ignored `reports/`, with **no deployable manifest**. `--allow-other-snapshot` exists for synthetic tests or separate exploratory inputs and prominently marks the report `other_snapshot_not_93`; **never** describe those runs as #93 reproduction. The command does not silently rebuild the old cohort from newer raw files.

## Local evidence and limitations (2026-10-13)

| Scenario | #93 validation factor/target/corridor/peers | Reload and local latency | Status |
| --- | --- | --- | --- |
| 0 | Not run | Not run on #93 | Blocked: original hashed inputs unavailable |
| 0.25 | Not run | Not run on #93 | Blocked: original hashed inputs unavailable |
| 0.50 control | Not run | Not run on #93 | Blocked: original hashed inputs unavailable |
| 0.75 | Not run | Not run on #93 | Blocked: original hashed inputs unavailable |
| 1 | Not run | Not run on #93 | Blocked: original hashed inputs unavailable |

The isolated worktree lacks **both** `data/processed/harmonized_marketplace_corpus.parquet` and `data/processed/macro_lookup_table.json`. Available raw CSVs do not include the required WDI PPP source CSV, and even reconstructing a current macro table would **not** prove the original #93 macro/parquet hashes or reproduce its dated cohort. The synthetic fixtures exercise consistent label/factor recomputation, fallback/same-country controls, train-only fit, reload parity, hash and provenance guards; **their results are not #93 findings or validated mentor prices**. Only restore the two matching, dated, ignored inputs from a trusted prior local snapshot to run the actual scenarios. A fresh independently sourced mentor-payment cohort and verified country roles are needed to decide real pricing; #91/#118 make that research non-blocking for M10–M14.
