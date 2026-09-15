"""Model-side runtime controls for UC10 manual retraining and UC11 tuning."""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import numpy as np

from src.api_contracts import GridSearchConfigDTO


@dataclass(frozen=True)
class GridSearchConfig:
    k_neighbors: tuple[int, ...] = (1, 3, 5, 7, 10)
    text_weight: float = 1.0
    metadata_weight: float = 1.0
    idw_epsilon: float = 1e-9
    minimum_partition_size: int = 1
    allow_fallback: bool = True

    @classmethod
    def from_dto(cls, config: GridSearchConfigDTO) -> "GridSearchConfig":
        return cls(
            k_neighbors=tuple(config.k_neighbors),
            text_weight=float(config.text_weight),
            metadata_weight=float(config.metadata_weight),
            idw_epsilon=float(config.idw_epsilon),
            minimum_partition_size=int(config.minimum_partition_size),
            allow_fallback=bool(config.allow_fallback),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["k_neighbors"] = list(self.k_neighbors)
        return payload


class GridSearchStore:
    def __init__(self, path: str = os.path.join("artifacts", "mlops_grid_search.json")) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._config = self._load()

    def _load(self) -> GridSearchConfig:
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return GridSearchConfig.from_dto(GridSearchConfigDTO.model_validate(payload))
        except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
            return GridSearchConfig()

    def get(self) -> GridSearchConfig:
        with self._lock:
            return self._config

    def update(self, config: GridSearchConfigDTO) -> GridSearchConfig:
        resolved = GridSearchConfig.from_dto(config)
        with self._lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            temporary_path = f"{self.path}.{uuid.uuid4().hex}.tmp"
            with open(temporary_path, "w", encoding="utf-8") as handle:
                json.dump(resolved.to_dict(), handle, indent=2, sort_keys=True)
            os.replace(temporary_path, self.path)
            self._config = resolved
            return resolved


class MLOpsService:
    """Coordinates safe tuning updates and serialized artifact publication."""

    def __init__(
        self,
        artifact_dir: str = "artifacts",
        grid_store: Optional[GridSearchStore] = None,
        retrain_runner: Optional[Callable[[str, GridSearchConfig], Dict[str, Any]]] = None,
    ) -> None:
        self.artifact_dir = artifact_dir
        self.grid_store = grid_store or GridSearchStore(os.path.join(artifact_dir, "mlops_grid_search.json"))
        self.retrain_runner = retrain_runner or self._build_environment_runner()
        self._retrain_lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _build_environment_runner() -> Optional[Callable[[str, GridSearchConfig], Dict[str, Any]]]:
        harmonized_path = os.getenv("MLOPS_HARMONIZED_PARQUET", "").strip()
        macro_lookup_path = os.getenv("MLOPS_MACRO_LOOKUP", "").strip()
        if not harmonized_path or not macro_lookup_path:
            return None

        def run(version_dir: str, config: GridSearchConfig) -> Dict[str, Any]:
            from src.train_pipeline import evaluate_and_serialize_training

            summary = evaluate_and_serialize_training(
                harmonized_parquet_path=harmonized_path,
                macro_lookup_path=macro_lookup_path,
                artifact_dir=version_dir,
                k_neighbors=config.k_neighbors[0],
                enforce_quality_gate=False,
                text_weight=config.text_weight,
                metadata_weight=config.metadata_weight,
                minimum_partition_size=config.minimum_partition_size,
                idw_epsilon=config.idw_epsilon,
                allow_fallback=config.allow_fallback,
            )
            return {
                "input_rows": summary.get("input_rows"),
                "quality_gate": summary.get("quality_gate"),
                "artifact_dir": version_dir,
            }

        return run

    def get_tuning(self) -> GridSearchConfig:
        return self.grid_store.get()

    def update_tuning(self, config: GridSearchConfigDTO) -> GridSearchConfig:
        return self.grid_store.update(config)

    def weighted_hybrid_coordinates(self, text_vector: Any, metadata_vector: Any) -> np.ndarray:
        """Apply the active empirical feature-block weights before spatial search."""
        config = self.get_tuning()
        text = np.asarray(text_vector, dtype=float).reshape(-1)
        metadata = np.asarray(metadata_vector, dtype=float).reshape(-1)
        if text.size != 50 or metadata.size != 3:
            raise ValueError("weighted hybrid coordinates require a 50-D text vector and 3-D metadata vector")
        if not np.all(np.isfinite(text)) or not np.all(np.isfinite(metadata)):
            raise ValueError("feature vectors must be finite")
        return np.concatenate([text * config.text_weight, metadata * config.metadata_weight])

    def job_status(self, job_id: str) -> Dict[str, Any]:
        return dict(self._jobs.get(job_id, {"job_id": job_id, "status": "unknown"}))

    def trigger_retrain(self) -> Dict[str, Any]:
        if not self._retrain_lock.acquire(blocking=False):
            return {"job_id": "", "status": "busy", "artifact_version": None, "error": "retraining already running"}

        job_id = uuid.uuid4().hex
        version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + job_id[:8]
        version_dir = os.path.join(self.artifact_dir, "versions", version)
        job = {"job_id": job_id, "status": "running", "artifact_version": version, "error": None}
        self._jobs[job_id] = job
        try:
            if self.retrain_runner is None:
                raise RuntimeError("No retrain runner configured; set training inputs before triggering retraining")
            os.makedirs(version_dir, exist_ok=False)
            result = self.retrain_runner(version_dir, self.get_tuning())
            manifest = {"job_id": job_id, "artifact_version": version, "result": result}
            manifest_path = os.path.join(self.artifact_dir, "active_model.json.tmp")
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(manifest, handle, indent=2, sort_keys=True)
            os.replace(manifest_path, os.path.join(self.artifact_dir, "active_model.json"))
            job.update({"status": "succeeded", "result": result})
        except Exception as exc:
            job.update({"status": "failed", "error": str(exc)})
        finally:
            self._retrain_lock.release()
        return dict(job)

