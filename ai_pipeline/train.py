from __future__ import annotations

import argparse
import json
import platform
import shutil
import tempfile
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pyarrow.parquet as pq
from sklearn.linear_model import LogisticRegression
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
    NRMS_MODEL_TYPE,
    sha256_file,
)
from .build_dataset import (
    DATASET_SCHEMA_VERSION,
    DATASET_SCHEMA_VERSION_V2,
    FEATURE_SCHEMA_VERSION,
)
from .model import (
    FEATURE_COLUMNS,
    NRMSArchitecture,
    NRMSLikeRanker,
    build_pairwise_examples,
    build_pipeline,
    records_to_matrix,
    train_pairwise_epoch,
)
from .schemas import HISTORY_SCHEMA_VERSION, parse_datetime

MODEL_TYPE = "sklearn-logistic-regression"
DEFAULT_SEED = 20260829
MIN_TRAIN_ROWS = 20
REQUIRED_DATASET_COLUMNS = frozenset(
    {"split", "label", "feature_schema_version", *FEATURE_COLUMNS}
)

NRMS_DEFAULT_EPOCHS = 5
NRMS_LEARNING_RATE = 0.1
NRMS_HISTORY_CAP = 20
NRMS_REQUIRED_ROW_COLUMNS = frozenset(
    {
        "sample_id",
        "request_group",
        "candidate_group",
        "split",
        "served_at",
        "position",
        "click_label",
        "article",
        "history",
        "feed_source",
    }
)


class DatasetValidationError(ValueError):
    """Raised when a dataset cannot safely be used for model training."""


def _peek_metadata(dataset: Path) -> dict[str, Any]:
    metadata_path = dataset.with_suffix(f"{dataset.suffix}.metadata.json")
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetValidationError(f"invalid dataset metadata: {error}") from error


def _read_metadata(dataset: Path) -> dict[str, Any]:
    metadata = _peek_metadata(dataset)
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
    model_object: Any,
    manifest: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        model_path = temporary / MODEL_FILENAME
        joblib.dump(model_object, model_path, compress=0)
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


# --- NRMS-like impression-aware ranker training (T7, dataset schema v2) ---


def _validate_v2_metadata(metadata: Mapping[str, Any]) -> None:
    if metadata.get("dataset_schema_version") != DATASET_SCHEMA_VERSION_V2:
        raise DatasetValidationError("dataset schema version is not supported")
    if metadata.get("history_schema_version") not in (HISTORY_SCHEMA_VERSION, "mind-pre-impression-history-v1"):
        raise DatasetValidationError("history schema version is not supported")
    if not metadata.get("feature_schema_version"):
        raise DatasetValidationError("feature schema version is missing")
    if not metadata.get("label_definition_version"):
        raise DatasetValidationError("label definition version is missing")
    if not metadata.get("encoder_version"):
        raise DatasetValidationError("encoder version is missing")
    dimension = metadata.get("encoder_dimension")
    if not isinstance(dimension, int) or dimension <= 0:
        raise DatasetValidationError("encoder dimension is missing or invalid")
    if not isinstance(metadata.get("query_window"), dict):
        raise DatasetValidationError("dataset data window is missing")


def _read_v2_rows(dataset: Path, metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    try:
        table = pq.read_table(dataset)
    except (OSError, ValueError) as error:
        raise DatasetValidationError(f"invalid parquet dataset: {error}") from error
    missing = sorted(NRMS_REQUIRED_ROW_COLUMNS - set(table.schema.names))
    if missing:
        raise DatasetValidationError(f"missing required columns: {', '.join(missing)}")
    rows = table.to_pylist()
    if metadata.get("row_count") != len(rows):
        raise DatasetValidationError("dataset row count does not match metadata")
    return rows


def _validate_v2_contract(rows: Sequence[Mapping[str, Any]], *, history_schema_version: str = HISTORY_SCHEMA_VERSION) -> None:
    splits_by_request: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        request_group = row.get("request_group")
        split = row.get("split")
        if not request_group or split not in ("train", "validation", "test"):
            raise DatasetValidationError(
                "row is missing request_group or has an unsupported split"
            )
        splits_by_request[str(request_group)].add(str(split))

        article = row.get("article") or {}
        if not article.get("embedding"):
            raise DatasetValidationError("candidate article is missing an embedding")

        served_at = parse_datetime(row["served_at"])
        for entry in row.get("history") or ():
            entry_article = entry.get("article") or {}
            if not entry_article.get("embedding"):
                raise DatasetValidationError("history entry is missing an embedding")
            if history_schema_version == "mind-pre-impression-history-v1":
                if (row.get("source_format") != "official-mind-tsv-v1"
                        or entry.get("provenance") != "mind-pre-impression-snapshot"
                        or entry.get("engaged_at") is not None):
                    raise DatasetValidationError("invalid timestamp-free MIND history provenance")
                continue
            if entry.get("engaged_at") is None:
                raise DatasetValidationError("local history requires an observed event timestamp")
            engaged_at = parse_datetime(entry["engaged_at"])
            if engaged_at >= served_at:
                raise DatasetValidationError(
                    "history event occurs at or after the request was served"
                )

    leaked = [
        request for request, splits in splits_by_request.items() if len(splits) != 1
    ]
    if leaked:
        raise DatasetValidationError("request_group appears in multiple dataset splits")


def _split_v2_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    by_split: dict[str, list[Mapping[str, Any]]] = {
        "train": [],
        "validation": [],
        "test": [],
    }
    for row in rows:
        by_split[row["split"]].append(row)
    if not by_split["train"]:
        raise DatasetValidationError("train split must not be empty")
    if not by_split["validation"]:
        raise DatasetValidationError("validation split must not be empty")
    if not by_split["test"]:
        raise DatasetValidationError("test holdout must not be empty")
    return by_split


def _select_attention_heads(dimension: int) -> int:
    for candidate in (2, 4, 8, 1):
        if dimension % candidate == 0:
            return candidate
    return 1


def _select_history_length(
    rows: Sequence[Mapping[str, Any]], *, cap: int = NRMS_HISTORY_CAP
) -> int:
    observed = max((len(row.get("history") or ()) for row in rows), default=0)
    return min(max(observed, 1), cap)


def _compute_popular_embedding(
    rows: Sequence[Mapping[str, Any]], dimension: int
) -> list[float]:
    vectors = [
        row["article"]["embedding"]
        for row in rows
        if (row.get("article") or {}).get("embedding") is not None
    ]
    if not vectors:
        return [0.0] * dimension
    return np.asarray(vectors, dtype=float).mean(axis=0).tolist()


def _checkpoint_contract(
    dataset: Path,
    metadata: Mapping[str, Any],
    architecture: NRMSArchitecture,
) -> dict[str, Any]:
    return {
        "checkpoint_schema_version": "nrms-training-checkpoint-v1",
        "dataset_sha256": sha256_file(dataset),
        "metadata_sha256": sha256_file(
            dataset.with_suffix(f"{dataset.suffix}.metadata.json")
        ),
        "embedding_dimension": architecture.embedding_dimension,
        "attention_heads": architecture.attention_heads,
        "history_length": architecture.history_length,
        "seed": architecture.seed,
        "encoder_version": metadata["encoder_version"],
        "history_schema_version": metadata["history_schema_version"],
        "label_definition_version": metadata["label_definition_version"],
        "learning_rate": NRMS_LEARNING_RATE,
    }


def _save_nrms_checkpoint(
    path: Path,
    ranker: NRMSLikeRanker,
    epoch: int,
    contract: Mapping[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    popular = (
        ranker.popular_embedding
        if ranker.popular_embedding is not None
        else np.zeros(ranker.architecture.embedding_dimension)
    )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        ) as handle:
            temporary_path = Path(handle.name)
            np.savez(
                handle,
                query_projection=ranker.query_projection,
                key_projection=ranker.key_projection,
                value_projection=ranker.value_projection,
                popular_embedding=np.asarray(popular, dtype=float),
                epoch=epoch,
                **contract,
            )
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _load_nrms_checkpoint(
    path: Path,
) -> tuple[NRMSLikeRanker, int, dict[str, Any]]:
    with np.load(path) as data:
        architecture = NRMSArchitecture(
            embedding_dimension=int(data["embedding_dimension"]),
            attention_heads=int(data["attention_heads"]),
            history_length=int(data["history_length"]),
            seed=int(data["seed"]),
        )
        ranker = NRMSLikeRanker(
            architecture=architecture,
            query_projection=np.array(data["query_projection"]),
            key_projection=np.array(data["key_projection"]),
            value_projection=np.array(data["value_projection"]),
            calibration_scale=1.0,
            calibration_bias=0.0,
            popular_embedding=np.array(data["popular_embedding"]),
        )
        epoch = int(data["epoch"])
        contract = {
            key: data[key].item()
            for key in (
                "checkpoint_schema_version",
                "dataset_sha256",
                "metadata_sha256",
                "embedding_dimension",
                "attention_heads",
                "history_length",
                "seed",
                "encoder_version",
                "history_schema_version",
                "label_definition_version",
                "learning_rate",
            )
        }
    return ranker, epoch, contract


def _validate_checkpoint_contract(
    actual: Mapping[str, Any], expected: Mapping[str, Any]
) -> None:
    labels = {
        "checkpoint_schema_version": "schema version",
        "dataset_sha256": "dataset checksum",
        "metadata_sha256": "metadata checksum",
        "embedding_dimension": "embedding dimension",
        "attention_heads": "attention heads",
        "history_length": "history length",
        "seed": "seed",
        "encoder_version": "encoder version",
        "history_schema_version": "history schema version",
        "label_definition_version": "label definition version",
        "learning_rate": "learning rate",
    }
    for key, expected_value in expected.items():
        if actual.get(key) != expected_value:
            raise DatasetValidationError(
                f"checkpoint {labels[key]} does not match the requested training run"
            )


def _calibrate_ranker(
    ranker: NRMSLikeRanker, validation_rows: Sequence[Mapping[str, Any]]
) -> NRMSLikeRanker:
    raw_scores: list[float] = []
    labels: list[int] = []
    for row in validation_rows:
        history_entries = sorted(
            row.get("history") or (), key=lambda entry: int(entry["ordinal"])
        )
        history_embeddings = [
            entry["article"]["embedding"]
            for entry in history_entries
            if (entry.get("article") or {}).get("embedding") is not None
        ]
        context = ranker.prepare_user_context(
            history_embeddings=history_embeddings,
            declared_topic_embedding=row.get("declared_topic_embedding"),
        )
        raw_scores.append(ranker.raw_score(context.vector, row["article"]["embedding"]))
        labels.append(int(row["click_label"]))
    if len(set(labels)) < 2:
        return ranker
    calibrator = LogisticRegression()
    calibrator.fit([[score] for score in raw_scores], labels)
    return ranker.with_calibration(
        scale=float(calibrator.coef_[0][0]), bias=float(calibrator.intercept_[0])
    )


def _train_nrms_from_dataset(
    dataset: Path,
    output: Path,
    metadata: Mapping[str, Any],
    *,
    seed: int,
    epochs: int,
    checkpoint: Path | None,
    resume: bool,
) -> dict[str, Any]:
    if epochs <= 0:
        raise DatasetValidationError("epochs must be positive")
    _validate_v2_metadata(metadata)
    rows = _read_v2_rows(dataset, metadata)
    _validate_v2_contract(rows, history_schema_version=metadata["history_schema_version"])
    rows_by_split = _split_v2_rows(rows)

    embedding_dimension = int(metadata["encoder_dimension"])
    attention_heads = _select_attention_heads(embedding_dimension)
    history_length = _select_history_length(rows_by_split["train"])
    architecture = NRMSArchitecture(
        embedding_dimension=embedding_dimension,
        attention_heads=attention_heads,
        history_length=history_length,
        seed=seed,
    )
    popular_embedding = _compute_popular_embedding(
        rows_by_split["train"], embedding_dimension
    )
    checkpoint_contract = _checkpoint_contract(dataset, metadata, architecture)

    start_epoch = 0
    if resume:
        if checkpoint is None or not checkpoint.exists():
            raise DatasetValidationError(
                "resume requested but checkpoint file does not exist"
            )
        ranker, start_epoch, stored_contract = _load_nrms_checkpoint(checkpoint)
        _validate_checkpoint_contract(stored_contract, checkpoint_contract)
        if start_epoch >= epochs:
            raise DatasetValidationError(
                "checkpoint epoch must be lower than the requested target epoch"
            )
    else:
        ranker = NRMSLikeRanker.initialize(
            architecture, popular_embedding=popular_embedding
        )

    train_examples = build_pairwise_examples(rows_by_split["train"])
    if not train_examples:
        raise DatasetValidationError(
            "train split has no eligible positive/negative pairs"
        )

    for epoch in range(start_epoch, epochs):
        ranker = train_pairwise_epoch(
            ranker, train_examples, learning_rate=NRMS_LEARNING_RATE
        )
        if checkpoint is not None:
            _save_nrms_checkpoint(
                checkpoint,
                ranker,
                epoch + 1,
                checkpoint_contract,
            )

    ranker = _calibrate_ranker(ranker, rows_by_split["validation"])

    row_counts = {split: len(values) for split, values in sorted(rows_by_split.items())}
    manifest: dict[str, Any] = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "model_version": output.name,
        "model_type": NRMS_MODEL_TYPE,
        "seed": seed,
        "dataset_schema_version": DATASET_SCHEMA_VERSION_V2,
        "architecture": {
            "embedding_dimension": architecture.embedding_dimension,
            "attention_heads": architecture.attention_heads,
            "history_length": architecture.history_length,
        },
        "embedding": {
            "version": metadata["encoder_version"],
            "dimension": metadata["encoder_dimension"],
        },
        "history": {
            "schema_version": metadata["history_schema_version"],
        },
        "label_schema": {
            "training_target": "click_label",
            "label_definition_version": metadata.get("label_definition_version"),
        },
        "row_counts": row_counts,
        "calibration": {
            "method": "temperature-scaled-sigmoid",
            "scale": ranker.calibration_scale,
            "bias": ranker.calibration_bias,
        },
        "training": {
            "epochs": epochs,
            "resumed_from_epoch": start_epoch,
            "learning_rate": NRMS_LEARNING_RATE,
            "pairwise_examples": len(train_examples),
        },
        "dependency_versions": _dependency_versions(),
        "dataset": {
            "parquet_sha256": sha256_file(dataset),
            "metadata_sha256": sha256_file(
                dataset.with_suffix(f"{dataset.suffix}.metadata.json")
            ),
            "source_code_version": metadata.get("code_version"),
        },
    }
    return _write_artifact(ranker, manifest, output)


def train_from_dataset(
    dataset: Path,
    output: Path,
    *,
    seed: int = DEFAULT_SEED,
    min_train_rows: int = MIN_TRAIN_ROWS,
    epochs: int | None = None,
    checkpoint: Path | None = None,
    resume: bool = False,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"artifact output already exists: {output}")
    preview_metadata = _peek_metadata(dataset)
    if preview_metadata.get("dataset_schema_version") == DATASET_SCHEMA_VERSION_V2:
        return _train_nrms_from_dataset(
            dataset,
            output,
            preview_metadata,
            seed=seed,
            epochs=epochs if epochs is not None else NRMS_DEFAULT_EPOCHS,
            checkpoint=checkpoint,
            resume=resume,
        )

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
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--checkpoint", type=Path, default=None)
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        manifest = train_from_dataset(
            args.dataset,
            args.output,
            seed=args.seed,
            epochs=args.epochs,
            checkpoint=args.checkpoint,
            resume=args.resume,
        )
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
