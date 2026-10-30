"""In-memory sliding window rate limiter for chat and ingestion endpoints.

Enforces Blueprint Section 10:
"Rate-limit upload, indexing, and chat; cap prompt context, question length, output tokens and concurrency."
"""

import time
from collections import defaultdict
from typing import Dict, List
from fastapi import HTTPException, Request, status
from app.core.config import settings

# client_id -> list of timestamps
_request_history: Dict[str, List[float]] = defaultdict(list)


def check_rate_limit(
    client_id: str,
    max_requests: int,
    window_seconds: int = 60,
    action_name: str = "requests",
) -> None:
    """Check sliding window rate limit for a client identifier.

    Args:
        client_id: Identifier such as client IP address.
        max_requests: Maximum allowed requests within the time window.
        window_seconds: Window duration in seconds (default 60s).
        action_name: Readable noun for the error detail message.

    Raises:
        HTTPException(429): If rate limit is exceeded.
    """
    now = time.monotonic()
    cutoff = now - window_seconds

    # Evict timestamps older than the sliding window
    history = [ts for ts in _request_history[client_id] if ts > cutoff]
    _request_history[client_id] = history

    if len(history) >= max_requests:
        retry_after = int(window_seconds - (now - history[0])) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "detail": f"Rate limit exceeded ({max_requests} {action_name}/minute). Please wait {retry_after}s before trying again.",
                "code": "rate_limit_exceeded",
                "retry_after_seconds": max(1, retry_after),
            },
            headers={"Retry-After": str(max(1, retry_after))},
        )

    _request_history[client_id].append(now)


def get_client_ip(request: Request) -> str:
    """Resolve client IP address from request, considering proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def chat_rate_limiter(request: Request) -> None:
    """FastAPI dependency to rate limit chat completions per client IP."""
    client_ip = get_client_ip(request)
    check_rate_limit(
        client_id=f"chat:{client_ip}",
        max_requests=settings.MAX_CHAT_REQUESTS_PER_MINUTE,
        window_seconds=60,
        action_name="chat questions",
    )


def reset_rate_limits() -> None:
    """Reset all stored rate limit histories (for use in automated tests)."""
    _request_history.clear()

