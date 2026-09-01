from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Mapping
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
