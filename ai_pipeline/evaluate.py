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

import pyarrow.parquet as pq

from .artifact import MODEL_FILENAME, load_artifact
from .model import FEATURE_COLUMNS

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
