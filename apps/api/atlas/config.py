from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../../.env", ".env"), extra="ignore")

    app_name: str = "Atlas API"
    database_url: str = "sqlite:///./atlas.db"
    atlas_auth_mode: str = "demo"
    atlas_demo_org_id: str = "org_atlas_demo"
    atlas_demo_role: str = "admin"
    auth0_domain: str = ""
    auth0_audience: str = "https://api.atlas.local"
    auth0_issuer: str = ""
    cors_origins: str = "http://localhost:3000"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        """Render supplies a generic Postgres URL; Atlas uses the installed psycopg v3 driver."""
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @property
    def origins(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
