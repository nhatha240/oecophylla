from __future__ import annotations

import argparse
import json
import platform
import shutil
import tempfile
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import pyarrow.parquet as pq
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from .artifact import (
    ARTIFACT_SCHEMA_VERSION,
    MANIFEST_FILENAME,
    MODEL_FILENAME,
    sha256_file,
)
from .build_dataset import DATASET_SCHEMA_VERSION, FEATURE_SCHEMA_VERSION
from .model import FEATURE_COLUMNS, build_pipeline, records_to_matrix

MODEL_TYPE = "sklearn-logistic-regression"
DEFAULT_SEED = 20260829
MIN_TRAIN_ROWS = 20
REQUIRED_DATASET_COLUMNS = frozenset(
    {"split", "label", "feature_schema_version", *FEATURE_COLUMNS}
)


class DatasetValidationError(ValueError):
    """Raised when a dataset cannot safely be used for model training."""


def _read_metadata(dataset: Path) -> dict[str, Any]:
    metadata_path = dataset.with_suffix(f"{dataset.suffix}.metadata.json")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetValidationError(f"invalid dataset metadata: {error}") from error
    if metadata.get("dataset_schema_version") != DATASET_SCHEMA_VERSION:
        raise DatasetValidationError("dataset schema version is not supported")
    if metadata.get("feature_schema_versions") != [FEATURE_SCHEMA_VERSION]:
        raise DatasetValidationError("feature schema version is not supported")
    if not isinstance(metadata.get("query_window"), dict):
        raise DatasetValidationError("dataset data window is missing")
    return metadata


def _load_training_rows(
    dataset: Path, metadata: Mapping[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[int]]]:
    try:
        parquet_file = pq.ParquetFile(dataset)
    except (OSError, ValueError) as error:
        raise DatasetValidationError(f"invalid parquet dataset: {error}") from error
    missing = sorted(REQUIRED_DATASET_COLUMNS - set(parquet_file.schema_arrow.names))
    if missing:
        raise DatasetValidationError(f"missing required columns: {', '.join(missing)}")

    selected_columns = ["split", "label", "feature_schema_version", *FEATURE_COLUMNS]
    rows = pq.read_table(dataset, columns=selected_columns).to_pylist()
    if metadata.get("row_count") != len(rows):
        raise DatasetValidationError("dataset row count does not match metadata")
    if any(row["feature_schema_version"] != FEATURE_SCHEMA_VERSION for row in rows):
        raise DatasetValidationError("row feature schema version is not supported")

    records_by_split: dict[str, list[dict[str, Any]]] = {
        "train": [],
        "validation": [],
        "test": [],
    }
    labels_by_split: dict[str, list[int]] = {
        "train": [],
        "validation": [],
        "test": [],
    }
    for row in rows:
        split = row["split"]
        if split not in records_by_split:
            raise DatasetValidationError(f"unsupported temporal split: {split}")
        records_by_split[split].append({name: row[name] for name in FEATURE_COLUMNS})
        labels_by_split[split].append(1 if row["label"] > 0 else 0)
    return records_by_split, labels_by_split


def _validate_population(
    records: Mapping[str, Sequence[Mapping[str, Any]]],
    labels: Mapping[str, Sequence[int]],
    min_train_rows: int,
) -> None:
    if len(records["train"]) < min_train_rows:
        raise DatasetValidationError(
            f"insufficient train rows: need at least {min_train_rows}"
        )
    if len(set(labels["train"])) != 2:
        raise DatasetValidationError("training split must contain both label classes")
    if not records["validation"]:
        raise DatasetValidationError("validation split must not be empty")
    if not records["test"]:
        raise DatasetValidationError("test holdout must not be empty")


def _validation_metrics(
    labels: Sequence[int], scores: Sequence[float]
) -> dict[str, Any]:
    predictions = [int(score >= 0.5) for score in scores]
    metrics: dict[str, Any] = {
        "accuracy": float(accuracy_score(labels, predictions)),
        "positive_rate": float(sum(labels) / len(labels)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "roc_auc": None,
    }
    if len(set(labels)) == 2:
        metrics["roc_auc"] = float(roc_auc_score(labels, scores))
    return metrics


def _dependency_versions() -> dict[str, str]:
    return {
        "joblib": version("joblib"),
        "numpy": version("numpy"),
        "python": platform.python_version(),
        "pyarrow": version("pyarrow"),
        "scikit-learn": version("scikit-learn"),
    }


def _write_artifact(
    pipeline: Any,
    manifest: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        model_path = temporary / MODEL_FILENAME
        joblib.dump(pipeline, model_path, compress=0)
        manifest["files"] = {
            MODEL_FILENAME: {
                "sha256": sha256_file(model_path),
                "size_bytes": model_path.stat().st_size,
            }
        }
        (temporary / MANIFEST_FILENAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.rename(output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def train_from_dataset(
    dataset: Path,
    output: Path,
    *,
    seed: int = DEFAULT_SEED,
    min_train_rows: int = MIN_TRAIN_ROWS,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"artifact output already exists: {output}")
    metadata = _read_metadata(dataset)
    records, labels = _load_training_rows(dataset, metadata)
    _validate_population(records, labels, min_train_rows)

    pipeline = build_pipeline(seed)
    train_matrix = records_to_matrix(records["train"])
    pipeline.fit(train_matrix, labels["train"])
    validation_scores = pipeline.predict_proba(
        records_to_matrix(records["validation"])
    )[:, 1]

    row_counts = dict(sorted((split, len(values)) for split, values in records.items()))
    manifest: dict[str, Any] = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "model_version": output.name,
        "model_type": MODEL_TYPE,
        "seed": seed,
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "label_definition_version": metadata.get("label_definition_version"),
        "target": "label > 0",
        "feature_columns": list(FEATURE_COLUMNS),
        "data_windows": dict(metadata["query_window"]),
        "row_counts": row_counts,
        "training_class_balance": dict(sorted(Counter(labels["train"]).items())),
        "validation_metrics": _validation_metrics(
            labels["validation"], validation_scores
        ),
        "dependency_versions": _dependency_versions(),
        "dataset": {
            "parquet_sha256": sha256_file(dataset),
            "metadata_sha256": sha256_file(
                dataset.with_suffix(f"{dataset.suffix}.metadata.json")
            ),
            "source_code_version": metadata.get("code_version"),
        },
    }
    return _write_artifact(pipeline, manifest, output)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train an immutable recommendation Logistic Regression artifact."
    )
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        manifest = train_from_dataset(args.dataset, args.output, seed=args.seed)
    except (DatasetValidationError, FileExistsError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                "artifact": str(args.output),
                "model_version": manifest["model_version"],
                "model_sha256": manifest["files"][MODEL_FILENAME]["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
