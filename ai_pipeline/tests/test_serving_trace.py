from dataclasses import replace
from datetime import timedelta
from uuid import UUID

from ai_pipeline.build_dataset import build_ranking_samples_v2
from ai_pipeline.tests.test_dataset_v2 import _load_local_fixture, config as config_fixture


def test_dataset_uses_generation_time_even_when_feed_is_served_later():
    config = config_fixture.__wrapped__()
    _, impressions, events, features = _load_local_fixture()
    impression = impressions[0]
    observed = impression.served_at - timedelta(minutes=1)
    late_click = replace(
        events[0],
        id=UUID(int=99999),
        occurred_at=observed + timedelta(seconds=1),
        ingested_at=observed + timedelta(seconds=1),
    )
    generation = str(UUID(int=88888))
    impressions = [
        replace(
            i,
            feature_snapshot=dict(
                i.feature_snapshot,
                schema_version="rank-features-v2",
                preference_observed_at=observed.isoformat(),
                retrieval_request_id=generation,
                candidate_published_at=(observed - timedelta(days=1)).isoformat(),
                content_language="vi",
                language_detector_version="unicode-script-heuristic-v1",
                declared_topics=[],
            ),
        )
        if i.request_id == impression.request_id
        else i
        for i in impressions
    ]
    result = build_ranking_samples_v2(
        impressions, events + [late_click], features, config
    )
    first_request_rows = [r for r in result.rows if r.served_at == impression.served_at]
    assert first_request_rows
    assert all(e.engaged_at < observed for r in first_request_rows for e in r.history)
