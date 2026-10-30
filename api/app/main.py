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

from app.core.config import settings, IS_VERCEL
from app.core.security import sanitize_secret_text
from app.api.routes.health import router as health_router
from app.api.routes.notes import router as notes_router
from app.api.routes.sources import router as sources_router
from app.api.routes.documents import router as documents_router
from app.api.routes.search import router as search_router
from app.api.routes.chat import router as chat_router

logger = logging.getLogger("app.main")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Local AI Second Brain API",
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log full trace of unhandled exceptions without leaking secrets, returning safe detail."""
    safe_exc_str = sanitize_secret_text(str(exc))
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, safe_exc_str)
    detail = safe_exc_str if settings.APP_ENV == "development" else "Internal Server Error"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail},
    )


# Configure CORS for local development (strictly restricted to known frontend origins)
allowed_origins = list(
    dict.fromkeys(
        origin.strip()
        for origin in [
            settings.FRONTEND_ORIGIN,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        if origin and origin.strip()
    )
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Root-level & readiness health probes (Blueprint Section 6)
app.include_router(health_router)

# Versioned API routes under /api/v1
app.include_router(notes_router, prefix=settings.API_V1_STR)
app.include_router(sources_router, prefix=settings.API_V1_STR)
app.include_router(documents_router, prefix=settings.API_V1_STR)
app.include_router(search_router, prefix=settings.API_V1_STR)
app.include_router(chat_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
async def startup_event():
    """Warm up ChromaDB on startup so the first request is not slow.
    If OPENROUTER_API_KEY is not set, vector search and chat will return 503 but
    the rest of the app (notes, PDF upload, CRUD) still works normally.
    """
    try:
        from app.ai import vector_store
        vector_store.get_collection()
    except Exception as exc:
        logger.warning("ChromaDB startup init failed (non-fatal): %s", exc)


# On Vercel there is no migration step and the SQLite file starts empty on each
# cold start, so create the schema directly. Locally, Alembic remains the source of truth.
if IS_VERCEL:
    from app.db.models import Base
    from app.db.session import engine

    Base.metadata.create_all(bind=engine)
