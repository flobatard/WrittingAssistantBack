import re

import chromadb
from langchain_text_splitters import MarkdownTextSplitter

from app.core.config import get_settings
from app.models.book import Book

settings = get_settings()


def _normalize_collection_name(name: str) -> str:
    """ChromaDB exige des noms composés uniquement de lettres, chiffres et underscores."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def vectorize_book(book: Book) -> dict:
    """
    Découpe le contenu Markdown du livre en chunks et les indexe dans ChromaDB.

    Returns:
        dict avec 'collection_name' et 'chunks_count'.
    """
    model_name = book.embedding_model_used or settings.EMBEDDING_MODEL_NAME
    raw_collection_name = f"book_{book.id}_{model_name}"
    collection_name = _normalize_collection_name(raw_collection_name)

    # 1. Découpage Markdown
    splitter = MarkdownTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(book.content)

    # 2. Initialisation ChromaDB
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    collection = client.get_or_create_collection(name=collection_name)

    # 3. Ajout des chunks (écrase les éventuels anciens documents)
    if chunks:
        collection.upsert(
            ids=[f"{book.id}_chunk_{i}" for i in range(len(chunks))],
            documents=chunks,
            metadatas=[{"book_id": book.id, "chunk_index": i} for i in range(len(chunks))],
        )

    return {
        "collection_name": collection_name,
        "chunks_count": len(chunks),
    }
