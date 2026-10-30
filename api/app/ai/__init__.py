"""AI provider adapters: embeddings and generation interfaces."""

from app.ai.embeddings import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    OpenRouterEmbeddingProvider,
)
from app.ai.generation import (
    FakeGenerationProvider,
    GenerationProvider,
    OpenRouterGenerationProvider,
)

__all__ = [
    "EmbeddingProvider",
    "OpenRouterEmbeddingProvider",
    "FakeEmbeddingProvider",
    "GenerationProvider",
    "OpenRouterGenerationProvider",
    "FakeGenerationProvider",
]
