"""Service layer for Notes and Sources operations."""

import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.db.models import Source, Tag
from app.schemas.note import NoteCreate, NoteUpdate


def get_or_create_tags(db: Session, tag_names: List[str]) -> List[Tag]:
    """Normalize tag names (lowercase, stripped) and retrieve or create Tag records."""
    normalized_names = list(
        {name.strip().lower() for name in tag_names if name.strip()}
    )
    if not normalized_names:
        return []

    # Fetch existing tags in bulk
    existing_tags = db.scalars(
        select(Tag).where(Tag.name.in_(normalized_names))
    ).all()
    existing_tag_map = {t.name: t for t in existing_tags}

    result: List[Tag] = []
    for name in normalized_names:
        if name in existing_tag_map:
            result.append(existing_tag_map[name])
        else:
            new_tag = Tag(name=name)
            db.add(new_tag)
            result.append(new_tag)

    return result


def create_note(db: Session, data: NoteCreate) -> Source:
    """Create a new note source with tags."""
    content_bytes = data.content.encode("utf-8")
    size_bytes = len(content_bytes)
    content_sha256 = hashlib.sha256(content_bytes).hexdigest()

    tags = get_or_create_tags(db, data.tags)

    note = Source(
        kind="note",
        title=data.title,
        content=data.content,
        mime_type="text/plain",
        size_bytes=size_bytes,
        content_sha256=content_sha256,
        status="pending",
        tags=tags,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_sources(
    db: Session,
    kind: Optional[str] = None,
    tag: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Source], int]:
    """List sources with optional filtering by kind, tag, and search query."""
    stmt = select(Source)

    if kind:
        stmt = stmt.where(Source.kind == kind)

    if tag:
        normalized_tag = tag.strip().lower()
        stmt = stmt.where(Source.tags.any(Tag.name == normalized_tag))

    if q:
        search_term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Source.title.ilike(search_term),
                Source.content.ilike(search_term),
            )
        )

    # Count total matching records
    count_stmt = select(func.count(func.distinct(Source.id)))
    if kind:
        count_stmt = count_stmt.where(Source.kind == kind)
    if tag:
        count_stmt = count_stmt.where(
            Source.tags.any(Tag.name == tag.strip().lower())
        )
    if q:
        count_stmt = count_stmt.where(
            or_(
                Source.title.ilike(f"%{q.strip()}%"),
                Source.content.ilike(f"%{q.strip()}%"),
            )
        )
    total = db.scalar(count_stmt) or 0

    # Apply ordering and pagination
    stmt = stmt.order_by(Source.updated_at.desc()).offset(offset).limit(limit)
    items = list(db.scalars(stmt).unique().all())

    return items, total


def get_source(db: Session, source_id: str) -> Optional[Source]:
    """Retrieve a single source by its ID."""
    return db.get(Source, source_id)


def update_note(
    db: Session, source_id: str, data: NoteUpdate
) -> Optional[Source]:
    """Update an existing note's title, content, or tags."""
    note = db.get(Source, source_id)
    if not note or note.kind != "note":
        return None

    if data.title is not None:
        note.title = data.title

    if data.content is not None:
        note.content = data.content
        content_bytes = data.content.encode("utf-8")
        note.size_bytes = len(content_bytes)
        note.content_sha256 = hashlib.sha256(content_bytes).hexdigest()
        # Mark status as pending re-indexing for future milestones
        note.status = "pending"

    if data.tags is not None:
        note.tags = get_or_create_tags(db, data.tags)

    note.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(note)
    return note


def delete_source(db: Session, source_id: str) -> bool:
    """Delete a source, all associated chunks and tag associations, and any uploaded file on disk."""
    from pathlib import Path
    from app.core.config import settings

    source = db.get(Source, source_id)
    if not source:
        return False

    # If it was an uploaded PDF, clean up the binary from data/uploads
    if source.kind == "pdf":
        file_path = Path(settings.UPLOAD_DIR) / f"{source_id}.pdf"
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass

    db.delete(source)
    db.commit()
    return True
