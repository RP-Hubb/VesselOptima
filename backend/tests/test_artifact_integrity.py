"""
VesselOptima — Tests for Forecast Model Artifact Cryptographic Integrity (DEF-007)

Verifies that model artifacts undergo mandatory SHA-256 checksum verification
prior to deserialization, preventing execution of corrupted or tampered weights.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import numpy as np

import pandas as pd
from app.engines.forecast.artifacts import ForecastArtifactService, compute_sha256
from app.engines.forecast.evaluation import ModelEvaluationResult, ValidationMetrics
from app.engines.forecast.models import NaivePersistenceModel


def test_artifact_checksum_verification_success(tmp_path: Path):
    """Artifacts with matching SHA-256 checksums load cleanly."""
    service = ForecastArtifactService(base_dir=tmp_path)
    model = NaivePersistenceModel()
    model.fit(pd.Series([10.0, 12.0, 14.0]))

    eval_result = ModelEvaluationResult(
        model_name="NaivePersistence",
        metrics=ValidationMetrics(mae=1.5, rmse=2.0, smape=5.0, directional_accuracy=0.8, total_eval_points=7),
        residuals=[-0.5] * 7,
    )

    metadata = service.save_artifact(
        model=model,
        best_eval=eval_result,
        all_evals={"NaivePersistence": eval_result},
        target="indices",
        series_id="INDEX_TEST",
        data_info={"unit": "POINTS", "start_date": "2024-01-01", "end_date": "2024-06-01", "rows": 180},
    )

    # Load artifact should succeed
    loaded_model, loaded_meta = service.load_artifact("indices", "INDEX_TEST", "v1.0.0")
    assert loaded_model.name == "NaivePersistence"
    assert loaded_meta["artifact_hash"] == metadata["artifact_hash"]


def test_artifact_tamper_detection_aborts_deserialization(tmp_path: Path):
    """Tampered model.joblib bytes mismatch the recorded SHA-256 in metadata and abort loading."""
    service = ForecastArtifactService(base_dir=tmp_path)
    model = NaivePersistenceModel()
    model.fit(pd.Series([10.0, 12.0, 14.0]))

    eval_result = ModelEvaluationResult(
        model_name="NaivePersistence",
        metrics=ValidationMetrics(mae=1.5, rmse=2.0, smape=5.0, directional_accuracy=0.8, total_eval_points=7),
        residuals=[-0.5] * 7,
    )

    service.save_artifact(
        model=model,
        best_eval=eval_result,
        all_evals={"NaivePersistence": eval_result},
        target="indices",
        series_id="INDEX_TAMPER",
        data_info={"unit": "POINTS", "start_date": "2024-01-01", "end_date": "2024-06-01", "rows": 180},
    )

    # Tamper with model.joblib
    model_path = tmp_path / "indices" / "INDEX_TAMPER" / "v1.0.0" / "model.joblib"
    with open(model_path, "ab") as f:
        f.write(b"\x00\x00\x00CORRUPT_BYTES")

    # Attempting to load MUST raise ValueError before deserialization
    with pytest.raises(ValueError, match="Artifact integrity violation: SHA-256 mismatch"):
        service.load_artifact("indices", "INDEX_TAMPER", "v1.0.0")


def test_artifact_missing_file_raises_not_found(tmp_path: Path):
    """Missing model or metadata files raise FileNotFoundError."""
    service = ForecastArtifactService(base_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        service.load_artifact("indices", "NON_EXISTENT_SERIES", "v1.0.0")
