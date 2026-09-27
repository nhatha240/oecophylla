from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC_FEATURES = (
    "topic_relevance",
    "freshness",
    "safety_score",
    "author_affinity",
    "heuristic_score",
)
CATEGORICAL_FEATURES = (
    "feed_source",
    "candidate_source",
    "is_followed_author",
)
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


class ModelInputError(ValueError):
    """Raised when inference input does not satisfy the feature contract."""


def records_to_matrix(records: Sequence[Mapping[str, Any]]) -> np.ndarray:
    missing = sorted(
        {
            feature
            for record in records
            for feature in FEATURE_COLUMNS
            if feature not in record
        }
    )
    if missing:
        raise ModelInputError(f"missing required features: {', '.join(missing)}")

    rows: list[list[Any]] = []
    for record in records:
        row: list[Any] = []
        for feature in FEATURE_COLUMNS:
            value = record[feature]
            if feature in NUMERIC_FEATURES and value is None:
                value = np.nan
            row.append(value)
        rows.append(row)
    return np.asarray(rows, dtype=object)


def build_pipeline(seed: int) -> Pipeline:
    numeric_indices = [FEATURE_COLUMNS.index(name) for name in NUMERIC_FEATURES]
    categorical_indices = [FEATURE_COLUMNS.index(name) for name in CATEGORICAL_FEATURES]
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[
                        (
                            "imputer",
                            SimpleImputer(strategy="median", keep_empty_features=True),
                        ),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_indices,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        (
                            "imputer",
                            SimpleImputer(
                                strategy="most_frequent", missing_values=None
                            ),
                        ),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_indices,
            ),
        ],
        remainder="drop",
    )
    classifier = LogisticRegression(
        class_weight="balanced",
        max_iter=1_000,
        random_state=seed,
        solver="liblinear",
    )
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )


# --- NRMS-like impression-aware ranker (T7) -------------------------------
#
# A minimal from-scratch multi-head self-attention user encoder over ordered
# reading history embeddings, scored against a candidate article embedding
# by dot product. Positional encoding makes the encoder order-aware; history
# is otherwise a permutation-invariant set under plain self-attention.


def _sigmoid(x: float) -> float:
    clipped = min(60.0, max(-60.0, x))
    return 1.0 / (1.0 + np.exp(-clipped))


def _sinusoidal_positions(length: int, dimension: int) -> np.ndarray:
    positions = np.arange(length, dtype=float)[:, None]
    dims = np.arange(dimension, dtype=float)[None, :]
    angle_rates = 1.0 / np.power(10000.0, (2 * (dims // 2)) / dimension)
    angles = positions * angle_rates
    encoding = np.zeros((length, dimension), dtype=float)
    encoding[:, 0::2] = np.sin(angles[:, 0::2])
    encoding[:, 1::2] = np.cos(angles[:, 1::2])
    return encoding


@dataclass(frozen=True)
class NRMSArchitecture:
    embedding_dimension: int
    attention_heads: int
    history_length: int
    seed: int
    position_scale: float = 1.0

    def __post_init__(self) -> None:
        if self.embedding_dimension <= 0:
            raise ValueError("embedding_dimension must be positive")
        if self.attention_heads <= 0:
            raise ValueError("attention_heads must be positive")
        if self.embedding_dimension % self.attention_heads != 0:
            raise ValueError("embedding_dimension must be divisible by attention_heads")
        if self.history_length < 0:
            raise ValueError("history_length must not be negative")
        if not np.isfinite(self.position_scale) or self.position_scale < 0:
            raise ValueError("position_scale must be finite and non-negative")

    @property
    def head_dimension(self) -> int:
        return self.embedding_dimension // self.attention_heads


@dataclass(frozen=True)
class UserContext:
    vector: np.ndarray
    source: str
    history_length: int
    fabricated_clicks: int


@dataclass(frozen=True)
class PairwiseExample:
    positive_request: str
    negative_request: str
    positive_label: int
    negative_label: int
    history_embeddings: tuple[tuple[float, ...], ...]
    declared_topic_embedding: tuple[float, ...] | None
    positive_embedding: tuple[float, ...]
    negative_embedding: tuple[float, ...]


@dataclass(frozen=True, eq=False)
class NRMSLikeRanker:
    architecture: NRMSArchitecture
    query_projection: np.ndarray
    key_projection: np.ndarray
    value_projection: np.ndarray
    calibration_scale: float
    calibration_bias: float
    popular_embedding: np.ndarray | None

    @classmethod
    def initialize(
        cls,
        architecture: NRMSArchitecture,
        *,
        popular_embedding: Sequence[float] | None = None,
    ) -> "NRMSLikeRanker":
        rng = np.random.default_rng(architecture.seed)
        shape = (
            architecture.attention_heads,
            architecture.embedding_dimension,
            architecture.head_dimension,
        )
        scale = 1.0 / np.sqrt(architecture.embedding_dimension)
        query = rng.normal(0.0, scale, size=shape)
        key = rng.normal(0.0, scale, size=shape)
        value = rng.normal(0.0, scale, size=shape)
        popular = (
            np.asarray(popular_embedding, dtype=float)
            if popular_embedding is not None
            else None
        )
        return cls(
            architecture=architecture,
            query_projection=query,
            key_projection=key,
            value_projection=value,
            calibration_scale=1.0,
            calibration_bias=0.0,
            popular_embedding=popular,
        )

    def _forward_history(
        self, embeddings: Sequence[Sequence[float]]
    ) -> tuple[np.ndarray, dict[str, Any]]:
        matrix = np.asarray(embeddings, dtype=float)
        length = matrix.shape[0]
        positioned = matrix + self.architecture.position_scale * _sinusoidal_positions(
            length, self.architecture.embedding_dimension
        )
        head_dimension = self.architecture.head_dimension
        head_outputs = []
        head_cache = []
        for head in range(self.architecture.attention_heads):
            query = positioned @ self.query_projection[head]
            key = positioned @ self.key_projection[head]
            value = positioned @ self.value_projection[head]
            scores = (query @ key.T) / np.sqrt(head_dimension)
            scores = scores - scores.max(axis=-1, keepdims=True)
            exp_scores = np.exp(scores)
            attention = exp_scores / exp_scores.sum(axis=-1, keepdims=True)
            context = attention @ value
            head_outputs.append(context)
            head_cache.append(
                {"query": query, "key": key, "value": value, "attention": attention}
            )
        concatenated = np.concatenate(head_outputs, axis=-1)
        user_vector = concatenated.mean(axis=0)
        cache = {"positioned": positioned, "heads": head_cache, "length": length}
        return user_vector, cache

    def _backward_history(
        self, cache: Mapping[str, Any], grad_user: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        length = cache["length"]
        head_dimension = self.architecture.head_dimension
        positioned = cache["positioned"]
        grad_query = np.zeros_like(self.query_projection)
        grad_key = np.zeros_like(self.key_projection)
        grad_value = np.zeros_like(self.value_projection)
        grad_concatenated = np.tile(grad_user / length, (length, 1))
        for head, head_cache in enumerate(cache["heads"]):
            grad_context = grad_concatenated[
                :, head * head_dimension : (head + 1) * head_dimension
            ]
            attention = head_cache["attention"]
            value = head_cache["value"]
            query = head_cache["query"]
            key = head_cache["key"]
            grad_attention = grad_context @ value.T
            grad_value_head = attention.T @ grad_context
            row_sum = np.sum(attention * grad_attention, axis=-1, keepdims=True)
            grad_scores = attention * (grad_attention - row_sum)
            scale = 1.0 / np.sqrt(head_dimension)
            grad_query_head = (grad_scores @ key) * scale
            grad_key_head = (grad_scores.T @ query) * scale
            grad_query[head] = positioned.T @ grad_query_head
            grad_key[head] = positioned.T @ grad_key_head
            grad_value[head] = positioned.T @ grad_value_head
        return grad_query, grad_key, grad_value

    def encode_history(self, embeddings: Sequence[Sequence[float]]) -> np.ndarray:
        if len(embeddings) == 0:
            raise ValueError("encode_history requires at least one embedding")
        vector, _ = self._forward_history(embeddings)
        return vector

    def _truncate_history(
        self, embeddings: Sequence[Sequence[float]]
    ) -> Sequence[Sequence[float]]:
        cap = self.architecture.history_length
        if cap > 0 and len(embeddings) > cap:
            return embeddings[-cap:]
        return embeddings

    def prepare_user_context(
        self,
        *,
        history_embeddings: Sequence[Sequence[float]],
        declared_topic_embedding: Sequence[float] | None = None,
    ) -> UserContext:
        history_embeddings = list(history_embeddings)
        if history_embeddings:
            truncated = self._truncate_history(history_embeddings)
            vector = self.encode_history(truncated)
            return UserContext(
                vector=vector,
                source="history",
                history_length=len(history_embeddings),
                fabricated_clicks=0,
            )
        if declared_topic_embedding is not None:
            vector = np.asarray(declared_topic_embedding, dtype=float)
            return UserContext(
                vector=vector,
                source="declared_topics",
                history_length=0,
                fabricated_clicks=0,
            )
        if self.popular_embedding is not None:
            vector = np.asarray(self.popular_embedding, dtype=float)
        else:
            vector = np.zeros(self.architecture.embedding_dimension, dtype=float)
        return UserContext(
            vector=vector,
            source="popular_articles",
            history_length=0,
            fabricated_clicks=0,
        )

    def raw_score(
        self, user_vector: np.ndarray, candidate_embedding: Sequence[float]
    ) -> float:
        return float(
            np.dot(
                np.asarray(user_vector, dtype=float),
                np.asarray(candidate_embedding, dtype=float),
            )
        )

    def score(
        self, user_vector: np.ndarray, candidate_embedding: Sequence[float]
    ) -> float:
        raw = self.raw_score(user_vector, candidate_embedding)
        logit = raw * self.calibration_scale + self.calibration_bias
        return float(_sigmoid(logit))

    def predict_scores(self, records: Sequence[Mapping[str, Any]]) -> list[float]:
        scores: list[float] = []
        for record in records:
            article = record.get("article") or {}
            candidate_embedding = article.get("embedding")
            if candidate_embedding is None:
                raise ModelInputError("candidate record is missing an embedding")
            history_entries = sorted(
                record.get("history") or (),
                key=lambda entry: int(entry["ordinal"]),
            )
            history_embeddings = [
                entry["article"]["embedding"]
                for entry in history_entries
                if (entry.get("article") or {}).get("embedding") is not None
            ]
            declared = record.get("declared_topic_embedding")
            context = self.prepare_user_context(
                history_embeddings=history_embeddings,
                declared_topic_embedding=declared,
            )
            scores.append(self.score(context.vector, candidate_embedding))
        return scores

    def with_updated_weights(
        self,
        *,
        query_projection: np.ndarray,
        key_projection: np.ndarray,
        value_projection: np.ndarray,
    ) -> "NRMSLikeRanker":
        return replace(
            self,
            query_projection=query_projection,
            key_projection=key_projection,
            value_projection=value_projection,
        )

    def with_calibration(self, *, scale: float, bias: float) -> "NRMSLikeRanker":
        return replace(self, calibration_scale=scale, calibration_bias=bias)


def build_pairwise_examples(
    rows: Sequence[Mapping[str, Any]],
) -> list[PairwiseExample]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["request_group"])].append(row)

    examples: list[PairwiseExample] = []
    for request_group in sorted(grouped):
        candidates = grouped[request_group]
        positives = [row for row in candidates if int(row["click_label"]) == 1]
        negatives = [row for row in candidates if int(row["click_label"]) == 0]
        if not positives or not negatives:
            continue
        reference = candidates[0]
        history_embeddings = tuple(
            tuple(float(value) for value in entry["article"]["embedding"])
            for entry in sorted(
                reference.get("history") or (),
                key=lambda entry: int(entry["ordinal"]),
            )
        )
        declared = reference.get("declared_topic_embedding")
        declared_topic_embedding = (
            tuple(float(value) for value in declared) if declared is not None else None
        )
        for positive in positives:
            for negative in negatives:
                examples.append(
                    PairwiseExample(
                        positive_request=request_group,
                        negative_request=request_group,
                        positive_label=1,
                        negative_label=0,
                        history_embeddings=history_embeddings,
                        declared_topic_embedding=declared_topic_embedding,
                        positive_embedding=tuple(
                            float(value) for value in positive["article"]["embedding"]
                        ),
                        negative_embedding=tuple(
                            float(value) for value in negative["article"]["embedding"]
                        ),
                    )
                )
    return examples


def train_pairwise_epoch(
    ranker: NRMSLikeRanker,
    examples: Sequence[PairwiseExample],
    *,
    learning_rate: float,
) -> NRMSLikeRanker:
    grad_query = np.zeros_like(ranker.query_projection)
    grad_key = np.zeros_like(ranker.key_projection)
    grad_value = np.zeros_like(ranker.value_projection)
    updated = 0
    for example in examples:
        if not example.history_embeddings:
            continue
        truncated = ranker._truncate_history(example.history_embeddings)
        user_vector, cache = ranker._forward_history(truncated)
        positive = np.asarray(example.positive_embedding, dtype=float)
        negative = np.asarray(example.negative_embedding, dtype=float)
        score_gap = ranker.raw_score(user_vector, positive) - ranker.raw_score(
            user_vector, negative
        )
        gradient_signal = _sigmoid(score_gap) - 1.0
        grad_user = gradient_signal * (positive - negative)
        dq, dk, dv = ranker._backward_history(cache, grad_user)
        grad_query += dq
        grad_key += dk
        grad_value += dv
        updated += 1
    if updated == 0:
        return ranker
    return ranker.with_updated_weights(
        query_projection=ranker.query_projection
        - learning_rate * (grad_query / updated),
        key_projection=ranker.key_projection - learning_rate * (grad_key / updated),
        value_projection=ranker.value_projection
        - learning_rate * (grad_value / updated),
    )
