import pytest
from app import main


@pytest.mark.asyncio
async def test_main_starts_metrics_and_exits_when_consumer_completes(monkeypatch) -> None:
    ports: list[int] = []

    async def completed_consumer(_cfg):
        return None

    monkeypatch.setattr(main, "start_http_server", ports.append)
    monkeypatch.setattr(main, "run_consumer", completed_consumer)

    await main.run()

    assert ports == [9109]
