from langchain_openai import OpenAIEmbeddings

from app.core.dependancies import EmbeddingConfig


def _normalize_base_url(url: str | None) -> str | None:
    """Ensure the base URL ends with /v1 for OpenAI-compatible APIs (e.g. Ollama)."""
    if not url:
        return None
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url


def get_embeddings(config: EmbeddingConfig) -> OpenAIEmbeddings:
    check_embedding_ctx_length = True
    if (config.provider == "ollama"):
        check_embedding_ctx_length = False
    return OpenAIEmbeddings(
        model=config.model or "text-embedding-3-large",
        api_key=config.api_key or "ollama",
        base_url=_normalize_base_url(config.url),
        check_embedding_ctx_length=check_embedding_ctx_length,
    )
