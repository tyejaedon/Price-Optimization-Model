"""Trust boundary for exported demonstration inference artifacts.

The operator must obtain and pin the manifest's SHA-256 through a trusted channel,
outside the artifact directory. Verification compares that external pin with the
manifest bytes and checks each listed file digest before any joblib deserialization.
The manifest does not hash itself, and hashes supplied only by a downloaded bundle
do not authenticate it or make pickle/joblib safe to load.
"""

import hashlib
import json
import os
import re
from typing import Any

from src.macro_arbitrage import (
    DEFAULT_BUNDLED_MACRO_LOOKUP, DEFAULT_FEATURE_NAMES, DEFAULT_INFERENCE_CONFIG_ARTIFACT,
    HYBRID_VECTOR_DIMENSIONS, TEXT_VECTOR_DIMENSIONS,
)
from src.nlp_pipeline import DEFAULT_METADATA_ARTIFACT, DEFAULT_SVD_ARTIFACT, DEFAULT_TFIDF_ARTIFACT
from src.spatial_engine import DEFAULT_KDTREE_ARTIFACT, DEFAULT_KDTREE_METADATA
from src.macro_arbitrage import DEFAULT_SCALER_ARTIFACT, DEFAULT_SCALER_METADATA

MANIFEST_NAME = "artifact_manifest.json"
SCHEMA_VERSION = 1
ARTIFACT_FILES = (
    DEFAULT_INFERENCE_CONFIG_ARTIFACT, DEFAULT_BUNDLED_MACRO_LOOKUP,
    DEFAULT_METADATA_ARTIFACT, DEFAULT_TFIDF_ARTIFACT, DEFAULT_SVD_ARTIFACT,
    DEFAULT_SCALER_METADATA, DEFAULT_SCALER_ARTIFACT,
    DEFAULT_KDTREE_METADATA, DEFAULT_KDTREE_ARTIFACT,
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


def _valid_provenance(dataset_version: Any, source_type: Any, split_policy: Any) -> bool:
    if not isinstance(dataset_version, str) or not VERSION_PATTERN.fullmatch(dataset_version):
        return False
    if not isinstance(source_type, str) or not isinstance(split_policy, str):
        return False
    if source_type not in ("synthetic proxy fixture", "harmonized KES/hour proxy labels; not verified mentor transactions"):
        prefix = "proxy marketplace data: "
        if not source_type.startswith(prefix):
            return False
        labels = source_type[len(prefix):].split(", ")
        allowed = {"upwork_jobs", "upwork_data_scientists", "other/unclassified"}
        if labels != ["unspecified source"] and (not labels or labels != sorted(set(labels)) or not set(labels) <= allowed):
            return False
    return split_policy in ("synthetic fixed fixture", "chronological_out_of_time") or bool(
        re.fullmatch(r"stratified_random_seed_[0-9]+; exploratory, not OOT", split_policy)
    )


def file_sha256(path: str) -> str:
    """Return the SHA-256 digest of a file's exact bytes."""
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _preprocessing(artifact_dir: str) -> dict[str, Any]:
    with open(os.path.join(artifact_dir, DEFAULT_METADATA_ARTIFACT), encoding="utf-8") as handle:
        nlp = json.load(handle)
    with open(os.path.join(artifact_dir, DEFAULT_SCALER_METADATA), encoding="utf-8") as handle:
        metadata = json.load(handle)
    return {
        "text": {key: nlp[key] for key in ("n_components_requested", "n_components_fitted", "max_features",
                                             "ngram_range", "min_df", "normalize_output")},
        "metadata": {key: metadata[key] for key in ("feature_names", "alpha")},
    }


def write_manifest(artifact_dir: str, config: dict[str, Any], *, dataset_version: str,
                   source_type: str, split_policy: str, dataset_sha256: str | None = None) -> str:
    """Write the manifest after fitted files and return its digest for external pinning.

    The returned digest is useful only when its expected value is independently
    trusted; creating a manifest and trusting its own digest is not authentication.
    """
    if not _valid_provenance(dataset_version, source_type, split_policy):
        raise ValueError("Artifact provenance must contain non-sensitive dataset/source/split identifiers")
    if dataset_sha256 is not None and not SHA256_PATTERN.fullmatch(dataset_sha256):
        raise ValueError("Invalid dataset SHA-256")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "model_family": "partitioned_kdtree_idw",
        "feature_schema": {"text_dimensions": TEXT_VECTOR_DIMENSIONS, "metadata_features": list(DEFAULT_FEATURE_NAMES),
                           "hybrid_dimensions": HYBRID_VECTOR_DIMENSIONS},
        "query_policy": {key: config[key] for key in ("k_neighbors", "idw_epsilon", "text_weight", "metadata_weight")},
        "partition_policy": {"minimum_partition_size": config["minimum_partition_size"],
                             "fallback_partition": config["fallback_partition"],
                             "allow_fallback": config["allow_fallback"],
                             "partition_density": config["partition_density"]},
        "preprocessing": _preprocessing(artifact_dir),
        "provenance": {"dataset_version": dataset_version, "source_type": source_type,
                       "split_policy": split_policy, "dataset_sha256": dataset_sha256,
                       "validation_status": "exploratory_not_empirically_approved"},
        "files_sha256": {name: file_sha256(os.path.join(artifact_dir, name)) for name in ARTIFACT_FILES},
    }
    path = os.path.join(artifact_dir, MANIFEST_NAME)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    return file_sha256(path)


def verify_manifest(artifact_dir: str, trusted_sha256: str | None) -> dict[str, Any]:
    """Verify the external manifest pin and listed artifact bytes before joblib loads.

    A valid pin authenticates the exact manifest only when provisioned separately
    from the bundle; the manifest itself has no self-hash and this function does not
    make untrusted pickle/joblib content intrinsically safe.
    """
    if not trusted_sha256 or not SHA256_PATTERN.fullmatch(trusted_sha256):
        raise ValueError("Untrusted artifacts: configure PRICING_ARTIFACT_MANIFEST_SHA256 with a pinned manifest digest")
    path = os.path.join(artifact_dir, MANIFEST_NAME)
    if file_sha256(path) != trusted_sha256:
        raise ValueError("Untrusted artifact manifest: pinned SHA-256 mismatch")
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Incompatible artifact manifest schema version")
    if set(manifest) != {"schema_version", "model_family", "feature_schema", "query_policy",
                         "partition_policy", "preprocessing", "provenance", "files_sha256"}:
        raise ValueError("Incompatible artifact manifest fields")
    if manifest.get("model_family") != "partitioned_kdtree_idw" or manifest.get("feature_schema") != {
        "text_dimensions": TEXT_VECTOR_DIMENSIONS, "metadata_features": list(DEFAULT_FEATURE_NAMES),
        "hybrid_dimensions": HYBRID_VECTOR_DIMENSIONS,
    }:
        raise ValueError("Incompatible artifact model or 53D feature schema")
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("validation_status") != "exploratory_not_empirically_approved" or not all(
        isinstance(provenance.get(key), str) and provenance[key].strip()
        for key in ("dataset_version", "source_type", "split_policy")
    ):
        raise ValueError("Missing or incompatible exploratory artifact provenance")
    if set(provenance) != {"dataset_version", "source_type", "split_policy", "dataset_sha256", "validation_status"}:
        raise ValueError("Incompatible artifact provenance fields")
    if not _valid_provenance(provenance["dataset_version"], provenance["source_type"], provenance["split_policy"]):
        raise ValueError("Invalid or sensitive artifact provenance")
    dataset_digest = provenance.get("dataset_sha256")
    if dataset_digest is not None and (not isinstance(dataset_digest, str) or not SHA256_PATTERN.fullmatch(dataset_digest)):
        raise ValueError("Invalid artifact dataset digest")
    files = manifest.get("files_sha256")
    if not isinstance(files, dict) or set(files) != set(ARTIFACT_FILES):
        raise ValueError("Incomplete artifact manifest file list")
    for name in ARTIFACT_FILES:
        expected = files[name]
        if not isinstance(expected, str) or not SHA256_PATTERN.fullmatch(expected):
            raise ValueError(f"Invalid artifact digest: {name}")
        if file_sha256(os.path.join(artifact_dir, name)) != expected:
            raise ValueError(f"Corrupted artifact: {name} SHA-256 mismatch")
    if manifest.get("preprocessing") != _preprocessing(artifact_dir):
        raise ValueError("Incompatible artifact preprocessing policy")
    return manifest
