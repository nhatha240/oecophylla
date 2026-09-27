from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ai_pipeline import mind_large


def write_source(root: Path, name: str, day: int, *, count=12, unlabeled=False):
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "news.tsv").write_text(
        "\n".join(
            f"N{i}\tsports\tfootball\tArticle {i}\tAbstract {i}\turl\t[]\t[]"
            for i in range(4)
        )
        + "\n"
    )
    (directory / "behaviors.tsv").write_text(
        "\n".join(
            f"{i}\tU{i}\t11/{day:02d}/2019 {1 + i // 2}:00:00 AM\tN0 N1 N2\t"
            + ("N2 N3" if unlabeled else "N2-1 N3-0")
            for i in range(count)
        )
        + "\n"
    )
    return directory


def test_streamed_sampling_is_deterministic_and_preserves_candidates(tmp_path):
    source = write_source(tmp_path, "train", 10)
    first, audit = mind_large.sample_behaviors(
        source / "behaviors.tsv", limit=8, seed=7
    )
    second, _ = mind_large.sample_behaviors(source / "behaviors.tsv", limit=8, seed=7)
    assert first == second
    assert audit["requests"] == 12
    assert len(first) == 8
    assert all(row[4] == "N2-1 N3-0" for row in first)


def test_new_holdout_excludes_all_previously_evaluated_requests(tmp_path):
    write_source(tmp_path, "MINDlarge_train", 10)
    write_source(tmp_path, "MINDlarge_dev", 15)
    previous = mind_large.prepare_dataset(tmp_path, train_requests=12, test_requests=4, seed=7, salt="secret")
    excluded = {r["request_group"] for r in previous["requests"] if r["split"] == "test"}
    current = mind_large.prepare_dataset(tmp_path, train_requests=12, test_requests=4, seed=7, salt="secret", exclude_test_requests=excluded)
    actual = {r["request_group"] for r in current["requests"] if r["split"] == "test"}
    assert len(actual) == 4 and actual.isdisjoint(excluded)
    assert current["metadata"]["excluded_test_requests"] == 4
    assert current["metadata"]["source_files"]["MINDlarge_dev/behaviors.tsv"]["excluded_requests"] == 4
    with pytest.raises(ValueError, match="exclusion"):
        mind_large.prepare_dataset(tmp_path, train_requests=12, test_requests=4, seed=7, salt="different-salt", exclude_test_requests=excluded)


def test_exclusion_cannot_return_a_short_holdout(tmp_path):
    write_source(tmp_path, "MINDlarge_train", 10)
    write_source(tmp_path, "MINDlarge_dev", 15)
    previous = mind_large.prepare_dataset(tmp_path, train_requests=12, test_requests=12, seed=7, salt="secret")
    excluded = {r["request_group"] for r in previous["requests"] if r["split"] == "test"}
    with pytest.raises(ValueError, match="available"):
        mind_large.prepare_dataset(tmp_path, train_requests=12, test_requests=1, seed=7, salt="secret", exclude_test_requests=excluded)


def test_compact_dataset_is_private_and_temporal_without_test_labels(tmp_path):
    write_source(tmp_path, "MINDlarge_train", 10)
    write_source(tmp_path, "MINDlarge_dev", 15)
    write_source(tmp_path, "MINDlarge_test", 19, unlabeled=True)
    result = mind_large.prepare_dataset(
        tmp_path,
        train_requests=12,
        test_requests=6,
        seed=7,
        salt="secret",
        history_limit=2,
    )
    rows = result["requests"]
    assert {r["split"] for r in rows} == {"train", "validation", "test"}
    times = {
        s: [r["served_at"] for r in rows if r["split"] == s]
        for s in ("train", "validation", "test")
    }
    assert max(times["train"]) < min(times["validation"]) < min(times["test"])
    assert all(len(r["history"]) == 2 and len(r["candidates"]) == 2 for r in rows)
    assert len({r["request_group"] for r in rows}) == len(rows)
    exported = json.dumps(result)
    assert '"U0"' not in exported and '"N0"' not in exported
    assert "engaged_at" not in exported and "published_at" not in exported
    assert result["metadata"]["official_test_used"] is False
    assert (
        result["metadata"]["source_files"]["MINDlarge_train/behaviors.tsv"]["requests"]
        == 12
    )


@pytest.mark.parametrize(
    "corruption,match",
    [
        ("N2 N3", "label"),
        ("N2-1 N2-0", "duplicate"),
        ("N2-1 N9-0", "unknown"),
        ("N2-1", "candidate"),
    ],
)
def test_invalid_candidates_are_rejected(tmp_path, corruption, match):
    train = write_source(tmp_path, "MINDlarge_train", 10)
    write_source(tmp_path, "MINDlarge_dev", 15)
    path = train / "behaviors.tsv"
    path.write_text(path.read_text().replace("N2-1 N3-0", corruption))
    with pytest.raises(ValueError, match=match):
        mind_large.prepare_dataset(
            tmp_path, train_requests=12, test_requests=6, seed=7, salt="secret"
        )


def test_overlapping_official_splits_are_rejected(tmp_path):
    write_source(tmp_path, "MINDlarge_train", 15)
    write_source(tmp_path, "MINDlarge_dev", 10)
    with pytest.raises(ValueError, match="chronological"):
        mind_large.prepare_dataset(
            tmp_path, train_requests=12, test_requests=6, seed=7, salt="secret"
        )


def test_embedding_cache_is_bound_to_text_and_encoder(tmp_path):
    articles = [{"text": "hello"}, {"text": "world"}]
    calls = []

    def encode(texts):
        calls.append(texts)
        return np.eye(2, dtype=np.float32)

    target = tmp_path / "vectors.npz"
    actual = mind_large.cached_embeddings(
        articles, target, encode=encode, encoder_version="v1", dimension=2
    )
    assert np.array_equal(actual, np.eye(2))
    mind_large.cached_embeddings(
        articles, target, encode=encode, encoder_version="v1", dimension=2
    )
    assert len(calls) == 1
    with pytest.raises(ValueError, match="cache"):
        mind_large.cached_embeddings(
            [{"text": "changed"}, articles[1]],
            target,
            encode=encode,
            encoder_version="v1",
            dimension=2,
        )
    with pytest.raises(ValueError, match="cache"):
        mind_large.cached_embeddings(
            articles, target, encode=encode, encoder_version="v2", dimension=2
        )


def test_invalid_embeddings_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="embedding"):
        mind_large.cached_embeddings(
            [{"text": "hello"}],
            tmp_path / "bad.npz",
            encode=lambda _: [[float("nan"), 0]],
            encoder_version="v1",
            dimension=2,
        )


def test_prepare_cli_creates_private_salt_and_resumable_dataset(tmp_path):
    write_source(tmp_path, "MINDlarge_train", 10)
    write_source(tmp_path, "MINDlarge_dev", 15)
    output = tmp_path / "output"
    assert (
        mind_large.main(
            [
                "--stage",
                "prepare",
                "--data-dir",
                str(tmp_path),
                "--output",
                str(output),
                "--train-requests",
                "12",
                "--test-requests",
                "6",
            ]
        )
        == 0
    )
    assert (output / "identity-salt").stat().st_mode & 0o777 == 0o600
    assert (
        json.loads((output / "dataset.json").read_text())["metadata"]["split_counts"][
            "test"
        ]
        == 6
    )
