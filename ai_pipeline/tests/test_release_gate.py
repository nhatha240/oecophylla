def test_release_gate_cannot_promote_mind_or_missing_live_evidence():
    from ai_pipeline.release_gate import evaluate_release

    report = dict(
        promotion=dict(eligible=True, conclusion="win"),
        sample=dict(requests=10000),
        segments={},
    )
    result = evaluate_release(report, None)
    assert result["decision"] == "INCONCLUSIVE"
    assert not result["approved"]
    evidence = dict(
        dataset=dict(source_format="official-mind-tsv-v1"), environment="benchmark"
    )
    assert not evaluate_release(report, evidence)["approved"]


def test_nonfinite_operational_values_never_approve():
    from ai_pipeline.release_gate import check_window

    window = dict(
        started_at="2026-09-01T00:00:00+00:00",
        ended_at="2026-09-04T00:00:00+00:00",
        requests=10000,
        p95_ms=float("nan"),
        fallback_rate=0,
        error_rate=0,
        order_changes=0,
    )
    assert check_window(window, minimum_hours=48, minimum_requests=10000, shadow=True)
    window["p95_ms"] = 100
    assert not check_window(
        window, minimum_hours=48, minimum_requests=10000, shadow=True
    )
    window["order_changes"] = 1
    assert check_window(window, minimum_hours=48, minimum_requests=10000, shadow=True)


def test_complete_bound_evidence_passes_and_changed_model_is_rejected():
    from ai_pipeline.release_gate import evaluate_release, METRICS, REQUIRED_SEGMENTS

    pair = {metric: dict(ci95=[0.01, 0.03]) for metric in METRICS}
    metrics = dict(
        coverage_at_k=0.5, embedding_diversity_at_k=0.5, strong_negative_rate_at_k=0
    )
    model_hash, comparison_hash, dataset_hash = "a" * 64, "b" * 64, "c" * 64
    report = dict(
        sample=dict(requests=1000),
        comparisons=dict(pure_vs_logged_position=pair, pure_vs_logistic=pair),
        models={
            name: metrics
            for name in ["pure_model", "post_policy", "logged_position_baseline"]
        },
        data_provenance=dict(
            source_formats=["oecophylla-telemetry-v2"],
            model_sha256=model_hash,
            dataset_sha256=dataset_hash,
        ),
        segments={},
    )
    for name, bucket in REQUIRED_SEGMENTS:
        report["segments"][name] = {
            bucket: dict(
                requests=100,
                impression_auc_eligible_requests=100,
                comparisons=dict(logged_position=pair, logistic=pair),
            )
        }
    window = dict(
        started_at="2026-09-01T00:00:00+00:00",
        ended_at="2026-09-04T00:00:00+00:00",
        requests=10000,
        p95_ms=100,
        fallback_rate=0,
        error_rate=0,
        order_changes=0,
        traffic_percent=5,
        model_sha256=model_hash,
    )
    trace = dict(
        request_group="1" * 64,
        candidate_group="2" * 64,
        dataset_sample_id="3" * 64,
        served_at="2026-09-01T01:00:00+00:00",
        visible_at="2026-09-01T01:00:01+00:00",
        click_at="2026-09-01T01:00:02+00:00",
        dwell_at="2026-09-01T01:00:13+00:00",
        history_reference_at="2026-09-01T01:01:00+00:00",
        shadow_scored_at="2026-09-01T01:01:01+00:00",
        dwell_ms=10000,
        model_version="nrms-v1",
        feature_schema_version="rank-features-v2",
        history_schema_version="user-history-snapshot-v1",
        dataset_schema_version="recommendation-dataset-v2",
    )
    evidence = dict(
        evidence_schema_version="recommendation-release-evidence-v1",
        environment="production",
        dataset=dict(
            source_format="oecophylla-telemetry-v2",
            sha256=dataset_hash,
            privacy_review_passed=True,
            temporal_audit_passed=True,
            serving_policy_parity_passed=True,
        ),
        trace=trace,
        shadow=window,
        canary=dict(
            window,
            started_at="2026-09-04T00:00:00+00:00",
            ended_at="2026-09-06T00:00:00+00:00",
        ),
        rollback=dict(heuristic_passed=True, model_sha256=model_hash),
        model_sha256=model_hash,
        comparison_sha256=comparison_hash,
    )
    assert evaluate_release(
        report, evidence, comparison_sha256=comparison_hash, model_sha256=model_hash
    )["approved"]
    assert not evaluate_release(
        report, evidence, comparison_sha256=comparison_hash, model_sha256="d" * 64
    )["approved"]
    report["sample"]["requests"] = float("nan")
    assert not evaluate_release(
        report, evidence, comparison_sha256=comparison_hash, model_sha256=model_hash
    )["approved"]
