from functools import lru_cache

import chromadb
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    APP_ENV: str = "development"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:4200"]

    # Base de données SQL (PostgreSQL via asyncpg)
    DATABASE_URL: str = "postgresql+asyncpg://writing_user:writing_password@localhost:5430/writing_assistant"

    # ChromaDB HTTP
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001

    OIDC_ISSUER_URL: str = "http://localhost:8080/realms/writting_assistant"
    # Optionnal
    OIDC_AUDIENCE: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_chroma_client() -> chromadb.HttpClient:
    s = get_settings()
    return chromadb.HttpClient(host=s.CHROMA_HOST, port=s.CHROMA_PORT)
