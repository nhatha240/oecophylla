from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.embedding_worker import PostRecord, ProcessResult
from app.rebuild import BatchRebuilder, RebuildConfig


class FakeSource:
    def __init__(self, posts: list[PostRecord]) -> None:
        self.posts = posts
        self.seen_cursors: list[str | None] = []

    async def fetch_batch(self, cursor: str | None, limit: int):
        self.seen_cursors.append(cursor)
        start = int(cursor or "0")
        batch = self.posts[start : start + limit]
        next_cursor = str(start + len(batch)) if batch else None
        return batch, next_cursor


class FakeProcessor:
    def __init__(self, fail_once_for: str | None = None) -> None:
        self.fail_once_for = fail_once_for
        self.attempts: dict[str, int] = {}

    async def process(self, record: PostRecord) -> ProcessResult:
        self.attempts[record.post_id] = self.attempts.get(record.post_id, 0) + 1
        if record.post_id == self.fail_once_for and self.attempts[record.post_id] == 1:
            raise RuntimeError("transient")
        return ProcessResult(status="created")


class MemoryCheckpoint:
    def __init__(self, cursor: str | None = None) -> None:
        self.cursor = cursor
        self.saved: list[str] = []

    def load(self) -> str | None:
        return self.cursor

    def save(self, cursor: str) -> None:
        self.cursor = cursor
        self.saved.append(cursor)


def records(count: int) -> list[PostRecord]:
    timestamp = datetime(2026, 8, 31, tzinfo=UTC)
    return [PostRecord(str(index), f"Bài {index}", [], timestamp) for index in range(count)]


@pytest.mark.asyncio
async def test_rebuild_retries_reports_sanitized_progress_and_checkpoints() -> None:
    source = FakeSource(records(3))
    processor = FakeProcessor(fail_once_for="1")
    checkpoint = MemoryCheckpoint()
    progress: list[dict] = []
    runner = BatchRebuilder(
        source,
        processor,
        checkpoint,
        RebuildConfig(batch_size=2, max_retries=2, concurrency=1),
        progress.append,
    )

    result = await runner.run()

    assert result.processed == 3
    assert result.failed == 0
    assert processor.attempts["1"] == 2
    assert checkpoint.saved == ["2", "3"]
    assert all("post_id" not in event for event in progress)


@pytest.mark.asyncio
async def test_rebuild_resumes_from_checkpoint() -> None:
    source = FakeSource(records(4))
    checkpoint = MemoryCheckpoint("2")
    processor = FakeProcessor()
    runner = BatchRebuilder(
        source,
        processor,
        checkpoint,
        RebuildConfig(batch_size=2, max_retries=0, concurrency=1),
    )

    result = await runner.run()

    assert result.processed == 2
    assert source.seen_cursors[0] == "2"
    assert set(processor.attempts) == {"2", "3"}
