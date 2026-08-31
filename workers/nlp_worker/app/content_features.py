from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections.abc import Sequence

SCHEMA_VERSION = "post-content-features-v1"
CONTENT_HASH_VERSION = "post-content-normalization-v1"
MODEL_REPOSITORY = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
ENCODER_VERSION = f"{MODEL_REPOSITORY}@{MODEL_REVISION}"
ENCODER_ARTIFACT = "model.safetensors"
ENCODER_ARTIFACT_SHA256 = (
    "1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477"
)
EMBEDDING_DIMENSION = 384
MODEL_LICENSE = "MIT"
MAX_TOKENS = 512

_WHITESPACE = re.compile(r"\s+", flags=re.UNICODE)


def normalize_content(value: str) -> str:
    """Apply the exact post-content-normalization-v1 transformation."""
    if not isinstance(value, str):
        raise TypeError("content must be Unicode text")
    normalized = unicodedata.normalize("NFC", value)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    if not normalized:
        raise ValueError("normalized content is empty")
    return normalized


def content_hash(value: str) -> str:
    normalized = normalize_content(value)
    material = f"{CONTENT_HASH_VERSION}\n{normalized}".encode()
    return hashlib.sha256(material).hexdigest()


def normalize_topics(values: Sequence[str]) -> list[str]:
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise TypeError("topic labels must be Unicode text")
        label = _WHITESPACE.sub(
            " ", unicodedata.normalize("NFC", value)
        ).strip().lower()
        if not label:
            continue
        if len(label) > 64:
            raise ValueError("topic label exceeds 64 Unicode characters")
        normalized.add(label)
    if len(normalized) > 32:
        raise ValueError("at most 32 normalized topic labels are allowed")
    return sorted(normalized, key=lambda label: label.encode("utf-8"))


def validate_embedding(values: Sequence[float]) -> list[float]:
    if len(values) != EMBEDDING_DIMENSION:
        raise ValueError(f"embedding must contain exactly {EMBEDDING_DIMENSION} values")
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise ValueError("embedding values must be finite")
    norm = math.sqrt(sum(value * value for value in result))
    if abs(norm - 1.0) > 0.001:
        raise ValueError("embedding must be L2-normalized")
    return result
