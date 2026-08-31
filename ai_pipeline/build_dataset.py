from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import subprocess
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TypeVar
from uuid import UUID

from recommendation_label import CONTRACT_VERSION, derive_label, event_label_version

from .config import DatasetConfig
from .schemas import (
    BehaviorEvent,
    BuildResult,
    BuildStats,
    DatasetRow,
    Impression,
    LabelName,
    SplitName,
    parse_datetime,
)

DATASET_SCHEMA_VERSION = "recommendation-dataset-v1"
FEATURE_SCHEMA_VERSION = "rank-features-v1"
LABEL_DEFINITION_VERSION_V1 = "engagement-label-v1"
REQUIRED_FEATURES = frozenset(
    {
        "schema_version",
        "topic_relevance",
        "freshness",
        "safety_score",
        "candidate_source",
        "is_followed_author",
        "author_affinity",
        "heuristic_score",
        "ml_score",
    }
)
LABEL_VALUES: dict[LabelName, int] = {
    "strong_negative": -2,
    "negative": -1,
    "positive": 1,
    "strong_positive": 2,
}


T = TypeVar("T", Impression, BehaviorEvent)


def _deduplicate(records: Iterable[T]) -> dict[UUID, T]:
    unique: dict[UUID, T] = {}
    for record in records:
        existing = unique.get(record.id)
        if existing is not None and existing != record:
            raise ValueError(f"conflicting duplicate record: {record.id}")
        unique.setdefault(record.id, record)
    return unique


def _hash_identity(value: UUID, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()


def _canonical_request_identity(impression: Impression) -> str:
    return f"{impression.user_id}:{impression.request_id}"


def _hmac_request_identity(impression: Impression, secret: str) -> str:
    return hmac.new(
        secret.encode(),
        _canonical_request_identity(impression).encode(),
        hashlib.sha256,
    ).hexdigest()


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _validate_snapshot(snapshot: Mapping[str, Any]) -> bool:
    return (
        snapshot.get("schema_version") == FEATURE_SCHEMA_VERSION
        and REQUIRED_FEATURES.issubset(snapshot)
        and isinstance(snapshot.get("candidate_source"), str)
        and bool(str(snapshot.get("candidate_source", "")).strip())
    )


def _split_rows(
    rows: Sequence[DatasetRow], config: DatasetConfig
) -> tuple[DatasetRow, ...]:
    grouped: dict[str, list[DatasetRow]] = defaultdict(list)
    for row in rows:
        grouped[row.audit_request_identity].append(row)
    ordered_groups = sorted(
        grouped.values(),
        key=lambda candidates: (
            min(candidate.served_at for candidate in candidates),
            candidates[0].audit_request_identity,
        ),
    )
    group_count = len(ordered_groups)
    if group_count == 0:
        return ()
    if group_count == 1:
        return tuple(replace(row, split="train") for row in ordered_groups[0])

    test_count = max(
        1,
        round(
            group_count
            * (1 - config.train_fraction - config.validation_fraction)
        ),
    )
    validation_count = (
        max(1, round(group_count * config.validation_fraction))
        if group_count >= 3
        else 0
    )
    if test_count + validation_count >= group_count:
        validation_count = max(0, group_count - test_count - 1)
    train_count = group_count - validation_count - test_count
    train_end = train_count
    validation_end = train_end + validation_count

    group_times = [
        min(candidate.served_at for candidate in candidates)
        for candidates in ordered_groups
    ]
    while 0 < train_end < group_count and group_times[train_end - 1] == group_times[
        train_end
    ]:
        train_end -= 1
    while (
        train_end < validation_end < group_count
        and group_times[validation_end - 1] == group_times[validation_end]
    ):
        validation_end -= 1
    validation_end = max(train_end, validation_end)

    split_rows: list[DatasetRow] = []
    for index, candidates in enumerate(ordered_groups):
        split: SplitName
        if index < train_end:
            split = "train"
        elif index < validation_end:
            split = "validation"
        else:
            split = "test"
        split_rows.extend(replace(row, split=split) for row in candidates)

    result = tuple(
        sorted(split_rows, key=lambda row: (row.visible_at, row.sample_id))
    )
    _assert_atomic_request_splits(rows, result)
    return result


def _assert_atomic_request_splits(
    source_rows: Sequence[DatasetRow], split_rows: Sequence[DatasetRow]
) -> None:
    source_samples = Counter(row.sample_id for row in source_rows)
    split_samples = Counter(row.sample_id for row in split_rows)
    if source_samples != split_samples:
        raise AssertionError("grouped split did not retain every eligible candidate")
    splits_by_request: dict[str, set[SplitName]] = defaultdict(set)
    for row in split_rows:
        splits_by_request[row.audit_request_identity].add(row.split)
    if any(len(splits) != 1 for splits in splits_by_request.values()):
        raise AssertionError("canonical request crossed dataset splits")


def _validate_request_envelopes(impressions: Iterable[Impression]) -> None:
    envelopes: dict[str, tuple[datetime, str, str]] = {}
    positions: dict[str, set[int]] = defaultdict(set)
    posts: dict[str, set[UUID]] = defaultdict(set)
    for impression in impressions:
        identity = _canonical_request_identity(impression)
        envelope = (
            impression.served_at,
            impression.feed_source,
            impression.model_version,
        )
        existing = envelopes.setdefault(identity, envelope)
        if existing != envelope:
            raise ValueError("conflicting canonical request identity")
        if (
            impression.position in positions[identity]
            or impression.post_id in posts[identity]
        ):
            raise ValueError("conflicting canonical request identity")
        positions[identity].add(impression.position)
        posts[identity].add(impression.post_id)


def build_samples(
    impressions: Iterable[Impression],
    events: Iterable[BehaviorEvent],
    config: DatasetConfig,
) -> BuildResult:
    impression_list = list(impressions)
    event_list = list(events)
    unique_impressions = _deduplicate(impression_list)
    unique_events = _deduplicate(event_list)
    window_impressions = [
        impression
        for impression in unique_impressions.values()
        if config.start <= impression.served_at < config.end
    ]
    _validate_request_envelopes(window_impressions)
    events_by_impression: dict[UUID, list[BehaviorEvent]] = defaultdict(list)
    for event in unique_events.values():
        if (
            event.impression_id is not None
            and (
                event.ingested_at is None
                or event.ingested_at <= config.extraction_time
            )
        ):
            events_by_impression[event.impression_id].append(event)

    served_without_visible = 0
    immature_impressions = 0
    unsupported_feature_schema = 0
    rows: list[DatasetRow] = []
    observed_label_versions: set[str] = set()
    window = timedelta(hours=config.label_window_hours)
    salt = config.hash_salt or ""

    for impression in sorted(
        unique_impressions.values(), key=lambda item: (item.served_at, item.id)
    ):
        if not config.start <= impression.served_at < config.end:
            continue
        linked_events = [
            event
            for event in events_by_impression.get(impression.id, ())
            if event.user_id == impression.user_id
            and event.post_id == impression.post_id
        ]
        visible_events = [
            event
            for event in linked_events
            if event.event_type == "visible"
            and event.occurred_at >= impression.served_at
        ]
        if not visible_events:
            served_without_visible += 1
            continue
        visible_at = min(event.occurred_at for event in visible_events)
        label_window_end = visible_at + window
        if label_window_end > config.extraction_time:
            immature_impressions += 1
            continue
        if not _validate_snapshot(impression.feature_snapshot):
            unsupported_feature_schema += 1
            continue

        label_events = [
            event
            for event in linked_events
            if visible_at <= event.occurred_at <= label_window_end
        ]
        persisted_versions = {event_label_version(event) for event in label_events}
        if len(persisted_versions) != 1:
            raise ValueError("mixed persisted label versions within one impression")
        persisted_label_version = persisted_versions.pop()
        observed_label_versions.add(persisted_label_version)
        if len(observed_label_versions) > 1:
            raise ValueError("mixed persisted label versions in one training run")
        label_result = derive_label(
            label_events,
            label_version=persisted_label_version,
            qualified_read_ms=config.qualified_read_ms,
            label_window_closed=True,
        )
        label_name: LabelName = label_result.semantic
        snapshot = impression.feature_snapshot
        if config.identity_mode == "hash":
            sample_id = _hash_identity(impression.id, salt)
            user_group = _hash_identity(impression.user_id, salt)
            post_group = _hash_identity(impression.post_id, salt)
            request_group = _hmac_request_identity(impression, salt)
        else:
            sample_id = f"sample-{len(rows) + 1:09d}"
            user_group = None
            post_group = None
            request_group = None

        rows.append(
            DatasetRow(
                sample_id=sample_id,
                user_group=user_group,
                post_group=post_group,
                request_group=request_group,
                split="train",
                label=(
                    int(label_result.training_target)
                    if persisted_label_version == "v2"
                    else LABEL_VALUES[label_name]
                ),
                label_name=label_name,
                served_at=impression.served_at,
                visible_at=visible_at,
                position=impression.position,
                feed_source=impression.feed_source,
                model_version=impression.model_version,
                feature_schema_version=FEATURE_SCHEMA_VERSION,
                topic_relevance=_optional_float(snapshot["topic_relevance"]),
                freshness=_optional_float(snapshot["freshness"]),
                safety_score=_optional_float(snapshot["safety_score"]),
                candidate_source=str(snapshot["candidate_source"]),
                is_followed_author=snapshot["is_followed_author"],
                author_affinity=_optional_float(snapshot["author_affinity"]),
                heuristic_score=_optional_float(snapshot["heuristic_score"]),
                ml_score=_optional_float(snapshot["ml_score"]),
                audit_user_id=str(impression.user_id),
                audit_post_id=str(impression.post_id),
                audit_request_identity=_canonical_request_identity(impression),
            )
        )

    if observed_label_versions and observed_label_versions != {
        config.recommendation_label_version
    }:
        persisted = next(iter(observed_label_versions))
        raise ValueError(
            f"persisted label version {persisted} does not match requested "
            f"dataset label version {config.recommendation_label_version}"
        )

    return BuildResult(
        rows=_split_rows(rows, config),
        stats=BuildStats(
            impressions_read=len(impression_list),
            events_read=len(event_list),
            served_without_visible=served_without_visible,
            immature_impressions=immature_impressions,
            unsupported_feature_schema=unsupported_feature_schema,
        ),
    )


def write_artifact(
    result: BuildResult,
    config: DatasetConfig,
    output: Path,
    *,
    code_version: str | None,
) -> Path:
    import pyarrow as arrow
    import pyarrow.parquet as parquet

    output.parent.mkdir(parents=True, exist_ok=True)
    records = [row.to_record() for row in result.rows]
    table = arrow.Table.from_pylist(records)
    parquet.write_table(table, output, compression="zstd")

    split_request_stats: dict[str, dict[str, Any]] = {}
    for split in ("train", "validation", "test"):
        candidates_per_request = Counter(
            row.audit_request_identity for row in result.rows if row.split == split
        )
        split_request_stats[split] = {
            "request_count": len(candidates_per_request),
            "candidate_count_distribution": dict(
                sorted(
                    Counter(candidates_per_request.values()).items(),
                    key=lambda pair: pair[0],
                )
            ),
        }

    metadata = {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "label_definition_version": (
            CONTRACT_VERSION
            if config.recommendation_label_version == "v2"
            else LABEL_DEFINITION_VERSION_V1
        ),
        "feature_schema_versions": sorted(
            {row.feature_schema_version for row in result.rows}
        ),
        "query_window": {
            "start": config.start.isoformat(),
            "end": config.end.isoformat(),
            "extraction_time": config.extraction_time.isoformat(),
        },
        "label_window_hours": config.label_window_hours,
        "qualified_read_ms": config.qualified_read_ms,
        **(
            {"positive_dwell_ms": config.qualified_read_ms}
            if config.recommendation_label_version == "v1"
            else {}
        ),
        "identity_mode": config.identity_mode,
        "row_count": len(result.rows),
        "split_counts": dict(sorted(Counter(row.split for row in result.rows).items())),
        "split_policy": {
            "atomic_unit": "canonical_request",
            "boundary": (
                "chronological_request_count_with_timestamp_ties_assigned_to_later_split"
            ),
            "request_identity": (
                "HMAC-SHA256(hash_salt,user_id:request_id)"
                if config.identity_mode == "hash"
                else "not_exported"
            ),
            "internal_grouping": (
                "canonical_user_and_request_identity_in_memory_only"
            ),
            "legacy_compatibility": (
                "request_group_rekeyed_from_sha256_request_id"
            ),
        },
        "split_request_stats": split_request_stats,
        "class_balance": dict(
            sorted(Counter(row.label_name for row in result.rows).items())
        ),
        "source_counts": {
            "impressions": result.stats.impressions_read,
            "events": result.stats.events_read,
        },
        "exclusions": {
            "served_without_visible": result.stats.served_without_visible,
            "immature_impressions": result.stats.immature_impressions,
            "unsupported_feature_schema": result.stats.unsupported_feature_schema,
        },
        "code_version": code_version,
    }
    metadata_path = output.with_suffix(f"{output.suffix}.metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metadata_path


async def fetch_telemetry(
    database_url: str, config: DatasetConfig
) -> tuple[list[Impression], list[BehaviorEvent]]:
    import asyncpg

    connection = await asyncpg.connect(database_url)
    try:
        impression_rows = await connection.fetch(
            """
            SELECT id, request_id, user_id, post_id, position, feed_source,
                   model_version, feature_snapshot, served_at
            FROM recommendation_impressions
            WHERE served_at >= $1 AND served_at < $2
            ORDER BY served_at, id
            """,
            config.start,
            config.end,
        )
        impression_ids = [row["id"] for row in impression_rows]
        event_rows = (
            await connection.fetch(
                """
                SELECT id, impression_id, user_id, post_id, event_type,
                       dwell_ms, metadata, occurred_at, ingested_at
                FROM behavior_events
                WHERE impression_id = ANY($1::uuid[])
                  AND occurred_at <= $2
                  AND ingested_at <= $2
                ORDER BY occurred_at, id
                """,
                impression_ids,
                config.extraction_time,
            )
            if impression_ids
            else []
        )
    finally:
        await connection.close()
    return (
        [Impression.from_mapping(row) for row in impression_rows],
        [BehaviorEvent.from_mapping(row) for row in event_rows],
    )


def _code_version() -> str | None:
    if version := os.getenv("GIT_SHA"):
        return version
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a leakage-safe recommendation dataset from telemetry."
    )
    parser.add_argument("--start", required=True, type=parse_datetime)
    parser.add_argument("--end", required=True, type=parse_datetime)
    parser.add_argument("--extraction-time", type=parse_datetime)
    parser.add_argument("--label-window-hours", type=int, default=24)
    parser.add_argument(
        "--qualified-read-ms",
        "--positive-dwell-ms",
        dest="qualified_read_ms",
        type=int,
        default=int(os.getenv("QUALIFIED_READ_MS", "10000")),
    )
    parser.add_argument(
        "--recommendation-label-version",
        choices=("v1", "v2"),
        default=os.getenv("RECOMMENDATION_LABEL_VERSION", "v1"),
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--identity-mode", choices=("hash", "drop"), default="hash")
    parser.add_argument("--hash-salt", default=os.getenv("DATASET_HASH_SALT"))
    return parser


async def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    extraction_time = args.extraction_time or datetime.now(timezone.utc)
    try:
        config = DatasetConfig(
            start=args.start,
            end=args.end,
            extraction_time=extraction_time,
            label_window_hours=args.label_window_hours,
            qualified_read_ms=args.qualified_read_ms,
            recommendation_label_version=args.recommendation_label_version,
            identity_mode=args.identity_mode,
            hash_salt=args.hash_salt,
        )
    except ValueError as error:
        parser.error(str(error))
    impressions, events = await fetch_telemetry(args.database_url, config)
    result = build_samples(impressions, events, config)
    metadata_path = write_artifact(
        result, config, args.output, code_version=_code_version()
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "metadata": str(metadata_path),
                "rows": len(result.rows),
            },
            sort_keys=True,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run(args, parser))


if __name__ == "__main__":
    raise SystemExit(main())
