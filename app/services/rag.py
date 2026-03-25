import re

from langchain_text_splitters import MarkdownTextSplitter
from langchain_chroma import Chroma
from app.services.embeddings_factory import get_embeddings

from app.core.config import get_chroma_client
from app.models.book import Book

from app.core.dependancies import EmbeddingConfig


def _normalize_collection_name(name: str) -> str:
    """ChromaDB exige des noms composés uniquement de lettres, chiffres et underscores."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def vectorize_book(book: Book, embedding_config: EmbeddingConfig) -> dict:
    """
    Découpe le contenu Markdown du livre en chunks et les indexe dans ChromaDB.

    Returns:
        dict avec 'collection_name' et 'chunks_count'.
    """
    model_name = embedding_config.model
    raw_collection_name = f"book_{book.id}_{model_name}"
    collection_name = _normalize_collection_name(raw_collection_name)

    # 1. Découpage Markdown
    splitter = MarkdownTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(book.content)

    # 2.
    embeddings = get_embeddings(embedding_config)

    # 3. Get or create the collection — UUID stays stable across re-vectorizations
    vectordb = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        client=get_chroma_client(),
    )

    # 4. Remove existing documents for this book before re-inserting
    existing = vectordb.get(where={"book_id": book.id})
    if existing["ids"]:
        vectordb.delete(ids=existing["ids"])

    # 5. Insert
    if chunks:
        vectordb.add_texts(
            texts=chunks,
            metadatas=[{"book_id": book.id, "chunk_index": i} for i in range(len(chunks))],
            ids=[f"{book.id}_chunk_{i}" for i in range(len(chunks))],
        )

    return {
        "collection_name": collection_name,
        "chunks_count": len(chunks),
    }
