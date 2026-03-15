"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:changeme@localhost:5432/seo_spider"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # CORS
    cors_origins: list[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
    ]

    # Logging
    log_level: str = "INFO"

    # Crawl defaults (0 = unlimited)
    max_crawl_urls: int = 10000
    max_crawl_depth: int = 10
    max_threads: int = 5
    rate_limit_rps: float = 2.0


settings = Settings()
