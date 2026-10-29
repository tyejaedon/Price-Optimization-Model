---
name: price-model-ops
description: Operational runbooks, verification procedures, and test execution workflows for the Price Optimization Model project.
---

# Price Optimization Model Operations Skill

This skill provides fast, low-token operational runbooks for verifying, testing, benchmarking, and debugging the Price-Optimization-Model service.

## 1. Quick Verification Pipeline

Run the standard test suite with minimal verbosity to conserve tokens:

```powershell
# Run all unit tests concisely
.venv\Scripts\pytest -q tests/
```

If a specific subsystem needs testing:

```powershell
# Test spatial engine only (including M16 multi-tier fallback & kernels)
.venv\Scripts\pytest -q tests/engine/test_spatial_engine.py tests/engine/test_spatial_engine_m16.py

# Test NLP pipeline only
.venv\Scripts\pytest -q tests/nlp/

# Test API endpoints and wire contracts only
.venv\Scripts\pytest -q tests/api/ tests/engine/test_canonical_pricing.py
```

## 2. Model Inference & Pipeline Sanity Check

To run a fast sanity check on the pipeline without launching the full server:

```powershell
python -c "from src.pipeline.master_pipeline import get_master_pipeline; p = get_master_pipeline(); print('Pipeline loaded successfully')"
```

## 3. ASGI API Local Smoke Test

To verify the FastAPI endpoint boots and responds to health checks:

```powershell
python -c "from fastapi.testclient import TestClient; from src.api.main import app; client = TestClient(app); res = client.get('/health'); print(res.status_code, res.json())"
```

## 4. Algorithmic Benchmarks & Continuous MLOps Drift Monitoring (M16)

Run the advisory research benchmarking and continuous monitoring tools:

```powershell
# Benchmark KNN IDW vs Ridge vs Random Forest vs Gradient Boosting (MAE, RMSE, MAPE, Latency, Interpretability)
python -m src.benchmarks.ensemble_benchmark --samples 500

# Benchmark exact KDTree vs Approximate Nearest Neighbor search scaling (N = 1k, 5k, 10k)
python -m src.benchmarks.ann_benchmark --scales 1000 5000 10000

# Run Population Stability Index (PSI) and Kolmogorov-Smirnov drift monitoring
python -m src.drift_monitor --drift-magnitude 0.25
```

## 5. Token & Context Conservation Guidelines
- When inspecting test failures, run pytest with `--tb=short` or specify the exact failing test function (`pytest -k test_name`) instead of re-running the entire suite with verbose stack traces.
- Keep data samples small during exploratory tests. Do not print full DataFrames to console output.
- All new features and pull requests must follow the FDD syntax: `<action> the <result> <by|to|of|from> a <object>`.
