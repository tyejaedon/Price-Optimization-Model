# Retrained model: 2026-10-04

The persisted model is a domain-partitioned KD-Tree with inverse-distance-weighted (IDW) pricing, using 50 text SVD and 3 normalized metadata coordinates. Training completed at `2026-10-04T17:54:13.695512+00:00` with random seed 42. The 22,677-row local harmonized corpus was split by industry into 15,873 training, 3,402 validation, and 3,402 test records. Preprocessing was fitted only on the training split.

An independent validation sweep of `k = 1, 3, 5, 7, 10, 15, 20, 30, 50` selected **k = 10** by validation R². The saved model's evaluation agrees with `experiment_report.json`.

| Split | IDW R² | IDW RMSE (KES/hour) | IDW MAE (KES/hour) | Category-mean baseline R² | Baseline RMSE (KES/hour) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Validation | 0.563592 | 20,999.112212 | 11,062.517278 | 0.032858 | 31,260.763583 |
| Test | 0.579124 | 20,870.888957 | 10,848.984095 | 0.042979 | 31,472.019903 |

The model beats the category-mean baseline on both splits, but **fails the required validation R² >= 0.75 quality gate**. Training used `--no-enforce-quality-gate` solely to save local evaluation artifacts; do not promote this model as quality-approved. This split's test result is descriptive, not a tuning criterion. Compared with the prior k=5 run (validation R² 0.532721; test R² 0.565242), the offline k=10 setting improves both scores but still fails the gate.

The API in `src/serve.py` currently uses the fixed `DEFAULT_QUERY_NEIGHBORS = 5` from `src/spatial_engine.py`; it does **not** read the persisted `k_neighbors = 10` from the training summary. Accordingly, the table above describes offline evaluation at k=10, not current serving behavior. Changing this would require a separate issue-scoped code change.

Inputs: `data/processed/harmonized_marketplace_corpus.parquet` and `data/processed/macro_lookup_table.json`. Persisted files are under `artifacts/` (`training_summary.json`, NLP reducer, metadata scaler, and industry KD-Trees); tuning tables and plots are under `reports/model_evaluation/`. All these directories are Git-ignored; do not commit local data or generated artifacts.

Reproduce from the repository root:

```powershell
python -m src.experiment_reporting --mode report --harmonized-parquet data/processed/harmonized_marketplace_corpus.parquet --macro-lookup data/processed/macro_lookup_table.json --output-dir reports/model_evaluation
python -m src.train_pipeline --mode evaluate --harmonized-parquet data/processed/harmonized_marketplace_corpus.parquet --macro-lookup data/processed/macro_lookup_table.json --artifact-dir artifacts --k-neighbors 10 --no-enforce-quality-gate
python -m unittest discover -s tests -p test_train_pipeline.py -q
```

Validation: saved NLP, scaler, and KD-Tree artifacts reload; training metrics exactly match the tuning report; 11 focused tests passed.
