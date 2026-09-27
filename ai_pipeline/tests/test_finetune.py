from __future__ import annotations

import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ai_pipeline import finetune
from ai_pipeline.artifact import ArtifactIntegrityError, load_artifact
from ai_pipeline.model import NRMSArchitecture, NRMSLikeRanker


@pytest.mark.parametrize("scale", [0.0, 0.02, 1.0])
def test_batched_training_encoder_matches_numpy_serving_for_padding(scale):
    architecture = NRMSArchitecture(
        embedding_dimension=8,
        attention_heads=2,
        history_length=4,
        seed=7,
        position_scale=scale,
    )
    original = NRMSLikeRanker.initialize(
        architecture, popular_embedding=np.ones(8) / np.sqrt(8)
    )
    model = finetune.TorchNRMS(original)
    histories = [np.eye(8)[:3], np.eye(8)[2:3], np.empty((0, 8))]
    batch, mask = finetune.history_batch(histories, dimension=8, device="cpu")
    actual = model(batch, mask).detach().numpy()
    for i, history in enumerate(histories):
        expected = original.prepare_user_context(history_embeddings=history).vector
        np.testing.assert_allclose(actual[i], expected, atol=1e-6)
    exported = model.export()
    np.testing.assert_allclose(
        exported.encode_history(histories[0]), actual[0], atol=1e-6
    )


def test_semantic_initialization_preserves_mean_pool_space():
    architecture = NRMSArchitecture(
        embedding_dimension=8,
        attention_heads=2,
        history_length=4,
        seed=7,
        position_scale=0.0,
    )
    model = finetune.initialize_ranker(architecture, np.ones(8))
    history = np.eye(8)[:3]
    np.testing.assert_allclose(
        model.encode_history(history), history.mean(axis=0), atol=1e-7
    )


def toy_requests(split, count=8):
    return [
        {
            "split": split,
            "request_group": f"{split}-{i}",
            "served_at": "2019-11-10T00:00:00+00:00",
            "history": [0, 0],
            "candidates": [1, 2],
            "labels": [1, 0],
        }
        for i in range(count)
    ]


def test_finetune_selects_on_validation_and_exports_loadable_artifact(tmp_path):
    torch.set_num_threads(1)
    vectors = np.eye(8, dtype=np.float32)
    training, validation = toy_requests("train"), toy_requests("validation")
    ranker, report = finetune.fit(
        training,
        validation,
        vectors,
        learning_rates=[0.01],
        epochs=4,
        batch_size=4,
        seed=7,
        history_limit=4,
        position_scale=0.02,
    )
    assert report["selection_split"] == "validation"
    assert report["optimizer_steps"] > 0
    assert ranker.raw_score(
        ranker.encode_history(vectors[[0, 0]]), vectors[1]
    ) > ranker.raw_score(ranker.encode_history(vectors[[0, 0]]), vectors[2])
    output = tmp_path / "artifact"
    finetune.export_artifact(
        ranker,
        output,
        training_report=report,
        dataset_metadata={"fixture": True},
        dataset_sha256="a" * 64,
        encoder_version="fixture-v1",
    )
    loaded = load_artifact(output)
    assert loaded.ranker.architecture.position_scale == 0.02
    manifest = json.loads((output / "manifest.json").read_text())
    manifest["architecture"]["position_scale"] = 1.0
    (output / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ArtifactIntegrityError, match="architecture"):
        load_artifact(output)


def test_finetune_refuses_holdout_or_duplicate_requests_in_selection():
    with pytest.raises(ValueError, match="split"):
        finetune.fit(toy_requests("train"), toy_requests("test"), np.eye(8), epochs=1)
    validation = toy_requests("validation")
    validation[0]["request_group"] = "train-0"
    with pytest.raises(ValueError, match="disjoint"):
        finetune.fit(toy_requests("train"), validation, np.eye(8), epochs=1)


def test_metrics_include_mind_mrr_and_cold_start_segments():
    requests = [{"history": [], "candidates": [0, 1, 2], "labels": [1, 0, 1]}]
    report = finetune.metrics(requests, [np.array([3.0, 2.0, 1.0])])
    assert report["mrr"] == pytest.approx((1 + 1 / 3) / 2)
    assert report["first_click_mrr"] == 1
    assert report["impression_auc"] == 0.5
    assert report["segments"]["cold"]["requests"] == 1
