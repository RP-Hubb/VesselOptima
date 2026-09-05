"""
VesselOptima — Local Forecast Model Artifact Registry & Persistence

Manages deterministic persistence of trained forecast model artifacts,
metadata, metrics, and SHA-256 manifests under models/forecast/<target>/<series_id>/<version>/.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib

from app.core.config import settings
from app.core.logging import get_logger
from app.engines.forecast.evaluation import ModelEvaluationResult
from app.engines.forecast.models import BaseForecastModel

logger = get_logger("engines.forecast.artifacts")


def compute_sha256(filepath: Path) -> str:
    """Computes SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


class ForecastArtifactService:
    """Handles saving, loading, and auditing of local forecast model artifacts."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir:
            self.base_dir = base_dir
        else:
            # Check configured dir or default to repo models/forecast/
            repo_root = Path(__file__).resolve().parents[4]
            self.base_dir = repo_root / "models" / "forecast"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_artifact(
        self,
        target: str,
        series_id: str,
        model: BaseForecastModel,
        best_eval: ModelEvaluationResult,
        all_evals: Dict[str, ModelEvaluationResult],
        data_info: Dict[str, Any],
        model_version: str = "v1.0.0",
        seed: int = 20260905,
    ) -> Dict[str, Any]:
        """
        Persists model weights, metadata, comparison metrics, and manifest.
        """
        artifact_dir = self.base_dir / target / series_id / model_version
        artifact_dir.mkdir(parents=True, exist_ok=True)

        model_path = artifact_dir / "model.joblib"
        metadata_path = artifact_dir / "metadata.json"
        metrics_path = artifact_dir / "metrics.json"
        manifest_path = artifact_dir / "manifest.json"

        # 1. Save Model binary
        joblib.dump(model, model_path)
        model_hash = compute_sha256(model_path)

        # 2. Save Metrics comparison JSON
        metrics_data = {
            "selected_model": model.name,
            "selected_metrics": asdict(best_eval.metrics),
            "all_candidates": {
                k: asdict(v.metrics) for k, v in all_evals.items()
            },
        }
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics_data, f, indent=2)

        # 3. Save Metadata JSON
        metadata = {
            "model_id": f"forecast_{target}_{series_id}_{model_version}",
            "model_version": model_version,
            "target": target,
            "series_id": series_id,
            "target_unit": data_info.get("unit", "POINTS"),
            "frequency": "DAILY",
            "training_start": data_info.get("start_date"),
            "training_end": data_info.get("end_date"),
            "total_observations": data_info.get("rows"),
            "forecast_horizons": [7, 14, 30],
            "features": ["lag_1", "lag_2", "lag_3", "lag_7", "lag_14", "lag_30", "rolling_mean_7", "rolling_std_7", "rolling_mean_14", "rolling_mean_30", "dayofweek", "month", "dayofyear"],
            "feature_version": "1.0.0",
            "validation_method": "expanding_window_walk_forward",
            "validation_folds": 3,
            "selected_model": model.name,
            "selected_metrics": asdict(best_eval.metrics),
            "provenance": data_info.get("provenance", "SYNTHETIC"),
            "source_dataset": f"{target}/{series_id}",
            "package_id": "demo-v1",
            "package_version": "1.0.0",
            "random_seed": seed,
            "created_at": "2026-09-05T00:00:00Z",
            "artifact_hash": model_hash,
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # 4. Save Artifact Manifest
        manifest = {
            "files": [
                {"file": "model.joblib", "sha256": model_hash},
                {"file": "metadata.json", "sha256": compute_sha256(metadata_path)},
                {"file": "metrics.json", "sha256": compute_sha256(metrics_path)},
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Saved forecast artifact to {artifact_dir} with hash {model_hash}")
        return metadata

    def load_artifact(
        self,
        target: str,
        series_id: str,
        model_version: str = "v1.0.0",
    ) -> Tuple[BaseForecastModel, Dict[str, Any]]:
        """Loads model weights and metadata from artifact directory."""
        artifact_dir = self.base_dir / target / series_id / model_version
        model_path = artifact_dir / "model.joblib"
        metadata_path = artifact_dir / "metadata.json"

        if not model_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(f"Model artifact not found at: {artifact_dir}")

        model = joblib.load(model_path)
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        return model, metadata

    def list_registry(self) -> List[Dict[str, Any]]:
        """Lists all registered models in the local artifact directory."""
        registry = []
        for meta_path in self.base_dir.rglob("metadata.json"):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    registry.append(data)
            except Exception as e:
                logger.warning(f"Failed to read metadata at {meta_path}: {e}")
        return sorted(registry, key=lambda x: (x["target"], x["series_id"]))
