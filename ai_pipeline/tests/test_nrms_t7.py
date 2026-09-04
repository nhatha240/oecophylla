from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ai_pipeline.artifact import ArtifactIntegrityError, load_artifact
from ai_pipeline.evaluate import compare_nrms_holdout
from ai_pipeline.model import NRMSArchitecture, NRMSLikeRanker, build_pairwise_examples
from ai_pipeline.train import DatasetValidationError, train_from_dataset

REPO_ROOT = Path(__file__).parents[2]
ENCODER = "fixture/multilingual@0123456789abcdef"


def _unit(axis: int, dimension: int = 8) -> list[float]:
    vector = [0.0] * dimension
    vector[axis % dimension] = 1.0
    return vector


def _article(group: str, axis: int, *, served_at: datetime) -> dict[str, Any]:
    return {
        "article_group": group,
        "representation_type": "post-content-embedding-v1",
        "encoder_version": ENCODER,
        "content_hash": f"{axis + 1:x}" * 64,
        "embedding": _unit(axis),
        "feature_source_updated_at": served_at - timedelta(days=axis % 3),
        "feature_computed_at": served_at - timedelta(hours=1),
        "category": None,
        "subcategory": None,
        "title": "Tin kinh tế Việt Nam" if axis % 2 == 0 else "Global markets",
        "abstract": None,
    }


def _rows(*, requests_per_split: int = 4) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    request_number = 0
    for split_index, split in enumerate(("train", "validation", "test")):
        for local_request in range(requests_per_split):
            served_at = base + timedelta(days=split_index * 10 + local_request)
            request_group = f"{request_number + 1:064x}"
            history_length = (local_request + split_index) % 4
            history = [
                {
                    "article": _article(
                        f"{5000 + request_number * 10 + ordinal:064x}",
                        ordinal,
                        served_at=served_at - timedelta(days=history_length - ordinal),
                    ),
                    "ordinal": ordinal,
                    "engaged_at": served_at
                    - timedelta(days=history_length - ordinal, seconds=1),
                    "provenance": "oecophylla-click-v2",
                }
                for ordinal in range(history_length)
            ]
            for position in range(3):
                positive = position == (history_length % 3)
                candidate_group = f"{10000 + request_number * 10 + position:064x}"
                rows.append(
                    {
                        "sample_id": f"{20000 + request_number * 10 + position:064x}",
                        "request_group": request_group,
                        "candidate_group": candidate_group,
                        "split": split,
                        "served_at": served_at,
                        "visible_at": served_at + timedelta(seconds=1),
                        "position": position,
                        "served": True,
                        "visible": True,
                        "click_label": int(positive),
                        "utility_label": int(positive),
                        "utility_label_name": "click" if positive else "negative",
                        "article": _article(
                            candidate_group,
                            history_length if positive else position + 4,
                            served_at=served_at,
                        ),
                        "history": history,
                        "feed_source": (
                            "personalized" if local_request % 2 else "fallback"
                        ),
                        "model_version": "heuristic-v1",
                        "source_format": "oecophylla-local-v2",
                        "dataset_scope": "served-impression-reranking",
                        "language": "vi" if local_request % 2 == 0 else "en",
                        "declared_topic_embedding": (
                            _unit(local_request) if not history else None
                        ),
                    }
                )
            request_number += 1
    return rows


def _write_dataset(tmp_path: Path, rows: list[dict[str, Any]] | None = None) -> Path:
    rows = _rows() if rows is None else rows
    dataset = tmp_path / "dataset-v2.parquet"
    pq.write_table(pa.Table.from_pylist(rows), dataset)
    metadata = {
        "dataset_schema_version": "recommendation-dataset-v2",
        "dataset_scope": "served-impression-reranking",
        "source_format": "oecophylla-local-v2",
        "feature_schema_version": "rank-features-v1",
        "history_schema_version": "user-history-snapshot-v1",
        "label_definition_version": "recommendation-engagement-label-v2",
        "encoder_version": ENCODER,
        "encoder_dimension": 8,
        "code_version": "fixture-t6-commit",
        "query_window_version": "event-time-v1",
        "query_window": {
            "start": "2026-09-01T00:00:00+00:00",
            "end": "2026-10-01T00:00:00+00:00",
            "extraction_time": "2026-10-02T00:00:00+00:00",
        },
        "identity_mode": "hash",
        "row_count": len(rows),
        "request_count": len({row["request_group"] for row in rows}),
        "retrieval_recall_supported": False,
    }
    dataset.with_suffix(".parquet.metadata.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    return dataset


def test_nrms_user_encoder_is_order_aware_and_uses_multiple_attention_heads():
    architecture = NRMSArchitecture(
        embedding_dimension=8,
        attention_heads=2,
        history_length=4,
        seed=7,
    )
    ranker = NRMSLikeRanker.initialize(architecture)
    forward = ranker.encode_history([_unit(0), _unit(1), _unit(2)])
    reverse = ranker.encode_history([_unit(2), _unit(1), _unit(0)])

    assert ranker.query_projection.shape == (2, 8, 4)
    assert ranker.key_projection.shape == (2, 8, 4)
    assert ranker.value_projection.shape == (2, 8, 4)
    assert forward.shape == (8,)
    assert np.isfinite(forward).all()
    assert not np.allclose(forward, reverse)


def test_pairwise_examples_never_cross_impression_boundaries():
    rows = _rows(requests_per_split=2)
    train_rows = [row for row in rows if row["split"] == "train"]

    examples = build_pairwise_examples(train_rows)

    assert examples
    assert all(
        example.positive_request == example.negative_request for example in examples
    )
    assert all(
        example.positive_label == 1 and example.negative_label == 0
        for example in examples
    )


def test_empty_history_uses_declared_then_popular_fallback_without_fake_clicks():
    architecture = NRMSArchitecture(8, 2, 4, 11)
    ranker = NRMSLikeRanker.initialize(architecture, popular_embedding=_unit(7))
    declared = ranker.prepare_user_context(
        history_embeddings=[], declared_topic_embedding=_unit(3)
    )
    popular = ranker.prepare_user_context(
        history_embeddings=[], declared_topic_embedding=None
    )

    assert declared.source == "declared_topics"
    assert popular.source == "popular_articles"
    assert declared.history_length == 0
    assert popular.history_length == 0
    assert declared.fabricated_clicks == 0
    assert popular.fabricated_clicks == 0


def test_v2_training_is_deterministic_resumable_and_manifest_is_complete(
    tmp_path: Path,
):
    dataset = _write_dataset(tmp_path)
    checkpoint = tmp_path / "checkpoint.npz"
    first = train_from_dataset(
        dataset,
        tmp_path / "nrms-a",
        seed=77,
        epochs=2,
        checkpoint=checkpoint,
    )
    resumed = train_from_dataset(
        dataset,
        tmp_path / "nrms-b",
        seed=77,
        epochs=4,
        checkpoint=checkpoint,
        resume=True,
    )
    uninterrupted = train_from_dataset(
        dataset,
        tmp_path / "nrms-c",
        seed=77,
        epochs=4,
    )

    assert first["model_type"] == "nrms-like-impression-ranker"
    assert resumed["architecture"]["attention_heads"] == 2
    assert resumed["embedding"]["version"] == ENCODER
    assert resumed["history"]["schema_version"] == "user-history-snapshot-v1"
    assert resumed["label_schema"]["training_target"] == "click_label"
    assert resumed["dataset"]["parquet_sha256"]
    assert resumed["calibration"]["method"] == "temperature-scaled-sigmoid"
    assert set(resumed["dependency_versions"]) >= {
        "joblib",
        "numpy",
        "pyarrow",
        "python",
    }
    assert (
        resumed["files"]["model.joblib"]["sha256"]
        == uninterrupted["files"]["model.joblib"]["sha256"]
    )
    assert resumed["training"]["resumed_from_epoch"] == 2


def test_nrms_artifact_loads_in_fresh_process_and_contains_no_private_groups(
    tmp_path: Path,
):
    rows = _rows()
    dataset = _write_dataset(tmp_path, rows)
    output = tmp_path / "nrms-v1"
    train_from_dataset(dataset, output, epochs=2)
    record_path = tmp_path / "record.json"
    record_path.write_text(json.dumps([rows[-1]], default=str), encoding="utf-8")
    script = """
import json, sys
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

    assert len(json.loads(completed.stdout)) == 1
    artifact_bytes = b"".join(path.read_bytes() for path in output.iterdir())
    assert rows[0]["request_group"].encode() not in artifact_bytes
    assert rows[0]["candidate_group"].encode() not in artifact_bytes


@pytest.mark.parametrize("failure", ["future_history", "request_leakage", "embedding"])
def test_training_rejects_leakage_and_missing_article_contract(
    tmp_path: Path, failure: str
):
    rows = _rows()
    if failure == "future_history":
        target = next(row for row in rows if row["history"])
        target["history"][0]["engaged_at"] = target["served_at"]
    elif failure == "request_leakage":
        duplicate = deepcopy(rows[0])
        duplicate["split"] = "test"
        duplicate["sample_id"] = "f" * 64
        rows.append(duplicate)
    else:
        rows[0]["article"]["embedding"] = None
    dataset = _write_dataset(tmp_path, rows)

    with pytest.raises(DatasetValidationError):
        train_from_dataset(dataset, tmp_path / "rejected")


def test_evaluation_reports_raw_post_policy_baselines_and_required_segments(
    tmp_path: Path,
):
    rows = _rows(requests_per_split=6)
    dataset = _write_dataset(tmp_path, rows)
    output = tmp_path / "nrms"
    train_from_dataset(dataset, output, epochs=2)

    report = compare_nrms_holdout(
        rows,
        load_artifact(output),
        minimum_requests=1,
        minimum_auc_requests=1,
    )

    assert set(report["models"]) == {
        "logged_position_baseline",
        "mean_pool_logistic_baseline",
        "pure_model",
        "post_policy",
    }
    assert set(report["models"]["pure_model"]) >= {
        "impression_auc",
        "mrr",
        "ndcg_at_5",
        "ndcg_at_10",
        "coverage_at_k",
        "embedding_diversity_at_k",
        "strong_negative_rate_at_k",
    }
    assert set(report["segments"]) == {
        "user_tenure",
        "article_tenure",
        "history_length",
        "feed_source",
        "language",
    }
    assert report["evaluation_scope"] == "untouched-temporal-test-requests"
    assert report["raw_model_precedes_post_policy"] is True
    assert report["promotion"]["eligible"] in {True, False}


def test_evaluation_rejects_insufficient_power_and_missing_segment_results(
    tmp_path: Path,
):
    rows = _rows(requests_per_split=2)
    dataset = _write_dataset(tmp_path, rows)
    output = tmp_path / "nrms"
    train_from_dataset(dataset, output, epochs=1)
    artifact = load_artifact(output)

    insufficient = compare_nrms_holdout(rows, artifact, minimum_requests=30)
    assert insufficient["promotion"] == {
        "eligible": False,
        "reason": "insufficient_test_requests",
    }

    for row in rows:
        row.pop("feed_source")
    with pytest.raises(ValueError, match="segment"):
        compare_nrms_holdout(rows, artifact, minimum_requests=1)


def test_evaluate_cli_dispatches_dataset_v2_to_nrms_report(tmp_path: Path):
    dataset = _write_dataset(tmp_path)
    artifact = tmp_path / "nrms"
    report_path = tmp_path / "comparison.json"
    train_from_dataset(dataset, artifact, epochs=1)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_pipeline.evaluate",
            "--dataset",
            str(dataset),
            "--artifact",
            str(artifact),
            "--output",
            str(report_path),
            "--minimum-requests",
            "1",
            "--minimum-auc-requests",
            "1",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_schema_version"] == "recommendation-nrms-comparison-v1"
    assert report_path.with_suffix(".md").is_file()


def test_promotion_rejects_a_model_that_regresses_against_logged_order():
    rows = _rows(requests_per_split=4)

    class DeliberatelyBadArtifact:
        def __init__(self) -> None:
            self.manifest: dict[str, Any] = {}

        def predict_scores(self, records: list[dict[str, Any]]) -> list[float]:
            return [float(1 - int(row["click_label"])) for row in records]

    report = compare_nrms_holdout(
        rows,
        DeliberatelyBadArtifact(),
        minimum_requests=1,
        minimum_auc_requests=1,
    )

    assert report["models"]["pure_model"]["impression_auc"] == 0.0
    assert report["promotion"] == {
        "eligible": False,
        "reason": "ranking_metric_regression",
    }


def test_resume_rejects_checkpoint_from_a_different_seed(tmp_path: Path):
    dataset = _write_dataset(tmp_path)
    checkpoint = tmp_path / "checkpoint.npz"
    train_from_dataset(
        dataset,
        tmp_path / "first",
        seed=77,
        epochs=1,
        checkpoint=checkpoint,
    )

    with pytest.raises(DatasetValidationError, match="seed"):
        train_from_dataset(
            dataset,
            tmp_path / "resumed",
            seed=999,
            epochs=2,
            checkpoint=checkpoint,
            resume=True,
        )


def test_resume_rejects_checkpoint_from_a_different_dataset(tmp_path: Path):
    dataset = _write_dataset(tmp_path)
    checkpoint = tmp_path / "checkpoint.npz"
    train_from_dataset(
        dataset,
        tmp_path / "first",
        epochs=1,
        checkpoint=checkpoint,
    )
    changed_rows = _rows()
    changed_rows[0]["article"]["embedding"] = _unit(7)
    _write_dataset(tmp_path, changed_rows)

    with pytest.raises(DatasetValidationError, match="dataset checksum"):
        train_from_dataset(
            dataset,
            tmp_path / "resumed",
            epochs=2,
            checkpoint=checkpoint,
            resume=True,
        )


def test_real_v2_shape_reports_missing_segment_metadata_without_crashing(
    tmp_path: Path,
):
    rows = _rows(requests_per_split=4)
    for row in rows:
        row.pop("language")
        row.pop("declared_topic_embedding")
    dataset = _write_dataset(tmp_path, rows)
    artifact_path = tmp_path / "nrms"
    train_from_dataset(dataset, artifact_path, epochs=1)

    report = compare_nrms_holdout(
        rows,
        load_artifact(artifact_path),
        minimum_requests=1,
        minimum_auc_requests=1,
    )

    assert report["segments"]["language"]["unknown"]["requests"] == 4
    assert report["promotion"] == {
        "eligible": False,
        "reason": "missing_segment_metadata",
    }


def test_nrms_loader_rejects_manifest_payload_architecture_mismatch(tmp_path: Path):
    dataset = _write_dataset(tmp_path)
    artifact_path = tmp_path / "nrms"
    train_from_dataset(dataset, artifact_path, epochs=1)
    manifest_path = artifact_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["architecture"]["attention_heads"] = 4
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ArtifactIntegrityError, match="architecture"):
        load_artifact(artifact_path)


@pytest.mark.parametrize("epochs", [0, -1])
def test_nrms_training_rejects_non_positive_epoch_count(tmp_path: Path, epochs: int):
    dataset = _write_dataset(tmp_path)

    with pytest.raises(DatasetValidationError, match="epochs"):
        train_from_dataset(dataset, tmp_path / f"nrms-{epochs}", epochs=epochs)


def test_promotion_win_requires_positive_paired_confidence_interval():
    rows = _rows(requests_per_split=40)

    class PerfectArtifact:
        def __init__(self) -> None:
            self.manifest: dict[str, Any] = {}

        def predict_scores(self, records: list[dict[str, Any]]) -> list[float]:
            return [float(row["click_label"]) for row in records]

    report = compare_nrms_holdout(rows, PerfectArtifact())
    ndcg = report["comparisons"]["pure_vs_logged_position"]["ndcg_at_10"]

    assert ndcg["requests"] == 40
    assert ndcg["ci95"][0] > 0.0
    assert report["promotion"] == {
        "eligible": True,
        "conclusion": "win",
    }


def test_equal_model_is_no_regression_and_not_a_statistical_win():
    rows = _rows(requests_per_split=30)

    class LoggedOrderArtifact:
        def __init__(self) -> None:
            self.manifest: dict[str, Any] = {}

        def predict_scores(self, records: list[dict[str, Any]]) -> list[float]:
            return [-float(row["position"]) for row in records]

    report = compare_nrms_holdout(rows, LoggedOrderArtifact())
    ndcg = report["comparisons"]["pure_vs_logged_position"]["ndcg_at_10"]

    assert ndcg["delta"] == 0.0
    assert ndcg["ci95"] == [0.0, 0.0]
    assert report["promotion"] == {
        "eligible": True,
        "conclusion": "no_regression",
    }
