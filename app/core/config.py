from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    APP_ENV: str = "development"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:4200"]

    # Base de données SQL (PostgreSQL via asyncpg)
    DATABASE_URL: str = "postgresql+asyncpg://writing_user:writing_password@localhost:5430/writing_assistant"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # Embeddings
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def get_settings() -> Settings:
    return Settings()
