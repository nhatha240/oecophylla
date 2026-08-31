from __future__ import annotations

from .embedding_worker import EmbeddingService
from .content_features import ENCODER_VERSION
from .metrics import default_metrics
from .model import PinnedSentenceEncoder
from .repository import AsyncpgFeatureRepository
from .settings import Settings


class DisabledEncoder:
    version = ENCODER_VERSION

    def encode_passage(self, _normalized_text: str) -> list[float]:
        raise RuntimeError("embedding inference is disabled")


def build_service(connection, cfg: Settings):
    repository = AsyncpgFeatureRepository(connection)
    if cfg.embedding_inference_enabled:
        encoder = PinnedSentenceEncoder(
            cfg.embedding_model_dir,
            allow_download=cfg.embedding_allow_download,
            device=cfg.embedding_device,
            torch_threads=cfg.embedding_torch_threads,
        )
    else:
        encoder = DisabledEncoder()
    service = EmbeddingService(repository, encoder, metrics=default_metrics())
    return service, repository
