from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration from environment variables (prefix ``SENDIT_``) or a ``.env`` file.

    Every value has a default that works for local development, so the service starts with
    zero configuration. Production overrides them via the environment (12-factor style).
    """

    model_config = SettingsConfigDict(env_prefix="SENDIT_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./sendit.db"
    log_level: str = "INFO"
    app_env: str = "local"


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once per process."""
    return Settings()
