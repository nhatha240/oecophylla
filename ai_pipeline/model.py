from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC_FEATURES = (
    "position",
    "topic_relevance",
    "freshness",
    "safety_score",
    "author_affinity",
    "heuristic_score",
    "ml_score",
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
