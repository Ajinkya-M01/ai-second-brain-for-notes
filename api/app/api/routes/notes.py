"""API route endpoints for Notes."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.note import NoteCreate, NoteResponse, NoteUpdate
from app.schemas.source import SourceListResponse, SourceResponse
from app.services import notes as note_service

router = APIRouter(prefix="/notes", tags=["notes"])


def to_note_response(source) -> NoteResponse:
    """Helper to convert Source DB model to NoteResponse DTO."""
    return NoteResponse(
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


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new note",
)
def create_note_endpoint(
    data: NoteCreate, db: Session = Depends(get_db)
) -> NoteResponse:
    """Create a new note, calculate content hash and store tags."""
    note = note_service.create_note(db, data)
    return to_note_response(note)


@router.get(
    "",
    response_model=SourceListResponse,
    summary="List notes with pagination and optional search/tag filter",
)
def list_notes_endpoint(
    tag: Optional[str] = Query(None, description="Filter by tag name"),
    q: Optional[str] = Query(None, description="Search keyword in title or content"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> SourceListResponse:
    """List notes ordered by updated_at descending."""
    items, total = note_service.list_sources(
        db, kind="note", tag=tag, q=q, limit=limit, offset=offset
    )
    return SourceListResponse(
        items=[
            SourceResponse(
                id=item.id,
                kind=item.kind,
                title=item.title,
                content=item.content,
                original_filename=item.original_filename,
                mime_type=item.mime_type,
                size_bytes=item.size_bytes,
                content_sha256=item.content_sha256,
                status=item.status,
                error_message=item.error_message,
                tags=[t.name for t in item.tags],
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Get a single note by ID",
)
def get_note_endpoint(
    note_id: str, db: Session = Depends(get_db)
) -> NoteResponse:
    """Retrieve full note by ID."""
    note = note_service.get_source(db, note_id)
    if not note or note.kind != "note":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    return to_note_response(note)


@router.patch(
    "/{note_id}",
    response_model=NoteResponse,
    summary="Update a note by ID",
)
def update_note_endpoint(
    note_id: str,
    data: NoteUpdate,
    db: Session = Depends(get_db),
) -> NoteResponse:
    """Update title, content, or tags of a note."""
    updated = note_service.update_note(db, note_id, data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    return to_note_response(updated)


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note by ID",
)
def delete_note_endpoint(note_id: str, db: Session = Depends(get_db)):
    """Delete note and all associated tag relationships."""
    deleted = note_service.delete_source(db, note_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found",
        )
    return None
