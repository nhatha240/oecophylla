"""Mini-batch attention-head fine-tuning over frozen multilingual embeddings.

Exports the existing NumPy serving ranker: PyTorch is a training dependency only.
Candidate negatives come exclusively from the same logged impression.
"""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .artifact import ARTIFACT_SCHEMA_VERSION, NRMS_MODEL_TYPE
from .evaluate import _ndcg_binary, _pairwise_auc
from .model import NRMSArchitecture, NRMSLikeRanker, _sinusoidal_positions
from .train import _dependency_versions, _write_artifact


def initialize_ranker(architecture, popular):
    ranker = NRMSLikeRanker.initialize(architecture, popular_embedding=popular)
    dimension = architecture.embedding_dimension
    heads = architecture.attention_heads
    width = architecture.head_dimension
    # Zero Q gives uniform attention initially; random K permits Q to learn.
    return replace(
        ranker,
        query_projection=np.zeros_like(ranker.query_projection),
        key_projection=ranker.key_projection * 0.1,
        value_projection=np.stack(
            [np.eye(dimension)[:, h * width : (h + 1) * width] for h in range(heads)]
        ),
    )


def history_batch(histories, *, dimension, device):
    length = max(1, max(map(len, histories)))
    values = np.zeros((len(histories), length, dimension), dtype=np.float32)
    mask = np.zeros((len(histories), length), dtype=bool)
    for index, history in enumerate(histories):
        values[index, : len(history)] = history
        mask[index, : len(history)] = True
    return torch.as_tensor(values, device=device), torch.as_tensor(mask, device=device)


class TorchNRMS(nn.Module):
    def __init__(self, ranker, *, freeze_values=False):
        super().__init__()
        self.original = ranker
        self.query = nn.Parameter(
            torch.tensor(ranker.query_projection, dtype=torch.float32)
        )
        self.key = nn.Parameter(
            torch.tensor(ranker.key_projection, dtype=torch.float32)
        )
        self.value = nn.Parameter(
            torch.tensor(ranker.value_projection, dtype=torch.float32),
            requires_grad=not freeze_values,
        )
        popular = ranker.popular_embedding
        if popular is None:
            popular = np.zeros(ranker.architecture.embedding_dimension)
        self.register_buffer("popular", torch.tensor(popular, dtype=torch.float32))

    def forward(self, history, mask):
        positions = torch.as_tensor(
            _sinusoidal_positions(history.shape[1], history.shape[2]),
            dtype=history.dtype,
            device=history.device,
        )
        positioned = history + self.original.architecture.position_scale * positions
        query = torch.einsum("bld,hdk->bhlk", positioned, self.query)
        key = torch.einsum("bld,hdk->bhlk", positioned, self.key)
        value = torch.einsum("bld,hdk->bhlk", positioned, self.value)
        scores = query @ key.transpose(-1, -2) / math.sqrt(query.shape[-1])
        # A finite sentinel makes all-empty rows safe before cold-start fallback.
        attention = scores.masked_fill(~mask[:, None, None, :], -1e9).softmax(dim=-1)
        context = (attention @ value).permute(0, 2, 1, 3).flatten(2)
        pooled = (context * mask[:, :, None]).sum(dim=1) / mask.sum(
            dim=1, keepdim=True
        ).clamp(min=1)
        semantic = (history * mask[:, :, None]).sum(dim=1) / mask.sum(
            dim=1, keepdim=True
        ).clamp(min=1)
        residual = self.original.architecture.semantic_residual
        pooled = (1 - residual) * pooled + residual * semantic
        return torch.where(mask.any(dim=1, keepdim=True), pooled, self.popular[None, :])

    def export(self):
        return replace(
            self.original,
            query_projection=self.query.detach().cpu().numpy().astype(float),
            key_projection=self.key.detach().cpu().numpy().astype(float),
            value_projection=self.value.detach().cpu().numpy().astype(float),
        )


def score_requests(ranker, requests, vectors):
    scores = []
    for row in requests:
        history = vectors[row["history"][-ranker.architecture.history_length :]]
        context = ranker.prepare_user_context(history_embeddings=history)
        scores.append(vectors[row["candidates"]] @ context.vector)
    return scores


def mean_pool_scores(requests, vectors, popular):
    scores = []
    for row in requests:
        user = vectors[row["history"]].mean(axis=0) if row["history"] else popular
        norm = np.linalg.norm(user)
        scores.append(vectors[row["candidates"]] @ user / max(float(norm), 1e-12))
    return scores


def request_metrics(labels, scores):
    labels = np.asarray(labels, dtype=int)
    scores = np.asarray(scores)
    if labels.shape != scores.shape or not np.isfinite(scores).all():
        raise ValueError("invalid prediction shape or non-finite scores")
    ranked = labels[np.argsort(-scores, kind="stable")].tolist()
    reciprocal = [1 / (i + 1) for i, label in enumerate(ranked) if label]
    return {
        "mrr": float(np.mean(reciprocal)) if reciprocal else 0.0,
        "first_click_mrr": reciprocal[0] if reciprocal else 0.0,
        "ndcg_at_5": _ndcg_binary(ranked, 5),
        "ndcg_at_10": _ndcg_binary(ranked, 10),
        "impression_auc": _pairwise_auc(
            list(zip(scores.tolist(), labels.tolist(), strict=True))
        ),
    }


def metrics(requests, scores, *, segments=True):
    if not requests or len(requests) != len(scores):
        raise ValueError("metrics require aligned nonempty requests and predictions")
    values = [
        request_metrics(row["labels"], s)
        for row, s in zip(requests, scores, strict=True)
    ]
    result = {
        key: float(np.mean([v[key] for v in values if v[key] is not None]))
        if any(v[key] is not None for v in values)
        else None
        for key in values[0]
    }
    result.update(
        requests=len(requests),
        candidates=sum(len(r["candidates"]) for r in requests),
        auc_eligible_requests=sum(v["impression_auc"] is not None for v in values),
    )
    catalog = {i for r in requests for i in r["candidates"]}
    selected = {
        r["candidates"][int(i)]
        for r, s in zip(requests, scores, strict=True)
        for i in np.argsort(-np.asarray(s), kind="stable")[:5]
    }
    result["coverage_at_5"] = len(selected) / len(catalog)
    if segments:
        result["segments"] = {}
        for name, predicate in (
            ("cold", lambda n: n == 0),
            ("history_1_2", lambda n: 1 <= n <= 2),
            ("history_3_plus", lambda n: n > 2),
        ):
            indices = [
                i for i, row in enumerate(requests) if predicate(len(row["history"]))
            ]
            if indices:
                result["segments"][name] = metrics(
                    [requests[i] for i in indices],
                    [scores[i] for i in indices],
                    segments=False,
                )
    return result


def _validate_splits(train, validation):
    if (
        not train
        or not validation
        or any(r["split"] != "train" for r in train)
        or any(r["split"] != "validation" for r in validation)
    ):
        raise ValueError("fit accepts only train and validation splits")
    identities = [r["request_group"] for r in train + validation]
    if len(identities) != len(set(identities)):
        raise ValueError("train and validation request groups must be disjoint")


def listwise_loss(logits, labels, mask):
    """Full logged slate CE with equal mass across its observed clicks."""
    if logits.shape != labels.shape or mask.shape != labels.shape:
        raise ValueError("listwise tensors must have aligned shapes")
    targets = labels * mask
    clicks = targets.sum(dim=1, keepdim=True)
    if (clicks <= 0).any():
        raise ValueError("listwise training rows need a click")
    log_probabilities = logits.masked_fill(~mask, -1e9).log_softmax(dim=1)
    return -(targets / clicks * log_probabilities).sum(dim=1).mean()


def fit(
    train,
    validation,
    vectors,
    *,
    learning_rates=(0.0001, 0.001),
    epochs=10,
    batch_size=32,
    seed=20260927,
    history_limit=20,
    position_scale=0.02,
    patience=3,
    freeze_values=False,
    semantic_residual=0.0,
    initial_ranker=None,
    objective="sampled_ce",
    negatives_per_positive=4,
    anchor_strength=0.0,
):
    _validate_splits(train, validation)
    if objective not in {"sampled_ce", "listwise_ce"}:
        raise ValueError("unknown training objective")
    if (
        negatives_per_positive < 1
        or not np.isfinite(anchor_strength)
        or anchor_strength < 0
    ):
        raise ValueError("invalid negatives or anchor strength")
    if freeze_values and position_scale != 0:
        raise ValueError("frozen semantic values require position_scale=0")
    if (
        epochs < 1
        or batch_size < 1
        or history_limit < 1
        or not learning_rates
        or any(not np.isfinite(x) or x <= 0 for x in learning_rates)
    ):
        raise ValueError("invalid training hyperparameters")
    if vectors.ndim != 2 or not np.isfinite(vectors).all():
        raise ValueError("invalid embeddings")
    torch.set_num_threads(2)
    torch.manual_seed(seed)
    positive_ids = [
        c
        for row in train
        for c, label in zip(row["candidates"], row["labels"], strict=True)
        if label
    ]
    examples = [
        (row, positive)
        for row in train
        if row["history"]
        for positive, label in zip(row["candidates"], row["labels"], strict=True)
        if label and 0 in row["labels"]
    ]
    if objective == "listwise_ce":
        examples = [
            (row, None)
            for row in train
            if row["history"] and 1 in row["labels"] and 0 in row["labels"]
        ]
    if not examples:
        raise ValueError("no warm-history positive/negative training pairs")
    popular = vectors[positive_ids].mean(axis=0)
    dimension = vectors.shape[1]
    architecture = NRMSArchitecture(
        dimension,
        2 if dimension % 2 == 0 else 1,
        history_limit,
        seed,
        position_scale,
        semantic_residual,
    )
    initial = initialize_ranker(architecture, popular)
    if initial_ranker is not None:
        if initial_ranker.architecture.embedding_dimension != dimension:
            raise ValueError("checkpoint embedding dimension mismatch")
        initial = replace(
            initial_ranker,
            architecture=replace(
                initial_ranker.architecture,
                history_length=history_limit,
                seed=seed,
                position_scale=position_scale,
                semantic_residual=semantic_residual,
            ),
            popular_embedding=popular,
        )
    best = initial
    initial_metrics = metrics(
        validation, score_requests(initial, validation, vectors), segments=False
    )
    best_score = initial_metrics["ndcg_at_10"]
    semantic_baseline = metrics(
        validation,
        mean_pool_scores(
            [{**row, "history": row["history"][-history_limit:]} for row in validation],
            vectors,
            popular,
        ),
        segments=False,
    )
    if freeze_values and semantic_baseline["ndcg_at_10"] > best_score:
        # The untrained semantic baseline is a first-class validation candidate.
        best = initialize_ranker(replace(architecture, position_scale=0.0), popular)
        best_score = semantic_baseline["ndcg_at_10"]
    selected = {
        "learning_rate": None,
        "epoch": 0,
        "validation_ndcg_at_10": best_score,
        "attention_finetuned": False,
        "checkpoint_retained": initial_ranker is not None and best is initial,
    }
    trials = []
    steps = 0
    for rate in learning_rates:
        rng = np.random.default_rng(seed)
        model = TorchNRMS(initial, freeze_values=freeze_values)
        anchor = model.value.detach().clone()
        optimizer = torch.optim.AdamW(model.parameters(), lr=rate, weight_decay=0.01)
        trial_best = -float("inf")
        stale = 0
        for epoch in range(1, epochs + 1):
            order = rng.permutation(len(examples))
            total_loss = 0.0
            for start in range(0, len(order), batch_size):
                batch = [examples[int(i)] for i in order[start : start + batch_size]]
                histories = [
                    vectors[row["history"][-history_limit:]] for row, _ in batch
                ]
                candidates, candidate_labels = [], []
                for row, positive in batch:
                    if objective == "listwise_ce":
                        candidates.append(row["candidates"])
                        candidate_labels.append(row["labels"])
                        continue
                    negatives = [
                        c
                        for c, label in zip(
                            row["candidates"], row["labels"], strict=True
                        )
                        if not label
                    ]
                    candidates.append(
                        [
                            positive,
                            *rng.choice(
                                negatives,
                                size=negatives_per_positive,
                                replace=len(negatives) < negatives_per_positive,
                            ).tolist(),
                        ]
                    )
                history, mask = history_batch(
                    histories, dimension=dimension, device="cpu"
                )
                width = max(map(len, candidates))
                indices = np.zeros((len(batch), width), dtype=int)
                candidate_mask = np.zeros(indices.shape, dtype=bool)
                labels = np.zeros(indices.shape, dtype=np.float32)
                for i, ids in enumerate(candidates):
                    indices[i, : len(ids)] = ids
                    candidate_mask[i, : len(ids)] = True
                    if candidate_labels:
                        labels[i, : len(ids)] = candidate_labels[i]
                candidate_vectors = torch.from_numpy(
                    np.asarray(vectors[indices], dtype=np.float32)
                )
                user = model(history, mask)
                logits = torch.einsum("bd,bcd->bc", user, candidate_vectors) * 10.0
                if objective == "listwise_ce":
                    loss = listwise_loss(
                        logits,
                        torch.from_numpy(labels),
                        torch.from_numpy(candidate_mask),
                    )
                else:
                    loss = nn.functional.cross_entropy(
                        logits, torch.zeros(len(batch), dtype=torch.long)
                    )
                if anchor_strength and not freeze_values:
                    loss = (
                        loss + anchor_strength * (model.value - anchor).square().mean()
                    )
                if not torch.isfinite(loss):
                    raise ValueError("non-finite training loss")
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                total_loss += float(loss.detach()) * len(batch)
                steps += 1
                if (start // batch_size + 1) % 500 == 0:
                    print(
                        json.dumps(
                            {
                                "stage": "training_progress",
                                "learning_rate": rate,
                                "epoch": epoch,
                                "examples_processed": start + len(batch),
                                "examples_total": len(examples),
                                "mean_loss": total_loss / (start + len(batch)),
                            }
                        ),
                        flush=True,
                    )
            ranker = model.export()
            validation_metric = metrics(
                validation, score_requests(ranker, validation, vectors), segments=False
            )
            score = validation_metric["ndcg_at_10"]
            entry = {
                "learning_rate": rate,
                "epoch": epoch,
                "loss": total_loss / len(examples),
                "validation": validation_metric,
            }
            trials.append(entry)
            print(json.dumps(dict(stage="epoch", **entry)), flush=True)
            if score > best_score:
                best, best_score = ranker, score
                selected = {
                    "learning_rate": rate,
                    "epoch": epoch,
                    "validation_ndcg_at_10": score,
                    "attention_finetuned": True,
                }
            if score > trial_best:
                trial_best, stale = score, 0
            else:
                stale += 1
            if stale >= patience:
                break
    # Positive temperature only: probability calibration must never reverse order.
    from scipy.optimize import minimize

    validation_scores = score_requests(best, validation, vectors)
    raw = np.concatenate(validation_scores)
    labels = np.concatenate([r["labels"] for r in validation])

    def calibration_objective(parameters):
        logits = raw * np.exp(parameters[0]) + parameters[1]
        return float(np.mean(np.logaddexp(0, logits) - labels * logits))

    optimum = minimize(
        calibration_objective,
        [0.0, -3.0],
        bounds=[(-6, 6), (-30, 30)],
        method="L-BFGS-B",
    )
    if not optimum.success or not np.isfinite(optimum.x).all():
        raise ValueError("validation calibration did not converge")
    best = best.with_calibration(
        scale=float(np.exp(optimum.x[0])), bias=float(optimum.x[1])
    )
    return best, {
        "selection_split": "validation",
        "selection_metric": "ndcg_at_10",
        "selected": selected,
        "trials": trials,
        "optimizer": "AdamW",
        "optimizer_steps": steps,
        "training_examples": len(examples),
        "negatives_per_positive": negatives_per_positive
        if objective == "sampled_ce"
        else None,
        "objective": objective,
        "anchor_strength": anchor_strength,
        "initial_checkpoint_validation": initial_metrics,
        "warm_start": initial_ranker is not None,
        "train_requests": len(train),
        "validation_requests": len(validation),
        "encoder_frozen": True,
        "calibration": "positive-temperature-sigmoid",
        "seed": seed,
        "batch_size": batch_size,
        "semantic_baseline_validation": semantic_baseline,
        "constraints": {
            "value_projection_frozen": freeze_values,
            "semantic_residual": semantic_residual,
            "position_scale": position_scale,
        },
    }


def export_artifact(
    ranker,
    output: Path,
    *,
    training_report,
    dataset_metadata,
    dataset_sha256,
    encoder_version,
):
    if output.exists():
        raise FileExistsError(f"artifact output already exists: {output}")
    architecture = ranker.architecture
    manifest = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "model_type": NRMS_MODEL_TYPE,
        "model_version": (
            f"{output.parent.name}-nrms" if output.name == "model" else output.name
        ),
        "dataset_schema_version": "recommendation-dataset-v2",
        "seed": architecture.seed,
        "architecture": {
            "embedding_dimension": architecture.embedding_dimension,
            "attention_heads": architecture.attention_heads,
            "history_length": architecture.history_length,
            "position_scale": architecture.position_scale,
            "semantic_residual": architecture.semantic_residual,
        },
        "embedding": {
            "version": encoder_version,
            "dimension": architecture.embedding_dimension,
        },
        "history": {"schema_version": "mind-pre-impression-history-v1"},
        "label_schema": {
            "training_target": "click_label",
            "label_definition_version": "mind-click-label-v1",
        },
        "training": training_report,
        "calibration": {
            "method": "positive-temperature-sigmoid",
            "scale": ranker.calibration_scale,
            "bias": ranker.calibration_bias,
        },
        "dependency_versions": dict(_dependency_versions(), torch=torch.__version__),
        "dataset": {
            "format": "mind-compact-v1",
            "sha256": dataset_sha256,
            "metadata": dataset_metadata,
        },
        "release": {
            "eligible": False,
            "status": "offline-benchmark-only",
            "reason": "requires Oecophylla social/Vietnamese holdout and operational gates",
        },
    }
    return _write_artifact(ranker, manifest, output)


def run_experiment(
    data, vectors, output, *, dataset_sha256, embedding_sha256, **kwargs
):
    from workers.nlp_worker.app.content_features import ENCODER_VERSION

    if (output / "model").exists() or (output / "report.json").exists():
        raise FileExistsError(
            "experiment already completed; choose a new output directory"
        )
    splits = {
        s: [r for r in data["requests"] if r["split"] == s]
        for s in ("train", "validation", "test")
    }
    ranker, training_report = fit(
        splits["train"],
        splits["validation"],
        vectors,
        history_limit=data["metadata"]["history_limit"],
        **kwargs,
    )
    # Only now read final holdout labels for reporting. They never enter fit().
    test = splits["test"]
    scores = {
        "logged_order": [-(np.arange(len(r["candidates"]), dtype=float)) for r in test],
        "mean_pool_semantic": mean_pool_scores(test, vectors, ranker.popular_embedding),
        "finetuned_nrms": score_requests(ranker, test, vectors),
    }
    result = {name: metrics(test, values) for name, values in scores.items()}
    deltas = np.array(
        [
            request_metrics(r["labels"], tuned)["ndcg_at_10"]
            - request_metrics(r["labels"], base)["ndcg_at_10"]
            for r, tuned, base in zip(
                test,
                scores["finetuned_nrms"],
                scores["mean_pool_semantic"],
                strict=True,
            )
        ]
    )
    rng = np.random.default_rng(kwargs["seed"])
    bootstrap = [
        rng.choice(deltas, size=len(deltas), replace=True).mean() for _ in range(1000)
    ]
    metadata = dict(data["metadata"], embedding_sha256=embedding_sha256)
    manifest = export_artifact(
        ranker,
        output / "model",
        training_report=training_report,
        dataset_metadata=metadata,
        dataset_sha256=dataset_sha256,
        encoder_version=ENCODER_VERSION,
    )
    report = {
        "schema": "mind-large-finetuning-report-v1",
        "dataset": metadata,
        "training": training_report,
        "holdout": result,
        "paired_ndcg_at_10_vs_mean_pool": {
            "delta": float(deltas.mean()),
            "ci95": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
        },
        "model_sha256": manifest["files"]["model.joblib"]["sha256"],
        "release": manifest["release"],
        "limitations": [
            "Sampled requests, not a full MINDlarge benchmark",
            "English news clicks, no friend graph or Vietnamese interactions",
            "Official unlabeled test not evaluated",
            "MRR averages reciprocal ranks of all clicked candidates; first_click_mrr is reported separately",
            "No publication timestamps or serving-policy validation",
        ],
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "stage": "complete",
                "holdout": result,
                "comparison": report["paired_ndcg_at_10_vs_mean_pool"],
                "artifact": str(output / "model"),
            }
        ),
        flush=True,
    )
    return report
