from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Literal, Protocol

from .content_features import (
    CONTENT_HASH_VERSION,
    ENCODER_VERSION,
    SCHEMA_VERSION,
    content_hash,
    normalize_content,
    normalize_topics,
    validate_embedding,
)
from .infer import infer_topics

logger = logging.getLogger("nlp_worker.embedding")


@dataclass(frozen=True)
class PostRecord:
    post_id: str
    content: str
    topics: list[str]
    updated_at: datetime


@dataclass(frozen=True)
class PostFeature:
    schema_version: str
    post_id: str
    encoder_version: str
    normalization_version: str
    content_hash: str
    embedding: list[float]
    normalized_topics: list[str]
    source_updated_at: datetime
    computed_at: datetime


@dataclass(frozen=True)
class ProcessResult:
    status: Literal["created", "unchanged", "fallback"]


class Encoder(Protocol):
    version: str

    def encode_passage(self, normalized_text: str) -> list[float]: ...


class FeatureRepository(Protocol):
    async def feature_exists(
        self, post_id: str, encoder_version: str, digest: str
    ) -> bool: ...

    async def insert_feature(self, feature: PostFeature) -> bool: ...

    async def ensure_topics(self, post_id: str, topics: list[str]) -> None: ...


class Metrics(Protocol):
    def observe_inference(self, elapsed: float) -> None: ...
    def feature_created(self) -> None: ...
    def feature_unchanged(self) -> None: ...
    def embedding_missing(self) -> None: ...
    def embedding_failure(self, reason: str) -> None: ...


class EmbeddingService:
    def __init__(
        self,
        repository: FeatureRepository,
        encoder: Encoder,
        *,
        metrics: Metrics,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if encoder.version != ENCODER_VERSION:
            raise ValueError("encoder version does not match the T4A contract")
        self.repository = repository
        self.encoder = encoder
        self.metrics = metrics
        self.clock = clock or (lambda: datetime.now(UTC))

    async def process(self, record: PostRecord) -> ProcessResult:
        topics = normalize_topics(record.topics or infer_topics(record.content))
        await self.repository.ensure_topics(record.post_id, topics)

        try:
            normalized = normalize_content(record.content)
            digest = content_hash(normalized)
        except (TypeError, ValueError):
            return self._fallback("validation")

        if await self.repository.feature_exists(
            record.post_id, self.encoder.version, digest
        ):
            self.metrics.feature_unchanged()
            return ProcessResult("unchanged")

        computed_at = self.clock()
        source_updated_at = record.updated_at
        if source_updated_at.tzinfo is None:
            source_updated_at = source_updated_at.replace(tzinfo=UTC)
        if source_updated_at > computed_at:
            return self._fallback("future_source")

        started = time.monotonic()
        try:
            embedding = validate_embedding(self.encoder.encode_passage(normalized))
        except ValueError:
            logger.warning("invalid embedding; retaining keyword topic fallback")
            return self._fallback("validation")
        except Exception:  # model failures must never block topic fallback
            logger.warning("embedding unavailable; retaining keyword topic fallback")
            return self._fallback("model")
        finally:
            self.metrics.observe_inference(time.monotonic() - started)

        feature = PostFeature(
            schema_version=SCHEMA_VERSION,
            post_id=record.post_id,
            encoder_version=self.encoder.version,
            normalization_version=CONTENT_HASH_VERSION,
            content_hash=digest,
            embedding=embedding,
            normalized_topics=topics,
            source_updated_at=source_updated_at,
            computed_at=computed_at,
        )
        try:
            inserted = await self.repository.insert_feature(feature)
        except Exception:
            logger.warning("embedding storage failed; retaining keyword topic fallback")
            return self._fallback("storage")
        if inserted:
            self.metrics.feature_created()
            return ProcessResult("created")
        self.metrics.feature_unchanged()
        return ProcessResult("unchanged")

    def _fallback(self, reason: str) -> ProcessResult:
        self.metrics.embedding_failure(reason)
        self.metrics.embedding_missing()
        return ProcessResult("fallback")
