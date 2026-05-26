from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgres://oecophylla:secret@postgres:5432/oecophylla"
    redis_url: str = "redis://:redissecret@redis:6379"
    feed_candidate_pool: int = 300
    feed_result_size: int = 50
    half_life_hours: float = 36.0


def settings() -> Settings:
    return Settings()
