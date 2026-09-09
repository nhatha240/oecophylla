from copy import deepcopy


def test_release_gate_cannot_promote_mind_or_missing_live_evidence():
    from ai_pipeline.release_gate import evaluate_release
    report = dict(promotion=dict(eligible=True, conclusion='win'), sample=dict(requests=10000), segments={})
    result = evaluate_release(report, None)
    assert result['decision'] == 'INCONCLUSIVE'
    assert not result['approved']
    evidence = dict(dataset=dict(source_format='official-mind-tsv-v1'), environment='benchmark')
    assert not evaluate_release(report, evidence)['approved']


def test_nonfinite_operational_values_never_approve():
    from ai_pipeline.release_gate import check_window
    window = dict(started_at='2026-09-01T00:00:00+00:00', ended_at='2026-09-04T00:00:00+00:00',
                  requests=10000, p95_ms=float('nan'), fallback_rate=0, error_rate=0, order_changes=0)
    assert check_window(window, minimum_hours=48, minimum_requests=10000, shadow=True)
    window['p95_ms'] = 100
    assert not check_window(window, minimum_hours=48, minimum_requests=10000, shadow=True)
    window['order_changes'] = 1
    assert check_window(window, minimum_hours=48, minimum_requests=10000, shadow=True)
