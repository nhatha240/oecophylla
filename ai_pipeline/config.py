from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

IdentityMode = Literal["hash", "drop"]


@dataclass(frozen=True)
class DatasetConfig:
    start: datetime
    end: datetime
    extraction_time: datetime
    label_window_hours: int = 24
    positive_dwell_ms: int = 10_000
    identity_mode: IdentityMode = "hash"
    hash_salt: str | None = None
    train_fraction: float = 0.70
    validation_fraction: float = 0.15

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
        if self.positive_dwell_ms <= 0:
            raise ValueError("positive_dwell_ms must be positive")
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
