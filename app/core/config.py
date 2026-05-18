import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    database_url: str
    groq_api_key: str = ""
    api_key: str = "sentinel-dev-key"
    cors_origins: list[str] = ["http://localhost:3000"]
    simulation_tick_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url")
    @classmethod
    def fix_db_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            # Accept JSON array: ["a","b"]
            if v.startswith("["):
                return json.loads(v)
            # Accept comma-separated: a,b,c
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


settings = Settings()
