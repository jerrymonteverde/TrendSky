from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: SecretStr | None = None
    postgres_host: str = "localhost"
    postgres_db: str = "trendsky"
    app_db_password: SecretStr = SecretStr("")
    cors_origins: list[str] = ["http://localhost:3000"]
    rate_limit_per_minute: int = Field(default=120, ge=1, le=10000)
    ingestion_enabled: bool = True
    jetstream_url: str = "wss://jetstream.us-east.bsky.network"
    ingestion_batch_size: int = Field(default=250, ge=1, le=2000)
    ingestion_flush_interval_ms: int = Field(default=1000, ge=100, le=10000)
    ingestion_queue_max_size: int = Field(default=5000, ge=100, le=20000)
    ingestion_retention_days: int = Field(default=30, ge=1, le=3650)
    ingestion_heartbeat_interval_seconds: int = Field(default=15, ge=5, le=60)
    ingestion_heartbeat_timeout_seconds: int = Field(default=60, ge=20, le=600)
    ingestion_reconnect_base_seconds: float = Field(default=1.0, ge=0.1, le=60)
    ingestion_reconnect_max_seconds: float = Field(default=60.0, ge=1, le=600)
    trends_enabled: bool = True
    trends_batch_size: int = Field(default=500, ge=1, le=1000)
    trends_refresh_seconds: int = Field(default=60, ge=15, le=600)
    trends_batch_pause_seconds: float = Field(default=0.25, ge=0.1, le=30)
    trends_min_posts: int = Field(default=5, ge=2, le=10000)
    trends_min_contributors: int = Field(default=3, ge=2, le=1000)
    trends_emerging_min_posts: int = Field(default=10, ge=5, le=10000)
    trends_emerging_min_contributors: int = Field(default=5, ge=3, le=1000)
    trends_growth_threshold: float = Field(default=25, gt=0, le=1000)
    trends_emerging_lift: float = Field(default=2, gt=1, le=100)
    trends_baseline_windows: int = Field(default=6, ge=3, le=12)
    trends_min_baseline_windows: int = Field(default=3, ge=3, le=12)
    trends_lateness_seconds: int = Field(default=60, ge=0, le=600)
    trends_stale_seconds: int = Field(default=180, ge=60, le=3600)
    trends_min_token_length: int = Field(default=3, ge=2, le=10)
    trends_max_keywords_per_post: int = Field(default=12, ge=1, le=32)
    trends_max_topics: int = Field(default=500, ge=10, le=5000)
    trends_phrases: list[str] = [
        "artificial intelligence",
        "climate change",
        "machine learning",
        "video games",
        "inteligencia artificial",
        "cambio climático",
        "aprendizaje automático",
        "video juegos",
        "mental health",
        "salud mental",
    ]

    def sqlalchemy_url(self) -> str | URL:
        if self.database_url is not None:
            return self.database_url.get_secret_value()
        return URL.create(
            "postgresql+psycopg",
            username="trendsky_app",
            password=self.app_db_password.get_secret_value(),
            host=self.postgres_host,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
