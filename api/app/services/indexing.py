"""Indexing service: embed chunks and upsert into ChromaDB.

Called after note creation/update and PDF upload.  The sequence is:
1. Load chunks from SQLite for the given source.
2. Embed them in batches using the injected EmbeddingProvider.
3. Upsert vectors into ChromaDB with source metadata.
4. Mark source.status = "indexed" (or "failed" on unrecoverable error).

SQLite stays consistent (source + chunks saved first) before any vector call,
so a failed embedding leaves the source in "failed" status and the canonical
text intact for retry.
"""

import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.ai import vector_store
from app.db.models import Chunk, Source

logger = logging.getLogger("app.services.indexing")

# Embed at most this many chunks per API call to stay within request limits
EMBED_BATCH_SIZE = 32


def index_source(
    db: Session,
    source_id: str,
    provider: EmbeddingProvider,
    title: Optional[str] = None,
) -> None:
    """Embed all chunks for a source and upsert into ChromaDB.

    Args:
        db: SQLAlchemy session (chunks already committed).
        source_id: UUID of the source to index.
        provider: EmbeddingProvider instance (real or fake for tests).
        title: optional override; if None, loaded from the source row.

    Raises:
        RuntimeError: if the embedding provider fails unrecoverably.
    """
    source = db.get(Source, source_id)
    if source is None:
        logger.warning("index_source: source %s not found in DB", source_id)
        return

    if title is None:
        title = source.title

    # Load all chunks for this source ordered by ordinal
    chunks: List[Chunk] = list(
        db.scalars(
            select(Chunk)
            .where(Chunk.source_id == source_id)
            .order_by(Chunk.ordinal)
        ).all()
    )

    if not chunks:
        logger.info("index_source: source %s has no chunks to embed", source_id)
        source.status = "indexed"
        db.commit()
        return

    # Delete old vectors first so re-index is clean (idempotent)
    vector_store.delete_by_source(source_id)

    try:
        embedded_chunks = []

        # Embed in batches
        for i in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch = chunks[i : i + EMBED_BATCH_SIZE]
            texts = [c.text for c in batch]
            embeddings = provider.embed(texts)

            for chunk, embedding in zip(batch, embeddings):
                embedded_chunks.append(
                    {
                        "id": chunk.id,
                        "embedding": embedding,
                        "text": chunk.text,
                        "source_id": source_id,
                        "title": title,
                        "page_number": chunk.page_number,
                    }
                )

        vector_store.upsert_chunks(embedded_chunks)
        source.status = "indexed"
        logger.info(
            "Indexed source %s (%s) — %d chunks embedded",
            source_id,
            title,
            len(embedded_chunks),
        )

    except Exception as exc:
        source.status = "failed"
        source.error_message = str(exc)[:500]
        logger.error("Failed to index source %s: %s", source_id, exc)
        raise

    finally:
        db.commit()


def delete_source_vectors(source_id: str) -> None:
    """Remove all vectors for a source from ChromaDB. Called on source delete."""
    vector_store.delete_by_source(source_id)
    logger.info("Deleted vectors for source %s", source_id)
