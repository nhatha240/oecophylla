from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
from sklearn.pipeline import Pipeline

from .model import FEATURE_COLUMNS, records_to_matrix

ARTIFACT_SCHEMA_VERSION = "recommendation-model-artifact-v1"
MODEL_FILENAME = "model.joblib"
MANIFEST_FILENAME = "manifest.json"


class ArtifactIntegrityError(ValueError):
    """Raised when a model artifact is incomplete, incompatible, or corrupt."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class LoadedArtifact:
    pipeline: Pipeline
    manifest: Mapping[str, Any]

    def predict_scores(self, records: Sequence[Mapping[str, Any]]) -> list[float]:
        if not records:
            return []
        matrix = records_to_matrix(records)
        probabilities = self.pipeline.predict_proba(matrix)[:, 1]
        return [float(value) for value in probabilities]


def load_artifact(directory: Path) -> LoadedArtifact:
    manifest_path = directory / MANIFEST_FILENAME
    model_path = directory / MODEL_FILENAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactIntegrityError(f"invalid artifact manifest: {error}") from error

    if manifest.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ArtifactIntegrityError("unsupported artifact schema version")
    if tuple(manifest.get("feature_columns", ())) != FEATURE_COLUMNS:
        raise ArtifactIntegrityError("artifact feature schema does not match runtime")
    try:
        expected_checksum = manifest["files"][MODEL_FILENAME]["sha256"]
    except (KeyError, TypeError) as error:
        raise ArtifactIntegrityError(
            "model checksum is missing from manifest"
        ) from error
    if not model_path.is_file():
        raise ArtifactIntegrityError("model file is missing")
    if sha256_file(model_path) != expected_checksum:
        raise ArtifactIntegrityError("model checksum mismatch")

    try:
        pipeline = joblib.load(model_path)
    except Exception as error:
        raise ArtifactIntegrityError(f"model cannot be loaded: {error}") from error
    if not isinstance(pipeline, Pipeline):
        raise ArtifactIntegrityError("model payload is not a sklearn Pipeline")
    return LoadedArtifact(pipeline=pipeline, manifest=manifest)
