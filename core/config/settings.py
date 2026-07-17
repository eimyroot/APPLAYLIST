from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "APPLAYLIST"
    app_env: str = "development"
    app_debug: bool = True

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_version: str = "0.1.0"
    schema_version: str = "0.1.0"

    log_level: str = "INFO"
    log_json: bool = True

    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173"

    database_url: str = "sqlite:///./applaylist.db"
    redis_url: str = "redis://redis:6379/0"

    api_token: str = "change-me"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"

    security_mode: str = "DEV"
    enable_embeddings: bool = False
    enable_external_connectors: bool = False
    enable_advanced_structure: bool = False
    enable_generative_preview: bool = False
    enable_composition_comparison: bool = False

    artifacts_dir: str = "./artifacts"
    exports_dir: str = "./exports"
    logs_dir: str = "./logs"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
