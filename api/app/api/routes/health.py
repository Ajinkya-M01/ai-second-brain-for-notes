"""Health and readiness routes."""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    details: Dict[str, Any] = {}


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Liveness probe returning simple OK status."""
    return HealthResponse(status="ok")


@router.get("/api/v1/health/ready", response_model=ReadinessResponse)
def get_readiness(db: Session = Depends(get_db)) -> ReadinessResponse:
    """Check database connectivity without exposing sensitive credentials."""
    try:
        db.execute(text("SELECT 1"))
        return ReadinessResponse(
            status="ready",
            database="connected",
            details={"sqlite": "operational"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database not ready: {str(exc)}",
        )
