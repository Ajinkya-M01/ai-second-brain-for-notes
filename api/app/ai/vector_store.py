"""ChromaDB persistent collection wrapper.

Responsibilities:
- Open (or create) a persistent local ChromaDB collection on startup.
- Upsert chunk vectors with metadata: source_id, chunk_id, page_number, title.
- Query top-k chunks by cosine distance for a question embedding.
- Delete all vectors belonging to a source_id (used on source delete/reindex).

ChromaDB is the *search index*, not the source of truth. The canonical text
lives in SQLite chunks. Embeddings can be rebuilt at any time by re-embedding
all chunks from the database.

Cosine distance (0 = identical, 2 = opposite). We convert to a similarity
score: similarity = 1 - (distance / 2), so 1.0 is perfect and 0.0 is worst.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("app.ai.vector_store")

_collection = None  # module-level singleton


def get_collection():
    """Return the shared ChromaDB collection, initializing it if needed."""
    global _collection
    if _collection is not None:
        return _collection

    import chromadb  # type: ignore
    from app.core.config import settings

    persist_dir = settings.CHROMA_PERSIST_DIR
    Path(persist_dir).mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=persist_dir)
    _collection = client.get_or_create_collection(
        name="second_brain_chunks",
        metadata={"hnsw:space": "cosine"},
    )
    logger.info("ChromaDB collection ready at %s (count=%d)", persist_dir, _collection.count())
    return _collection


def reset_collection_for_tests():
    """Reset the module-level singleton — for use in test fixtures only."""
    global _collection
    _collection = None


def upsert_chunks(
    chunks: List[Dict[str, Any]],
) -> None:
    """Upsert pre-embedded chunk vectors into ChromaDB.

    Args:
        chunks: list of dicts, each with:
            - "id": str  (chunk UUID, used as vector ID)
            - "embedding": List[float]
            - "text": str  (stored as document text for inspection)
            - "source_id": str
            - "title": str
            - "page_number": int | None
    """
    if not chunks:
        return

    collection = get_collection()
    ids = [c["id"] for c in chunks]
    embeddings = [c["embedding"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "source_id": c["source_id"],
            "title": c["title"],
            "page_number": c.get("page_number") if c.get("page_number") is not None else -1,
        }
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    logger.debug("Upserted %d vectors into ChromaDB", len(chunks))


def delete_by_source(source_id: str) -> None:
    """Remove all vectors belonging to a given source from ChromaDB."""
    collection = get_collection()
    collection.delete(where={"source_id": source_id})
    logger.debug("Deleted vectors for source_id=%s", source_id)


def query_similar(
    query_embedding: List[float],
    n_results: int = 5,
    source_ids: Optional[List[str]] = None,
    min_similarity: float = 0.0,
) -> List[Dict[str, Any]]:
    """Return ranked chunks similar to the query embedding.

    Args:
        query_embedding: float vector from the same embedding model.
        n_results: maximum number of results to return.
        source_ids: optional list to restrict search to specific sources.
        min_similarity: discard results with similarity below this threshold.

    Returns:
        List of dicts sorted by descending similarity:
        {chunk_id, source_id, title, page_number, text, similarity}
    """
    collection = get_collection()

    if collection.count() == 0:
        return []

    where = {"source_id": {"$in": source_ids}} if source_ids else None

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    ids = results["ids"][0]
    distances = results["distances"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    for chunk_id, dist, doc, meta in zip(ids, distances, documents, metadatas):
        # ChromaDB cosine distance: 0 = identical. Convert to 0-1 similarity.
        similarity = max(0.0, 1.0 - dist / 2.0)
        if similarity < min_similarity:
            continue
        page_number = meta.get("page_number")
        hits.append(
            {
                "chunk_id": chunk_id,
                "source_id": meta.get("source_id", ""),
                "title": meta.get("title", ""),
                "page_number": page_number if page_number != -1 else None,
                "text": doc,
                "similarity": round(similarity, 4),
            }
        )

    return hits
