import re
from typing import Sequence

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from app.services.embeddings_factory import get_embeddings

from app.core.config import get_chroma_client
from app.models.book import Book
from app.models.manuscript_node import ManuscriptNode

from app.core.dependancies import EmbeddingConfig


def _normalize_collection_name(name: str) -> str:
    """ChromaDB exige des noms composés uniquement de lettres, chiffres et underscores."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def vectorize_book(book: Book, embedding_config: EmbeddingConfig, chapters: Sequence[ManuscriptNode]) -> dict:
    """
    Agrège le contenu Markdown des chapitres (ordonnés par position) et les indexe dans ChromaDB.

    Returns:
        dict avec 'collection_name' et 'chunks_count'.
    """
    model_name = embedding_config.model
    raw_collection_name = f"book_{book.id}_{model_name}"
    collection_name = _normalize_collection_name(raw_collection_name)

    # 1. Concaténer les chapitres dans l'ordre
    combined_content = "\n\n".join(
        f"# {chapter.title}\n\n{chapter.content}" for chapter in chapters
    )

    # 2. Découpage Markdown
    markdown_splitter = MarkdownHeaderTextSplitter(chunk_size=1500, chunk_overlap=200)
    md_header_splits = markdown_splitter.split_text(combined_content)

    # 3. Ensuite, on sous-découpe les chapitres trop longs avec un splitter classique
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500, 
        chunk_overlap=200
    )
    chunks = text_splitter.split_documents(md_header_splits)

    embeddings = get_embeddings(embedding_config)

    # 4. Get or create the collection
    vectordb = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        client=get_chroma_client(),
    )

    # 5. Remove existing documents for this book before re-inserting
    existing = vectordb.get(where={"book_id": book.id})
    if existing["ids"]:
        vectordb.delete(ids=existing["ids"])

    client = get_chroma_client()

    # 6. Supprimer toutes les collections existantes pour ce livre (tous modèles confondus)
    prefix = _normalize_collection_name(f"book_{book.id}_")
    for col in client.list_collections():
        if col.name.startswith(prefix) and col.name != collection_name:
            client.delete_collection(col.name)

    # 7. Insert in batches to respect ChromaDB's max batch size
    BATCH_SIZE = 5000
    if chunks:
        for start in range(0, len(chunks), BATCH_SIZE):
            end = start + BATCH_SIZE
            vectordb.add_texts(
                texts=chunks[start:end],
                metadatas=[{"book_id": book.id, "chunk_index": i} for i in range(start, min(end, len(chunks)))],
                ids=[f"{book.id}_chunk_{i}" for i in range(start, min(end, len(chunks)))],
            )

    return {
        "collection_name": collection_name,
        "chunks_count": len(chunks),
    }


def query_book(book: Book, query: str, embedding_config: EmbeddingConfig, k: int = 5) -> dict:
    """
    Recherche les chunks les plus pertinents pour une question donnée.

    Returns:
        dict avec 'query', 'results' (liste de chunks avec score et metadata).
    """
    model_name = embedding_config.model
    raw_collection_name = f"book_{book.id}_{model_name}"
    collection_name = _normalize_collection_name(raw_collection_name)

    embeddings = get_embeddings(embedding_config)

    vectordb = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        client=get_chroma_client(),
    )

    results = vectordb.similarity_search_with_score(query, k=k)

    return {
        "query": query,
        "results": [
            {
                "content": doc.page_content,
                "score": score,
                "metadata": doc.metadata,
            }
            for doc, score in results
        ],
    }
