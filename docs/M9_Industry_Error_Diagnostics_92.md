# Issue #92 — exploratory industry error diagnostics

This is **deferred, non-blocking research** under the [#91 provenance decision](Label_Provenance_Audit_91.md), not a new serving gate. Existing harmonized rates are **proxy posted job budgets and profile asking rates**, not verified mentor transactions. Never use random-split results as evidence of chronological OOT performance or mentor-pricing accuracy. The raw-KES `R² >= 0.75` OOT policy in #81 is unchanged.

## Reproduce locally (PowerShell)

With an existing **ignored** harmonized parquet and macro lookup:

```powershell
python -m src.validation_diagnostics --mode industry --harmonized-parquet data/processed/harmonized_marketplace_corpus.parquet --macro-lookup data/processed/macro_lookup_table.json --dataset-version proxy-snapshot-v1 --seeds 42 43 44
python -m pytest -q tests/test_validation_diagnostics.py tests/test_oot_training.py
```

The output is an aggregate-only `reports/m9_industry_error_diagnostics/industry_error_diagnostics.json` (Git-ignored). It contains input SHA-256 values, an immutable dataset version (defaults to `sha256:<parquet digest>`), predeclared seed/configuration, population and split counts, model/category-mean baseline raw-KES validation RMSE and R², and industry/source/source-by-industry coverage. It exports **no individual records, descriptions, prediction rows, group identifiers or dates**. A report is identical on rerun with identical inputs and parameters. Do not commit datasets or generated reports.

## Split and metric policy

* Predeclare seeds and IDW `k`, without selecting either by validation/test scores. Assign each **sanitized NLP description** (irrespective of rate, industry or source) wholly to one of train/validation/test. Allocate groups approximately 70/15/15; row proportions may vary for repeated descriptions. Record IDs and description groups are disjoint. This guards duplicate-text leakage; it is **not** a source-grouped or chronological split.
* Fit TF-IDF/SVD, metadata scaling and KD-Trees on training rows only. Recompute partition saturation/density from **training-only counts** on every split. Category means and global fallback use training labels only. Take labels from `harmonized_hourly_rate`, never from an untrusted `target_rate` override. No held-out-rate trimming, source exclusions or score-selected partitions are allowed. Nonfinite rates fail explicitly, rather than silently removing hard cases.
* Diagnostics use **validation only**. Test remains unscored for this exploratory report. The fixed first seed supplies aggregate per-industry/source counts, target/residual p10/median/p90, high-error counts (`|predicted - actual| > 5,000 KES/hour`), labels outside post-arbitrage `[500, 35,000]` KES/hour, and each segment's **share of total validation squared error**. Segments with fewer than 30 validation rows are flagged as sparse, never dropped; R² is `null` for fewer than two or constant targets. Source and industry totals overlap by design; compare error shares *within* each separate segmentation. The summary also describes validation metric variation across predeclared seeds (not independent-population confidence intervals).
* Inspect large squared-error shares alongside **sample volume**, rate ranges, and baseline gaps. Extreme target ranges or tiny groups suggest data-quality/coverage questions; consistent baseline gaps suggest checking representation or IDW routing, **not** a proven causal diagnosis. Do not optimize against the first-seed segment table or publish segment-specific scores as validated rates.

The original #91 audited parquet contained **no** observation timestamps. A local rebuilt snapshot may carry job-publication dates but still lack observation times for profile asking rates; coverage is recorded explicitly as `timestamped_rows` and the missing count in `oot_evaluation.reason`. The report always states `oot_evaluation.status = not_run`: even a dated job-posting cohort is not evidence of *mentor transactions*. #81 separately owns a predeclared cutoff, vetted source-event provenance, chronological holdout, population eligibility and the unchanged OOT gate; this tool deliberately does not compute OOT metrics or claim source-grouped evaluation from incomparable job/profile source labels.
