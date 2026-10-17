"""API route endpoints for generic Sources (notes and documents)."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from app.db.models import Chunk
from app.db.session import get_db
from app.schemas.chunk import ChunkListResponse, ChunkResponse
from app.schemas.source import SourceListResponse, SourceResponse
from app.services import notes as note_service
from sqlalchemy import func, select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/sources", tags=["sources"])


def to_source_response(source) -> SourceResponse:
    """Helper to convert Source DB model to SourceResponse DTO."""
    return SourceResponse(
        id=source.id,
        kind=source.kind,
        title=source.title,
        content=source.content,
        original_filename=source.original_filename,
        mime_type=source.mime_type,
        size_bytes=source.size_bytes,
        content_sha256=source.content_sha256,
        status=source.status,
        error_message=source.error_message,
        tags=[tag.name for tag in source.tags],
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.get(
    "",
    response_model=SourceListResponse,
    summary="List all sources (notes, PDFs) with filters",
)
def list_sources_endpoint(
    kind: Optional[str] = Query(None, description="Filter by kind: note or pdf"),
    tag: Optional[str] = Query(None, description="Filter by tag name"),
    q: Optional[str] = Query(None, description="Search keyword"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset"),
    db: Session = Depends(get_db),
) -> SourceListResponse:
    """List all sources ordered by updated_at descending."""
    items, total = note_service.list_sources(
        db, kind=kind, tag=tag, q=q, limit=limit, offset=offset
    )
    return SourceListResponse(
        items=[to_source_response(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{source_id}",
    response_model=SourceResponse,
    summary="Get source details and content preview",
)
def get_source_endpoint(
    source_id: str, db: Session = Depends(get_db)
) -> SourceResponse:
    """Retrieve a single source by ID."""
    source = note_service.get_source(db, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    return to_source_response(source)


@router.delete(
    "/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a source by ID",
)
def delete_source_endpoint(source_id: str, db: Session = Depends(get_db)):
    """Delete source and cascade chunks and tags."""
    deleted = note_service.delete_source(db, source_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )
    return None


@router.get(
    "/{source_id}/chunks",
    response_model=ChunkListResponse,
    summary="List extracted chunks for a source",
)
def get_source_chunks_endpoint(
    source_id: str,
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset"),
    db: Session = Depends(get_db),
) -> ChunkListResponse:
    """Retrieve extracted chunks and page numbers for a source."""
    source = note_service.get_source(db, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found",
        )

    stmt = (
        select(Chunk)
        .where(Chunk.source_id == source_id)
        .order_by(Chunk.ordinal)
        .offset(offset)
        .limit(limit)
    )
    chunks = db.scalars(stmt).all()

    total_stmt = select(func.count(Chunk.id)).where(Chunk.source_id == source_id)
    total = db.scalar(total_stmt) or 0

    return ChunkListResponse(
        items=[
            ChunkResponse(
                id=c.id,
                source_id=c.source_id,
                ordinal=c.ordinal,
                page_number=c.page_number,
                text=c.text,
                token_estimate=c.token_estimate,
            )
            for c in chunks
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
