from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

SplitName = Literal["train", "validation", "test"]
LabelName = Literal[
    "exposure",
    "click",
    "qualified_read",
    "strong_negative",
    "negative",
    "positive",
    "strong_positive",
]
HistoryEventType = Literal["click"]
HISTORY_SCHEMA_VERSION = "user-history-snapshot-v1"
DATASET_V2_SCOPE = "served-impression-reranking"
ArticleRepresentationType = Literal["post-content-embedding-v1", "mind-text-v1"]


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("timestamp must be a datetime or ISO-8601 string")
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


@dataclass(frozen=True)
class Impression:
    id: UUID
    request_id: UUID
    user_id: UUID
    post_id: UUID
    position: int
    feed_source: str
    model_version: str
    feature_snapshot: Mapping[str, Any]
    served_at: datetime

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> Impression:
        return cls(
            id=UUID(str(row["id"])),
            request_id=UUID(str(row["request_id"])),
            user_id=UUID(str(row["user_id"])),
            post_id=UUID(str(row["post_id"])),
            position=int(row["position"]),
            feed_source=str(row["feed_source"]),
            model_version=str(row["model_version"]),
            feature_snapshot=dict(row["feature_snapshot"]),
            served_at=parse_datetime(row["served_at"]),
        )


@dataclass(frozen=True)
class BehaviorEvent:
    id: UUID
    impression_id: UUID | None
    user_id: UUID
    post_id: UUID
    event_type: str
    dwell_ms: int | None
    occurred_at: datetime
    ingested_at: datetime | None = None
    event_version: str | None = None
    metadata: Mapping[str, Any] | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> BehaviorEvent:
        impression_id = row.get("impression_id")
        dwell_ms = row.get("dwell_ms")
        metadata = (
            dict(row["metadata"])
            if isinstance(row.get("metadata"), Mapping)
            else None
        )
        persisted_version = row.get("event_version")
        if persisted_version is None and metadata is not None:
            persisted_version = metadata.get("event_version")
        return cls(
            id=UUID(str(row["id"])),
            impression_id=UUID(str(impression_id)) if impression_id else None,
            user_id=UUID(str(row["user_id"])),
            post_id=UUID(str(row["post_id"])),
            event_type=str(row["event_type"]),
            dwell_ms=int(dwell_ms) if dwell_ms is not None else None,
            occurred_at=parse_datetime(row["occurred_at"]),
            ingested_at=(
                parse_datetime(row["ingested_at"])
                if row.get("ingested_at") is not None
                else None
            ),
            event_version=(
                str(persisted_version)
                if persisted_version is not None
                else None
            ),
            metadata=metadata,
        )


@dataclass(frozen=True)
class ArticleFeatureRecord:
    id: UUID
    post_id: UUID
    encoder_version: str
    content_hash: str
    embedding: tuple[float, ...]
    source_updated_at: datetime
    computed_at: datetime

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> ArticleFeatureRecord:
        return cls(
            id=UUID(str(row["id"])),
            post_id=UUID(str(row["post_id"])),
            encoder_version=str(row["encoder_version"]),
            content_hash=str(row["content_hash"]),
            embedding=tuple(float(value) for value in row["embedding"]),
            source_updated_at=parse_datetime(row["source_updated_at"]),
            computed_at=parse_datetime(row["computed_at"]),
        )


@dataclass(frozen=True)
class HistoryEntry:
    event_id: UUID
    post_id: UUID
    event_type: HistoryEventType
    engaged_at: datetime
    encoder_version: str
    content_hash: str
    feature_source_updated_at: datetime
    feature_computed_at: datetime
    embedding: tuple[float, ...]

    def to_audit_record(
        self, *, identity_mode: Literal["hash", "drop"], hash_salt: str | None
    ) -> dict[str, Any]:
        record = {
            "event_type": self.event_type,
            "engaged_at": self.engaged_at,
            "encoder_version": self.encoder_version,
            "content_hash": self.content_hash,
            "feature_source_updated_at": self.feature_source_updated_at,
            "feature_computed_at": self.feature_computed_at,
        }
        if identity_mode == "hash":
            if not hash_salt:
                raise ValueError("hash_salt is required when identity_mode=hash")
            record["post_group"] = hmac.new(
                hash_salt.encode(),
                str(self.post_id).encode(),
                hashlib.sha256,
            ).hexdigest()
        else:
            record["post_group"] = None
        return record


@dataclass(frozen=True)
class HistorySnapshot:
    schema_version: str
    user_id: UUID
    reference_at: datetime
    entries: tuple[HistoryEntry, ...]

    def to_audit_record(
        self, *, identity_mode: Literal["hash", "drop"], hash_salt: str | None
    ) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "reference_at": self.reference_at,
            "entries": [
                entry.to_audit_record(
                    identity_mode=identity_mode,
                    hash_salt=hash_salt,
                )
                for entry in self.entries
            ],
        }


@dataclass(frozen=True)
class DatasetRow:
    sample_id: str
    user_group: str | None
    post_group: str | None
    request_group: str | None
    split: SplitName
    label: int
    label_name: LabelName
    served_at: datetime
    visible_at: datetime
    position: int
    feed_source: str
    model_version: str
    feature_schema_version: str
    topic_relevance: float | None
    freshness: float | None
    safety_score: float | None
    candidate_source: str
    is_followed_author: bool | None
    author_affinity: float | None
    heuristic_score: float | None
    ml_score: float | None
    audit_user_id: str
    audit_post_id: str
    audit_request_identity: str

    def to_record(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "user_group": self.user_group,
            "post_group": self.post_group,
            "request_group": self.request_group,
            "split": self.split,
            "label": self.label,
            "label_name": self.label_name,
            "served_at": self.served_at,
            "visible_at": self.visible_at,
            "position": self.position,
            "feed_source": self.feed_source,
            "model_version": self.model_version,
            "feature_schema_version": self.feature_schema_version,
            "topic_relevance": self.topic_relevance,
            "freshness": self.freshness,
            "safety_score": self.safety_score,
            "candidate_source": self.candidate_source,
            "is_followed_author": self.is_followed_author,
            "author_affinity": self.author_affinity,
            "heuristic_score": self.heuristic_score,
            "ml_score": self.ml_score,
        }


@dataclass(frozen=True)
class BuildStats:
    impressions_read: int
    events_read: int
    served_without_visible: int
    immature_impressions: int
    unsupported_feature_schema: int


@dataclass(frozen=True)
class BuildResult:
    rows: tuple[DatasetRow, ...]
    stats: BuildStats


@dataclass(frozen=True)
class ArticleRepresentation:
    article_group: str
    representation_type: ArticleRepresentationType
    encoder_version: str | None = None
    content_hash: str | None = None
    embedding: tuple[float, ...] | None = None
    category: str | None = None
    subcategory: str | None = None
    title: str | None = None
    abstract: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "article_group": self.article_group,
            "representation_type": self.representation_type,
            "encoder_version": self.encoder_version,
            "content_hash": self.content_hash,
            "embedding": list(self.embedding) if self.embedding is not None else None,
            "category": self.category,
            "subcategory": self.subcategory,
            "title": self.title,
            "abstract": self.abstract,
        }


@dataclass(frozen=True)
class RankingHistoryEntry:
    article: ArticleRepresentation
    ordinal: int
    engaged_at: datetime | None
    provenance: Literal["oecophylla-click-v2", "mind-pre-impression-snapshot"]

    def to_record(self) -> dict[str, Any]:
        return {
            "article": self.article.to_record(),
            "ordinal": self.ordinal,
            "engaged_at": self.engaged_at,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class RankingDatasetRow:
    sample_id: str
    request_group: str
    candidate_group: str
    split: SplitName
    served_at: datetime
    visible_at: datetime
    position: int
    served: bool
    visible: bool
    click_label: int
    utility_label: int
    utility_label_name: LabelName
    article: ArticleRepresentation
    history: tuple[RankingHistoryEntry, ...]
    feed_source: str
    model_version: str
    source_format: str
    dataset_scope: Literal["served-impression-reranking"] = DATASET_V2_SCOPE
    audit_request_identity: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "request_group": self.request_group,
            "candidate_group": self.candidate_group,
            "split": self.split,
            "served_at": self.served_at,
            "visible_at": self.visible_at,
            "position": self.position,
            "served": self.served,
            "visible": self.visible,
            "click_label": self.click_label,
            "utility_label": self.utility_label,
            "utility_label_name": self.utility_label_name,
            "article": self.article.to_record(),
            "history": [entry.to_record() for entry in self.history],
            "feed_source": self.feed_source,
            "model_version": self.model_version,
            "source_format": self.source_format,
            "dataset_scope": self.dataset_scope,
        }


@dataclass(frozen=True)
class RankingBuildResult:
    rows: tuple[RankingDatasetRow, ...]
    stats: BuildStats
    expected_encoder_version: str | None = None
    expected_embedding_dimension: int | None = None


@dataclass(frozen=True)
class DatasetV2ValidationReport:
    request_count: int
    candidate_count: int
    empty_history_requests: int
    click_class_balance: Mapping[int, int]
    utility_class_balance: Mapping[int, int]
