"""Benchmark a frozen NRMS artifact on a registered, evaluation-only MIND holdout."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import numpy as np
from threadpoolctl import threadpool_info, threadpool_limits

from workers.nlp_worker.app.content_features import ENCODER_VERSION

from .artifact import LoadedNRMSArtifact, load_artifact, sha256_file
from .finetune import mean_pool_scores, request_metrics, score_requests
from .mind_large import cached_embeddings


def metrics_for_request(labels, scores):
    labels, scores = np.asarray(labels), np.asarray(scores, dtype=float)
    if (
        labels.ndim != 1
        or scores.shape != labels.shape
        or len(labels) < 2
        or not np.isin(labels, [0, 1]).all()
        or not np.isfinite(scores).all()
    ):
        raise ValueError("metrics require aligned binary labels and finite predictions")
    result = request_metrics(labels, scores)
    ranked = labels[np.argsort(-scores, kind="stable")]
    relevant = int(labels.sum())
    for k in (5, 10):
        hits = int(ranked[:k].sum())
        result[f"precision_at_{k}"] = hits / k
        result[f"recall_at_{k}"] = hits / relevant if relevant else 0.0
        result[f"hit_at_{k}"] = float(hits > 0)
    return result


def validate_holdout(requests, vectors, *, dimension, history_limit):
    if (
        not requests
        or vectors.ndim != 2
        or vectors.shape[1] != dimension
        or not np.isfinite(vectors).all()
        or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=0.001)
    ):
        raise ValueError("invalid holdout or embedding matrix")
    groups = set()
    for row in requests:
        if row.get("split") != "test":
            raise ValueError("benchmark accepts test requests only")
        if not row.get("request_group") or not row.get("user_group"):
            raise ValueError("stable request and user identities are required")
        if row["request_group"] in groups:
            raise ValueError("duplicate benchmark request")
        groups.add(row["request_group"])
        candidates, history, labels = row["candidates"], row["history"], row["labels"]
        if (
            len(candidates) < 2
            or len(candidates) != len(labels)
            or len(set(candidates)) != len(candidates)
            or len(history) > history_limit
            or not np.isin(labels, [0, 1]).all()
        ):
            raise ValueError("invalid request candidates, labels or history")
        if any(
            not isinstance(index, int) or index < 0 or index >= len(vectors)
            for index in candidates + history
        ):
            raise ValueError("article index is outside the aligned embedding matrix")


def score_models(requests, vectors, ranker, *, seed):
    random_scores = []
    for row in requests:
        material = f"{seed}:{row['request_group']}".encode()
        request_seed = int.from_bytes(hashlib.sha256(material).digest()[:8])
        random_scores.append(
            np.random.default_rng(request_seed).random(len(row["candidates"]))
        )
    popular = ranker.popular_embedding
    if popular is None:
        popular = np.zeros(ranker.architecture.embedding_dimension)
    return {
        "logged_order": [
            -np.arange(len(row["candidates"]), dtype=float) for row in requests
        ],
        "random": random_scores,
        "semantic_mean_pool": mean_pool_scores(requests, vectors, popular),
        "nrms": score_requests(ranker, requests, vectors),
    }


def _aggregate(requests, individual, scores, vectors):
    result = {}
    for key in individual[0]:
        values = [row[key] for row in individual if row[key] is not None]
        result[key] = float(np.mean(values)) if values else None
    catalog = {article for row in requests for article in row["candidates"]}
    result.update(
        requests=len(requests),
        unique_users=len({row["user_group"] for row in requests}),
        candidates=sum(len(row["candidates"]) for row in requests),
        catalog_articles=len(catalog),
        auc_eligible_requests=sum(
            row["impression_auc"] is not None for row in individual
        ),
        auc_excluded_requests=sum(row["impression_auc"] is None for row in individual),
        no_click_requests=sum(not any(row["labels"]) for row in requests),
    )
    for k in (5, 10):
        selected = {
            row["candidates"][int(index)]
            for row, values in zip(requests, scores, strict=True)
            for index in np.argsort(-np.asarray(values), kind="stable")[:k]
        }
        result[f"coverage_at_{k}"] = len(selected) / len(catalog)
        result[f"short_slate_requests_at_{k}"] = sum(
            len(row["candidates"]) < k for row in requests
        )
    return result


def evaluate_models(requests, scores_by_model, vectors):
    models, individual_by_model = {}, {}
    for name, scores in scores_by_model.items():
        individual = []
        for row, values in zip(requests, scores, strict=True):
            metrics = metrics_for_request(row["labels"], values)
            ranked = np.argsort(-np.asarray(values), kind="stable")[:10]
            top = vectors[np.asarray(row["candidates"])[ranked]]
            similarities = np.clip(top @ top.T, -1, 1)
            metrics["embedding_diversity_at_10"] = float(
                (1 - similarities)[np.triu_indices(len(top), k=1)].mean()
            )
            individual.append(metrics)
        aggregate = _aggregate(requests, individual, scores, vectors)
        segments = {}
        for segment, lower, upper in (
            ("cold", 0, 0),
            ("history_1_2", 1, 2),
            ("history_3_10", 3, 10),
            ("history_11_plus", 11, float("inf")),
        ):
            indices = [
                index
                for index, row in enumerate(requests)
                if lower <= len(row["history"]) <= upper
            ]
            if indices:
                segments[segment] = _aggregate(
                    [requests[index] for index in indices],
                    [individual[index] for index in indices],
                    [scores[index] for index in indices],
                    vectors,
                )
        aggregate["segments"] = segments
        models[name], individual_by_model[name] = aggregate, individual
    return models, individual_by_model


def paired_comparison(requests, candidate, baseline, *, seed, resamples):
    if not requests or resamples < 100:
        raise ValueError(
            "paired bootstrap requires requests and at least 100 resamples"
        )
    deltas = np.array(
        [
            model["ndcg_at_10"] - base["ndcg_at_10"]
            for _, model, base in zip(requests, candidate, baseline, strict=True)
        ]
    )
    clusters = defaultdict(list)
    for row, delta in zip(requests, deltas, strict=True):
        clusters[row["user_group"]].append(delta)
    ordered = [clusters[key] for key in sorted(clusters)]
    sums, counts = (
        np.array([sum(values) for values in ordered]),
        np.array([len(values) for values in ordered]),
    )
    rng = np.random.default_rng(seed)
    request_bootstrap = [
        rng.choice(deltas, len(deltas), replace=True).mean() for _ in range(resamples)
    ]
    rng = np.random.default_rng(seed)
    clustered = []
    for _ in range(resamples):
        indices = rng.integers(0, len(ordered), size=len(ordered))
        clustered.append(sums[indices].sum() / counts[indices].sum())
    return {
        "metric": "ndcg_at_10",
        "baseline": "semantic_mean_pool",
        "delta": float(deltas.mean()),
        "request_ci95": np.quantile(request_bootstrap, [0.025, 0.975]).tolist(),
        "user_cluster_ci95": np.quantile(clustered, [0.025, 0.975]).tolist(),
        "unique_users": len(ordered),
        "requests": len(requests),
        "resamples": resamples,
        "cluster_weighting": "resample users with replacement; preserve request-weighted means",
        "wins": int((deltas > 0).sum()),
        "ties": int((deltas == 0).sum()),
        "losses": int((deltas < 0).sum()),
    }


def measure_latency(requests, vectors, ranker, *, seed):
    rng = np.random.default_rng(seed)
    indices = rng.permutation(len(requests))[: min(500, len(requests))]
    actual, candidate_counts = [], []

    def measure(history, candidates):
        start = perf_counter()
        context = ranker.prepare_user_context(history_embeddings=history)
        np.argsort(-(candidates @ context.vector), kind="stable")
        return (perf_counter() - start) * 1000

    for index in indices[:20]:
        row = requests[int(index)]
        measure(vectors[row["history"]], vectors[row["candidates"]])
    for index in indices:
        row = requests[int(index)]
        actual.append(measure(vectors[row["history"]], vectors[row["candidates"]]))
        candidate_counts.append(len(row["candidates"]))

    def summary(values):
        return dict(
            zip(
                ("p50_ms", "p95_ms", "p99_ms"),
                np.quantile(values, [0.5, 0.95, 0.99]).tolist(),
                strict=True,
            ),
            samples=len(values),
        )

    result = {
        "sampled_slates": summary(actual),
        "scope": "CPU user context + raw dot scores + stable sort; excludes embedding creation, input gathering, calibration, DB, network, HTTP and retrieval",
    }
    result["sampled_slates"]["candidate_count"] = {
        "min": min(candidate_counts),
        "median": float(np.median(candidate_counts)),
        "max": max(candidate_counts),
    }
    if len(vectors) >= 300:
        history = vectors[
            rng.choice(len(vectors), min(20, len(vectors)), replace=False)
        ]
        candidates = vectors[rng.choice(len(vectors), 300, replace=False)]
        for _ in range(20):
            measure(history, candidates)
        result["fixed_300_candidates"] = summary(
            [measure(history, candidates) for _ in range(100)]
        )
        result["fixed_300_candidates"]["scope"] = (
            "synthetic size workload using holdout embeddings; 20 history entries"
        )
    return result


def _csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_reports(output, report, requests, individual):
    names = (
        "report.json",
        "report.md",
        "metrics.csv",
        "segments.csv",
        "per-request.csv",
    )
    if any((output / name).exists() for name in names):
        raise FileExistsError(
            "benchmark report already exists; completed outputs are immutable"
        )
    output.mkdir(parents=True, exist_ok=True)
    overall, segments, details = [], [], []
    for model, metrics in report["models"].items():
        overall.append(
            {
                "model": model,
                **{key: value for key, value in metrics.items() if key != "segments"},
            }
        )
        segments.extend(
            {"model": model, "history_segment": segment, **values}
            for segment, values in metrics["segments"].items()
        )
        for row, values in zip(requests, individual[model], strict=True):
            details.append(
                {
                    "model": model,
                    "request_group": row["request_group"],
                    "user_group": row["user_group"],
                    "history_length": len(row["history"]),
                    "candidates": len(row["candidates"]),
                    **values,
                }
            )
    _csv(output / "metrics.csv", overall)
    _csv(output / "segments.csv", segments)
    _csv(output / "per-request.csv", details)
    lines = [
        "# Recommendation benchmark",
        "",
        f"Decision: **{report['decision']}** (offline comparison only).",
        "",
        "| Model | AUC | MIND MRR | nDCG@5 | nDCG@10 | Coverage@10 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for model, metrics in report["models"].items():
        values = [
            metrics[key]
            for key in (
                "impression_auc",
                "mrr",
                "ndcg_at_5",
                "ndcg_at_10",
                "coverage_at_10",
            )
        ]
        cells = [f"{value:.6f}" if value is not None else "N/A" for value in values]
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    comparison = report["comparison"]
    lines.extend(
        [
            "",
            "## Paired NRMS minus semantic baseline",
            "",
            f"nDCG@10 delta: {comparison['delta']:.6f}.",
            f"User-cluster bootstrap 95% CI: {comparison['user_cluster_ci95']}.",
            f"Request bootstrap 95% CI: {comparison['request_ci95']}.",
            "",
            "## Precision, recall and semantic diversity",
            "",
            "| Model | P@5 | P@10 | R@5 | R@10 | Hit@10 | Diversity@10 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for model, metrics in report["models"].items():
        cells = [
            f"{metrics[key]:.6f}"
            for key in (
                "precision_at_5",
                "precision_at_10",
                "recall_at_5",
                "recall_at_10",
                "hit_at_10",
                "embedding_diversity_at_10",
            )
        ]
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    lines.extend(
        [
            "",
            "## Latency",
            "",
            "```json",
            json.dumps(report["latency"], indent=2),
            "```",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    directory = args.run_dir
    if (directory / "report.json").exists():
        raise FileExistsError("completed benchmark is immutable")
    protocol_path, dataset_path = (
        directory / "protocol.json",
        directory / "dataset.json",
    )
    protocol = json.loads(protocol_path.read_text())
    dataset = json.loads(dataset_path.read_text())
    artifact_path = Path(protocol["artifact"])
    artifact = load_artifact(artifact_path)
    if not isinstance(artifact, LoadedNRMSArtifact):
        raise TypeError("NRMS artifact is required")
    checks = {
        "dataset_sha256": sha256_file(dataset_path),
        "model_sha256": sha256_file(artifact_path / "model.joblib"),
        "manifest_sha256": sha256_file(artifact_path / "manifest.json"),
    }
    if any(protocol[name] != value for name, value in checks.items()):
        raise ValueError("inputs changed after protocol registration")
    embeddings_path = directory / "embeddings.npz"
    audit = json.loads((directory / "embedding-audit.json").read_text())
    if (
        audit["embeddings_sha256"] != sha256_file(embeddings_path)
        or audit["encoder_version"] != ENCODER_VERSION
    ):
        raise ValueError("embedding audit checksum/encoder mismatch")
    vectors = cached_embeddings(
        dataset["articles"],
        embeddings_path,
        encode=lambda _: None,
        encoder_version=ENCODER_VERSION,
        dimension=artifact.ranker.architecture.embedding_dimension,
    )
    requests = dataset["requests"]
    validate_holdout(
        requests,
        vectors,
        dimension=artifact.ranker.architecture.embedding_dimension,
        history_limit=artifact.ranker.architecture.history_length,
    )
    if len(requests) != protocol["requests"]:
        raise ValueError("request count differs from registered protocol")
    groups = {row["request_group"] for row in requests}
    excluded = set()
    for previous in protocol["excluded_datasets"]:
        path = Path(previous["path"])
        if sha256_file(path) != previous["sha256"]:
            raise ValueError("excluded dataset checksum changed")
        old = json.loads(path.read_text())
        prior = {
            row["request_group"] for row in old["requests"] if row["split"] == "test"
        }
        if not groups.isdisjoint(prior):
            raise ValueError("holdout overlaps previously evaluated requests")
        excluded.update(prior)
    start = perf_counter()
    with threadpool_limits(limits=1):
        scores = score_models(requests, vectors, artifact.ranker, seed=protocol["seed"])
        print(
            json.dumps(
                {"stage": "scored", "models": list(scores), "requests": len(requests)}
            ),
            flush=True,
        )
        models, individual = evaluate_models(requests, scores, vectors)
        comparison = paired_comparison(
            requests,
            individual["nrms"],
            individual["semantic_mean_pool"],
            seed=protocol["seed"],
            resamples=protocol["bootstrap_resamples"],
        )
        latency = measure_latency(
            requests, vectors, artifact.ranker, seed=protocol["seed"]
        )
        pools = threadpool_info()
    low, high = comparison["user_cluster_ci95"]
    sufficient = comparison["requests"] >= 1000 and comparison["unique_users"] >= 100
    decision = (
        "improved_vs_semantic_baseline"
        if sufficient and low > 0
        else "regressed_vs_semantic_baseline"
        if sufficient and high < 0
        else "inconclusive"
    )
    baseline = models["semantic_mean_pool"]["ndcg_at_10"]
    comparison["relative_delta"] = comparison["delta"] / baseline if baseline else None
    report = {
        "schema": "recommendation-benchmark-report-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol": protocol,
        "protocol_sha256": sha256_file(protocol_path),
        "dataset": {
            **dataset["metadata"],
            "articles": len(dataset["articles"]),
            "requests": len(requests),
            "unique_users": len({row["user_group"] for row in requests}),
            "candidates": sum(len(row["candidates"]) for row in requests),
            "overlap_with_prior_holdouts": 0,
            "excluded_requests_verified": len(excluded),
        },
        "embedding_audit": audit,
        "models": models,
        "comparison": comparison,
        "decision": decision,
        "latency": latency,
        "evaluation_elapsed_seconds": perf_counter() - start,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "threadpools": pools,
        },
        "implementation_sha256": {
            name: sha256_file(Path(__file__).with_name(name))
            for name in (
                "benchmark.py",
                "benchmark_data.py",
                "finetune.py",
                "model.py",
                "evaluate.py",
            )
        },
        "production_release": "inconclusive; no production-domain holdout or operational evidence",
        "limitations": [
            "Sampled English MINDlarge dev, not the full official unlabeled test or leaderboard protocol.",
            "No native Vietnamese interactions, friend/follow graph, access-control or candidate-retrieval evaluation.",
            "Logged order is a reference baseline, not the Oecophylla heuristic.",
            "MIND MRR averages reciprocal ranks of all clicks; first_click_mrr is separate. Ties preserve logged position.",
            "Precision@k divides by k even for short slates; AUC excludes requests without both label classes.",
            "Coverage denominator is the sampled candidate catalog. Diversity is mean pairwise embedding cosine distance, not a relevance score.",
            "No publication times, serving-policy, exposure-bias correction, real negative feedback or production latency measurements.",
            "Model remains fixed throughout this evaluation; this report does not authorize model promotion.",
        ],
    }
    write_reports(directory, report, requests, individual)
    print(
        json.dumps(
            {
                "stage": "complete",
                "decision": decision,
                "comparison": comparison,
                "models": {
                    name: {
                        key: metrics[key]
                        for key in ("impression_auc", "mrr", "ndcg_at_5", "ndcg_at_10")
                    }
                    for name, metrics in models.items()
                },
                "output": str(directory),
            }
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
