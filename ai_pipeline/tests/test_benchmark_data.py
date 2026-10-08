from __future__ import annotations

import json

import numpy as np
import pytest

from ai_pipeline import benchmark, benchmark_data
from ai_pipeline.artifact import sha256_file
from ai_pipeline.benchmark_data import merge_embeddings, prepare_holdout
from ai_pipeline.finetune import export_artifact
from ai_pipeline.mind_adapter import _private_id
from ai_pipeline.mind_large import cached_embeddings
from ai_pipeline.model import NRMSArchitecture, NRMSLikeRanker
from workers.nlp_worker.app.content_features import ENCODER_VERSION


def source(root, *, candidates="N1-1 N2-0 N3-0"):
    for name in ("MINDlarge_train", "MINDlarge_dev"):
        directory = root / name
        directory.mkdir()
        (directory / "news.tsv").write_text(
            "\n".join(
                f"N{i}\tnews\tlocal\tTitle {i}\tText {i}\turl\t[]\t[]" for i in range(4)
            )
            + "\n"
        )
    (root / "MINDlarge_dev/behaviors.tsv").write_text(
        "\n".join(
            f"{i}\tU{i % 3}\t11/15/2019 {i + 1}:00:00 AM\tN0 N1 N2\t{candidates}"
            for i in range(8)
        )
        + "\n"
    )


def test_fresh_holdout_excludes_previous_requests_and_keeps_all_candidates(tmp_path):
    source(tmp_path)
    previous = {_private_id("secret", "mind-request", "MINDlarge_dev:U0:0")}
    data = prepare_holdout(
        tmp_path,
        excluded=previous,
        limit=5,
        seed=7,
        salt="secret",
        history_limit=2,
        training_end="2019-11-14T23:59:59+00:00",
    )
    requests = data["requests"]
    assert len(requests) == 5
    assert previous.isdisjoint(row["request_group"] for row in requests)
    assert all(
        row["split"] == "test" and len(row["candidates"]) == 3 for row in requests
    )
    assert all(len(row["history"]) == 2 for row in requests)
    assert all(len(row["user_group"]) == 64 for row in requests)
    assert '"U0"' not in json.dumps(data) and '"N0"' not in json.dumps(data)
    assert data["metadata"]["excluded_requests"] == 1
    assert (
        prepare_holdout(
            tmp_path,
            excluded=previous,
            limit=5,
            seed=7,
            salt="secret",
            history_limit=2,
            training_end="2019-11-14T23:59:59+00:00",
        )
        == data
    )


def test_wrong_salt_and_non_temporal_data_are_rejected(tmp_path):
    source(tmp_path)
    previous = {_private_id("secret", "mind-request", "MINDlarge_dev:U0:0")}
    with pytest.raises(ValueError, match="exclusion"):
        prepare_holdout(
            tmp_path,
            excluded=previous,
            limit=5,
            seed=7,
            salt="wrong",
            history_limit=20,
            training_end="2019-11-14T00:00:00+00:00",
        )
    with pytest.raises(ValueError, match="training"):
        prepare_holdout(
            tmp_path,
            excluded=set(),
            limit=8,
            seed=7,
            salt="secret",
            history_limit=20,
            training_end="2019-11-15T03:00:00+00:00",
        )


@pytest.mark.parametrize("candidates", ["N1 N2", "N1-1 N1-0", "N1-2 N2-0", "N1-1 N9-0"])
def test_bad_candidate_labels_or_articles_fail_closed(tmp_path, candidates):
    source(tmp_path, candidates=candidates)
    with pytest.raises(ValueError):
        prepare_holdout(
            tmp_path,
            excluded=set(),
            limit=8,
            seed=7,
            salt="secret",
            history_limit=20,
            training_end="2019-11-14T00:00:00+00:00",
        )


def test_embedding_reuse_encodes_only_missing_text_and_keeps_alignment():
    articles = [
        {"article_group": "b", "text": "second"},
        {"article_group": "a", "text": "first"},
    ]
    reference = [{"article_group": "a", "text": "first"}]
    calls = []

    def encode(texts):
        calls.append(texts)
        return np.array([[0.0, 1.0]])

    vectors, audit = merge_embeddings(
        articles, reference, np.array([[1.0, 0.0]]), encode=encode
    )
    assert calls == [["second"]]
    assert vectors.tolist() == [[0.0, 1.0], [1.0, 0.0]]
    assert audit == {"reused_articles": 1, "encoded_articles": 1}


def test_embedding_reuse_rejects_text_revision_and_invalid_encoder_output():
    reference = [{"article_group": "a", "text": "first"}]
    with pytest.raises(ValueError, match="revision"):
        merge_embeddings(
            [{"article_group": "a", "text": "changed"}],
            reference,
            np.array([[1.0, 0.0]]),
            encode=lambda _: None,
        )
    with pytest.raises(ValueError, match="embedding"):
        merge_embeddings(
            [{"article_group": "b", "text": "new"}],
            reference,
            np.array([[1.0, 0.0]]),
            encode=lambda _: [[float("nan"), 0.0]],
        )


def test_complete_embedding_cache_does_not_invoke_encoder():
    reference = [{"article_group": "a", "text": "first"}]

    def forbidden(_):
        raise AssertionError("should reuse cache")

    vectors, audit = merge_embeddings(
        reference, reference, np.array([[1.0, 0.0]]), encode=forbidden
    )
    assert vectors.tolist() == [[1.0, 0.0]]
    assert audit["encoded_articles"] == 0


@pytest.fixture
def frozen_reference(tmp_path):
    data_dir = tmp_path / "source"
    data_dir.mkdir()
    source(data_dir)
    reference = tmp_path / "reference"
    reference.mkdir()
    articles = [
        {
            "article_group": _private_id("secret", "mind-article", f"N{i}"),
            "text": f"Title {i} Text {i}",
            "category": "news",
            "subcategory": "local",
        }
        for i in range(4)
    ]
    requests = [
        {
            "request_group": "train",
            "split": "train",
            "served_at": "2019-11-10T00:00:00+00:00",
        },
        {
            "request_group": "validation",
            "split": "validation",
            "served_at": "2019-11-14T00:00:00+00:00",
        },
        {
            "request_group": _private_id(
                "secret", "mind-request", "MINDlarge_dev:U0:0"
            ),
            "split": "test",
            "served_at": "2019-11-15T01:00:00+00:00",
        },
    ]
    sources = {
        name: {"sha256": sha256_file(data_dir / name)}
        for name in (
            "MINDlarge_dev/behaviors.tsv",
            "MINDlarge_train/news.tsv",
            "MINDlarge_dev/news.tsv",
        )
    }
    vectors = np.eye(384, dtype=np.float32)[:4]
    cached_embeddings(
        articles,
        reference / "embeddings.npz",
        encode=lambda _: vectors,
        encoder_version=ENCODER_VERSION,
        dimension=384,
    )
    metadata = {
        "source_files": sources,
        "embedding_sha256": sha256_file(reference / "embeddings.npz"),
    }
    (reference / "dataset.json").write_text(
        json.dumps({"articles": articles, "requests": requests, "metadata": metadata})
    )
    (reference / "identity-salt").write_text("secret")
    ranker = NRMSLikeRanker.initialize(
        NRMSArchitecture(
            embedding_dimension=384, attention_heads=4, history_length=2, seed=7
        ),
        popular_embedding=vectors[0],
    )
    export_artifact(
        ranker,
        reference / "model",
        training_report={},
        dataset_metadata=metadata,
        dataset_sha256=sha256_file(reference / "dataset.json"),
        encoder_version=ENCODER_VERSION,
    )
    run = tmp_path / "run"
    arguments = [
        "--data-dir",
        str(data_dir),
        "--artifact",
        str(reference / "model"),
        "--reference-dir",
        str(reference),
        "--output",
        str(run),
        "--requests",
        "5",
        "--seed",
        "7",
    ]
    return run, reference, arguments


def test_registered_benchmark_runs_end_to_end_with_verified_reference_cache(
    frozen_reference,
):
    run, _, arguments = frozen_reference
    assert benchmark_data.main(["--stage", "prepare", *arguments]) == 0
    assert benchmark_data.main(["--stage", "encode", *arguments]) == 0
    assert benchmark.main(["--run-dir", str(run)]) == 0
    report = json.loads((run / "report.json").read_text())
    assert report["dataset"]["overlap_with_prior_holdouts"] == 0
    assert report["dataset"]["excluded_requests_verified"] == 1
    assert report["decision"] == "inconclusive"
    assert report["models"]["nrms"]["requests"] == 5
    with pytest.raises(FileExistsError):
        benchmark.main(["--run-dir", str(run)])


def test_next_benchmark_can_exclude_this_run_without_exporting_the_salt(
    frozen_reference,
):
    run, reference, arguments = frozen_reference
    benchmark_data.main(["--stage", "prepare", *arguments])
    salt = run / "identity-salt"
    assert salt.is_file()
    assert salt.stat().st_mode & 0o777 == 0o600
    assert "secret" not in (run / "protocol.json").read_text()
    next_args = arguments.copy()
    next_args[next_args.index("--output") + 1] = str(run.parent / "next")
    next_args[next_args.index("--requests") + 1] = "2"
    benchmark_data.main(
        [
            "--stage",
            "prepare",
            *next_args,
            "--exclude-dataset",
            str(run / "dataset.json"),
        ]
    )
    next_data = json.loads((run.parent / "next/dataset.json").read_text())
    assert next_data["metadata"]["excluded_requests"] == 6
    assert (reference / "identity-salt").read_text() == "secret"


@pytest.mark.parametrize("key", ["dataset_sha256", "model_sha256", "requests"])
def test_changed_registered_inputs_fail_before_evaluation(frozen_reference, key):
    run, _, arguments = frozen_reference
    benchmark_data.main(["--stage", "prepare", *arguments])
    benchmark_data.main(["--stage", "encode", *arguments])
    protocol = json.loads((run / "protocol.json").read_text())
    protocol[key] = 99 if key == "requests" else "wrong"
    (run / "protocol.json").write_text(json.dumps(protocol))
    with pytest.raises(ValueError):
        benchmark.main(["--run-dir", str(run)])
    assert not (run / "report.json").exists()
