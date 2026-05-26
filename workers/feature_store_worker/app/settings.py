from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://oecophylla:secret@postgres:5432/oecophylla"
    redis_url: str = "redis://:redissecret@redis:6379"
    kafka_brokers: str = "kafka:9092"
    interactions_topic: str = "oecophylla.interactions"
    consumer_group: str = "oecophylla.feature-store.v1"

    pref_ttl_seconds: int = 1800
    trending_ttl_seconds: int = 300
    flush_interval_seconds: float = 5.0
    flush_batch_size: int = 100


def settings() -> Settings:
    return Settings()
