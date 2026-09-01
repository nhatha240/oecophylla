from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from .content_features import (
    ENCODER_ARTIFACT,
    ENCODER_ARTIFACT_SHA256,
    ENCODER_VERSION,
    MAX_TOKENS,
    MODEL_REPOSITORY,
    MODEL_REVISION,
    validate_embedding,
)

logger = logging.getLogger("nlp_worker.model")


class ModelUnavailableError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_artifact(model_dir: Path) -> Path:
    candidates = list(model_dir.rglob(ENCODER_ARTIFACT))
    if len(candidates) != 1:
        raise ModelUnavailableError("pinned model artifact is missing or ambiguous")
    artifact = candidates[0]
    if sha256_file(artifact) != ENCODER_ARTIFACT_SHA256:
        raise ModelUnavailableError("pinned model artifact checksum mismatch")
    return artifact


def download_pinned_model(target: Path) -> Path:
    """Download only the immutable T4A revision and verify its main artifact."""
    from huggingface_hub import snapshot_download

    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_REPOSITORY,
        revision=MODEL_REVISION,
        local_dir=target,
    )
    verify_model_artifact(target)
    return target


class PinnedSentenceEncoder:
    version = ENCODER_VERSION

    def __init__(
        self,
        model_dir: str,
        *,
        allow_download: bool = False,
        device: str = "cpu",
        torch_threads: int = 1,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.allow_download = allow_download
        self.device = device
        self.torch_threads = torch_threads
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            try:
                verify_model_artifact(self.model_dir)
            except ModelUnavailableError:
                if not self.allow_download:
                    raise
                download_pinned_model(self.model_dir)

            import torch
            from sentence_transformers import SentenceTransformer

            torch.set_num_threads(self.torch_threads)
            self._model = SentenceTransformer(
                str(self.model_dir),
                device=self.device,
                trust_remote_code=False,
            )
            self._model.max_seq_length = MAX_TOKENS
            logger.info("pinned multilingual embedding model loaded")
            return self._model
        except ModelUnavailableError:
            raise
        except Exception as exc:
            raise ModelUnavailableError("pinned embedding model could not be loaded") from exc

    def encode_passage(self, normalized_text: str) -> list[float]:
        try:
            encoded = self._load().encode(
                [f"passage: {normalized_text}"],
                batch_size=1,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )[0]
            return validate_embedding(encoded.tolist())
        except ModelUnavailableError:
            raise
        except Exception as exc:
            raise ModelUnavailableError("embedding inference failed") from exc
