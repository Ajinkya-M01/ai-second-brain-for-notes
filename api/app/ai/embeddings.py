"""Embedding provider interface and adapters.

Design:
- EmbeddingProvider is a simple abstract base; code outside this module
  only depends on the interface, not the concrete implementation.
- OpenRouterEmbeddingProvider calls nvidia/nemotron-3-embed-1b:free via the
  OpenAI-compatible API. The key is read solely from backend environment
  (settings.OPENROUTER_API_KEY). It is never logged or returned to callers.
- FakeEmbeddingProvider produces deterministic random-ish vectors for
  automated tests. It must never appear in production configuration.
- tenacity handles transient 429/5xx with bounded exponential backoff + jitter.
  Non-transient errors (4xx except 429) are re-raised immediately without retry.
"""

import hashlib
import logging
import random
import struct
from abc import ABC, abstractmethod
from typing import List

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.security import sanitize_secret_text

logger = logging.getLogger("app.ai.embeddings")

# Expected embedding dimension for nemotron-3-embed-1b
NEMOTRON_EMBED_DIM = 1024


def _is_transient(exc: Exception) -> bool:
    """Return True only for rate-limit or server errors worth retrying."""
    try:
        from openai import APIStatusError  # type: ignore

        if isinstance(exc, APIStatusError):
            return exc.status_code in (429, 500, 502, 503, 504)
    except ImportError:
        pass
    return False


class EmbeddingProvider(ABC):
    """Interface for embedding a list of text strings into float vectors."""

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return one embedding vector per input text.

        Args:
            texts: Non-empty list of strings to embed.

        Returns:
            List of float vectors, one per input, in the same order.

        Raises:
            RuntimeError: If the provider is unavailable or returns unexpected output.
        """


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    """Calls OpenRouter's embeddings endpoint using the OpenAI Python client.

    The model slug (nvidia/nemotron-3-embed-1b:free) and base URL are both
    configurable via settings so tests can override them without environment hacks.
    The API key is loaded once at construction time from settings and is never
    logged, returned, or sent to the frontend.
    """

    def __init__(self) -> None:
        from openai import OpenAI  # type: ignore
        from app.core.config import settings

        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. "
                "Set it in your .env file to enable embedding and search."
            )

        self._model = settings.OPENROUTER_EMBEDDING_MODEL
        self._client = OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
        )

    @retry(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=1, max=30),
        reraise=True,
    )
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed texts via OpenRouter. Retries on transient 429/5xx only."""
        if not texts:
            return []

        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
        except Exception as exc:
            # Log provider errors (without leaking the key or authorization headers)
            logger.error(
                "Embedding provider error (%s): %s",
                type(exc).__name__,
                sanitize_secret_text(str(exc)),
            )
            raise RuntimeError(
                f"Embedding service unavailable ({type(exc).__name__}). "
                "Check OPENROUTER_API_KEY and model availability."
            ) from exc

        if len(response.data) != len(texts):
            raise RuntimeError(
                f"Embedding provider returned {len(response.data)} vectors "
                f"for {len(texts)} inputs."
            )

        return [item.embedding for item in response.data]


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic fake embeddings for automated tests.

    Each text is hashed to a seed so the same text always produces the
    same vector. Vectors are NOT meaningful for similarity; they exist only
    to let the full indexing/search code path run without a live API call.

    IMPORTANT: Never use this in production — ChromaDB will hold garbage vectors.
    """

    def __init__(self, dim: int = NEMOTRON_EMBED_DIM) -> None:
        self._dim = dim

    def embed(self, texts: List[str]) -> List[List[float]]:
        result: List[List[float]] = []
        for text in texts:
            seed_bytes = hashlib.sha256(text.encode()).digest()
            # Unpack first 4 bytes as uint32 for a deterministic seed
            seed = struct.unpack(">I", seed_bytes[:4])[0]
            rng = random.Random(seed)
            vec = [rng.gauss(0.0, 1.0) for _ in range(self._dim)]
            # L2-normalize so cosine distance behaves predictably
            magnitude = sum(v * v for v in vec) ** 0.5 or 1.0
            result.append([v / magnitude for v in vec])
        return result
