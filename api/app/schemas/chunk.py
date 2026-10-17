"""Pydantic schemas for extracted chunks."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ChunkResponse(BaseModel):
    id: str
    source_id: str
    ordinal: int
    page_number: Optional[int] = None
    text: str
    token_estimate: int

    model_config = ConfigDict(from_attributes=True)


class ChunkListResponse(BaseModel):
    items: List[ChunkResponse]
    total: int
    limit: int
    offset: int
