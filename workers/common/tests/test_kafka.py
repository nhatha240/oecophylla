from types import SimpleNamespace

from oecophylla_worker_common.kafka import (
    MicroBatchBuffer,
    build_json_consumer,
    decode_json_value,
)


def test_decode_json_value_accepts_utf8_envelopes() -> None:
    assert decode_json_value(b'{"event_type":"liked"}') == {
        "event_type": "liked"
    }


def test_build_json_consumer_centralizes_safe_defaults(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_consumer(topic: str, **kwargs: object) -> SimpleNamespace:
        captured["topic"] = topic
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        "oecophylla_worker_common.kafka.AIOKafkaConsumer", fake_consumer
    )

    build_json_consumer(
        topic="oecophylla.interactions",
        brokers="kafka:9092",
        group_id="worker.v1",
        enable_auto_commit=False,
    )

    assert captured["topic"] == "oecophylla.interactions"
    assert captured["bootstrap_servers"] == "kafka:9092"
    assert captured["group_id"] == "worker.v1"
    assert captured["auto_offset_reset"] == "earliest"
    assert captured["enable_auto_commit"] is False
    assert captured["value_deserializer"](b'{"data":{}}') == {"data": {}}


def test_micro_batch_buffer_drains_and_can_prepend_retries() -> None:
    now = [10.0]
    buffer = MicroBatchBuffer(
        batch_size=2,
        flush_interval_seconds=5.0,
        clock=lambda: now[0],
    )

    buffer.extend_records(
        {
            "partition-0": [
                SimpleNamespace(value={"event_id": "1"}),
                SimpleNamespace(value=None),
            ]
        }
    )
    assert buffer.ready() is False

    now[0] = 15.0
    assert buffer.ready() is True
    assert buffer.drain() == [{"event_id": "1"}]
    assert buffer.ready() is False

    buffer.extend_values([{"event_id": "3"}])
    buffer.prepend([{"event_id": "2"}])
    assert buffer.ready() is True
    assert buffer.drain() == [{"event_id": "2"}, {"event_id": "3"}]
