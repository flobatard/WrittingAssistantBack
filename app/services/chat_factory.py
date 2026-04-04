from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel # La classe parente

from app.core.dependancies import ChatConfig

def _normalize_base_url(url: str | None) -> str | None:
    """Ensure the base URL ends with /v1 for OpenAI-compatible APIs (e.g. Ollama)."""
    if not url:
        return None
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url

def get_chat(config: ChatConfig) -> BaseChatModel:
    if (config.provider_type == "gemini"):
        return ChatGoogleGenerativeAI(
            model=config.model or "gemini-1.5-flash",
            google_api_key=config.api_key
            # Le SDK Google gère ses propres URLs, 
            # mais tu peux passer 'client_options' si tu as un proxy spécifique.
        )
    return ChatOpenAI(
        model=config.model or "gpt-4o",
        api_key=config.api_key or "ollama",
        base_url=_normalize_base_url(config.url) or None,
    )
