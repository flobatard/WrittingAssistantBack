# app/core/dependencies.py
from dataclasses import dataclass
from fastapi import Header, HTTPException

@dataclass
class ChatConfig:
    provider: str
    api_key: str | None
    url: str | None
    model: str | None

@dataclass
class EmbeddingConfig:
    provider: str
    api_key: str | None
    url: str | None
    model: str | None

async def get_chat_config(
    x_chat_provider: str | None = Header(default=None),
    x_chat_api_key: str | None = Header(default=None),
    x_chat_api_url: str | None = Header(default=None),
    x_chat_model: str | None = Header(default=None),
) -> ChatConfig:
    if not x_chat_provider:
        raise HTTPException(status_code=401, detail="X-Chat-Provider manquant dans les headers")
    return ChatConfig(
        provider=x_chat_provider,
        api_key=x_chat_api_key,
        url=x_chat_api_url,
        model=x_chat_model,
    )

async def get_embedding_config(
    x_embedding_provider: str | None = Header(default=None),
    x_embedding_api_key: str | None = Header(default=None),
    x_embedding_api_url: str | None = Header(default=None),
    x_embedding_model: str | None = Header(default=None),
) -> EmbeddingConfig:
    if not x_embedding_provider:
        raise HTTPException(status_code=401, detail="X-Embedding-Provider manquant dans les headers")
    return EmbeddingConfig(
        provider=x_embedding_provider,
        api_key=x_embedding_api_key,
        url=x_embedding_api_url,
        model=x_embedding_model,
    )