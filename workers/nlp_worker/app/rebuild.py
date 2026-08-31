from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import asyncpg

from .embedding_worker import EmbeddingService, PostRecord, ProcessResult
from .runtime import build_service
from .settings import Settings

logger = logging.getLogger("nlp_worker.rebuild")


@dataclass(frozen=True)
class RebuildConfig:
    batch_size: int = 32
    max_retries: int = 3
    concurrency: int = 1
    retry_delay_seconds: float = 0.1


@dataclass(frozen=True)
class RebuildResult:
    processed: int
    created: int
    unchanged: int
    fallback: int
    failed: int


class PostSource(Protocol):
    async def fetch_batch(
        self, cursor: str | None, limit: int
    ) -> tuple[list[PostRecord], str | None]: ...


class Checkpoint(Protocol):
    def load(self) -> str | None: ...
    def save(self, cursor: str) -> None: ...


class JsonCheckpoint:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> str | None:
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text())["cursor"]

    def save(self, cursor: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"cursor": cursor}))
        os.chmod(temporary, 0o600)
        temporary.replace(self.path)


class BatchRebuilder:
    def __init__(
        self,
        source: PostSource,
        processor: EmbeddingService,
        checkpoint: Checkpoint,
        config: RebuildConfig,
        progress: Callable[[dict], None] | None = None,
    ) -> None:
        self.source = source
        self.processor = processor
        self.checkpoint = checkpoint
        self.config = config
        self.progress = progress or (lambda event: logger.info("rebuild progress %s", event))

    async def run(self) -> RebuildResult:
        cursor = self.checkpoint.load()
        counts = {"processed": 0, "created": 0, "unchanged": 0, "fallback": 0, "failed": 0}
        while True:
            posts, next_cursor = await self.source.fetch_batch(cursor, self.config.batch_size)
            if not posts:
                break
            semaphore = asyncio.Semaphore(self.config.concurrency)

            async def one(
                record: PostRecord, gate: asyncio.Semaphore = semaphore
            ) -> ProcessResult | None:
                async with gate:
                    for attempt in range(self.config.max_retries + 1):
                        try:
                            result = await self.processor.process(record)
                            if result.status != "fallback" or attempt >= self.config.max_retries:
                                return result
                        except Exception:  # noqa: BLE001 -- bounded retry boundary
                            if attempt >= self.config.max_retries:
                                return None
                        await asyncio.sleep(self.config.retry_delay_seconds * (2**attempt))
                return None

            results = await asyncio.gather(*(one(record) for record in posts))
            for result in results:
                counts["processed"] += 1
                if result is None:
                    counts["failed"] += 1
                else:
                    counts[result.status] += 1
            if next_cursor is None:
                break
            if all(result is not None for result in results):
                self.checkpoint.save(next_cursor)
            cursor = next_cursor
            set_lag = getattr(getattr(self.processor, "metrics", None), "set_rebuild_lag", None)
            if set_lag is not None:
                latest = max(record.updated_at for record in posts)
                if latest.tzinfo is None:
                    latest = latest.replace(tzinfo=UTC)
                set_lag((datetime.now(UTC) - latest).total_seconds())
            self.progress(dict(counts))
        return RebuildResult(**counts)


async def _run_cli(args: argparse.Namespace) -> int:
    cfg = Settings()
    connection = await asyncpg.connect(cfg.database_url)
    try:
        service, repository = build_service(connection, cfg)
        runner = BatchRebuilder(
            repository,
            service,
            JsonCheckpoint(Path(args.checkpoint)),
            RebuildConfig(
                batch_size=cfg.embedding_batch_size,
                max_retries=cfg.embedding_max_retries,
                concurrency=cfg.embedding_concurrency,
                retry_delay_seconds=cfg.embedding_retry_delay_seconds,
            ),
        )
        result = await runner.run()
        logger.info("rebuild complete %s", result)
        return 0 if result.failed == 0 else 1
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume-safe multilingual embedding rebuild")
    parser.add_argument("--checkpoint", default="/var/lib/oecophylla/nlp-rebuild.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(_run_cli(args)))


if __name__ == "__main__":
    main()
