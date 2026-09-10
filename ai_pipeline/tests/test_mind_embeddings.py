from copy import deepcopy
from pathlib import Path

import pytest
from ai_pipeline.mind_adapter import adapt_mind
from ai_pipeline.train import _validate_v2_contract, DatasetValidationError


def test_mind_embeddings_preserve_order_and_never_invent_event_times():
    from ai_pipeline.mind_embeddings import materialize_records

    fixture = Path(__file__).parent / "fixtures/mind_v2"
    result = adapt_mind(
        fixture / "news.tsv", fixture / "behaviors.tsv", hash_salt="test"
    )
    rows = [row.to_record() for row in result.rows]
    calls = []

    def encoder(texts):
        calls.extend(texts)
        return [[1.0, 0.0] for text in texts]

    output = materialize_records(
        rows, encoder=encoder, encoder_version="fixture@1", dimension=2
    )
    _validate_v2_contract(
        output, history_schema_version="mind-pre-impression-history-v1"
    )
    assert len(calls) == len(set(calls))
    for original, updated in zip(rows, output):
        assert original["split"] == updated["split"]
        assert original["request_group"] == updated["request_group"]
        assert all(e["engaged_at"] is None for e in updated["history"])
        assert [e["ordinal"] for e in original["history"]] == [
            e["ordinal"] for e in updated["history"]
        ]
        assert updated["article"]["title"] is None
        assert updated["article"]["published_at"] is None
        assert updated["language"] == "en"
    bad = deepcopy(output)
    next(r for r in bad if r["history"])["history"][0]["provenance"] = (
        "oecophylla-click-v2"
    )
    with pytest.raises(DatasetValidationError):
        _validate_v2_contract(
            bad, history_schema_version="mind-pre-impression-history-v1"
        )
    with pytest.raises(DatasetValidationError):
        _validate_v2_contract(output)
