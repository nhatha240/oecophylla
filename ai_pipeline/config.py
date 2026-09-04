from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from recommendation_label import QUALIFIED_READ_MS

IdentityMode = Literal["hash", "drop"]
LabelVersion = Literal["v1", "v2"]


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
        if self.history_recent_limit + self.history_long_term_limit <= 0:
            raise ValueError("history limits must leave at least one slot")
