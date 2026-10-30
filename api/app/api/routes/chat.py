"""POST /api/v1/chat — Grounded question-answering over indexed chunks.

Design:
- Uses OpenRouterGenerationProvider with nvidia/nemotron-3.5-lightning:free.
- Retrieves relevant chunks first; if retrieval yields no adequate evidence,
  returns a clear "I couldn't find this in your sources" response without invoking the LLM.
- Validates citation labels in backend code and builds citation metadata strictly from
  retrieved chunks. Model-invented citations are discarded.
- Does not configure paid model fallbacks.
- Returns 503 if OPENROUTER_API_KEY is not configured or if provider services fail.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.embeddings import EmbeddingProvider
from app.ai.generation import GenerationProvider, OpenRouterGenerationProvider
from app.api.routes.search import get_embedding_provider
from app.core.config import settings
from app.core.rate_limit import chat_rate_limiter
from app.core.security import sanitize_secret_text
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import answer_question

logger = logging.getLogger("app.api.routes.chat")

router = APIRouter(prefix="/chat", tags=["chat"])


def get_generation_provider() -> GenerationProvider:
    """Dependency: returns configured OpenRouterGenerationProvider or raises 503."""
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "detail": "AI chat is not configured. Set OPENROUTER_API_KEY in the backend environment.",
                "code": "ai_not_configured",
            },
        )
    return OpenRouterGenerationProvider()


@router.post(
    "",
    response_model=ChatResponse,
    summary="Grounded question-answering with citations",
    dependencies=[Depends(chat_rate_limiter)],
)
def chat_endpoint(
    body: ChatRequest,
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    generation_provider: GenerationProvider = Depends(get_generation_provider),
) -> ChatResponse:
    """Answer a user question strictly grounded in retrieved second brain notes and PDFs.

    Returns:
        ChatResponse containing the answer text, verified citation objects, and grounded flag.
    """
    try:
        response = answer_question(
            question=body.question,
            embedding_provider=embedding_provider,
            generation_provider=generation_provider,
            source_ids=body.source_ids,
            limit=body.limit,
            min_similarity=body.min_similarity,
            conversation_id=body.conversation_id,
        )
        return response
    except RuntimeError as exc:
        safe_detail = sanitize_secret_text(str(exc))
        logger.error("Chat generation failed: %s", safe_detail)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": safe_detail, "code": "chat_service_failed"},
        )

