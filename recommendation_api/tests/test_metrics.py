from __future__ import annotations

import math

import pytest

from app.metrics import (
    catalog_coverage,
    hit_rate_at_k,
    impression_auc,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    topic_diversity,
    topic_precision_at_k,
)


def test_ranking_metrics_match_a_hand_calculated_example():
    ranked = ["post-a", "post-b", "post-c"]
    relevant = {"post-a", "post-c", "post-d"}

    assert precision_at_k(ranked, relevant, k=3) == pytest.approx(2 / 3)
    assert recall_at_k(ranked, relevant, k=3) == pytest.approx(2 / 3)
    expected_ndcg = (1.0 + 1.0 / math.log2(4)) / (
        1.0 + 1.0 / math.log2(3) + 1.0 / math.log2(4)
    )
    assert ndcg_at_k(ranked, relevant, k=3) == pytest.approx(expected_ndcg)
    assert hit_rate_at_k(ranked, relevant, k=3) == 1.0
    assert reciprocal_rank(ranked, relevant) == pytest.approx(1.0)


def test_mind_impression_auc_counts_ties_and_excludes_single_class_groups():
    assert impression_auc([0.9, 0.8, 0.1], [1, 0, 0]) == 1.0
    assert impression_auc([0.5, 0.5], [1, 0]) == 0.5
    assert impression_auc([0.9, 0.1], [0, 0]) is None
    assert impression_auc([0.9, 0.1], [1, 1]) is None


def test_zero_click_impression_has_zero_reciprocal_rank():
    assert reciprocal_rank(["post-a", "post-b"], set()) == 0.0


def test_metrics_do_not_divide_by_zero():
    assert precision_at_k([], set(), k=10) == 0.0
    assert recall_at_k(["post-a"], set(), k=10) == 0.0
    assert ndcg_at_k([], set(), k=10) == 0.0
    assert hit_rate_at_k([], set(), k=10) == 0.0
    assert catalog_coverage([], catalog_size=0) == 0.0
    assert topic_diversity([]) == 0.0


def test_precision_at_k_uses_k_as_the_denominator():
    assert precision_at_k(["post-a"], {"post-a"}, k=3) == pytest.approx(1 / 3)


def test_topic_names_are_compared_as_topics_not_character_sets():
    ranked_topics = [["business"], ["technology"], ["ai"]]
    positive_topics = {"business", "technology", "ai"}

    assert topic_precision_at_k(ranked_topics, positive_topics, k=3) == 1.0


def test_coverage_and_topic_diversity_match_small_fixture():
    assert catalog_coverage(
        [["post-a", "post-b"], ["post-b", "post-c"]], catalog_size=5
    ) == pytest.approx(3 / 5)
    assert topic_diversity([["ai", "technology"], ["ai"], []]) == pytest.approx(2 / 3)


@pytest.mark.parametrize("k", [0, -1])
def test_ranking_metrics_reject_non_positive_k(k: int):
    with pytest.raises(ValueError, match="k must be positive"):
        precision_at_k(["post-a"], {"post-a"}, k=k)
