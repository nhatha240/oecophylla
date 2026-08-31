from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.content_features import EMBEDDING_DIMENSION, ENCODER_VERSION
from app.embedding_worker import EmbeddingService, PostRecord


class FakeEncoder:
    version = ENCODER_VERSION

    def __init__(self, *, failure: Exception | None = None, dimension: int = EMBEDDING_DIMENSION):
        self.failure = failure
        self.dimension = dimension
        self.calls: list[str] = []

    def encode_passage(self, normalized_text: str) -> list[float]:
        self.calls.append(normalized_text)
        if self.failure:
            raise self.failure
        result = [0.0] * self.dimension
        result[0] = 1.0
        return result


class FakeRepository:
    def __init__(self) -> None:
        self.keys: set[tuple[str, str, str]] = set()
        self.features = []
        self.topic_updates: list[tuple[str, list[str]]] = []

    async def feature_exists(self, post_id: str, encoder_version: str, digest: str) -> bool:
        return (post_id, encoder_version, digest) in self.keys

    async def insert_feature(self, feature) -> bool:
        key = (feature.post_id, feature.encoder_version, feature.content_hash)
        if key in self.keys:
            return False
        self.keys.add(key)
        self.features.append(feature)
        return True

    async def ensure_topics(self, post_id: str, topics: list[str]) -> None:
        self.topic_updates.append((post_id, topics))


class FakeMetrics:
    def __init__(self) -> None:
        self.created = self.unchanged = self.missing = self.failures = 0

    def observe_inference(self, _elapsed: float) -> None:
        pass

    def feature_created(self) -> None:
        self.created += 1

    def feature_unchanged(self) -> None:
        self.unchanged += 1

    def embedding_missing(self) -> None:
        self.missing += 1

    def embedding_failure(self, _reason: str) -> None:
        self.failures += 1


def post(content: str, *, post_id: str = "operational-post", updated_at=None) -> PostRecord:
    return PostRecord(
        post_id=post_id,
        content=content,
        topics=[],
        updated_at=updated_at or datetime(2026, 8, 31, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_same_content_and_encoder_is_embedded_exactly_once() -> None:
    repository = FakeRepository()
    encoder = FakeEncoder()
    metrics = FakeMetrics()
    service = EmbeddingService(repository, encoder, metrics=metrics)

    first = await service.process(post("Bài viết về trí tuệ nhân tạo"))
    second = await service.process(post("Bài viết  về\ntrí tuệ nhân tạo"))

    assert first.status == "created"
    assert second.status == "unchanged"
    assert encoder.calls == ["Bài viết về trí tuệ nhân tạo"]
    assert len(repository.features) == 1
    assert metrics.created == 1
    assert metrics.unchanged == 1


@pytest.mark.asyncio
async def test_changed_content_creates_new_immutable_revision() -> None:
    repository = FakeRepository()
    encoder = FakeEncoder()
    service = EmbeddingService(repository, encoder, metrics=FakeMetrics())

    await service.process(post("Nội dung ban đầu"))
    result = await service.process(post("Nội dung đã sửa"))

    assert result.status == "created"
    assert len(repository.features) == 2
    assert repository.features[0].content_hash != repository.features[1].content_hash


@pytest.mark.asyncio
async def test_model_unavailable_keeps_keyword_topics_and_never_raises() -> None:
    repository = FakeRepository()
    metrics = FakeMetrics()
    encoder = FakeEncoder(failure=RuntimeError("model unavailable"))
    service = EmbeddingService(repository, encoder, metrics=metrics)

    result = await service.process(post("Tin công nghệ và trí tuệ nhân tạo"))

    assert result.status == "fallback"
    assert repository.topic_updates == [("operational-post", ["ai", "tech"])]
    assert repository.features == []
    assert metrics.missing == 1
    assert metrics.failures == 1


@pytest.mark.asyncio
async def test_invalid_dimension_falls_back_without_storage() -> None:
    repository = FakeRepository()
    service = EmbeddingService(
        repository, FakeEncoder(dimension=7), metrics=FakeMetrics()
    )

    result = await service.process(post("Bài viết hợp lệ"))

    assert result.status == "fallback"
    assert repository.features == []


@pytest.mark.asyncio
async def test_future_source_timestamp_is_not_persisted() -> None:
    repository = FakeRepository()
    now = datetime(2026, 8, 31, tzinfo=UTC)
    service = EmbeddingService(
        repository,
        FakeEncoder(),
        metrics=FakeMetrics(),
        clock=lambda: now,
    )

    result = await service.process(post("Bài viết", updated_at=now + timedelta(seconds=1)))

    assert result.status == "fallback"
    assert repository.features == []
