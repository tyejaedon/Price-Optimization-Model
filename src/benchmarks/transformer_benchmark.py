"""M16.4 (Optional): TF-IDF + TruncatedSVD vs. Sentence Transformers benchmark.

Evaluates the production 50D TF-IDF + TruncatedSVD pipeline against
``sentence-transformers/all-MiniLM-L6-v2`` (384D raw and 50D SVD/PCA-reduced)
across semantic retrieval alignment, downstream rate regression accuracy on
chronological validation and OOT test windows, and single-threaded CPU latency,
memory footprint, and artifact disk size.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import shutil
import statistics
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence, cast

import numpy as np
import pandas as pd
import psutil
import sklearn
from sklearn.decomposition import PCA, TruncatedSVD

from src.benchmarks.inference_safe_benchmark import _split_population
from src.data.ingest_multisource import BILATERAL_ALPHA
from src.engine.interval_synthesizer import synthesize_corridor
from src.engine.macro_arbitrage import ContinuousMetadataNormalizer
from src.engine.spatial_engine import (
    DEFAULT_IDW_EPSILON,
    DEFAULT_MIN_PARTITION_SIZE,
    DomainPartitionedKDTreeIndexer,
)
from src.nlp.nlp_pipeline import TextFeatureReducer, ensure_text_dimensions
from src.training.train_pipeline import (
    DEFAULT_HARMONIZED_PARQUET,
    DEFAULT_IDW_NEIGHBORS,
    _build_category_mean_baseline,
    _metric_summary,
    _predict_category_mean_baseline,
    load_harmonized_parquet,
)

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_OUTPUT_DIR = "reports/m16_transformer_benchmark"
DEFAULT_VALIDATION_CUTOFF = "2024-02-20T00:00:00+00:00"
DEFAULT_TEST_CUTOFF = "2024-02-22T00:00:00+00:00"
DEFAULT_REDUCED_DIM = 50
DEFAULT_WARMUP_DOCS = 10
DEFAULT_LATENCY_DOCS = 100

POLYSEMY_PROBES: tuple[dict[str, str], ...] = (
    {
        "label": "python_backend_api",
        "industry_partition": "web_backend",
        "query": "Build a scalable Python FastAPI and PostgreSQL REST microservice with Docker and Redis caching.",
    },
    {
        "label": "python_data_etl",
        "industry_partition": "data_engineering",
        "query": "Develop a Python pandas and PySpark ETL data pipeline ingesting parquet files into BigQuery.",
    },
    {
        "label": "react_web_dashboard",
        "industry_partition": "web_frontend",
        "query": "Create a responsive React TypeScript analytics dashboard with Tailwind CSS and REST API integration.",
    },
    {
        "label": "cloud_devops_iac",
        "industry_partition": "devops_cloud",
        "query": "Configure AWS EKS Kubernetes cluster using Terraform Infrastructure as Code and GitHub Actions CI/CD.",
    },
    {
        "label": "cloud_accounting_erp",
        "industry_partition": "finance_accounting",
        "query": "Manage cloud accounting migration to QuickBooks Online, bank reconciliation, and monthly VAT filings.",
    },
    {
        "label": "brand_ui_design",
        "industry_partition": "design_creative",
        "query": "Design a modern SaaS brand identity, Figma design system, and interactive mobile onboarding screens.",
    },
)


@dataclass(frozen=True)
class LatencyMemoryProfile:
    """Single-threaded CPU latency and memory measurement for one text encoder."""

    name: str
    iterations: int
    warmup: int
    cold_start_ms: float
    mean_ms: float
    min_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    throughput_docs_per_sec: float
    tracemalloc_peak_mb: float
    rss_before_mb: float
    rss_after_load_mb: float
    rss_delta_load_mb: float
    rss_after_infer_mb: float
    artifact_disk_mb: float


def configure_single_thread_env() -> None:
    """Pin BLAS/OMP/MKL environment variables to single-threaded execution."""
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[var] = "1"


def l2_normalize_rows(matrix: np.ndarray) -> np.ndarray:
    """Return row-wise L2-normalized float32 embeddings with zero-norm safety."""
    arr = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    safe_norms = np.where(norms > 1e-12, norms, 1.0)
    return arr / safe_norms


def build_fused_coordinates(text_vectors: np.ndarray, metadata_vectors: np.ndarray) -> np.ndarray:
    """Concatenate text embeddings (N, d) and 3D normalized metadata (N, 3)."""
    text_arr = np.asarray(text_vectors, dtype=np.float64)
    meta_arr = np.asarray(metadata_vectors, dtype=np.float64)
    if text_arr.ndim != 2 or meta_arr.ndim != 2:
        raise ValueError("Expected 2D text and metadata arrays.")
    if text_arr.shape[0] != meta_arr.shape[0] or meta_arr.shape[1] != 3:
        raise ValueError(f"Incompatible shapes for fusion: text={text_arr.shape}, meta={meta_arr.shape}.")
    fused = np.concatenate((text_arr, meta_arr), axis=1)
    if not np.isfinite(fused).all():
        raise ValueError("Non-finite values encountered in fused coordinates.")
    return fused


def reduce_embeddings_train_only(
    train_embeddings: np.ndarray,
    val_embeddings: np.ndarray,
    test_embeddings: np.ndarray,
    method: str = "svd",
    n_components: int = DEFAULT_REDUCED_DIM,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Fit SVD or PCA strictly on training embeddings and project all splits."""
    effective_dim = min(int(n_components), train_embeddings.shape[0] - 1, train_embeddings.shape[1])
    if effective_dim < 1:
        raise ValueError("Insufficient samples or dimensions for dimensionality reduction.")
    if method == "svd":
        reducer: TruncatedSVD | PCA = TruncatedSVD(n_components=effective_dim, random_state=random_state)
    elif method == "pca":
        reducer = PCA(n_components=effective_dim, random_state=random_state)
    else:
        raise ValueError(f"Unsupported reduction method '{method}'. Expected 'svd' or 'pca'.")

    train_red = ensure_text_dimensions(reducer.fit_transform(train_embeddings), expected_dimensions=n_components)
    val_red = ensure_text_dimensions(reducer.transform(val_embeddings), expected_dimensions=n_components)
    test_red = ensure_text_dimensions(reducer.transform(test_embeddings), expected_dimensions=n_components)
    explained = float(np.sum(reducer.explained_variance_ratio_))
    return train_red, val_red, test_red, round(explained, 6)


def _evaluate_split_predictions(
    indexer: DomainPartitionedKDTreeIndexer,
    vectors: np.ndarray,
    frame: pd.DataFrame,
    k: int = DEFAULT_IDW_NEIGHBORS,
) -> tuple[dict[str, Any], list[list[int]]]:
    """Predict rates and FR-06 corridors on a held-out split."""
    y_true = frame["target_rate"].to_numpy(dtype=float)
    saturations = frame["market_saturation_score"].to_numpy(dtype=float)
    industries = frame["industry_partition"].astype(str).tolist()

    preds = np.empty(len(frame), dtype=float)
    widths = np.empty(len(frame), dtype=float)
    peer_indices: list[list[int]] = []
    fallback_count = 0
    invariants_ok = True

    for idx, (vec, ind, sat) in enumerate(zip(vectors, industries, saturations)):
        res = indexer.predict_base_rate(vec, ind, k=k, epsilon=DEFAULT_IDW_EPSILON)
        base = float(res["base_predicted_rate"])
        peer_std = float(res["peer_stddev"])
        corridor = synthesize_corridor(base, peer_std, float(sat))
        min_q = float(corridor["min_quoted_rate"])
        max_q = float(corridor["max_quoted_rate"])
        if min_q < 0.0 or max_q < min_q:
            invariants_ok = False
        preds[idx] = base
        widths[idx] = max_q - min_q
        peer_indices.append([int(p["peer_index"]) for p in res["nearest_neighbors"]])
        if res["fallback_triggered"]:
            fallback_count += 1

    metrics = _metric_summary(y_true, preds)
    metrics["mean_bias_kes"] = round(float(np.mean(preds - y_true)), 6)
    metrics["corridor_mean_width_kes"] = round(float(np.mean(widths)), 6)
    metrics["corridor_median_width_kes"] = round(float(np.median(widths)), 6)
    metrics["corridor_p95_width_kes"] = round(float(np.percentile(widths, 95)), 6)
    metrics["fallback_count"] = int(fallback_count)
    metrics["invariants_ok"] = bool(invariants_ok)
    metrics["rows"] = int(len(frame))
    return metrics, peer_indices


def evaluate_representation(
    name: str,
    train_text: np.ndarray,
    val_text: np.ndarray,
    test_text: np.ndarray,
    train_meta: np.ndarray,
    val_meta: np.ndarray,
    test_meta: np.ndarray,
    train_frame: pd.DataFrame,
    val_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    k: int = DEFAULT_IDW_NEIGHBORS,
) -> tuple[dict[str, Any], list[list[int]], list[list[int]]]:
    """Fit a KD-tree on train fused coordinates and score validation and OOT test."""
    text_dim = int(train_text.shape[1])
    hybrid_dim = text_dim + 3
    train_vecs = build_fused_coordinates(train_text, train_meta)
    val_vecs = build_fused_coordinates(val_text, val_meta)
    test_vecs = build_fused_coordinates(test_text, test_meta)

    indexer = DomainPartitionedKDTreeIndexer(
        minimum_partition_size=DEFAULT_MIN_PARTITION_SIZE,
        vector_dimensions=hybrid_dim,
    )
    indexer.fit(
        hybrid_vectors=train_vecs,
        industry_partitions=train_frame["industry_partition"].astype(str).tolist(),
        record_indices=train_frame.index.to_numpy(dtype=int),
        verified_rates=train_frame["target_rate"].to_numpy(dtype=float),
    )

    val_metrics, val_peers = _evaluate_split_predictions(indexer, val_vecs, val_frame, k=k)
    test_metrics, test_peers = _evaluate_split_predictions(indexer, test_vecs, test_frame, k=k)

    result = {
        "representation": name,
        "text_dimensions": text_dim,
        "hybrid_dimensions": hybrid_dim,
        "validation": val_metrics,
        "test_oot": test_metrics,
    }
    return result, val_peers, test_peers


def compute_retrieval_alignment(
    query_semantic_embeddings: np.ndarray,
    train_semantic_embeddings: np.ndarray,
    train_index_to_pos: Mapping[int, int],
    candidate_peers: Sequence[Sequence[int]],
    reference_peers: Sequence[Sequence[int]] | None = None,
) -> dict[str, Any]:
    """Measure semantic cosine alignment in MiniLM space and peer Jaccard overlap."""
    query_norm = l2_normalize_rows(query_semantic_embeddings)
    train_norm = l2_normalize_rows(train_semantic_embeddings)

    mean_cosines: list[float] = []
    top1_cosines: list[float] = []
    jaccards: list[float] = []

    for row_idx, peer_ids in enumerate(candidate_peers):
        positions = [train_index_to_pos[pid] for pid in peer_ids if pid in train_index_to_pos]
        if positions:
            sims = train_norm[positions] @ query_norm[row_idx]
            mean_cosines.append(float(np.mean(sims)))
            top1_cosines.append(float(sims[0]))
        if reference_peers is not None:
            ref_set = set(reference_peers[row_idx])
            cand_set = set(peer_ids)
            union = ref_set | cand_set
            jaccards.append(len(ref_set & cand_set) / len(union) if union else 1.0)

    return {
        "queries": len(candidate_peers),
        "mean_top5_semantic_cosine": round(float(np.mean(mean_cosines)), 6) if mean_cosines else None,
        "mean_top1_semantic_cosine": round(float(np.mean(top1_cosines)), 6) if top1_cosines else None,
        "mean_top5_jaccard_vs_tfidf": round(float(np.mean(jaccards)), 6) if jaccards else None,
    }


def profile_encoder_latency_memory(
    name: str,
    load_fn: Callable[[], Callable[[str], np.ndarray]],
    texts: Sequence[str],
    artifact_disk_mb: float,
    warmup: int = DEFAULT_WARMUP_DOCS,
    iterations: int = DEFAULT_LATENCY_DOCS,
) -> LatencyMemoryProfile:
    """Measure cold-start time, single-doc latency percentiles, tracemalloc, and RSS."""
    proc = psutil.Process(os.getpid())
    gc.collect()
    rss_before = proc.memory_info().rss / (1024 * 1024)

    tracemalloc.start()
    t0 = time.perf_counter()
    encode_single = load_fn()
    cold_start_ms = (time.perf_counter() - t0) * 1000.0
    rss_after_load = proc.memory_info().rss / (1024 * 1024)

    sample_texts = [str(t) for t in texts]
    if not sample_texts:
        raise ValueError("At least one sample text is required for profiling.")

    for i in range(warmup):
        _ = encode_single(sample_texts[i % len(sample_texts)])

    latencies_ms: list[float] = []
    for i in range(iterations):
        doc = sample_texts[i % len(sample_texts)]
        start_ns = time.perf_counter_ns()
        _ = encode_single(doc)
        latencies_ms.append((time.perf_counter_ns() - start_ns) / 1_000_000.0)

    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_after_infer = proc.memory_info().rss / (1024 * 1024)

    arr = np.asarray(latencies_ms, dtype=float)
    mean_ms = float(np.mean(arr))
    return LatencyMemoryProfile(
        name=name,
        iterations=iterations,
        warmup=warmup,
        cold_start_ms=round(cold_start_ms, 3),
        mean_ms=round(mean_ms, 3),
        min_ms=round(float(np.min(arr)), 3),
        p50_ms=round(float(np.percentile(arr, 50)), 3),
        p95_ms=round(float(np.percentile(arr, 95)), 3),
        p99_ms=round(float(np.percentile(arr, 99)), 3),
        max_ms=round(float(np.max(arr)), 3),
        throughput_docs_per_sec=round(1000.0 / mean_ms, 3) if mean_ms > 0 else 0.0,
        tracemalloc_peak_mb=round(peak_bytes / (1024 * 1024), 3),
        rss_before_mb=round(rss_before, 3),
        rss_after_load_mb=round(rss_after_load, 3),
        rss_delta_load_mb=round(max(0.0, rss_after_load - rss_before), 3),
        rss_after_infer_mb=round(rss_after_infer, 3),
        artifact_disk_mb=round(float(artifact_disk_mb), 3),
    )


def _dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    if path.is_file():
        return path.stat().st_size / (1024 * 1024)
    total = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return total / (1024 * 1024)


def _encode_minilm_corpus(
    model_name: str,
    train_texts: Sequence[str],
    val_texts: Sequence[str],
    test_texts: Sequence[str],
    cache_dir: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, Any]:
    """Encode or load cached 384D MiniLM embeddings for train/val/test splits."""
    import torch
    from sentence_transformers import SentenceTransformer

    torch.set_num_threads(1)
    cache_dir.mkdir(parents=True, exist_ok=True)
    train_path = cache_dir / "minilm_train_384d.npy"
    val_path = cache_dir / "minilm_val_384d.npy"
    test_path = cache_dir / "minilm_test_384d.npy"

    model = SentenceTransformer(model_name, device="cpu")
    if train_path.exists() and val_path.exists() and test_path.exists():
        train_emb = np.load(train_path)
        val_emb = np.load(val_path)
        test_emb = np.load(test_path)
        if (
            train_emb.shape == (len(train_texts), 384)
            and val_emb.shape == (len(val_texts), 384)
            and test_emb.shape == (len(test_texts), 384)
        ):
            return train_emb, val_emb, test_emb, model

    train_emb = model.encode(list(train_texts), batch_size=64, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    val_emb = model.encode(list(val_texts), batch_size=64, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    test_emb = model.encode(list(test_texts), batch_size=64, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    np.save(train_path, np.asarray(train_emb, dtype=np.float32))
    np.save(val_path, np.asarray(val_emb, dtype=np.float32))
    np.save(test_path, np.asarray(test_emb, dtype=np.float32))
    return np.asarray(train_emb, dtype=np.float32), np.asarray(val_emb, dtype=np.float32), np.asarray(test_emb, dtype=np.float32), model


def _export_and_verify_onnx(model: Any, onnx_dir: Path, sample_texts: Sequence[str]) -> tuple[Path, float]:
    """Export SentenceTransformer backbone to ONNX and verify embedding parity."""
    import onnxruntime as ort
    import torch

    onnx_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = onnx_dir / "minilm_l6_v2.onnx"
    tokenizer = model.tokenizer
    transformer = model[0].auto_model
    transformer.eval()

    if not onnx_path.exists():
        dummy = tokenizer(
            ["benchmark dummy input"],
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        torch.onnx.export(
            transformer,
            (dummy["input_ids"], dummy["attention_mask"], dummy["token_type_ids"]),
            str(onnx_path),
            input_names=["input_ids", "attention_mask", "token_type_ids"],
            output_names=["last_hidden_state"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "seq"},
                "attention_mask": {0: "batch", 1: "seq"},
                "token_type_ids": {0: "batch", 1: "seq"},
                "last_hidden_state": {0: "batch", 1: "seq"},
            },
            opset_version=17,
            do_constant_folding=True,
        )

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    session = ort.InferenceSession(str(onnx_path), sess_options=opts, providers=["CPUExecutionProvider"])

    probe = list(sample_texts[:5])
    pt_emb = model.encode(probe, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    encoded = tokenizer(probe, padding=True, truncation=True, max_length=256, return_tensors="np")
    outputs = session.run(
        None,
        {
            "input_ids": encoded["input_ids"].astype(np.int64),
            "attention_mask": encoded["attention_mask"].astype(np.int64),
            "token_type_ids": encoded["token_type_ids"].astype(np.int64),
        },
    )[0]
    mask = encoded["attention_mask"][..., None].astype(np.float32)
    pooled = (outputs * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
    onnx_emb = l2_normalize_rows(pooled)
    max_abs_diff = float(np.max(np.abs(pt_emb - onnx_emb)))
    return onnx_path, round(max_abs_diff, 7)


def _run_polysemy_probes(
    reducer: TextFeatureReducer,
    normalizer: ContinuousMetadataNormalizer,
    minilm_model: Any,
    train_frame: pd.DataFrame,
    train_tfidf_vecs: np.ndarray,
    train_minilm_vecs: np.ndarray,
    train_minilm_384d: np.ndarray,
) -> list[dict[str, Any]]:
    """Compare top-3 retrieved training peers on curated polysemy/domain queries."""
    tfidf_indexer = DomainPartitionedKDTreeIndexer(vector_dimensions=53)
    tfidf_indexer.fit(
        hybrid_vectors=train_tfidf_vecs,
        industry_partitions=train_frame["industry_partition"].astype(str).tolist(),
        record_indices=train_frame.index.to_numpy(dtype=int),
        verified_rates=train_frame["target_rate"].to_numpy(dtype=float),
    )
    minilm_indexer = DomainPartitionedKDTreeIndexer(vector_dimensions=387)
    minilm_indexer.fit(
        hybrid_vectors=train_minilm_vecs,
        industry_partitions=train_frame["industry_partition"].astype(str).tolist(),
        record_indices=train_frame.index.to_numpy(dtype=int),
        verified_rates=train_frame["target_rate"].to_numpy(dtype=float),
    )

    train_idx_to_pos = {int(idx): pos for pos, idx in enumerate(train_frame.index.tolist())}
    neutral_meta = np.array([[0.5, 0.5, 0.5]], dtype=float)
    probe_texts = [p["query"] for p in POLYSEMY_PROBES]
    probe_minilm_384d = l2_normalize_rows(
        minilm_model.encode(probe_texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    )
    probe_tfidf_50d = ensure_text_dimensions(reducer.transform(probe_texts), expected_dimensions=50)

    probe_results: list[dict[str, Any]] = []
    for i, probe in enumerate(POLYSEMY_PROBES):
        q_tfidf = build_fused_coordinates(probe_tfidf_50d[i : i + 1], neutral_meta)[0]
        q_minilm = build_fused_coordinates(probe_minilm_384d[i : i + 1], neutral_meta)[0]
        res_tfidf = tfidf_indexer.predict_base_rate(q_tfidf, probe["industry_partition"], k=5)
        res_minilm = minilm_indexer.predict_base_rate(q_minilm, probe["industry_partition"], k=5)

        def _summarize_peers(peers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
            items = []
            for p in peers[:3]:
                pid = int(p["peer_index"])
                pos = train_idx_to_pos[pid]
                cos = float(train_minilm_384d[pos] @ probe_minilm_384d[i])
                desc = " ".join(str(train_frame.iloc[pos]["raw_description"]).split())[:120]
                items.append({
                    "verified_rate": round(float(p["verified_rate"]), 2),
                    "semantic_cosine": round(cos, 4),
                    "snippet": desc,
                })
            return items

        probe_results.append({
            "label": probe["label"],
            "industry_partition": probe["industry_partition"],
            "query": probe["query"],
            "tfidf_svd_50d_rate": round(float(res_tfidf["base_predicted_rate"]), 2),
            "minilm_384d_rate": round(float(res_minilm["base_predicted_rate"]), 2),
            "tfidf_top3": _summarize_peers(res_tfidf["nearest_neighbors"]),
            "minilm_top3": _summarize_peers(res_minilm["nearest_neighbors"]),
        })
    return probe_results


def _online_metadata(normalizer: ContinuousMetadataNormalizer, frame: pd.DataFrame) -> np.ndarray:
    return np.vstack([
        normalizer.transform_live_metadata(
            str(row.mentor_country_iso2),
            str(row.client_country_iso2),
            float(row.market_saturation_score),
            float(row.industry_relative_density),
        ).reshape(-1)
        for row in frame.itertuples(index=False)
    ])


def run_benchmark(
    harmonized_parquet: str,
    macro_lookup: str,
    output_dir: str,
    validation_cutoff: str = DEFAULT_VALIDATION_CUTOFF,
    test_cutoff: str = DEFAULT_TEST_CUTOFF,
    model_name: str = DEFAULT_MODEL_NAME,
    latency_docs: int = DEFAULT_LATENCY_DOCS,
) -> dict[str, Any]:
    """Execute the full M16.4 TF-IDF+SVD vs. Sentence Transformer benchmark."""
    configure_single_thread_env()
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    cache_dir = out_path / "cache"
    artifacts_dir = out_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    raw_df = load_harmonized_parquet(harmonized_parquet)
    split, _ = _split_population(raw_df, validation_cutoff, test_cutoff)

    normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup, alpha=BILATERAL_ALPHA)
    train_meta = normalizer.fit_transform(cast(list[dict[str, Any]], split.train.to_dict(orient="records")))
    val_meta = _online_metadata(normalizer, split.validation)
    test_meta = _online_metadata(normalizer, split.test)

    train_texts = split.train["raw_description"].astype(str).tolist()
    val_texts = split.validation["raw_description"].astype(str).tolist()
    test_texts = split.test["raw_description"].astype(str).tolist()

    # 1. Production 50D TF-IDF + SVD
    reducer = TextFeatureReducer(
        n_components=DEFAULT_REDUCED_DIM,
        max_features=12000,
        ngram_range=(1, 2),
        min_df=1,
        random_state=42,
        normalize_output=False,
    )
    train_tfidf = ensure_text_dimensions(reducer.fit_transform(train_texts), DEFAULT_REDUCED_DIM)
    val_tfidf = ensure_text_dimensions(reducer.transform(val_texts), DEFAULT_REDUCED_DIM)
    test_tfidf = ensure_text_dimensions(reducer.transform(test_texts), DEFAULT_REDUCED_DIM)

    tfidf_art_dir = artifacts_dir / "tfidf_svd_50d"
    if tfidf_art_dir.exists():
        shutil.rmtree(tfidf_art_dir)
    tfidf_art_dir.mkdir(parents=True, exist_ok=True)
    reducer.save_artifacts(str(tfidf_art_dir))
    normalizer.save_artifacts(str(tfidf_art_dir))
    tfidf_disk_mb = _dir_size_mb(tfidf_art_dir)

    # 2. MiniLM-L6-v2 384D + train-only 50D reductions
    train_384, val_384, test_384, minilm_model = _encode_minilm_corpus(
        model_name, train_texts, val_texts, test_texts, cache_dir
    )
    train_minilm_svd, val_minilm_svd, test_minilm_svd, svd_var = reduce_embeddings_train_only(
        train_384, val_384, test_384, method="svd", n_components=DEFAULT_REDUCED_DIM
    )
    train_minilm_pca, val_minilm_pca, test_minilm_pca, pca_var = reduce_embeddings_train_only(
        train_384, val_384, test_384, method="pca", n_components=DEFAULT_REDUCED_DIM
    )

    # Category mean baseline
    cat_means, global_mean = _build_category_mean_baseline(split.train)
    val_cat_metrics = _metric_summary(
        split.validation["target_rate"].to_numpy(dtype=float),
        _predict_category_mean_baseline(split.validation, cat_means, global_mean),
    )
    test_cat_metrics = _metric_summary(
        split.test["target_rate"].to_numpy(dtype=float),
        _predict_category_mean_baseline(split.test, cat_means, global_mean),
    )

    # 3. Evaluate all 4 representations
    eval_tfidf, val_peers_tfidf, test_peers_tfidf = evaluate_representation(
        "tfidf_svd_50d", train_tfidf, val_tfidf, test_tfidf, train_meta, val_meta, test_meta,
        split.train, split.validation, split.test,
    )
    eval_minilm_384, val_peers_384, test_peers_384 = evaluate_representation(
        "minilm_l6_v2_384d", train_384, val_384, test_384, train_meta, val_meta, test_meta,
        split.train, split.validation, split.test,
    )
    eval_minilm_svd, val_peers_msvd, test_peers_msvd = evaluate_representation(
        "minilm_svd_50d", train_minilm_svd, val_minilm_svd, test_minilm_svd, train_meta, val_meta, test_meta,
        split.train, split.validation, split.test,
    )
    eval_minilm_pca, val_peers_mpca, test_peers_mpca = evaluate_representation(
        "minilm_pca_50d", train_minilm_pca, val_minilm_pca, test_minilm_pca, train_meta, val_meta, test_meta,
        split.train, split.validation, split.test,
    )
    eval_minilm_svd["explained_variance_sum"] = svd_var
    eval_minilm_pca["explained_variance_sum"] = pca_var
    eval_tfidf["explained_variance_sum"] = round(float(reducer.explained_variance_sum() or 0.0), 6)

    # 4. Semantic retrieval alignment (in MiniLM 384D semantic space)
    train_idx_to_pos = {int(idx): pos for pos, idx in enumerate(split.train.index.tolist())}
    retrieval_alignment = {
        "validation": {
            "tfidf_svd_50d": compute_retrieval_alignment(val_384, train_384, train_idx_to_pos, val_peers_tfidf, val_peers_tfidf),
            "minilm_l6_v2_384d": compute_retrieval_alignment(val_384, train_384, train_idx_to_pos, val_peers_384, val_peers_tfidf),
            "minilm_svd_50d": compute_retrieval_alignment(val_384, train_384, train_idx_to_pos, val_peers_msvd, val_peers_tfidf),
            "minilm_pca_50d": compute_retrieval_alignment(val_384, train_384, train_idx_to_pos, val_peers_mpca, val_peers_tfidf),
        },
        "test_oot": {
            "tfidf_svd_50d": compute_retrieval_alignment(test_384, train_384, train_idx_to_pos, test_peers_tfidf, test_peers_tfidf),
            "minilm_l6_v2_384d": compute_retrieval_alignment(test_384, train_384, train_idx_to_pos, test_peers_384, test_peers_tfidf),
            "minilm_svd_50d": compute_retrieval_alignment(test_384, train_384, train_idx_to_pos, test_peers_msvd, test_peers_tfidf),
            "minilm_pca_50d": compute_retrieval_alignment(test_384, train_384, train_idx_to_pos, test_peers_mpca, test_peers_tfidf),
        },
    }

    # 5. Polysemy & domain terminology probes
    train_tfidf_vecs = build_fused_coordinates(train_tfidf, train_meta)
    train_minilm_vecs = build_fused_coordinates(train_384, train_meta)
    polysemy_probes = _run_polysemy_probes(
        reducer, normalizer, minilm_model, split.train, train_tfidf_vecs, train_minilm_vecs, train_384
    )

    # 6. ONNX export & parity check
    onnx_dir = artifacts_dir / "minilm_onnx"
    onnx_path, onnx_max_abs_diff = _export_and_verify_onnx(minilm_model, onnx_dir, val_texts)
    onnx_disk_mb = _dir_size_mb(onnx_dir)
    pt_model_dir = artifacts_dir / "minilm_pytorch"
    if not pt_model_dir.exists():
        minilm_model.save(str(pt_model_dir))
    pt_disk_mb = _dir_size_mb(pt_model_dir)

    # Free heavy corpus model before profiling individual loaders cleanly
    del minilm_model
    gc.collect()

    # 7. Single-threaded CPU latency & memory profiling
    def _load_tfidf() -> Callable[[str], np.ndarray]:
        loaded = TextFeatureReducer.load_artifacts(str(tfidf_art_dir))
        return lambda text: ensure_text_dimensions(loaded.transform([text]), DEFAULT_REDUCED_DIM)

    def _load_minilm_pytorch() -> Callable[[str], np.ndarray]:
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(1)
        st_model = SentenceTransformer(str(pt_model_dir), device="cpu")
        return lambda text: st_model.encode([text], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)

    def _load_minilm_onnx() -> Callable[[str], np.ndarray]:
        import onnxruntime as ort
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(str(pt_model_dir))
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        session = ort.InferenceSession(str(onnx_path), sess_options=opts, providers=["CPUExecutionProvider"])

        def _encode_onnx(text: str) -> np.ndarray:
            enc = tokenizer([text], padding=True, truncation=True, max_length=256, return_tensors="np")
            out = session.run(
                None,
                {
                    "input_ids": enc["input_ids"].astype(np.int64),
                    "attention_mask": enc["attention_mask"].astype(np.int64),
                    "token_type_ids": enc["token_type_ids"].astype(np.int64),
                },
            )[0]
            mask = enc["attention_mask"][..., None].astype(np.float32)
            pooled = (out * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
            return l2_normalize_rows(pooled)

        return _encode_onnx

    profiles = [
        asdict(profile_encoder_latency_memory("tfidf_svd_50d", _load_tfidf, val_texts, tfidf_disk_mb, iterations=latency_docs)),
        asdict(profile_encoder_latency_memory("minilm_pytorch_cpu", _load_minilm_pytorch, val_texts, pt_disk_mb, iterations=latency_docs)),
        asdict(profile_encoder_latency_memory("minilm_onnx_cpu", _load_minilm_onnx, val_texts, onnx_disk_mb, iterations=latency_docs)),
    ]

    report = {
        "metadata": {
            "model_name": model_name,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "sklearn_version": sklearn.__version__,
            "thread_env": {
                "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
                "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
                "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
            },
            "splits": {
                "train": int(len(split.train)),
                "validation": int(len(split.validation)),
                "test_oot": int(len(split.test)),
                "validation_cutoff": validation_cutoff,
                "test_cutoff": test_cutoff,
            },
            "onnx_max_abs_diff_vs_pytorch": onnx_max_abs_diff,
        },
        "category_mean_baseline": {
            "validation": val_cat_metrics,
            "test_oot": test_cat_metrics,
        },
        "regression_results": [eval_tfidf, eval_minilm_384, eval_minilm_svd, eval_minilm_pca],
        "retrieval_alignment": retrieval_alignment,
        "polysemy_probes": polysemy_probes,
        "latency_memory_profiles": profiles,
    }

    report_file = out_path / "benchmark.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M16.4 TF-IDF + SVD vs. Sentence Transformers benchmark.")
    parser.add_argument("--harmonized-parquet", default=DEFAULT_HARMONIZED_PARQUET)
    parser.add_argument("--macro-lookup", default="data/processed/macro_lookup_table.json")
    parser.add_argument("--validation-cutoff", default=DEFAULT_VALIDATION_CUTOFF)
    parser.add_argument("--test-cutoff", default=DEFAULT_TEST_CUTOFF)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--latency-docs", type=int, default=DEFAULT_LATENCY_DOCS)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    report = run_benchmark(
        harmonized_parquet=args.harmonized_parquet,
        macro_lookup=args.macro_lookup,
        output_dir=args.output_dir,
        validation_cutoff=args.validation_cutoff,
        test_cutoff=args.test_cutoff,
        model_name=args.model_name,
        latency_docs=args.latency_docs,
    )
    print(json.dumps({"report": str(Path(args.output_dir) / "benchmark.json"), "profiles": len(report["latency_memory_profiles"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
