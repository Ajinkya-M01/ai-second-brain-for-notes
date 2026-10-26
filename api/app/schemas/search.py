"""Pydantic schemas for the search endpoint."""

from typing import List, Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(5, ge=1, le=20)
    source_ids: Optional[List[str]] = None


class SearchHit(BaseModel):
    chunk_id: str
    source_id: str
    title: str
    page_number: Optional[int] = None
    excerpt: str
    similarity: float


class SearchResponse(BaseModel):
    query: str
    hits: List[SearchHit]
    total: int
