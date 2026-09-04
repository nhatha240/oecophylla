from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import subprocess
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .build_dataset import _split_ranking_rows, validate_dataset_v2
from .schemas import (
    ArticleRepresentation,
    BuildStats,
    RankingBuildResult,
    RankingDatasetRow,
    RankingHistoryEntry,
)

MIND_ARTICLE_REPRESENTATION_VERSION = "mind-text-v1"
MIND_SOURCE_FORMAT = "official-mind-tsv-v1"


@dataclass(frozen=True)
class _MindArticle:
    source_id: str
    category: str
    subcategory: str
    title: str
    abstract: str


def _private_id(salt: str, namespace: str, value: str) -> str:
    return hmac.new(
        salt.encode(),
        f"{namespace}:{value}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _parse_news(path: Path) -> dict[str, _MindArticle]:
    articles: dict[str, _MindArticle] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        fields = raw_line.split("\t")
        if len(fields) != 8:
            raise ValueError(f"news.tsv line {line_number} must contain 8 tab-separated fields")
        source_id, category, subcategory, title, abstract, _url, _title_entities, _abstract_entities = fields
        if not source_id or not (title.strip() or abstract.strip()):
            raise ValueError(f"news.tsv line {line_number} has no usable article text")
        article = _MindArticle(source_id, category, subcategory, title, abstract)
        existing = articles.setdefault(source_id, article)
        if existing != article:
            raise ValueError(f"conflicting duplicate MIND article at line {line_number}")
    if not articles:
        raise ValueError("news.tsv must contain at least one article")
    return articles


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.strptime(value.strip(), "%m/%d/%Y %I:%M:%S %p").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        raise ValueError(f"invalid MIND behavior timestamp: {value}") from error


def _representation(article: _MindArticle, salt: str) -> ArticleRepresentation:
    text_digest = hashlib.sha256(
        f"{MIND_ARTICLE_REPRESENTATION_VERSION}\n{article.category}\n"
        f"{article.subcategory}\n{article.title}\n{article.abstract}".encode()
    ).hexdigest()
    return ArticleRepresentation(
        article_group=_private_id(salt, "mind-article", article.source_id),
        representation_type="mind-text-v1",
        content_hash=text_digest,
        category=article.category or None,
        subcategory=article.subcategory or None,
        title=article.title or None,
        abstract=article.abstract or None,
    )


def _history(
    source_ids: Iterable[str],
    articles: dict[str, _MindArticle],
    salt: str,
) -> tuple[RankingHistoryEntry, ...]:
    entries: list[RankingHistoryEntry] = []
    for ordinal, source_id in enumerate(source_ids):
        try:
            article = articles[source_id]
        except KeyError as error:
            raise ValueError(f"unknown MIND article in history: {source_id}") from error
        entries.append(
            RankingHistoryEntry(
                article=_representation(article, salt),
                ordinal=ordinal,
                engaged_at=None,
                provenance="mind-pre-impression-snapshot",
            )
        )
    return tuple(entries)


def adapt_mind(
    news_path: Path,
    behaviors_path: Path,
    *,
    hash_salt: str,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> RankingBuildResult:
    if not hash_salt:
        raise ValueError("hash_salt is required")
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("train and validation fractions must be between zero and one")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train and validation fractions must leave a test holdout")
    articles = _parse_news(news_path)
    rows: list[RankingDatasetRow] = []
    seen_requests: set[str] = set()

    behavior_lines = behaviors_path.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(behavior_lines, start=1):
        fields = raw_line.split("\t")
        if len(fields) != 5:
            raise ValueError(
                f"behaviors.tsv line {line_number} must contain 5 tab-separated fields"
            )
        impression_id, user_id, time_text, history_text, impression_text = fields
        canonical_request = f"{user_id}:{impression_id}"
        if canonical_request in seen_requests:
            raise ValueError("conflicting canonical MIND request identity")
        seen_requests.add(canonical_request)
        served_at = _parse_timestamp(time_text)
        request_group = _private_id(salt=hash_salt, namespace="mind-request", value=canonical_request)
        history = _history(history_text.split() if history_text.strip() else (), articles, hash_salt)
        candidate_tokens = impression_text.split()
        for position, token in enumerate(candidate_tokens):
            try:
                article_id, label_text = token.rsplit("-", 1)
            except ValueError as error:
                raise ValueError(f"malformed MIND impression token: {token}") from error
            if label_text not in {"0", "1"}:
                raise ValueError("MIND click label must be 0 or 1")
            try:
                article = articles[article_id]
            except KeyError as error:
                raise ValueError(f"unknown MIND article: {article_id}") from error
            click_label = int(label_text)
            rows.append(
                RankingDatasetRow(
                    sample_id=_private_id(
                        hash_salt,
                        "mind-sample",
                        f"{canonical_request}:{article_id}:{position}",
                    ),
                    request_group=request_group,
                    candidate_group=_private_id(hash_salt, "mind-article", article_id),
                    split="train",
                    served_at=served_at,
                    visible_at=served_at,
                    position=position,
                    served=True,
                    visible=True,
                    click_label=click_label,
                    utility_label=click_label,
                    utility_label_name="click" if click_label else "negative",
                    article=_representation(article, hash_salt),
                    history=history,
                    feed_source="mind-benchmark",
                    model_version="mind-logged-policy-unknown",
                    source_format=MIND_SOURCE_FORMAT,
                    audit_request_identity=canonical_request,
                )
            )

    result = RankingBuildResult(
        rows=_split_ranking_rows(rows, train_fraction, validation_fraction),
        stats=BuildStats(
            impressions_read=len(rows),
            events_read=0,
            served_without_visible=0,
            immature_impressions=0,
            unsupported_feature_schema=0,
        ),
    )
    validate_dataset_v2(result)
    return result


def _code_version() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def write_mind_artifact(result: RankingBuildResult, output: Path) -> Path:
    import pyarrow as arrow
    from pyarrow import parquet

    report = validate_dataset_v2(result)
    code_version = _code_version()
    if not code_version:
        raise ValueError("MIND dataset artifact requires an immutable code version")
    output.parent.mkdir(parents=True, exist_ok=True)
    parquet.write_table(
        arrow.Table.from_pylist([row.to_record() for row in result.rows]),
        output,
        compression="zstd",
    )
    request_times: dict[str, datetime] = {}
    for row in result.rows:
        request_times.setdefault(row.request_group, row.served_at)
    metadata = {
        "dataset_schema_version": "recommendation-dataset-v2",
        "dataset_scope": "served-impression-reranking",
        "source_format": MIND_SOURCE_FORMAT,
        "feature_schema_version": MIND_ARTICLE_REPRESENTATION_VERSION,
        "history_schema_version": "mind-pre-impression-history-v1",
        "label_definition_version": "mind-click-label-v1",
        "encoder_version": "not-applied-mind-text-v1",
        "code_version": code_version,
        "query_window_version": "mind-behavior-window-v1",
        "query_window": {
            "start": min(request_times.values()).isoformat(),
            "end": max(request_times.values()).isoformat(),
        },
        "row_count": len(result.rows),
        "request_count": report.request_count,
        "empty_history_requests": report.empty_history_requests,
        "split_counts": dict(sorted(Counter(row.split for row in result.rows).items())),
        "class_balance": {
            "click_label": {
                str(key): value for key, value in sorted(report.click_class_balance.items())
            },
            "utility_label": {
                str(key): value for key, value in sorted(report.utility_class_balance.items())
            },
        },
        "privacy": {
            "raw_mind_user_ids": False,
            "raw_mind_news_ids": False,
            "raw_mind_impression_ids": False,
        },
        "retrieval_recall_supported": False,
    }
    metadata_path = output.with_suffix(f"{output.suffix}.metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metadata_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert official MIND news.tsv and behaviors.tsv to recommendation-dataset-v2."
    )
    parser.add_argument("--news", required=True, type=Path)
    parser.add_argument("--behaviors", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hash-salt", required=True)
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--validation-fraction", type=float, default=0.15)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = adapt_mind(
        args.news,
        args.behaviors,
        hash_salt=args.hash_salt,
        train_fraction=args.train_fraction,
        validation_fraction=args.validation_fraction,
    )
    metadata_path = write_mind_artifact(result, args.output)
    print(
        json.dumps(
            {
                "metadata": str(metadata_path),
                "output": str(args.output),
                "requests": len({row.request_group for row in result.rows}),
                "rows": len(result.rows),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
