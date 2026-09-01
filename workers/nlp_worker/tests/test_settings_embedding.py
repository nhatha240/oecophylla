import pytest
from pydantic import ValidationError

from app.content_features import ENCODER_ARTIFACT_SHA256, ENCODER_VERSION
from app.settings import Settings


def test_embedding_settings_are_pinned_to_t4a_contract() -> None:
    cfg = Settings()

    assert cfg.embedding_encoder_version == ENCODER_VERSION
    assert cfg.embedding_artifact_sha256 == ENCODER_ARTIFACT_SHA256
    assert cfg.embedding_device == "cpu"
    assert cfg.embedding_inference_enabled is False


def test_unknown_encoder_override_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(embedding_encoder_version="mutable/latest")
