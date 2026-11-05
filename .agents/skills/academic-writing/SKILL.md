---
name: academic-writing
description: >-
  Academic dissertation and technical documentation writing standards for Strathmore
  University research publications. Enforces continuous paragraph prose (no point form),
  strict grammatical tense rules (past for completed actions, present for established
  evidence, future for incomplete work), concise technical explanations without padding,
  structured A4-compliant tables, and the Narrative-Diagram-Interpretation presentation sequence.
---

# Academic Writing & Dissertation Documentation Skill

This skill enforces the official technical writing, linguistic style, and structural standards for the Strathmore University undergraduate research thesis (*Munyua, 2026*), aligning with institutional guidelines provided by the School of Computing and Engineering Sciences.

## 1. Core Prose & Linguistic Invariants

1. **Strict Grammatical Tense Hierarchy:**
   - **Past Tense:** Use exclusively for completed research activities, implementations, model training, and executed test suites (e.g., *"The dataset was partitioned temporally"*, *"Five candidate estimators were evaluated"*).
   - **Present Tense:** Use exclusively for established scientific knowledge, active runtime behavior, and what documents, tables, or figures illustrate (e.g., *"Figure 5.2 illustrates the coordinate fusion pipeline"*, *"Table 5.7 summarizes holdout metrics"*).
   - **Future Tense:** Restrict strictly to genuinely uncompleted activities, recommendations, or prospective extensions in Chapter 6.

2. **Continuous Flowing Paragraphs (Zero Bullet Points):**
   - Academic dissertation chapters (specifically Chapters 1 through 5) must be composed in continuous, coherent prose paragraphs connected by logical transitions.
   - Do NOT present core methodologies, requirements analysis, or empirical evaluations in point-form outlines, dashed lists, or informal notes.

3. **Concise, High-Density Technical Explanations:**
   - Avoid generic conceptual tutorials or textbook filler (e.g., explaining what RAM, Docker, or cross-validation is in abstract terms).
   - Focus explanations strictly on project-specific architectural justifications, mathematical formulations, operational constraints, and empirical trade-offs.

4. **Third-Person Objective Academic Register:**
   - Use third-person formal voice or objective passive voice (*"The matrix was projected into..."*). Avoid first-person singular pronouns (*"I"*, *"my"*).

## 2. Evidence-First Presentation: The Narrative–Diagram–Interpretation Triad

Every figure, graph, or visual model in Chapter 4 and Chapter 5 must follow the strict institutional presentation sequence:
1. **Narrative (Before Diagram):** Frame what the diagram represents, why it is relevant, its scope, and the specific requirement or research objective it addresses.
2. **Diagram (Visual Representation):** Clean, uncluttered diagram using approved notation (Mermaid, PlantUML, or high-resolution vector export) sized for A4 portrait layout.
3. **Figure Caption:** Numbered and captioned according to institutional rules (e.g., `Figure 5.3: Latent Text Dimensionality vs. Holdout Generalization and Query Latency`).
4. **Interpretation (After Diagram):** Critically analyze the important flows, inflection points, empirical trade-offs, and design implications instead of merely repeating the visual labels.

## 3. Standard Mathematical Nomenclature

- **Unified Coordinate Vector:** $q = [e_1, \dots, e_n, \; \tilde{\beta}_{ij}, \; \tilde{s}, \; \tilde{\rho}]^T \in \mathbb{R}^{n+3}$ ($n=50$ for production SVD, $n=384$ for sentence transformers).
- **Damped Bilateral PPP Arbitrage Factor:** $\beta_{ij} = (\frac{\text{PPP}_j}{\text{PPP}_i} \cdot \frac{\text{CoL}_i}{\text{CoL}_j})^\alpha$ with damping exponent $\alpha \in [0, 1]$ (default $0.50$; domestic $\beta_{ii} \equiv 1.0$).
- **Inverse Distance Weighting (IDW) Kernel:** $w_k = \frac{1}{(d_k)^p + \epsilon}$ normalized as $\bar{w}_k = \frac{w_k}{\sum_{m=1}^k w_m}$.
- **Pricing Corridor Bounds:** $[r_{\min}, r_{\max}]$ where $r_{\min} = \max(r_{\text{floor}}, \hat{r}_{\text{base}} - z \sigma_{\text{peer}})$ and $r_{\max} = \hat{r}_{\text{base}} + z \sigma_{\text{peer}}$.
- **Final Tariff-Protected Quote:** $\hat{r}_{\text{final}} = \hat{r}_{\text{base}} + \tau(\hat{r}_{\text{base}})$.
