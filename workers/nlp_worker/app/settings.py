from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .content_features import ENCODER_ARTIFACT_SHA256, ENCODER_VERSION


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://oecophylla:secret@postgres:5432/oecophylla"
    kafka_brokers: str = "kafka:9092"
    content_created_topic: str = "oecophylla.content.created"
    content_updated_topic: str = "oecophylla.content.updated"
    consumer_group: str = "oecophylla.nlp.v1"

    flush_interval_seconds: float = 5.0
    flush_batch_size: int = 50

    embedding_inference_enabled: bool = False
    embedding_encoder_version: Literal[ENCODER_VERSION] = ENCODER_VERSION
    embedding_artifact_sha256: Literal[ENCODER_ARTIFACT_SHA256] = ENCODER_ARTIFACT_SHA256
    embedding_model_dir: str = "/opt/models/multilingual-e5-small"
    embedding_allow_download: bool = False
    embedding_device: Literal["cpu"] = "cpu"
    embedding_torch_threads: int = Field(default=1, ge=1, le=8)
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    embedding_concurrency: int = Field(default=1, ge=1, le=8)
    embedding_max_retries: int = Field(default=3, ge=0, le=10)
    embedding_retry_delay_seconds: float = Field(default=0.25, ge=0, le=60)
    metrics_port: int = Field(default=9109, ge=1024, le=65535)


def settings() -> Settings:
    return Settings()
