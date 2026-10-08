"""Bounded-memory MIND training data: one embedding per article, one history per request.

Official dev is a sealed labeled holdout. Official train supplies chronological
train/validation. Official test has no public labels and is never used for fitting.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import secrets
from pathlib import Path

import numpy as np

from workers.nlp_worker.app.content_features import normalize_content

from .artifact import sha256_file
from .mind_adapter import _parse_timestamp, _private_id


def sample_behaviors(path: Path, *, limit: int, seed: int, exclude=None):
    """Keep the lowest request hashes in O(limit) memory; never sample by label."""
    if limit < 1:
        raise ValueError("request limit must be positive")
    digest = hashlib.sha256()
    heap = []
    count = 0
    excluded = 0
    with path.open("rb") as handle:
        for count, line in enumerate(handle, 1):
            digest.update(line)
            fields = line.rstrip(b"\r\n").split(b"\t")
            if len(fields) != 5:
                raise ValueError(f"malformed behavior at line {count}")
            if exclude is not None and exclude(fields):
                excluded += 1
                continue
            priority = int.from_bytes(
                hashlib.sha256(
                    str(seed).encode() + b":" + fields[1] + b":" + fields[0]
                ).digest()
            )
            item = (-priority, line)
            if len(heap) < limit:
                heapq.heappush(heap, item)
            elif item > heap[0]:
                heapq.heapreplace(heap, item)
    if count - excluded < limit:
        raise ValueError(
            f"requested {limit} requests, but only {count - excluded} are available"
        )
    rows = [
        line.decode("utf-8").rstrip("\r\n").split("\t")
        for _, line in sorted(heap, reverse=True)
    ]
    return rows, {
        "requests": count,
        "selected": len(rows),
        "sha256": digest.hexdigest(),
        "excluded_requests": excluded,
    }


def prepare_dataset(
    data_dir: Path,
    *,
    train_requests: int,
    test_requests: int,
    seed: int,
    salt: str,
    history_limit: int = 20,
    exclude_test_requests: set[str] | None = None,
):
    if not salt or history_limit < 1:
        raise ValueError("salt and a positive history limit are required")
    sources = {}
    audit = {}
    needed = set()
    seen = set()
    excluded = exclude_test_requests or set()
    for source, limit in (
        ("MINDlarge_train", train_requests),
        ("MINDlarge_dev", test_requests),
    ):
        path = data_dir / source / "behaviors.tsv"

        def exclude(fields, source=source):
            identity = f"{source}:{fields[1].decode()}:{fields[0].decode()}"
            return _private_id(salt, "mind-request", identity) in excluded

        selected, audit[f"{source}/behaviors.tsv"] = sample_behaviors(
            path,
            limit=limit,
            seed=seed,
            exclude=exclude if source == "MINDlarge_dev" and excluded else None,
        )
        if source == "MINDlarge_dev" and audit[f"{source}/behaviors.tsv"][
            "excluded_requests"
        ] != len(excluded):
            raise ValueError(
                "holdout exclusion mismatch: verify source data and identity salt"
            )
        parsed = []
        for impression, user, when, history, candidates in selected:
            identity = f"{source}:{user}:{impression}"
            if identity in seen:
                raise ValueError("duplicate canonical request")
            seen.add(identity)
            candidate_ids, labels = [], []
            for token in candidates.split():
                if "-" not in token or token.rsplit("-", 1)[1] not in {"0", "1"}:
                    raise ValueError(
                        "training/evaluation requires binary click labels; official test is unlabeled"
                    )
                candidate, label = token.rsplit("-", 1)
                candidate_ids.append(candidate)
                labels.append(int(label))
            if len(candidate_ids) < 2:
                raise ValueError("each request needs at least two candidates")
            if len(set(candidate_ids)) != len(candidate_ids):
                raise ValueError("duplicate candidate in request")
            history_ids = history.split()[-history_limit:]
            needed.update(candidate_ids)
            needed.update(history_ids)
            parsed.append(
                {
                    "request_group": _private_id(salt, "mind-request", identity),
                    "user_group": _private_id(salt, "mind-user", user),
                    "served_at": _parse_timestamp(when).isoformat(),
                    "history": history_ids,
                    "candidates": candidate_ids,
                    "labels": labels,
                }
            )
        sources[source] = sorted(
            parsed, key=lambda row: (row["served_at"], row["request_group"])
        )

    train = sources["MINDlarge_train"]
    test = sources["MINDlarge_dev"]
    times = sorted({r["served_at"] for r in train})
    if len(times) < 2 or train[-1]["served_at"] >= test[0]["served_at"]:
        raise ValueError(
            "selected official splits must be strictly chronological with at least two training timestamps"
        )
    cutoff = times[min(len(times) - 1, max(1, int(len(times) * 0.85)))]
    for row in train:
        row["split"] = "train" if row["served_at"] < cutoff else "validation"
    for row in test:
        row["split"] = "test"

    news = {}
    for source in sources:
        path = data_dir / source / "news.tsv"
        audit[f"{source}/news.tsv"] = {"sha256": sha256_file(path)}
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                fields = line.rstrip("\r\n").split("\t")
                if len(fields) != 8:
                    raise ValueError("news.tsv must have eight fields")
                if fields[0] not in needed:
                    continue
                text = normalize_content(" ".join(fields[3:5]))
                value = {
                    "article_group": _private_id(salt, "mind-article", fields[0]),
                    "text": text,
                    "category": fields[1],
                    "subcategory": fields[2],
                }
                if fields[0] in news and news[fields[0]] != value:
                    raise ValueError(
                        "conflicting article revisions across official splits"
                    )
                news[fields[0]] = value
    if needed - news.keys():
        raise ValueError(f"unknown articles: {len(needed - news.keys())}")
    ordered_ids = sorted(news, key=lambda key: news[key]["article_group"])
    indices = {key: i for i, key in enumerate(ordered_ids)}
    requests = train + test
    for row in requests:
        row["candidates"] = [indices[key] for key in row["candidates"]]
        row["history"] = [indices[key] for key in row["history"]]
    return {
        "articles": [news[key] for key in ordered_ids],
        "requests": requests,
        "metadata": {
            "format": "mind-compact-v1",
            "sampling": "lowest-sha256-canonical-request-v1",
            "seed": seed,
            "source_files": audit,
            "history_limit": history_limit,
            "validation_cutoff": cutoff,
            "official_dev_is_test": True,
            "official_test_used": False,
            "all_selected_candidates_retained": True,
            "raw_identifiers_exported": False,
            "history_provenance": "mind-pre-impression-snapshot",
            "history_timestamps_available": False,
            "publication_timestamps_available": False,
            "social_graph_available": False,
            "language": "en",
            "scope": "sampled-MINDlarge-news-benchmark",
            "excluded_test_requests": len(excluded),
            "excluded_test_groups_sha256": hashlib.sha256(
                "\n".join(sorted(excluded)).encode()
            ).hexdigest(),
            "split_counts": {
                s: sum(r["split"] == s for r in requests)
                for s in ("train", "validation", "test")
            },
        },
    }


def cached_embeddings(
    articles, target: Path, *, encode, encoder_version: str, dimension: int
):
    texts = [a["text"] for a in articles]
    fingerprint = hashlib.sha256(
        json.dumps(
            {"texts": texts, "encoder": encoder_version, "dimension": dimension},
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if target.exists():
        with np.load(target, allow_pickle=False) as cache:
            if str(cache["fingerprint"].item()) != fingerprint:
                raise ValueError("embedding cache does not match text and encoder")
            vectors = cache["vectors"]
    else:
        vectors = np.asarray(encode(texts), dtype=np.float32)
    if (
        vectors.shape != (len(texts), dimension)
        or not np.isfinite(vectors).all()
        or not np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=0.001)
    ):
        raise ValueError("invalid embedding vectors")
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp.npz")
        np.savez(temporary, fingerprint=fingerprint, vectors=vectors)
        temporary.replace(target)
    return vectors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", choices=("prepare", "encode", "train", "all"), default="all"
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data _train "))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--train-requests", type=int, default=10000)
    parser.add_argument("--test-requests", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260927)
    parser.add_argument("--history-limit", type=int, default=20)
    parser.add_argument(
        "--exclude-holdout",
        type=Path,
        action="append",
        default=[],
        help="Prior dataset.json whose test requests must be excluded; adjacent identity-salt must be present and shared across prior runs.",
    )
    parser.add_argument(
        "--preserve-semantics",
        action="store_true",
        help="Freeze identity value projections, remove position noise, and retain half the mean-pool semantic vector.",
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "mps", "cuda"),
        default="cpu",
        help="Device for text embeddings; ranker fitting uses CPU.",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument(
        "--learning-rates", type=float, nargs="+", default=[0.0001, 0.001]
    )
    args = parser.parse_args(argv)
    if (
        args.batch_size < 1
        or args.epochs < 1
        or any(not np.isfinite(v) or v <= 0 for v in args.learning_rates)
    ):
        parser.error("batch size, epochs, and learning rates must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    dataset_path = args.output / "dataset.json"
    if args.stage in {"prepare", "all"}:
        if dataset_path.exists():
            parser.error("dataset already exists; resume with --stage encode or train")
        salt_path = args.output / "identity-salt"
        excluded = set()
        source_salt = None
        exclusions = []
        for previous_path in args.exclude_holdout:
            previous = json.loads(previous_path.read_text())
            if not previous["metadata"].get("official_dev_is_test"):
                parser.error("excluded datasets must use official dev as holdout")
            prior_salt = (previous_path.parent / "identity-salt").read_text().strip()
            if not prior_salt or (
                source_salt is not None and prior_salt != source_salt
            ):
                parser.error(
                    "excluded datasets must share the same nonempty identity salt"
                )
            source_salt = prior_salt
            excluded.update(
                r["request_group"] for r in previous["requests"] if r["split"] == "test"
            )
            exclusions.append(sha256_file(previous_path))
        if (
            source_salt
            and salt_path.exists()
            and salt_path.read_text().strip() != source_salt
        ):
            parser.error("output salt does not match excluded datasets")
        if not salt_path.exists():
            with open(
                salt_path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)
            ) as handle:
                handle.write(source_salt or secrets.token_hex(32))
        data = prepare_dataset(
            args.data_dir,
            train_requests=args.train_requests,
            test_requests=args.test_requests,
            seed=args.seed,
            salt=salt_path.read_text().strip(),
            history_limit=args.history_limit,
            exclude_test_requests=excluded,
        )
        data["metadata"]["excluded_dataset_sha256"] = exclusions
        dataset_path.write_text(json.dumps(data, ensure_ascii=False))
        print(
            json.dumps(
                dict(
                    stage="prepared", articles=len(data["articles"]), **data["metadata"]
                )
            ),
            flush=True,
        )
    else:
        data = json.loads(dataset_path.read_text())
    if args.stage == "prepare":
        return 0
    from workers.nlp_worker.app.content_features import (
        EMBEDDING_DIMENSION,
        ENCODER_VERSION,
    )

    embeddings_path = args.output / "embeddings.npz"
    if args.stage in {"encode", "all"}:
        from workers.nlp_worker.app.model import PinnedSentenceEncoder

        if args.model_dir is None:
            parser.error("--model-dir is required for encoding")
        encoder = PinnedSentenceEncoder(
            str(args.model_dir), device=args.device, torch_threads=2
        )

        def encode(texts):
            return encoder._load().encode(
                ["passage: " + t for t in texts],
                batch_size=args.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=True,
            )

        vectors = cached_embeddings(
            data["articles"],
            embeddings_path,
            encode=encode,
            encoder_version=ENCODER_VERSION,
            dimension=EMBEDDING_DIMENSION,
        )
        print(json.dumps({"stage": "encoded", "articles": len(vectors)}), flush=True)
    else:

        def no_encode(_):
            raise ValueError("embedding cache missing; run --stage encode first")

        vectors = cached_embeddings(
            data["articles"],
            embeddings_path,
            encode=no_encode,
            encoder_version=ENCODER_VERSION,
            dimension=EMBEDDING_DIMENSION,
        )
    if args.stage == "encode":
        return 0
    from .finetune import run_experiment

    run_experiment(
        data,
        vectors,
        args.output,
        dataset_sha256=sha256_file(dataset_path),
        embedding_sha256=sha256_file(embeddings_path),
        epochs=args.epochs,
        learning_rates=args.learning_rates,
        batch_size=args.batch_size,
        seed=args.seed,
        **(
            {"freeze_values": True, "position_scale": 0.0, "semantic_residual": 0.5}
            if args.preserve_semantics
            else {}
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
