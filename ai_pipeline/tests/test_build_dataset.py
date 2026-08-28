from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_pipeline.build_dataset import build_samples, write_artifact
from ai_pipeline.config import DatasetConfig
from ai_pipeline.schemas import BehaviorEvent, Impression

FIXTURE = Path(__file__).parent / "fixtures" / "telemetry_v1.json"


def load_fixture() -> tuple[list[Impression], list[BehaviorEvent]]:
    payload = json.loads(FIXTURE.read_text())
    return (
        [Impression.from_mapping(row) for row in payload["impressions"]],
        [BehaviorEvent.from_mapping(row) for row in payload["events"]],
    )


@pytest.fixture
def config() -> DatasetConfig:
    return DatasetConfig(
        start=datetime(2026, 8, 1, tzinfo=timezone.utc),
        end=datetime(2026, 8, 10, tzinfo=timezone.utc),
        extraction_time=datetime(2026, 8, 12, tzinfo=timezone.utc),
        label_window_hours=24,
        positive_dwell_ms=10_000,
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
        ({"positive_dwell_ms": 0}, "positive_dwell_ms must be positive"),
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
