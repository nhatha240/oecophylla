from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow.parquet as pq

from ai_pipeline.artifact import load_artifact


DATASET = Path(
    r"D:\UIT\DATN\mind-small\pilot-embedded.parquet"
)

ARTIFACT = Path(
    r"D:\UIT\DATN\mind-small\nrms-pilot-v2\model"
)


def article_id(article: Mapping[str, Any]) -> str:
    """
    Return the best stable identifier available for an article.
    """

    for key in (
        "article_group",
        "candidate_group",
        "post_group",
        "article_id",
        "news_id",
        "id",
        "content_hash",
    ):
        value = article.get(key)

        if value is not None:
            return str(value)

    return "unknown"


def history_signature(
    row: Mapping[str, Any],
) -> tuple[str, ...]:
    """
    Create a stable fingerprint of the user's history.
    """

    entries = sorted(
        row.get("history") or (),
        key=lambda entry: int(
            entry.get("ordinal") or 0
        ),
    )

    result: list[str] = []

    for entry in entries:
        article = entry.get("article") or {}

        result.append(
            article_id(article)
        )

    return tuple(result)


def history_embeddings(
    row: Mapping[str, Any],
) -> list[Sequence[float]]:
    """
    Extract history article embeddings exactly in history order.
    """

    entries = sorted(
        row.get("history") or (),
        key=lambda entry: int(
            entry.get("ordinal") or 0
        ),
    )

    result: list[Sequence[float]] = []

    for entry in entries:
        article = entry.get("article") or {}
        embedding = article.get("embedding")

        if embedding is None:
            continue

        result.append(embedding)

    return result


def cosine(
    left: Sequence[float],
    right: Sequence[float],
) -> float | None:
    left_vector = np.asarray(
        left,
        dtype=float,
    )

    right_vector = np.asarray(
        right,
        dtype=float,
    )

    left_norm = float(
        np.linalg.norm(left_vector)
    )

    right_norm = float(
        np.linalg.norm(right_vector)
    )

    if left_norm == 0.0 or right_norm == 0.0:
        return None

    return float(
        np.dot(
            left_vector,
            right_vector,
        )
        / (
            left_norm
            * right_norm
        )
    )


def describe(
    name: str,
    values: Sequence[float],
) -> None:
    array = np.asarray(
        values,
        dtype=float,
    )

    if len(array) == 0:
        print(f"{name}: no data")
        return

    print(f"{name}")
    print(f"  Count  : {len(array)}")
    print(f"  Min    : {np.min(array):.8f}")
    print(f"  P05    : {np.percentile(array, 5):.8f}")
    print(f"  P25    : {np.percentile(array, 25):.8f}")
    print(f"  Median : {np.median(array):.8f}")
    print(f"  Mean   : {np.mean(array):.8f}")
    print(f"  P75    : {np.percentile(array, 75):.8f}")
    print(f"  P95    : {np.percentile(array, 95):.8f}")
    print(f"  Max    : {np.max(array):.8f}")


def main() -> None:
    print("=" * 80)
    print("NRMS USER-CONTEXT COLLAPSE DIAGNOSTIC")
    print("=" * 80)

    print("\nLoading dataset...")

    table = pq.read_table(DATASET)
    rows = table.to_pylist()

    test_rows = [
        row
        for row in rows
        if row.get("split") == "test"
    ]

    grouped: dict[
        str,
        list[Mapping[str, Any]],
    ] = defaultdict(list)

    for row in test_rows:
        grouped[
            str(row["request_group"])
        ].append(row)

    print(
        f"Test rows     : {len(test_rows)}"
    )

    print(
        f"Test requests : {len(grouped)}"
    )

    print("\nLoading NRMS artifact...")

    artifact = load_artifact(
        ARTIFACT
    )

    ranker = getattr(
        artifact,
        "ranker",
        None,
    )

    if ranker is None:
        raise RuntimeError(
            "Loaded artifact does not expose "
            "an NRMS ranker."
        )

    prepare_user_context = getattr(
        ranker,
        "prepare_user_context",
        None,
    )

    if not callable(
        prepare_user_context
    ):
        raise RuntimeError(
            "NRMS ranker does not expose "
            "prepare_user_context()."
        )

    context_vectors: list[np.ndarray] = []

    request_ids: list[str] = []

    sources: Counter[str] = Counter()

    effective_history_lengths: list[int] = []

    raw_history_lengths: list[int] = []

    fabricated_clicks: list[int] = []

    history_signatures: Counter[
        tuple[str, ...]
    ] = Counter()

    print("\nBuilding user contexts...")

    for index, request_group in enumerate(
        sorted(grouped),
        start=1,
    ):
        request_rows = grouped[
            request_group
        ]

        if not request_rows:
            continue

        representative = request_rows[0]

        embeddings = history_embeddings(
            representative
        )

        raw_history_lengths.append(
            len(
                representative.get(
                    "history"
                )
                or ()
            )
        )

        declared = representative.get(
            "declared_topic_embedding"
        )

        context = prepare_user_context(
            history_embeddings=embeddings,
            declared_topic_embedding=declared,
        )

        vector = np.asarray(
            context.vector,
            dtype=float,
        )

        if vector.ndim != 1:
            raise RuntimeError(
                "User context vector is not 1-D."
            )

        if not np.all(
            np.isfinite(vector)
        ):
            raise RuntimeError(
                "User context contains non-finite values."
            )

        context_vectors.append(
            vector
        )

        request_ids.append(
            request_group
        )

        sources[
            str(
                getattr(
                    context,
                    "source",
                    "unknown",
                )
            )
        ] += 1

        effective_history_lengths.append(
            int(
                getattr(
                    context,
                    "history_length",
                    len(embeddings),
                )
            )
        )

        fabricated_clicks.append(
            int(
                getattr(
                    context,
                    "fabricated_clicks",
                    0,
                )
            )
        )

        history_signatures[
            history_signature(
                representative
            )
        ] += 1

        if index % 25 == 0:
            print(
                f"Processed "
                f"{index}/"
                f"{len(grouped)} requests"
            )

    if not context_vectors:
        raise RuntimeError(
            "No user contexts were generated."
        )

    matrix = np.vstack(
        context_vectors
    )

    print("\n" + "=" * 80)
    print("CONTEXT SOURCE")
    print("=" * 80)

    for source, count in (
        sources.most_common()
    ):
        print(
            f"{source:<30}: "
            f"{count:>5} "
            f"({count / len(context_vectors):.2%})"
        )

    print("\n" + "=" * 80)
    print("HISTORY")
    print("=" * 80)

    describe(
        "Raw history length",
        raw_history_lengths,
    )

    print()

    describe(
        "Effective history length",
        effective_history_lengths,
    )

    print()

    describe(
        "Fabricated clicks",
        fabricated_clicks,
    )

    unique_histories = len(
        history_signatures
    )

    most_common_history_count = (
        history_signatures.most_common(1)[0][1]
        if history_signatures
        else 0
    )

    print(
        "\nUnique history signatures : "
        f"{unique_histories}"
    )

    print(
        "Duplicate-history requests : "
        f"{len(context_vectors) - unique_histories}"
    )

    print(
        "Most common history count  : "
        f"{most_common_history_count}"
    )

    print("\n" + "=" * 80)
    print("USER VECTOR NORMS")
    print("=" * 80)

    norms = np.linalg.norm(
        matrix,
        axis=1,
    )

    describe(
        "Context vector norm",
        norms,
    )

    normalized = np.zeros_like(
        matrix,
        dtype=float,
    )

    valid = norms > 0.0

    normalized[
        valid
    ] = (
        matrix[valid]
        / norms[valid, None]
    )

    print("\n" + "=" * 80)
    print("PAIRWISE USER-CONTEXT COSINE SIMILARITY")
    print("=" * 80)

    pairwise_cosines: list[float] = []

    for left in range(
        len(normalized)
    ):
        if not valid[left]:
            continue

        for right in range(
            left + 1,
            len(normalized),
        ):
            if not valid[right]:
                continue

            pairwise_cosines.append(
                float(
                    np.dot(
                        normalized[left],
                        normalized[right],
                    )
                )
            )

    describe(
        "Pairwise cosine similarity",
        pairwise_cosines,
    )

    mean_context = np.mean(
        matrix,
        axis=0,
    )

    similarity_to_mean: list[
        float
    ] = []

    for vector in matrix:
        value = cosine(
            vector,
            mean_context,
        )

        if value is not None:
            similarity_to_mean.append(
                value
            )

    print("\n" + "=" * 80)
    print("SIMILARITY TO GLOBAL MEAN USER CONTEXT")
    print("=" * 80)

    describe(
        "Cosine(user, mean_user)",
        similarity_to_mean,
    )

    popular_embedding = getattr(
        ranker,
        "popular_embedding",
        None,
    )

    if popular_embedding is not None:
        similarity_to_popular: list[
            float
        ] = []

        for vector in matrix:
            value = cosine(
                vector,
                popular_embedding,
            )

            if value is not None:
                similarity_to_popular.append(
                    value
                )

        print("\n" + "=" * 80)
        print("SIMILARITY TO POPULAR EMBEDDING")
        print("=" * 80)

        describe(
            "Cosine(user, popular_embedding)",
            similarity_to_popular,
        )

    print("\n" + "=" * 80)
    print("CONTEXT VARIATION")
    print("=" * 80)

    dimension_std = np.std(
        matrix,
        axis=0,
    )

    print(
        f"Embedding dimensions       : "
        f"{matrix.shape[1]}"
    )

    print(
        f"Mean dimension STD         : "
        f"{np.mean(dimension_std):.8f}"
    )

    print(
        f"Median dimension STD       : "
        f"{np.median(dimension_std):.8f}"
    )

    print(
        f"Maximum dimension STD      : "
        f"{np.max(dimension_std):.8f}"
    )

    centered = (
        matrix
        - np.mean(
            matrix,
            axis=0,
            keepdims=True,
        )
    )

    total_variance = float(
        np.sum(
            centered ** 2
        )
    )

    if total_variance > 0:
        singular_values = np.linalg.svd(
            centered,
            full_matrices=False,
            compute_uv=False,
        )

        variance = (
            singular_values ** 2
        )

        variance_ratio = (
            variance
            / np.sum(variance)
        )

        print(
            f"PC1 variance share         : "
            f"{variance_ratio[0]:.4%}"
        )

        if len(
            variance_ratio
        ) >= 2:
            print(
                f"Top-2 variance share       : "
                f"{np.sum(variance_ratio[:2]):.4%}"
            )

        if len(
            variance_ratio
        ) >= 5:
            print(
                f"Top-5 variance share       : "
                f"{np.sum(variance_ratio[:5]):.4%}"
            )

        if len(
            variance_ratio
        ) >= 10:
            print(
                f"Top-10 variance share      : "
                f"{np.sum(variance_ratio[:10]):.4%}"
            )

    print("\n" + "=" * 80)
    print("NEAREST CONTEXT PAIRS")
    print("=" * 80)

    pair_rows: list[
        tuple[
            float,
            str,
            str,
        ]
    ] = []

    for left in range(
        len(normalized)
    ):
        if not valid[left]:
            continue

        for right in range(
            left + 1,
            len(normalized),
        ):
            if not valid[right]:
                continue

            similarity = float(
                np.dot(
                    normalized[left],
                    normalized[right],
                )
            )

            pair_rows.append(
                (
                    similarity,
                    request_ids[left],
                    request_ids[right],
                )
            )

    pair_rows.sort(
        key=lambda item: -item[0]
    )

    print(
        f"{'Rank':<6}"
        f"{'Cosine':>12}  "
        f"{'Request A':<32}"
        f"{'Request B':<32}"
    )

    print("-" * 84)

    for rank, (
        similarity,
        left_request,
        right_request,
    ) in enumerate(
        pair_rows[:20],
        start=1,
    ):
        print(
            f"{rank:<6}"
            f"{similarity:>12.8f}  "
            f"{left_request:<32}"
            f"{right_request:<32}"
        )

    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()