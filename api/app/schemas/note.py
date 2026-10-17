"""Pydantic schemas for note operations."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Title of the note")
    content: str = Field(..., description="Markdown or text content")
    tags: List[str] = Field(default_factory=list, description="List of tag names")


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated title")
    content: Optional[str] = Field(None, description="Updated content")
    tags: Optional[List[str]] = Field(None, description="Updated list of tag names")


class NoteResponse(BaseModel):
    id: str
    kind: str
    title: str
    content: Optional[str] = None
    original_filename: Optional[str] = None
    mime_type: str
    size_bytes: int
    content_sha256: str
    status: str
    error_message: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
