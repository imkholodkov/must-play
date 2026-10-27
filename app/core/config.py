"""Настройки приложения из переменных окружения и файла .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Must Play"
    database_url: str = "postgresql+psycopg://mustplay:change-me@localhost:5432/mustplay"


@lru_cache
def get_settings() -> Settings:
    return Settings()
