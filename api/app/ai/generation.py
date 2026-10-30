"""Generation provider interface and adapters for chat completions.

Design:
- GenerationProvider is an abstract base class; callers depend only on the interface.
- OpenRouterGenerationProvider calls nvidia/nemotron-3.5-lightning:free via the
  OpenAI-compatible chat completions API. The API key is read solely from backend
  environment settings (settings.OPENROUTER_API_KEY) and is never logged or returned.
- No paid model fallbacks are configured.
- Tenacity handles transient 429 and 5xx errors with bounded exponential backoff and jitter.
- FakeGenerationProvider provides deterministic, configurable responses for automated tests
  without requiring network access or external API keys.
"""

import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.security import sanitize_secret_text

logger = logging.getLogger("app.ai.generation")


def _is_transient(exc: Exception) -> bool:
    """Return True only for rate-limit or server errors worth retrying."""
    try:
        from openai import APIStatusError  # type: ignore

        if isinstance(exc, APIStatusError):
            return exc.status_code in (429, 500, 502, 503, 504)
    except ImportError:
        pass
    return False


class GenerationProvider(ABC):
    """Interface for text generation / chat completions."""

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        """Generate a completion for the provided message sequence.

        Args:
            messages: List of message dictionaries with 'role' and 'content'.
            max_tokens: Maximum tokens in the generated response.
            temperature: Sampling temperature (lower = more deterministic).

        Returns:
            Generated assistant response text.

        Raises:
            RuntimeError: If generation fails unrecoverably.
        """


class OpenRouterGenerationProvider(GenerationProvider):
    """Calls OpenRouter's chat completions endpoint using the OpenAI Python client.

    Model: nvidia/nemotron-3.5-lightning:free (from settings.OPENROUTER_CHAT_MODEL).
    Base URL: https://openrouter.ai/api/v1 (from settings.OPENROUTER_BASE_URL).
    """

    def __init__(self) -> None:
        from openai import OpenAI  # type: ignore
        from app.core.config import settings

        if not settings.OPENROUTER_API_KEY:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. "
                "Set it in your .env file to enable chat completions."
            )

        self._model = settings.OPENROUTER_CHAT_MODEL
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
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        """Generate an answer using OpenRouter chat completions. Retries on transient 429/5xx only."""
        if not messages:
            return ""

        # Strictly cap maximum generated tokens to prevent runaway output
        bounded_max_tokens = min(max_tokens, 1024)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore
                max_tokens=bounded_max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            # Log provider errors without leaking the API key or authorization headers
            logger.error(
                "Generation provider error (%s): %s",
                type(exc).__name__,
                sanitize_secret_text(str(exc)),
            )
            raise RuntimeError(
                f"Generation service unavailable ({type(exc).__name__}). "
                "Check OPENROUTER_API_KEY and model availability."
            ) from exc

        choice = response.choices[0]
        content = choice.message.content or ""
        return content.strip()


class FakeGenerationProvider(GenerationProvider):
    """Deterministic fake generator for automated tests.

    Supports custom fixed responses, response queues, or dynamic callbacks.
    Records calls for assertion verification.
    """

    def __init__(
        self,
        default_response: str = "Based on the provided information [S1], here is the answer.",
        responses: Optional[List[str]] = None,
        callback: Optional[Callable[[List[Dict[str, str]]], str]] = None,
    ) -> None:
        self.default_response = default_response
        self._responses = list(responses) if responses else []
        self._callback = callback
        self.call_count = 0
        self.last_messages: Optional[List[Dict[str, str]]] = None

    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        self.call_count += 1
        self.last_messages = messages

        if self._callback is not None:
            return self._callback(messages)

        if self._responses:
            return self._responses.pop(0)

        return self.default_response
