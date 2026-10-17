"""SQLAlchemy database models for sources, chunks, tags, and source-tag associations."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Index,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def generate_uuid() -> str:
    """Generate a random UUID4 string."""
    return str(uuid.uuid4())


# Association table for Many-to-Many relationship between sources and tags
source_tags = Table(
    "source_tags",
    Base.metadata,
    Column(
        "source_id",
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        String(36),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Source(Base):
    """Canonical source document or note."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 'note' or 'pdf'
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Raw canonical text for notes
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="text/plain")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # 'pending', 'indexed', 'failed'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="Chunk.ordinal",
    )
    tags: Mapped[List["Tag"]] = relationship(
        "Tag",
        secondary=source_tags,
        back_populates="sources",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_sources_kind_updated_at", "kind", "updated_at"),
    )


class Chunk(Base):
    """Page-aware chunk extracted from a source for vector search and citations."""

    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-based for PDF
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("source_id", "ordinal", name="uq_chunks_source_ordinal"),
    )


class Tag(Base):
    """Categorization tag for filtering sources."""

    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )

    # Relationships
    sources: Mapped[List["Source"]] = relationship(
        "Source",
        secondary=source_tags,
        back_populates="tags",
    )
