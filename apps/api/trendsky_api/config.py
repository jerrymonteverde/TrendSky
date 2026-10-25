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
