from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import math
import os
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

from recommendation_label import CONTRACT_VERSION, derive_label, event_label_version

from .config import PINNED_ENCODER_VERSION, DatasetConfig
from .schemas import (
    DATASET_V2_SCOPE,
    HISTORY_SCHEMA_VERSION,
    ArticleFeatureRecord,
    ArticleRepresentation,
    BehaviorEvent,
    BuildResult,
    BuildStats,
    DatasetRow,
    DatasetV2ValidationReport,
    HistoryEntry,
    HistorySnapshot,
    Impression,
    LabelName,
    RankingBuildResult,
    RankingDatasetRow,
    RankingHistoryEntry,
    SplitName,
    parse_datetime,
)

DATASET_SCHEMA_VERSION = "recommendation-dataset-v1"
DATASET_SCHEMA_VERSION_V2 = "recommendation-dataset-v2"
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


T = TypeVar("T", Impression, BehaviorEvent, ArticleFeatureRecord)


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


def _history_total_limit(config: Any) -> int:
    recent_limit = int(getattr(config, "history_recent_limit", 0))
    long_term_limit = int(getattr(config, "history_long_term_limit", 0))
    if recent_limit < 0 or long_term_limit < 0:
        raise ValueError("history limits must be non-negative")
    return recent_limit + long_term_limit


def _qualifies_for_history(event: BehaviorEvent, reference_at: datetime) -> bool:
    return (
        event.user_id is not None
        and event.event_type == "click"
        and event_label_version(event) == "v2"
        and event.occurred_at < reference_at
        and (event.ingested_at is None or event.ingested_at <= reference_at)
    )


def _select_history_feature(
    features: Sequence[ArticleFeatureRecord], engaged_at: datetime
) -> ArticleFeatureRecord | None:
    eligible = [
        feature
        for feature in features
        if feature.source_updated_at <= engaged_at and feature.computed_at <= engaged_at
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda feature: (
            feature.source_updated_at,
            feature.computed_at,
            feature.id,
        ),
    )


def build_history_snapshot(
    user_id: UUID,
    reference_at: datetime,
    events: Iterable[BehaviorEvent],
    article_features: Iterable[ArticleFeatureRecord],
    config: Any,
) -> HistorySnapshot:
    total_limit = _history_total_limit(config)
    selected_events = (
        sorted(
            (
                event
                for event in events
                if event.user_id == user_id and _qualifies_for_history(event, reference_at)
            ),
            key=lambda event: (event.occurred_at, event.id),
        )[-total_limit:]
        if total_limit
        else []
    )
    features_by_post = defaultdict(list)
    for feature in _deduplicate(article_features).values():
        features_by_post[feature.post_id].append(feature)

    entries: list[HistoryEntry] = []
    for event in selected_events:
        feature = _select_history_feature(features_by_post.get(event.post_id, ()), event.occurred_at)
        if feature is None:
            continue
        entries.append(
            HistoryEntry(
                event_id=event.id,
                post_id=event.post_id,
                event_type="click",
                engaged_at=event.occurred_at,
                encoder_version=feature.encoder_version,
                content_hash=feature.content_hash,
                feature_source_updated_at=feature.source_updated_at,
                feature_computed_at=feature.computed_at,
                embedding=feature.embedding,
            )
        )
    return HistorySnapshot(
        schema_version=HISTORY_SCHEMA_VERSION,
        user_id=user_id,
        reference_at=reference_at,
        entries=tuple(entries),
    )


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


def _article_representation_from_feature(
    feature: ArticleFeatureRecord, salt: str
) -> ArticleRepresentation:
    return ArticleRepresentation(
        article_group=_hash_identity(feature.post_id, salt),
        representation_type="post-content-embedding-v1",
        encoder_version=feature.encoder_version,
        content_hash=feature.content_hash,
        embedding=feature.embedding,
        feature_source_updated_at=feature.source_updated_at,
        feature_computed_at=feature.computed_at,
    )


def _split_ranking_rows(
    rows: Sequence[RankingDatasetRow],
    train_fraction: float,
    validation_fraction: float,
) -> tuple[RankingDatasetRow, ...]:
    grouped: dict[str, list[RankingDatasetRow]] = defaultdict(list)
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

    test_count = max(1, round(group_count * (1 - train_fraction - validation_fraction)))
    validation_count = max(1, round(group_count * validation_fraction)) if group_count >= 3 else 0
    if test_count + validation_count >= group_count:
        validation_count = max(0, group_count - test_count - 1)
    train_end = group_count - validation_count - test_count
    validation_end = train_end + validation_count
    group_times = [min(row.served_at for row in group) for group in ordered_groups]
    train_end = _snap_split_boundary(
        train_end,
        group_times,
        prefer_non_empty_side="left",
    )
    validation_end = _snap_split_boundary(
        validation_end,
        group_times,
        prefer_non_empty_side="right",
    )
    validation_end = max(train_end, validation_end)

    split_rows: list[RankingDatasetRow] = []
    for index, group in enumerate(ordered_groups):
        split: SplitName
        if index < train_end:
            split = "train"
        elif index < validation_end:
            split = "validation"
        else:
            split = "test"
        split_rows.extend(replace(row, split=split) for row in group)
    return tuple(sorted(split_rows, key=lambda row: (row.served_at, row.position, row.sample_id)))


def _snap_split_boundary(
    boundary: int,
    group_times: Sequence[datetime],
    *,
    prefer_non_empty_side: Literal["left", "right"],
) -> int:
    group_count = len(group_times)
    if boundary <= 0:
        return 0
    if boundary >= group_count:
        return group_count
    if group_times[boundary - 1] != group_times[boundary]:
        return boundary

    left_boundary = boundary
    while (
        0 < left_boundary < group_count
        and group_times[left_boundary - 1] == group_times[left_boundary]
    ):
        left_boundary -= 1
    right_boundary = boundary
    while (
        0 < right_boundary < group_count
        and group_times[right_boundary - 1] == group_times[right_boundary]
    ):
        right_boundary += 1

    def score(candidate: int) -> tuple[int, int, int, int]:
        left_non_empty = int(candidate > 0)
        right_non_empty = int(candidate < group_count)
        populated_sides = left_non_empty + right_non_empty
        preferred_side = (
            left_non_empty if prefer_non_empty_side == "left" else right_non_empty
        )
        return (-populated_sides, -preferred_side, abs(candidate - boundary), candidate)

    return min((left_boundary, right_boundary), key=score)


def build_ranking_samples_v2(
    impressions: Iterable[Impression],
    events: Iterable[BehaviorEvent],
    article_features: Iterable[ArticleFeatureRecord],
    config: DatasetConfig,
) -> RankingBuildResult:
    if config.dataset_schema_version != "v2":
        raise ValueError("build_ranking_samples_v2 requires dataset schema v2")
    impression_list = list(impressions)
    event_list = list(events)
    feature_list = list(article_features)
    unique_impressions = _deduplicate(impression_list)
    unique_events = _deduplicate(event_list)
    unique_features = _deduplicate(feature_list)
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
            and (event.ingested_at is None or event.ingested_at <= config.extraction_time)
        ):
            events_by_impression[event.impression_id].append(event)
    features_by_post: dict[UUID, list[ArticleFeatureRecord]] = defaultdict(list)
    for feature in unique_features.values():
        features_by_post[feature.post_id].append(feature)

    rows: list[RankingDatasetRow] = []
    served_without_visible = 0
    immature_impressions = 0
    unsupported_feature_schema = 0
    label_window = timedelta(hours=config.label_window_hours)
    salt = config.hash_salt or ""

    for impression in sorted(window_impressions, key=lambda item: (item.served_at, item.position, item.id)):
        linked_events = [
            event
            for event in events_by_impression.get(impression.id, ())
            if event.user_id == impression.user_id and event.post_id == impression.post_id
        ]
        visible_events = [
            event
            for event in linked_events
            if event.event_type == "visible" and event.occurred_at >= impression.served_at
        ]
        if not visible_events:
            served_without_visible += 1
            continue
        visible_at = min(event.occurred_at for event in visible_events)
        label_window_end = visible_at + label_window
        if label_window_end > config.extraction_time:
            immature_impressions += 1
            continue
        if not _validate_snapshot(impression.feature_snapshot):
            unsupported_feature_schema += 1
            continue
        label_events = [
            event
            for event in linked_events
            if impression.served_at <= event.occurred_at <= label_window_end
        ]
        persisted_versions = {event_label_version(event) for event in label_events}
        if persisted_versions != {"v2"}:
            raise ValueError("recommendation dataset v2 requires only persisted label v2 events")
        label = derive_label(
            label_events,
            label_version="v2",
            qualified_read_ms=config.qualified_read_ms,
            label_window_closed=True,
        )
        if label.training_target is None:
            raise ValueError("recommendation dataset v2 requires finalized utility labels")

        feature = _select_history_feature(
            features_by_post.get(impression.post_id, ()), impression.served_at
        )
        article = (
            _article_representation_from_feature(feature, salt)
            if feature is not None
            else ArticleRepresentation(
                article_group=_hash_identity(impression.post_id, salt),
                representation_type="post-content-embedding-v1",
            )
        )
        history_snapshot = build_history_snapshot(
            impression.user_id,
            impression.served_at,
            unique_events.values(),
            unique_features.values(),
            config,
        )
        history = tuple(
            RankingHistoryEntry(
                article=_article_representation_from_feature(
                    ArticleFeatureRecord(
                        id=entry.event_id,
                        post_id=entry.post_id,
                        encoder_version=entry.encoder_version,
                        content_hash=entry.content_hash,
                        embedding=entry.embedding,
                        source_updated_at=entry.feature_source_updated_at,
                        computed_at=entry.feature_computed_at,
                    ),
                    salt,
                ),
                ordinal=index,
                engaged_at=entry.engaged_at,
                provenance="oecophylla-click-v2",
            )
            for index, entry in enumerate(history_snapshot.entries)
        )
        rows.append(
            RankingDatasetRow(
                sample_id=_hash_identity(impression.id, salt),
                request_group=_hmac_request_identity(impression, salt),
                candidate_group=_hash_identity(impression.post_id, salt),
                split="train",
                served_at=impression.served_at,
                visible_at=visible_at,
                position=impression.position,
                served=True,
                visible=True,
                click_label=int(any(event.event_type == "click" for event in label_events)),
                utility_label=int(label.training_target),
                utility_label_name=label.semantic,
                article=article,
                history=history,
                feed_source=impression.feed_source,
                model_version=impression.model_version,
                source_format="oecophylla-telemetry-v2",
                audit_request_identity=_canonical_request_identity(impression),
            )
        )

    result = RankingBuildResult(
        rows=_split_ranking_rows(rows, config.train_fraction, config.validation_fraction),
        stats=BuildStats(
            impressions_read=len(impression_list),
            events_read=len(event_list),
            served_without_visible=served_without_visible,
            immature_impressions=immature_impressions,
            unsupported_feature_schema=unsupported_feature_schema,
        ),
        expected_encoder_version=config.encoder_version,
        expected_embedding_dimension=config.encoder_dimension,
    )
    validate_dataset_v2(result)
    return result


def _validate_article_representation(
    article: ArticleRepresentation,
    *,
    expected_encoder_version: str | None,
    expected_embedding_dimension: int | None,
    available_at: datetime | None,
) -> None:
    if article.representation_type == "post-content-embedding-v1":
        if article.embedding is None:
            raise ValueError("missing article representation")
        if not article.embedding or any(not math.isfinite(value) for value in article.embedding):
            raise ValueError("invalid article embedding")
        if not article.encoder_version or not article.content_hash:
            raise ValueError("missing article representation provenance")
        if (
            article.feature_source_updated_at is None
            or article.feature_computed_at is None
        ):
            raise ValueError("missing article feature revision timestamps")
        if (
            article.feature_source_updated_at.tzinfo is None
            or article.feature_computed_at.tzinfo is None
        ):
            raise ValueError("article feature revision timestamps require a timezone")
        if article.feature_source_updated_at > article.feature_computed_at:
            raise ValueError("article feature source timestamp exceeds computation time")
        if available_at is not None and (
            article.feature_source_updated_at > available_at
            or article.feature_computed_at > available_at
        ):
            raise ValueError("article feature revision must not be from the future")
        if not _is_private_hash(article.content_hash):
            raise ValueError(
                "article content_hash must be 64 lowercase hexadecimal characters"
            )
        if (
            expected_encoder_version is not None
            and article.encoder_version != expected_encoder_version
        ):
            raise ValueError("article encoder version does not match dataset metadata")
        if (
            expected_embedding_dimension is not None
            and len(article.embedding) != expected_embedding_dimension
        ):
            raise ValueError("article embedding dimension does not match dataset metadata")
        norm = math.sqrt(sum(value * value for value in article.embedding))
        if not math.isclose(norm, 1.0, rel_tol=1e-5, abs_tol=1e-5):
            raise ValueError("article embedding must be finite and L2-normalized")
    elif article.representation_type == "mind-text-v1":
        if not ((article.title or "").strip() or (article.abstract or "").strip()):
            raise ValueError("missing article representation")
        if article.embedding is not None:
            raise ValueError("MIND text representation must not contain an unpinned embedding")
        if article.content_hash is None or not _is_private_hash(article.content_hash):
            raise ValueError("MIND text representation requires a versioned content hash")
        if (
            article.feature_source_updated_at is not None
            or article.feature_computed_at is not None
        ):
            raise ValueError("MIND text representation must not fabricate feature timestamps")
    else:
        raise ValueError("unsupported article representation")


def _is_private_hash(value: str) -> bool:
    if len(value) != 64 or value != value.lower():
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _contains_forbidden_identity_key(value: Any) -> bool:
    forbidden = {
        "user_id",
        "post_id",
        "impression_id",
        "request_id",
        "news_id",
        "mind_id",
    }
    if isinstance(value, Mapping):
        return bool(forbidden.intersection(value)) or any(
            _contains_forbidden_identity_key(child) for child in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_identity_key(child) for child in value)
    return False


def validate_dataset_v2(result: RankingBuildResult) -> DatasetV2ValidationReport:
    if not result.rows:
        raise ValueError("recommendation dataset v2 must contain candidates")
    by_request: dict[str, list[RankingDatasetRow]] = defaultdict(list)
    sample_ids: set[str] = set()
    for row in result.rows:
        if row.dataset_scope != DATASET_V2_SCOPE:
            raise ValueError("dataset scope must be served-impression-reranking")
        if not row.served or not row.visible:
            raise ValueError("dataset v2 candidates must be served and visibly proven")
        if row.served_at.tzinfo is None or row.visible_at.tzinfo is None:
            raise ValueError("dataset v2 timestamps must include a timezone")
        if row.visible_at < row.served_at:
            raise ValueError("visible_at must not precede served_at")
        if row.click_label not in (0, 1) or row.utility_label not in (0, 1):
            raise ValueError("dataset v2 labels must be binary")
        expected_utility = {
            "click": 1,
            "qualified_read": 1,
            "positive": 1,
            "strong_positive": 1,
            "negative": 0,
            "strong_negative": 0,
        }.get(row.utility_label_name)
        if expected_utility is None or row.utility_label != expected_utility:
            raise ValueError("utility label does not match its versioned semantic")
        if not all(
            _is_private_hash(value)
            for value in (row.sample_id, row.request_group, row.candidate_group)
        ):
            raise ValueError("dataset v2 identities must be private hashes")
        if row.sample_id in sample_ids:
            raise ValueError("dataset v2 sample_id must be unique")
        sample_ids.add(row.sample_id)
        if row.article.article_group != row.candidate_group:
            raise ValueError("candidate identity must match its article representation")
        _validate_article_representation(
            row.article,
            expected_encoder_version=result.expected_encoder_version,
            expected_embedding_dimension=result.expected_embedding_dimension,
            available_at=row.served_at,
        )
        if [entry.ordinal for entry in row.history] != list(range(len(row.history))):
            raise ValueError("history ordinals must be contiguous and ordered")
        local_history_times = [
            entry.engaged_at
            for entry in row.history
            if entry.provenance == "oecophylla-click-v2"
        ]
        if local_history_times != sorted(local_history_times):
            raise ValueError("history timestamps must be ordered")
        for entry in row.history:
            if not _is_private_hash(entry.article.article_group):
                raise ValueError("history identities must be private hashes")
            _validate_article_representation(
                entry.article,
                expected_encoder_version=result.expected_encoder_version,
                expected_embedding_dimension=result.expected_embedding_dimension,
                available_at=entry.engaged_at,
            )
            if entry.provenance == "oecophylla-click-v2":
                if entry.engaged_at is None or entry.engaged_at >= row.served_at:
                    raise ValueError("history must be strictly before serving")
            elif entry.provenance == "mind-pre-impression-snapshot":
                if entry.engaged_at is not None:
                    raise ValueError("MIND snapshot history must use ordinal ordering")
            else:
                raise ValueError("unsupported history provenance")
        if _contains_forbidden_identity_key(row.to_record()):
            raise ValueError("raw identity field leaked into dataset v2")
        by_request[row.request_group].append(row)

    empty_history_requests = 0
    for candidates in by_request.values():
        if len(candidates) < 2:
            raise ValueError("each request requires at least two candidates")
        if len({row.split for row in candidates}) != 1:
            raise ValueError("request group crosses splits")
        if len({row.audit_request_identity for row in candidates}) != 1:
            raise ValueError("request hash collision or conflicting request envelope")
        if len({row.position for row in candidates}) != len(candidates):
            raise ValueError("candidate positions must be unique within a request")
        if len({row.candidate_group for row in candidates}) != len(candidates):
            raise ValueError("candidates must be unique within a request")
        if len({row.history for row in candidates}) != 1:
            raise ValueError("request candidates must share one history snapshot")
        if len(
            {
                (row.served_at, row.feed_source, row.model_version, row.source_format)
                for row in candidates
            }
        ) != 1:
            raise ValueError("request candidates must share one immutable serving envelope")
        if not candidates[0].history:
            empty_history_requests += 1

    request_times_by_split: dict[SplitName, list[datetime]] = defaultdict(list)
    for candidates in by_request.values():
        request_times_by_split[candidates[0].split].append(candidates[0].served_at)
    split_order: tuple[SplitName, ...] = ("train", "validation", "test")
    populated = [split_name for split_name in split_order if request_times_by_split[split_name]]
    for earlier, later in pairwise(populated):
        if max(request_times_by_split[earlier]) > min(request_times_by_split[later]):
            raise ValueError("dataset splits are not chronological")

    click_balance = Counter(row.click_label for row in result.rows)
    utility_balance = Counter(row.utility_label for row in result.rows)
    if set(click_balance) != {0, 1}:
        raise ValueError("click_label class balance requires positive and negative candidates")
    if set(utility_balance) != {0, 1}:
        raise ValueError("utility_label class balance requires positive and negative candidates")
    return DatasetV2ValidationReport(
        request_count=len(by_request),
        candidate_count=len(result.rows),
        empty_history_requests=empty_history_requests,
        click_class_balance=dict(click_balance),
        utility_class_balance=dict(utility_balance),
    )


def write_dataset_v2_artifact(
    result: RankingBuildResult,
    config: DatasetConfig,
    output: Path,
    *,
    code_version: str | None,
    source_format: str,
) -> Path:
    import pyarrow as arrow
    from pyarrow import parquet

    report = validate_dataset_v2(result)
    if not code_version or not code_version.strip():
        raise ValueError("dataset v2 artifact requires an immutable code version")
    if config.dataset_schema_version != "v2":
        raise ValueError("dataset v2 artifact requires schema-version v2")
    if config.recommendation_label_version != "v2":
        raise ValueError("dataset v2 artifact requires engagement-label-v2")
    if result.expected_encoder_version != config.encoder_version:
        raise ValueError("artifact encoder version was not verified by dataset rows")
    if result.expected_embedding_dimension != config.encoder_dimension:
        raise ValueError("artifact embedding dimension was not verified by dataset rows")
    if {row.source_format for row in result.rows} != {source_format}:
        raise ValueError("artifact source format does not match dataset rows")
    output.parent.mkdir(parents=True, exist_ok=True)
    parquet.write_table(
        arrow.Table.from_pylist([row.to_record() for row in result.rows]),
        output,
        compression="zstd",
    )
    candidates_per_request = Counter(row.request_group for row in result.rows)
    metadata = {
        "dataset_schema_version": DATASET_SCHEMA_VERSION_V2,
        "dataset_scope": DATASET_V2_SCOPE,
        "source_format": source_format,
        "feature_schema_version": config.feature_schema_version,
        "history_schema_version": HISTORY_SCHEMA_VERSION,
        "label_definition_version": CONTRACT_VERSION,
        "qualified_read_ms": config.qualified_read_ms,
        "encoder_version": config.encoder_version,
        "encoder_dimension": config.encoder_dimension,
        "code_version": code_version,
        "query_window_version": config.query_window_version,
        "query_window": {
            "start": config.start.isoformat(),
            "end": config.end.isoformat(),
            "extraction_time": config.extraction_time.isoformat(),
        },
        "identity_mode": config.identity_mode,
        "row_count": len(result.rows),
        "request_count": report.request_count,
        "empty_history_requests": report.empty_history_requests,
        "split_counts": dict(sorted(Counter(row.split for row in result.rows).items())),
        "candidate_count_distribution": dict(sorted(Counter(candidates_per_request.values()).items())),
        "class_balance": {
            "click_label": {str(key): value for key, value in sorted(report.click_class_balance.items())},
            "utility_label": {str(key): value for key, value in sorted(report.utility_class_balance.items())},
        },
        "exclusions": {
            "served_without_visible": result.stats.served_without_visible,
            "immature_impressions": result.stats.immature_impressions,
            "unsupported_feature_schema": result.stats.unsupported_feature_schema,
        },
        "split_policy": {
            "atomic_unit": "canonical_request",
            "boundary": "chronological_request_count_with_unsplit_timestamp_buckets",
        },
        "privacy": {
            "raw_user_ids": False,
            "raw_post_ids": False,
            "raw_request_ids": False,
        },
        "retrieval_recall_supported": False,
    }
    metadata_path = output.with_suffix(f"{output.suffix}.metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metadata_path


def write_artifact(
    result: BuildResult,
    config: DatasetConfig,
    output: Path,
    *,
    code_version: str | None,
) -> Path:
    import pyarrow as arrow
    from pyarrow import parquet

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
                       dwell_ms, metadata, occurred_at, ingested_at, event_version
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


async def fetch_dataset_v2_inputs(
    database_url: str, config: DatasetConfig
) -> tuple[list[Impression], list[BehaviorEvent], list[ArticleFeatureRecord]]:
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
        user_ids = sorted({row["user_id"] for row in impression_rows})
        event_rows = (
            await connection.fetch(
                """
                SELECT id, impression_id, user_id, post_id, event_type,
                       dwell_ms, metadata, occurred_at, ingested_at, event_version
                FROM behavior_events
                WHERE (
                    impression_id = ANY($1::uuid[])
                    OR (
                        user_id = ANY($2::uuid[])
                        AND event_type = 'click'
                        AND event_version = 'v2'
                        AND occurred_at < $3
                    )
                )
                  AND occurred_at <= $4
                  AND ingested_at <= $4
                ORDER BY occurred_at, id
                """,
                impression_ids,
                user_ids,
                config.end,
                config.extraction_time,
            )
            if impression_ids
            else []
        )
        post_ids = sorted(
            {row["post_id"] for row in impression_rows}.union(
                row["post_id"] for row in event_rows if row["event_type"] == "click"
            )
        )
        feature_rows = (
            await connection.fetch(
                """
                SELECT id, post_id, encoder_version, content_hash, embedding,
                       source_updated_at, computed_at
                FROM post_content_features
                WHERE post_id = ANY($1::uuid[])
                  AND encoder_version = $2
                  AND computed_at <= $3
                ORDER BY post_id, source_updated_at, computed_at, id
                """,
                post_ids,
                config.encoder_version,
                config.extraction_time,
            )
            if post_ids
            else []
        )
    finally:
        await connection.close()
    return (
        [Impression.from_mapping(row) for row in impression_rows],
        [BehaviorEvent.from_mapping(row) for row in event_rows],
        [ArticleFeatureRecord.from_mapping(row) for row in feature_rows],
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
        default=None,
    )
    parser.add_argument(
        "--schema-version",
        choices=("v1", "v2"),
        default="v1",
        help="Output schema; v2 emits grouped ranking rows with histories and article representations.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--identity-mode", choices=("hash", "drop"), default="hash")
    parser.add_argument("--hash-salt", default=os.getenv("DATASET_HASH_SALT"))
    parser.add_argument(
        "--encoder-version",
        default=os.getenv("EMBEDDING_ENCODER_VERSION", PINNED_ENCODER_VERSION),
    )
    parser.add_argument("--encoder-dimension", type=int, default=384)
    parser.add_argument("--history-recent-limit", type=int, default=20)
    parser.add_argument("--history-long-term-limit", type=int, default=30)
    return parser


async def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    extraction_time = args.extraction_time or datetime.now(timezone.utc)
    label_version = args.recommendation_label_version
    if label_version is None:
        label_version = (
            "v2"
            if args.schema_version == "v2"
            else os.getenv("RECOMMENDATION_LABEL_VERSION", "v1")
        )
    try:
        config = DatasetConfig(
            start=args.start,
            end=args.end,
            extraction_time=extraction_time,
            label_window_hours=args.label_window_hours,
            qualified_read_ms=args.qualified_read_ms,
            recommendation_label_version=label_version,
            identity_mode=args.identity_mode,
            hash_salt=args.hash_salt,
            history_recent_limit=args.history_recent_limit,
            history_long_term_limit=args.history_long_term_limit,
            dataset_schema_version=args.schema_version,
            encoder_version=args.encoder_version,
            encoder_dimension=args.encoder_dimension,
        )
    except ValueError as error:
        parser.error(str(error))
    if config.dataset_schema_version == "v2":
        impressions, events, features = await fetch_dataset_v2_inputs(
            args.database_url, config
        )
        result = build_ranking_samples_v2(impressions, events, features, config)
        metadata_path = write_dataset_v2_artifact(
            result,
            config,
            args.output,
            code_version=_code_version(),
            source_format="oecophylla-telemetry-v2",
        )
    else:
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
