---
name: milestone-issue-governance
description: >-
  Standards for decomposing dissertation engineering requirements into Feature-Driven
  Development (FDD) issues and milestones. Enforces canonical issue naming syntax,
  traceability matrices, and strict isolation between core degree deliverables (M1-M15)
  and external supervisor advisory exploration (M16).
---

# Milestone & Issue Governance Skill

This skill governs the systematic formulation, tracking, and execution of engineering milestones and GitHub issues for the dissertation codebase.

## 1. Feature-Driven Development (FDD) Naming Syntax

All milestone work items and issue titles must strictly adhere to the standard FDD syntax template:
`<action> the <result> <by|to|of|from> a <object>`

Examples:
- `Curate the experimental findings diagrams for Chapter 5 documentation`
- `Benchmark the KNN spatial engine against gradient boosted tree ensembles`
- `Tune the neighborhood size and distance weighting kernels for IDW regression`
- `Evaluate the latent text dimensionality trade-offs of truncated SVD`
- `Enforce the four-tier cold-start fallback cascade for sparse skill partitions`

## 2. Milestone Architecture & Deliverable Isolation

To ensure academic deadlines and degree requirements remain uncompromised, milestones must be categorized into two distinct operational tiers:

1. **Core Academic Deliverables (Milestones 1 through 15):**
   - Strictly tied to the approved dissertation proposal objectives, system architecture, functional requirements (FR-01 to FR-07), and non-functional requirements (NFR-01 to NFR-05).
   - Blocking for academic submission and final oral defense.
   - Any external feedback that alters core scope must be formally reconciled via a feedback-resolution matrix.

2. **External Advisory Research Track (Milestone 16):**
   - Encapsulates high-level supervisor, coordinator, or external reviewer recommendations (e.g., exploratory ANN scaling, sentence transformers, continuous drift automation).
   - Maintained in research isolation: issues in M16 are non-blocking for core degree milestones.
   - Documented in Chapter 5 as exploratory ablations or positioned in Chapter 6 as future work.

## 3. Issue Template & Traceability Standards

Every created issue must contain:
1. **Problem Statement:** Exact gap or research question addressed.
2. **Requirement Traceability:** Direct link to Chapter 4 requirements (e.g., FR-04, NFR-01) or Chapter 1 specific objectives.
3. **Predeclared Experimental Protocol:** Hypotheses, data snapshot SHA-256 hashes, frozen random seeds, and evaluation metrics.
4. **Concrete Checklists:** Checkbox list of actionable implementation steps.
5. **Acceptable Evidence Criteria:** Measurable criteria (unit test pass rates, benchmark tables, generated figures).
