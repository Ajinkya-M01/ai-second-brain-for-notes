import logging
import sys
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure api directory is always on sys.path
_API_DIR = Path(__file__).resolve().parent.parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from app.core.config import settings
from app.api.routes.health import router as health_router
from app.api.routes.notes import router as notes_router
from app.api.routes.sources import router as sources_router
from app.api.routes.documents import router as documents_router

logger = logging.getLogger("app.main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Local AI Second Brain API",
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log full trace of unhandled exceptions and return readable error message."""
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    detail = str(exc) if settings.APP_ENV == "development" else "Internal Server Error"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail},
    )


# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_ORIGIN,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root-level & readiness health probes (Blueprint Section 6)
app.include_router(health_router)

# Versioned API routes under /api/v1
app.include_router(notes_router, prefix=settings.API_V1_STR)
app.include_router(sources_router, prefix=settings.API_V1_STR)
app.include_router(documents_router, prefix=settings.API_V1_STR)
