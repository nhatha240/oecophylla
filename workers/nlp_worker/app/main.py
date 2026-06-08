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
    stop_task = asyncio.create_task(stop.wait())

    # Wait for either a shutdown signal OR the consumer exiting on its own. The
    # latter means an unrecoverable error — surface it so the process exits
    # non-zero and the container's restart policy can recover, rather than
    # idling forever with a dead consumer (silent failure).
    done, pending = await asyncio.wait(
        {consumer_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
    )

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    if consumer_task in done:
        exc = consumer_task.exception()
        if exc is not None:
            logger.error("nlp-worker consumer crashed: %s", exc, exc_info=exc)
            raise exc

    logger.info("nlp-worker stopped")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":
    main()
