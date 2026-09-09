### 2h. Run M4.2 IDW regression + peer explainability demo
```bash
python -m src.spatial_engine --mode idw_demo --artifact-dir artifacts --requested-partition product_management --min-partition-size 2 --k 3
```

### 2i. Run M5.1 M-Pesa tariff evaluator demo
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

