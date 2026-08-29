from __future__ import annotations

import json
from typing import Any

import pytest

from ai_pipeline.evaluate import compare_holdout, write_comparison_report
from ai_pipeline.model import FEATURE_COLUMNS


class SpyArtifact:
    manifest = {
        "model_version": "logreg-v1",
        "files": {"model.joblib": {"sha256": "abc123"}},
    }

    def __init__(self):
        self.records: list[dict[str, Any]] = []

    def predict_scores(self, records):
        self.records = list(records)
        assert all(set(record) == set(FEATURE_COLUMNS) for record in records)
        return [float(record["topic_relevance"]) for record in records]


def _holdout(requests: int = 4) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request in range(requests):
        for rank in range(4):
            positive = rank == 0
            strong_negative = rank == 3
            rows.append(
                {
                    "sample_id": f"sample-{request}-{rank}",
                    "user_group": f"user-{request % 2}",
                    "request_group": f"request-{request}",
                    "post_group": f"post-{request}-{rank}",
                    "split": "test",
                    "label": 1 if positive else (-2 if strong_negative else -1),
                    "label_name": (
                        "positive"
                        if positive
                        else ("strong_negative" if strong_negative else "negative")
                    ),
                    "position": rank,
                    "feed_source": "personalized",
                    "feature_schema_version": "rank-features-v1",
                    "topic_relevance": 0.9 if positive else 0.1 + rank / 100,
                    "freshness": 0.8,
                    "safety_score": 1.0,
                    "candidate_source": "topic" if rank % 2 else "follow",
                    "is_followed_author": rank % 2 == 0,
                    "author_affinity": None,
                    "heuristic_score": float(rank),
                    "ml_score": None,
                }
            )
    return rows


def test_baseline_and_ml_are_scored_on_same_temporal_holdout():
    artifact = SpyArtifact()

    report = compare_holdout(_holdout(), artifact, k=2, minimum_requests=1)

    assert report["sample"] == {"impressions": 16, "requests": 4, "users": 2}
    assert report["holdout_checksum"]
    assert report["baseline"]["sample_impressions"] == 16
    assert report["ml"]["sample_impressions"] == 16
    assert report["ml"]["ndcg_at_k"] > report["baseline"]["ndcg_at_k"]
    assert report["conclusion"] == "win"
    assert len(artifact.records) == 16
    assert all("label" not in record for record in artifact.records)


def test_insufficient_sample_never_claims_ml_win():
    report = compare_holdout(
        _holdout(requests=2), SpyArtifact(), k=2, minimum_requests=30
    )

    assert report["conclusion"] == "inconclusive"
    assert report["confidence_intervals"] is None


def test_comparison_can_fail_or_pass_no_regression_guardrails():
    rows = _holdout()
    for row in rows:
        row["heuristic_score"] = row["topic_relevance"]

    class RegressingArtifact(SpyArtifact):
        def predict_scores(self, records):
            return [float(index % 4) / 3 for index, _ in enumerate(records)]

    class BaselineArtifact(SpyArtifact):
        def predict_scores(self, records):
            return [float(record["heuristic_score"]) for record in records]

    failed = compare_holdout(rows, RegressingArtifact(), k=2, minimum_requests=1)
    unchanged = compare_holdout(rows, BaselineArtifact(), k=2, minimum_requests=1)

    assert failed["conclusion"] == "fail"
    assert unchanged["conclusion"] == "no_regression"


def test_large_sample_has_deterministic_confidence_intervals():
    report = compare_holdout(
        _holdout(requests=30), SpyArtifact(), k=2, minimum_requests=30
    )

    assert report["confidence_intervals"] is not None
    assert set(report["confidence_intervals"]) == {
        "baseline_ndcg_at_k",
        "ml_ndcg_at_k",
    }


@pytest.mark.parametrize("failure", ["k", "holdout", "groups", "scores"])
def test_comparison_rejects_invalid_holdout_contract(failure: str):
    rows = _holdout()
    artifact = SpyArtifact()
    kwargs = {"k": 2, "minimum_requests": 1}
    if failure == "k":
        kwargs["k"] = 0
    elif failure == "holdout":
        for row in rows:
            row["split"] = "train"
    elif failure == "groups":
        rows[0]["request_group"] = None
    else:
        artifact.predict_scores = lambda records: [0.5]

    with pytest.raises(ValueError):
        compare_holdout(rows, artifact, **kwargs)


def test_comparison_report_writes_auditable_json_and_markdown(tmp_path):
    report = compare_holdout(_holdout(), SpyArtifact(), k=2, minimum_requests=1)

    json_path, markdown_path = write_comparison_report(report, tmp_path / "comparison")

    persisted = json.loads(json_path.read_text())
    assert persisted["artifact"] == {
        "model_sha256": "abc123",
        "model_version": "logreg-v1",
    }
    markdown = markdown_path.read_text()
    assert "# Recommendation model comparison" in markdown
    assert "win" in markdown
