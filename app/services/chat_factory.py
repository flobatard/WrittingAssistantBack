from langchain_openai import ChatOpenAI

from app.core.dependancies import ChatConfig


def get_chat(config: ChatConfig) -> ChatOpenAI:
    return ChatOpenAI(
        model=config.model or "gpt-4o",
        api_key=config.api_key,
        base_url=config.url or None,
    )
