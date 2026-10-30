"""Security utilities for secret sanitization, file streaming limits, and defensive checks."""

import re
from fastapi import HTTPException, UploadFile, status
from app.core.config import settings


def sanitize_secret_text(text: str) -> str:
    """Scrub sensitive API keys, authorization bearer tokens, and credentials from text.

    Ensures that exception traces, logs, and error responses never leak secrets.
    """
    if not text:
        return text

    sanitized = text

    # 1. Redact configured OpenRouter API key if present
    if settings.OPENROUTER_API_KEY and len(settings.OPENROUTER_API_KEY) > 4:
        sanitized = sanitized.replace(settings.OPENROUTER_API_KEY, "[REDACTED_API_KEY]")

    # 2. Redact standard Bearer tokens (e.g. Bearer sk-or-v1-...)
    sanitized = re.sub(
        r"Bearer\s+[A-Za-z0-9_\-\.]{8,}",
        "Bearer [REDACTED_TOKEN]",
        sanitized,
        flags=re.IGNORECASE,
    )

    # 3. Redact common API key patterns (e.g. sk-or-v1-..., sk-...)
    sanitized = re.sub(
        r"sk-[a-zA-Z0-9_\-]{12,}",
        "[REDACTED_KEY]",
        sanitized,
    )

    return sanitized


async def read_bounded_upload_stream(file: UploadFile, max_bytes: int) -> bytes:
    """Read an uploaded file in bounded chunks to prevent denial-of-service memory exhaustion.

    Args:
        file: The uploaded FastAPI UploadFile.
        max_bytes: Maximum allowed bytes before rejecting the stream.

    Returns:
        Accumulated file bytes.

    Raises:
        HTTPException(413): If total stream bytes exceed max_bytes.
    """
    chunk_size = 1024 * 64  # 64 KB read buffer
    accumulated = bytearray()
    total_bytes = 0

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed upload cap of {max_bytes / (1024 * 1024):.1f} MB.",
            )
        accumulated.extend(chunk)

    return bytes(accumulated)

