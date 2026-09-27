import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ai_pipeline.artifact import ArtifactIntegrityError, load_artifact
from ai_pipeline.finetune import (
    TorchNRMS,
    export_artifact,
    fit,
    history_batch,
    initialize_ranker,
)
from ai_pipeline.model import NRMSArchitecture, NRMSLikeRanker


def test_residual_encoder_and_backward_match_torch_serving_contract():
    architecture = NRMSArchitecture(
        8, 2, 4, 7, position_scale=0.02, semantic_residual=0.5
    )
    ranker = NRMSLikeRanker.initialize(architecture)
    history = np.eye(8)[:3]
    batch, mask = history_batch([history], dimension=8, device="cpu")
    model = TorchNRMS(ranker)
    output = model(batch, mask)
    gradient = np.arange(8, dtype=float) / 8
    (output * torch.tensor(gradient, dtype=torch.float32)).sum().backward()
    expected, cache = ranker._forward_history(history)
    np.testing.assert_allclose(output.detach().numpy()[0], expected, atol=1e-6)
    for actual, wanted in zip(
        ranker._backward_history(cache, gradient),
        [model.query.grad, model.key.grad, model.value.grad],
        strict=True,
    ):
        np.testing.assert_allclose(actual, wanted.numpy(), atol=1e-6)


def test_full_semantic_residual_preserves_mean_pool_even_with_rotated_projections():
    architecture = NRMSArchitecture(8, 2, 4, 7, semantic_residual=1.0)
    ranker = NRMSLikeRanker.initialize(architecture)
    history = np.eye(8)[:3]
    np.testing.assert_allclose(ranker.encode_history(history), history.mean(axis=0))


@pytest.mark.parametrize("residual", [-0.1, 1.1, float("nan")])
def test_invalid_semantic_residual_is_rejected(residual):
    with pytest.raises(ValueError, match="semantic_residual"):
        NRMSArchitecture(8, 2, 4, 7, semantic_residual=residual)


def test_frozen_values_do_not_receive_updates_and_single_history_keeps_meaning():
    architecture = NRMSArchitecture(8, 2, 4, 7, position_scale=0, semantic_residual=0.5)
    ranker = initialize_ranker(architecture, np.ones(8))
    model = TorchNRMS(ranker, freeze_values=True)
    batch, mask = history_batch([np.eye(8)[:3]], dimension=8, device="cpu")
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.1)
    model(batch, mask)[0, 0].backward()
    assert model.value.grad is None
    optimizer.step()
    exported = model.export()
    np.testing.assert_array_equal(exported.value_projection, ranker.value_projection)
    np.testing.assert_allclose(
        exported.encode_history(np.eye(8)[2:3]), np.eye(8)[2], atol=1e-7
    )


def test_semantic_tuning_considers_untrained_baseline_and_records_constraints(tmp_path):
    rows = lambda split: [
        {
            "split": split,
            "request_group": f"{split}-{i}",
            "served_at": "2019-11-10T00:00:00+00:00"
            if split == "train"
            else "2019-11-11T00:00:00+00:00",
            "history": [0, 1],
            "candidates": [0, 2],
            "labels": [1, 0],
        }
        for i in range(8)
    ]
    ranker, report = fit(
        rows("train"),
        rows("validation"),
        np.eye(8, dtype=np.float32),
        epochs=1,
        learning_rates=[0.01],
        freeze_values=True,
        semantic_residual=0.5,
        position_scale=0,
    )
    assert report["constraints"]["value_projection_frozen"] is True
    assert (
        report["selected"]["validation_ndcg_at_10"]
        >= report["semantic_baseline_validation"]["ndcg_at_10"]
    )
    export_artifact(
        ranker,
        tmp_path / "model",
        training_report=report,
        dataset_metadata={},
        dataset_sha256="a" * 64,
        encoder_version="fixture",
    )
    manifest_path = tmp_path / "model" / "manifest.json"
    loaded = load_artifact(tmp_path / "model")
    assert (
        loaded.ranker.architecture.semantic_residual
        == ranker.architecture.semantic_residual
    )
    manifest = json.loads(manifest_path.read_text())
    manifest["architecture"]["semantic_residual"] = 0.9
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ArtifactIntegrityError, match="architecture"):
        load_artifact(tmp_path / "model")


def test_semantic_constraints_reject_position_noise():
    with pytest.raises(ValueError, match="position_scale"):
        fit(
            [{"split": "train", "request_group": "a"}],
            [{"split": "validation", "request_group": "b"}],
            np.eye(8),
            freeze_values=True,
            position_scale=1,
        )
