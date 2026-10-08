"""Prepare an evaluation-only MIND holdout for a frozen, verified model."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from workers.nlp_worker.app.content_features import (
    EMBEDDING_DIMENSION,
    ENCODER_VERSION,
    normalize_content,
)

from .artifact import LoadedNRMSArtifact, load_artifact, sha256_file
from .mind_adapter import _parse_timestamp, _private_id
from .mind_large import cached_embeddings, sample_behaviors
from .schemas import parse_datetime


def prepare_holdout(
    data_dir, *, excluded, limit, seed, salt, history_limit, training_end
):
    if not salt or history_limit < 1:
        raise ValueError("salt and positive history limit are required")

    def exclude(fields):
        identity = f"MINDlarge_dev:{fields[1].decode()}:{fields[0].decode()}"
        return _private_id(salt, "mind-request", identity) in excluded

    selected, audit = sample_behaviors(
        data_dir / "MINDlarge_dev/behaviors.tsv",
        limit=limit,
        seed=seed,
        exclude=exclude,
    )
    if audit["excluded_requests"] != len(excluded):
        raise ValueError("holdout exclusion mismatch: wrong salt or source data")
    requests, needed, seen = [], set(), set()
    for impression, user, when, history, candidates in selected:
        group = _private_id(salt, "mind-request", f"MINDlarge_dev:{user}:{impression}")
        if group in seen:
            raise ValueError("duplicate canonical request")
        seen.add(group)
        served = _parse_timestamp(when)
        if served <= parse_datetime(training_end):
            raise ValueError(
                "holdout must follow the frozen model's training/validation window"
            )
        ids, labels = [], []
        for token in candidates.split():
            fields = token.rsplit("-", 1)
            if len(fields) != 2 or fields[1] not in {"0", "1"}:
                raise ValueError("evaluation requires binary click labels")
            ids.append(fields[0])
            labels.append(int(fields[1]))
        if len(ids) < 2 or len(set(ids)) != len(ids):
            raise ValueError("requests need at least two unique candidates")
        history_ids = history.split()[-history_limit:]
        needed.update(ids + history_ids)
        requests.append(
            {
                "request_group": group,
                "user_group": _private_id(salt, "mind-user", user),
                "served_at": served.isoformat(),
                "history": history_ids,
                "candidates": ids,
                "labels": labels,
                "split": "test",
            }
        )
    articles, sources = {}, {"MINDlarge_dev/behaviors.tsv": audit}
    for name in ("MINDlarge_train", "MINDlarge_dev"):
        path = data_dir / name / "news.tsv"
        sources[f"{name}/news.tsv"] = {"sha256": sha256_file(path)}
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                fields = line.rstrip("\r\n").split("\t")
                if len(fields) != 8:
                    raise ValueError("news.tsv must have eight fields")
                if fields[0] not in needed:
                    continue
                article = {
                    "article_group": _private_id(salt, "mind-article", fields[0]),
                    "text": normalize_content(" ".join(fields[3:5])),
                    "category": fields[1],
                    "subcategory": fields[2],
                }
                if fields[0] in articles and articles[fields[0]] != article:
                    raise ValueError(
                        "conflicting article revision across source splits"
                    )
                articles[fields[0]] = article
    if needed - articles.keys():
        raise ValueError("unknown candidate/history articles")
    ordered = sorted(articles, key=lambda key: articles[key]["article_group"])
    indices = {key: index for index, key in enumerate(ordered)}
    for row in requests:
        row["history"] = [indices[key] for key in row["history"]]
        row["candidates"] = [indices[key] for key in row["candidates"]]
    requests.sort(key=lambda row: (row["served_at"], row["request_group"]))
    return {
        "articles": [articles[key] for key in ordered],
        "requests": requests,
        "metadata": {
            "format": "mind-compact-benchmark-v1",
            "seed": seed,
            "history_limit": history_limit,
            "training_window_end": training_end,
            "sampling": "lowest-sha256-canonical-request-v1",
            "source_files": sources,
            "excluded_requests": len(excluded),
            "all_selected_candidates_retained": True,
            "official_test_used": False,
            "raw_identifiers_exported": False,
            "language": "en",
            "history_provenance": "mind-pre-impression-snapshot",
            "publication_timestamps_available": False,
            "social_graph_available": False,
        },
    }


def merge_embeddings(articles, reference, reference_vectors, *, encode):
    reference_vectors = np.asarray(reference_vectors, dtype=np.float32)
    if (
        reference_vectors.ndim != 2
        or len(reference_vectors) != len(reference)
        or not np.isfinite(reference_vectors).all()
        or not np.allclose(np.linalg.norm(reference_vectors, axis=1), 1, atol=0.001)
    ):
        raise ValueError("invalid reference embeddings")
    by_id = {article["article_group"]: index for index, article in enumerate(reference)}
    if len(by_id) != len(reference):
        raise ValueError("duplicate reference article identity")
    vectors = np.empty((len(articles), reference_vectors.shape[1]), dtype=np.float32)
    missing = []
    for index, article in enumerate(articles):
        old = by_id.get(article["article_group"])
        if old is None:
            missing.append(index)
        else:
            if reference[old]["text"] != article["text"]:
                raise ValueError("cached article text revision mismatch")
            vectors[index] = reference_vectors[old]
    if missing:
        encoded = np.asarray(
            encode([articles[index]["text"] for index in missing]), dtype=np.float32
        )
        if (
            encoded.shape != (len(missing), reference_vectors.shape[1])
            or not np.isfinite(encoded).all()
            or not np.allclose(np.linalg.norm(encoded, axis=1), 1, atol=0.001)
        ):
            raise ValueError("encoder returned invalid embeddings")
        vectors[missing] = encoded
    return vectors, {
        "reused_articles": len(articles) - len(missing),
        "encoded_articles": len(missing),
    }


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def store_identity_salt(output, salt):
    """Keep the exclusion key private so later runs can exclude this holdout."""
    path = output / "identity-salt"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(salt + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("prepare", "encode"), required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data _train "))
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--exclude-dataset", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20261002)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    args = parser.parse_args(argv)
    artifact = load_artifact(args.artifact)
    if not isinstance(artifact, LoadedNRMSArtifact) or artifact.manifest[
        "embedding"
    ] != {"version": ENCODER_VERSION, "dimension": EMBEDDING_DIMENSION}:
        raise ValueError("benchmark requires the pinned multilingual NRMS artifact")
    reference_path = args.reference_dir / "dataset.json"
    embedding_path = args.reference_dir / "embeddings.npz"
    reference = _json(reference_path)
    if sha256_file(reference_path) != artifact.manifest["dataset"]["sha256"]:
        raise ValueError("reference dataset is not the frozen model's training dataset")
    if (
        sha256_file(embedding_path)
        != artifact.manifest["dataset"]["metadata"]["embedding_sha256"]
    ):
        raise ValueError("reference embedding checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=True)
    protocol_path = args.output / "protocol.json"
    dataset_path = args.output / "dataset.json"
    if args.stage == "prepare":
        if protocol_path.exists() or dataset_path.exists():
            raise FileExistsError(
                "benchmark already prepared; use a new output directory"
            )
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
                raise ValueError(
                    "holdout exclusion datasets must share the same identity salt"
                )
            data = _json(path)
            excluded.update(
                row["request_group"]
                for row in data["requests"]
                if row["split"] == "test"
            )
            prior.append({"path": str(path), "sha256": sha256_file(path)})
        training_end = max(
            row["served_at"] for row in reference["requests"] if row["split"] != "test"
        )
        data = prepare_holdout(
            args.data_dir,
            excluded=excluded,
            limit=args.requests,
            seed=args.seed,
            salt=salt,
            history_limit=artifact.ranker.architecture.history_length,
            training_end=training_end,
        )
        for path in paths:
            old_sources = _json(path)["metadata"]["source_files"]
            for name, current in data["metadata"]["source_files"].items():
                if old_sources[name]["sha256"] != current["sha256"]:
                    raise ValueError(
                        "benchmark source differs from previously evaluated data"
                    )
        store_identity_salt(args.output, salt)
        dataset_path.write_text(json.dumps(data, ensure_ascii=False) + "\n")
        protocol = {
            "schema": "recommendation-benchmark-protocol-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model_version": artifact.manifest["model_version"],
            "artifact": str(args.artifact.resolve()),
            "model_sha256": sha256_file(args.artifact / "model.joblib"),
            "manifest_sha256": sha256_file(args.artifact / "manifest.json"),
            "dataset_sha256": sha256_file(dataset_path),
            "reference_dataset_sha256": sha256_file(reference_path),
            "reference_embeddings_sha256": sha256_file(embedding_path),
            "excluded_datasets": prior,
            "seed": args.seed,
            "requests": args.requests,
            "primary_metric": "ndcg_at_10",
            "primary_baseline": "semantic_mean_pool",
            "baselines": ["logged_order", "random", "semantic_mean_pool"],
            "bootstrap_resamples": 1000,
            "confidence_level": 0.95,
            "bootstrap_unit": "user-cluster; request-weighted mean",
            "decision": "cluster CI excludes zero; minimum 1000 requests and 100 users",
            "latency": {
                "device": "cpu",
                "blas_threads": 1,
                "sample_requests": 500,
                "fixed_candidates": 300,
                "fixed_history": 20,
                "fixed_repeats": 100,
                "warmup_requests": 20,
            },
            "selection": "fixed artifact; no training, tuning or selection on benchmark labels",
            "scope": "sampled English MINDlarge dev; offline reranking only",
        }
        protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "stage": "prepared",
                    "requests": len(data["requests"]),
                    "articles": len(data["articles"]),
                    "excluded_requests": len(excluded),
                }
            ),
            flush=True,
        )
        return 0
    protocol, data = _json(protocol_path), _json(dataset_path)
    checks = {
        "dataset_sha256": sha256_file(dataset_path),
        "model_sha256": sha256_file(args.artifact / "model.joblib"),
        "manifest_sha256": sha256_file(args.artifact / "manifest.json"),
        "reference_dataset_sha256": sha256_file(reference_path),
        "reference_embeddings_sha256": sha256_file(embedding_path),
    }
    if any(protocol[name] != value for name, value in checks.items()):
        raise ValueError("benchmark inputs changed after protocol registration")
    old_vectors = cached_embeddings(
        reference["articles"],
        embedding_path,
        encode=lambda _: None,
        encoder_version=ENCODER_VERSION,
        dimension=EMBEDDING_DIMENSION,
    )

    def encode(texts):
        if args.model_dir is None:
            raise ValueError("--model-dir is required to encode missing articles")
        from workers.nlp_worker.app.model import PinnedSentenceEncoder

        print(
            json.dumps(
                {
                    "stage": "encoding_missing",
                    "articles": len(texts),
                    "device": args.device,
                }
            ),
            flush=True,
        )
        encoder = PinnedSentenceEncoder(
            str(args.model_dir), device=args.device, torch_threads=2
        )
        return encoder._load().encode(
            ["passage: " + text for text in texts],
            batch_size=32,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        )

    vectors, audit = merge_embeddings(
        data["articles"], reference["articles"], old_vectors, encode=encode
    )
    target = args.output / "embeddings.npz"
    cached_embeddings(
        data["articles"],
        target,
        encode=lambda _: vectors,
        encoder_version=ENCODER_VERSION,
        dimension=EMBEDDING_DIMENSION,
    )
    audit.update(encoder_version=ENCODER_VERSION, embeddings_sha256=sha256_file(target))
    (args.output / "embedding-audit.json").write_text(
        json.dumps(audit, indent=2) + "\n"
    )
    print(json.dumps({"stage": "encoded", **audit}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
