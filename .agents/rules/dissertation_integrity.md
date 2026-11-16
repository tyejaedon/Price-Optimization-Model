---
description: Dissertation integrity, document identity, and mathematical rendering validation rules
globs: ["docs/**/*.md", "**/*.tex", "**/*.docx"]
always_on: true
---

# Dissertation Integrity and Scientific Rigor Rules

When authoring, editing, or validating Strathmore University dissertation chapters, technical reports, or architecture documentation, strictly adhere to the following invariants:

## 1. Zero Unrendered Placeholders and Glyphs
- Never permit empty parentheses `()`, unrendered placeholder blocks (`■`), dangling colons (`:`), or empty parameter brackets in generated or compiled text.
- Every variable mentioned in prose must be explicitly defined (e.g., $d = 50$, $k = 5$, $\alpha = 0.50$, $R^2 \ge 0.75$).
- Every equation caption must be accompanied by its numbered display formula and full parameter notation.

## 2. Document Identity & Temporal Harmonization
- Harmonize document framing to reflect the actual project stage:
  - If reporting completed implementations, tests, and artifacts, frame the document as the **Research Dissertation / Project Report** using past tense for completed work.
  - Eliminate proposal phrasing (*"will be developed"*, *"shall discuss"*) from Chapters 1 through 5.
  - Position institutional front-matter (Strathmore cover crest, Declaration and Approval with admission number `169684`, and signed approvals) at the very front of the manuscript.

## 3. Financial & Payment Logic Invariants
- Safaricom M-Pesa schedule must be consistently designated as the **15-tier Peer-to-Peer (P2P)** schedule (`mpesa_p2p_users_2026-08-04.csv`, KES 1.00 to KES 250,000.00).
- Domestic tariff protection activates strictly when both mentor and client reside in Kenya (`mentorCountry == 'KE' and clientCountry == 'KE'`).
- Cross-border export transactions bypass domestic M-Pesa fees but must document standard international processor / FX settlement deductions (2.9%–4.8% via Flutterwave, Paystack, or PayPal-to-M-Pesa).

## 4. Software Stack Veracity
- Never invent or fabricate software package versions.
- Pinned package versions must correspond strictly to verified releases in `requirements.txt` and `build.gradle.kts` (e.g., Python 3.11, FastAPI 0.115+, scikit-learn 1.5+, AGP 8.5.2 with compatible Gradle 8.7+).

## 5. Scholarly Citation Hygiene
- Never include hallucinated citations or website URLs disguised as peer-reviewed publications (e.g., replace `adplist2021adplist` with institutional platform documentation or peer-reviewed literature).
- Ensure all in-text citations appear in the References list and vice versa (e.g., Benmoshe, 2025; Chai & Draxler, 2014; Cassel, 1918; World Bank, 2020; Safaricom PLC, 2024).
