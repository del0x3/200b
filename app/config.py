"""Application settings loaded from environment / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Single source of truth for runtime configuration.

    Reads from environment variables (or `.env` in development).
    All fields have safe defaults so the app can boot in dev without an
    `.env`; in production the values must be set explicitly.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = ""
    jwt_secret: str = "dev-secret-change-me"
    deepseek_api_key: str = ""
    env: str = "development"

    @property
    def is_production(self) -> bool:
        """True if `ENV=production` (case-insensitive)."""
        return self.env.lower() == "production"

    @property
    def effective_database_url(self) -> str:
        """Returns a SQLAlchemy-compatible URL, falling back to local SQLite.

        Normalises legacy `postgres://` / `postgresql://` URLs to the
        explicit `postgresql+psycopg://` driver form so SQLAlchemy 2.x
        picks the right dialect on Render's managed Postgres.
        """
        if not self.database_url:
            return "sqlite:///./dev.db"
        url: str = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


settings = Settings()
