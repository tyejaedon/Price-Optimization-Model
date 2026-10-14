"""Price Optimization Model.

Subpackages:
  - src.core: Shared configurations, contracts, and observability.
  - src.data: Ingestion, schema normalization, and enrichment.
  - src.nlp: NLP tokenization, vectorization, and embeddings.
  - src.engine: Core algorithmic, spatial, and pricing models.
  - src.training: Model training, OOT validation, diagnostics, and reporting.
  - src.benchmarks: Sensitivity analyses, profiling, and validation benchmarks.
  - src.api: HTTP serving, schemas, MLOps, and persistence.
"""

import importlib
import sys
from importlib.abc import MetaPathFinder
from importlib.util import find_spec, spec_from_loader

_LEGACY_MAP = {
    "config": "src.core.config",
    "artifact_contract": "src.core.artifact_contract",
    "observability": "src.core.observability",
    "ingest_multisource": "src.data.ingest_multisource",
    "ingest_platform": "src.data.ingest_platform",
    "metadata_enrichment": "src.data.metadata_enrichment",
    "label_provenance_audit": "src.data.label_provenance_audit",
    "nlp_pipeline": "src.nlp.nlp_pipeline",
    "spatial_engine": "src.engine.spatial_engine",
    "platform_price": "src.engine.platform_price",
    "interval_synthesizer": "src.engine.interval_synthesizer",
    "macro_arbitrage": "src.engine.macro_arbitrage",
    "tariff_evaluator": "src.engine.tariff_evaluator",
    "train_pipeline": "src.training.train_pipeline",
    "oot_gate": "src.training.oot_gate",
    "validation_diagnostics": "src.training.validation_diagnostics",
    "experiment_reporting": "src.training.experiment_reporting",
    "inference_safe_benchmark": "src.benchmarks.inference_safe_benchmark",
    "alpha_sensitivity_benchmark": "src.benchmarks.alpha_sensitivity_benchmark",
    "knn_sensitivity_benchmark": "src.benchmarks.knn_sensitivity_benchmark",
    "text_sensitivity_benchmark": "src.benchmarks.text_sensitivity_benchmark",
    "svd_dimension_benchmark": "src.benchmarks.svd_dimension_benchmark",
    "svd_rolling_benchmark": "src.benchmarks.svd_rolling_benchmark",
    "protected_pricing_benchmark": "src.benchmarks.protected_pricing_benchmark",
    "performance_profiling": "src.benchmarks.performance_profiling",
    "serve": "src.api.serve",
    "api_contracts": "src.api.api_contracts",
    "mlops_service": "src.api.mlops_service",
    "repository": "src.api.repository",
    "deployment": "src.api.deployment",
}

class _LegacySrcFinder(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname.startswith("src."):
            parts = fullname.split(".")
            if len(parts) == 2 and parts[1] in _LEGACY_MAP:
                target_mod = _LEGACY_MAP[parts[1]]
                spec = find_spec(target_mod)
                if spec is not None:
                    return spec_from_loader(fullname, spec.loader, origin=spec.origin)
        return None

# Append after standard PathFinder so physical files on disk take precedence
if not any(isinstance(finder, _LegacySrcFinder) for finder in sys.meta_path):
    sys.meta_path.append(_LegacySrcFinder())

def __getattr__(name: str):
    if name in _LEGACY_MAP:
        mod = importlib.import_module(_LEGACY_MAP[name])
        sys.modules[f"src.{name}"] = mod
        return mod
    raise AttributeError(f"module 'src' has no attribute '{name}'")
