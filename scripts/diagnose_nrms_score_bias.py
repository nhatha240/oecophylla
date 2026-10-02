from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from statistics import median
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

K = 10


def candidate_id(
    row: Mapping[str, Any],
) -> str:
    value = row.get("candidate_group")

    if value is not None:
        return str(value)

    article = row.get("article") or {}

    for key in (
        "article_group",
        "post_group",
        "article_id",
        "news_id",
        "id",
    ):
        value = article.get(key)

        if value is not None:
            return str(value)

    return str(row.get("sample_id", "unknown"))


def candidate_embedding(
    row: Mapping[str, Any],
) -> np.ndarray | None:
    article = row.get("article") or {}

    embedding = article.get("embedding")

    if embedding is None:
        return None

    vector = np.asarray(
        embedding,
        dtype=float,
    )

    if vector.ndim != 1:
        return None

    if not np.all(np.isfinite(vector)):
        return None

    return vector


def rank_average(
    values: Sequence[float],
) -> np.ndarray:
    """
    Average-rank implementation for Spearman correlation.
    Handles ties without scipy.
    """

    array = np.asarray(
        values,
        dtype=float,
    )

    order = np.argsort(
        array,
        kind="mergesort",
    )

    ranks = np.empty(
        len(array),
        dtype=float,
    )

    i = 0

    while i < len(order):
        j = i + 1

        while (
            j < len(order)
            and array[order[j]]
            == array[order[i]]
        ):
            j += 1

        average_rank = (
            i + j - 1
        ) / 2.0 + 1.0

        ranks[order[i:j]] = average_rank

        i = j

    return ranks


def pearson(
    x: Sequence[float],
    y: Sequence[float],
) -> float | None:
    if len(x) < 2 or len(y) < 2:
        return None

    xv = np.asarray(
        x,
        dtype=float,
    )

    yv = np.asarray(
        y,
        dtype=float,
    )

    if (
        np.std(xv) == 0.0
        or np.std(yv) == 0.0
    ):
        return None

    return float(
        np.corrcoef(xv, yv)[0, 1]
    )


def spearman(
    x: Sequence[float],
    y: Sequence[float],
) -> float | None:
    if len(x) < 2 or len(y) < 2:
        return None

    return pearson(
        rank_average(x),
        rank_average(y),
    )


def show_corr(
    name: str,
    x: Sequence[float],
    y: Sequence[float],
) -> None:
    p = pearson(x, y)
    s = spearman(x, y)

    print(
        f"{name:<46}"
        f" Pearson={p if p is not None else 'NA'}"
        f"  Spearman={s if s is not None else 'NA'}"
    )


def main() -> None:
    print("=" * 80)
    print("NRMS SCORE / CANDIDATE BIAS DIAGNOSTIC")
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

    print("\nLoading artifact...")

    artifact = load_artifact(
        ARTIFACT
    )

    score_by_candidate: dict[
        str,
        list[float],
    ] = defaultdict(list)

    norm_by_candidate: dict[
        str,
        list[float],
    ] = defaultdict(list)

    opportunities: dict[
        str,
        int,
    ] = defaultdict(int)

    selections: dict[
        str,
        int,
    ] = defaultdict(int)

    request_score_std: list[
        float
    ] = []

    request_score_range: list[
        float
    ] = []

    all_scores: list[
        float
    ] = []

    print("\nScoring requests...")

    for index, request_group in enumerate(
        sorted(grouped),
        start=1,
    ):
        candidates = grouped[
            request_group
        ]

        scores = (
            artifact.predict_rank_scores(
                candidates
            )
        )

        if len(scores) != len(candidates):
            raise RuntimeError(
                "Score count does not match "
                "candidate count."
            )

        score_array = np.asarray(
            scores,
            dtype=float,
        )

        if len(score_array):
            request_score_std.append(
                float(
                    np.std(score_array)
                )
            )

            request_score_range.append(
                float(
                    np.max(score_array)
                    - np.min(score_array)
                )
            )

        ranked = sorted(
            zip(
                candidates,
                scores,
            ),
            key=lambda pair: (
                -float(pair[1]),
                int(
                    pair[0].get(
                        "position"
                    )
                    or 0
                ),
                candidate_id(
                    pair[0]
                ),
            ),
        )

        top = ranked[:K]

        request_seen: set[str] = set()

        for row, score in zip(
            candidates,
            scores,
            strict=True,
        ):
            cid = candidate_id(
                row
            )

            value = float(
                score
            )

            score_by_candidate[
                cid
            ].append(value)

            all_scores.append(
                value
            )

            if cid not in request_seen:
                opportunities[
                    cid
                ] += 1

                request_seen.add(
                    cid
                )

            embedding = (
                candidate_embedding(
                    row
                )
            )

            if embedding is not None:
                norm_by_candidate[
                    cid
                ].append(
                    float(
                        np.linalg.norm(
                            embedding
                        )
                    )
                )

        for row, _score in top:
            selections[
                candidate_id(row)
            ] += 1

        if index % 25 == 0:
            print(
                f"Processed "
                f"{index}/"
                f"{len(grouped)} requests"
            )

    candidates = sorted(
        score_by_candidate
    )

    mean_scores: list[
        float
    ] = []

    selected_values: list[
        float
    ] = []

    opportunity_values: list[
        float
    ] = []

    selection_rates: list[
        float
    ] = []

    embedding_norms: list[
        float
    ] = []

    norm_mean_scores: list[
        float
    ] = []

    norm_selected: list[
        float
    ] = []

    norm_selection_rates: list[
        float
    ] = []

    candidate_rows: list[
        tuple[
            str,
            int,
            int,
            float,
            float,
            float,
            float,
        ]
    ] = []

    for cid in candidates:
        scores = score_by_candidate[
            cid
        ]

        available = opportunities.get(
            cid,
            0,
        )

        selected = selections.get(
            cid,
            0,
        )

        rate = (
            selected / available
            if available
            else 0.0
        )

        mean_score = float(
            np.mean(scores)
        )

        std_score = float(
            np.std(scores)
        )

        norms = norm_by_candidate.get(
            cid,
            [],
        )

        mean_norm = (
            float(np.mean(norms))
            if norms
            else float("nan")
        )

        mean_scores.append(
            mean_score
        )

        selected_values.append(
            float(selected)
        )

        opportunity_values.append(
            float(available)
        )

        selection_rates.append(
            rate
        )

        if np.isfinite(
            mean_norm
        ):
            embedding_norms.append(
                mean_norm
            )

            norm_mean_scores.append(
                mean_score
            )

            norm_selected.append(
                float(selected)
            )

            norm_selection_rates.append(
                rate
            )

        candidate_rows.append(
            (
                cid,
                available,
                selected,
                rate,
                mean_score,
                std_score,
                mean_norm,
            )
        )

    print("\n" + "=" * 80)
    print("REQUEST-LEVEL SCORE SPREAD")
    print("=" * 80)

    if request_score_std:
        print(
            "Median request score STD   : "
            f"{median(request_score_std):.8f}"
        )

        print(
            "Mean request score STD     : "
            f"{np.mean(request_score_std):.8f}"
        )

    if request_score_range:
        print(
            "Median request score range : "
            f"{median(request_score_range):.8f}"
        )

        print(
            "Mean request score range   : "
            f"{np.mean(request_score_range):.8f}"
        )

    print("\n" + "=" * 80)
    print("CANDIDATE CORRELATIONS")
    print("=" * 80)

    show_corr(
        "Opportunities vs Selected",
        opportunity_values,
        selected_values,
    )

    show_corr(
        "Mean rank score vs Selected",
        mean_scores,
        selected_values,
    )

    show_corr(
        "Mean rank score vs Selection rate",
        mean_scores,
        selection_rates,
    )

    if embedding_norms:
        show_corr(
            "Embedding norm vs Mean rank score",
            embedding_norms,
            norm_mean_scores,
        )

        show_corr(
            "Embedding norm vs Selected",
            embedding_norms,
            norm_selected,
        )

        show_corr(
            "Embedding norm vs Selection rate",
            embedding_norms,
            norm_selection_rates,
        )

    print("\n" + "=" * 80)
    print("EMBEDDING NORM DISTRIBUTION")
    print("=" * 80)

    if embedding_norms:
        norm_array = np.asarray(
            embedding_norms,
            dtype=float,
        )

        print(
            f"Candidates with embedding : "
            f"{len(norm_array)}"
        )

        print(
            f"Minimum norm              : "
            f"{np.min(norm_array):.8f}"
        )

        print(
            f"P05 norm                  : "
            f"{np.percentile(norm_array, 5):.8f}"
        )

        print(
            f"Median norm               : "
            f"{np.median(norm_array):.8f}"
        )

        print(
            f"Mean norm                 : "
            f"{np.mean(norm_array):.8f}"
        )

        print(
            f"P95 norm                  : "
            f"{np.percentile(norm_array, 95):.8f}"
        )

        print(
            f"Maximum norm              : "
            f"{np.max(norm_array):.8f}"
        )

        minimum = float(
            np.min(norm_array)
        )

        maximum = float(
            np.max(norm_array)
        )

        if minimum > 0:
            print(
                "Max / Min norm            : "
                f"{maximum / minimum:.4f}x"
            )

    print("\n" + "=" * 80)
    print("CANDIDATE IDENTITY VARIANCE DECOMPOSITION")
    print("=" * 80)

    all_score_array = np.asarray(
        all_scores,
        dtype=float,
    )

    grand_mean = float(
        np.mean(all_score_array)
    )

    total_ss = float(
        np.sum(
            (
                all_score_array
                - grand_mean
            )
            ** 2
        )
    )

    between_ss = 0.0

    within_ss = 0.0

    for cid in candidates:
        values = np.asarray(
            score_by_candidate[cid],
            dtype=float,
        )

        candidate_mean = float(
            np.mean(values)
        )

        between_ss += (
            len(values)
            * (
                candidate_mean
                - grand_mean
            )
            ** 2
        )

        within_ss += float(
            np.sum(
                (
                    values
                    - candidate_mean
                )
                ** 2
            )
        )

    identity_share = (
        between_ss / total_ss
        if total_ss > 0
        else 0.0
    )

    print(
        f"Total score variance SS    : "
        f"{total_ss:.8f}"
    )

    print(
        f"Between-candidate SS       : "
        f"{between_ss:.8f}"
    )

    print(
        f"Within-candidate SS        : "
        f"{within_ss:.8f}"
    )

    print(
        "Candidate identity share   : "
        f"{identity_share:.4%}"
    )

    print("\n" + "=" * 80)
    print("TOP 30 BY SELECTION COUNT")
    print("=" * 80)

    candidate_rows.sort(
        key=lambda item: (
            -item[2],
            -item[3],
            item[0],
        )
    )

    print(
        f"{'Rank':<5}"
        f"{'Candidate':<44}"
        f"{'Avail':>7}"
        f"{'Select':>8}"
        f"{'Rate':>9}"
        f"{'MeanScore':>14}"
        f"{'ScoreSTD':>14}"
        f"{'EmbNorm':>14}"
    )

    print("-" * 116)

    for rank, row in enumerate(
        candidate_rows[:30],
        start=1,
    ):
        (
            cid,
            available,
            selected,
            rate,
            mean_score,
            std_score,
            mean_norm,
        ) = row

        norm_text = (
            f"{mean_norm:.6f}"
            if np.isfinite(mean_norm)
            else "NA"
        )

        print(
            f"{rank:<5}"
            f"{cid:<44}"
            f"{available:>7}"
            f"{selected:>8}"
            f"{rate:>8.2%}"
            f"{mean_score:>14.6f}"
            f"{std_score:>14.6f}"
            f"{norm_text:>14}"
        )

    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()