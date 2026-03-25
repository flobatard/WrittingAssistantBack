from langchain_openai import OpenAIEmbeddings

from app.core.dependancies import EmbeddingConfig


def get_embeddings(config: EmbeddingConfig) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=config.model or "text-embedding-3-large",
        api_key=config.api_key,
        base_url=config.url or None,
    )
