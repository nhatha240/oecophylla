from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ai_pipeline.build_dataset import validate_dataset_v2
from ai_pipeline.mind_adapter import adapt_mind

FIXTURE = Path(__file__).parent / "fixtures" / "mind_v2"


def test_mind_and_local_use_the_same_v2_validator_and_private_schema():
    result = adapt_mind(
        FIXTURE / "news.tsv",
        FIXTURE / "behaviors.tsv",
        hash_salt="mind-fixture-salt",
        train_fraction=0.34,
        validation_fraction=0.33,
    )

    report = validate_dataset_v2(result)

    assert report.request_count == 3
    assert report.empty_history_requests == 1
    assert len(result.rows) == 6
    assert {row.split for row in result.rows} == {"train", "validation", "test"}
    assert all(row.dataset_scope == "served-impression-reranking" for row in result.rows)
    assert all(row.article.representation_type == "mind-text-v1" for row in result.rows)
    histories_by_time = {
        row.served_at: row.history for row in result.rows if row.position == 0
    }
    latest_history = histories_by_time[max(histories_by_time)]
    assert [entry.ordinal for entry in latest_history] == [0, 1]
    assert [entry.article.title for entry in latest_history] == [
        "Home side wins",
        "Storm approaches",
    ]
    exported = json.dumps([row.to_record() for row in result.rows], default=str)
    for raw_identity in ("I1", "I2", "I3", "U1", "U2", "N1", "N2", "N3", "N4", "N5"):
        assert raw_identity not in exported


def test_mind_adapter_rejects_unknown_articles_and_invalid_labels(tmp_path: Path):
    news = tmp_path / "news.tsv"
    news.write_text((FIXTURE / "news.tsv").read_text(encoding="utf-8"), encoding="utf-8")
    behaviors = tmp_path / "behaviors.tsv"
    behaviors.write_text(
        "I1\tU1\t11/15/2019 9:00:00 AM\t\tUNKNOWN-1 N2-0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown MIND article"):
        adapt_mind(news, behaviors, hash_salt="salt")

    behaviors.write_text(
        "I1\tU1\t11/15/2019 9:00:00 AM\t\tN1-2 N2-0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="click label must be 0 or 1"):
        adapt_mind(news, behaviors, hash_salt="salt")


def test_validator_rejects_request_split_leakage_and_single_candidate():
    result = adapt_mind(
        FIXTURE / "news.tsv",
        FIXTURE / "behaviors.tsv",
        hash_salt="mind-fixture-salt",
        train_fraction=0.34,
        validation_fraction=0.33,
    )
    first = result.rows[0]
    same_group = next(row for row in result.rows[1:] if row.request_group == first.request_group)
    leaked = replace(same_group, split="test" if first.split != "test" else "train")
    rows = tuple(leaked if row.sample_id == same_group.sample_id else row for row in result.rows)
    with pytest.raises(ValueError, match="request group crosses splits"):
        validate_dataset_v2(replace(result, rows=rows))

    without_peer = tuple(row for row in result.rows if row.sample_id != same_group.sample_id)
    with pytest.raises(ValueError, match="at least two candidates"):
        validate_dataset_v2(replace(result, rows=without_peer))
