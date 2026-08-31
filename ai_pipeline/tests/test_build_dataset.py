from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from ai_pipeline.build_dataset import build_samples, write_artifact
from ai_pipeline.config import DatasetConfig
from ai_pipeline.schemas import BehaviorEvent, Impression
from recommendation_label import derive_label

FIXTURE = Path(__file__).parent / "fixtures" / "telemetry_v1.json"
LABEL_V2_FIXTURE = (
    Path(__file__).parents[2]
    / "tests/fixtures/recommendation_telemetry/label-v2-cases.json"
)


def load_fixture() -> tuple[list[Impression], list[BehaviorEvent]]:
    payload = json.loads(FIXTURE.read_text())
    return (
        [Impression.from_mapping(row) for row in payload["impressions"]],
        [BehaviorEvent.from_mapping(row) for row in payload["events"]],
    )


def grouped_telemetry(
    candidate_counts: tuple[int, ...] = (1, 1, 3, 1),
) -> tuple[list[Impression], list[BehaviorEvent]]:
    impressions, events = load_fixture()
    snapshot = impressions[0].feature_snapshot
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    grouped_impressions: list[Impression] = []
    grouped_events: list[BehaviorEvent] = []
    sequence = 1
    for group_index, candidate_count in enumerate(candidate_counts, start=1):
        request_id = UUID(int=10_000 + group_index)
        served_at = datetime(2026, 8, group_index, tzinfo=timezone.utc)
        for position in range(candidate_count):
            impression_id = UUID(int=20_000 + sequence)
            post_id = UUID(int=30_000 + sequence)
            grouped_impressions.append(
                Impression(
                    id=impression_id,
                    request_id=request_id,
                    user_id=user_id,
                    post_id=post_id,
                    position=position,
                    feed_source="personalized",
                    model_version="heuristic-v1",
                    feature_snapshot=snapshot,
                    served_at=served_at,
                )
            )
            grouped_events.append(
                BehaviorEvent(
                    id=UUID(int=40_000 + sequence),
                    impression_id=impression_id,
                    user_id=user_id,
                    post_id=post_id,
                    event_type="visible",
                    dwell_ms=None,
                    occurred_at=served_at + timedelta(seconds=1),
                )
            )
            sequence += 1
    return grouped_impressions, grouped_events


@pytest.fixture
def config() -> DatasetConfig:
    return DatasetConfig(
        start=datetime(2026, 8, 1, tzinfo=timezone.utc),
        end=datetime(2026, 8, 10, tzinfo=timezone.utc),
        extraction_time=datetime(2026, 8, 12, tzinfo=timezone.utc),
        label_window_hours=24,
        qualified_read_ms=10_000,
        identity_mode="hash",
        hash_salt="fixture-salt",
    )


def test_visible_exposure_and_label_v1_boundaries(config: DatasetConfig):
    impressions, events = load_fixture()

    result = build_samples(impressions, events, config)
    by_post = {row.audit_post_id: row for row in result.rows}

    assert "00000000-0000-0000-0000-000000001002" not in by_post
    assert by_post["00000000-0000-0000-0000-000000001001"].label_name == "negative"
    assert by_post["00000000-0000-0000-0000-000000001004"].label_name == "negative"
    assert (
        by_post["00000000-0000-0000-0000-000000001005"].label_name == "strong_positive"
    )
    assert (
        by_post["00000000-0000-0000-0000-000000001006"].label_name == "strong_negative"
    )
    assert by_post["00000000-0000-0000-0000-000000001007"].label_name == "positive"
    assert by_post["00000000-0000-0000-0000-000000001008"].label_name == "positive"


def test_shared_label_v2_fixture_is_the_dataset_label_source():
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
        assert result.training_target == case["expected"]["training_target"], case["id"]


def test_label_v2_uses_binary_targets_and_versioned_metadata(
    config: DatasetConfig, tmp_path: Path
):
    impressions, events = load_fixture()
    v2_config = replace(config, recommendation_label_version="v2")
    result = build_samples(impressions, events, v2_config)
    assert {row.label for row in result.rows} <= {0, 1}

    metadata_path = write_artifact(
        result, v2_config, tmp_path / "v2.parquet", code_version="test"
    )
    metadata = json.loads(metadata_path.read_text())
    assert metadata["label_definition_version"] == "engagement-label-v2"
    assert metadata["qualified_read_ms"] == 10_000


def test_immature_and_unsupported_schema_rows_are_excluded(config: DatasetConfig):
    impressions, events = load_fixture()

    result = build_samples(impressions, events, config)

    assert result.stats.immature_impressions == 1
    assert result.stats.unsupported_feature_schema == 1
    assert result.stats.served_without_visible == 1
    assert len(result.rows) == 6


def test_duplicate_telemetry_does_not_multiply_samples(config: DatasetConfig):
    impressions, events = load_fixture()

    first = build_samples(impressions, events, config)
    second = build_samples(impressions, events, config)

    assert len({row.sample_id for row in first.rows}) == len(first.rows)
    assert first == second


def test_only_serving_time_feature_allowlist_is_exported(config: DatasetConfig):
    impressions, events = load_fixture()
    result = build_samples(impressions, events, config)
    row = next(
        row
        for row in result.rows
        if row.audit_post_id == "00000000-0000-0000-0000-000000001005"
    )

    exported = row.to_record()
    assert exported["topic_relevance"] == 0.9
    assert "current_view_count" not in exported
    assert set(exported).isdisjoint({"user_id", "post_id", "impression_id"})
    assert len(exported["request_group"]) == 64
    assert exported["request_group"] != "00000000-0000-0000-0000-0000000010e5"
    assert row.user_group != row.audit_user_id
    assert row.post_group != row.audit_post_id


def test_drop_identity_mode_exports_no_stable_identity(config: DatasetConfig):
    impressions, events = load_fixture()

    result = build_samples(
        impressions,
        events,
        replace(config, identity_mode="drop", hash_salt=None),
    )

    assert all(row.user_group is None for row in result.rows)
    assert all(row.post_group is None for row in result.rows)
    assert [row.sample_id for row in result.rows] == [
        f"sample-{index:09d}" for index in range(1, 7)
    ]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"start": datetime(2026, 8, 1)}, "start must include a timezone"),
        (
            {"end": datetime(2026, 8, 1, tzinfo=timezone.utc)},
            "start must be before end",
        ),
        ({"label_window_hours": 0}, "label_window_hours must be positive"),
        ({"qualified_read_ms": 0}, "qualified_read_ms must be positive"),
        (
            {"recommendation_label_version": "v3"},
            "recommendation_label_version must be v1 or v2",
        ),
        ({"hash_salt": None}, "hash_salt is required"),
        ({"identity_mode": "invalid"}, "identity_mode must be hash or drop"),
        ({"train_fraction": 0}, "train_fraction must be between zero and one"),
        (
            {"validation_fraction": 0},
            "validation_fraction must be between zero and one",
        ),
        (
            {"train_fraction": 0.9, "validation_fraction": 0.1},
            "fractions must leave a test holdout",
        ),
    ],
)
def test_invalid_dataset_config_is_rejected(
    config: DatasetConfig, changes: dict[str, object], message: str
):
    with pytest.raises(ValueError, match=message):
        replace(config, **changes)


def test_time_split_is_disjoint_and_latest_rows_are_test_holdout(
    config: DatasetConfig,
):
    impressions, events = load_fixture()
    rows = build_samples(impressions, events, config).rows
    split_ids = {
        split: {row.sample_id for row in rows if row.split == split}
        for split in ("train", "validation", "test")
    }

    assert all(split_ids.values())
    assert split_ids["train"].isdisjoint(split_ids["validation"])
    assert split_ids["train"].isdisjoint(split_ids["test"])
    assert split_ids["validation"].isdisjoint(split_ids["test"])
    train_times = [row.visible_at for row in rows if row.split == "train"]
    validation_times = [row.visible_at for row in rows if row.split == "validation"]
    test_times = [row.visible_at for row in rows if row.split == "test"]
    assert max(train_times) <= min(validation_times) <= min(test_times)


def test_grouped_time_split_keeps_candidates_atomic_at_percentage_boundaries(
    config: DatasetConfig,
):
    impressions, events = grouped_telemetry()

    rows = build_samples(impressions, events, config).rows

    splits_by_request: dict[str, set[str]] = {}
    for row in rows:
        assert row.request_group is not None
        splits_by_request.setdefault(row.request_group, set()).add(row.split)
    assert all(len(splits) == 1 for splits in splits_by_request.values())
    assert sorted(
        sum(row.request_group == request for row in rows)
        for request in splits_by_request
    ) == [1, 1, 1, 3]


def test_request_group_hashes_the_canonical_user_and_request_identity(
    config: DatasetConfig,
):
    impressions, events = grouped_telemetry((2,))
    impression = impressions[0]

    rows = build_samples(impressions, events, config).rows

    expected = hmac.new(
        str(config.hash_salt).encode(),
        f"{impression.user_id}:{impression.request_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    assert {row.request_group for row in rows} == {expected}


def test_same_request_id_for_different_users_has_distinct_canonical_groups(
    config: DatasetConfig,
):
    impressions, events = grouped_telemetry((1, 1))
    second_user = UUID("00000000-0000-0000-0000-000000000002")
    impressions[1] = replace(
        impressions[1],
        request_id=impressions[0].request_id,
        user_id=second_user,
    )
    events[1] = replace(events[1], user_id=second_user)

    rows = build_samples(impressions, events, config).rows

    assert len({row.request_group for row in rows}) == 2


def test_drop_identity_mode_still_splits_requests_atomically(
    config: DatasetConfig,
):
    impressions, events = grouped_telemetry()

    rows = build_samples(
        impressions,
        events,
        replace(config, identity_mode="drop", hash_salt=None),
    ).rows

    assert all(row.request_group is None for row in rows)
    split_by_request: dict[UUID, set[str]] = {}
    request_by_post = {
        str(impression.post_id): impression.request_id for impression in impressions
    }
    for row in rows:
        split_by_request.setdefault(request_by_post[row.audit_post_id], set()).add(
            row.split
        )
    assert all(len(splits) == 1 for splits in split_by_request.values())


def test_requests_tied_at_a_boundary_stay_in_the_same_later_split(
    config: DatasetConfig,
):
    impressions, events = grouped_telemetry((1, 1, 1, 1))
    tied_time = impressions[1].served_at
    impressions[2] = replace(impressions[2], served_at=tied_time)
    events[2] = replace(events[2], occurred_at=tied_time + timedelta(seconds=1))

    rows = build_samples(impressions, events, config).rows

    request_by_post = {
        str(impression.post_id): impression.request_id for impression in impressions
    }
    split_by_request = {
        request_by_post[row.audit_post_id]: row.split for row in rows
    }
    assert split_by_request[impressions[1].request_id] == "validation"
    assert split_by_request[impressions[2].request_id] == "validation"


@pytest.mark.parametrize(
    "changes",
    [
        {"feed_source": "fallback"},
        {"model_version": "other-v1"},
        {"served_at": datetime(2026, 8, 2, tzinfo=timezone.utc)},
        {"position": 0},
        {"post_id": UUID(int=30_001)},
    ],
)
def test_conflicting_request_envelope_is_rejected(
    config: DatasetConfig, changes: dict[str, object]
):
    impressions, events = grouped_telemetry((2,))
    impressions[1] = replace(impressions[1], **changes)

    with pytest.raises(ValueError, match="conflicting canonical request identity"):
        build_samples(impressions, events, config)


def test_parquet_and_metadata_are_auditable_and_contain_no_raw_ids(
    config: DatasetConfig, tmp_path: Path
):
    import pyarrow.parquet as parquet

    impressions, events = load_fixture()
    result = build_samples(impressions, events, config)
    output = tmp_path / "dataset.parquet"

    metadata_path = write_artifact(result, config, output, code_version="test-sha")

    table = parquet.read_table(output)
    metadata = json.loads(metadata_path.read_text())
    assert table.num_rows == 6
    assert "user_id" not in table.column_names
    assert "post_id" not in table.column_names
    assert metadata["row_count"] == 6
    assert metadata["query_window"] == {
        "start": "2026-08-01T00:00:00+00:00",
        "end": "2026-08-10T00:00:00+00:00",
        "extraction_time": "2026-08-12T00:00:00+00:00",
    }
    assert metadata["class_balance"] == {
        "negative": 2,
        "positive": 2,
        "strong_negative": 1,
        "strong_positive": 1,
    }
    assert metadata["feature_schema_versions"] == ["rank-features-v1"]
    assert metadata["code_version"] == "test-sha"


def test_metadata_records_group_boundary_policy_and_candidate_distributions(
    config: DatasetConfig, tmp_path: Path
):
    impressions, events = grouped_telemetry()
    result = build_samples(impressions, events, config)

    metadata_path = write_artifact(
        result, config, tmp_path / "grouped.parquet", code_version="test-sha"
    )
    metadata = json.loads(metadata_path.read_text())

    assert metadata["split_policy"] == {
        "atomic_unit": "canonical_request",
        "boundary": (
            "chronological_request_count_with_timestamp_ties_assigned_to_later_split"
        ),
        "internal_grouping": "canonical_user_and_request_identity_in_memory_only",
        "legacy_compatibility": "request_group_rekeyed_from_sha256_request_id",
        "request_identity": "HMAC-SHA256(hash_salt,user_id:request_id)",
    }
    split_stats = metadata["split_request_stats"]
    assert sum(stats["request_count"] for stats in split_stats.values()) == 4
    assert sum(
        int(candidate_count) * request_count
        for stats in split_stats.values()
        for candidate_count, request_count in stats[
            "candidate_count_distribution"
        ].items()
    ) == 6
    assert any(
        stats["candidate_count_distribution"].get("3") == 1
        for stats in split_stats.values()
    )


def test_drop_mode_metadata_audits_internal_grouping_without_exporting_identity(
    config: DatasetConfig, tmp_path: Path
):
    impressions, events = grouped_telemetry()
    drop_config = replace(config, identity_mode="drop", hash_salt=None)
    result = build_samples(impressions, events, drop_config)

    metadata_path = write_artifact(
        result, drop_config, tmp_path / "drop.parquet", code_version="test-sha"
    )
    metadata = json.loads(metadata_path.read_text())

    assert metadata["split_policy"]["request_identity"] == "not_exported"
    assert metadata["split_policy"]["internal_grouping"] == (
        "canonical_user_and_request_identity_in_memory_only"
    )
    assert all(row.to_record()["request_group"] is None for row in result.rows)
