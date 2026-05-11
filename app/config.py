from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = ""
    jwt_secret: str = "dev-secret-change-me"
    deepseek_api_key: str = ""
    env: str = "development"

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @property
    def effective_database_url(self) -> str:
        if not self.database_url:
            return "sqlite:///./dev.db"
        url: str = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


settings = Settings()
