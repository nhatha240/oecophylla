from __future__ import annotations

import numpy as np
import pytest

from ai_pipeline.benchmark import (
    evaluate_models,
    metrics_for_request,
    paired_comparison,
    score_models,
    validate_holdout,
    write_reports,
)
from ai_pipeline.model import NRMSArchitecture, NRMSLikeRanker


def rows():
    return [
        {
            "request_group": "r1",
            "user_group": "u1",
            "history": [],
            "candidates": [0, 1, 2],
            "labels": [1, 0, 1],
            "split": "test",
        },
        {
            "request_group": "r2",
            "user_group": "u2",
            "history": [0, 1],
            "candidates": [0, 1, 2],
            "labels": [0, 1, 0],
            "split": "test",
        },
    ]


def test_mind_mrr_differs_from_first_click_and_short_slate_precision_is_defined():
    metrics = metrics_for_request([1, 0, 1], [3, 2, 1])
    assert metrics["mrr"] == pytest.approx(2 / 3)
    assert metrics["first_click_mrr"] == 1
    assert metrics["impression_auc"] == 0.5
    assert metrics["precision_at_5"] == 0.4
    assert metrics["recall_at_10"] == 1
    assert metrics["ndcg_at_10"] == pytest.approx(
        (1 + 1 / np.log2(4)) / (1 + 1 / np.log2(3))
    )


def test_auc_ties_and_ineligible_requests_are_explicit():
    assert metrics_for_request([1, 0], [1, 1])["impression_auc"] == 0.5
    absent = metrics_for_request([0, 0], [1, 2])
    assert absent["impression_auc"] is None
    assert absent["mrr"] == absent["recall_at_5"] == absent["hit_at_5"] == 0
    with pytest.raises(ValueError):
        metrics_for_request([1, 0], [float("nan"), 2])
    with pytest.raises(ValueError):
        metrics_for_request([1, 2], [1, 2])


def test_overlap_training_rows_and_misaligned_embeddings_are_rejected():
    vectors = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
    validate_holdout(rows(), vectors, dimension=2, history_limit=20)
    with pytest.raises(ValueError, match="test"):
        validate_holdout(
            [{**rows()[0], "split": "train"}], vectors, dimension=2, history_limit=20
        )
    with pytest.raises(ValueError, match="duplicate"):
        validate_holdout([rows()[0], rows()[0]], vectors, dimension=2, history_limit=20)
    with pytest.raises(ValueError, match="index"):
        validate_holdout(
            [{**rows()[0], "candidates": [0, 1, 8]}],
            vectors,
            dimension=2,
            history_limit=20,
        )


def test_baselines_do_not_depend_on_labels_or_request_iteration_order():
    vectors = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
    ranker = NRMSLikeRanker.initialize(
        NRMSArchitecture(
            embedding_dimension=2, attention_heads=1, history_length=20, seed=7
        ),
        popular_embedding=np.array([1.0, 0.0]),
    )
    scores = score_models(rows(), vectors, ranker, seed=19)
    reordered = score_models(list(reversed(rows())), vectors, ranker, seed=19)
    changed = score_models(
        [{**row, "labels": [0, 0, 0]} for row in rows()], vectors, ranker, seed=19
    )
    assert set(scores) == {"logged_order", "random", "semantic_mean_pool", "nrms"}
    for model, values in scores.items():
        for index in range(2):
            assert np.array_equal(values[index], reordered[model][1 - index])
            assert np.array_equal(values[index], changed[model][index])
    assert np.array_equal(scores["nrms"][0], scores["semantic_mean_pool"][0])


def test_aggregation_reports_catalog_coverage_and_history_segments():
    vectors = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
    report, individual = evaluate_models(
        rows(), {"nrms": [np.array([3, 2, 1]), np.array([1, 3, 2])]}, vectors
    )
    model = report["nrms"]
    assert model["requests"] == 2 and model["candidates"] == 6
    assert model["auc_eligible_requests"] == 2
    assert model["coverage_at_10"] == 1
    assert model["embedding_diversity_at_10"] == pytest.approx(4 / 3)
    assert model["segments"]["cold"]["requests"] == 1
    assert model["segments"]["history_1_2"]["requests"] == 1
    assert len(individual["nrms"]) == 2


def test_user_cluster_bootstrap_preserves_request_weighting_and_correlation():
    requests = [{"user_group": "a"}] * 8 + [{"user_group": "b"}] * 2
    candidate = [{"ndcg_at_10": 0.6}] * 8 + [{"ndcg_at_10": 0.2}] * 2
    baseline = [{"ndcg_at_10": 0.4}] * 10
    result = paired_comparison(requests, candidate, baseline, seed=7, resamples=1000)
    assert result["delta"] == pytest.approx(0.12)
    assert result["user_cluster_ci95"] == pytest.approx([-0.2, 0.2])
    assert result["unique_users"] == 2
    assert result["user_cluster_ci95"][0] < result["request_ci95"][0]


def test_reports_are_machine_readable_and_cannot_overwrite_a_completed_run(tmp_path):
    vectors = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
    models, individual = evaluate_models(
        rows(), {"nrms": [np.array([3, 2, 1]), np.array([1, 3, 2])]}, vectors
    )
    report = {
        "models": models,
        "comparison": {"delta": 0, "request_ci95": [0, 0], "user_cluster_ci95": [0, 0]},
        "decision": "inconclusive",
        "latency": {},
        "limitations": ["Offline only"],
    }
    write_reports(tmp_path, report, rows(), individual)
    assert (tmp_path / "report.json").is_file()
    assert "nrms" in (tmp_path / "metrics.csv").read_text()
    assert "u1" in (tmp_path / "per-request.csv").read_text()
    assert "Offline only" in (tmp_path / "report.md").read_text()
    with pytest.raises(FileExistsError):
        write_reports(tmp_path, report, rows(), individual)
