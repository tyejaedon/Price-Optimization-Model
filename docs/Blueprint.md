**Here’s the **full README.md** with everything converted into tables for consistency — including the repository structure, system architecture tiers, and the 4‑step pipeline.

```markdown
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
|------|-------|---------|--------|
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
|------|------------------|----------------|
| **Tier 1: Client Mobile App** | Android / Kotlin | Jetpack Compose UI (country selectors, skill inputs), PricingViewModel, hardware-backed encrypted storage |
| **Tier 2: Cloud Ingestion API** | FastAPI / ASGI | Non-blocking async endpoints, Pydantic V2 validation, Firebase JWT authentication |
| **Tier 3: Core Analytical & ML Pipeline** | Scikit-Learn | NLP tokenizer & dimensionality reducer (TF-IDF + SVD), PPP parity scaler, KD-Tree nearest-neighbor search (k=5), Safaricom M-Pesa tariff calculator |
| **Tier 4: Persistence & Storage** | Firebase / Cloud Firestore | Firebase authentication (sessions & tokens), Firestore NoSQL (audit logs, peer nodes, reference lookups) |

---

## Repository Structure

| Path / File              | Purpose                                                                 |
|---------------------------|-------------------------------------------------------------------------|
| `artifacts/`             | Saved ML models (`.joblib` files)                                       |
| `data/raw/`              | Local source datasets (Upwork, World Bank, Numbeo)                      |
| `data/processed/`        | Cleaned Parquet corpus & lookup tables                                  |
| `src/config.py`          | Hyperparameters, fee bands, and paths                                   |
| `src/ingest_multisource.py` | Merges & cleans raw CSV datasets                                    |
| `src/nlp_pipeline.py`    | Cleans text & extracts SVD skill vectors                                |
| `src/macro_arbitrage.py` | Cross-border PPP & cost-of-living scaler                                |
| `src/spatial_engine.py`  | KD-Tree spatial indexer & rate predictor                                |
| `src/tariff_evaluator.py`| Safaricom M-Pesa tariff fee calculator                                  |
| `src/train_pipeline.py`  | 70/15/15 model training & evaluation                                    |
| `src/serve.py`           | FastAPI production inference server                                     |
| `tests/`                 | Unit tests for NLP, parity, and spatial matching                        |
| `requirements.txt`       | Pinned Python dependencies                                              |
| `README.md`              | Project overview and documentation                                      |

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
  "mpesa_tariff_surcharge": 108.0,
  "final_quoted_rate": 4808.0,
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
```

---**
