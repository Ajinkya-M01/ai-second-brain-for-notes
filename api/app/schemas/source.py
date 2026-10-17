"""Pydantic schemas for generic sources and paginated list responses."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SourceResponse(BaseModel):
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


class SourceListResponse(BaseModel):
    items: List[SourceResponse]
    total: int
    limit: int
    offset: int
