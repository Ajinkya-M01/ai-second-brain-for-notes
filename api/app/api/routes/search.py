"""POST /api/v1/search — embed query and return ranked chunk hits.

No answer generation here — this milestone returns search results only.
The embedding provider is resolved at request time:
- If OPENROUTER_API_KEY is set, uses OpenRouterEmbeddingProvider.
- If not set, returns 503 with a clear disabled message.

Tests inject a FakeEmbeddingProvider via the `embedding_provider` dependency
override so no live API calls are made.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.embeddings import EmbeddingProvider, OpenRouterEmbeddingProvider
from app.ai import vector_store
from app.core.config import settings
from app.schemas.search import SearchHit, SearchRequest, SearchResponse

logger = logging.getLogger("app.api.routes.search")

router = APIRouter(prefix="/search", tags=["search"])


def get_embedding_provider() -> EmbeddingProvider:
    """Dependency: returns the configured embedding provider or raises 503."""
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "detail": "AI search is not configured. Set OPENROUTER_API_KEY in the backend environment.",
                "code": "ai_not_configured",
            },
        )
    return OpenRouterEmbeddingProvider()


@router.post(
    "",
    response_model=SearchResponse,
    summary="Semantic search over indexed chunks",
)
def search_endpoint(
    body: SearchRequest,
    provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> SearchResponse:
    """Embed the query with Nemotron and return the most similar chunks.

    Response includes source title, page number, and a text excerpt.
    Similarity is a 0-1 score (1 = identical). Results are ordered by
    descending similarity.
    """
    try:
        embeddings = provider.embed([body.query])
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": str(exc), "code": "embedding_failed"},
        )

    query_embedding = embeddings[0]

    raw_hits = vector_store.query_similar(
        query_embedding=query_embedding,
        n_results=body.limit,
        source_ids=body.source_ids or None,
    )

    hits = [
        SearchHit(
            chunk_id=h["chunk_id"],
            source_id=h["source_id"],
            title=h["title"],
            page_number=h["page_number"],
            excerpt=h["text"][:400],  # cap excerpt length for API response
            similarity=h["similarity"],
        )
        for h in raw_hits
    ]

    return SearchResponse(
        query=body.query,
        hits=hits,
        total=len(hits),
    )
