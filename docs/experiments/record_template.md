# Experiment record template (copy for an issue; do not fill with invented results)

Status: **planned / running / completed / not identifiable / deferred**. Issue: **#TBD**. PR and report link: **TBD**. Date/time and researcher: **TBD**. If work has not run, keep results as **not run**; never fill in example scores.

## Before inspecting candidate outcomes

1. **Question and falsifiable hypothesis:** What would count as evidence *for* or *against* changing one setting? Is the goal error, peer stability, memory, latency or a product-policy invariant? Which alternatives already exist (#38, #93, #117)?
2. **Data/label provenance:** Immutable dataset + macro lookup names, versions and SHA-256; raw label meaning (posted budget, profile asking rate, *synthetic* platform record or verified payment), KES/hour conversion and country-role assumptions. Is the target independently observed or **computed using the tested parameter**? If the latter, restrict conclusions to sensitivity, not an empirical optimum.
3. **Frozen protocol:** Eligibility/exclusions with counts; source time coverage, identity/duplicate policy, predeclared UTC chronological train/validation/final-test cutoffs and row counts; industry distribution; train-only TF-IDF/SVD, scaler, density and index fits. State whether the proposed test labels/scores have **ever been viewed for this snapshot** (the #93 final window has); if so, reuse is exploratory rather than blind confirmation. If there are no reliable timestamps, say so and label a random split exploratory, never OOT.
4. **Single-variable comparison:** Current baseline and why it exists; changed setting and *small, justified, predeclared* candidate values; everything held constant (representation, alpha, k/epsilon, weights, partition fallback, hardware and seeds). Keep unrelated product/security/tariff rules out of score tuning.
5. **Measurements and decision rule:** Raw-KES/hour MAE/RMSE/R² and bias when an independent held-out label exists; per-industry coverage, nearest-peer rank/overlap, corridor sensitivity where relevant, finite vectors/reload parity, train/warm inference p50/p95, memory and artifact size. Select on validation only; open a **genuinely unopened final test** once, if available. Otherwise report exploratory validation/sensitivity, not a new test-backed winner. Fix thresholds *before* scoring or report descriptive trade-offs without a winner.

## After the run (or if it cannot be identified)

| Candidate / baseline | Validation: MAE, RMSE, R² (or N/A + why) | Final test: genuinely sealed / previously opened / not available | Neighbor/explanation changes | Warm p95 / memory / bytes | Failures / observations |
| --- | --- | --- | --- | --- | --- |
| Not run | Not run | Not run | Not run | Not run | Replace after an actual experiment |

- **Environment and reproducibility:** Commands, code commit, dataset/macro hashes, library versions, platform/CPU/threads, fixed seed; location of ignored aggregate-only reports and relevant tests. Do not commit raw records, model binaries, individual predictions, IDs or secrets.
- **Interpretation:** What was observed (include null and negative results), what was assumed, what cannot be inferred about paid mentor rates, uncertainty from small partitions/time drift, and whether a request can compute the feature without leakage.
- **Decision:** Retain the documented default / propose a *separate* schema or model migration / cannot choose with current data. A proxy-validation winner is never automatic deployment approval. Link the result from [the index](README.md) and update [assumption provenance](assumptions.md) without erasing the original baseline.
