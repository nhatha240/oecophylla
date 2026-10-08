from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from ai_pipeline import continuation, finetune, mind_large
from ai_pipeline.artifact import sha256_file
from ai_pipeline.benchmark_data import store_identity_salt
from ai_pipeline.continuation import preserve_validation_boundary, select_winner
from ai_pipeline.model import NRMSArchitecture
from ai_pipeline.tests.test_mind_large import write_source
from workers.nlp_worker.app.content_features import ENCODER_VERSION


def test_expanded_training_preserves_parent_cutoff_and_equal_timestamp_bucket():
    reference = {
        "metadata": {"validation_cutoff": "2019-11-14T12:00:00+00:00"},
        "requests": [{"request_group": "old", "split": "train"}],
    }
    data = {
        "metadata": {},
        "requests": [
            {
                "request_group": "old",
                "served_at": "2019-11-14T11:00:00+00:00",
                "split": "validation",
            },
            {
                "request_group": "new1",
                "served_at": "2019-11-14T12:00:00+00:00",
                "split": "train",
            },
            {
                "request_group": "new2",
                "served_at": "2019-11-14T12:00:00+00:00",
                "split": "train",
            },
            {
                "request_group": "test",
                "served_at": "2019-11-15T00:00:00+00:00",
                "split": "test",
            },
        ],
    }
    preserve_validation_boundary(data, reference)
    assert [row["split"] for row in data["requests"]] == [
        "train",
        "validation",
        "validation",
        "test",
    ]
    corrupted = copy.deepcopy(reference)
    corrupted["requests"].append({"request_group": "new1", "split": "train"})
    with pytest.raises(ValueError, match="parent training"):
        preserve_validation_boundary(data, corrupted)


def test_winner_is_selected_only_by_validation_with_parent_winning_ties():
    candidates = [
        {"name": "parent_r2", "validation_ndcg_at_10": 0.35, "test_ndcg_at_10": 0.1},
        {"name": "tuned", "validation_ndcg_at_10": 0.34, "test_ndcg_at_10": 0.9},
    ]
    assert select_winner(candidates)["name"] == "parent_r2"
    candidates[1]["validation_ndcg_at_10"] = 0.35
    assert select_winner(candidates)["name"] == "parent_r2"
    candidates[1]["validation_ndcg_at_10"] = 0.36
    assert select_winner(candidates)["name"] == "tuned"
    with pytest.raises(ValueError):
        select_winner([])


def test_continuation_runs_end_to_end_then_seals_selection_and_reports(tmp_path):
    source = tmp_path / "source"
    write_source(source, "MINDlarge_train", 10)
    write_source(source, "MINDlarge_dev", 15)
    reference = tmp_path / "reference"
    reference.mkdir()
    data = mind_large.prepare_dataset(
        source, train_requests=12, test_requests=2, seed=7, salt="secret"
    )
    vectors = np.eye(384, dtype=np.float32)[: len(data["articles"])]
    mind_large.cached_embeddings(
        data["articles"],
        reference / "embeddings.npz",
        encode=lambda _: vectors,
        encoder_version=ENCODER_VERSION,
        dimension=384,
    )
    data["metadata"]["embedding_sha256"] = sha256_file(reference / "embeddings.npz")
    (reference / "dataset.json").write_text(json.dumps(data))
    store_identity_salt(reference, "secret")
    ranker = finetune.initialize_ranker(
        NRMSArchitecture(384, 2, 20, 7, 0.0, 0.5), vectors[0]
    )
    finetune.export_artifact(
        ranker,
        reference / "model",
        training_report={},
        dataset_metadata=data["metadata"],
        dataset_sha256=sha256_file(reference / "dataset.json"),
        encoder_version=ENCODER_VERSION,
    )
    run = tmp_path / "run"
    args = ["--run-dir", str(run), "--reference-dir", str(reference)]
    assert (
        continuation.main(
            [
                "--stage",
                "prepare",
                *args,
                "--data-dir",
                str(source),
                "--train-requests",
                "12",
                "--holdout-requests",
                "4",
                "--epochs",
                "1",
                "--batch-size",
                "4",
                "--configs",
                "attention20",
                "value20",
            ]
        )
        == 0
    )
    assert continuation.main(["--stage", "encode", *args]) == 0
    with pytest.raises(FileNotFoundError):
        continuation.main(["--stage", "select", *args])
    assert continuation.main(["--stage", "train", *args]) == 0
    assert not (run / "benchmark").exists()
    assert continuation.main(["--stage", "select", *args]) == 0
    with pytest.raises(FileExistsError, match="frozen"):
        continuation.main(["--stage", "train", *args])
    assert continuation.main(["--stage", "benchmark", *args]) == 0
    report = json.loads((run / "benchmark/report.json").read_text())
    result = json.loads((run / "target-result.json").read_text())
    assert report["dataset"]["overlap_with_prior_holdouts"] == 0
    assert result["comparison_to_parent"]["baseline"] == "parent_r2"
    assert result["ndcg_at_10"] == report["models"]["nrms"]["ndcg_at_10"]
    with pytest.raises(FileExistsError, match="opened"):
        continuation.main(["--stage", "benchmark", *args])
