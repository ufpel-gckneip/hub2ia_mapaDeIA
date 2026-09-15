"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Database ──
    # Async URL used by the FastAPI app (psycopg3 async driver).
    database_url: str = "postgresql+psycopg://mapadeia:mapadeia@localhost:5432/mapadeia"

    # ── Auth ──
    # NOTE: override in production via env. Used to sign JWTs and reset/verify tokens.
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_lifetime_seconds: int = 60 * 60 * 24  # 24h

    # ── CORS ──
    # Comma-separated list of allowed origins for the SPA in dev.
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    # ── Caching ──
    cache_ttl_seconds: int = 300

    # ── Tracking ──
    analytics_retention_days: int = 365

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic / the pipeline loader (psycopg3 sync driver)."""
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
