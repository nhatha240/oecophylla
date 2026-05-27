from __future__ import annotations

import asyncio
import logging
import signal

from .settings import Settings
from .kafka_consumer import run_consumer

logger = logging.getLogger("nlp_worker")


async def run() -> None:
    cfg = Settings()
    logger.info(
        "nlp-worker starting; brokers=%s topic=%s group=%s",
        cfg.kafka_brokers,
        cfg.content_created_topic,
        cfg.consumer_group,
    )
    stop = asyncio.Event()

    def _stop(*_: object) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _stop)

    consumer_task = asyncio.create_task(run_consumer(cfg))
    await stop.wait()
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    logger.info("nlp-worker stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":
    main()
