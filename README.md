# Dynamic Price Optimizer for Technical Mentors & Consultants

An intelligent pricing recommendation engine designed for independent consultants, technical mentors, and digital freelancers in emerging markets like Kenya.  

It analyzes qualitative skills from profile text, balances cross-border purchasing power, finds real market comparisons, and adds localized mobile money (M-Pesa) fee protection so practitioners never underquote or lose profit to transaction costs.

---

## The Problem

Freelancers and mentors in emerging economies face a tough rate-setting challenge:

- **The Cross-Border Dilemma**: If you quote international clients using local rates, you leave substantial money on the table. If you quote static US rates ($100+/hr), you price out local and regional African clients.  
- **Guesswork Pricing**: Most independent professionals guess their hourly rates arbitrarily, leading to prolonged haggling, undercharging, or imposter syndrome.  
- **Hidden Fee Leakage**: For domestic micro-consulting paid via mobile money (like Safaricom M-Pesa), withdrawal and transfer fees directly chip away at your net take-home earnings if not calculated into the quote upfront.  

---

## How It Works

The engine uses a **4-step pipeline**:

| Step | Input | Process | Output |
| --- | --- | --- | --- |
| **1. NLP Capability Analysis** | Profile Bio & Skills | TF-IDF + SVD dimensionality reduction | 50-dimensional skill vector |
| **2. Cross-Border Parity Adjustment** | Mentor & Client Country | World Bank PPP & cost-of-living scaling | Balanced international/local rate |
| **3. Peer Cluster Lookup** | Industry Category | KD-Tree nearest-neighbor search (k=5) | Average of top 5 peer rates |
| **4. Additive Margin Protection** | M-Pesa Fee Schedule | Safaricom tariff calculator | Final quoted rate with fee protection |

### M-Pesa Margin Protection Formula
\[
\text{Final Quoted Rate} = \text{Base Recommended Rate} + \text{M-Pesa Transfer Fee}
\]

---

## System Architecture

| Tier | Technology Stack | Key Components |
| --- | --- | --- |
| **Tier 1: Client Mobile App** | Android / Kotlin | Jetpack Compose UI (country selectors, skill inputs), PricingViewModel, hardware-backed encrypted storage |
| **Tier 2: Cloud Ingestion API** | FastAPI / ASGI | Non-blocking async endpoints, Pydantic V2 validation, Firebase JWT authentication |
| **Tier 3: Core Analytical & ML Pipeline** | Scikit-Learn | NLP tokenizer & dimensionality reducer (TF-IDF + SVD), PPP parity scaler, KD-Tree nearest-neighbor search (k=5), Safaricom M-Pesa tariff calculator |
| **Tier 4: Persistence & Storage** | Firebase / Cloud Firestore | Firebase authentication (sessions & tokens), Firestore NoSQL (audit logs, peer nodes, reference lookups) |

---

## Repository Structure

| Path / File | Purpose |
| --- | --- |
| `Data/` | Top-level data directory for raw and processed project datasets |
| `Data/Raw/` | Source datasets collected from external platforms and public indicators |
| `Data/Raw/Cost_Index/` | Cost-of-living reference data by country |
| `Data/Raw/Data_Scientist_Upwork/` | Upwork data scientist pricing and profile data |
| `Data/Raw/Developer_Survey/` | Developer survey summary datasets |
| `Data/Raw/freelancer_earnings/` | Freelancer earnings and skill stack datasets |
| `Data/Raw/upwork-jobs.csv/` | Raw Upwork jobs export |
| `Data/Raw/World_Development_Indicators/` | World Bank development and macroeconomic indicators |
| `Data/Processed/` | Cleaned or transformed datasets ready for downstream analysis |
| `Docs/` | Project documentation, diagrams, and design artifacts |
| `Docs/Blueprint.md` | Project blueprint and planning document |
| `Docs/Project_Milestones_and_Issues.md` | Detailed milestone roadmap and GitHub issue breakdown |
| `Docs/Architecture/` | Architecture diagrams and technical design references |
| `Docs/Architecture/Class/` | Class diagrams for API gateway, domain, ML pipeline, and mobile modules |
| `Docs/Architecture/Conceptual Framework/` | High-level conceptual framework assets |
| `Docs/Architecture/Database Schema/` | Database schema diagrams in image and vector formats |
| `Docs/Architecture/ERD/` | Entity-relationship diagrams |
| `Docs/Architecture/ML Pipeline/` | Machine learning pipeline diagrams |
| `Docs/Architecture/System Arch/` | Overall system architecture diagrams |
| `Docs/Architecture/Use case/` | Use-case diagrams |
| `.github/ISSUE_TEMPLATE/` | GitHub issue forms aligned to project workstreams |
| `.github/pull_request_template.md` | PR checklist tied to milestone and issue workflow |
| `.github/copilot-instructions.md` | Agent instructions for issue-linked branching and PR governance |
| `.github/agents/` | Workflow governance agent docs and skill packs |
| `.github/workflows/pr-governance.yml` | PR policy gates: draft-first, branch-issue linkage, issue closure format |
| `.github/workflows/ci-checks.yml` | CI integrity checks for repository safety and Python sanity |
| `scripts/bootstrap-workflow.ps1` | Prompts for issue/branch type, creates compliant branch, and opens draft PR with milestone/labels |
| `scripts/ready-pr.ps1` | Verifies required checks and transitions draft PRs to Ready for Review |
| `CONTRIBUTING.md` | Contributor process, label map, and milestone mapping guide |
| `Src/` | Source code directory for implementation modules |
| `Test/` | Test directory for validation and QA assets |
| `Readme.md` | Project overview, setup guidance, and usage documentation |

---

## Quickstart & Setup

### Prerequisites
- Python: 3.11 or higher  
- Java SDK: 17+ (if building the Android client)  
- Android Studio: Hedgehog (2023.1.1) or newer  

### 1. Installation
```bash
git clone https://github.com/your-username/dynamic-pricing-engine.git
cd dynamic-pricing-engine

python3 -m venv venv
source venv/bin/activate       # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

# Download required NLTK lexical corpora
python -c "import nltk; nltk.download('stopwords'); nltk.download('wordnet')"
```

### 2. Prepare Data & Build Corpus
```bash
python -m src.ingest_multisource
```

### 2b. Preview and export M1.2 harmonized marketplace records
```bash
python -m src.ingest_multisource --mode harmonize_corpus --preview-limit 5
python -m src.ingest_multisource --mode harmonize_corpus --output data/processed/harmonized_marketplace_corpus.csv
```

### 2c. Build M1.3 harmonized parquet with macro joins
```bash
python -m src.ingest_multisource --mode macro_lookup --output data/processed/macro_lookup_table.json
python -m src.ingest_multisource --mode harmonize_parquet --macro-lookup data/processed/macro_lookup_table.json --output data/processed/harmonized_marketplace_corpus.parquet --preview-limit 3
```

### 2d. Run M2.1 text sanitization preview
```bash
python -m src.nlp_pipeline --text "Senior backend engineer with 8 years of API platform experience"
```

### 2e. Run M2.2 TF-IDF + SVD artifact demo
```bash
python -m src.nlp_pipeline --mode fit_demo --n-components 50 --max-features 12000 --artifact-dir artifacts
```

### 2f. Run M3.1 metadata scaler demo
```bash
python -m src.macro_arbitrage --mode fit_demo --artifact-dir artifacts --mentor-country KE --client-country US --market-saturation 0.25 --industry-density 0.4
```

### 2g. Run M3.2 hybrid coordinate fusion demo
```bash
python -m src.macro_arbitrage --mode fuse_demo --artifact-dir artifacts --mentor-country KE --client-country US --market-saturation 0.25 --industry-density 0.4
```

### 2h. Run M4.2 IDW regression + peer explainability demo
```bash
python -m src.spatial_engine --mode idw_demo --artifact-dir artifacts --requested-partition product_management --min-partition-size 2 --k 3
### 2h. Run M5.1 M-Pesa tariff evaluator demo
```bash
python -m src.tariff_evaluator --base-rate 4500 --mentor-country KE --show-bands
```

### 3. Train the Model
```bash
python -m src.train_pipeline
```

### 4. Start the Inference Server
```bash
uvicorn src.serve:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Reference

### Get a Rate Recommendation
**POST** `/api/v1/optimize-price`

Request:
```json
{
  "raw_description": "Senior Android engineer specializing in Kotlin coroutines, Jetpack Compose UI architecture, and clean MVVM modularization. Mentored 15+ junior developers in TDD.",
  "selected_industry": "SOFTWARE_ENG",
  "mentor_country": "KE",
  "client_country": "US",
  "competitiveness_score": 0.65,
  "market_saturation_score": 0.45
}
```

Response:
```json
{
  "base_predicted_rate": 4700.0,
  "mpesa_tariff_surcharge": 55.0,
  "final_quoted_rate": 4755.0,
  "currency": "KES",
  "bilateral_arbitrage_factor": 0.51,
  "nearest_neighbors": [
    {
      "peer_index": 1402,
      "distance": 0.214,
      "verified_rate": 4900.0,
      "similarity_score": 0.823
    },
    {
      "peer_index": 891,
      "distance": 0.289,
      "verified_rate": 4650.0,
      "similarity_score": 0.775
    }
  ]
}
```

---

## Health Check
**GET** `/health`
```json
{
  "status": "HEALTHY",
  "models_loaded": true
}
```

---

## Running Automated Tests
```bash
pytest tests/ -v
```

---

## Academic Attribution
Developed as an academic thesis project at the **School of Computing and Engineering Sciences, Strathmore University, Nairobi, Kenya**.

```bibtex
@thesis{munyua2026dynamicpricing,
  author    = {Munyua, Jaedon Jeremiel},
  title     = {A Content-Based Dynamic Price Optimization Framework for Professional Mentorship Services in the Freelance Economy},
  school    = {School of Computing and Engineering Sciences, Strathmore University},
  year      = {2026},
  address   = {Nairobi, Kenya},
  type      = {Undergraduate Thesis}
}
```

---

## License
Distributed under the **MIT License**.

---

