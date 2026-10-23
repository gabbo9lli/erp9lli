import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "ERP9lli API"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False

    DB_TYPE: str = "sqlite"
    DATABASE_URL: str = "sqlite:///./site.db"

    JWT_SECRET_KEY: str = "super-secret-key"

    DEV_AUTH_USER: str = "dev@example.com"
    DEV_AUTH_ROLE: str = "Admin"

    ECOMMERCE_WEBHOOK_SECRET: str = "spree-secret-token"

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    SMTP_ENABLED: bool = False

    ENABLED_MODULES: str = "all"
    TESTING: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def is_module_enabled(self, module_name: str) -> bool:
        enabled = self.ENABLED_MODULES.strip().lower()
        if enabled == "all" or not enabled:
            return True
        active_set = {m.strip().lower() for m in enabled.split(",") if m.strip()}
        return module_name.strip().lower() in active_set

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_testing(self) -> bool:
        return bool(self.TESTING) or os.getenv("TESTING", "0").lower() in ("1", "true")

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
