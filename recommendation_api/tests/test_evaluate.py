from app.schemas import EvaluateResponse


def test_evaluate_response_shape():
    e = EvaluateResponse(
        precision_at_k=0.0,
        ctr_simulation=0.0,
        diversity=0.0,
        fallback_rate=0.0,
    )
    dump = e.model_dump()
    assert dump.keys() == {
        "precision_at_k",
        "ctr_simulation",
        "diversity",
        "fallback_rate",
    }
