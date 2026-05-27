from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://oecophylla:secret@postgres:5432/oecophylla"
    kafka_brokers: str = "kafka:9092"
    content_created_topic: str = "oecophylla.content.created"
    consumer_group: str = "oecophylla.nlp.v1"

    flush_interval_seconds: float = 5.0
    flush_batch_size: int = 50


def settings() -> Settings:
    return Settings()
