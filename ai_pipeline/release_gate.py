"""Fail-closed production approval combining offline and operational evidence."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

from .artifact import sha256_file
from .schemas import parse_datetime

METRICS = ("impression_auc", "mrr", "ndcg_at_5", "ndcg_at_10")
REQUIRED_SEGMENTS = (
    ("user_tenure", "new"),
    ("article_tenure", "new"),
    ("language", "vi"),
)


def _number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def check_window(window, *, minimum_hours: int, minimum_requests: int, shadow: bool):
    reasons = []
    try:
        start, end = (
            parse_datetime(window["started_at"]),
            parse_datetime(window["ended_at"]),
        )
        if (end - start).total_seconds() < minimum_hours * 3600 or end > datetime.now(
            timezone.utc
        ):
            reasons.append("observation_window")
    except (KeyError, ValueError, TypeError):
        reasons.append("observation_window")
    count = window.get("requests")
    if type(count) is not int or count < minimum_requests:
        reasons.append("request_count")
    for name, maximum in [
        ("p95_ms", 500),
        ("fallback_rate", 0.01),
        ("error_rate", 0.001),
    ]:
        value = window.get(name)
        if not _number(value) or not 0 <= value <= maximum:
            reasons.append(name)
    if shadow and (
        type(window.get("order_changes")) is not int or window.get("order_changes") != 0
    ):
        reasons.append("shadow_order_changes")
    return reasons


def _trace_valid(trace):
    try:
        for key in ["request_group", "candidate_group", "dataset_sample_id"]:
            if not re.fullmatch("[a-f0-9]{64}", trace[key]):
                return False
        times = [
            parse_datetime(trace[k])
            for k in [
                "served_at",
                "visible_at",
                "click_at",
                "dwell_at",
                "history_reference_at",
                "shadow_scored_at",
            ]
        ]
        if not (
            times[0]
            <= times[1]
            <= times[2]
            <= times[3]
            < times[4]
            <= times[5]
            <= datetime.now(timezone.utc)
        ):
            return False
        return (
            trace["feature_schema_version"] == "rank-features-v2"
            and trace["history_schema_version"] == "user-history-snapshot-v1"
            and trace["dataset_schema_version"] == "recommendation-dataset-v2"
            and type(trace["dwell_ms"]) is int
            and trace["dwell_ms"] >= 10000
            and bool(trace["model_version"])
        )
    except (KeyError, TypeError, ValueError):
        return False


def evaluate_release(report, evidence, *, comparison_sha256=None, model_sha256=None):
    missing, failures = [], []
    evidence = evidence or {}
    if evidence.get("evidence_schema_version") != "recommendation-release-evidence-v1":
        missing.append("versioned_release_evidence")
    if (
        evidence.get("environment") != "production"
        or evidence.get("dataset", {}).get("source_format") != "oecophylla-telemetry-v2"
    ):
        missing.append("production_domain_holdout")
    provenance = report.get("data_provenance", {})
    if provenance.get("source_formats") != ["oecophylla-telemetry-v2"]:
        missing.append("comparison_production_provenance")
    if not provenance.get("dataset_sha256") or provenance.get(
        "dataset_sha256"
    ) != evidence.get("dataset", {}).get("sha256"):
        missing.append("dataset_evidence_binding")
    if provenance.get("model_sha256") != model_sha256 or not model_sha256:
        missing.append("comparison_model_binding")
    for field in [
        "privacy_review_passed",
        "temporal_audit_passed",
        "serving_policy_parity_passed",
    ]:
        if evidence.get("dataset", {}).get(field) is not True:
            missing.append(field)
    if (
        type(report.get("sample", {}).get("requests")) is not int
        or report["sample"]["requests"] < 1000
    ):
        missing.append("minimum_1000_test_requests")
    # Require request-bootstrap bounds against both logged policy and LR; point
    # estimates alone cannot establish no regression.
    for name in ["pure_vs_logged_position", "pure_vs_logistic"]:
        for metric in METRICS:
            interval = (
                report.get("comparisons", {}).get(name, {}).get(metric, {}).get("ci95")
            )
            if (
                not isinstance(interval, list)
                or len(interval) != 2
                or not all(_number(v) for v in interval)
            ):
                missing.append(f"{name}:{metric}:confidence_interval")
            elif interval[1] < -0.01:
                failures.append(f"{name}:{metric}:regression")
            elif interval[0] < -0.01:
                missing.append(f"{name}:{metric}:uncertain_no_regression")
    for name, bucket in REQUIRED_SEGMENTS:
        segment = report.get("segments", {}).get(name, {}).get(bucket, {})
        if any(
            type(segment.get(key)) is not int or segment[key] < 100
            for key in ["requests", "impression_auc_eligible_requests"]
        ):
            missing.append(f"{name}:{bucket}:minimum_100_requests")
        for baseline in ["logged_position", "logistic"]:
            for metric in METRICS:
                interval = (
                    segment.get("comparisons", {})
                    .get(baseline, {})
                    .get(metric, {})
                    .get("ci95")
                )
                if (
                    not isinstance(interval, list)
                    or len(interval) != 2
                    or not all(_number(v) for v in interval)
                ):
                    missing.append(
                        f"{name}:{bucket}:{baseline}:{metric}:confidence_interval"
                    )
                elif interval[1] < -0.01:
                    failures.append(f"{name}:{bucket}:{baseline}:{metric}:regression")
                elif interval[0] < -0.01:
                    missing.append(
                        f"{name}:{bucket}:{baseline}:{metric}:uncertain_no_regression"
                    )
    models = report.get("models", {})
    for model in ["pure_model", "post_policy"]:
        for metric, higher in [
            ("coverage_at_k", True),
            ("embedding_diversity_at_k", True),
            ("strong_negative_rate_at_k", False),
        ]:
            value = models.get(model, {}).get(metric)
            baseline = models.get("logged_position_baseline", {}).get(metric)
            if not _number(value) or not _number(baseline):
                missing.append(f"{model}:{metric}")
            elif (baseline - value if higher else value - baseline) > 0.02:
                failures.append(f"{model}:{metric}:guardrail_regression")
    for name, hours, count in [("shadow", 48, 10000), ("canary", 24, 5000)]:
        if (
            evidence.get(name, {}).get("model_sha256") != model_sha256
            or not model_sha256
        ):
            missing.append(f"{name}:model_evidence_binding")
        missing.extend(
            f"{name}:{r}"
            for r in check_window(
                evidence.get(name, {}),
                minimum_hours=hours,
                minimum_requests=count,
                shadow=name == "shadow",
            )
        )
    try:
        if parse_datetime(evidence["canary"]["started_at"]) < parse_datetime(
            evidence["shadow"]["ended_at"]
        ):
            missing.append("canary_must_follow_shadow")
    except (KeyError, TypeError, ValueError):
        missing.append("shadow_canary_chronology")
    traffic = evidence.get("canary", {}).get("traffic_percent")
    if not _number(traffic) or not 0 < traffic <= 5:
        missing.append("bounded_canary_traffic")
    if not _trace_valid(evidence.get("trace", {})):
        missing.append("served_behavior_dataset_history_shadow_trace")
    if (
        evidence.get("rollback", {}).get("heuristic_passed") is not True
        or evidence.get("rollback", {}).get("model_sha256") != model_sha256
    ):
        missing.append("rollback_rehearsal")
    for name, expected in [
        ("comparison_sha256", comparison_sha256),
        ("model_sha256", model_sha256),
    ]:
        if not expected or evidence.get(name) != expected:
            missing.append(name + ":evidence_binding")
    decision = "FAIL" if failures else ("INCONCLUSIVE" if missing else "NO_REGRESSION")
    if not failures and not missing:
        ci = report["comparisons"]["pure_vs_logged_position"]["ndcg_at_10"]["ci95"]
        if ci[0] > 0:
            decision = "WIN"
    return dict(
        release_schema_version="recommendation-release-gate-v1",
        decision=decision,
        approved=decision in ("WIN", "NO_REGRESSION"),
        missing_evidence=sorted(set(missing)),
        failures=sorted(set(failures)),
        comparison_sha256=comparison_sha256,
        model_sha256=model_sha256,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_release(
        json.loads(args.comparison.read_text()),
        json.loads(args.evidence.read_text()) if args.evidence else None,
        comparison_sha256=sha256_file(args.comparison),
        model_sha256=sha256_file(args.model),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "output": str(args.output)}))
    return 0 if result["approved"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
