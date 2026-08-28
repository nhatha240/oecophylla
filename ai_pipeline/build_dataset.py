from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, TypeVar
from uuid import UUID

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
LABEL_DEFINITION_VERSION = "engagement-label-v1"
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


def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _validate_snapshot(snapshot: Mapping[str, Any]) -> bool:
    return (
        snapshot.get("schema_version") == FEATURE_SCHEMA_VERSION
        and REQUIRED_FEATURES.issubset(snapshot)
        and isinstance(snapshot.get("candidate_source"), str)
        and bool(str(snapshot.get("candidate_source", "")).strip())
    )


def _label_for(events: Sequence[BehaviorEvent], positive_dwell_ms: int) -> LabelName:
    event_types = {event.event_type for event in events}
    if event_types & {"hide", "report"}:
        return "strong_negative"
    if event_types & {"save", "share"}:
        return "strong_positive"
    if event_types & {"click", "like", "comment"}:
        return "positive"
    if any(
        event.event_type in {"view", "dwell"}
        and event.dwell_ms is not None
        and event.dwell_ms >= positive_dwell_ms
        for event in events
    ):
        return "positive"
    return "negative"


def _split_rows(
    rows: Sequence[DatasetRow], config: DatasetConfig
) -> tuple[DatasetRow, ...]:
    ordered = sorted(rows, key=lambda row: (row.visible_at, row.sample_id))
    count = len(ordered)
    if count == 0:
        return ()
    if count == 1:
        return (replace(ordered[0], split="train"),)

    test_count = max(
        1, round(count * (1 - config.train_fraction - config.validation_fraction))
    )
    validation_count = (
        max(1, round(count * config.validation_fraction)) if count >= 3 else 0
    )
    if test_count + validation_count >= count:
        validation_count = max(0, count - test_count - 1)
    train_count = count - validation_count - test_count
    train_end = train_count
    validation_end = train_end + validation_count

    split_rows: list[DatasetRow] = []
    for index, row in enumerate(ordered):
        split: SplitName
        if index < train_end:
            split = "train"
        elif index < validation_end:
            split = "validation"
        else:
            split = "test"
        split_rows.append(replace(row, split=split))
    return tuple(split_rows)


def build_samples(
    impressions: Iterable[Impression],
    events: Iterable[BehaviorEvent],
    config: DatasetConfig,
) -> BuildResult:
    impression_list = list(impressions)
    event_list = list(events)
    unique_impressions = _deduplicate(impression_list)
    unique_events = _deduplicate(event_list)
    events_by_impression: dict[UUID, list[BehaviorEvent]] = defaultdict(list)
    for event in unique_events.values():
        if event.impression_id is not None:
            events_by_impression[event.impression_id].append(event)

    served_without_visible = 0
    immature_impressions = 0
    unsupported_feature_schema = 0
    rows: list[DatasetRow] = []
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
        label_name = _label_for(label_events, config.positive_dwell_ms)
        snapshot = impression.feature_snapshot
        if config.identity_mode == "hash":
            sample_id = _hash_identity(impression.id, salt)
            user_group = _hash_identity(impression.user_id, salt)
            post_group = _hash_identity(impression.post_id, salt)
        else:
            sample_id = f"sample-{len(rows) + 1:09d}"
            user_group = None
            post_group = None

        rows.append(
            DatasetRow(
                sample_id=sample_id,
                user_group=user_group,
                post_group=post_group,
                split="train",
                label=LABEL_VALUES[label_name],
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
            )
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

    metadata = {
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "label_definition_version": LABEL_DEFINITION_VERSION,
        "feature_schema_versions": sorted(
            {row.feature_schema_version for row in result.rows}
        ),
        "query_window": {
            "start": config.start.isoformat(),
            "end": config.end.isoformat(),
            "extraction_time": config.extraction_time.isoformat(),
        },
        "label_window_hours": config.label_window_hours,
        "positive_dwell_ms": config.positive_dwell_ms,
        "identity_mode": config.identity_mode,
        "row_count": len(result.rows),
        "split_counts": dict(sorted(Counter(row.split for row in result.rows).items())),
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
                       dwell_ms, occurred_at
                FROM behavior_events
                WHERE impression_id = ANY($1::uuid[])
                  AND occurred_at <= $2
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
        "--positive-dwell-ms",
        type=int,
        default=int(os.getenv("POSITIVE_DWELL_MS", "10000")),
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
            positive_dwell_ms=args.positive_dwell_ms,
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
