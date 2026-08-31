from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import UUID

import pytest

from app.evaluate import (
    BehaviorRecord,
    ImpressionRecord,
    build_temporal_split,
    evaluate,
    evaluate_records,
)
from app.schemas import EvaluateResponse
from recommendation_label import derive_label

UTC = timezone.utc
USER_ID = UUID("00000000-0000-0000-0000-000000000001")
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000010")
POST_A = UUID("00000000-0000-0000-0000-0000000000a1")
POST_B = UUID("00000000-0000-0000-0000-0000000000b2")
POST_C = UUID("00000000-0000-0000-0000-0000000000c3")
IMP_A = UUID("00000000-0000-0000-0000-0000000001a1")
IMP_B = UUID("00000000-0000-0000-0000-0000000001b2")
IMP_C = UUID("00000000-0000-0000-0000-0000000001c3")
CUTOFF = datetime(2026, 8, 20, tzinfo=UTC)
AS_OF = datetime(2026, 8, 23, tzinfo=UTC)
LABEL_V2_FIXTURE = (
    Path(__file__).parents[2]
    / "tests/fixtures/recommendation_telemetry/label-v2-cases.json"
)


def impression(
    impression_id: UUID,
    post_id: UUID,
    served_at: datetime,
    *,
    position: int,
    feed_source: str = "personalized",
    topics: tuple[str, ...] = ("ai",),
) -> ImpressionRecord:
    return ImpressionRecord(
        id=impression_id,
        request_id=REQUEST_ID,
        user_id=USER_ID,
        post_id=post_id,
        position=position,
        feed_source=feed_source,
        topics=topics,
        served_at=served_at,
    )


def event(
    impression_id: UUID | None,
    post_id: UUID,
    event_type: str,
    occurred_at: datetime,
    *,
    dwell_ms: int | None = None,
    ingested_at: datetime | None = None,
    event_version: str | None = None,
) -> BehaviorRecord:
    return BehaviorRecord(
        impression_id=impression_id,
        user_id=USER_ID,
        post_id=post_id,
        event_type=event_type,
        dwell_ms=dwell_ms,
        occurred_at=occurred_at,
        ingested_at=ingested_at,
        event_version=event_version,
    )


def test_temporal_split_excludes_immature_impressions_and_future_events():
    mature = impression(IMP_A, POST_A, CUTOFF + timedelta(hours=1), position=0)
    immature = impression(IMP_B, POST_B, AS_OF - timedelta(hours=12), position=1)
    before_cutoff = impression(IMP_C, POST_C, CUTOFF - timedelta(minutes=1), position=2)
    training = event(None, POST_C, "like", CUTOFF - timedelta(seconds=1))
    label = event(IMP_A, POST_A, "click", mature.served_at + timedelta(hours=2))
    after_window = event(IMP_A, POST_A, "like", mature.served_at + timedelta(hours=25))
    future = event(IMP_A, POST_A, "save", AS_OF + timedelta(seconds=1))

    split = build_temporal_split(
        [mature, immature, before_cutoff],
        [training, label, after_window, future],
        cutoff_at=CUTOFF,
        label_window_hours=24,
        as_of=AS_OF,
    )

    assert split.training_events == (training,)
    assert split.validation_impressions == (mature,)
    assert split.label_events_by_impression == {IMP_A: (label,)}


def test_observed_ctr_and_fallback_rate_come_from_finalized_impressions():
    first = impression(IMP_A, POST_A, CUTOFF + timedelta(hours=1), position=0)
    fallback = impression(
        IMP_B,
        POST_B,
        CUTOFF + timedelta(hours=2),
        position=1,
        feed_source="fallback",
        topics=("business",),
    )
    click = event(IMP_A, POST_A, "click", first.served_at + timedelta(hours=1))

    result = evaluate_records(
        [first, fallback],
        [click],
        cutoff_at=CUTOFF,
        label_window_hours=24,
        as_of=AS_OF,
        k=2,
        catalog_size=10,
    )

    assert result.status == "ok"
    assert result.ctr_observed == 0.5
    assert result.ctr_simulation is None
    assert result.fallback_rate == 0.5
    assert result.sample_users == 1
    assert result.sample_impressions == 2
    assert result.cutoff_at == CUTOFF
    assert result.label_window_hours == 24


def test_shared_label_v2_fixture_is_the_online_evaluator_label_source():
    fixture = json.loads(LABEL_V2_FIXTURE.read_text())
    for case in fixture["label_cases"]:
        result = derive_label(
            case["events"],
            label_version="v2",
            qualified_read_ms=fixture["qualified_read_ms"],
            label_window_closed=case["label_window_closed"],
            defaults=fixture["event_defaults"],
        )
        assert result.semantic == case["expected"]["semantic"], case["id"]
        assert result.accepted_events == case["expected"]["accepted_events"], case["id"]
        assert result.deduplicated_events == case["expected"]["deduplicated_events"], case["id"]
    for case in fixture["ordering_cases"]:
        result = derive_label(
            case["input_events"],
            label_version="v2",
            qualified_read_ms=fixture["qualified_read_ms"],
            label_window_closed=case["label_window_closed"],
            defaults=fixture["event_defaults"],
        )
        assert list(result.processing_order) == case["expected"]["processing_order"], case["id"]
        assert result.semantic == case["expected"]["semantic"], case["id"]
    for case in fixture["event_retry_cases"]:
        with pytest.raises(ValueError, match="conflicting duplicate event"):
            derive_label(
                [case["first"], case["retry"]],
                label_version="v2",
                qualified_read_ms=fixture["qualified_read_ms"],
                label_window_closed=True,
                defaults=fixture["event_defaults"],
            )


def test_label_resolver_recursively_canonicalizes_duplicate_json_objects():
    first = {
        "event_id": "30000000-0000-4000-8000-000000000090",
        "event_type": "click",
        "occurred_at": "2026-08-30T03:00:00Z",
        "metadata": {"target": "post_detail", "context": {"source": "feed", "position": 1}},
    }
    retry = {
        "metadata": {"context": {"position": 1, "source": "feed"}, "target": "post_detail"},
        "occurred_at": "2026-08-30T03:00:00Z",
        "event_type": "click",
        "event_id": "30000000-0000-4000-8000-000000000090",
    }

    result = derive_label(
        [first, retry],
        label_version="v2",
        qualified_read_ms=10_000,
        label_window_closed=True,
    )

    assert result.accepted_events == 1
    assert result.deduplicated_events == 1


def test_v2_long_dwell_is_relevant_but_below_threshold_dwell_is_not():
    first = impression(IMP_A, POST_A, CUTOFF + timedelta(hours=1), position=0)
    second = impression(IMP_B, POST_B, CUTOFF + timedelta(hours=1), position=1)
    events = [
        event(IMP_A, POST_A, "visible", first.served_at, event_version="v2"),
        event(
            IMP_A,
            POST_A,
            "dwell",
            first.served_at + timedelta(seconds=10),
            dwell_ms=10_000,
            event_version="v2",
        ),
        event(IMP_B, POST_B, "visible", second.served_at, event_version="v2"),
        event(
            IMP_B,
            POST_B,
            "dwell",
            second.served_at + timedelta(seconds=9),
            dwell_ms=9_999,
            event_version="v2",
        ),
    ]

    result = evaluate_records(
        [first, second],
        events,
        cutoff_at=CUTOFF,
        label_window_hours=24,
        as_of=AS_OF,
        k=2,
        catalog_size=10,
        recommendation_label_version="v2",
        qualified_read_ms=10_000,
    )

    assert result.precision_at_k == 0.5


def test_v2_excludes_labels_ingested_after_the_evaluation_cutoff():
    served = impression(IMP_A, POST_A, CUTOFF + timedelta(hours=1), position=0)
    events = [
        event(
            IMP_A,
            POST_A,
            "visible",
            served.served_at,
            ingested_at=served.served_at,
            event_version="v2",
        ),
        event(
            IMP_A,
            POST_A,
            "dwell",
            served.served_at + timedelta(seconds=10),
            dwell_ms=10_000,
            ingested_at=AS_OF + timedelta(seconds=1),
            event_version="v2",
        ),
    ]

    result = evaluate_records(
        [served],
        events,
        cutoff_at=CUTOFF,
        label_window_hours=24,
        as_of=AS_OF,
        k=1,
        catalog_size=10,
        recommendation_label_version="v2",
        qualified_read_ms=10_000,
    )

    assert result.precision_at_k == 0.0


def test_runtime_flags_cannot_reinterpret_an_unversioned_legacy_view():
    viewed = impression(IMP_A, POST_A, CUTOFF + timedelta(hours=1), position=0)
    short_view = event(
        IMP_A,
        POST_A,
        "view",
        viewed.served_at + timedelta(seconds=5),
        dwell_ms=5_000,
    )

    legacy = evaluate_records(
        [viewed],
        [short_view],
        cutoff_at=CUTOFF,
        label_window_hours=24,
        as_of=AS_OF,
        k=1,
        catalog_size=10,
        recommendation_label_version="v1",
        qualified_read_ms=10_000,
    )
    v2 = evaluate_records(
        [viewed],
        [short_view],
        cutoff_at=CUTOFF,
        label_window_hours=24,
        as_of=AS_OF,
        k=1,
        catalog_size=10,
        recommendation_label_version="v2",
        qualified_read_ms=10_000,
    )

    assert legacy.precision_at_k == 1.0
    assert v2.precision_at_k == 1.0


def test_explicit_v2_short_view_is_not_a_qualified_read():
    viewed = impression(IMP_A, POST_A, CUTOFF + timedelta(hours=1), position=0)
    short_view = event(
        IMP_A,
        POST_A,
        "view",
        viewed.served_at + timedelta(seconds=5),
        dwell_ms=5_000,
        event_version="v2",
    )

    result = evaluate_records(
        [viewed],
        [short_view],
        cutoff_at=CUTOFF,
        label_window_hours=24,
        as_of=AS_OF,
        k=1,
        catalog_size=10,
        recommendation_label_version="v2",
        qualified_read_ms=10_000,
    )

    assert result.precision_at_k == 0.0


def test_insufficient_data_does_not_publish_misleading_metrics():
    immature = impression(IMP_A, POST_A, AS_OF - timedelta(hours=1), position=0)

    result = evaluate_records(
        [immature],
        [],
        cutoff_at=CUTOFF,
        label_window_hours=24,
        as_of=AS_OF,
        k=1,
        catalog_size=10,
    )

    assert result.status == "insufficient_data"
    assert result.sample_impressions == 0
    assert result.precision_at_k is None
    assert result.recall_at_k is None
    assert result.ndcg_at_k is None
    assert result.hit_rate is None
    assert result.catalog_coverage is None
    assert result.topic_diversity is None
    assert result.ctr_observed is None
    assert result.fallback_rate is None


def test_evaluate_response_exposes_temporal_sample_metadata():
    response = EvaluateResponse(
        status="insufficient_data",
        sample_users=0,
        sample_impressions=0,
        cutoff_at=CUTOFF,
        label_window_hours=24,
    )

    assert response.model_dump().keys() == {
        "status",
        "precision_at_k",
        "recall_at_k",
        "ndcg_at_k",
        "hit_rate",
        "catalog_coverage",
        "topic_diversity",
        "ctr_observed",
        "fallback_rate",
        "sample_users",
        "sample_impressions",
        "cutoff_at",
        "label_window_hours",
        "ctr_simulation",
        "diversity",
    }


@pytest.mark.asyncio
async def test_database_evaluation_uses_stored_impressions_and_observed_events():
    served_at = CUTOFF + timedelta(hours=1)

    class FakePool:
        async def fetch(self, query: str, *_args):
            if "FROM recommendation_impressions" in query:
                return [
                    {
                        "id": IMP_A,
                        "request_id": REQUEST_ID,
                        "user_id": USER_ID,
                        "post_id": POST_A,
                        "position": 0,
                        "feed_source": "fallback",
                        "topics": ["technology"],
                        "served_at": served_at,
                    }
                ]
            if "FROM behavior_events" in query:
                return [
                    {
                        "impression_id": IMP_A,
                        "user_id": USER_ID,
                        "post_id": POST_A,
                        "event_type": "click",
                        "id": UUID("10000000-0000-0000-0000-000000000001"),
                        "dwell_ms": None,
                        "metadata": {},
                        "occurred_at": served_at + timedelta(hours=1),
                        "ingested_at": served_at + timedelta(hours=1),
                    }
                ]
            raise AssertionError(query)

        async def fetchval(self, query: str):
            assert "count(*)" in query
            return 20

    class FakeDB:
        pool = FakePool()

    result = await evaluate(
        FakeDB(),
        object(),
        USER_ID,
        1,
        cutoff_at=CUTOFF,
        label_window_hours=24,
        as_of=AS_OF,
    )

    assert result.status == "ok"
    assert result.precision_at_k == 1.0
    assert result.ctr_observed == 1.0
    assert result.fallback_rate == 1.0
