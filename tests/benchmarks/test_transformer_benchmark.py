"""Synthetic unit tests for M16.4 transformer vs. TF-IDF+SVD benchmark helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.benchmarks.transformer_benchmark import (
    build_fused_coordinates,
    compute_retrieval_alignment,
    evaluate_representation,
    l2_normalize_rows,
    profile_encoder_latency_memory,
    reduce_embeddings_train_only,
)


def _synthetic_frame(n_rows: int, start_idx: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    partitions = ["web_backend", "design_creative", "devops_cloud"]
    return pd.DataFrame(
        {
            "industry_partition": [partitions[i % len(partitions)] for i in range(n_rows)],
            "target_rate": rng.uniform(1500.0, 9000.0, size=n_rows),
            "market_saturation_score": rng.uniform(0.1, 0.9, size=n_rows),
            "raw_description": [f"Synthetic project description {start_idx + i}" for i in range(n_rows)],
        },
        index=np.arange(start_idx, start_idx + n_rows, dtype=int),
    )


def test_build_fused_coordinates_supports_53d_and_387d() -> None:
    meta = np.full((6, 3), 0.5, dtype=float)
    fused_53 = build_fused_coordinates(np.ones((6, 50), dtype=float), meta)
    fused_387 = build_fused_coordinates(np.ones((6, 384), dtype=float), meta)

    assert fused_53.shape == (6, 53)
    assert fused_387.shape == (6, 387)

    with pytest.raises(ValueError, match="Non-finite"):
        bad = np.ones((6, 50), dtype=float)
        bad[0, 0] = np.nan
        build_fused_coordinates(bad, meta)


def test_reduce_embeddings_train_only_svd_and_pca() -> None:
    rng = np.random.default_rng(42)
    train_384 = l2_normalize_rows(rng.normal(size=(80, 384)))
    val_384 = l2_normalize_rows(rng.normal(size=(20, 384)))
    test_384 = l2_normalize_rows(rng.normal(size=(25, 384)))

    for method in ("svd", "pca"):
        tr, va, te, var_sum = reduce_embeddings_train_only(train_384, val_384, test_384, method=method, n_components=50)
        assert tr.shape == (80, 50)
        assert va.shape == (20, 50)
        assert te.shape == (25, 50)
        assert 0.0 < var_sum <= 1.000001


def test_evaluate_representation_and_retrieval_alignment() -> None:
    rng = np.random.default_rng(7)
    train_df = _synthetic_frame(30, 0, seed=1)
    val_df = _synthetic_frame(12, 100, seed=2)
    test_df = _synthetic_frame(12, 200, seed=3)

    train_384 = l2_normalize_rows(rng.normal(size=(30, 384)))
    val_384 = l2_normalize_rows(rng.normal(size=(12, 384)))
    test_384 = l2_normalize_rows(rng.normal(size=(12, 384)))

    train_meta = rng.uniform(0.0, 1.0, size=(30, 3))
    val_meta = rng.uniform(0.0, 1.0, size=(12, 3))
    test_meta = rng.uniform(0.0, 1.0, size=(12, 3))

    res, val_peers, test_peers = evaluate_representation(
        "minilm_l6_v2_384d",
        train_384,
        val_384,
        test_384,
        train_meta,
        val_meta,
        test_meta,
        train_df,
        val_df,
        test_df,
        k=5,
    )
    assert res["text_dimensions"] == 384
    assert res["hybrid_dimensions"] == 387
    assert res["validation"]["invariants_ok"] is True
    assert res["test_oot"]["invariants_ok"] is True
    assert len(val_peers) == 12 and len(test_peers) == 12

    idx_to_pos = {int(idx): pos for pos, idx in enumerate(train_df.index.tolist())}
    align = compute_retrieval_alignment(val_384, train_384, idx_to_pos, val_peers, val_peers)
    assert align["queries"] == 12
    assert align["mean_top5_jaccard_vs_tfidf"] == 1.0
    assert -1.0 <= align["mean_top5_semantic_cosine"] <= 1.0


def test_profile_encoder_latency_memory_with_stub() -> None:
    def _load() -> callable:
        return lambda text: np.full((1, 50), float(len(text)), dtype=np.float32)

    prof = profile_encoder_latency_memory(
        "stub_encoder",
        _load,
        ["alpha beta gamma", "delta epsilon"],
        artifact_disk_mb=1.25,
        warmup=2,
        iterations=10,
    )
    assert prof.iterations == 10
    assert prof.p50_ms <= prof.p95_ms <= prof.p99_ms
    assert prof.artifact_disk_mb == 1.25
    assert prof.tracemalloc_peak_mb >= 0.0
