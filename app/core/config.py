import json
from typing import Any
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    groq_api_key: str = ""
    api_key: str = "sentinel-dev-key"
    # Stored as str to prevent pydantic-settings from auto-JSON-parsing it.
    # Accepted formats: JSON array OR comma-separated plain string.
    cors_origins: Any = "http://localhost:3000"
    simulation_tick_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def parse_and_fix(self) -> "Settings":
        # Fix postgres:// → postgresql://
        if isinstance(self.database_url, str) and self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql://", 1)

        # Parse cors_origins into a proper list
        v = self.cors_origins
        if isinstance(v, list):
            pass
        elif isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                try:
                    v = json.loads(v)
                except json.JSONDecodeError:
                    v = [v]
            else:
                v = [o.strip() for o in v.split(",") if o.strip()]
            self.cors_origins = v
        return self


settings = Settings()
