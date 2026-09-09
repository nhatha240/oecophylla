from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from aiokafka import AIOKafkaConsumer


def decode_json_value(value: bytes) -> Any:
    """Decode a UTF-8 Kafka value as JSON."""
    return json.loads(value.decode("utf-8"))


def build_json_consumer(
    *,
    topic: str,
    brokers: str,
    group_id: str,
    enable_auto_commit: bool,
) -> AIOKafkaConsumer:
    """Build a JSON Kafka consumer with the worker-wide offset defaults."""
    return AIOKafkaConsumer(
        topic,
        bootstrap_servers=brokers,
        group_id=group_id,
        enable_auto_commit=enable_auto_commit,
        auto_offset_reset="earliest",
        value_deserializer=decode_json_value,
    )


class MicroBatchBuffer:
    """Collect Kafka record values until size or latency triggers a flush.

    The class owns buffering policy only. Workers retain responsibility for
    processing, retries, and offset commits because those delivery guarantees
    differ by worker.
    """

    def __init__(
        self,
        *,
        batch_size: int,
        flush_interval_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if flush_interval_seconds <= 0:
            raise ValueError("flush_interval_seconds must be positive")
        self.batch_size = batch_size
        self.flush_interval_seconds = flush_interval_seconds
        self._clock = clock
        self._values: list[Any] = []
        self._last_flush = clock()

    def __bool__(self) -> bool:
        return bool(self._values)

    @property
    def values(self) -> list[Any]:
        return self._values

    @property
    def timeout_ms(self) -> int:
        return max(1, int(self.flush_interval_seconds * 1000))

    def extend_records(self, records: Mapping[object, Iterable[object]]) -> None:
        for partition_records in records.values():
            for record in partition_records:
                value = getattr(record, "value", None)
                if value is not None:
                    self._values.append(value)

    def extend_values(self, values: Iterable[Any]) -> None:
        self._values.extend(values)

    def replace(self, values: Iterable[Any]) -> None:
        self._values = list(values)

    def prepend(self, values: Iterable[Any]) -> None:
        self._values = [*values, *self._values]

    def ready(self) -> bool:
        return bool(self._values) and (
            len(self._values) >= self.batch_size
            or self._clock() - self._last_flush >= self.flush_interval_seconds
        )

    def drain(self) -> list[Any]:
        values = self._values
        self._values = []
        self.touch()
        return values

    def touch(self) -> None:
        self._last_flush = self._clock()
