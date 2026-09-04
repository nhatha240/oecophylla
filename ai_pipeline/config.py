from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from recommendation_label import QUALIFIED_READ_MS

IdentityMode = Literal["hash", "drop"]
LabelVersion = Literal["v1", "v2"]
DatasetSchemaVersion = Literal["v1", "v2"]

PINNED_ENCODER_VERSION = (
    "intfloat/multilingual-e5-small@"
    "614241f622f53c4eeff9890bdc4f31cfecc418b3"
)
DATASET_V2_FEATURE_SCHEMA_VERSION = "post-content-features-v1"
DATASET_V2_QUERY_WINDOW_VERSION = "event-time-window-v1"
ENCODER_VERSION_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*@[0-9a-f]{40}$"
)


@dataclass(frozen=True)
class DatasetConfig:
    start: datetime
    end: datetime
    extraction_time: datetime
    label_window_hours: int = 24
    qualified_read_ms: int = QUALIFIED_READ_MS
    recommendation_label_version: LabelVersion = "v1"
    identity_mode: IdentityMode = "hash"
    hash_salt: str | None = None
    train_fraction: float = 0.70
    validation_fraction: float = 0.15
    history_recent_limit: int = 20
    history_long_term_limit: int = 30
    dataset_schema_version: DatasetSchemaVersion = "v1"
    feature_schema_version: str = "post-content-features-v1"
    encoder_version: str = PINNED_ENCODER_VERSION
    encoder_dimension: int = 384
    query_window_version: str = "event-time-window-v1"

    def __post_init__(self) -> None:
        for name in ("start", "end", "extraction_time"):
            if getattr(self, name).tzinfo is None:
                raise ValueError(f"{name} must include a timezone")
        if self.start >= self.end:
            raise ValueError("start must be before end")
        if self.extraction_time < self.start:
            raise ValueError("extraction_time must not be before start")
        if self.label_window_hours <= 0:
            raise ValueError("label_window_hours must be positive")
        if self.qualified_read_ms <= 0:
            raise ValueError("qualified_read_ms must be positive")
        if self.recommendation_label_version not in ("v1", "v2"):
            raise ValueError("recommendation_label_version must be v1 or v2")
        if self.identity_mode not in ("hash", "drop"):
            raise ValueError("identity_mode must be hash or drop")
        if self.identity_mode == "hash" and not self.hash_salt:
            raise ValueError("hash_salt is required when identity_mode=hash")
        if not 0 < self.train_fraction < 1:
            raise ValueError("train_fraction must be between zero and one")
        if not 0 < self.validation_fraction < 1:
            raise ValueError("validation_fraction must be between zero and one")
        if self.train_fraction + self.validation_fraction >= 1:
            raise ValueError("train and validation fractions must leave a test holdout")
        if self.history_recent_limit < 0:
            raise ValueError("history_recent_limit must be non-negative")
        if self.history_long_term_limit < 0:
            raise ValueError("history_long_term_limit must be non-negative")
        if self.dataset_schema_version not in ("v1", "v2"):
            raise ValueError("dataset_schema_version must be v1 or v2")
        if (
            self.dataset_schema_version == "v2"
            and self.recommendation_label_version != "v2"
        ):
            raise ValueError("dataset v2 requires label v2")
        if self.dataset_schema_version == "v2" and self.identity_mode != "hash":
            raise ValueError("dataset v2 requires identity_mode=hash")
        if (
            self.dataset_schema_version == "v2"
            and self.feature_schema_version != DATASET_V2_FEATURE_SCHEMA_VERSION
        ):
            raise ValueError("dataset v2 requires post-content-features-v1")
        if (
            self.dataset_schema_version == "v2"
            and self.query_window_version != DATASET_V2_QUERY_WINDOW_VERSION
        ):
            raise ValueError("dataset v2 requires event-time-window-v1")
        if not ENCODER_VERSION_PATTERN.fullmatch(self.encoder_version):
            raise ValueError("encoder_version must be an immutable repository revision")
        if self.encoder_dimension <= 0:
            raise ValueError("encoder_dimension must be positive")
        if not self.feature_schema_version.strip():
            raise ValueError("feature_schema_version must not be empty")
        if not self.query_window_version.strip():
            raise ValueError("query_window_version must not be empty")
