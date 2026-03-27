import re
from typing import Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter
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
    Indexe chaque nœud du manuscrit individuellement dans ChromaDB avec des métadonnées riches.

    Returns:
        dict avec 'collection_name' et 'chunks_count'.
    """
    model_name = embedding_config.model
    collection_name = _normalize_collection_name(f"book_{book.id}_{model_name}")

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)

    # 1. Chunker chaque nœud individuellement et attacher ses métadonnées
    all_documents = []
    for node in chapters:
        if not node.content:
            continue
        node_text = f"# {node.title}\n\n{node.content}"
        splits = text_splitter.create_documents([node_text])
        for i, doc in enumerate(splits):
            doc.metadata = {
                "book_id": book.id,
                "book_title": book.title,
                "node_front_id": str(node.front_id),
                "node_type": node.node_type,
                "node_title": node.title,
                "position": node.position,
                "depth_level": node.depth_level,
                "chunk_index": i,
            }
        all_documents.extend(splits)

    # 2. Supprimer toutes les collections existantes pour ce livre (tous modèles confondus)
    client = get_chroma_client()
    prefix = _normalize_collection_name(f"book_{book.id}_")
    for col in client.list_collections():
        if col.name.startswith(prefix):
            client.delete_collection(col.name)

    # 3. Créer la nouvelle collection et insérer en batches
    embeddings = get_embeddings(embedding_config)
    vectordb = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        client=client,
    )

    BATCH_SIZE = 5000
    for start in range(0, len(all_documents), BATCH_SIZE):
        batch = all_documents[start:start + BATCH_SIZE]
        ids = [
            f"{book.id}_{doc.metadata['node_front_id']}_chunk_{doc.metadata['chunk_index']}"
            for doc in batch
        ]
        vectordb.add_documents(batch, ids=ids)

    return {
        "collection_name": collection_name,
        "chunks_count": len(all_documents),
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
