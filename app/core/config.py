from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    APP_ENV: str = "development"

    # Base de données SQL
    DATABASE_URL: str = "sqlite+aiosqlite:///./writing_assistant.db"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # Embeddings
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache
def get_settings() -> Settings:
    return Settings()
