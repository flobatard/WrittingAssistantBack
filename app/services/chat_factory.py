from langchain_openai import ChatOpenAI

from app.core.dependancies import ChatConfig

def _normalize_base_url(url: str | None) -> str | None:
    """Ensure the base URL ends with /v1 for OpenAI-compatible APIs (e.g. Ollama)."""
    if not url:
        return None
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url

def get_chat(config: ChatConfig) -> ChatOpenAI:
    return ChatOpenAI(
        model=config.model or "gpt-4o",
        api_key=config.api_key or "ollama",
        base_url=_normalize_base_url(config.url) or None,
    )
