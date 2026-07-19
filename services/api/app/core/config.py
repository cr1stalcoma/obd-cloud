from urllib.parse import quote_plus

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "obd"
    postgres_password: str = ""
    postgres_db: str = "obd_cloud"
    postgres_host: str = "postgres"
    redis_url: str = "redis://redis:6379/0"
    bot_internal_token: str
    encryption_key: str
    scanner_offline_seconds: int = 45
    public_api_url: str = "https://obd.lexora.by"

    @computed_field
    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:5432/{self.postgres_db}"


settings = Settings()
