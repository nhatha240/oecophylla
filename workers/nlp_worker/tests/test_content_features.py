import hashlib
import math

import pytest

from app.content_features import (
    CONTENT_HASH_VERSION,
    EMBEDDING_DIMENSION,
    ENCODER_ARTIFACT_SHA256,
    ENCODER_VERSION,
    content_hash,
    normalize_content,
    normalize_topics,
    validate_embedding,
)


def test_contract_constants_match_t4a() -> None:
    assert ENCODER_VERSION == (
        "intfloat/multilingual-e5-small@"
        "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    )
    assert ENCODER_ARTIFACT_SHA256 == (
        "1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477"
    )
    assert EMBEDDING_DIMENSION == 384


def test_normalization_is_deterministic_and_preserves_vietnamese() -> None:
    decomposed = "  To\u0302i\r\n\t yêu   Việt Nam  "
    normalized = normalize_content(decomposed)

    assert normalized == "Tôi yêu Việt Nam"
    assert normalize_content(normalized) == normalized

    expected = hashlib.sha256(
        f"{CONTENT_HASH_VERSION}\n{normalized}".encode("utf-8")
    ).hexdigest()
    assert content_hash(decomposed) == expected


def test_normalization_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_content("\r\n\t ")


def test_topics_are_normalized_deduplicated_and_utf8_sorted() -> None:
    assert normalize_topics(["  Thời\t sự ", "KINH TẾ", "kinh tế", "thời sự"]) == [
        "kinh tế",
        "thời sự",
    ]


def test_embedding_validation_rejects_wrong_dimension_nonfinite_and_nonunit() -> None:
    valid = [0.0] * EMBEDDING_DIMENSION
    valid[0] = 1.0
    assert validate_embedding(valid) == valid

    with pytest.raises(ValueError, match="384"):
        validate_embedding([1.0])

    nonfinite = valid.copy()
    nonfinite[1] = math.nan
    with pytest.raises(ValueError, match="finite"):
        validate_embedding(nonfinite)

    with pytest.raises(ValueError, match="L2-normalized"):
        validate_embedding([0.0] * EMBEDDING_DIMENSION)
