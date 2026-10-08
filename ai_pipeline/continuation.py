"""Validation-only continuation search followed by one sealed MIND benchmark."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from workers.nlp_worker.app.content_features import EMBEDDING_DIMENSION, ENCODER_VERSION

from .artifact import LoadedNRMSArtifact, load_artifact, sha256_file
from .benchmark import evaluate_models, paired_comparison
from .benchmark import main as benchmark_main
from .benchmark_data import merge_embeddings, store_identity_salt
from .finetune import export_artifact, fit, metrics, score_requests
from .mind_large import cached_embeddings, prepare_dataset

CONFIGS = {
    "attention20": {
        "history_limit": 20,
        "freeze_values": True,
        "objective": "sampled_ce",
        "negatives_per_positive": 8,
        "anchor_strength": 0.0,
        "learning_rates": [0.0003, 0.001],
    },
    "attention50": {
        "history_limit": 50,
        "freeze_values": True,
        "objective": "sampled_ce",
        "negatives_per_positive": 8,
        "anchor_strength": 0.0,
        "learning_rates": [0.0003, 0.001],
    },
    "value20": {
        "history_limit": 20,
        "freeze_values": False,
        "objective": "listwise_ce",
        "anchor_strength": 1.0,
        "learning_rates": [0.00003, 0.0001],
    },
    "value50": {
        "history_limit": 50,
        "freeze_values": False,
        "objective": "listwise_ce",
        "anchor_strength": 1.0,
        "learning_rates": [0.00003, 0.0001],
    },
}


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def preserve_validation_boundary(data, reference):
    cutoff = reference["metadata"]["validation_cutoff"]
    for row in data["requests"]:
        if row["split"] != "test":
            row["split"] = "train" if row["served_at"] < cutoff else "validation"
    old_train = {
        row["request_group"] for row in reference["requests"] if row["split"] == "train"
    }
    validation = {
        row["request_group"] for row in data["requests"] if row["split"] == "validation"
    }
    if old_train & validation:
        raise ValueError("parent training requests overlap new validation")
    data["metadata"]["validation_cutoff"] = cutoff
    data["metadata"]["split_counts"] = {
        split: sum(row["split"] == split for row in data["requests"])
        for split in ("train", "validation", "test")
    }
    if not all(data["metadata"]["split_counts"].values()):
        raise ValueError("continuation requires nonempty chronological splits")


def select_winner(candidates):
    if not candidates or any(
        not np.isfinite(row["validation_ndcg_at_10"]) for row in candidates
    ):
        raise ValueError("finite validation candidates are required")
    # Input order is registered in advance, with the parent first for tied scores.
    return max(candidates, key=lambda row: row["validation_ndcg_at_10"])


def checked_inputs(directory):
    protocol = read(directory / "search-protocol.json")
    artifact = load_artifact(Path(protocol["parent_artifact"]))
    checks = {
        "parent_model_sha256": sha256_file(
            Path(protocol["parent_artifact"]) / "model.joblib"
        ),
        "parent_manifest_sha256": sha256_file(
            Path(protocol["parent_artifact"]) / "manifest.json"
        ),
        "dataset_sha256": sha256_file(directory / "dataset.json"),
    }
    if any(protocol[key] != value for key, value in checks.items()):
        raise ValueError("registered continuation inputs changed")
    return protocol, artifact, read(directory / "dataset.json")


def encode_data(directory, protocol, data, *, model_dir, device):
    reference_dir = Path(protocol["reference_dir"])
    reference = read(reference_dir / "dataset.json")
    ref_vectors = cached_embeddings(
        reference["articles"],
        reference_dir / "embeddings.npz",
        encode=lambda _: None,
        encoder_version=ENCODER_VERSION,
        dimension=EMBEDDING_DIMENSION,
    )
    target = directory / "embeddings.npz"
    if target.exists():
        return cached_embeddings(
            data["articles"],
            target,
            encode=lambda _: None,
            encoder_version=ENCODER_VERSION,
            dimension=EMBEDDING_DIMENSION,
        )

    def encode(texts):
        if model_dir is None:
            raise ValueError("--model-dir required for new article embeddings")
        from workers.nlp_worker.app.model import PinnedSentenceEncoder

        print(
            json.dumps({"stage": "encode_missing", "articles": len(texts)}), flush=True
        )
        encoder = PinnedSentenceEncoder(str(model_dir), device=device, torch_threads=2)
        return encoder._load().encode(
            ["passage: " + text for text in texts],
            batch_size=32,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        )

    vectors, audit = merge_embeddings(
        data["articles"], reference["articles"], ref_vectors, encode=encode
    )
    cached_embeddings(
        data["articles"],
        target,
        encode=lambda _: vectors,
        encoder_version=ENCODER_VERSION,
        dimension=EMBEDDING_DIMENSION,
    )
    audit.update(embeddings_sha256=sha256_file(target), encoder_version=ENCODER_VERSION)
    write(directory / "embedding-audit.json", audit)
    protocol["embeddings_sha256"] = sha256_file(target)
    protocol["ready_for_training_at"] = datetime.now(timezone.utc).isoformat()
    write(directory / "search-protocol.json", protocol)
    print(json.dumps({"stage": "encoded", **audit}), flush=True)
    return vectors


def train_candidates(directory, protocol, parent, data, vectors, trial=None):
    train = [row for row in data["requests"] if row["split"] == "train"]
    validation = [row for row in data["requests"] if row["split"] == "validation"]
    for name, config in protocol["configs"].items():
        if trial and trial != name:
            continue
        output = directory / "trials" / name
        if (output / "training.json").exists():
            load_artifact(output / "model")
            continue
        output.mkdir(parents=True, exist_ok=True)
        print(
            json.dumps({"stage": "train_candidate", "name": name, "config": config}),
            flush=True,
        )
        ranker, training = fit(
            train,
            validation,
            vectors,
            initial_ranker=parent.ranker,
            epochs=protocol["epochs"],
            patience=protocol["patience"],
            batch_size=protocol["batch_size"]
            if config["objective"] == "sampled_ce"
            else min(32, protocol["batch_size"]),
            seed=protocol["seed"],
            position_scale=0.0,
            semantic_residual=0.5,
            **config,
        )
        training.update(
            parent_model_sha256=protocol["parent_model_sha256"],
            configuration=name,
            training_window_end=max(row["served_at"] for row in train),
        )
        manifest = export_artifact(
            ranker,
            output / "model",
            training_report=training,
            dataset_metadata={
                **data["metadata"],
                "embedding_sha256": protocol["embeddings_sha256"],
            },
            dataset_sha256=protocol["dataset_sha256"],
            encoder_version=ENCODER_VERSION,
        )
        write(
            output / "training.json",
            {
                "name": name,
                "validation_ndcg_at_10": training["selected"]["validation_ndcg_at_10"],
                "training": training,
                "model_sha256": manifest["files"]["model.joblib"]["sha256"],
            },
        )
    if trial and trial not in protocol["configs"]:
        raise ValueError("trial was not registered")


def freeze_winner(directory, protocol, parent, data, vectors):
    if (directory / "selection.json").exists():
        raise FileExistsError("winner is already frozen")
    validation = [row for row in data["requests"] if row["split"] == "validation"]
    parent_metrics = metrics(
        validation, score_requests(parent.ranker, validation, vectors)
    )
    candidates = [
        {
            "name": "parent_r2",
            "validation_ndcg_at_10": parent_metrics["ndcg_at_10"],
            "validation": parent_metrics,
        }
    ]
    for name in protocol["configs"]:
        entry = read(directory / "trials" / name / "training.json")
        artifact = load_artifact(directory / "trials" / name / "model")
        if (
            entry["model_sha256"]
            != artifact.manifest["files"]["model.joblib"]["sha256"]
        ):
            raise ValueError("trial report/model mismatch")
        candidates.append(entry)
    winner = select_winner(candidates)
    if winner["name"] == "parent_r2":
        export_artifact(
            parent.ranker,
            directory / "model",
            training_report={
                "selection_split": "validation",
                "attention_finetuned": False,
                "parent_retained": True,
                "parent_model_sha256": protocol["parent_model_sha256"],
            },
            dataset_metadata={
                **data["metadata"],
                "embedding_sha256": protocol["embeddings_sha256"],
            },
            dataset_sha256=protocol["dataset_sha256"],
            encoder_version=ENCODER_VERSION,
        )
    else:
        shutil.copytree(
            directory / "trials" / winner["name"] / "model", directory / "model"
        )
    # Copied manifests retain their actual selected candidate's version and provenance.
    frozen = load_artifact(directory / "model")
    selection = {
        "selected": winner["name"],
        "validation_ndcg_at_10": winner["validation_ndcg_at_10"],
        "parent_validation_ndcg_at_10": parent_metrics["ndcg_at_10"],
        "candidates": [
            {"name": row["name"], "validation_ndcg_at_10": row["validation_ndcg_at_10"]}
            for row in candidates
        ],
        "selection_split": "validation",
        "holdout_labels_used": False,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "model_sha256": frozen.manifest["files"]["model.joblib"]["sha256"],
    }
    write(directory / "selection.json", selection)
    print(json.dumps({"stage": "winner_frozen", **selection}), flush=True)


def benchmark_winner(directory, protocol, parent, data, vectors):
    selection = read(directory / "selection.json")
    artifact = load_artifact(directory / "model")
    if (
        selection["model_sha256"]
        != artifact.manifest["files"]["model.joblib"]["sha256"]
    ):
        raise ValueError("selected model changed before benchmark")
    benchmark = directory / "benchmark"
    if benchmark.exists():
        raise FileExistsError("sealed benchmark already opened")
    benchmark.mkdir()
    cap = artifact.ranker.architecture.history_length
    requests = [
        {**row, "history": row["history"][-cap:]}
        for row in data["requests"]
        if row["split"] == "test"
    ]
    needed = sorted(
        {index for row in requests for index in row["history"] + row["candidates"]}
    )
    index_map = {index: offset for offset, index in enumerate(needed)}
    for row in requests:
        row["history"] = [index_map[index] for index in row["history"]]
        row["candidates"] = [index_map[index] for index in row["candidates"]]
    articles = [data["articles"][index] for index in needed]
    bench_vectors = vectors[needed]
    metadata = {
        **data["metadata"],
        "format": "mind-compact-benchmark-v1",
        "history_limit": cap,
        "excluded_requests": data["metadata"]["excluded_test_requests"],
        "training_window_end": max(
            row["served_at"] for row in data["requests"] if row["split"] != "test"
        ),
    }
    dataset_path = benchmark / "dataset.json"
    write(
        dataset_path, {"articles": articles, "requests": requests, "metadata": metadata}
    )
    store_identity_salt(benchmark, (directory / "identity-salt").read_text().strip())
    cached_embeddings(
        articles,
        benchmark / "embeddings.npz",
        encode=lambda _: bench_vectors,
        encoder_version=ENCODER_VERSION,
        dimension=EMBEDDING_DIMENSION,
    )
    write(
        benchmark / "embedding-audit.json",
        {
            "encoder_version": ENCODER_VERSION,
            "embeddings_sha256": sha256_file(benchmark / "embeddings.npz"),
            "reused_articles": len(articles),
            "encoded_articles": 0,
        },
    )
    write(
        benchmark / "protocol.json",
        {
            "schema": "recommendation-benchmark-protocol-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "artifact": str((directory / "model").resolve()),
            "model_version": artifact.manifest["model_version"],
            "model_sha256": sha256_file(directory / "model/model.joblib"),
            "manifest_sha256": sha256_file(directory / "model/manifest.json"),
            "dataset_sha256": sha256_file(dataset_path),
            "excluded_datasets": protocol["excluded_datasets"],
            "seed": protocol["seed"],
            "requests": len(requests),
            "bootstrap_resamples": 1000,
            "primary_metric": "ndcg_at_10",
            "primary_baseline": "semantic_mean_pool",
            "confidence_level": 0.95,
            "absolute_target": protocol["absolute_target"],
            "search_protocol_sha256": sha256_file(directory / "search-protocol.json"),
            "selection_sha256": sha256_file(directory / "selection.json"),
            "scope": "fresh sampled MINDlarge dev; validation-only model selection",
        },
    )
    benchmark_main(["--run-dir", str(benchmark)])
    report = read(benchmark / "report.json")
    scores = score_requests(parent.ranker, requests, bench_vectors)
    parent_models, individual = evaluate_models(
        requests, {"parent_r2": scores}, bench_vectors
    )
    tuned_scores = score_requests(artifact.ranker, requests, bench_vectors)
    _, tuned_individual = evaluate_models(
        requests, {"nrms": tuned_scores}, bench_vectors
    )
    comparison = paired_comparison(
        requests,
        tuned_individual["nrms"],
        individual["parent_r2"],
        seed=protocol["seed"],
        resamples=1000,
    )
    comparison["baseline"] = "parent_r2"
    result = {
        "target": protocol["absolute_target"],
        "achieved": report["models"]["nrms"]["ndcg_at_10"]
        > protocol["absolute_target"],
        "ndcg_at_10": report["models"]["nrms"]["ndcg_at_10"],
        "selected": selection["selected"],
        "parent": parent_models["parent_r2"],
        "comparison_to_parent": comparison,
        "model_sha256": selection["model_sha256"],
        "production_release": "inconclusive",
    }
    write(directory / "target-result.json", result)
    print(json.dumps({"stage": "target_result", **result}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        choices=("prepare", "encode", "train", "select", "benchmark"),
        required=True,
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data _train "))
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=Path("artifacts/models/mind-large-20260927-r2"),
    )
    parser.add_argument("--exclude-dataset", type=Path, action="append", default=[])
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--train-requests", type=int, default=200000)
    parser.add_argument("--holdout-requests", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20261003)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument(
        "--configs", nargs="+", choices=tuple(CONFIGS), default=list(CONFIGS)
    )
    parser.add_argument("--trial", choices=tuple(CONFIGS))
    args = parser.parse_args(argv)
    directory = args.run_dir
    if args.stage == "prepare":
        directory.mkdir(parents=True, exist_ok=True)
        if (directory / "search-protocol.json").exists() or (
            directory / "dataset.json"
        ).exists():
            raise FileExistsError("continuation already prepared")
        reference_path = args.reference_dir / "dataset.json"
        reference = read(reference_path)
        parent_path = args.reference_dir / "model"
        parent = load_artifact(parent_path)
        if not isinstance(parent, LoadedNRMSArtifact) or parent.manifest[
            "embedding"
        ] != {"version": ENCODER_VERSION, "dimension": EMBEDDING_DIMENSION}:
            raise ValueError("pinned multilingual NRMS parent is required")
        if (
            sha256_file(reference_path) != parent.manifest["dataset"]["sha256"]
            or sha256_file(args.reference_dir / "embeddings.npz")
            != parent.manifest["dataset"]["metadata"]["embedding_sha256"]
        ):
            raise ValueError("parent dataset/embeddings checksum mismatch")
        salt = (args.reference_dir / "identity-salt").read_text().strip()
        paths = list(
            dict.fromkeys(
                [
                    reference_path.resolve(),
                    *[path.resolve() for path in args.exclude_dataset],
                ]
            )
        )
        excluded, prior = set(), []
        for path in paths:
            if (path.parent / "identity-salt").read_text().strip() != salt:
                raise ValueError("holdouts must share identity salt")
            excluded.update(
                row["request_group"]
                for row in read(path)["requests"]
                if row["split"] == "test"
            )
            prior.append({"path": str(path), "sha256": sha256_file(path)})
        data = prepare_dataset(
            args.data_dir,
            train_requests=args.train_requests,
            test_requests=args.holdout_requests,
            seed=args.seed,
            salt=salt,
            history_limit=50,
            exclude_test_requests=excluded,
        )
        preserve_validation_boundary(data, reference)
        for path in paths:
            old = read(path)["metadata"]["source_files"]
            if any(
                old[name]["sha256"] != value["sha256"]
                for name, value in data["metadata"]["source_files"].items()
                if name in old
            ):
                raise ValueError("source data changed relative to prior holdouts")
        store_identity_salt(directory, salt)
        write(directory / "dataset.json", data)
        protocol = {
            "schema": "nrms-continuation-search-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
            "absolute_target": 0.4,
            "parent_artifact": str(parent_path.resolve()),
            "reference_dir": str(args.reference_dir.resolve()),
            "parent_model_sha256": sha256_file(parent_path / "model.joblib"),
            "parent_manifest_sha256": sha256_file(parent_path / "manifest.json"),
            "dataset_sha256": sha256_file(directory / "dataset.json"),
            "excluded_datasets": prior,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "patience": 2,
            "configs": {name: CONFIGS[name] for name in args.configs},
            "selection": "max validation nDCG@10; parent included; first candidate wins ties; no holdout inspection before freezing",
            "validation_cutoff": reference["metadata"]["validation_cutoff"],
            "split_counts": data["metadata"]["split_counts"],
        }
        write(directory / "search-protocol.json", protocol)
        print(
            json.dumps(
                {
                    "stage": "prepared",
                    "articles": len(data["articles"]),
                    "split_counts": data["metadata"]["split_counts"],
                    "excluded_requests": len(excluded),
                }
            ),
            flush=True,
        )
        return 0
    protocol, parent, data = checked_inputs(directory)
    if args.stage == "encode":
        encode_data(
            directory, protocol, data, model_dir=args.model_dir, device=args.device
        )
        return 0
    target = directory / "embeddings.npz"
    if sha256_file(target) != protocol["embeddings_sha256"]:
        raise ValueError("training embeddings changed")
    vectors = cached_embeddings(
        data["articles"],
        target,
        encode=lambda _: None,
        encoder_version=ENCODER_VERSION,
        dimension=EMBEDDING_DIMENSION,
    )
    with threadpool_limits(limits=1):
        if args.stage == "train":
            if (directory / "selection.json").exists():
                raise FileExistsError("search frozen; start a new experiment")
            train_candidates(
                directory, protocol, parent, data, vectors, trial=args.trial
            )
        elif args.stage == "select":
            freeze_winner(directory, protocol, parent, data, vectors)
        else:
            benchmark_winner(directory, protocol, parent, data, vectors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
