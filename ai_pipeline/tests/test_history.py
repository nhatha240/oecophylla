from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from ai_pipeline.build_dataset import build_history_snapshot
from ai_pipeline.config import DatasetConfig
from ai_pipeline.schemas import (
    ArticleFeatureRecord,
    BehaviorEvent,
    HistorySnapshot,
)

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
POST_A = UUID("00000000-0000-0000-0000-00000000000a")
POST_B = UUID("00000000-0000-0000-0000-00000000000b")
POST_C = UUID("00000000-0000-0000-0000-00000000000c")
POST_D = UUID("00000000-0000-0000-0000-00000000000d")
POST_E = UUID("00000000-0000-0000-0000-00000000000e")
REFERENCE_AT = datetime(2026, 9, 4, 8, 0, tzinfo=timezone.utc)


def _config(**overrides) -> DatasetConfig:
    values = {
        "start": datetime(2026, 9, 1, tzinfo=timezone.utc),
        "end": datetime(2026, 9, 5, tzinfo=timezone.utc),
        "extraction_time": REFERENCE_AT,
        "label_window_hours": 24,
        "qualified_read_ms": 10_000,
        "recommendation_label_version": "v2",
        "identity_mode": "hash",
        "hash_salt": "history-test-salt",
        "history_recent_limit": 2,
        "history_long_term_limit": 1,
    }
    values.update(overrides)
    return DatasetConfig(**values)


def _event(
    event_id: int,
    post_id: UUID,
    event_type: str,
    occurred_at: datetime,
    *,
    ingested_at: datetime | None = None,
    event_version: str = "v2",
) -> BehaviorEvent:
    return BehaviorEvent(
        id=UUID(int=event_id),
        impression_id=None,
        user_id=USER_ID,
        post_id=post_id,
        event_type=event_type,
        dwell_ms=None,
        occurred_at=occurred_at,
        ingested_at=ingested_at or occurred_at,
        event_version=event_version,
        metadata={"event_version": event_version},
    )


def _feature(
    feature_id: int,
    post_id: UUID,
    *,
    source_updated_at: datetime,
    computed_at: datetime,
    content_hash: str,
) -> ArticleFeatureRecord:
    embedding = [0.0] * 384
    embedding[0] = 1.0
    return ArticleFeatureRecord(
        id=UUID(int=feature_id),
        post_id=post_id,
        encoder_version=(
            "intfloat/multilingual-e5-small@"
            "614241f622f53c4eeff9890bdc4f31cfecc418b3"
        ),
        content_hash=content_hash,
        embedding=embedding,
        source_updated_at=source_updated_at,
        computed_at=computed_at,
    )


def test_history_snapshot_filters_future_simultaneous_delayed_and_missing_rows():
    config = _config()
    events = [
        _event(1, POST_A, "click", REFERENCE_AT - timedelta(hours=3)),
        _event(2, POST_B, "click", REFERENCE_AT),
        _event(3, POST_C, "click", REFERENCE_AT + timedelta(seconds=1)),
        _event(
            4,
            POST_D,
            "click",
            REFERENCE_AT - timedelta(hours=2),
            ingested_at=REFERENCE_AT + timedelta(seconds=1),
        ),
        _event(5, POST_E, "qualified_read", REFERENCE_AT - timedelta(hours=1)),
    ]
    features = [
        _feature(
            11,
            POST_A,
            source_updated_at=REFERENCE_AT - timedelta(days=2),
            computed_at=REFERENCE_AT - timedelta(days=2),
            content_hash="a" * 64,
        ),
        _feature(
            12,
            POST_D,
            source_updated_at=REFERENCE_AT - timedelta(days=1),
            computed_at=REFERENCE_AT - timedelta(days=1),
            content_hash="d" * 64,
        ),
    ]

    snapshot = build_history_snapshot(USER_ID, REFERENCE_AT, events, features, config)

    assert isinstance(snapshot, HistorySnapshot)
    assert [entry.post_id for entry in snapshot.entries] == [POST_A]
    assert snapshot.entries[0].engaged_at == REFERENCE_AT - timedelta(hours=3)


def test_history_snapshot_uses_the_latest_feature_revision_available_at_click_time():
    click_at = REFERENCE_AT - timedelta(hours=4)
    config = _config()
    events = [_event(10, POST_A, "click", click_at)]
    features = [
        _feature(
            21,
            POST_A,
            source_updated_at=REFERENCE_AT - timedelta(days=2),
            computed_at=REFERENCE_AT - timedelta(days=2),
            content_hash="1" * 64,
        ),
        _feature(
            22,
            POST_A,
            source_updated_at=click_at + timedelta(minutes=1),
            computed_at=click_at + timedelta(minutes=1),
            content_hash="2" * 64,
        ),
    ]

    snapshot = build_history_snapshot(USER_ID, REFERENCE_AT, events, features, config)

    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].content_hash == "1" * 64


def test_history_snapshot_respects_recent_and_long_term_limits():
    config = _config(history_recent_limit=2, history_long_term_limit=1)
    events = [
        _event(30 + index, UUID(int=100 + index), "click", REFERENCE_AT - timedelta(hours=index))
        for index in range(5, 0, -1)
    ]
    features = [
        _feature(
            50 + index,
            UUID(int=100 + index),
            source_updated_at=REFERENCE_AT - timedelta(days=3),
            computed_at=REFERENCE_AT - timedelta(days=3),
            content_hash=f"{index:x}" * 64,
        )
        for index in range(1, 6)
    ]

    snapshot = build_history_snapshot(USER_ID, REFERENCE_AT, events, features, config)

    assert [entry.post_id for entry in snapshot.entries] == [
        UUID(int=103),
        UUID(int=102),
        UUID(int=101),
    ]


def test_history_snapshot_exports_hashed_post_groups_without_raw_post_ids():
    config = _config()
    event = _event(90, POST_A, "click", REFERENCE_AT - timedelta(hours=2))
    feature = _feature(
        91,
        POST_A,
        source_updated_at=REFERENCE_AT - timedelta(days=2),
        computed_at=REFERENCE_AT - timedelta(days=2),
        content_hash="9" * 64,
    )

    snapshot = build_history_snapshot(USER_ID, REFERENCE_AT, [event], [feature], config)
    exported = snapshot.to_audit_record(identity_mode=config.identity_mode, hash_salt=config.hash_salt)

    assert exported["entries"][0]["post_group"] is not None
    assert "post_id" not in exported["entries"][0]


def test_history_snapshot_can_be_empty_for_users_without_eligible_clicks():
    snapshot = build_history_snapshot(
        USER_ID,
        REFERENCE_AT,
        [_event(200, POST_A, "qualified_read", REFERENCE_AT - timedelta(hours=1))],
        [],
        _config(),
    )

    assert snapshot.entries == ()


def test_history_snapshot_is_empty_when_both_history_limits_are_zero():
    event = _event(201, POST_A, "click", REFERENCE_AT - timedelta(hours=1))
    feature = _feature(
        202,
        POST_A,
        source_updated_at=REFERENCE_AT - timedelta(days=2),
        computed_at=REFERENCE_AT - timedelta(days=2),
        content_hash="a" * 64,
    )

    snapshot = build_history_snapshot(
        USER_ID,
        REFERENCE_AT,
        [event],
        [feature],
        _config(history_recent_limit=0, history_long_term_limit=0),
    )

    assert snapshot.entries == ()
