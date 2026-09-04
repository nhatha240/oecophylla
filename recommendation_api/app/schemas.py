from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from ai_pipeline.schemas import HistoryEntry, HistorySnapshot


class RecommendFeedRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    candidate_pool: int = Field(default=300, ge=1, le=1000)
    exclude_post_ids: list[UUID] = Field(default_factory=list)


class RankFeatureSnapshot(BaseModel):
    schema_version: Literal["rank-features-v1"]
    topic_relevance: Optional[float]
    freshness: Optional[float]
    safety_score: Optional[float]
    candidate_source: str
    is_followed_author: Optional[bool]
    author_affinity: Optional[float]
    heuristic_score: Optional[float]
    ml_score: Optional[float]


class RecommendationItem(BaseModel):
    post_id: UUID
    score: float
    source: str
    reason: str = ""
    features: RankFeatureSnapshot


class RecommendFeedResponse(BaseModel):
    items: list[RecommendationItem]
    model_version: str = Field(min_length=1)
    generated_at: datetime


class CandidatePost(BaseModel):
    id: UUID
    author_id: UUID
    topics: list[str]
    safety_score: float
    created_at: datetime
    source: str

    @property
    def primary_topic(self) -> Optional[str]:
        return self.topics[0] if self.topics else None


class RebuildRequest(BaseModel):
    user_id: Optional[UUID] = None


class RebuildResponse(BaseModel):
    users_processed: int
    duration_ms: int


class EvaluateRequest(BaseModel):
    user_id: UUID
    k: int = Field(default=10, ge=1, le=100)


class EvaluateResponse(BaseModel):
    status: Literal["ok", "insufficient_data"]
    precision_at_k: Optional[float] = None
    recall_at_k: Optional[float] = None
    ndcg_at_k: Optional[float] = None
    hit_rate: Optional[float] = None
    catalog_coverage: Optional[float] = None
    topic_diversity: Optional[float] = None
    ctr_observed: Optional[float] = None
    fallback_rate: Optional[float] = None
    sample_users: int = Field(ge=0)
    sample_impressions: int = Field(ge=0)
    cutoff_at: datetime
    label_window_hours: int = Field(ge=1)
    ctr_simulation: Optional[float] = Field(default=None, deprecated=True)
    diversity: Optional[float] = Field(default=None, deprecated=True)


class HistoryEntryPayload(BaseModel):
    event_id: UUID
    post_id: UUID
    event_type: Literal["click"]
    engaged_at: datetime
    encoder_version: str = Field(min_length=1)
    content_hash: str = Field(min_length=64, max_length=64)
    feature_source_updated_at: datetime
    feature_computed_at: datetime
    embedding: list[float]

    def to_offline_entry(self) -> HistoryEntry:
        return HistoryEntry(
            event_id=self.event_id,
            post_id=self.post_id,
            event_type=self.event_type,
            engaged_at=self.engaged_at,
            encoder_version=self.encoder_version,
            content_hash=self.content_hash,
            feature_source_updated_at=self.feature_source_updated_at,
            feature_computed_at=self.feature_computed_at,
            embedding=tuple(self.embedding),
        )

    def to_cache_record(self) -> dict[str, object]:
        return {
            "event_id": str(self.event_id),
            "post_id": str(self.post_id),
            "event_type": self.event_type,
            "engaged_at": self.engaged_at.isoformat(),
            "encoder_version": self.encoder_version,
            "content_hash": self.content_hash,
            "feature_source_updated_at": self.feature_source_updated_at.isoformat(),
            "feature_computed_at": self.feature_computed_at.isoformat(),
        }


class UserHistorySnapshotPayload(BaseModel):
    schema_version: Literal["user-history-snapshot-v1"]
    user_id: UUID
    reference_at: datetime
    entries: list[HistoryEntryPayload] = Field(default_factory=list)

    def to_offline_snapshot(self) -> HistorySnapshot:
        return HistorySnapshot(
            schema_version=self.schema_version,
            user_id=self.user_id,
            reference_at=self.reference_at,
            entries=tuple(entry.to_offline_entry() for entry in self.entries),
        )

    def to_cache_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "reference_at": self.reference_at.isoformat(),
            "entries": [entry.to_cache_record() for entry in self.entries],
        }
