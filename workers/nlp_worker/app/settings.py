from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://oecophylla:secret@postgres:5432/oecophylla"
    kafka_brokers: str = "kafka:9092"
    content_created_topic: str = "oecophylla.content.created"
    consumer_group: str = "oecophylla.nlp.v1"

    flush_interval_seconds: float = 5.0
    flush_batch_size: int = 50

    # --- Optional LLM analysis via LM Studio (OpenAI-compatible API) ---
    # When enabled, the worker asks a local LLM to classify topics and score
    # content safety; on any error it falls back to the keyword analyzer, so the
    # pipeline never blocks on the LLM. Point base_url at LM Studio's server
    # (Developer tab → "Start Server", default port 1234).
    nlp_llm_enabled: bool = False
    nlp_llm_base_url: str = "http://host.docker.internal:1234/v1"
    nlp_llm_model: str = "gemma-4-12b"
    nlp_llm_api_key: str = "lm-studio"
    nlp_llm_timeout_seconds: float = 30.0


def settings() -> Settings:
    return Settings()
