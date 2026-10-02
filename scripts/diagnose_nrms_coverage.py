from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow.parquet as pq

from ai_pipeline.artifact import load_artifact


# ============================================================
# DEFAULT CONFIG
# ============================================================

DEFAULT_DATASET = Path(
    r"D:\UIT\DATN\mind-small\pilot-embedded.parquet"
)

DEFAULT_ARTIFACT = Path(
     r"D:\UIT\DATN\mind-small\nrms-pilot-v2\model"
)

DEFAULT_K = 10

# Số lần chạy Random baseline.
# 500 là đủ tốt cho pilot hiện tại.
DEFAULT_RANDOM_RUNS = 500

DEFAULT_SEED = 20261002


# ============================================================
# ARTICLE IDENTIFIER
# ============================================================

def article_id(
    row: Mapping[str, Any],
) -> str:
    """
    Lấy ID chuẩn của candidate/article.

    Dataset hiện tại dùng candidate_group và giá trị này
    khớp với article.article_group.

    Các fallback phía sau giúp script vẫn hoạt động nếu
    schema thay đổi nhẹ trong tương lai.
    """

    for key in (
        "candidate_group",
        "post_group",
        "article_group",
        "article_id",
        "news_id",
    ):
        value = row.get(key)

        if value is not None:
            return str(value)

    article = row.get("article")

    if isinstance(article, Mapping):
        for key in (
            "article_group",
            "candidate_group",
            "post_group",
            "article_id",
            "news_id",
        ):
            value = article.get(key)

            if value is not None:
                return str(value)

    value = row.get("sample_id")

    if value is not None:
        return str(value)

    raise ValueError(
        "No usable article identifier found"
    )


# ============================================================
# SAFE POSITION
# ============================================================

def safe_position(
    row: Mapping[str, Any],
) -> int:
    try:
        return int(
            row.get("position") or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0


# ============================================================
# RANK ONE REQUEST
# ============================================================

def rank_request(
    artifact: Any,
    candidates: Sequence[
        Mapping[str, Any]
    ],
    k: int,
) -> list[
    Mapping[str, Any]
]:
    """
    Rank candidate bằng RAW rank scores.

    Không dùng calibrated probability cho ranking,
    vì calibration có thể thay đổi thứ tự nếu scale âm.

    Đây chính là nguyên tắc chúng ta đã sửa trước đó.
    """

    scores = (
        artifact.predict_rank_scores(
            candidates
        )
    )

    if len(scores) != len(candidates):
        raise ValueError(
            "Score count mismatch: "
            f"{len(scores)} scores / "
            f"{len(candidates)} candidates"
        )

    ranked = sorted(
        zip(
            candidates,
            scores,
            strict=True,
        ),
        key=lambda pair: (
            -float(pair[1]),
            safe_position(pair[0]),
            article_id(pair[0]),
        ),
    )

    return [
        row
        for row, _score in ranked[:k]
    ]


# ============================================================
# CONCENTRATION
# ============================================================

def concentration(
    counter: Counter[str],
    n: int,
) -> float:
    total = sum(
        counter.values()
    )

    if total == 0:
        return 0.0

    return (
        sum(
            count
            for _article, count
            in counter.most_common(n)
        )
        / total
    )


# ============================================================
# RANK DATA FOR SPEARMAN
# ============================================================

def rankdata_average(
    values: Sequence[float],
) -> np.ndarray:
    """
    Tạo rank có xử lý tie bằng average rank.

    Không cần scipy.
    """

    values_array = np.asarray(
        values,
        dtype=float,
    )

    order = np.argsort(
        values_array,
        kind="mergesort",
    )

    ranks = np.empty(
        len(values_array),
        dtype=float,
    )

    i = 0

    while i < len(values_array):
        j = i + 1

        while (
            j < len(values_array)
            and values_array[
                order[j]
            ]
            == values_array[
                order[i]
            ]
        ):
            j += 1

        average_rank = (
            (i + 1) + j
        ) / 2.0

        ranks[
            order[i:j]
        ] = average_rank

        i = j

    return ranks


# ============================================================
# PEARSON
# ============================================================

def pearson(
    x: Sequence[float],
    y: Sequence[float],
) -> float | None:

    x_array = np.asarray(
        x,
        dtype=float,
    )

    y_array = np.asarray(
        y,
        dtype=float,
    )

    if (
        len(x_array) < 2
        or len(y_array) < 2
    ):
        return None

    if (
        np.all(
            x_array == x_array[0]
        )
        or np.all(
            y_array == y_array[0]
        )
    ):
        return None

    value = np.corrcoef(
        x_array,
        y_array,
    )[0, 1]

    if not np.isfinite(value):
        return None

    return float(value)


# ============================================================
# SPEARMAN
# ============================================================

def spearman(
    x: Sequence[float],
    y: Sequence[float],
) -> float | None:

    return pearson(
        rankdata_average(x),
        rankdata_average(y),
    )


def fmt_corr(
    value: float | None,
) -> str:

    if value is None:
        return "undefined"

    return f"{value:.6f}"


# ============================================================
# DINIC MAX FLOW
# ============================================================

class Dinic:
    """
    Max-flow dùng để tính chính xác số article unique
    tối đa có thể xuất hiện trong tất cả Top-K.

    Không cần networkx/scipy.
    """

    def __init__(
        self,
        node_count: int,
    ) -> None:

        self.graph: list[
            list[list[int]]
        ] = [
            []
            for _ in range(
                node_count
            )
        ]

    def add_edge(
        self,
        source: int,
        target: int,
        capacity: int,
    ) -> None:

        forward = [
            target,
            len(
                self.graph[target]
            ),
            int(capacity),
        ]

        reverse = [
            source,
            len(
                self.graph[source]
            ),
            0,
        ]

        self.graph[
            source
        ].append(
            forward
        )

        self.graph[
            target
        ].append(
            reverse
        )

    def max_flow(
        self,
        source: int,
        sink: int,
    ) -> int:

        total = 0

        while True:

            level = [
                -1
            ] * len(
                self.graph
            )

            level[source] = 0

            queue: deque[int] = deque(
                [source]
            )

            while queue:

                node = queue.popleft()

                for (
                    target,
                    _reverse,
                    capacity,
                ) in self.graph[node]:

                    if (
                        capacity > 0
                        and level[target] < 0
                    ):

                        level[target] = (
                            level[node] + 1
                        )

                        queue.append(
                            target
                        )

            if level[sink] < 0:
                return total

            work = [
                0
            ] * len(
                self.graph
            )

            def dfs(
                node: int,
                amount: int,
            ) -> int:

                if node == sink:
                    return amount

                while (
                    work[node]
                    < len(
                        self.graph[node]
                    )
                ):

                    edge = self.graph[
                        node
                    ][
                        work[node]
                    ]

                    (
                        target,
                        reverse_index,
                        capacity,
                    ) = edge

                    if (
                        capacity > 0
                        and level[target]
                        == level[node] + 1
                    ):

                        pushed = dfs(
                            target,
                            min(
                                amount,
                                capacity,
                            ),
                        )

                        if pushed:

                            edge[2] -= pushed

                            self.graph[
                                target
                            ][
                                reverse_index
                            ][2] += pushed

                            return pushed

                    work[node] += 1

                return 0

            while True:

                pushed = dfs(
                    source,
                    10**9,
                )

                if pushed == 0:
                    break

                total += pushed


# ============================================================
# EXACT MAXIMUM REACHABLE COVERAGE
# ============================================================

def maximum_reachable_unique(
    grouped: Mapping[
        str,
        Sequence[
            Mapping[str, Any]
        ],
    ],
    catalog_ids: Sequence[str],
    k: int,
) -> int:
    """
    Tính chính xác số article unique tối đa có thể được chọn
    với candidate pool hiện tại.

    Graph:

        source
          |
          v
       article
          |
          v
       request
          |
          v
         sink

    source -> article:
        capacity = 1

    article -> request:
        capacity = 1 nếu article xuất hiện trong request

    request -> sink:
        capacity = min(K, candidate count)

    Vì mỗi article chỉ cần được chọn một lần để đóng góp
    vào Coverage, max-flow chính là số article unique tối đa.
    """

    articles = sorted(
        set(catalog_ids)
    )

    requests = sorted(
        grouped
    )

    article_index = {
        value: index
        for index, value
        in enumerate(articles)
    }

    request_index = {
        value: index
        for index, value
        in enumerate(requests)
    }

    source = 0

    article_offset = 1

    request_offset = (
        article_offset
        + len(articles)
    )

    sink = (
        request_offset
        + len(requests)
    )

    flow = Dinic(
        sink + 1
    )

    # Mỗi article chỉ đóng góp tối đa 1
    # vào số unique article.
    for aid in articles:

        flow.add_edge(
            source,
            article_offset
            + article_index[aid],
            1,
        )

    for request_id in requests:

        unique_ids = {
            article_id(row)
            for row
            in grouped[
                request_id
            ]
        }

        request_node = (
            request_offset
            + request_index[
                request_id
            ]
        )

        for aid in unique_ids:

            flow.add_edge(
                article_offset
                + article_index[aid],
                request_node,
                1,
            )

        flow.add_edge(
            request_node,
            sink,
            min(
                k,
                len(unique_ids),
            ),
        )

    return flow.max_flow(
        source,
        sink,
    )


# ============================================================
# ONE RANDOM BASELINE RUN
# ============================================================

def random_once(
    grouped: Mapping[
        str,
        Sequence[
            Mapping[str, Any]
        ],
    ],
    catalog_size: int,
    k: int,
    rng: np.random.Generator,
) -> dict[str, float]:

    counter: Counter[str] = Counter()

    for request_id in sorted(
        grouped
    ):

        candidates = list(
            grouped[
                request_id
            ]
        )

        take = min(
            k,
            len(candidates),
        )

        if take == 0:
            continue

        indexes = rng.choice(
            len(candidates),
            size=take,
            replace=False,
        )

        for index in np.atleast_1d(
            indexes
        ):

            aid = article_id(
                candidates[
                    int(index)
                ]
            )

            counter[aid] += 1

    unique_selected = len(
        counter
    )

    return {
        "coverage": (
            unique_selected
            / catalog_size
            if catalog_size
            else 0.0
        ),
        "unique_selected":
            float(
                unique_selected
            ),
        "top10_concentration":
            concentration(
                counter,
                10,
            ),
        "top20_concentration":
            concentration(
                counter,
                20,
            ),
        "max_selections_per_article":
            float(
                max(
                    counter.values(),
                    default=0,
                )
            ),
    }


# ============================================================
# RANDOM DISTRIBUTION
# ============================================================

def distribution(
    values: Sequence[float],
) -> dict[str, float]:

    x = np.asarray(
        values,
        dtype=float,
    )

    return {
        "mean":
            float(
                x.mean()
            ),
        "std":
            float(
                x.std(ddof=1)
            )
            if len(x) > 1
            else 0.0,
        "p05":
            float(
                np.quantile(
                    x,
                    0.05,
                )
            ),
        "p50":
            float(
                np.quantile(
                    x,
                    0.50,
                )
            ),
        "p95":
            float(
                np.quantile(
                    x,
                    0.95,
                )
            ),
        "min":
            float(
                x.min()
            ),
        "max":
            float(
                x.max()
            ),
    }


# ============================================================
# ARGUMENTS
# ============================================================

def build_parser() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(
        description=(
            "NRMS coverage, random baseline, "
            "candidate opportunity and maximum "
            "reachable coverage diagnostic."
        )
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
    )

    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT,
    )

    parser.add_argument(
        "--k",
        type=int,
        default=DEFAULT_K,
    )

    parser.add_argument(
        "--random-runs",
        type=int,
        default=DEFAULT_RANDOM_RUNS,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )

    return parser


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    args = (
        build_parser()
        .parse_args()
    )

    if args.k <= 0:
        raise ValueError(
            "--k must be > 0"
        )

    if args.random_runs <= 0:
        raise ValueError(
            "--random-runs must be > 0"
        )

    if not args.dataset.is_file():
        raise FileNotFoundError(
            f"Dataset not found: "
            f"{args.dataset}"
        )

    if not args.artifact.exists():
        raise FileNotFoundError(
            f"Artifact not found: "
            f"{args.artifact}"
        )

    print(
        "=" * 80
    )

    print(
        "NRMS COVERAGE / RANDOM BASELINE / "
        "MAX-REACHABLE DIAGNOSTIC"
    )

    print(
        "=" * 80
    )

    # --------------------------------------------------------
    # LOAD DATASET
    # --------------------------------------------------------

    print(
        "\nLoading dataset..."
    )

    table = pq.read_table(
        args.dataset
    )

    rows = table.to_pylist()

    test_rows = [
        row
        for row in rows
        if row.get("split")
        == "test"
    ]

    grouped: dict[
        str,
        list[
            dict[str, Any]
        ],
    ] = defaultdict(list)

    for row in test_rows:

        request_group = str(
            row[
                "request_group"
            ]
        )

        grouped[
            request_group
        ].append(
            row
        )

    request_sizes = np.asarray(
        [
            len(values)
            for values
            in grouped.values()
        ],
        dtype=int,
    )

    catalog_ids = sorted(
        {
            article_id(row)
            for row
            in test_rows
        }
    )

    catalog_size = len(
        catalog_ids
    )

    expected_slots = sum(
        min(
            args.k,
            len(values),
        )
        for values
        in grouped.values()
    )

    maximum_slots = (
        len(grouped)
        * args.k
    )

    missing_slots = (
        maximum_slots
        - expected_slots
    )

    # --------------------------------------------------------
    # DUPLICATE CHECK
    # --------------------------------------------------------

    duplicate_rows = 0
    duplicate_requests = 0

    for candidates in grouped.values():

        ids = [
            article_id(row)
            for row
            in candidates
        ]

        duplicates = (
            len(ids)
            - len(set(ids))
        )

        if duplicates > 0:

            duplicate_requests += 1
            duplicate_rows += duplicates

    print(
        "\n"
        + "=" * 80
    )

    print(
        "DATASET"
    )

    print(
        "=" * 80
    )

    print(
        f"Total dataset rows         : "
        f"{len(rows)}"
    )

    print(
        f"Test rows                  : "
        f"{len(test_rows)}"
    )

    print(
        f"Test requests              : "
        f"{len(grouped)}"
    )

    print(
        f"Catalog articles           : "
        f"{catalog_size}"
    )

    print(
        f"Minimum candidates         : "
        f"{int(request_sizes.min())}"
    )

    print(
        f"Maximum candidates         : "
        f"{int(request_sizes.max())}"
    )

    print(
        f"Mean candidates            : "
        f"{request_sizes.mean():.4f}"
    )

    print(
        f"Requests < {args.k} candidates  : "
        f"{int((request_sizes < args.k).sum())}"
    )

    print(
        f"Expected Top-{args.k} slots      : "
        f"{expected_slots}"
    )

    print(
        f"Maximum Top-{args.k} slots       : "
        f"{maximum_slots}"
    )

    print(
        f"Missing Top-{args.k} slots       : "
        f"{missing_slots}"
    )

    print(
        f"Duplicate candidate reqs   : "
        f"{duplicate_requests}"
    )

    print(
        f"Duplicate candidate rows   : "
        f"{duplicate_rows}"
    )

    # --------------------------------------------------------
    # LOAD MODEL
    # --------------------------------------------------------

    print(
        "\nLoading NRMS artifact..."
    )

    artifact = load_artifact(
        args.artifact
    )

    selected_counter: Counter[str] = (
        Counter()
    )

    opportunity_counter: Counter[str] = (
        Counter()
    )

    # --------------------------------------------------------
    # SCORE NRMS
    # --------------------------------------------------------

    print(
        "\nScoring NRMS requests..."
    )

    for index, request_id in enumerate(
        sorted(grouped),
        start=1,
    ):

        candidates = grouped[
            request_id
        ]

        # Opportunity được tính theo request,
        # không phải row.
        for aid in {
            article_id(row)
            for row
            in candidates
        }:

            opportunity_counter[
                aid
            ] += 1

        selected_rows = rank_request(
            artifact,
            candidates,
            args.k,
        )

        for row in selected_rows:

            selected_counter[
                article_id(row)
            ] += 1

        if (
            index % 25 == 0
            or index
            == len(grouped)
        ):

            print(
                f"Processed "
                f"{index}/"
                f"{len(grouped)} "
                f"requests"
            )

    # --------------------------------------------------------
    # NRMS METRICS
    # --------------------------------------------------------

    nrms_slots = sum(
        selected_counter.values()
    )

    nrms_unique = len(
        selected_counter
    )

    nrms_coverage = (
        nrms_unique
        / catalog_size
        if catalog_size
        else 0.0
    )

    nrms_top10 = concentration(
        selected_counter,
        10,
    )

    nrms_top20 = concentration(
        selected_counter,
        20,
    )

    nrms_max = max(
        selected_counter.values(),
        default=0,
    )

    unknown_ids = sorted(
        set(
            selected_counter
        )
        - set(
            catalog_ids
        )
    )

    accounting_pass = (
        nrms_slots
        == expected_slots
    )

    print(
        "\n"
        + "=" * 80
    )

    print(
        "NRMS RESULT"
    )

    print(
        "=" * 80
    )

    print(
        f"Unique selected            : "
        f"{nrms_unique}"
    )

    print(
        f"Coverage                   : "
        f"{nrms_coverage:.6f} "
        f"({nrms_coverage:.2%})"
    )

    print(
        f"Top-10 concentration       : "
        f"{nrms_top10:.4%}"
    )

    print(
        f"Top-20 concentration       : "
        f"{nrms_top20:.4%}"
    )

    print(
        f"Max selections/article     : "
        f"{nrms_max}"
    )

    print(
        f"Top-K accounting           : "
        f"{'PASS' if accounting_pass else 'FAIL'}"
    )

    print(
        f"Unknown selected IDs       : "
        f"{len(unknown_ids)}"
    )

    # --------------------------------------------------------
    # CORRELATION
    # --------------------------------------------------------

    availability: list[float] = []
    selections: list[float] = []
    select_rates: list[float] = []

    for aid in catalog_ids:

        available = (
            opportunity_counter.get(
                aid,
                0,
            )
        )

        selected = (
            selected_counter.get(
                aid,
                0,
            )
        )

        rate = (
            selected / available
            if available
            else 0.0
        )

        availability.append(
            float(
                available
            )
        )

        selections.append(
            float(
                selected
            )
        )

        select_rates.append(
            float(
                rate
            )
        )

    correlations = {
        "pearson_available_selected":
            pearson(
                availability,
                selections,
            ),

        "spearman_available_selected":
            spearman(
                availability,
                selections,
            ),

        "pearson_available_select_rate":
            pearson(
                availability,
                select_rates,
            ),

        "spearman_available_select_rate":
            spearman(
                availability,
                select_rates,
            ),
    }

    print(
        "\n"
        + "=" * 80
    )

    print(
        "OPPORTUNITY / SELECTION CORRELATION"
    )

    print(
        "=" * 80
    )

    print(
        "Pearson  Available vs Selected   : "
        + fmt_corr(
            correlations[
                "pearson_available_selected"
            ]
        )
    )

    print(
        "Spearman Available vs Selected   : "
        + fmt_corr(
            correlations[
                "spearman_available_selected"
            ]
        )
    )

    print(
        "Pearson  Available vs SelectRate : "
        + fmt_corr(
            correlations[
                "pearson_available_select_rate"
            ]
        )
    )

    print(
        "Spearman Available vs SelectRate : "
        + fmt_corr(
            correlations[
                "spearman_available_select_rate"
            ]
        )
    )

    # --------------------------------------------------------
    # TOP SELECTED
    # --------------------------------------------------------

    print(
        "\n"
        + "=" * 80
    )

    print(
        "30 MOST SELECTED ARTICLES"
    )

    print(
        "=" * 80
    )

    print(
        f"{'Rank':<5}"
        f"{'Article':<66}"
        f"{'Selected':>9}"
        f"{'Available':>11}"
        f"{'Rate':>10}"
    )

    print(
        "-" * 101
    )

    for (
        rank,
        (
            aid,
            selected,
        ),
    ) in enumerate(
        selected_counter.most_common(
            30
        ),
        start=1,
    ):

        available = (
            opportunity_counter.get(
                aid,
                0,
            )
        )

        rate = (
            selected / available
            if available
            else 0.0
        )

        print(
            f"{rank:<5}"
            f"{aid:<66}"
            f"{selected:>9}"
            f"{available:>11}"
            f"{rate:>9.2%}"
        )

    # --------------------------------------------------------
    # MOST OPPORTUNITIES
    # --------------------------------------------------------

    print(
        "\n"
        + "=" * 80
    )

    print(
        "20 ARTICLES WITH MOST CANDIDATE OPPORTUNITIES"
    )

    print(
        "=" * 80
    )

    print(
        f"{'Rank':<5}"
        f"{'Article':<66}"
        f"{'Available':>11}"
        f"{'Selected':>10}"
        f"{'Rate':>10}"
    )

    print(
        "-" * 102
    )

    for (
        rank,
        (
            aid,
            available,
        ),
    ) in enumerate(
        opportunity_counter.most_common(
            20
        ),
        start=1,
    ):

        selected = (
            selected_counter.get(
                aid,
                0,
            )
        )

        rate = (
            selected / available
            if available
            else 0.0
        )

        print(
            f"{rank:<5}"
            f"{aid:<66}"
            f"{available:>11}"
            f"{selected:>10}"
            f"{rate:>9.2%}"
        )

    # --------------------------------------------------------
    # EXACT MAXIMUM REACHABLE COVERAGE
    # --------------------------------------------------------

    print(
        "\nComputing exact maximum "
        "reachable coverage..."
    )

    oracle_unique = (
        maximum_reachable_unique(
            grouped,
            catalog_ids,
            args.k,
        )
    )

    oracle_coverage = (
        oracle_unique
        / catalog_size
        if catalog_size
        else 0.0
    )

    print(
        f"Maximum reachable unique  : "
        f"{oracle_unique}"
    )

    print(
        f"Maximum reachable coverage: "
        f"{oracle_coverage:.6f} "
        f"({oracle_coverage:.2%})"
    )

    # --------------------------------------------------------
    # RANDOM BASELINE
    # --------------------------------------------------------

    print(
        f"\nRunning "
        f"{args.random_runs} "
        f"random baseline runs..."
    )

    rng = np.random.default_rng(
        args.seed
    )

    random_values: dict[
        str,
        list[float],
    ] = {
        "coverage": [],
        "unique_selected": [],
        "top10_concentration": [],
        "top20_concentration": [],
        "max_selections_per_article": [],
    }

    for run in range(
        1,
        args.random_runs + 1,
    ):

        result = random_once(
            grouped,
            catalog_size,
            args.k,
            rng,
        )

        for (
            key,
            value,
        ) in result.items():

            random_values[
                key
            ].append(
                float(value)
            )

        if (
            run % 100 == 0
            or run
            == args.random_runs
        ):

            print(
                f"Random run "
                f"{run}/"
                f"{args.random_runs}"
            )

    random_summary = {
        key:
            distribution(
                values
            )

        for (
            key,
            values,
        ) in random_values.items()
    }

    # --------------------------------------------------------
    # COMPARISON TABLE
    # --------------------------------------------------------

    print(
        "\n"
        + "=" * 80
    )

    print(
        "NRMS VS RANDOM VS MAXIMUM REACHABLE"
    )

    print(
        "=" * 80
    )

    print(
        f"{'Metric':<28}"
        f"{'NRMS':>12}"
        f"{'RandomMean':>14}"
        f"{'P05':>12}"
        f"{'P50':>12}"
        f"{'P95':>12}"
        f"{'Oracle':>12}"
    )

    print(
        "-" * 102
    )

    def show_row(
        name: str,
        nrms: float,
        random_key: str,
        oracle: float | None = None,
        percent: bool = False,
    ) -> None:

        stats = random_summary[
            random_key
        ]

        if percent:

            def formatter(
                value: float,
            ) -> str:
                return f"{value:.2%}"

        else:

            def formatter(
                value: float,
            ) -> str:
                return f"{value:.2f}"

        oracle_text = (
            "-"
            if oracle is None
            else formatter(
                oracle
            )
        )

        print(
            f"{name:<28}"
            f"{formatter(nrms):>12}"
            f"{formatter(stats['mean']):>14}"
            f"{formatter(stats['p05']):>12}"
            f"{formatter(stats['p50']):>12}"
            f"{formatter(stats['p95']):>12}"
            f"{oracle_text:>12}"
        )

    show_row(
        "Coverage",
        nrms_coverage,
        "coverage",
        oracle_coverage,
        True,
    )

    show_row(
        "Unique selected",
        float(
            nrms_unique
        ),
        "unique_selected",
        float(
            oracle_unique
        ),
    )

    show_row(
        "Top-10 concentration",
        nrms_top10,
        "top10_concentration",
        percent=True,
    )

    show_row(
        "Top-20 concentration",
        nrms_top20,
        "top20_concentration",
        percent=True,
    )

    show_row(
        "Max selections/article",
        float(
            nrms_max
        ),
        "max_selections_per_article",
    )

    # --------------------------------------------------------
    # COVERAGE GAP
    # --------------------------------------------------------

    random_mean = (
        random_summary[
            "coverage"
        ][
            "mean"
        ]
    )

    random_std = (
        random_summary[
            "coverage"
        ][
            "std"
        ]
    )

    z_score = (
        (
            nrms_coverage
            - random_mean
        )
        / random_std

        if random_std > 0
        else None
    )

    print(
        "\n"
        + "=" * 80
    )

    print(
        "COVERAGE GAP"
    )

    print(
        "=" * 80
    )

    print(
        f"NRMS coverage              : "
        f"{nrms_coverage:.6f} "
        f"({nrms_coverage:.2%})"
    )

    print(
        f"Random mean coverage       : "
        f"{random_mean:.6f} "
        f"({random_mean:.2%})"
    )

    print(
        f"Maximum reachable coverage : "
        f"{oracle_coverage:.6f} "
        f"({oracle_coverage:.2%})"
    )

    print(
        f"NRMS - Random mean         : "
        f"{nrms_coverage - random_mean:+.6f}"
    )

    print(
        f"NRMS - Maximum reachable   : "
        f"{nrms_coverage - oracle_coverage:+.6f}"
    )

    print(
        "NRMS z-score vs random     : "
        + (
            "undefined"
            if z_score is None
            else f"{z_score:.4f}"
        )
    )

    # --------------------------------------------------------
    # JSON REPORT
    # --------------------------------------------------------

    report: dict[str, Any] = {

        "config": {

            "dataset":
                str(
                    args.dataset
                ),

            "artifact":
                str(
                    args.artifact
                ),

            "k":
                args.k,

            "random_runs":
                args.random_runs,

            "seed":
                args.seed,
        },

        "dataset": {

            "total_rows":
                len(rows),

            "test_rows":
                len(test_rows),

            "requests":
                len(grouped),

            "catalog_articles":
                catalog_size,

            "minimum_candidates":
                int(
                    request_sizes.min()
                ),

            "maximum_candidates":
                int(
                    request_sizes.max()
                ),

            "mean_candidates":
                float(
                    request_sizes.mean()
                ),

            "requests_below_k":
                int(
                    (
                        request_sizes
                        < args.k
                    ).sum()
                ),

            "expected_top_k_slots":
                expected_slots,

            "maximum_top_k_slots":
                maximum_slots,

            "missing_top_k_slots":
                missing_slots,

            "duplicate_candidate_requests":
                duplicate_requests,

            "duplicate_candidate_rows":
                duplicate_rows,
        },

        "nrms": {

            "coverage":
                nrms_coverage,

            "unique_selected":
                nrms_unique,

            "top10_concentration":
                nrms_top10,

            "top20_concentration":
                nrms_top20,

            "max_selections_per_article":
                nrms_max,

            "actual_top_k_slots":
                nrms_slots,

            "top_k_accounting_pass":
                accounting_pass,

            "unknown_selected_ids":
                unknown_ids,
        },

        "correlations":
            correlations,

        "random":
            random_summary,

        "maximum_reachable": {

            "unique_selected":
                oracle_unique,

            "coverage":
                oracle_coverage,
        },

        "coverage_gap": {

            "nrms_minus_random_mean":
                nrms_coverage
                - random_mean,

            "nrms_minus_maximum_reachable":
                nrms_coverage
                - oracle_coverage,

            "nrms_zscore_vs_random":
                z_score,
        },
    }

    if args.output is not None:

        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.output.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            "\nJSON report saved:"
        )

        print(
            args.output
        )

    print(
        "\n"
        + "=" * 80
    )

    print(
        "DIAGNOSTIC COMPLETE"
    )

    print(
        "=" * 80
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )