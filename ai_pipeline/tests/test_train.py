from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ai_pipeline.artifact import ArtifactIntegrityError, load_artifact
from ai_pipeline.model import FEATURE_COLUMNS
from ai_pipeline.train import DatasetValidationError, train_from_dataset

REPO_ROOT = Path(__file__).parents[2]


def _row(index: int, split: str, *, one_class: bool = False) -> dict[str, Any]:
    positive = False if one_class else index % 2 == 0
    candidate_source = "topic" if index % 3 else "follow"
    feed_source = "personalized" if index % 4 else "fallback"
    if split == "validation":
        candidate_source = "validation-only"
    elif split == "test":
        candidate_source = "future-only"
    return {
        "sample_id": f"raw-user-secret-{index}",
        "user_group": f"raw-user-secret-group-{index % 5}",
        "post_group": f"raw-post-secret-group-{index}",
        "split": split,
        "label": 1 if positive else -1,
        "label_name": "positive" if positive else "negative",
        "served_at": f"2026-08-{index + 1:02d}T00:00:00+00:00",
        "visible_at": f"2026-08-{index + 1:02d}T00:01:00+00:00",
        "position": index % 10,
        "feed_source": feed_source,
        "model_version": "heuristic-v1",
        "feature_schema_version": "rank-features-v1",
        "topic_relevance": 999.0 if split == "test" else index / 100,
        "freshness": None if index % 7 == 0 else 1 - index / 100,
        "safety_score": 1.0,
        "candidate_source": candidate_source,
        "is_followed_author": None if index % 11 == 0 else index % 2 == 0,
        "author_affinity": None if index % 5 else index / 100,
        "heuristic_score": index / 50,
        "ml_score": None,
    }


def _write_dataset(
    tmp_path: Path,
    *,
    train_rows: int = 24,
    validation_rows: int = 8,
    test_rows: int = 8,
    one_class: bool = False,
    feature_schema_version: str = "rank-features-v1",
    drop_column: str | None = None,
) -> Path:
    rows: list[dict[str, Any]] = []
    index = 0
    for split, count in (
        ("train", train_rows),
        ("validation", validation_rows),
        ("test", test_rows),
    ):
        for _ in range(count):
            row = _row(index, split, one_class=one_class)
            if drop_column is not None:
                row.pop(drop_column)
            rows.append(row)
            index += 1

    dataset = tmp_path / "dataset.parquet"
    pq.write_table(pa.Table.from_pylist(rows), dataset)
    metadata = {
        "dataset_schema_version": "recommendation-dataset-v1",
        "label_definition_version": "engagement-label-v1",
        "feature_schema_versions": [feature_schema_version],
        "query_window": {
            "start": "2026-08-01T00:00:00+00:00",
            "end": "2026-09-10T00:00:00+00:00",
            "extraction_time": "2026-09-12T00:00:00+00:00",
        },
        "row_count": len(rows),
        "split_counts": {
            "train": train_rows,
            "validation": validation_rows,
            "test": test_rows,
        },
    }
    dataset.with_suffix(".parquet.metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    return dataset


def test_training_is_deterministic_and_manifest_is_auditable(tmp_path: Path):
    dataset = _write_dataset(tmp_path)

    first = train_from_dataset(dataset, tmp_path / "logreg-v1-a", seed=20260829)
    second = train_from_dataset(dataset, tmp_path / "logreg-v1-b", seed=20260829)

    assert first["artifact_schema_version"] == "recommendation-model-artifact-v1"
    assert first["model_type"] == "sklearn-logistic-regression"
    assert first["seed"] == 20260829
    assert first["feature_schema_version"] == "rank-features-v1"
    assert first["dataset_schema_version"] == "recommendation-dataset-v1"
    assert first["feature_columns"] == list(FEATURE_COLUMNS)
    assert first["data_windows"]["extraction_time"] == "2026-09-12T00:00:00+00:00"
    assert first["row_counts"] == {"test": 8, "train": 24, "validation": 8}
    assert set(first["dependency_versions"]) >= {
        "joblib",
        "numpy",
        "python",
        "scikit-learn",
    }
    assert set(first["validation_metrics"]) >= {
        "accuracy",
        "positive_rate",
        "precision",
        "recall",
        "roc_auc",
    }
    assert (
        first["files"]["model.joblib"]["sha256"]
        == second["files"]["model.joblib"]["sha256"]
    )
    assert first["validation_metrics"] == second["validation_metrics"]


def test_pipeline_fits_train_only_and_handles_unknown_category(tmp_path: Path):
    dataset = _write_dataset(tmp_path)
    output = tmp_path / "logreg-v1"
    train_from_dataset(dataset, output)

    artifact = load_artifact(output)
    preprocessor = artifact.pipeline.named_steps["preprocessor"]
    categorical = preprocessor.named_transformers_["categorical"]
    learned_categories = {
        str(value)
        for values in categorical.named_steps["onehot"].categories_
        for value in values
    }

    assert "future-only" not in learned_categories
    assert "validation-only" not in learned_categories
    score = artifact.predict_scores(
        [
            {
                "position": 2,
                "feed_source": "brand-new-source",
                "topic_relevance": None,
                "freshness": None,
                "safety_score": 1.0,
                "candidate_source": "brand-new-candidate",
                "is_followed_author": None,
                "author_affinity": None,
                "heuristic_score": 0.5,
                "ml_score": None,
            }
        ]
    )[0]
    assert 0.0 <= score <= 1.0


@pytest.mark.parametrize(
    ("dataset_options", "message"),
    [
        ({"feature_schema_version": "rank-features-v2"}, "feature schema"),
        ({"drop_column": "freshness"}, "missing required columns"),
    ],
)
def test_schema_mismatch_fails_without_artifact(
    tmp_path: Path, dataset_options: dict[str, Any], message: str
):
    dataset = _write_dataset(tmp_path, **dataset_options)
    output = tmp_path / "bad-artifact"

    with pytest.raises(DatasetValidationError, match=message):
        train_from_dataset(dataset, output)

    assert not output.exists()


@pytest.mark.parametrize(
    "dataset_options",
    [
        {"train_rows": 12, "validation_rows": 4, "test_rows": 4},
        {"one_class": True},
    ],
)
def test_invalid_training_population_leaves_no_artifact(
    tmp_path: Path, dataset_options: dict[str, Any]
):
    dataset = _write_dataset(tmp_path, **dataset_options)
    output = tmp_path / "invalid-population"

    with pytest.raises(DatasetValidationError):
        train_from_dataset(dataset, output)

    assert not output.exists()


def test_corrupt_model_checksum_is_rejected(tmp_path: Path):
    dataset = _write_dataset(tmp_path)
    output = tmp_path / "logreg-v1"
    train_from_dataset(dataset, output)
    model_path = output / "model.joblib"
    model_path.write_bytes(model_path.read_bytes() + b"corrupt")

    with pytest.raises(ArtifactIntegrityError, match="checksum"):
        load_artifact(output)


def test_artifact_is_immutable_and_contains_no_training_identity(tmp_path: Path):
    dataset = _write_dataset(tmp_path)
    output = tmp_path / "logreg-v1"
    train_from_dataset(dataset, output)

    with pytest.raises(FileExistsError, match="already exists"):
        train_from_dataset(dataset, output)

    artifact_bytes = b"".join(
        path.read_bytes() for path in output.iterdir() if path.is_file()
    )
    assert b"raw-user-secret" not in artifact_bytes
    assert b"raw-post-secret" not in artifact_bytes


def test_artifact_loads_and_predicts_in_a_new_process(tmp_path: Path):
    dataset = _write_dataset(tmp_path)
    output = tmp_path / "logreg-v1"
    train_from_dataset(dataset, output)
    record = {key: _row(50, "test")[key] for key in FEATURE_COLUMNS}
    record_path = tmp_path / "inference.json"
    record_path.write_text(json.dumps([record]), encoding="utf-8")
    script = """
import json
import sys
from pathlib import Path
from ai_pipeline.artifact import load_artifact

artifact = load_artifact(Path(sys.argv[1]))
records = json.loads(Path(sys.argv[2]).read_text())
print(json.dumps(artifact.predict_scores(records)))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script, str(output), str(record_path)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    scores = json.loads(completed.stdout)
    assert len(scores) == 1
    assert 0.0 <= scores[0] <= 1.0
