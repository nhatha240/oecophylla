from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://oecophylla:secret@postgres:5432/oecophylla"
    redis_url: str = "redis://:redissecret@redis:6379"
    feed_candidate_pool: int = 300
    feed_result_size: int = 50
    half_life_hours: float = 36.0
    seen_cooldown_days: int = Field(default=7, ge=0, le=3650)
    ranker_mode: Literal["heuristic", "ml", "shadow"] = "heuristic"
    model_artifact_path: Path = Path("/models/current")
    recommendation_label_version: Literal["v1", "v2"] = "v1"
    qualified_read_ms: int = Field(default=10_000, gt=0, le=1_800_000)
    preference_schema_version: Literal["v1", "v2"] = "v1"
    preference_half_life_hours: float = Field(default=720.0, gt=0)
    preference_behavior_coefficient: float = Field(default=0.75, ge=0)
    preference_declared_coefficient: float = Field(default=0.25, ge=0)
    preference_evidence_saturation: float = Field(default=2.5, gt=0)
    history_recent_limit: int = Field(default=20, ge=0, le=500)
    history_long_term_limit: int = Field(default=30, ge=0, le=500)
    history_cache_ttl_seconds: int = Field(default=1800, ge=1, le=86_400)
    history_lookup_slack: int = Field(default=50, ge=0, le=500)


def settings() -> Settings:
    return Settings()
