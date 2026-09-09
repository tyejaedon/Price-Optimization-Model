# Contributing Guide

Thanks for contributing to `Price-Optimization-Model`.

This project uses a milestone-driven workflow called the **Price Optimization Model Feature Track**. Every code change should map to a tracked issue and milestone.

---

## Workflow Overview

1. Open or pick a GitHub issue.
2. Confirm the issue has the correct milestone and workstream labels.
3. Create a branch from `master`.
4. Implement and validate your change.
5. Open a PR using the repository PR template.
6. Link the PR to the issue using `Closes #<issue_number>`.

---

## Issue Templates

Use the issue templates in `.github/ISSUE_TEMPLATE/`:

- `01_data_engineering.yml`
- `02_nlp_feature_engineering.yml`
- `03_spatial_modeling.yml`
- `04_api_backend.yml`
- `05_testing_performance.yml`

Each template collects:
- milestone intent,
- tasks,
- acceptance criteria,
- file/document references.

> Note: GitHub issue forms cannot always assign milestones automatically in every setup. After creating an issue, confirm milestone assignment manually.

---

## Milestone Map

| Milestone | Scope |
| --- | --- |
| Milestone 1: Data Ingestion & Macroeconomic Harmonization | Raw data ingestion, macro lookup extraction, currency harmonization |
| Milestone 2: Semantic NLP & Dimensionality Reduction Pipeline | Text cleaning, TF-IDF, Truncated SVD artifacts |
| Milestone 3: Bilateral Arbitrage Scaler & Coordinate Fusion | Metadata scaling and 53D coordinate fusion |
| Milestone 4: Partitioned Spatial Indexing & IDW Regression | KD-Tree partitioning, nearest-neighbor retrieval, IDW prediction |
| Milestone 5: Localized Financial Margin Protection (M-Pesa) | M-Pesa surcharge rules and domestic margin protection |
| Milestone 6: Master Pipeline Training, Validation & Auditing | Split strategy, benchmarking, R^2 gate, artifact serialization |
| Milestone 7: Production ASGI API Service (FastAPI) | DTO schemas, inference endpoint, health checks |
| Milestone 8: Automated Verification, Latency Profiling & MLOps | Unit tests, performance profiling, operational readiness |

---

## Label Map for Workstreams

Apply `project:feature-track` to all feature-track issues and PR-related issues.

| Label | Use When |
| --- | --- |
| `data-engineering` | Ingestion, cleaning, harmonization, or dataset export work |
| `macroeconomics` | PPP, parity factors, country code normalization, cost-of-living logic |
| `nlp-prep` | Marketplace text shaping before model vectorization |
| `nlp` | NLP pipeline behavior, tokenization, lemmatization |
| `preprocessing` | Sanitization and normalization logic |
| `machine-learning` | Core model behavior and learning pipelines |
| `feature-engineering` | Metadata scaling and vector fusion |
| `spatial` | KD-Tree index structure, partitioning, nearest-neighbor routing |
| `algorithms` | IDW math, weighting stability, scoring logic |
| `fintech` | Pricing/fee financial logic |
| `margin-protection` | M-Pesa surcharge and quote protection rules |
| `model-training` | Train/validation/test orchestration |
| `evaluation` | RMSE/R^2 metrics, baseline comparisons, quality gates |
| `api` | API contracts and endpoint design |
| `schemas` | DTO/Pydantic validation definitions |
| `backend` | Service startup, inference wiring, runtime behavior |
| `testing` | Unit/integration regression tests |
| `qa` | Quality gates, invariance checks, edge-case validation |
| `performance` | Runtime latency and efficiency checks |
| `benchmarking` | Profiling and comparative performance runs |
| `pipeline` | Multi-step orchestration and artifact flow |

---

## Pull Request Requirements

Use `.github/pull_request_template.md` and ensure all required fields are completed.

Every PR must:

- link at least one issue (`Closes #...`),
- state target milestone,
- list primary workstream label,
- include validation evidence (commands + key output),
- confirm no large raw data files were committed.

Repository policy automation also enforces:

- PR is opened as **Draft** first,
- branch name follows `<type>/<issue-number>-<slug>`,
- PR body closes the matching issue number from the branch,
- required checks pass before merge.

Recommended:

- keep one PR focused on one issue when possible,
- include small, reviewable commits,
- keep acceptance criteria traceable from issue to PR.

---

## Workflow Bootstrap Script

Use `scripts/bootstrap-workflow.ps1` to automate the policy flow:

- prompts for issue number and branch type when missing,
- creates a compliant branch name (`<type>/<issue-number>-<slug>`),
- pushes the branch to `origin`,
- opens a **draft PR** with milestone and labels prefilled from the linked issue.

Example (interactive):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap-workflow.ps1
```

Example (non-interactive):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap-workflow.ps1 -IssueNumber 14 -BranchType feature
```

Safe test mode:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap-workflow.ps1 -IssueNumber 14 -BranchType feature -DryRun
```

Mark a draft PR as ready only after required checks pass:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ready-pr.ps1 -Wait
```

Dry-run preview for PR readiness:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ready-pr.ps1 -PrNumber 14 -DryRun
```

---

## Branch Naming Convention

Required format for feature-track work:

```text
<type>/<issue-number>-<short-topic>
```

Examples:

- `feature/14-fastapi-health-endpoint`
- `fix/9-idw-zero-distance-stability`
- `chore/3-parquet-export-cleanup`


---

## Commit Message Convention

Suggested commit format:

```text
type(scope): short description
```

Examples:

- `feat(data): add PPP lookup extraction utility`
- `feat(nlp): add tfidf + svd artifact persistence`
- `test(api): validate 422 behavior for invalid payloads`

---

## Data Safety and Large Files

The repository is configured to ignore local datasets under `Data/`.

Before pushing:

1. run `git status`,
2. confirm no files under `Data/` are staged,
3. remove accidentally staged data using `git restore --staged <path>`.

---

## Protected Branch and Required Checks

`master` is protected. Direct pushes are blocked by branch protection.

Merge requires:

- at least 1 approving review,
- resolved conversations,
- passing required checks:
  - `Policy Gates`
  - `Repository Integrity`
  - `Python Sanity`

Workflow files responsible for these gates:

- `.github/workflows/pr-governance.yml`
- `.github/workflows/ci-checks.yml`

---

## Source-of-Truth Planning Docs

Use these documents for planning alignment:

- `README.md`
- `Docs/Blueprint.md`
- `Docs/Project_Milestones_and_Issues.md`

If implementation decisions change, update docs and linked issues in the same PR.

