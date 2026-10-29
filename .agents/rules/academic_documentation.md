# Academic Documentation & Technical Writing Standards

All architectural documentation, research reports, and technical summaries must adhere to the standards of the Strathmore University dissertation proposal (*Munyua, 2026*):

1. **Academic Tone & Perspective:**
   - Use third-person objective perspective. Avoid informal first-person singular pronouns ("I", "my").
   - Employ formal passive construction for methodology ("The feature space was partitioned using k-d trees") or first-person plural for collective investigative intent ("We formulate the pricing corridor as...").
   - Frame conclusions empirically using measurable metrics (MAE in KES/hour, RMSE, MAPE %, inference latency in ms, Recall@k).

2. **Mathematical Nomenclature Standards:**
   - Unified feature space: $q = [e_1, \dots, e_n, \; \tilde{\beta}_{ij}, \; \tilde{s}, \; \tilde{\rho}]^T \in \mathbb{R}^{n+3}$.
   - Latent text dimension: $e \in \mathbb{R}^n$ ($n=50$ for SVD, $n=384$ for Sentence Transformers).
   - Bilateral PPP arbitrage factor: $\beta_{ij} = (\frac{\text{PPP}_j}{\text{PPP}_i} \cdot \frac{\text{CoL}_i}{\text{CoL}_j})^\alpha$ with damping coefficient $\alpha \in [0, 1]$ (default $0.50$).
   - Normalized IDW weights: $w_k = \frac{1}{(d_k)^p + \epsilon}, \; \bar{w}_k = \frac{w_k}{\sum w_j}$.
   - Pricing corridor: $[r_{\min}, r_{\max}]$ where $r_{\min} = \max(r_{\text{floor}}, \hat{r}_{\text{base}} - z \sigma_{\text{peer}})$ and $r_{\max} = \hat{r}_{\text{base}} + z \sigma_{\text{peer}}$.

3. **Core Domain Lexicon:**
   - Always utilize canonical domain terms: *Cross-Border Arbitrage Paradox*, *Domestic Underpricing Trap*, *International Alienation Trap*, *Transaction Fee Vulnerability*, *Content-Based Dynamic Pricing*, *Cold-Start Fallback Cascade*.

4. **Institutional Reference:**
   - Refer to `docs/Architecture/Academic_Documentation_Style_Guide.md` for complete derivations, diagrams, and domain taxonomy mappings.
