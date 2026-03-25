from app.core.dependancies import EmbeddingConfig



def get_embeddings(config : EmbeddingConfig):
    if config.provider == "openai":
        return OpenAIEmbeddings(
            model=config.model or "text-embedding-3-large",
            api_key=config.api_key,
        )

    elif config.provider_type == "openai_compatible":
        return OpenAIEmbeddings(
            model=config.model,
            api_key=config.api_key,
            base_url=config.url,  # 🔥 clé pour ton provider custom
        )

    else:
        raise ValueError(f"Provider inconnu: {config.provider} and not openai_compatible: {config.provider_type}")