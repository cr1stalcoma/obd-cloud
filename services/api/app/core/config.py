from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://obd:obd@postgres:5432/obd_cloud"
    redis_url: str = "redis://redis:6379/0"
    bot_internal_token: str
    encryption_key: str
    scanner_offline_seconds: int = 45
    public_api_url: str = "https://obd.lexora.by"


settings = Settings()
