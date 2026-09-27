"""Rank an already-authorized candidate list from friends and news using post text.

This is an offline model interface, not access control or friend retrieval. Supply
only candidates the user may see and reading history from before this request.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from workers.nlp_worker.app.content_features import normalize_content

from .artifact import LoadedNRMSArtifact, load_artifact


def recommend_posts(ranker, payload, *, encode):
    candidates = payload.get("candidates", [])
    if not candidates or any(
        not isinstance(c.get("id"), str) or not c["id"].strip() for c in candidates
    ):
        raise ValueError("nonempty candidates with string IDs are required")
    if len({c["id"] for c in candidates}) != len(candidates):
        raise ValueError("candidate IDs must be unique")
    limit = ranker.architecture.history_length
    history = (
        payload.get("history", [])[-limit:] if limit else payload.get("history", [])
    )
    interests = payload.get("interests", []) if not history else []
    texts = [normalize_content(text) for text in history + interests] + [
        normalize_content(c["text"]) for c in candidates
    ]
    embeddings = np.asarray(encode(texts), dtype=float)
    if (
        embeddings.shape != (len(texts), ranker.architecture.embedding_dimension)
        or not np.isfinite(embeddings).all()
        or not np.allclose(np.linalg.norm(embeddings, axis=1), 1, atol=0.001)
    ):
        raise ValueError("encoder returned invalid embeddings")
    declared = (
        embeddings[len(history) : len(history) + len(interests)].mean(axis=0)
        if interests
        else None
    )
    if declared is not None:
        declared /= max(float(np.linalg.norm(declared)), 1e-12)
    context = ranker.prepare_user_context(
        history_embeddings=embeddings[: len(history)], declared_topic_embedding=declared
    )
    recommendations = [
        {
            "id": c["id"],
            "source": c.get("source", "unspecified"),
            "score": ranker.score(context.vector, vector),
        }
        for c, vector in zip(
            candidates, embeddings[len(history) + len(interests) :], strict=True
        )
    ]
    recommendations.sort(key=lambda c: -c["score"])
    return {
        "based_on": context.source,
        "history_used": len(history),
        "recommendations": recommendations,
    }


def main(argv=None):
    from workers.nlp_worker.app.content_features import (
        EMBEDDING_DIMENSION,
        ENCODER_VERSION,
    )
    from workers.nlp_worker.app.model import PinnedSentenceEncoder

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    args = parser.parse_args(argv)
    artifact = load_artifact(args.artifact)
    if not isinstance(artifact, LoadedNRMSArtifact) or artifact.manifest[
        "embedding"
    ] != {"version": ENCODER_VERSION, "dimension": EMBEDDING_DIMENSION}:
        parser.error("artifact is incompatible with the pinned content encoder")
    encoder = PinnedSentenceEncoder(
        str(args.model_dir), device=args.device, torch_threads=2
    )

    def encode(texts):
        return encoder._load().encode(
            ["passage: " + text for text in texts],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    result = recommend_posts(
        artifact.ranker, json.loads(args.input.read_text()), encode=encode
    )
    result["model_version"] = artifact.manifest["model_version"]
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
