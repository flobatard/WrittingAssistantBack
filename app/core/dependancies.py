# app/core/dependencies.py
from fastapi import Header, HTTPException, Depends

async def get_chat_api_key(x_chat_api_key: str | None = Header(default=None)):
    if not x_chat_api_key:
        raise HTTPException(status_code=401, detail="Clé API Chat manquante dans les headers")
    return x_chat_api_key

async def get_embedding_api_key(x_embedding_api_key: str | None = Header(default=None)):
    if not x_embedding_api_key:
        raise HTTPException(status_code=401, detail="Clé API Embedding manquante")
    return x_embedding_api_key