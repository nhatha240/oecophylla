from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RecommendFeedRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    candidate_pool: int = Field(default=300, ge=1, le=1000)
    exclude_post_ids: list[UUID] = Field(default_factory=list)


class RecommendationItem(BaseModel):
    post_id: UUID
    score: float
    source: str
    reason: str = ""


class RecommendFeedResponse(BaseModel):
    items: list[RecommendationItem]
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
    precision_at_k: float
    ctr_simulation: float
    diversity: float
    fallback_rate: float
