from fastapi import APIRouter

from app.core.config import get_chroma_client

router = APIRouter(tags=["dev"])


@router.get("/chroma/collections")
def list_chroma_collections():
    client = get_chroma_client()
    collections = client.list_collections()
    return [
        {
            "name": col.name,
            "count": col.count(),
        }
        for col in collections
    ]


@router.get("/chroma/collections/{collection_name}")
def get_chroma_collection(collection_name: str, limit: int = 10, offset: int = 0):
    client = get_chroma_client()
    col = client.get_collection(collection_name)
    result = col.get(limit=limit, offset=offset, include=["documents", "metadatas"])
    return {
        "name": collection_name,
        "total_count": col.count(),
        "items": [
            {
                "id": id_,
                "document": doc,
                "metadata": meta,
            }
            for id_, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
        ],
    }


@router.delete("/chroma/collections/{collection_name}")
def delete_chroma_collection(collection_name: str):
    client = get_chroma_client()
    client.delete_collection(collection_name)
    return {"deleted": collection_name}
