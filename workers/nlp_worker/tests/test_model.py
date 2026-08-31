from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from app import model
from app.content_features import EMBEDDING_DIMENSION, ENCODER_ARTIFACT


def test_sha256_and_artifact_verification(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / ENCODER_ARTIFACT
    artifact.write_bytes(b"pinned bytes")
    expected = hashlib.sha256(b"pinned bytes").hexdigest()
    monkeypatch.setattr(model, "ENCODER_ARTIFACT_SHA256", expected)

    assert model.sha256_file(artifact) == expected
    assert model.verify_model_artifact(tmp_path) == artifact


def test_artifact_verification_rejects_missing_and_checksum_mismatch(tmp_path: Path) -> None:
    with pytest.raises(model.ModelUnavailableError, match="missing"):
        model.verify_model_artifact(tmp_path)

    (tmp_path / ENCODER_ARTIFACT).write_bytes(b"wrong")
    with pytest.raises(model.ModelUnavailableError, match="checksum"):
        model.verify_model_artifact(tmp_path)


def test_pinned_encoder_validates_encoded_output(monkeypatch) -> None:
    class FakeOutput:
        def tolist(self):
            vector = [0.0] * EMBEDDING_DIMENSION
            vector[0] = 1.0
            return vector

    class FakeModel:
        def encode(self, inputs, **kwargs):
            assert inputs == ["passage: Tin tức Việt Nam"]
            assert kwargs["normalize_embeddings"] is True
            return [FakeOutput()]

    encoder = model.PinnedSentenceEncoder("/missing")
    monkeypatch.setattr(encoder, "_load", lambda: FakeModel())

    assert encoder.encode_passage("Tin tức Việt Nam")[0] == 1.0


def test_pinned_encoder_wraps_inference_failure(monkeypatch) -> None:
    class BrokenModel:
        def encode(self, *_args, **_kwargs):
            raise RuntimeError("secret model detail")

    encoder = model.PinnedSentenceEncoder("/missing")
    monkeypatch.setattr(encoder, "_load", lambda: BrokenModel())

    with pytest.raises(model.ModelUnavailableError, match="inference failed"):
        encoder.encode_passage("Tin tức")
