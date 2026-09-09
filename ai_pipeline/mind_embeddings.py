"""Materialize MIND title/abstract with the same pinned passage encoder as serving.

MIND's pre-impression history has order but no event timestamps. This preserves
that provenance; no publication, ingestion, or engagement times are fabricated.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from collections.abc import Callable, Sequence

from workers.nlp_worker.app.content_features import content_hash, normalize_content
from .artifact import sha256_file

HISTORY_SCHEMA = "mind-pre-impression-history-v1"
FEATURE_SCHEMA = "mind-text-embedding-v1"


def materialize_records(
    rows,
    *,
    encoder: Callable,
    encoder_version: str,
    dimension: int,
    history_limit: int = 20,
):
    if history_limit < 1:
        raise ValueError("history limit must be positive")
    rows = [dict(row, history=row["history"][-history_limit:]) for row in rows]
    texts = {}
    for row in rows:
        if row.get("source_format") != "official-mind-tsv-v1":
            raise ValueError("only official MIND rows may use timestamp-free history")
        for article in [row["article"], *(e["article"] for e in row["history"])]:
            text = normalize_content(
                " ".join(filter(None, (article.get("title"), article.get("abstract"))))
            )
            texts.setdefault(text, None)
    text_values = list(texts)
    vectors = encoder(text_values)
    if len(vectors) != len(text_values):
        raise ValueError("encoder returned incorrect embedding count")
    for text, values in zip(text_values, vectors, strict=True):
        vector = [float(v) for v in values]
        if (
            len(vector) != dimension
            or not all(math.isfinite(v) for v in vector)
            or abs(math.sqrt(sum(v * v for v in vector)) - 1) > 0.001
        ):
            raise ValueError("invalid encoder output")
        texts[text] = vector
    articles = {}

    def materialize(article):
        group = article["article_group"]
        if group not in articles:
            text = normalize_content(
                " ".join(filter(None, (article.get("title"), article.get("abstract"))))
            )
            articles[group] = dict(
                article,
                representation_type=FEATURE_SCHEMA,
                encoder_version=encoder_version,
                embedding=texts[text],
                content_hash=content_hash(text),
                title=None,
                abstract=None,
                language="en",
                language_detector_version="mind-source-language-v1",
            )
        return articles[group]

    return [
        dict(
            row,
            article=materialize(row["article"]),
            history=[
                dict(e, article=materialize(e["article"])) for e in row["history"]
            ],
            language="en",
            feature_schema_version=FEATURE_SCHEMA,
        )
        for row in rows
    ]


def main(argv: Sequence[str] | None = None) -> int:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from workers.nlp_worker.app.content_features import (
        ENCODER_VERSION,
        EMBEDDING_DIMENSION,
    )
    from workers.nlp_worker.app.model import PinnedSentenceEncoder

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)
    if args.batch_size < 1:
        parser.error("batch size must be positive")
    metadata_path = args.dataset.with_suffix(args.dataset.suffix + ".metadata.json")
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("source_format") != "official-mind-tsv-v1":
        parser.error("input must be an official MIND adapter artifact")
    model = PinnedSentenceEncoder(str(args.model_dir), device=args.device)

    def encode(texts):
        return model._load().encode(
            ["passage: " + t for t in texts],
            batch_size=args.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        )

    rows = materialize_records(
        pq.read_table(args.dataset).to_pylist(),
        encoder=encode,
        encoder_version=ENCODER_VERSION,
        dimension=EMBEDDING_DIMENSION,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), args.output, compression="zstd")
    metadata.update(
        feature_schema_version=FEATURE_SCHEMA,
        encoder_version=ENCODER_VERSION,
        encoder_dimension=EMBEDDING_DIMENSION,
        materialization=dict(
            source_parquet_sha256=sha256_file(args.dataset),
            source_metadata_sha256=sha256_file(metadata_path),
            text_fields_exported=False,
            event_timestamps_inferred=False,
            history_limit=20,
            publication_timestamps_available=False,
        ),
    )
    args.output.with_suffix(args.output.suffix + ".metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n"
    )
    print(json.dumps(dict(output=str(args.output), rows=len(rows))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
