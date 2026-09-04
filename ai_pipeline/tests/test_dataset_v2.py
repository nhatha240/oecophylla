from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from ai_pipeline.build_dataset import (
    build_ranking_samples_v2,
    validate_dataset_v2,
    write_dataset_v2_artifact,
)
from ai_pipeline.config import DatasetConfig
from ai_pipeline.schemas import ArticleFeatureRecord, BehaviorEvent, Impression

FIXTURE = Path(__file__).parent / "fixtures" / "local_telemetry_v2.json"
ENCODER = (
    "intfloat/multilingual-e5-small@"
    "614241f622f53c4eeff9890bdc4f31cfecc418b3"
)


def _load_local_fixture():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    user_id = UUID(payload["user_id"])
    impressions = []
    events = []
    features = []
    event_counter = 100
    snapshot = {
        "schema_version": "rank-features-v1",
        "topic_relevance": 0.5,
        "freshness": 0.8,
        "safety_score": 1.0,
        "candidate_source": "personalized",
        "is_followed_author": False,
        "author_affinity": 0.0,
        "heuristic_score": 0.6,
        "ml_score": None,
    }
    for seed in payload["seed_history"]:
        occurred_at = datetime.fromisoformat(seed["clicked_at"].replace("Z", "+00:00"))
        events.append(
            BehaviorEvent(
                id=UUID(seed["event_id"]),
                impression_id=None,
                user_id=user_id,
                post_id=UUID(seed["post_id"]),
                event_type="click",
                dwell_ms=None,
                occurred_at=occurred_at,
                ingested_at=occurred_at,
                event_version="v2",
            )
        )
    for request in payload["requests"]:
        served_at = datetime.fromisoformat(request["served_at"].replace("Z", "+00:00"))
        for candidate in request["candidates"]:
            impression_id = UUID(candidate["impression_id"])
            post_id = UUID(candidate["post_id"])
            impressions.append(
                Impression(
                    id=impression_id,
                    request_id=UUID(request["request_id"]),
                    user_id=user_id,
                    post_id=post_id,
                    position=candidate["position"],
                    feed_source="personalized",
                    model_version="heuristic-v1",
                    feature_snapshot=snapshot,
                    served_at=served_at,
                )
            )
            outcome = candidate["outcome"]
            if outcome == "not_visible":
                continue
            visible_at = served_at + timedelta(seconds=1)
            events.append(
                BehaviorEvent(
                    id=UUID(int=event_counter),
                    impression_id=impression_id,
                    user_id=user_id,
                    post_id=post_id,
                    event_type="visible",
                    dwell_ms=None,
                    occurred_at=visible_at,
                    ingested_at=visible_at,
                    event_version="v2",
                )
            )
            event_counter += 1
            outcome_events = {
                "click": [("click", None)],
                "qualified_read": [("dwell", 10_000)],
                "hide": [("hide", None)],
                "click_then_report": [("click", None), ("report", None)],
                "skip": [],
            }[outcome]
            for offset, (event_type, dwell_ms) in enumerate(outcome_events, start=2):
                occurred_at = served_at + timedelta(seconds=offset)
                events.append(
                    BehaviorEvent(
                        id=UUID(int=event_counter),
                        impression_id=impression_id,
                        user_id=user_id,
                        post_id=post_id,
                        event_type=event_type,
                        dwell_ms=dwell_ms,
                        occurred_at=occurred_at,
                        ingested_at=occurred_at,
                        event_version="v2",
                    )
                )
                event_counter += 1
    for index, article in enumerate(payload["articles"], start=1):
        embedding = [0.0] * 384
        embedding[article["embedding_axis"]] = 1.0
        features.append(
            ArticleFeatureRecord(
                id=UUID(int=1000 + index),
                post_id=UUID(article["post_id"]),
                encoder_version=ENCODER,
                content_hash=f"{index:x}" * 64,
                embedding=tuple(embedding),
                source_updated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                computed_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
            )
        )
    return payload, impressions, events, features


@pytest.fixture
def config() -> DatasetConfig:
    return DatasetConfig(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 4, tzinfo=timezone.utc),
        extraction_time=datetime(2026, 9, 5, 12, tzinfo=timezone.utc),
        label_window_hours=24,
        recommendation_label_version="v2",
        identity_mode="hash",
        hash_salt="dataset-v2-test-salt",
        dataset_schema_version="v2",
        encoder_version=ENCODER,
        encoder_dimension=384,
    )


def test_local_v2_preserves_visibility_labels_history_and_scope(config: DatasetConfig):
    payload, impressions, events, features = _load_local_fixture()

    result = build_ranking_samples_v2(impressions, events, features, config)
    report = validate_dataset_v2(result)

    assert len(result.rows) == 6
    assert result.stats.served_without_visible == 1
    assert report.request_count == 3
    assert report.empty_history_requests == 0
    assert {row.dataset_scope for row in result.rows} == {"served-impression-reranking"}
    assert all(row.served and row.visible for row in result.rows)
    assert all(entry.engaged_at < row.served_at for row in result.rows for entry in row.history)
    assert all(len({row.split for row in result.rows if row.request_group == group}) == 1 for group in {row.request_group for row in result.rows})
    assert any(row.click_label == 0 and row.utility_label == 1 for row in result.rows)
    assert any(row.click_label == 1 and row.utility_label == 0 for row in result.rows)
    exported = json.dumps([row.to_record() for row in result.rows], default=str)
    for raw_id in [payload["user_id"], *payload["retrieved_but_not_served"]]:
        assert raw_id not in exported
    assert all(candidate["post_id"] not in exported for request in payload["requests"] for candidate in request["candidates"])


def test_v2_validator_rejects_missing_embedding_and_future_history(config: DatasetConfig):
    _, impressions, events, features = _load_local_fixture()
    result = build_ranking_samples_v2(impressions, events, features, config)
    first = result.rows[0]

    missing = replace(first, article=replace(first.article, embedding=None))
    with pytest.raises(ValueError, match="missing article representation"):
        validate_dataset_v2(replace(result, rows=(missing, *result.rows[1:])))

    leaked_entry = replace(first.history[0], engaged_at=first.served_at)
    leaked = replace(first, history=(leaked_entry, *first.history[1:]))
    with pytest.raises(ValueError, match="history must be strictly before serving"):
        validate_dataset_v2(replace(result, rows=(leaked, *result.rows[1:])))


def test_v2_validator_rejects_encoder_dimension_and_identity_mismatch(
    config: DatasetConfig,
):
    _, impressions, events, features = _load_local_fixture()
    result = build_ranking_samples_v2(impressions, events, features, config)
    first = result.rows[0]

    wrong_encoder = replace(first, article=replace(first.article, encoder_version=ENCODER[:-1] + "0"))
    with pytest.raises(ValueError, match="encoder version"):
        validate_dataset_v2(replace(result, rows=(wrong_encoder, *result.rows[1:])))

    history_row = next(row for row in result.rows if row.history)
    wrong_history = replace(
        history_row.history[0].article,
        encoder_version=ENCODER[:-1] + "0",
    )
    invalid_history = (
        replace(history_row.history[0], article=wrong_history),
        *history_row.history[1:],
    )
    with pytest.raises(ValueError, match="encoder version"):
        validate_dataset_v2(
            replace(
                result,
                rows=tuple(
                    replace(row, history=invalid_history)
                    if row.request_group == history_row.request_group
                    else row
                    for row in result.rows
                ),
            )
        )

    wrong_dimension = replace(first, article=replace(first.article, embedding=(1.0, 0.0)))
    with pytest.raises(ValueError, match="embedding dimension"):
        validate_dataset_v2(replace(result, rows=(wrong_dimension, *result.rows[1:])))

    zero_vector = replace(first, article=replace(first.article, embedding=(0.0,) * 384))
    with pytest.raises(ValueError, match="L2-normalized"):
        validate_dataset_v2(replace(result, rows=(zero_vector, *result.rows[1:])))

    bad_sample = replace(first, sample_id="not-a-private-hash")
    with pytest.raises(ValueError, match="private hashes"):
        validate_dataset_v2(replace(result, rows=(bad_sample, *result.rows[1:])))


def test_v2_keeps_click_that_precedes_proven_visibility(config: DatasetConfig):
    _, impressions, events, features = _load_local_fixture()
    target = impressions[0]
    events = [
        replace(event, occurred_at=target.served_at + timedelta(milliseconds=500))
        if event.impression_id == target.id and event.event_type == "click"
        else event
        for event in events
    ]

    result = build_ranking_samples_v2(impressions, events, features, config)
    row = next(item for item in result.rows if item.position == target.position and item.served_at == target.served_at)

    assert row.click_label == 1
    assert row.utility_label == 1


@pytest.mark.parametrize("timestamp_field", ["source_updated_at", "computed_at"])
def test_v2_never_uses_candidate_feature_revision_from_after_serving(
    config: DatasetConfig,
    timestamp_field: str,
):
    _, impressions, events, features = _load_local_fixture()
    target = impressions[0]
    features = [
        replace(feature, **{timestamp_field: target.served_at + timedelta(seconds=1)})
        if feature.post_id == target.post_id
        else feature
        for feature in features
    ]

    with pytest.raises(ValueError, match="missing article representation"):
        build_ranking_samples_v2(impressions, events, features, config)


def test_v2_artifact_keeps_and_validates_feature_revision_timestamps(
    config: DatasetConfig,
):
    _, impressions, events, features = _load_local_fixture()
    result = build_ranking_samples_v2(impressions, events, features, config)

    for row in result.rows:
        assert row.article.feature_source_updated_at <= row.served_at
        assert row.article.feature_computed_at <= row.served_at
        for entry in row.history:
            assert entry.article.feature_source_updated_at <= entry.engaged_at
            assert entry.article.feature_computed_at <= entry.engaged_at

    first = result.rows[0]
    future_article = replace(
        first.article,
        feature_computed_at=first.served_at + timedelta(seconds=1),
    )
    with pytest.raises(ValueError, match="feature revision must not be from the future"):
        validate_dataset_v2(
            replace(result, rows=(replace(first, article=future_article), *result.rows[1:]))
        )


def test_v2_validator_rejects_reordered_or_non_contiguous_history(
    config: DatasetConfig,
):
    _, impressions, events, features = _load_local_fixture()
    result = build_ranking_samples_v2(impressions, events, features, config)
    first = next(row for row in result.rows if len(row.history) >= 2)

    duplicate_ordinal = replace(first.history[1], ordinal=first.history[0].ordinal)
    invalid_ordinals = replace(first, history=(first.history[0], duplicate_ordinal))
    with pytest.raises(ValueError, match="history ordinals"):
        validate_dataset_v2(
            replace(
                result,
                rows=tuple(
                    replace(row, history=invalid_ordinals.history)
                    if row.request_group == first.request_group
                    else row
                    for row in result.rows
                ),
            )
        )

    decreasing = replace(
        first.history[1],
        engaged_at=first.history[0].engaged_at - timedelta(seconds=1),
    )
    invalid_times = replace(first, history=(first.history[0], decreasing))
    with pytest.raises(ValueError, match="history timestamps must be ordered"):
        validate_dataset_v2(
            replace(
                result,
                rows=tuple(
                    replace(row, history=invalid_times.history)
                    if row.request_group == first.request_group
                    else row
                    for row in result.rows
                ),
            )
        )


def test_v2_validator_accepts_and_counts_empty_history(config: DatasetConfig):
    _, impressions, events, features = _load_local_fixture()
    result = build_ranking_samples_v2(impressions, events, features, config)
    first_group = result.rows[0].request_group
    rows = tuple(
        replace(row, history=()) if row.request_group == first_group else row
        for row in result.rows
    )

    report = validate_dataset_v2(replace(result, rows=rows))

    assert report.empty_history_requests == 1


def test_v2_artifact_pins_versions_and_contains_no_raw_identity(
    config: DatasetConfig, tmp_path: Path
):
    from pyarrow import parquet

    payload, impressions, events, features = _load_local_fixture()
    result = build_ranking_samples_v2(impressions, events, features, config)

    metadata_path = write_dataset_v2_artifact(
        result,
        config,
        tmp_path / "dataset-v2.parquet",
        code_version="test-sha",
        source_format="oecophylla-telemetry-v2",
    )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    table = parquet.read_table(tmp_path / "dataset-v2.parquet")
    assert metadata["dataset_schema_version"] == "recommendation-dataset-v2"
    assert metadata["dataset_scope"] == "served-impression-reranking"
    assert metadata["feature_schema_version"] == "post-content-features-v1"
    assert metadata["label_definition_version"] == "engagement-label-v2"
    assert metadata["qualified_read_ms"] == 10_000
    assert metadata["encoder_version"] == ENCODER
    assert metadata["encoder_dimension"] == 384
    assert metadata["code_version"] == "test-sha"
    assert metadata["query_window_version"] == "event-time-window-v1"
    assert metadata["class_balance"]["click_label"] == {"0": 4, "1": 2}
    serialized = table.to_pydict()
    assert payload["user_id"] not in json.dumps(serialized, default=str)

    other_encoder = replace(config, encoder_version=ENCODER[:-40] + "0" * 40)
    with pytest.raises(ValueError, match="encoder version was not verified"):
        write_dataset_v2_artifact(
            result,
            other_encoder,
            tmp_path / "mismatched.parquet",
            code_version="test-sha",
            source_format="oecophylla-telemetry-v2",
        )


def test_v2_config_requires_explicit_v2_label_and_pinned_encoder(config: DatasetConfig):
    with pytest.raises(ValueError, match="dataset v2 requires label v2"):
        replace(config, recommendation_label_version="v1")
    with pytest.raises(ValueError, match="encoder_version"):
        replace(config, encoder_version="mutable/latest")
    with pytest.raises(ValueError, match="encoder_dimension"):
        replace(config, encoder_dimension=0)
    with pytest.raises(ValueError, match="identity_mode=hash"):
        replace(config, identity_mode="drop", hash_salt=None)
    with pytest.raises(ValueError, match="post-content-features-v1"):
        replace(config, feature_schema_version="post-content-features-v2")
    with pytest.raises(ValueError, match="event-time-window-v1"):
        replace(config, query_window_version="processing-time-window-v1")
