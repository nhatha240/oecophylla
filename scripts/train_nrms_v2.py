from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq

from ai_pipeline.finetune import run_experiment


DEFAULT_DATASET = Path(
    r"D:\UIT\DATN\mind-small\pilot-embedded.parquet"
)

DEFAULT_METADATA = Path(
    r"D:\UIT\DATN\mind-small\pilot-embedded.parquet.metadata.json"
)

DEFAULT_OUTPUT = Path(
    r"D:\UIT\DATN\mind-small\nrms-pilot-v2"
)


# ============================================================
# Utility
# ============================================================


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def get_article_id(
    article: dict[str, Any] | None,
    *,
    fallback: str | None = None,
) -> str:
    """
    Return the stable private article identifier used by the
    prepared MIND dataset.

    article_group is preferred because raw MIND news IDs have
    already been privacy-transformed by the project.
    """

    article = article or {}

    for key in (
        "article_group",
        "candidate_group",
        "content_hash",
        "sample_id",
    ):
        value = article.get(key)

        if value not in (None, ""):
            return str(value)

    if fallback not in (None, ""):
        return str(fallback)

    raise ValueError(
        "Unable to determine article identifier"
    )


def get_embedding(
    article: dict[str, Any] | None,
    *,
    article_id: str,
    expected_dimension: int,
) -> np.ndarray:
    article = article or {}

    embedding = article.get("embedding")

    if embedding is None:
        raise ValueError(
            f"Article {article_id} is missing embedding"
        )

    vector = np.asarray(
        embedding,
        dtype=np.float32,
    )

    if vector.ndim != 1:
        raise ValueError(
            f"Article {article_id}: "
            f"embedding ndim={vector.ndim}, expected 1"
        )

    if vector.shape[0] != expected_dimension:
        raise ValueError(
            f"Article {article_id}: "
            f"embedding dimension={vector.shape[0]}, "
            f"expected={expected_dimension}"
        )

    if not np.isfinite(vector).all():
        raise ValueError(
            f"Article {article_id} contains NaN/Inf"
        )

    return vector


def history_signature(
    history: list[dict[str, Any]],
) -> tuple[str, ...]:
    ordered = sorted(
        history,
        key=lambda item: int(
            item.get("ordinal") or 0
        ),
    )

    return tuple(
        get_article_id(
            item.get("article"),
            fallback=(
                item.get("article", {})
                or {}
            ).get("content_hash"),
        )
        for item in ordered
    )


def vector_catalog_sha256(
    article_ids: list[str],
    vectors: np.ndarray,
) -> str:
    """
    Deterministic checksum over article order + vectors.
    """

    digest = hashlib.sha256()

    for article_id, vector in zip(
        article_ids,
        vectors,
        strict=True,
    ):
        digest.update(
            article_id.encode("utf-8")
        )

        digest.update(b"\0")

        digest.update(
            np.asarray(
                vector,
                dtype="<f4",
            ).tobytes(
                order="C"
            )
        )

    return digest.hexdigest()


# ============================================================
# Dataset adapter
# ============================================================


def build_nrms_dataset(
    rows: list[dict[str, Any]],
    *,
    metadata: dict[str, Any],
) -> tuple[
    dict[str, Any],
    np.ndarray,
    dict[str, int],
]:
    """
    Convert candidate-level pilot Parquet rows into the
    request-level format expected by ai_pipeline.finetune.

    Input:
        one row = one candidate article

    Output request:
        {
            "request_group": str,
            "split": str,
            "history": [article_index, ...],
            "candidates": [article_index, ...],
            "labels": [0/1, ...],
        }
    """

    embedding_dimension = int(
        metadata.get(
            "encoder_dimension",
            384,
        )
    )

    history_limit = int(
        metadata.get(
            "materialization",
            {},
        ).get(
            "history_limit",
            20,
        )
    )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        request_group = row.get(
            "request_group"
        )

        if request_group in (
            None,
            "",
        ):
            raise ValueError(
                "Found row without request_group"
            )

        grouped[
            str(request_group)
        ].append(row)

    # --------------------------------------------------------
    # 1. Build global article embedding catalog
    # --------------------------------------------------------

    catalog: dict[
        str,
        np.ndarray,
    ] = {}

    def add_article(
        article: dict[str, Any] | None,
        *,
        fallback: str | None,
    ) -> str:
        article_id = get_article_id(
            article,
            fallback=fallback,
        )

        vector = get_embedding(
            article,
            article_id=article_id,
            expected_dimension=(
                embedding_dimension
            ),
        )

        previous = catalog.get(
            article_id
        )

        if previous is None:
            catalog[
                article_id
            ] = vector

        else:
            if not np.allclose(
                previous,
                vector,
                rtol=1e-5,
                atol=1e-6,
            ):
                raise ValueError(
                    "Conflicting embeddings "
                    f"for article {article_id}"
                )

        return article_id

    for row in rows:
        add_article(
            row.get("article"),
            fallback=(
                row.get(
                    "candidate_group"
                )
                or row.get("sample_id")
            ),
        )

        for entry in (
            row.get("history")
            or []
        ):
            article = (
                entry.get("article")
                or {}
            )

            add_article(
                article,
                fallback=article.get(
                    "content_hash"
                ),
            )

    # Deterministic article indexing
    article_ids = sorted(
        catalog
    )

    article_to_index = {
        article_id: index
        for index, article_id
        in enumerate(article_ids)
    }

    vectors = np.stack(
        [
            catalog[
                article_id
            ]
            for article_id
            in article_ids
        ],
        axis=0,
    ).astype(
        np.float32,
        copy=False,
    )

    # --------------------------------------------------------
    # 2. Build request-level records
    # --------------------------------------------------------

    requests: list[
        dict[str, Any]
    ] = []

    split_counter: Counter[str] = (
        Counter()
    )

    positive_counter: Counter[str] = (
        Counter()
    )

    empty_history_requests = 0

    candidate_counts: list[int] = []
    history_counts: list[int] = []

    for request_group in sorted(
        grouped
    ):
        request_rows = grouped[
            request_group
        ]

        splits = {
            str(row.get("split"))
            for row in request_rows
        }

        if len(splits) != 1:
            raise ValueError(
                f"Request {request_group} "
                f"has multiple splits: "
                f"{sorted(splits)}"
            )

        split = next(
            iter(splits)
        )

        if split not in {
            "train",
            "validation",
            "test",
        }:
            raise ValueError(
                f"Unexpected split "
                f"{split!r}"
            )

        # Candidate ordering should follow
        # original impression position.
        ordered_rows = sorted(
            request_rows,
            key=lambda row: (
                int(
                    row.get(
                        "position"
                    )
                    or 0
                ),
                str(
                    row.get(
                        "candidate_group"
                    )
                    or ""
                ),
            ),
        )

        candidate_indices: list[int] = []
        labels: list[int] = []

        for row in ordered_rows:
            article_id = get_article_id(
                row.get("article"),
                fallback=(
                    row.get(
                        "candidate_group"
                    )
                    or row.get(
                        "sample_id"
                    )
                ),
            )

            candidate_indices.append(
                article_to_index[
                    article_id
                ]
            )

            label = int(
                row.get(
                    "click_label"
                )
                or 0
            )

            if label not in (0, 1):
                raise ValueError(
                    f"Invalid click_label "
                    f"{label} in request "
                    f"{request_group}"
                )

            labels.append(label)

        # ----------------------------------------------------
        # Verify history is identical across all candidates
        # of one request.
        # ----------------------------------------------------

        first_history = list(
            ordered_rows[0].get(
                "history"
            )
            or []
        )

        expected_history_signature = (
            history_signature(
                first_history
            )
        )

        for row in ordered_rows[1:]:
            signature = (
                history_signature(
                    list(
                        row.get(
                            "history"
                        )
                        or []
                    )
                )
            )

            if (
                signature
                != expected_history_signature
            ):
                raise ValueError(
                    "Candidate rows of request "
                    f"{request_group} have "
                    "different histories"
                )

        ordered_history = sorted(
            first_history,
            key=lambda entry: int(
                entry.get(
                    "ordinal"
                )
                or 0
            ),
        )

        # Dataset already uses history_limit=20.
        # Keep the most recent entries if necessary.
        if history_limit > 0:
            ordered_history = (
                ordered_history[
                    -history_limit:
                ]
            )

        history_indices: list[int] = []

        for entry in ordered_history:
            article = (
                entry.get("article")
                or {}
            )

            article_id = (
                get_article_id(
                    article,
                    fallback=article.get(
                        "content_hash"
                    ),
                )
            )

            history_indices.append(
                article_to_index[
                    article_id
                ]
            )

        if not history_indices:
            empty_history_requests += 1

        split_counter[
            split
        ] += 1

        positive_counter[
            split
        ] += sum(labels)

        candidate_counts.append(
            len(candidate_indices)
        )

        history_counts.append(
            len(history_indices)
        )

        requests.append(
            {
                "request_group": (
                    request_group
                ),
                "split": split,
                "history": (
                    history_indices
                ),
                "candidates": (
                    candidate_indices
                ),
                "labels": labels,
            }
        )

    # --------------------------------------------------------
    # 3. Final validation
    # --------------------------------------------------------

    if vectors.ndim != 2:
        raise ValueError(
            "vectors must be 2-dimensional"
        )

    if (
        vectors.shape[1]
        != embedding_dimension
    ):
        raise ValueError(
            "Unexpected embedding dimension"
        )

    if not np.isfinite(
        vectors
    ).all():
        raise ValueError(
            "vectors contain NaN/Inf"
        )

    if not requests:
        raise ValueError(
            "No requests were produced"
        )

    stats = {
        "rows": len(rows),
        "requests": len(requests),
        "articles": len(article_ids),
        "embedding_dimension": (
            embedding_dimension
        ),
        "history_limit": (
            history_limit
        ),
        "train_requests": (
            split_counter["train"]
        ),
        "validation_requests": (
            split_counter[
                "validation"
            ]
        ),
        "test_requests": (
            split_counter["test"]
        ),
        "train_positive_labels": (
            positive_counter["train"]
        ),
        "validation_positive_labels": (
            positive_counter[
                "validation"
            ]
        ),
        "test_positive_labels": (
            positive_counter["test"]
        ),
        "empty_history_requests": (
            empty_history_requests
        ),
        "min_candidates": int(
            min(candidate_counts)
        ),
        "max_candidates": int(
            max(candidate_counts)
        ),
        "min_history": int(
            min(history_counts)
        ),
        "max_history": int(
            max(history_counts)
        ),
    }

    adapted_metadata = dict(
        metadata
    )

    adapted_metadata[
        "nrms_adapter"
    ] = {
        "format": (
            "candidate-parquet-to-"
            "finetune-request-v1"
        ),
        **stats,
    }

    data = {
        "requests": requests,
        "metadata": (
            adapted_metadata
        ),
    }

    return (
        data,
        vectors,
        stats,
    )


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train NRMS V2 directly from "
            "pilot-embedded.parquet."
        )
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
    )

    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )

    parser.add_argument(
        "--learning-rates",
        type=float,
        nargs="+",
        default=[
            0.0001,
            0.001,
        ],
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=20260927,
    )

    parser.add_argument(
        "--preserve-semantics",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Use anti-collapse NRMS settings: "
            "freeze value projection, "
            "remove positional noise, "
            "and retain 50%% semantic "
            "mean-pool residual."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate and adapt dataset "
            "without training."
        ),
    )

    return parser.parse_args()


# ============================================================
# Main
# ============================================================


def main() -> int:
    args = parse_args()

    print(
        "=" * 72
    )

    print(
        "NRMS V2 TRAINING PIPELINE"
    )

    print(
        "=" * 72
    )

    print(
        f"Dataset : {args.dataset}"
    )

    print(
        f"Metadata: {args.metadata}"
    )

    print(
        f"Output  : {args.output}"
    )

    # --------------------------------------------------------
    # Input validation
    # --------------------------------------------------------

    if not args.dataset.exists():
        raise FileNotFoundError(
            args.dataset
        )

    if not args.metadata.exists():
        raise FileNotFoundError(
            args.metadata
        )

    print(
        "\nLoading metadata..."
    )

    metadata = json.loads(
        args.metadata.read_text(
            encoding="utf-8"
        )
    )

    print(
        "Loading Parquet..."
    )

    table = pq.read_table(
        args.dataset
    )

    rows = table.to_pylist()

    print(
        f"Loaded rows: {len(rows)}"
    )

    # --------------------------------------------------------
    # Candidate → request adapter
    # --------------------------------------------------------

    print(
        "\nBuilding NRMS "
        "request-level dataset..."
    )

    data, vectors, stats = (
        build_nrms_dataset(
            rows,
            metadata=metadata,
        )
    )

    print(
        "\n"
        + "=" * 72
    )

    print(
        "ADAPTER VALIDATION"
    )

    print(
        "=" * 72
    )

    for key, value in (
        stats.items()
    ):
        print(
            f"{key:<30}: {value}"
        )

    print(
        f"{'vectors_shape':<30}: "
        f"{vectors.shape}"
    )

    print(
        f"{'vectors_dtype':<30}: "
        f"{vectors.dtype}"
    )

    print(
        f"{'vectors_finite':<30}: "
        f"{np.isfinite(vectors).all()}"
    )

    dataset_sha256 = (
        sha256_file(
            args.dataset
        )
    )

    article_ids = sorted(
        {
            get_article_id(
                row.get("article"),
                fallback=(
                    row.get(
                        "candidate_group"
                    )
                    or row.get(
                        "sample_id"
                    )
                ),
            )
            for row in rows
        }
        |
        {
            get_article_id(
                entry.get("article"),
                fallback=(
                    entry.get(
                        "article",
                        {},
                    )
                    or {}
                ).get(
                    "content_hash"
                ),
            )
            for row in rows
            for entry in (
                row.get("history")
                or []
            )
        }
    )

    embedding_sha256 = (
        vector_catalog_sha256(
            article_ids,
            vectors,
        )
    )

    print(
        f"{'dataset_sha256':<30}: "
        f"{dataset_sha256}"
    )

    print(
        f"{'embedding_sha256':<30}: "
        f"{embedding_sha256}"
    )

    # --------------------------------------------------------
    # Dry run
    # --------------------------------------------------------

    if args.dry_run:
        print(
            "\n"
            + "=" * 72
        )

        print(
            "DRY RUN PASSED"
        )

        print(
            "=" * 72
        )

        print(
            "Dataset can now be passed "
            "to finetune.run_experiment()."
        )

        return 0

    # --------------------------------------------------------
    # Protect existing artifact
    # --------------------------------------------------------

    if (
        (args.output / "model").exists()
        or
        (args.output / "report.json").exists()
    ):
        raise FileExistsError(
            "Output already contains a "
            "completed experiment: "
            f"{args.output}"
        )

    args.output.mkdir(
        parents=True,
        exist_ok=True,
    )

    history_limit = int(
        stats[
            "history_limit"
        ]
    )

    # --------------------------------------------------------
    # Anti-collapse configuration
    # --------------------------------------------------------

    experiment_kwargs: dict[
        str,
        Any,
    ] = {}

    if args.preserve_semantics:
        experiment_kwargs.update(
            {
                "freeze_values": True,
                "position_scale": 0.0,
                "semantic_residual": 0.5,
            }
        )

    print(
        "\n"
        + "=" * 72
    )

    print(
        "TRAINING CONFIGURATION"
    )

    print(
        "=" * 72
    )

    print(
        f"epochs                  : "
        f"{args.epochs}"
    )

    print(
        f"batch_size              : "
        f"{args.batch_size}"
    )

    print(
        f"learning_rates          : "
        f"{args.learning_rates}"
    )

    print(
        f"seed                    : "
        f"{args.seed}"
    )

    print(
        f"history_limit           : "
        f"{history_limit}"
    )

    print(
        f"preserve_semantics      : "
        f"{args.preserve_semantics}"
    )

    if args.preserve_semantics:
        print(
            "freeze_values           : True"
        )

        print(
            "position_scale          : 0.0"
        )

        print(
            "semantic_residual       : 0.5"
        )

    print(
        "\nTraining NRMS V2..."
    )
    # finetune.run_experiment() expects history_limit to be part of the
    # request-level dataset metadata.  The source pilot metadata stores it
    # under materialization, so make the adapter contract explicit here.
    data.setdefault("metadata", {})
    data["metadata"]["history_limit"] = int(history_limit)

    report = run_experiment(
        data,
        vectors,
        args.output,
        dataset_sha256=dataset_sha256,
        embedding_sha256=(
            embedding_sha256
        ),
        epochs=args.epochs,
        learning_rates=tuple(
            args.learning_rates
        ),
        batch_size=args.batch_size,
        seed=args.seed,
        **experiment_kwargs,
    )

    print(
        "\n"
        + "=" * 72
    )

    print(
        "TRAINING COMPLETE"
    )

    print(
        "=" * 72
    )

    print(
        f"Artifact: "
        f"{args.output / 'model'}"
    )

    print(
        f"Report  : "
        f"{args.output / 'report.json'}"
    )

    holdout = report.get(
        "holdout",
        {}
    )

    if holdout:
        print(
            "\nHOLDOUT RESULTS"
        )

        print(
            json.dumps(
                holdout,
                indent=2,
                ensure_ascii=False,
            )
        )

    comparison = report.get(
        "paired_ndcg_at_10_vs_mean_pool"
    )

    if comparison:
        print(
            "\nPAIRED NDCG@10 "
            "VS MEAN POOL"
        )

        print(
            json.dumps(
                comparison,
                indent=2,
                ensure_ascii=False,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )