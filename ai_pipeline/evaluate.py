from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Mapping, Protocol, Sequence

import numpy as np
import pyarrow.parquet as pq
from sklearn.linear_model import LogisticRegression

from .artifact import MODEL_FILENAME, load_artifact
from .model import FEATURE_COLUMNS
from .schemas import parse_datetime

METRIC_NAMES = (
    "impression_auc",
    "mrr",
    "ndcg_at_5",
    "ndcg_at_10",
    "precision_at_k",
    "recall_at_k",
    "ndcg_at_k",
    "hit_rate",
    "coverage",
    "diversity",
    "strong_negative_rate",
)


class ScoreArtifact(Protocol):
    manifest: Mapping[str, Any]

    def predict_scores(self, records: Sequence[Mapping[str, Any]]) -> list[float]: ...


def _precision(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    return sum(item in relevant for item in ranked[:k]) / k


def _recall(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    return len(set(ranked[:k]) & relevant) / len(relevant) if relevant else 0.0


def _ndcg(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    dcg = sum(
        1 / math.log2(index + 2)
        for index, item in enumerate(ranked[:k])
        if item in relevant
    )
    ideal = sum(1 / math.log2(index + 2) for index in range(min(k, len(relevant))))
    return dcg / ideal


def _mean(values: Sequence[float]) -> float:
    return round(fmean(values), 6) if values else 0.0


def _reciprocal_rank(ranked: Sequence[str], relevant: set[str]) -> float:
    for rank, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def _impression_auc(
    candidates: Sequence[tuple[Mapping[str, Any], float]],
) -> float | None:
    positives = [score for row, score in candidates if int(row["label"]) > 0]
    negatives = [score for row, score in candidates if int(row["label"]) <= 0]
    if not positives or not negatives:
        return None
    credit = sum(
        1.0 if positive > negative else (0.5 if positive == negative else 0.0)
        for positive in positives
        for negative in negatives
    )
    return credit / (len(positives) * len(negatives))


def _evaluate_scores(
    rows: Sequence[Mapping[str, Any]], scores: Sequence[float], k: int
) -> tuple[dict[str, Any], dict[str, list[float]]]:
    grouped: dict[str, list[tuple[Mapping[str, Any], float]]] = defaultdict(list)
    for row, score in zip(rows, scores, strict=True):
        grouped[str(row["request_group"])].append((row, score))

    per_request: dict[str, list[float]] = defaultdict(list)
    top_posts: set[str] = set()
    for request_group in sorted(grouped):
        candidates = grouped[request_group]
        ranked = sorted(
            candidates,
            key=lambda pair: (
                -pair[1],
                int(pair[0]["position"]),
                str(pair[0]["post_group"]),
            ),
        )
        ranked_ids = [str(row["post_group"]) for row, _ in ranked]
        relevant = {
            str(row["post_group"]) for row, _ in ranked if int(row["label"]) > 0
        }
        top = ranked[:k]
        top_posts.update(str(row["post_group"]) for row, _ in top)
        per_request["precision_at_k"].append(_precision(ranked_ids, relevant, k))
        per_request["recall_at_k"].append(_recall(ranked_ids, relevant, k))
        per_request["ndcg_at_k"].append(_ndcg(ranked_ids, relevant, k))
        per_request["mrr"].append(_reciprocal_rank(ranked_ids, relevant))
        per_request["ndcg_at_5"].append(_ndcg(ranked_ids, relevant, 5))
        per_request["ndcg_at_10"].append(_ndcg(ranked_ids, relevant, 10))
        auc = _impression_auc(candidates)
        if auc is not None:
            per_request["impression_auc"].append(auc)
        per_request["hit_rate"].append(float(bool(set(ranked_ids[:k]) & relevant)))
        per_request["diversity"].append(
            len({str(row["candidate_source"]) for row, _ in top}) / len(top)
            if top
            else 0.0
        )
        per_request["strong_negative_rate"].append(
            sum(row["label_name"] == "strong_negative" for row, _ in top) / k
        )

    catalog = {str(row["post_group"]) for row in rows}
    metrics = {
        name: _mean(per_request[name]) for name in METRIC_NAMES if name != "coverage"
    }
    metrics["coverage"] = round(len(top_posts) / len(catalog), 6) if catalog else 0.0
    metrics["sample_impressions"] = len(rows)
    metrics["impression_auc_eligible_requests"] = len(
        per_request["impression_auc"]
    )
    metrics["impression_auc_excluded_requests"] = len(grouped) - len(
        per_request["impression_auc"]
    )
    return metrics, per_request


def _bootstrap_ci95(
    values: Sequence[float], *, seed: int, resamples: int = 1_000
) -> list[float]:
    if not values:
        raise ValueError("confidence interval requires request-level values")
    if len(values) == 1:
        value = round(float(values[0]), 6)
        return [value, value]
    generator = random.Random(seed)
    sample_size = len(values)
    means = sorted(
        fmean(generator.choice(values) for _ in range(sample_size))
        for _ in range(resamples)
    )
    lower = means[round(0.025 * (resamples - 1))]
    upper = means[round(0.975 * (resamples - 1))]
    return [round(max(0.0, lower), 6), round(min(1.0, upper), 6)]


def _validate_group_contract(rows: Sequence[Mapping[str, Any]]) -> None:
    splits_by_request: dict[str, set[str]] = defaultdict(set)
    users_by_request: dict[str, set[str]] = defaultdict(set)
    candidates_by_request: dict[str, int] = defaultdict(int)
    for row in rows:
        request_group = row.get("request_group")
        user_group = row.get("user_group")
        if not request_group or not user_group:
            raise ValueError("dataset requires stable user_group and request_group")
        request = str(request_group)
        splits_by_request[request].add(str(row.get("split")))
        users_by_request[request].add(str(user_group))
        candidates_by_request[request] += 1
    if any(len(splits) != 1 for splits in splits_by_request.values()):
        raise ValueError("request_group appears in multiple dataset splits")
    if any(len(users) != 1 for users in users_by_request.values()):
        raise ValueError("request_group has conflicting canonical identities")
    undersized = [
        request for request, count in candidates_by_request.items() if count < 2
    ]
    if undersized:
        raise ValueError("every request requires at least two candidates")


def compare_holdout(
    rows: Sequence[Mapping[str, Any]],
    artifact: ScoreArtifact,
    *,
    k: int = 10,
    minimum_requests: int = 30,
    minimum_auc_requests: int | None = None,
    ndcg_tolerance: float = 0.01,
    guardrail_drop: float = 0.02,
    win_delta: float = 0.01,
) -> dict[str, Any]:
    if k <= 0:
        raise ValueError("k must be positive")
    if minimum_requests <= 0:
        raise ValueError("minimum_requests must be positive")
    minimum_auc_requests = (
        minimum_requests if minimum_auc_requests is None else minimum_auc_requests
    )
    if minimum_auc_requests <= 0:
        raise ValueError("minimum_auc_requests must be positive")
    _validate_group_contract(rows)
    holdout = [row for row in rows if row.get("split") == "test"]
    if not holdout:
        raise ValueError("dataset has no test holdout")
    records = [{name: row[name] for name in FEATURE_COLUMNS} for row in holdout]
    ml_scores = artifact.predict_scores(records)
    if len(ml_scores) != len(holdout):
        raise ValueError("model score count does not match holdout")
    baseline_scores = [float(row["heuristic_score"] or 0.0) for row in holdout]
    baseline, baseline_requests = _evaluate_scores(holdout, baseline_scores, k)
    ml, ml_requests = _evaluate_scores(holdout, ml_scores, k)

    request_count = len({str(row["request_group"]) for row in holdout})
    auc_eligible_requests = ml["impression_auc_eligible_requests"]
    auc_excluded_requests = ml["impression_auc_excluded_requests"]
    conclusion = "no_regression"
    if (
        request_count < minimum_requests
        or auc_eligible_requests < minimum_auc_requests
    ):
        conclusion = "inconclusive"
    elif (
        ml["ndcg_at_k"] < baseline["ndcg_at_k"] - ndcg_tolerance
        or ml["impression_auc"]
        < baseline["impression_auc"] - ndcg_tolerance
        or ml["mrr"] < baseline["mrr"] - ndcg_tolerance
        or ml["ndcg_at_5"] < baseline["ndcg_at_5"] - ndcg_tolerance
        or ml["ndcg_at_10"] < baseline["ndcg_at_10"] - ndcg_tolerance
        or ml["coverage"] < baseline["coverage"] - guardrail_drop
        or ml["diversity"] < baseline["diversity"] - guardrail_drop
        or ml["strong_negative_rate"]
        > baseline["strong_negative_rate"] + guardrail_drop
    ):
        conclusion = "fail"
    elif ml["ndcg_at_k"] >= baseline["ndcg_at_k"] + win_delta:
        conclusion = "win"

    confidence_intervals: dict[str, list[float] | None] | None = None
    if request_count >= 30:
        confidence_intervals = {}
        for index, metric in enumerate(
            (
                "ndcg_at_k",
                "impression_auc",
                "mrr",
                "ndcg_at_5",
                "ndcg_at_10",
            )
        ):
            baseline_values = baseline_requests[metric]
            ml_values = ml_requests[metric]
            confidence_intervals[f"baseline_{metric}"] = (
                _bootstrap_ci95(baseline_values, seed=index * 2)
                if baseline_values
                else None
            )
            confidence_intervals[f"ml_{metric}"] = (
                _bootstrap_ci95(ml_values, seed=index * 2 + 1)
                if ml_values
                else None
            )
    sample_ids = sorted(str(row["sample_id"]) for row in holdout)
    checksum = hashlib.sha256("\n".join(sample_ids).encode()).hexdigest()
    manifest = artifact.manifest
    return {
        "report_schema_version": "recommendation-comparison-v1",
        "artifact": {
            "model_version": manifest["model_version"],
            "model_sha256": manifest["files"][MODEL_FILENAME]["sha256"],
        },
        "config": {
            "k": k,
            "minimum_requests": minimum_requests,
            "minimum_auc_requests": minimum_auc_requests,
            "ndcg_tolerance": ndcg_tolerance,
            "guardrail_drop": guardrail_drop,
            "win_delta": win_delta,
        },
        "sample": {
            "users": len({str(row["user_group"]) for row in holdout}),
            "requests": request_count,
            "impressions": len(holdout),
            "auc_eligible_requests": auc_eligible_requests,
            "auc_excluded_requests": auc_excluded_requests,
        },
        "holdout_checksum": checksum,
        "baseline": baseline,
        "ml": ml,
        "confidence_intervals": confidence_intervals,
        "confidence_interval_method": "request_group_bootstrap_percentile_95",
        "conclusion": conclusion,
    }


# --- NRMS-like impression-aware ranker evaluation (T7, dataset schema v2) -

NRMS_SEGMENT_NAMES = (
    "user_tenure",
    "article_tenure",
    "history_length",
    "feed_source",
    "language",
)


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    left_vector = np.asarray(left, dtype=float)
    right_vector = np.asarray(right, dtype=float)
    left_norm = np.linalg.norm(left_vector)
    right_norm = np.linalg.norm(right_vector)
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return float(np.dot(left_vector, right_vector) / (left_norm * right_norm))


def _mean_pool(vectors: Sequence[Sequence[float]]) -> np.ndarray | None:
    if not vectors:
        return None
    return np.asarray(vectors, dtype=float).mean(axis=0)


def _naive_user_vector(row: Mapping[str, Any]) -> np.ndarray | None:
    history_vectors = [
        entry["article"]["embedding"]
        for entry in row.get("history") or ()
        if (entry.get("article") or {}).get("embedding") is not None
    ]
    pooled = _mean_pool(history_vectors)
    if pooled is not None:
        return pooled
    declared = row.get("declared_topic_embedding")
    return np.asarray(declared, dtype=float) if declared is not None else None


def _logistic_baseline_feature(row: Mapping[str, Any]) -> float:
    user_vector = _naive_user_vector(row)
    candidate = (row.get("article") or {}).get("embedding")
    if user_vector is None or candidate is None:
        return 0.0
    return _cosine_similarity(user_vector, candidate)


def _logistic_baseline_scores(
    rows_by_split: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, float]:
    train_rows = rows_by_split.get("train", ())
    test_rows = rows_by_split.get("test", ())
    train_labels = [int(row["click_label"]) for row in train_rows]
    test_feature_rows = [[_logistic_baseline_feature(row)] for row in test_rows]
    if len(set(train_labels)) < 2:
        return {str(row["sample_id"]): 0.5 for row in test_rows}
    train_features = [[_logistic_baseline_feature(row)] for row in train_rows]
    model = LogisticRegression()
    model.fit(train_features, train_labels)
    probabilities = model.predict_proba(test_feature_rows)[:, 1]
    return {
        str(row["sample_id"]): float(score)
        for row, score in zip(test_rows, probabilities, strict=True)
    }


def _post_policy_scores(
    request_rows: Sequence[Mapping[str, Any]],
    pure_scores: Mapping[str, float],
    heuristic_scores: Mapping[str, float],
    *,
    confidence_threshold: float = 0.5,
) -> dict[str, float]:
    top_score = max(pure_scores.values())
    if top_score < confidence_threshold:
        return dict(heuristic_scores)
    return dict(pure_scores)


def _ndcg_binary(ranked_labels: Sequence[int], k: int) -> float:
    if not any(ranked_labels):
        return 0.0
    dcg = sum(
        1.0 / math.log2(index + 2)
        for index, label in enumerate(ranked_labels[:k])
        if label
    )
    ideal_hits = min(k, sum(ranked_labels))
    ideal = sum(1.0 / math.log2(index + 2) for index in range(ideal_hits))
    return dcg / ideal if ideal else 0.0


def _mrr_binary(ranked_labels: Sequence[int]) -> float:
    for rank, label in enumerate(ranked_labels, start=1):
        if label:
            return 1.0 / rank
    return 0.0


def _pairwise_auc(pairs: Sequence[tuple[float, int]]) -> float | None:
    positives = [score for score, label in pairs if label]
    negatives = [score for score, label in pairs if not label]
    if not positives or not negatives:
        return None
    credit = sum(
        1.0 if positive > negative else (0.5 if positive == negative else 0.0)
        for positive in positives
        for negative in negatives
    )
    return credit / (len(positives) * len(negatives))


def _request_metrics(
    rows: Sequence[Mapping[str, Any]], scores_by_id: Mapping[str, float]
) -> dict[str, float | None]:
    ranked = sorted(
        rows,
        key=lambda row: (-scores_by_id[str(row["sample_id"])], int(row["position"])),
    )
    ranked_labels = [int(row["click_label"]) for row in ranked]
    pairs = [
        (scores_by_id[str(row["sample_id"])], int(row["click_label"])) for row in rows
    ]
    return {
        "mrr": _mrr_binary(ranked_labels),
        "ndcg_at_5": _ndcg_binary(ranked_labels, 5),
        "ndcg_at_10": _ndcg_binary(ranked_labels, 10),
        "impression_auc": _pairwise_auc(pairs),
    }


def _aggregate_model_metrics(
    rows_by_request: Mapping[str, Sequence[Mapping[str, Any]]],
    scores_by_id: Mapping[str, float],
) -> dict[str, Any]:
    per_request = [
        _request_metrics(rows, scores_by_id) for rows in rows_by_request.values()
    ]
    result: dict[str, Any] = {}
    for key in ("mrr", "ndcg_at_5", "ndcg_at_10"):
        values = [entry[key] for entry in per_request]
        result[key] = round(fmean(values), 6) if values else 0.0
    auc_values = [
        entry["impression_auc"]
        for entry in per_request
        if entry["impression_auc"] is not None
    ]
    result["impression_auc"] = round(fmean(auc_values), 6) if auc_values else None
    result["impression_auc_eligible_requests"] = len(auc_values)
    result["requests"] = len(per_request)
    return result


def _validate_v2_segment_contract(rows: Sequence[Mapping[str, Any]]) -> None:
    missing_feed_source = any("feed_source" not in row for row in rows)
    missing_language = any("language" not in row for row in rows)
    if missing_feed_source or missing_language:
        raise ValueError(
            "dataset rows are missing required segment fields (feed_source/language)"
        )


def _bucket_user_tenure(row: Mapping[str, Any]) -> str:
    return "existing" if row.get("history") else "new"


def _bucket_article_tenure(
    row: Mapping[str, Any], *, threshold_hours: float = 24.0
) -> str:
    article = row.get("article") or {}
    updated = article.get("feature_source_updated_at")
    served = row.get("served_at")
    if updated is None or served is None:
        return "unknown"
    age_hours = (parse_datetime(served) - parse_datetime(updated)).total_seconds() / 3600.0
    return "new" if age_hours <= threshold_hours else "established"


def _bucket_history_length(row: Mapping[str, Any]) -> str:
    length = len(row.get("history") or ())
    if length == 0:
        return "0"
    if length <= 2:
        return "1-2"
    return "3+"


def _representative_positive(
    rows: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    for row in rows:
        if int(row["click_label"]) == 1:
            return row
    return rows[0]


def _segment_bucket_keys(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    representative = rows[0]
    positive = _representative_positive(rows)
    return {
        "user_tenure": _bucket_user_tenure(representative),
        "article_tenure": _bucket_article_tenure(positive),
        "history_length": _bucket_history_length(representative),
        "feed_source": str(representative.get("feed_source")),
        "language": str(representative.get("language")),
    }


def _segment_report(
    rows_by_request: Mapping[str, Sequence[Mapping[str, Any]]],
    scores_by_id: Mapping[str, float],
) -> dict[str, dict[str, Any]]:
    bucket_requests: dict[str, dict[str, list[str]]] = {
        name: defaultdict(list) for name in NRMS_SEGMENT_NAMES
    }
    for request_group, rows in rows_by_request.items():
        keys = _segment_bucket_keys(rows)
        for name, bucket in keys.items():
            bucket_requests[name][bucket].append(request_group)

    segments: dict[str, dict[str, Any]] = {}
    for name, buckets in bucket_requests.items():
        segments[name] = {
            bucket: _aggregate_model_metrics(
                {request: rows_by_request[request] for request in requests},
                scores_by_id,
            )
            for bucket, requests in buckets.items()
        }
    return segments


def compare_nrms_holdout(
    rows: Sequence[Mapping[str, Any]],
    artifact: ScoreArtifact,
    *,
    minimum_requests: int = 30,
    minimum_auc_requests: int | None = None,
) -> dict[str, Any]:
    if minimum_requests <= 0:
        raise ValueError("minimum_requests must be positive")
    minimum_auc_requests = (
        minimum_requests if minimum_auc_requests is None else minimum_auc_requests
    )
    if minimum_auc_requests <= 0:
        raise ValueError("minimum_auc_requests must be positive")
    _validate_v2_segment_contract(rows)

    rows_by_split: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        rows_by_split[str(row["split"])].append(row)
    test_rows = rows_by_split.get("test", [])
    if not test_rows:
        raise ValueError("dataset has no test holdout")

    test_by_request: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in test_rows:
        test_by_request[str(row["request_group"])].append(row)

    heuristic_scores = {
        str(row["sample_id"]): -float(row["position"]) for row in test_rows
    }
    logistic_scores = _logistic_baseline_scores(rows_by_split)
    pure_scores = dict(
        zip(
            (str(row["sample_id"]) for row in test_rows),
            artifact.predict_scores(test_rows),
            strict=True,
        )
    )

    post_policy_scores: dict[str, float] = {}
    for request_rows in test_by_request.values():
        ids = [str(row["sample_id"]) for row in request_rows]
        request_pure = {sample_id: pure_scores[sample_id] for sample_id in ids}
        request_heuristic = {sample_id: heuristic_scores[sample_id] for sample_id in ids}
        post_policy_scores.update(
            _post_policy_scores(request_rows, request_pure, request_heuristic)
        )

    models = {
        "heuristic_baseline": _aggregate_model_metrics(test_by_request, heuristic_scores),
        "logistic_baseline": _aggregate_model_metrics(test_by_request, logistic_scores),
        "pure_model": _aggregate_model_metrics(test_by_request, pure_scores),
        "post_policy": _aggregate_model_metrics(test_by_request, post_policy_scores),
    }
    segments = _segment_report(test_by_request, pure_scores)

    request_count = len(test_by_request)
    auc_eligible_requests = models["pure_model"]["impression_auc_eligible_requests"]
    if request_count < minimum_requests:
        promotion: dict[str, Any] = {
            "eligible": False,
            "reason": "insufficient_test_requests",
        }
    elif auc_eligible_requests < minimum_auc_requests:
        promotion = {
            "eligible": False,
            "reason": "insufficient_auc_eligible_requests",
        }
    else:
        promotion = {"eligible": True}

    return {
        "report_schema_version": "recommendation-nrms-comparison-v1",
        "evaluation_scope": "untouched-temporal-test-requests",
        "raw_model_precedes_post_policy": True,
        "sample": {
            "requests": request_count,
            "impressions": len(test_rows),
            "auc_eligible_requests": auc_eligible_requests,
        },
        "models": models,
        "segments": segments,
        "promotion": promotion,
    }


def write_comparison_report(
    report: Mapping[str, Any], output: Path
) -> tuple[Path, Path]:
    json_path = output if output.suffix == ".json" else output.with_suffix(".json")
    markdown_path = json_path.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    baseline = report["baseline"]
    ml = report["ml"]
    markdown_path.write_text(
        "\n".join(
            [
                "# Recommendation model comparison",
                "",
                f"- Conclusion: **{report['conclusion']}**",
                f"- Holdout impressions: {report['sample']['impressions']}",
                f"- Holdout requests: {report['sample']['requests']}",
                (
                    "- Impression AUC requests: "
                    f"{report['sample']['auc_eligible_requests']} eligible, "
                    f"{report['sample']['auc_excluded_requests']} excluded"
                ),
                f"- Artifact: `{report['artifact']['model_version']}`",
                "",
                "| Metric | Baseline | ML |",
                "|---|---:|---:|",
                *[
                    f"| {name} | {baseline[name]:.6f} | {ml[name]:.6f} |"
                    for name in METRIC_NAMES
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, markdown_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare heuristic and ML ranking on one temporal test holdout."
    )
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--minimum-requests", type=int, default=30)
    parser.add_argument("--minimum-auc-requests", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    rows = pq.read_table(args.dataset).to_pylist()
    artifact = load_artifact(args.artifact)
    report = compare_holdout(
        rows,
        artifact,
        k=args.k,
        minimum_requests=args.minimum_requests,
        minimum_auc_requests=args.minimum_auc_requests,
    )
    json_path, markdown_path = write_comparison_report(report, args.output)
    print(
        json.dumps(
            {
                "conclusion": report["conclusion"],
                "json": str(json_path),
                "markdown": str(markdown_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
