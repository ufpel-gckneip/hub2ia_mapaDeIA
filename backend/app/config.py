"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Minimum length for a usable HMAC signing key (SHA-256 → 32 bytes; RFC 7518 §3.2).
SECRET_KEY_MIN_LENGTH = 32

# Well-known placeholder values that must never sign real tokens, even if long.
INSECURE_SECRET_KEYS = {
    "",
    "change-me",
    "changeme",
    "change-me-in-production",
    "secret",
    "your-secret-key",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Database ──
    # Async URL used by the FastAPI app (psycopg3 async driver).
    database_url: str = "postgresql+psycopg://mapadeia:mapadeia@localhost:5432/mapadeia"

    # ── Auth ──
    # Signs JWTs and reset/verify tokens. No usable default on purpose: it must be
    # supplied via the SECRET_KEY env var and pass assert_secure_secret_key(),
    # which the API enforces at startup (see app.main).
    secret_key: str = ""
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

    def assert_secure_secret_key(self) -> None:
        """Fail fast unless SECRET_KEY is a strong, non-placeholder value.

        Called at API startup (not at Settings construction) so the pipeline
        loader — which imports settings but never boots the API — is unaffected.
        """
        key = self.secret_key.strip()
        if key.lower() in INSECURE_SECRET_KEYS or len(key) < SECRET_KEY_MIN_LENGTH:
            raise RuntimeError(
                "SECRET_KEY is unset, a known placeholder, or too short. "
                f"Set the SECRET_KEY env var to a strong random value "
                f"(>= {SECRET_KEY_MIN_LENGTH} chars), e.g. `openssl rand -hex 32`."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
